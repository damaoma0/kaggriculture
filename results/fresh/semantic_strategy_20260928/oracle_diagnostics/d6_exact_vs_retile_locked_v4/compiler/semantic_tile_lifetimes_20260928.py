"""Maturity-feasible anonymous crop lifetimes from daily semantic counts.

The integer program links a planting-date cohort to one first harvest (ongoing
crops only) and one release event, or a censored end-of-season survival. It uses
no future source coordinates, and never identifies a future event with an
original source tile. Initial cohorts use only the already-played opening.

Planting and release counts are hard equalities. In strict mode, the first
harvest marker is derived only from engine maturity and retained occupancy.
The earlier diagnostic extension can additionally impose recorded first-harvest
counts. The objective resolves otherwise anonymous assignments in favour of
ordinary crop lifespans and harvesting before abandoning an ongoing crop.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
FIRST = {"WHEAT": 2, "CARROT": 2, "MELON": 10, "TOMATO": 8, "STRAWBERRY": 10}
LAST_HARVEST = {"WHEAT": 4, "CARROT": 3, "MELON": 12, "TOMATO": 11, "STRAWBERRY": 16}
EXPIRY = {crop: age + 1 for crop, age in LAST_HARVEST.items()}
ONGOING = {"TOMATO", "STRAWBERRY"}
EVENT_FIELDS = {"harvest": "crop_end_counts", "remove": "crop_remove_counts", "disappear": "crop_disappear_counts"}


class LifetimeInfeasible(ValueError):
    pass


def initial_group(cell, tile, semantic):
    """An initial group is fully determined by public opening history."""
    birth = int(cell["planted_day"])
    prior = None
    if cell["crop"] in ONGOING:
        old_harvests = semantic["opening_plan"]["harv_tiles"]
        prior = next((d for d in range(birth + 1, int(semantic["handoff_day"]))
                      if int(tile) in old_harvests[d]), None)
    return birth, True, prior


def crop_groups(semantic, crop):
    groups = Counter()
    handoff, n = int(semantic["handoff_day"]), int(semantic["n"])
    for tile, cell in semantic["initial_state"]["tiles"].items():
        if cell.get("crop") == crop:
            groups[initial_group(cell, tile, semantic)] += 1
    for day in range(handoff, n):
        count = int(semantic["days"][day].get("plant_counts", {}).get(crop, 0))
        if count:
            groups[(day, False, None)] += count
    return sorted(groups.items(), key=lambda row: (row[0][0], row[0][1], -1 if row[0][2] is None else row[0][2]))


def solve_crop(semantic, crop, *, time_limit=15.0, enforce_lifespan=True, use_first_harvest_counts=False):
    """Return integer paths for one crop, with solver diagnostics.

    No first harvest is required for a cohort deliberately dug or lost before
    it produces. A previously harvested initial cohort cannot satisfy a new
    first-harvest count. Day-29 unknown disappearances are censored.
    """
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    from scipy.sparse import coo_array

    start_time = time.perf_counter()
    handoff, n = int(semantic["handoff_day"]), int(semantic["n"])
    groups = crop_groups(semantic, crop)
    if not groups:
        return [], {"crop": crop, "variables": 0, "seconds": 0.0, "status": "empty"}
    rows, rhs, row_index = [], [], {}

    def constraint(key, count):
        row_index[key] = len(rows)
        rows.append(key)
        rhs.append(float(count))

    for gi, (_, count) in enumerate(groups):
        constraint(("birth", gi), count)
    first_days = []
    if crop in ONGOING and use_first_harvest_counts:
        for day in range(handoff, n):
            count = int(semantic["days"][day].get("first_harvest_counts", {}).get(crop, 0))
            if count:
                first_days.append(day)
                constraint(("first", day), count)
    releases = []
    for kind, field in EVENT_FIELDS.items():
        for day in range(handoff, n):
            count = int((semantic["days"][day].get(field) or {}).get(crop, 0))
            if count:
                if kind == "harvest" and crop in ONGOING:
                    raise LifetimeInfeasible(f"{crop} has a one-time harvest-end count")
                releases.append((day, kind, count))
                constraint(("exit", day, kind), count)
    surviving = sum(count for _, count in groups) - sum(count for _, _, count in releases)
    if surviving < 0:
        raise LifetimeInfeasible(f"{crop}: releases exceed initial + future births")
    if surviving:
        releases.append((None, "censored", surviving))
        constraint(("exit", None, "censored"), surviving)

    columns, objective, r_indices, c_indices = [], [], [], []
    for gi, ((birth, initial, prior), group_count) in enumerate(groups):
        oldest_day = max(handoff, birth)
        choices = [prior] if prior is not None else [None]
        if crop in ONGOING and prior is None:
            if use_first_harvest_counts:
                choices += [d for d in first_days if d >= birth + FIRST[crop]
                            and (not enforce_lifespan or d <= birth + LAST_HARVEST[crop])]
            else:
                # Strict tiling never consults recorded ongoing harvest timing.
                # The lower layer may harvest the surviving cohort as soon as
                # its public planting date makes production available.
                earliest = max(handoff, birth + FIRST[crop])
                if earliest < n and (not enforce_lifespan or earliest <= birth + LAST_HARVEST[crop]):
                    choices.append(earliest)
        for first in choices:
            for release_day, kind, _ in releases:
                event_day = n - 1 if release_day is None else release_day
                if event_day < oldest_day:
                    continue
                # Harvest / DIG / disappearance of today's newly planted crop
                # cannot consume an older morning cohort. Actual seeded losses
                # can first occur on the second unwatered day.
                if release_day is not None and event_day <= birth:
                    continue
                if first is not None and first > event_day:
                    continue
                if crop in ONGOING and prior is None and not use_first_harvest_counts:
                    earliest = max(handoff, birth + FIRST[crop])
                    expected_first = earliest if earliest <= event_day and earliest < n else None
                    if first != expected_first:
                        continue
                age = event_day - birth
                if kind == "harvest" and age < FIRST[crop]:
                    continue
                if enforce_lifespan:
                    if kind == "harvest" and age > LAST_HARVEST[crop]:
                        continue
                    if kind == "remove" and age > EXPIRY[crop]:
                        continue
                    if kind == "disappear" and age > EXPIRY[crop]:
                        continue
                    if kind == "censored" and age > EXPIRY[crop]:
                        continue
                col = len(columns)
                columns.append({"crop": crop, "birth": birth, "initial": initial,
                                "prior_first_harvest": prior, "first_harvest": first,
                                "exit_day": release_day, "exit_type": kind})
                linked = [row_index[("birth", gi)], row_index[("exit", release_day, kind)]]
                if use_first_harvest_counts and first is not None and first >= handoff:
                    linked.append(row_index[("first", first)])
                r_indices.extend(linked)
                c_indices.extend([col] * len(linked))
                if kind == "harvest":
                    cost = (LAST_HARVEST[crop] - age) ** 2
                elif kind == "disappear":
                    cost = min((EXPIRY[crop] - age) ** 2, 0.25 + max(0, age - 2) ** 2)
                elif kind == "remove":
                    cost = 0.15 * (EXPIRY[crop] - age) ** 2
                else:
                    cost = 0.0
                if crop in ONGOING and first is None and age >= FIRST[crop]:
                    cost += 5.0
                if first is not None:
                    cost += 0.05 * max(0, first - birth - FIRST[crop]) ** 2
                # Deterministic tiny tie break depends on anonymous dates only.
                cost += 0.00001 * ((gi + 1) * (event_day + 3) + (first or 0))
                objective.append(cost)
    if not columns:
        raise LifetimeInfeasible(f"{crop}: no maturity/lifespan-feasible paths")
    matrix = coo_array((np.ones(len(r_indices)), (np.asarray(r_indices, dtype=np.int32), np.asarray(c_indices, dtype=np.int32))),
                       shape=(len(rows), len(columns))).tocsc()
    upper = max(count for _, count in groups)
    result = milp(np.asarray(objective), integrality=np.ones(len(columns)),
                  bounds=Bounds(np.zeros(len(columns)), np.full(len(columns), upper)),
                  constraints=LinearConstraint(matrix, rhs, rhs),
                  options={"time_limit": float(time_limit), "mip_rel_gap": 0.0, "presolve": True})
    if result.x is None:
        raise LifetimeInfeasible(f"{crop}: {result.message}; rows={len(rows)}, paths={len(columns)}")
    integer = np.rint(result.x).astype(int)
    if max(abs(result.x - integer), default=0) > 1e-5 or not np.array_equal(matrix @ integer, np.asarray(rhs)):
        raise LifetimeInfeasible(f"{crop}: solver did not return an exact integer count assignment")
    paths = [{**column, "count": int(count)} for column, count in zip(columns, integer) if count]
    return paths, {"crop": crop, "variables": len(columns), "constraints": len(rows),
                   "seconds": time.perf_counter() - start_time, "status": int(result.status),
                   "message": result.message, "objective": float(result.fun),
                   "enforce_lifespan": bool(enforce_lifespan),
                   "use_first_harvest_counts": bool(use_first_harvest_counts)}


def solve_lifetimes(semantic, *, time_limit=15.0, enforce_lifespan=True, use_first_harvest_counts=False):
    by_crop, diagnostics = {}, []
    for crop in FIRST:
        by_crop[crop], detail = solve_crop(semantic, crop, time_limit=time_limit, enforce_lifespan=enforce_lifespan,
                                         use_first_harvest_counts=use_first_harvest_counts)
        diagnostics.append(detail)
    result = {"schema_version": 1, "handoff_day": semantic["handoff_day"], "n": semantic["n"],
              "by_crop": by_crop, "diagnostics": diagnostics,
              "use_first_harvest_counts": bool(use_first_harvest_counts),
              "source": "Anonymous semantic counts and observed opening cohorts only"}
    validate_lifetimes(semantic, result)
    return result


def validate_lifetimes(semantic, result, use_first_harvest_counts=None):
    if use_first_harvest_counts is None:
        use_first_harvest_counts = result.get("use_first_harvest_counts", True)
    handoff, n = int(semantic["handoff_day"]), int(semantic["n"])
    for crop, paths in result["by_crop"].items():
        births, firsts, exits, groups = Counter(), Counter(), Counter(), Counter()
        for path in paths:
            birth, first, exit_day, count = path["birth"], path["first_harvest"], path["exit_day"], path["count"]
            assert isinstance(count, int) and count > 0
            groups[(birth, path["initial"], path["prior_first_harvest"])] += count
            if not path["initial"]:
                births[birth] += count
            if first is not None:
                assert first - birth >= FIRST[crop], (crop, path)
                if first >= handoff:
                    firsts[first] += count
                assert exit_day is None or first <= exit_day
            if exit_day is not None:
                exits[(exit_day, path["exit_type"])] += count
                if path["exit_type"] == "harvest":
                    assert exit_day - birth >= FIRST[crop]
        assert groups == Counter(dict(crop_groups(semantic, crop))), (crop, "birth groups")
        for day in range(handoff, n):
            row = semantic["days"][day]
            assert births[day] == row.get("plant_counts", {}).get(crop, 0), (crop, day, "plant")
            if use_first_harvest_counts:
                assert firsts[day] == row.get("first_harvest_counts", {}).get(crop, 0), (crop, day, "first")
            for kind, field in EVENT_FIELDS.items():
                assert exits[(day, kind)] == (row.get(field) or {}).get(crop, 0), (crop, day, kind)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--episodes", default="")
    parser.add_argument("--time-limit", type=float, default=15.0)
    parser.add_argument("--relax-lifespan", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--strict", action="store_true", help="Strict tile-change mode (the default)")
    mode.add_argument("--extended-first-harvest-counts", action="store_true",
                      help="Diagnostic extension: additionally impose copied future ongoing first-harvest counts")
    args = parser.parse_args()
    use_first_harvest_counts = args.extended_first_harvest_counts
    base = ROOT / "results/fresh/semantic_tile_20260928"
    source = args.inputs or base / ("semantic_inputs.json" if use_first_harvest_counts else "semantic_inputs_strict_clean.json")
    destination = args.out or base / ("anonymous_lifetimes_extended.json" if use_first_harvest_counts else "anonymous_lifetimes_strict_clean.json")
    worlds = json.loads(source.read_text(encoding="utf-8"))
    selected = set(args.episodes.split(",")) if args.episodes else set(worlds)
    result, failures = {}, {}
    started = time.perf_counter()
    for episode, semantic in worlds.items():
        if episode not in selected:
            continue
        try:
            result[episode] = solve_lifetimes(semantic, time_limit=args.time_limit, enforce_lifespan=not args.relax_lifespan,
                                              use_first_harvest_counts=use_first_harvest_counts)
            print(episode, "ok", round(sum(row["seconds"] for row in result[episode]["diagnostics"]), 3), flush=True)
        except LifetimeInfeasible as error:
            failures[episode] = str(error)
            print(episode, "INFEASIBLE", error, flush=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
    report = {"worlds": len(result), "failures": failures, "seconds": time.perf_counter() - started,
              "path": str(destination), "enforce_lifespan": not args.relax_lifespan,
              "use_first_harvest_counts": use_first_harvest_counts}
    destination.with_suffix(".report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
