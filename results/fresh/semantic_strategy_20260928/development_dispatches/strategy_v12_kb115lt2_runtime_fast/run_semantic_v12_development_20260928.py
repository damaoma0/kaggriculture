"""Immutable, serial V12 live8 development screen with declared early stops."""
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import sys

DIRECTORY = Path(__file__).resolve().parent
MANIFEST = json.loads((DIRECTORY / "manifest.json").read_text(encoding="utf-8"))
STUDY = Path(MANIFEST["study"])
FROZEN = STUDY / "candidates" / MANIFEST["candidate"]
sys.path.insert(0, str(FROZEN / "harness"))
import semantic_strategy_gate_20260928 as G


def check_result(case):
    path = STUDY / "runs" / MANIFEST["candidate"] / "development/live" / (case["id"] + ".json")
    row = G.read(path)
    assert row["candidate_manifest_sha256"] == MANIFEST["candidate_manifest_sha256"]
    assert row["protocol_sha256"] == MANIFEST["protocol_sha256"] and row["case"] == case
    errors = []
    if not row.get("completed") or not row.get("eligible") or not row.get("ledger_verified") or row.get("errors"):
        errors.append("incomplete, ineligible, ledger failure or callback error")
    if not row.get("measured_runtime_valid") or any(t > 60 for t in row.get("measured_overage_used", [float("inf")])):
        errors.append("runtime invalid")
    engine = row.get("engine_audit", {})
    if engine.get("steps") != 720 or engine.get("statuses") != ["DONE", "DONE"] or engine.get("act_timeout") != 1 or any(v < 0 for v in engine.get("remaining_overage", [-1])):
        errors.append("engine incomplete or budget exhausted")
    if any(x.get("errors", 0) for x in row.get("live_opponent_internal_health", {}).values()):
        errors.append("rival internal error")
    diagnostics = row.get("final_diagnostics", {})
    own = diagnostics.get(str(case["seat"]), [])
    if not isinstance(own, list) or any(x.get("executor_errors_cumulative", 0) for x in own):
        errors.append("executor diagnostic missing or errored")
    actions = G.read(path.with_suffix(".actions.json"))
    if list(map(len, actions)) != [719, 719]:
        errors.append("missing executed calls")
    return dict(case=case["id"], result_sha256=G.sha(path), actions_sha256=G.sha(path.with_suffix(".actions.json")),
        technical_valid=not errors, technical_errors=errors, margin=row.get("margin"),
        win=not errors and row.get("margin", 0) > 0,
        measured_overage=row.get("measured_overage_used"), engine_remaining=engine.get("remaining_overage"))


def main():
    import psutil
    G.verify_files(DIRECTORY, MANIFEST["files"])
    assert G.sha(FROZEN / "manifest.json") == MANIFEST["candidate_manifest_sha256"]
    assert G.sha(STUDY / "protocol.json") == MANIFEST["protocol_sha256"]
    cases = G.read(STUDY / "protocol.json")["development"]["live"]
    assert cases == MANIFEST["cases"] and len(cases) == 8
    reused = MANIFEST["reuse"]
    for name, value in reused["files"].items():
        assert G.sha(STUDY / name) == value, name
    rows = [check_result(next(c for c in cases if c["id"] == reused["case"]))]
    assert rows[0]["technical_valid"], "Smoke must pass before panel dispatch"
    stop_reason = None
    attempted = {rows[0]["case"]}
    def checkpoint():
        value = dict(scope=MANIFEST["scope"], candidate=MANIFEST["candidate"], rows=rows,
            planned_denominator=8, wins=sum(r["win"] for r in rows), remaining=[c["id"] for c in cases if c["id"] not in attempted],
            stop_reason=stop_reason, complete=len(attempted) == 8,
            all_attempted_technical_valid=all(r["technical_valid"] for r in rows),
            gate_pass=len(attempted) == 8 and all(r["technical_valid"] for r in rows) and sum(r["win"] for r in rows) >= 6,
            qualification_dispatched=False, recorded_dispatched=False)
        (DIRECTORY / "checkpoint.json").write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(value), flush=True)
    checkpoint()
    for case in cases:
        if case["id"] in attempted:
            continue
        if sum(r["win"] for r in rows) + 8-len(attempted) < 6:
            stop_reason = "cannot reach6wins among original8planned cases"
            break
        free = psutil.virtual_memory().available / 2**30
        if free < 3.3:
            stop_reason = f"memory guard: free{free:.3f}GiB <3.3GiB; no case dispatched"
            break
        output = STUDY / "runs" / MANIFEST["candidate"] / "development/live" / (case["id"] + ".json")
        assert not output.exists(), "No rerun or replacement of existing outcomes"
        job = dict(study=str(STUDY), candidate=MANIFEST["candidate"], case=case, kind="live", output=str(output),
            harness_extension=dict(root=str(DIRECTORY), files=MANIFEST["files"]))
        print(f"Dispatch {case['id']} one fresh worker, free{free:.3f}GiB", flush=True)
        # A fresh spawned child imports the immutable driver; module globals,
        # opponent heap and candidate state cannot carry between games.
        with ProcessPoolExecutor(max_workers=1, max_tasks_per_child=1) as pool:
            pool.submit(G.play_job, job).result()
        attempted.add(case["id"])
        rows.append(check_result(case))
        if not rows[-1]["technical_valid"]:
            stop_reason = "technical invalidity; remaining cases not dispatched"
        checkpoint()
        if stop_reason:
            break
    checkpoint()


if __name__ == "__main__":
    main()
