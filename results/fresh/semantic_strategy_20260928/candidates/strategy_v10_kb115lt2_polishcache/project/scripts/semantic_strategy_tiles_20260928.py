"""Causal daily semantic decisions -> the validated strict spatial compiler.

Only the current official observation and our own earlier observations enter
this adapter. Future rows are policy forecasts, never a test-world recording.
It derives feasible anonymous lifecycle counts before invoking the unchanged
20260928 reuse allocator/compiler. The same API works at any morning handoff.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy

from semantic_tile_planner_20260928 import compile_plan, label
from semantic_tile_lifetimes_20260928 import FIRST, ONGOING

CROPS = tuple(FIRST)
ANIMALS = ("COW", "GOOSE", "SHEEP")
STRUCTURE = {"COW": "PASTURE", "SHEEP": "PASTURE", "GOOSE": "COOP"}
RELEASE_AGE = {"WHEAT": 3, "CARROT": 3, "MELON": 10, "TOMATO": 12, "STRAWBERRY": 17}
QUADRANTS = ("NW", "NE", "SW", "SE")


def empty_plan(n=30):
    return dict(n=n, plant=[{} for _ in range(n)], events=[],
                board=[[" ."] * 100 for _ in range(n)],
                struct_by_day=[{} for _ in range(n)],
                animals_by_day=[{} for _ in range(n)],
                harv_tiles=[[] for _ in range(n)], removals=[[] for _ in range(n)],
                hands=[0] * n, land_day={}, cum_sold=[{} for _ in range(n)])


def cells_from_farm(farm):
    cells = {}
    for y, row in enumerate(farm["tiles"]):
        for x, t in enumerate(row):
            i = str(10 * y + x)
            if t == "LOCKED":
                cells[i] = {"locked": True}
            elif isinstance(t, dict) and t.get("kind") == "PLANT":
                cells[i] = {"kind": "PLANT", "crop": t["crop"], "planted_day": int(t["planted_day"])}
            elif isinstance(t, dict) and t.get("kind") in ("PASTURE", "COOP"):
                cells[i] = {"kind": t["kind"]}
                if t.get("animal"):
                    cells[i].update(animal=t["animal"], placed_day=int(t["placed_day"]))
            else:
                cells[i] = {}
    return cells


def observe_own(obs, memory):
    """Record only already-observed public occupancy; keep no source identity."""
    step = int(obs["step"]); day, hour = divmod(step, 24)
    farm = obs["farms"][int(obs["player"])]
    cells = cells_from_farm(farm)
    prefix = memory.setdefault("observed_prefix", empty_plan())
    if hour == 0:
        prefix["board"][day] = [label(cells[str(i)]) for i in range(100)]
    prefix["hands"][day] = max(prefix["hands"][day], len(farm.get("hands", [])))
    previous = memory.get("last_cells", {})
    for tile, cell in cells.items():
        if cell.get("crop"):
            birth, crop = cell["planted_day"], cell["crop"]
            if birth <= day and (previous.get(tile, {}).get("crop"), previous.get(tile, {}).get("planted_day")) != (crop, birth):
                prefix["plant"][birth][tile] = crop
        if hour == 0 and day:
            if cell.get("kind") in ("COOP", "PASTURE"):
                prefix["struct_by_day"][day-1][tile] = cell["kind"]
            else:
                prefix["struct_by_day"][day-1].pop(tile, None)
            if cell.get("animal"):
                prefix["animals_by_day"][day-1][tile] = cell["animal"]
            else:
                prefix["animals_by_day"][day-1].pop(tile, None)
    for q in farm.get("unlocked_quadrants", ["NW"]):
        if q != "NW" and q not in prefix["land_day"]:
            prefix["land_day"][q] = max(0, (step - 1) // 24)
    prefix["events"] = [[d, int(t), crop] for d, row in enumerate(prefix["plant"]) for t, crop in row.items()]
    memory["last_cells"] = cells
    memory["last_step"] = step
    return memory


def _counts(value, allowed):
    return {key: max(0, int(value.get(key, 0))) for key in allowed if int(value.get(key, 0)) > 0}


def _row(day, hands=0):
    return dict(day=day, plant_counts={}, build_counts={}, remove_structure_counts={},
                animal_add_counts={}, animal_exit_counts={}, animal_retire_counts={},
                crop_end_counts={}, crop_remove_counts={}, crop_disappear_counts={},
                hands=hands, land_add_count=0, end_occupancy_counts=None)


def _retire_priority(animal, day):
    first, interval = {"COW": (8, 2), "SHEEP": (6, 3), "GOOSE": (4, 1)}[animal["species"]]
    birth = animal["birth"]
    remaining = sum(night+1-birth >= first and (night+1-birth-first) % interval == 0
                    for night in range(day, 29))
    return remaining, -birth


def build_plan(obs, proposal, memory=None, config=None):
    """Build a complete modelled suffix; only today's retirement is committed.

    The crop release calendar and capacity constraints are computed, so a donor's
    incompatible past cohort cannot be treated as part of the live farm. Public
    initial coordinates pass to the unchanged tiler; forecast events have none.
    """
    memory = memory if memory is not None else {}
    config = config or {}
    day = int(obs["step"]) // 24
    if int(obs["step"]) % 24:
        raise ValueError("semantic tile planning requires a morning observation")
    farm = obs["farms"][int(obs["player"])]
    cells = cells_from_farm(farm)
    prefix_all = memory.get("observed_prefix", empty_plan())
    prefix = deepcopy(prefix_all)
    for field in ("plant", "struct_by_day", "animals_by_day", "harv_tiles", "removals", "hands", "cum_sold"):
        prefix[field] = prefix[field][:day]
    prefix["board"] = prefix["board"][:day] + [[label(cells[str(i)]) for i in range(100)]]
    prefix["events"] = [e for e in prefix["events"] if e[0] < day]
    prefix["land_day"] = {q: d for q, d in prefix["land_day"].items() if d < day}
    for q in farm.get("unlocked_quadrants", ["NW"]):
        if q != "NW":
            prefix["land_day"].setdefault(q, max(0, day-1))

    # Existing ongoing cohorts have an engine-derived first-harvest opportunity,
    # not a copied DSM collection date. This is only a cohort interface marker.
    plant_paths = []
    age_map = dict(RELEASE_AGE, **config.get("release_age", {}))
    for tile, cell in cells.items():
        crop = cell.get("crop")
        if not crop:
            continue
        birth = cell["planted_day"]
        first = birth + FIRST[crop] if crop in ONGOING else None
        prior = first if first is not None and first < day else None
        if prior is not None:
            prefix["harv_tiles"][prior].append(int(tile))
        end = max(day, birth + age_map[crop])
        # Match the policy's public yield-readiness count. Same-age cohorts are
        # still assigned anonymously by the spatial compiler.
        if crop not in ONGOING and day-birth == age_map[crop] and day < 29:
            raw = farm["tiles"][int(tile)//10][int(tile)%10]
            max_age = {"WHEAT": 4, "CARROT": 3, "MELON": 12}[crop]
            projected = int(raw.get("yield_units", 0))
            if not raw.get("watered_today") and (max_age+1)//2 <= day-birth <= max_age:
                projected += 1+int(int(raw.get("fertilized_until_day", -1)) >= day)
            if projected < {"WHEAT": 5, "CARROT": 4, "MELON": 6}[crop]:
                end = day+1
                # This is a property of today's observed crop, not an anonymous
                # future event. Keep it attached to this initial tile so the
                # compiler cannot swap its delayed harvest with a ready peer.
                cell["harvest_not_before"] = day+1
        if crop not in ONGOING and birth + FIRST[crop] <= 29:
            end = min(end, 29)
        plant_paths.append(dict(crop=crop, birth=birth, initial=True,
                                prior_first_harvest=prior,
                                first_harvest=first if first is not None and first < 30 else None,
                                exit_day=end if end < 30 else None,
                                exit_type=("remove" if crop in ONGOING else "harvest") if end < 30 else "censored", count=1))

    animals = []
    committed = memory.get("retirements", {})
    for tile, cell in cells.items():
        if not cell.get("animal"):
            continue
        a = dict(species=cell["animal"], birth=cell["placed_day"], retiring=None)
        old = committed.get(tile)
        if old and (old["animal"], old["placed_day"]) == (a["species"], a["birth"]):
            raw = farm["tiles"][int(tile)//10][int(tile)%10]
            start = day-1 if int(raw.get("consecutive_unfed", 0)) >= 1 else day
            cell["retiring_since"] = start
            a["retiring"] = start
        animals.append(a)
    structures = Counter(c["kind"] for c in cells.values() if c.get("kind") in ("COOP", "PASTURE"))
    unlocked = len(farm.get("unlocked_quadrants", ["NW"]))
    rows = [_row(d) for d in range(30)]
    forecast = {int(r["day"]): r for r in proposal.get("forecast", [])}
    forecast[day] = dict(proposal["today"], day=day)
    warnings = []

    for d in range(day, 30):
        request = forecast.get(d, {})
        row = rows[d]
        row["hands"] = min(15, max(0, int(request.get("hands", 10))))
        want_land = max(unlocked, min(4, int(request.get("target_land_count", unlocked))))
        additions = min(4-unlocked, max(int(request.get("land_add_count", 0)), want_land-unlocked))
        row["land_add_count"] = additions
        unlocked += additions
        for p in plant_paths:
            if p["exit_day"] == d:
                field = "crop_remove_counts" if p["exit_type"] == "remove" else "crop_end_counts"
                row[field][p["crop"]] = row[field].get(p["crop"], 0) + 1
        survivors = [p for p in plant_paths if p["birth"] <= d and (p["exit_day"] is None or p["exit_day"] > d)]
        # Both retirement days retain their pen until the evening exit.
        for species, amount in _counts(request.get("animal_retire_counts", {}), ANIMALS).items():
            candidates = [a for a in animals if a["species"] == species and a["retiring"] is None]
            take = sorted(candidates, key=lambda a: _retire_priority(a, d))[:amount]
            row["animal_retire_counts"][species] = len(take)
            for a in take:
                a["retiring"] = d
        empty = structures.copy()
        empty.subtract(STRUCTURE[a["species"]] for a in animals)
        slots = unlocked * 25 - len(survivors) - sum(structures.values())
        for kind in ("PASTURE", "COOP"):
            remove = min(max(0, empty[kind]),
                         max(0, int(request.get("remove_structure_counts", {}).get(kind, 0))))
            if remove:
                row["remove_structure_counts"][kind] = remove
                structures[kind] -= remove; empty[kind] -= remove; slots += remove
        for species, amount in _counts(request.get("animal_add_counts", {}), ANIMALS).items():
            kind = STRUCTURE[species]
            actual = min(amount, max(0, empty[kind]) + max(0, slots))
            build = max(0, actual - max(0, empty[kind]))
            structures[kind] += build; slots -= build
            empty[kind] = max(0, empty[kind]-actual)
            if build:
                row["build_counts"][kind] = row["build_counts"].get(kind, 0) + build
            if actual:
                row["animal_add_counts"][species] = actual
                animals.extend(dict(species=species, birth=d, retiring=None) for _ in range(actual))
            if actual < amount:
                warnings.append(dict(day=d, kind="animal_capacity_clip", species=species, requested=amount, actual=actual))
        wanted = _counts(request.get("plant_counts", {}), CROPS)
        for crop in list(wanted):
            if d + FIRST[crop] > 29:
                wanted.pop(crop)
        # Empty pens can be turned into crops; an occupied retiring pen cannot.
        shortage = max(0, sum(wanted.values())-slots)
        for kind in ("PASTURE", "COOP"):
            remove = min(max(0, empty[kind]), shortage)
            if remove:
                row["remove_structure_counts"][kind] = row["remove_structure_counts"].get(kind, 0)+remove
                structures[kind] -= remove; slots += remove; shortage = max(0, shortage-remove)
        priorities = request.get("plant_priority", ["STRAWBERRY", "TOMATO", "MELON", "CARROT", "WHEAT"])
        priorities = list(dict.fromkeys(list(priorities)+list(CROPS)))
        for crop in priorities:
            amount = wanted.get(crop, 0)
            actual = min(amount, max(0, slots)); slots -= actual
            if actual:
                row["plant_counts"][crop] = actual
                end = d + age_map[crop]
                if crop not in ONGOING:
                    end = min(end, 29)
                first = d + FIRST[crop] if crop in ONGOING else None
                plant_paths.extend(dict(crop=crop, birth=d, initial=False,
                                        prior_first_harvest=None,
                                        first_harvest=first if first is not None and first < 30 else None,
                                        exit_day=end if end < 30 else None,
                                        exit_type=("remove" if crop in ONGOING else "harvest") if end < 30 else "censored", count=1)
                                   for _ in range(actual))
            if actual < amount:
                warnings.append(dict(day=d, kind="crop_capacity_clip", crop=crop, requested=amount, actual=actual))
        leaving = [a for a in animals if a["retiring"] is not None and a["retiring"] + 1 == d]
        row["animal_exit_counts"] = dict(Counter(a["species"] for a in leaving))
        animals = [a for a in animals if a not in leaving]
        empty_at_end = structures.copy()
        empty_at_end.subtract(STRUCTURE[a["species"]] for a in animals)
        crop_totals = Counter(p["crop"] for p in plant_paths if p["birth"] <= d and (p["exit_day"] is None or p["exit_day"] > d))
        row["end_occupancy_counts"] = dict(crops=dict(crop_totals), structures=dict(+structures),
                                            animals=dict(Counter(a["species"] for a in animals)),
                                            empty_structures=dict(+empty_at_end), locked=100-25*unlocked,
                                            empty_or_weed=25*unlocked-sum(crop_totals.values())-sum(structures.values()))

    semantic = dict(schema_version=2, semantic_scope="tile_changes_only", n=30, handoff_day=day,
                    initial_state=dict(day=day, tiles=cells, board=prefix["board"][day],
                                       unlocked_quadrants=list(farm.get("unlocked_quadrants", ["NW"]))),
                    opening_plan=prefix, days=rows)
    by_crop = {crop: [p for p in plant_paths if p["crop"] == crop] for crop in CROPS}
    paths = dict(by_crop=by_crop, use_first_harvest_counts=False, diagnostics=[],
                 source="Policy forecast and observed crop birthdays; no recorded future")
    plan = compile_plan(semantic, variant="reuse", lifetimes=paths)
    today = plan["planner_metadata"]["daily"][0]
    # A forecasted exit is not an observed exit. Keep the intention until the
    # next actual board confirms disappearance, including an unexpected feed.
    retired_cells = {tile: c for tile, c in cells.items()
                     if c.get("animal") and "retiring_since" in c}
    retired_cells.update({tile: c for tile, c in today["tiles"].items()
                         if c.get("animal") and "retiring_since" in c})
    memory["retirements"] = {tile: dict(animal=c["animal"], placed_day=c["placed_day"],
                                        first_unfed_day=c["retiring_since"])
                            for tile, c in retired_cells.items()}
    return plan, memory, dict(capacity_adjustments=warnings, semantic_today=rows[day],
                              today=today, forecast_counts=rows[day:])
