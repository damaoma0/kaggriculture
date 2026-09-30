"""Exact-engine diagnostic for ten frozen nearest-donor three-day windows.

The target world, shop schedule, and opponent stream remain the target tape.
Only the target seat's actions in [D*24,(D+3)*24) are replaced by the
recorded donor seat actions.  This is a bounded counterfactual diagnostic,
not a continuation policy or a full-season claim.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import research_labour_profit as R  # noqa: E402

OUT = ROOT / "results" / "fresh" / "tape_gap_plans"
PRODUCTS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_compact(path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def raw_actions(path):
    raw = read_json(path)
    # Official raw replay steps are observations at t with the action that
    # advances t -> t+1.  There are 720 states and 719 executable actions.
    assert len(raw["steps"]) == 720, path
    return [[deepcopy(raw["steps"][t + 1][seat].get("action") or {}) for t in range(719)] for seat in range(2)]


def production(work, seat, start=0, stop=10**9):
    out = Counter()
    for item in work:
        if item["seat"] != seat or not start <= item["t"] < stop or not item["cmd"]:
            continue
        if item["cmd"][0] in ("HARVEST", "COLLECT_FERTILIZER"):
            for product, amount in item["delta"].items():
                if product in PRODUCTS and amount > 0:
                    out[product] += amount
    return {p: int(out[p]) for p in PRODUCTS}


def asset_counts(state, seat):
    out = Counter()
    for row in state[0].observation.farms[seat]["tiles"]:
        for tile in row:
            if isinstance(tile, dict):
                item = tile.get("crop") or tile.get("animal")
                if item:
                    out[item] += 1
    return dict(out)


def placement_counts(work, seat, start=0, stop=10**9):
    out = Counter()
    for item in work:
        if item["seat"] != seat or not start <= item["t"] < stop or not item["cmd"]:
            continue
        cmd = item["cmd"]
        if cmd[0] == "PLANT" and len(cmd) > 1:
            out["crop:" + str(cmd[1])] += 1
        elif cmd[0] == "PLACE" and len(cmd) > 1:
            out["place"] += 1
        elif cmd[0] == "BUY_PRODUCT" and len(cmd) > 1 and cmd[1] in ("COW", "SHEEP", "GOOSE"):
            out["animal:" + str(cmd[1])] += 1
    return dict(out)


def money_delta(state, seat):
    # KaggleStruct attribute values can lag the dictionary after a run.
    return float(state[0].observation.farms[seat]["money"])


def run_case(case, donor_raw):
    episode = str(case["episode"])
    day = int(case["day"])
    seat = int(case["seat"])
    start, stop = day * 24, min((day + 3) * 24, 719)
    own_path = ROOT / "data" / "ladder_panel" / "56395605" / f"{episode}.json.gz"
    own_game = load_compact(own_path)
    assert int(own_game["episode"]) == int(episode)
    original = [deepcopy(own_game["our_actions"] if i == int(own_game["seat"]) else own_game["opp_actions"]) for i in range(2)]
    donor = raw_actions(donor_raw)
    donor_seat = int(case["source"]["donor_seat"])
    borrowed = deepcopy(original)
    borrowed[seat][start:stop] = deepcopy(donor[donor_seat][start:stop])

    # The downloaded UMG compact tape is an independent action-record check.
    # Its own action list must agree with raw steps[t+1] for this window.
    compact_donor_path = ROOT / "data" / "mg_tapes" / str(case["source"]["donor_submission"]) / f"{case['source']['donor_episode']}.json.gz"
    donor_alignment = None
    if compact_donor_path.exists():
        compact_donor = load_compact(compact_donor_path)
        compact_actions = compact_donor.get("actions") or compact_donor.get("our_actions")
        if compact_actions is not None:
            donor_alignment = donor[donor_seat][start:stop] == compact_actions[start:stop]
            assert donor_alignment, ("donor raw/compact action mismatch", episode, day)

    # Use separate simulator instances: run() advances/mutates its state.
    with R.Simulator(own_game) as sim:
        baseline = sim.run(sim.initial, 0, stop, original, capture=True, snapshots=True)
    with R.Simulator(own_game) as sim:
        counter = sim.run(sim.initial, 0, stop, borrowed, capture=True, snapshots=True)

    assert baseline["state"][seat].status == "ACTIVE" or stop == 719
    assert counter["state"][seat].status == "ACTIVE" or stop == 719
    base_prod = production(baseline["work"], seat, start, stop)
    cf_prod = production(counter["work"], seat, start, stop)
    base_assets, cf_assets = asset_counts(baseline["state"], seat), asset_counts(counter["state"], seat)
    lost = {k: max(0, base_assets.get(k, 0) - cf_assets.get(k, 0)) for k in base_assets}
    assert base_prod == {p: int(case["source"]["actual"].get(p, 0)) for p in PRODUCTS}, (episode, day, base_prod, case["source"]["actual"])
    return {
        "episode": int(episode), "seat": seat, "day": day, "window_steps": [start, stop],
        "donor_episode": int(case["source"]["donor_episode"]), "donor_seat": donor_seat,
        "donor_submission": int(case["source"]["donor_submission"]),
        "baseline_cash_at_stop": money_delta(baseline["state"], seat),
        "borrowed_cash_at_stop": money_delta(counter["state"], seat),
        "cash_delta_borrowed_minus_baseline": money_delta(counter["state"], seat) - money_delta(baseline["state"], seat),
        "baseline_output": base_prod, "borrowed_output": cf_prod,
        "borrowed_minus_baseline_output": {p: cf_prod[p] - base_prod[p] for p in PRODUCTS},
        "donor_recorded_next3_output": case["source"]["donor_output"],
        "target_recorded_next3_output": case["source"]["actual"],
        "baseline_terminal_assets": base_assets, "borrowed_terminal_assets": cf_assets,
        "asset_count_deficit_at_stop": {k: v for k, v in lost.items() if v},
        "baseline_placements_in_window": placement_counts(baseline["work"], seat, start, stop),
        "borrowed_placements_in_window": placement_counts(counter["work"], seat, start, stop),
        "donor_raw_matches_compact_window": donor_alignment,
        "donor_action_window_sha256": __import__("hashlib").sha256(json.dumps(donor[donor_seat][start:stop], sort_keys=True).encode()).hexdigest(),
    }


def main():
    payload = read_json(OUT / "local_transfer.json")
    cases = payload["cases"][:10]
    dataset_paths = [ROOT / "results" / "fresh" / "cumulative_planning" / "dataset_train.json",
                     ROOT / "results" / "fresh" / "cumulative_planning" / "dataset_test.json"]
    donor_paths = {}
    for ds in dataset_paths:
        for row in read_json(ds)["games"]:
            donor_paths[(int(row["episode"]), int(row["seat"]))] = Path(row["source_raw"])
    rows, failures = [], []
    for case in cases:
        key = (int(case["source"]["donor_episode"]), int(case["source"]["donor_seat"]))
        try:
            rows.append(run_case(case, donor_paths[key]))
        except Exception as exc:
            failures.append({"episode": case["episode"], "day": case["day"], "error": repr(exc)})
    result = {
        "schema_version": 1, "diagnostic": "exact target-world three-day donor action transplant",
        "audit_correction": "cash and tile reads use farm dictionary subscripts; KaggleStruct numeric attributes can be stale after Simulator.run",
        "cases_requested": len(cases), "cases_completed": len(rows), "failures": failures,
        "shop_path": "target compact tape schedule; no future donor shop observations used",
        "results": rows,
    }
    out = OUT / "nearest_donor_windows.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    (OUT / "nearest_donor_windows_summary.md").write_text(
        "# Nearest donor window diagnostic\n\n"
        f"Completed {len(rows)}/{len(cases)} frozen cases with exact engine execution. "
        "The donor own-seat actions replace only the target three-day window; target shops and opponent actions remain fixed. "
        "This is a production diagnostic, not an adaptive-policy or full-season claim.\n",
        encoding="utf-8")
    print(json.dumps({"completed": len(rows), "failures": failures, "output": str(out)}, indent=2))


if __name__ == "__main__":
    main()
