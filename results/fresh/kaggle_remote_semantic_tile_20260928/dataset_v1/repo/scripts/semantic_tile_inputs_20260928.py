"""Extract coordinate-free daily changes from the 40 cash-verified DSM recordings.

No gameplay is run. Future tile coordinates appear only in exact_tile_audit.json.
The planner receives an actual day-11 starting board / opening prefix and counts
of successful daily changes, never source tile identities or future cohort links.

Animal retirement starts on the first of the two final unfed days; occupancy
ends after the following night. A final-day omission without an observed escape
is explicitly censored, rather than being declared an observed exit.

The original extractor's hires_arrived is shifted by one day, and its final
hands_present is zero because the season ends before the final midnight. Use
hands_present through day 28 and the shifted successful hires on day 29.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PANEL = ROOT / "results/fresh/threads_20260928/panel_dsm40b.txt"
DEFAULT_OUT = ROOT / "results/fresh/semantic_tile_20260928"
LABEL_CROP = {"WH": "WHEAT", "CA": "CARROT", "TO": "TOMATO", "ST": "STRAWBERRY", "ME": "MELON"}
ONGOING = {"TOMATO", "STRAWBERRY"}
KINDS = set(LABEL_CROP.values()) | {"COW", "SHEEP", "GOOSE", "COOP", "PASTURE"}


def counts(items):
    return dict(sorted(Counter(items).items()))


def _intmap(row):
    return {int(t): v for t, v in row.items()}


def read_panel(path):
    return [g.strip().split(":") for g in Path(path).read_text(encoding="utf-8").strip().split(",") if g.strip()]


def load_executor():
    spec = importlib.util.spec_from_file_location("semantic_tile_frozen_executor", ROOT / "agents/mgt_lead_kb115lt.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def initial_state(sem, exact, handoff_day):
    """Coordinates here describe only the already-played opening, observable now."""
    planted, placed = {}, {}
    for d in range(handoff_day):
        for crop, tiles in sem["days"][d]["planted"].items():
            for tile in tiles:
                planted[int(tile)] = (crop, d)
        for tile in sem["days"][d]["animals"]["placed"]:
            placed[int(tile)] = d
    board = list(exact["board"][handoff_day])
    crops = {}
    for tile, label in enumerate(board):
        if label in LABEL_CROP:
            crop = LABEL_CROP[label]
            assert tile in planted and planted[tile][0] == crop, (tile, crop, planted.get(tile))
            crops[str(tile)] = {"crop": crop, "planted_day": planted[tile][1]}
    structs = _intmap(exact["struct_by_day"][handoff_day - 1])
    animals = _intmap(exact["animals_by_day"][handoff_day - 1])
    return {
        "day": handoff_day,
        "board": board,
        "crops": crops,
        "structures": {str(t): s for t, s in sorted(structs.items())},
        "animals": {str(t): {"species": s, "placed_day": placed[t]} for t, s in sorted(animals.items())},
        "unlocked_quadrants": [q for q in ("NW", "NE", "SW", "SE") if q == "NW" or exact["land_day"].get(q, 99) < handoff_day],
    }


def opening_prefix(exact, handoff_day):
    result = {"n": exact["n"]}
    for key in ("plant", "struct_by_day", "animals_by_day", "harv_tiles", "removals", "hands", "cum_sold"):
        result[key] = deepcopy(exact[key][:handoff_day])
    result["board"] = deepcopy(exact["board"][:handoff_day + 1])
    result["events"] = [deepcopy(e) for e in exact["events"] if int(e[0]) < handoff_day]
    result["land_day"] = {q: d for q, d in exact["land_day"].items() if int(d) < handoff_day}
    return result


def occupancy(board, structs, animals):
    return {
        "crops": counts(LABEL_CROP[label] for label in board if label in LABEL_CROP),
        "structures": counts(structs.values()),
        "animals": counts(animals.values()),
        "empty_structures": counts(kind for tile, kind in structs.items() if tile not in animals),
        "locked": board.count(" L"),
        "empty_or_weed": board.count(" ."),
    }


def extract_game(sem, exact, handoff_day=11):
    """Return (planner_input, coordinateful_audit); neither mutates its inputs."""
    days, n = sem["days"], int(exact["n"])
    assert len(days) == n
    assert sem["meta"]["cash_match"], "Only cash-reproduced source recordings are eligible"
    structs = [_intmap(row) for row in exact["struct_by_day"]]
    animals = [_intmap(row) for row in exact["animals_by_day"]]
    retire = [Counter() for _ in range(n)]
    retiring_tiles = [[] for _ in range(n)]
    exits = [Counter() for _ in range(n)]
    animal_add = [Counter() for _ in range(n)]
    retire_errors = []
    for d in range(n):
        before = animals[d - 1] if d else {}
        for tile, species in animals[d].items():
            if before.get(tile) != species:
                animal_add[d][species] += 1
        # The source only supplies the end-of-day boundary through day 28.
        if d >= n - 1:
            continue
        for tile, species in before.items():
            if animals[d].get(tile) == species:
                continue
            exits[d][species] += 1
            first_unfed = d - 1
            if first_unfed < 0 or any(tile in days[k]["maintenance"].get("FEED", []) for k in (first_unfed, d)):
                retire_errors.append({"exit_day": d, "tile": tile, "species": species})
            else:
                retire[first_unfed][species] += 1
                retiring_tiles[first_unfed].append({"tile": tile, "species": species, "exit_day": d})
    assert not retire_errors, ("Animal exit without two final unfed days", retire_errors)

    rows, audit_rows = [], []
    for d, source in enumerate(days):
        board = exact["board"][d]
        end_known = d + 1 < n
        end = exact["board"][d + 1] if end_known else None
        prev_struct = structs[d - 1] if d else {}
        plant = counts(c for c, ts in source["planted"].items() for _ in ts)
        build = counts("COOP" if op == "BUILD_COOP" else "PASTURE" for op, ts in source["built"].items() for _ in ts)
        remove_struct = counts(kind for tile, kind in prev_struct.items() if structs[d].get(tile) != kind)
        harvest_ends = counts(LABEL_CROP[board[int(t)]] for t in exact["harv_tiles"][d]
                              if board[int(t)] in LABEL_CROP and LABEL_CROP[board[int(t)]] not in ONGOING)
        first_harvest = counts(LABEL_CROP[board[int(t)]] for t in exact["harv_tiles"][d]
                              if board[int(t)] in LABEL_CROP and LABEL_CROP[board[int(t)]] in ONGOING)
        crop_remove = counts(row[1] for row in exact["removals"][d])
        disappear = None
        if end_known:
            disappear = Counter(LABEL_CROP[l] for l in board if l in LABEL_CROP)
            disappear.update(plant)
            disappear.subtract(harvest_ends)
            disappear.subtract(crop_remove)
            disappear.subtract(Counter(LABEL_CROP[l] for l in end if l in LABEL_CROP))
            assert min(disappear.values(), default=0) >= 0, (sem["meta"]["episode"], d, disappear)
            disappear = dict(sorted((c, k) for c, k in disappear.items() if k))
        # All hired hands disappear each midnight (engine _end_of_day), so this
        # is successful daily hires, not a difference between consecutive days.
        hires = int(source["labour"]["hands_present"])
        if d == n - 1:
            hires = int(days[d - 1]["labour"]["hires_arrived"])
        row = {
            "day": d,
            "plant_counts": plant,
            "build_counts": build,
            "remove_structure_counts": remove_struct,
            "animal_add_counts": dict(sorted(animal_add[d].items())),
            "animal_exit_counts": dict(sorted(exits[d].items())),
            "animal_retire_counts": dict(sorted(retire[d].items())),
            "crop_end_counts": harvest_ends,
            "first_harvest_counts": first_harvest,
            "crop_remove_counts": crop_remove,
            "crop_disappear_counts": disappear,
            "hands": hires,
            "land_add_count": sum(int(day) == d for day in exact["land_day"].values()),
            "end_occupancy_counts": occupancy(end, structs[d], animals[d]) if end_known else None,
        }
        rows.append(row)
        audit_rows.append({
            "day": d, "end_boundary_observed": end_known,
            "board_start": board, "board_end": end,
            "retiring_animals": retiring_tiles[d],
            "physically_present_animals_end": {str(t): a for t, a in animals[d].items()} if end_known else None,
            "source_hands_present": source["labour"]["hands_present"], "successful_daily_hires": hires,
        })

    terminal_unfed = []
    for tile, species in animals[-1].items():
        if tile not in days[-1]["maintenance"].get("FEED", []):
            terminal_unfed.append({"tile": tile, "species": species,
                                   "also_unfed_previous_day": tile not in days[-2]["maintenance"].get("FEED", [])})
    result = {
        "schema_version": 1, "n": n, "handoff_day": handoff_day,
        "initial_state": initial_state(sem, exact, handoff_day),
        "opening_plan": opening_prefix(exact, handoff_day),
        "days": rows,
        "terminal_unfed_counts": counts(r["species"] for r in terminal_unfed),
        "terminal_two_unfed_counts": counts(r["species"] for r in terminal_unfed if r["also_unfed_previous_day"]),
    }
    assert_coordinate_free_days(result)
    audit = {"meta": deepcopy(sem["meta"]), "exact_interface": deepcopy(exact), "days": audit_rows,
             "terminal_unfed_animals": terminal_unfed,
             "limitations": ["Final day ends at hour 23 observation; day-29 midnight is not executed.",
                             "Day-29 end occupancy is unknown in the semantic archive and is not invented.",
                             "Terminal no-feed without observed exit is censored, not a confirmed animal exit.",
                             "Original TilePlanView hands[29] is 0; semantic daily hires corrects this archive endpoint bug."]}
    return result, audit


def assert_coordinate_free_days(game):
    """Strict schema validator: no future tile keys, sequences, cohort IDs or positions."""
    mappings = {"plant_counts", "build_counts", "remove_structure_counts", "animal_add_counts", "animal_exit_counts",
                "animal_retire_counts", "crop_end_counts", "first_harvest_counts", "crop_remove_counts", "crop_disappear_counts"}
    allowed = mappings | {"day", "hands", "land_add_count", "end_occupancy_counts"}
    for row in game["days"]:
        assert set(row) == allowed
        for field in mappings:
            val = row[field]
            if val is None:
                assert field == "crop_disappear_counts" and row["day"] == game["n"] - 1
                continue
            assert set(val) <= KINDS
            assert all(isinstance(k, int) and k >= 0 for k in val.values())
        occ = row["end_occupancy_counts"]
        if occ is not None:
            assert set(occ) == {"crops", "structures", "animals", "empty_structures", "locked", "empty_or_weed"}
            for key in ("crops", "structures", "animals", "empty_structures"):
                assert set(occ[key]) <= KINDS
                assert all(isinstance(k, int) and k >= 0 for k in occ[key].values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    executor = load_executor()
    inputs, audits, source_hashes = {}, {}, {}
    for team, episode in read_panel(args.panel):
        path = ROOT / "data/leader_semantics" / team / f"{episode}.json.gz"
        sem = json.loads(gzip.decompress(path.read_bytes()))
        exact = executor.TilePlanView(executor.Target(sem)).to_dict()
        inputs[episode], audits[episode] = extract_game(sem, exact)
        source_hashes[episode] = hashlib.sha256(path.read_bytes()).hexdigest()
    args.out.mkdir(parents=True, exist_ok=True)
    for name, payload in (("semantic_inputs.json", inputs), ("exact_tile_audit.json", audits)):
        (args.out / name).write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    report = {
        "world_count": len(inputs), "all_cash_verified": True, "full_games_executed": 0,
        "future_coordinates_in_planner_input": False,
        "opening_coordinates": "Observed day-11 state and replayed days 0-10 only",
        "engine_source": ".venv/Lib/site-packages/kaggle_environments/envs/kaggriculture/kaggriculture.py",
        "engine_retirement_rule": "Animal escapes after two consecutive unfed end-of-day refreshes; structure remains.",
        "source_sha256": source_hashes,
        "semantic_sha256": hashlib.sha256((args.out / "semantic_inputs.json").read_bytes()).hexdigest(),
        "day29_hires_corrections": {ep: {"old": a["exact_interface"]["hands"][-1], "actual": inputs[ep]["days"][-1]["hands"]}
                                   for ep, a in audits.items()},
        "confirmed_retirements_from_handoff": sum(sum(d["animal_retire_counts"].values()) for g in inputs.values() for d in g["days"][11:]),
    }
    (args.out / "extraction_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in ("source_sha256", "day29_hires_corrections")}, indent=2))


if __name__ == "__main__":
    main()
