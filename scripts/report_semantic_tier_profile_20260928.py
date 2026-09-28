"""Read-only summary of the preserved, incomplete normal-budget profile."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    args = parser.parse_args()
    source = args.study / "tier_pre_profile_v8_live06_v1"
    target = args.study / "reports/tier_pre_profile_v8_live06_v1_summary.json"
    assert not target.exists(), "Append-only evidence"
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = load(source / "manifest.json")
    rows = []
    functions = {"_tier_pre", "_tier_core", "_tier_polish", "_tier_eval", "_tier_best_ins",
                 "_tier_relief", "_tier_fill", "_tier_search", "_tier_seg_cost", "_tier_picks"}
    for day in (18, 24):
        path = source / f"d{day:02}.json"
        data = load(path)
        rows.append(dict(day=day, source_sha256=sha(path),
            wall_seconds=data["original_pre_wall_seconds"], cpu_seconds=data["original_pre_cpu_seconds"],
            gc_seconds=data["gc_seconds"], gc_generation_counts=dict(Counter(e["generation"] for e in data["gc_events"])),
            rss_before=data["rss_before"], rss_after=data["rss_after"],
            selected_functions=[r for r in data["functions"] if r["function"] in functions],
            top20_cumulative=data["functions"][:20], numeric_counter_deltas=data["numeric_counter_deltas"]))
    report = dict(scope="INCOMPLETE_DIAGNOSTIC_PROFILE_NOT_A_GATE", manifest_sha256=sha(source / "manifest.json"),
        verified_whole_game=False, shadow_calls=manifest["shadow_calls"], mismatched_shadow_actions=len(manifest["shadow_mismatches"]),
        verified_dawns=len(manifest["dawn_checks"]), recorded_prefix_dawns_equal=all(
            all(v for k, v in row.items() if k != "day") for row in manifest["dawn_checks"]),
        last_shadow_step=manifest["call_timings"][-1]["step"],
        measured_shadow_overage=sum(max(0, r["seconds"] - 1) for r in manifest["call_timings"]),
        replay_cash_equal=manifest["replay_cash_equal"], replay_complete_ledgers_equal=manifest["replay_complete_ledgers_equal"],
        requested_days=[18, 24, 28], captured_days=[18, 24], profiles=rows,
        interpretation=["Normal time bank exhausted after step600 (day25 hour0). Subsequent saved own actions were not returned, so full replay cash/ledgers fail. All601 available shadow actions and26 dawn states match.",
            "GC consumed less than0.005 seconds in either captured call, with no generation2 collection. This rules out GC as the dominant cost of these captured calls only.",
            "Live V9's large heap is absent, so no causal conclusion about historical V9/V10 full-game timeouts follows.",
            "cProfile overhead is charged inside the ordinary engine clock. Cumulative function times overlap; do not sum them.",
            "Route evaluation, insertion/fill/relief, repeated core passes and polish are substantial. Search-only caching targets a smaller subset of the cost."],
        no_retry=True, script_sha256=sha(Path(__file__)))
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
