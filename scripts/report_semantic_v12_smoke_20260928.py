"""Preserve the single technical smoke separately from the live8 screen."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    args = parser.parse_args()
    study = args.study.resolve()
    out = study / "reports/v12_live06_technical_smoke_report.json"
    assert not out.exists()
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    read = lambda p: json.loads(p.read_text(encoding="utf-8"))
    sources = [study / f"runs/{n}/development/live/live-06.json" for n in
               ("strategy_v8_kb115lt2_readiness", "strategy_v12_kb115lt2_runtime_fast")]
    original, candidate = map(read, sources)
    a, b = [read(p.with_suffix(".actions.json")) for p in sources]
    differences = []
    for seat in (0, 1):
        for step, (x, y) in enumerate(zip(a[seat], b[seat])):
            if x == y:
                continue
            physical = {k: v for k, v in x.items() if k != "market"} == {k: v for k, v in y.items() if k != "market"}
            mx, my = x.get("market", []), y.get("market", [])
            differences.append(dict(seat=seat, step=step, physical_equal=physical,
                distinct_sell_permutation_only=physical and len(mx) == len(my) <= 10
                    and len({o[1] for o in mx}) == len(mx) and all(o[0] == "SELL" for o in mx + my)
                    and Counter(map(tuple, mx)) == Counter(map(tuple, my)),
                original_market=mx, candidate_market=my))
    own = candidate["case"]["seat"]
    report = dict(scope="ONE_NORMAL_BUDGET_TECHNICAL_SMOKE_NOT_STRENGTH_PANEL", candidate="strategy_v12_kb115lt2_runtime_fast",
        source_sha256={str(p): sha(p) for p in sources}, action_sha256={str(p.with_suffix(".actions.json")): sha(p.with_suffix(".actions.json")) for p in sources},
        candidate_manifest_sha256=candidate["candidate_manifest_sha256"], completed=candidate["completed"], eligible=candidate["eligible"],
        technical_pass=candidate["eligible"] and candidate["ledger_verified"] and not candidate["errors"] and candidate["measured_runtime_valid"],
        cash=candidate["cash"], rival_cash=candidate["opponent_cash"], margin=candidate["margin"],
        engine_audit=candidate["engine_audit"], measured_overage=candidate["measured_overage_used"],
        reference_measured_overage=original["measured_overage_used"], max_call=max(candidate["timings"][own]),
        action_counts=list(map(len, b)), cash_equal=candidate["cash_by_seat"] == original["cash_by_seat"],
        complete_ledgers_equal=candidate["daily"] == original["daily"], shops_equal=candidate["shops"] == original["shops"],
        action_differences=differences, all_physical_actions_equal=all(d["physical_equal"] for d in differences),
        all_byte_actions_equal=not differences, executor_errors=max(r.get("executor_errors_cumulative", 0) for r in candidate["final_diagnostics"][str(own)]),
        opponent_health=candidate["live_opponent_internal_health"], source_module_audit=candidate["source_module_audit"],
        day_dawn_seconds=[dict(day=d, reference=original["timings"][own][d*24], candidate=candidate["timings"][own][d*24]) for d in range(6, 30)],
        limitation="Single technical case passes; no full-panel strength or paired speed claim. Root-authorized remaining live8 dispatch reuses this exact outcome and will stop on invalidity or unattainable6wins.",
        script_sha256=sha(Path(__file__)))
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
