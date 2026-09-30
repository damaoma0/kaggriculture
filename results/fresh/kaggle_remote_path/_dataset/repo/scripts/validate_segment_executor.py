"""Native-engine smoke validation for a deterministic sample of donor segments.

This is intentionally a narrow harness.  It starts from the source replay's
official state at each donor boundary, runs the portable executor for 72 turns
against a PASS rival, and records outcomes/rejections.  It does not modify the
executor or claim that replaying an own donor is an online benchmark.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "results/fresh/segment_stitch/library.json"
OUT = ROOT / "results/fresh/segment_stitch/native_validation.json"
EXECUTOR_HASH_PATH = ROOT / "scripts/fragments/segment_job_executor.py"
DATA = ROOT / "results/fresh/cumulative_planning"
PRODUCTS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")


def read(path): return json.loads(path.read_text(encoding="utf-8"))


def selected_nodes(nodes):
    result = []
    for day in (12, 15, 18, 21, 24, 27):
        candidates = [n for n in nodes if n["day"] == day]
        candidates.sort(key=lambda n: hashlib.sha256(n["id"].encode()).hexdigest())
        result.extend(candidates[:2])
    assert len(result) == 12
    return result


def raw_lookup():
    paths = list((DATA / "raw_replays").glob("episode-*-replay.json"))
    found = {int(p.name.split("-")[1]): p for p in paths}
    # The rich source path is authoritative when a replay was kept outside the
    # copied raw_replays panel; together these cover all 105 library episodes.
    for dataset in (DATA / "dataset_train.json", DATA / "dataset_test.json"):
        for game in read(dataset)["games"]:
            if int(game.get("submission", -1)) != 56266758:
                continue
            path = Path(game.get("source_raw", ""))
            if path.exists(): found[int(game["episode"])] = path
    return found


def recorded_actions(raw):
    # Replay action at t+1 was issued for observation t; Simulator indexes t.
    return [[deepcopy(raw["steps"][t + 1][seat].get("action", {})) for t in range(719)] for seat in (0, 1)]


def shops_by_day(raw):
    return [list(raw["steps"][min(day * 24, 719)][0]["observation"]["town"]["unlocked_shops"])
            for day in range(31)]


def cohort(farm):
    c = Counter()
    for row in farm.get("tiles", []):
        for t in row:
            if t is None: c["EMPTY"] += 1
            elif t == "LOCKED": c["LOCKED"] += 1
            elif isinstance(t, dict):
                if t.get("kind") == "PLANT": c["PLANT:" + str(t.get("crop"))] += 1
                elif t.get("animal"): c["ANIMAL:" + str(t.get("animal"))] += 1
                else: c["STRUCTURE:" + str(t.get("kind"))] += 1
    return c


def differences(expected, actual):
    return {k: actual.get(k, 0) - expected.get(k, 0) for k in sorted(set(expected) | set(actual))
            if actual.get(k, 0) != expected.get(k, 0)}


def tile_state_differences(expected_farm, actual_farm):
    """Concise coordinate-level end-state delta, including age/care/yield fields."""
    out = []
    for y, (erow, arow) in enumerate(zip(expected_farm.get("tiles", []), actual_farm.get("tiles", []))):
        for x, (expected, actual) in enumerate(zip(erow, arow)):
            if expected != actual:
                out.append({"tile": [x, y], "expected": expected, "actual": actual})
    return out


def harvest_inventory_delta(work, seat):
    # Matches the label extractor: successful HARVEST/COLLECT_FERTILIZER
    # inventory deltas only.  It deliberately excludes purchases and sales.
    out = Counter()
    for row in work:
        if row["seat"] != seat or not row.get("cmd"):
            continue
        if row["cmd"][0] not in ("HARVEST", "COLLECT_FERTILIZER"):
            continue
        for product, delta in row.get("delta", {}).items():
            if product in PRODUCTS and delta > 0:
                out[product] += delta
    return {p: int(out[p]) for p in PRODUCTS}


def add_capacity_sales(action, observation, executor_state):
    """Sell only shed surplus beyond this day's still-declared physical inputs."""
    day = int(observation.get("day", 0)) - int(executor_state.get("start_day", 0))
    hour = int(observation.get("hour", 0))
    need = Counter()
    for job in executor_state.get("jobs", []):
        if job.get("day") != day or job.get("hour", 0) < hour:
            continue
        cmd = job.get("cmd", [])
        if cmd and cmd[0] == "FEED": need["WHEAT"] += 1
        elif cmd and cmd[0] == "FERTILIZE": need["FERTILIZER"] += 1
        elif cmd and cmd[0] == "PLACE" and len(cmd) > 1: need[cmd[1]] += 1
    shed = observation.get("private", {}).get("shed", {})
    orders = list(action.get("market", []))
    for product in PRODUCTS:
        surplus = max(0, int(shed.get(product, 0)) - need[product])
        if surplus and len(orders) < 10:
            orders.append(["SELL", product, surplus])
    if orders: action["market"] = orders
    return action


def run_node(node, raw_path, hire_to=11):
    import research_labour_profit as R
    from fragments.segment_job_executor import segment_executor_action, segment_executor_start, segment_executor_status

    node = deepcopy(node)
    # Reproduction validates donor jobs only; safety jobs would change the plan.
    node["safety_assets"] = False
    node["hire_to"] = hire_to
    raw = read(raw_path)
    seat, start = int(node["seat"]), int(node["day"]) * 24
    game = {"seed": int(raw["info"]["seed"]), "seat": seat, "shops": shops_by_day(raw)}
    source_actions = recorded_actions(raw)
    with R.Simulator(game) as sim:
        # Official interpreter reconstructs the exact recorded source state.
        source = sim.run(sim.initial, 0, start, source_actions, snapshots=False, capture=False)["state"]
        start_farm = deepcopy(source[0].observation.farms[seat])
        if start_farm != node["start_farm"]:
            raise AssertionError("source_reconstruction_start_farm_mismatch")
        state = deepcopy(source)
        own_obs = state[seat].observation
        executor_state = segment_executor_start(own_obs, node)
        initial_status = segment_executor_status(executor_state)
        if not executor_state.get("ok"):
            return {"id": node["id"], "day": node["day"], "episode": node["episode"], "seat": seat, "hire_to": hire_to,
                    "started": False, "initial_status": initial_status,
                    "rejected_window": initial_status.get("failure"), "expected_output": node["output"]}
        sim.capture, sim.work, sim.events = True, [], []
        for t in range(start, min(start + 72, 719)):
            sim.t = t
            sim.seats = {id(f): i for i, f in enumerate(state[0].observation.farms)}
            for s in (0, 1): state[s].observation.step = t
            action = segment_executor_action(state[seat].observation, executor_state)
            action = add_capacity_sales(action, state[seat].observation, executor_state)
            rival_farm = state[0].observation.farms[1 - seat]
            rival = {"farmer": ["PASS"], "hands": [["PASS"] for _ in rival_farm.get("hands", [])], "market": []}
            state[seat].action = deepcopy(action)
            state[1 - seat].action = rival
            R.E.interpreter(state, sim.env)
            if (t + 1) % 24 == 0:
                # This is source-path conditioning for direct donor reproduction,
                # not an executor input or an online evaluation condition.
                state[0].observation.town.unlocked_shops[:] = game["shops"][(t + 1) // 24]
        for s in (0, 1): state[s].observation.step = min(start + 72, 719)
        status = segment_executor_status(executor_state)
        harvested = harvest_inventory_delta(sim.work, seat)
        actual_farm = state[0].observation.farms[seat]
        expected_cohort, actual_cohort = cohort(node["end_farm"]), cohort(actual_farm)
        return {"id": node["id"], "day": node["day"], "episode": node["episode"], "seat": seat, "hire_to": hire_to,
                "started": True, "initial_status": initial_status, "status": status,
                "donor_physical_output": node["output"],
                "executed_physical_output": harvested,
                "output_difference": differences(Counter(node["output"]), Counter(harvested)),
                "production_comparison": "directly comparable: both use successful HARVEST/COLLECT_FERTILIZER inventory deltas from the official interpreter",
                "start_cohort_matches_node": cohort(start_farm) == cohort(node["start_farm"]),
                "start_cohort": dict(cohort(start_farm)),
                "end_cohort_difference": differences(expected_cohort, actual_cohort),
                "end_tile_state_differences": tile_state_differences(node["end_farm"], actual_farm),
                "end_structural_difference": {k: v for k, v in differences(expected_cohort, actual_cohort).items()
                                             if k.startswith("STRUCTURE:") or k in ("EMPTY", "LOCKED")},
                "starting_cash": start_farm["money"], "ending_cash": actual_farm["money"],
                "issued_jobs": status.get("issued_jobs", 0),
                "rejected_window": status.get("failure"),
                "rival": "PASS", "source_future_shops_conditioned": True}


def main():
    nodes = selected_nodes(read(LIBRARY)["segments"])
    raws = raw_lookup()
    def save(rows, complete=False):
        payload = {"schema_version": 1, "complete": complete,
                   "library_sha256": hashlib.sha256(LIBRARY.read_bytes()).hexdigest(),
                   "executor_sha256": hashlib.sha256(EXECUTOR_HASH_PATH.read_bytes()).hexdigest(),
                   "design": "12 deterministic donor nodes: two SHA256-id ordered nodes per start day; official engine reconstruction from source replay state; executor owns one seat and rival passes.",
                   "limitations": ["Source future shops are conditioned after each day only to reproduce the donor window; they are never passed to executor state.",
                                   "This is a direct donor-window smoke validation, not a whole-game or independent-policy benchmark."],
                   "rows": rows,
                   "summary": {"requested": len(nodes), "completed_rows": len(rows),
                               "started_at_11": sum(r["attempts"][0].get("started", False) for r in rows),
                               "rejected_at_11": sum(bool(r["attempts"][0].get("rejected_window")) for r in rows),
                               "extra_worker_diagnostics": sum(max(0, len(r["attempts"]) - 1) for r in rows),
                               "errors": sum(any("error" in a for a in r["attempts"]) for r in rows)}}
        temp = OUT.with_suffix(".json.tmp")
        temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp.replace(OUT)
    rows = []
    for node in nodes:
        path = raws.get(int(node["episode"]))
        if path is None:
            rows.append({"id": node["id"], "attempts": [{"started": False, "hire_to": 11,
                                                             "error": "missing_raw_replay"}]})
            save(rows)
            continue
        try:
            first = run_node(node, path, hire_to=11)
            attempts = [first]
            # Worker counts 12/13 are diagnostics only, never selected by
            # production result; try them solely after an infeasible preflight.
            if not first.get("started") or first.get("rejected_window"):
                attempts.extend(run_node(node, path, hire_to=h) for h in (12, 13))
            rows.append({"id": node["id"], "attempts": attempts})
        except Exception as exc:
            rows.append({"id": node["id"], "attempts": [{"started": False, "hire_to": 11, "error": repr(exc)}]})
        save(rows)
    save(rows, complete=True)
    print(json.dumps(read(OUT)["summary"]))


if __name__ == "__main__": main()
