"""Immutable serial V13 paired live8 screen; no absolute win-count cutoff."""
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

ORIGINAL_DIAGNOSTICS = G.diagnostics


def exchange_diagnostics(fn):
    """Read existing small summaries; never call a state initializer or agent."""
    value = ORIGINAL_DIAGNOSTICS(fn)
    state = getattr(fn, "__globals__", {}).get("_STATE")
    if isinstance(value, list) and isinstance(state, dict):
        kb_state = getattr(state.get("kb"), "_S", None) or {}
        days = kb_state.get("sd", {}).get("tier_days", {})
        for row in value:
            if isinstance(row, dict):
                exchange = (days.get(str(row.get("day")), {}).get("polish") or {}).get("harvest_exchange")
                if exchange is not None:
                    row["harvest_exchange"] = json.loads(json.dumps(exchange, default=str))
    return value


G.diagnostics = exchange_diagnostics


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
    if any(x.get("errors", 0) for x in (row.get("live_opponent_internal_health") or {}).values()):
        errors.append("rival internal error")
    own = row.get("final_diagnostics", {}).get(str(case["seat"]), [])
    if not isinstance(own, list) or not own or any(x.get("executor_errors_cumulative", 0) for x in own):
        errors.append("executor diagnostic missing or errored")
    actions = G.read(path.with_suffix(".actions.json"))
    if list(map(len, actions)) != [719, 719]:
        errors.append("missing executed calls")
    exchanges = [dict(day=x["day"], **x["harvest_exchange"]) for x in own
                 if isinstance(x, dict) and "harvest_exchange" in x] if isinstance(own, list) else []
    reference_path = STUDY / "runs" / MANIFEST["reference_candidate"] / "development/live" / (case["id"] + ".json")
    reference = G.read(reference_path)
    assert reference["case"] == case and reference["candidate_manifest_sha256"] == MANIFEST["reference_manifest_sha256"]
    def delta(key):
        return row[key]-reference[key] if isinstance(row.get(key), (int,float)) else None
    return dict(case=case["id"], result_sha256=G.sha(path), actions_sha256=G.sha(path.with_suffix(".actions.json")),
        technical_valid=not errors, technical_errors=errors, margin=row.get("margin"),
        win=not errors and row.get("margin", 0) > 0, harvest_exchanges=exchanges,
        reference_result_sha256=G.sha(reference_path), reference_margin=reference["margin"],
        margin_delta=delta("margin"), own_cash_delta=delta("cash"), rival_cash_delta=delta("opponent_cash"),
        natural_shops_equal=row.get("shops") == reference["shops"],
        measured_overage=row.get("measured_overage_used"), engine_remaining=engine.get("remaining_overage"))


def main():
    import psutil
    G.verify_files(DIRECTORY, MANIFEST["files"])
    assert G.sha(FROZEN / "manifest.json") == MANIFEST["candidate_manifest_sha256"]
    assert G.sha(STUDY / "protocol.json") == MANIFEST["protocol_sha256"]
    cases = G.read(STUDY / "protocol.json")["development"]["live"]
    assert cases == MANIFEST["cases"] and len(cases) == 8 and MANIFEST["absolute_win_threshold"] is None
    assert G.sha(STUDY / "candidates" / MANIFEST["reference_candidate"] / "manifest.json") == MANIFEST["reference_manifest_sha256"]
    rows, attempted, stop_reason = [], set(), None
    def checkpoint():
        paired = [r["margin_delta"] for r in rows if r["margin_delta"] is not None]
        value = dict(scope=MANIFEST["scope"], candidate=MANIFEST["candidate"], rows=rows,
            planned_denominator=8, wins=sum(r["win"] for r in rows), remaining=[c["id"] for c in cases if c["id"] not in attempted],
            stop_reason=stop_reason, complete=len(attempted) == 8,
            all_attempted_technical_valid=all(r["technical_valid"] for r in rows),
            incremental_screen_complete=len(attempted) == 8 and all(r["technical_valid"] for r in rows),
            absolute_win_threshold=None, mean_paired_margin_delta=sum(paired)/len(paired) if paired else None,
            qualification_dispatched=False, recorded_dispatched=False)
        (DIRECTORY / "checkpoint.json").write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({k:v for k,v in value.items() if k != "rows"}), flush=True)
    checkpoint()
    for case in cases:
        free = psutil.virtual_memory().available / 2**30
        if free < MANIFEST["minimum_free_gib"]:
            stop_reason = f"memory guard: free {free:.3f} GiB <3.3 GiB; no case dispatched"
            break
        output = STUDY / "runs" / MANIFEST["candidate"] / "development/live" / (case["id"] + ".json")
        assert not output.exists(), "No rerun or replacement of existing outcomes"
        job = dict(study=str(STUDY), candidate=MANIFEST["candidate"], case=case, kind="live", output=str(output),
            harness_extension=dict(root=str(DIRECTORY), files=MANIFEST["files"]))
        print(f"Dispatch {case['id']}, one fresh worker, free {free:.3f} GiB", flush=True)
        with ProcessPoolExecutor(max_workers=1, max_tasks_per_child=1) as pool:
            pool.submit(G.play_job, job).result()
        attempted.add(case["id"])
        rows.append(check_result(case))
        print(json.dumps(rows[-1]), flush=True)
        if not rows[-1]["technical_valid"]:
            stop_reason = "technical invalidity; remaining cases not dispatched"
        checkpoint()
        if stop_reason:
            break
    checkpoint()


if __name__ == "__main__":
    main()
