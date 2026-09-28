"""Read saved V8/V9 artifacts; never import agents or execute the engine."""
import argparse
import hashlib
import json
import statistics
import time
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def diagnostic_copy_benchmark(diagnostics, repeats=3):
    """Current-host estimate of the recorded harness's daily JSON copy only."""
    samples = []
    byte_count = 0
    for _ in range(repeats):
        start = time.perf_counter()
        for day in range(len(diagnostics)):
            encoded = json.dumps(diagnostics[:day+1], default=str)
            json.loads(encoded)
        samples.append(time.perf_counter() - start)
    for day in range(len(diagnostics)):
        byte_count += len(json.dumps(diagnostics[:day+1], default=str).encode())
    return dict(median_seconds=statistics.median(samples), samples_seconds=samples,
                cumulative_serialized_bytes=byte_count,
                limitation="Current-host JSON-copy microbenchmark, not a reconstruction of historical CPU contention or complete action runtime.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists(), "Append-only report: choose an unused output path"
    study = args.study.resolve()
    identifiers = ["strategy_v8_kb115lt2_readiness", "strategy_v9_kb115lt2_reveal"]
    rows = []
    for i in range(8):
        case = f"live-{i:02}"
        paths = [study / "runs" / version / "development/live" / (case + ".json") for version in identifiers]
        before, after = map(read, paths)
        actions = [read(p.with_suffix(".actions.json")) for p in paths]
        assert before["case"] == after["case"]
        seat = before["case"]["seat"]
        limit = min(*(len(stream) for pair in actions for stream in pair))
        first = next((step for step in range(limit) if any(actions[0][s][step] != actions[1][s][step]
                     for s in range(2))), limit)
        da, db = [row["final_diagnostics"][str(seat)] for row in (before, after)]
        fields = ("proposal", "policy", "realized_plan", "end_board", "retirements",
                  "animal_tile_lookahead", "retirement_count_lookahead")
        equal_days = [day for day in range(min(len(da), len(db))) if day >= 6
                      and all(da[day].get(key) == db[day].get(key) for key in fields)]
        dawns = [step for step in range(144, first, 24)]
        row = dict(case=case, seat=seat, completed=after["completed"], eligible=after["eligible"],
            source_result_sha256=[sha(p) for p in paths],
            source_actions_sha256=[sha(p.with_suffix(".actions.json")) for p in paths],
            first_any_action_difference=first, both_full_action_streams_equal=actions[0] == actions[1],
            logged_semantic_plan_equal_days=equal_days,
            overage_seconds=[r["measured_overage_used"][seat] for r in (before, after)],
            total_candidate_seconds=[sum(r["timings"][seat]) for r in (before, after)],
            logged_upper_planner_seconds=[sum(d.get("planner_seconds", 0) for d in ds) for ds in (da, db)],
            common_action_prefix_dawn_timings=[dict(step=step, v8=before["timings"][seat][step],
                                                   v9=after["timings"][seat][step]) for step in dawns],
            engine_audit=after["engine_audit"], action_counts=[len(a) for a in actions[1]],
            candidate_last_call_step=len(after["timings"][seat])-1,
            largest_candidate_call_seconds=max(after["timings"][seat]),
            software_errors=after["errors"],
            executor_errors=max((d.get("executor_errors_cumulative", 0) for d in db), default=0),
            opponent_health=after["live_opponent_internal_health"],
            incomplete_assertion=after.get("error"))
        if actions[0] == actions[1]:
            row["current_json_copy_microbenchmark"] = dict(v8=diagnostic_copy_benchmark(da),
                                                          v9=diagnostic_copy_benchmark(db))
        rows.append(row)
    manifests = [study / "candidates" / version / "manifest.json" for version in identifiers]
    value = dict(scope="READ_ONLY_EXISTING_ARTIFACTS_NO_GAME_OR_REPLAY", candidate_order=identifiers,
        manifest_sha256=[sha(p) for p in manifests], planned=8, recorded=8,
        completed=sum(r["completed"] for r in rows), valid=sum(r["eligible"] for r in rows),
        invalid_cases=[r["case"] for r in rows if not r["eligible"]], rows=rows,
        conclusions=[
            "V9 is rejected on the unchanged runtime gate; both failures remain in the eight-case denominator.",
            "DONE/DONE at final environment state is insufficient: timed-out candidate calls stop early while the engine advances with fallback actions.",
            "Whole action-stream equality in live01/live05 rules out changed realized gameplay as the sole explanation for their large runtime increase.",
            "Logged upper-planner time is too small to account for the total increase; it includes the new policy-memory deepcopy but excludes lower-executor work and the harness's final diagnostic serialization.",
            "The JSON-copy microbenchmark measures only today's copying cost. Historical CPU/load/thermal/GC telemetry and lower-executor CPU timing were not captured, so host load versus source overhead cannot be apportioned definitively.",
            "No invalid game is rerun, no deadline is relaxed, and no partial or replacement score is used."])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value[key] for key in ("planned", "recorded", "completed", "valid", "invalid_cases")}, indent=2))
    for row in rows:
        if "current_json_copy_microbenchmark" in row:
            print(row["case"], json.dumps(row["current_json_copy_microbenchmark"]))


if __name__ == "__main__":
    main()
