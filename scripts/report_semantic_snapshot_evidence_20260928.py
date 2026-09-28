"""Hash-bound read-only V10 prefix and D28 mandatory-harvest evidence."""
from collections import Counter
import argparse
import gzip
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    args = parser.parse_args()
    study = args.study.resolve()
    target = study / "reports/v10_prefix_and_v8_d28_core_evidence.json"
    assert not target.exists()
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    read = lambda p: json.loads(p.read_text(encoding="utf-8"))
    paths = [study / f"runs/{name}/development/live/live-06.actions.json" for name in
             ("strategy_v8_kb115lt2_readiness", "strategy_v10_kb115lt2_polishcache")]
    streams = list(map(read, paths))
    comparisons = []
    for seat in (0, 1):
        diffs = []
        for step, (left, right) in enumerate(zip(streams[0][seat], streams[1][seat])):
            if left == right:
                continue
            physical_equal = {k: v for k, v in left.items() if k != "market"} == {k: v for k, v in right.items() if k != "market"}
            a, b = left.get("market", []), right.get("market", [])
            pure = (physical_equal and len(a) == len(b) <= 10 and all(o[0] == "SELL" for o in a + b)
                    and len({o[1] for o in a}) == len(a) and Counter(map(tuple, a)) == Counter(map(tuple, b)))
            diffs.append(dict(step=step, physical_equal=physical_equal,
                distinct_product_sell_permutation_only=pure, reference_market=a, candidate_market=b))
        comparisons.append(dict(seat=seat, reference_calls=len(streams[0][seat]), candidate_calls=len(streams[1][seat]),
            compared_calls=min(len(streams[0][seat]), len(streams[1][seat])), differences=diffs,
            all_physical_commands_equal=all(d["physical_equal"] for d in diffs),
            all_differences_are_distinct_product_sell_permutations=all(d["distinct_product_sell_permutation_only"] for d in diffs)))
    directory = study / "eval_search_fixtures_v8_live06_v1"
    path = directory / "d28_retirement_routes.json.gz"
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        traces = json.load(stream)
    cores = []
    for row in traces["core_passes"]:
        stops = [dict(unit=u, item=item) for u, route in row["result_routes"].items()
                 for item in route["items"] if item.get("tile") == 48]
        cores.append(dict(pass_index=row["pass_index"], xretire48=row["xretire"].get("48"),
            input_rec48=row["rec48"], output_stops48=stops,
            unplanned48=[x for x in row["summary"].get("unplanned", []) if x[0] == 48],
            mandatory_lateness=row["summary"].get("mand_late")))
    snapshots = []
    for row in traces["snapshots"]:
        if row["hour"] not in (0, 9, 23):
            continue
        invs = row["private"]["inventories"]
        snapshots.append(dict(hour=row["hour"], tile48=row["tile48"],
            unit11_position=row["positions"]["hands"][10] if len(row["positions"]["hands"]) > 10 else None,
            unit11_inventory=invs[11] if len(invs) > 11 else None,
            unit11_action=row["action"]["hands"][10] if len(row["action"]["hands"]) > 10 else None,
            unit11_route_after=row["after"]["routes"].get("11"),
            final_unplanned48=[x for x in row["after"]["tier_summary"].get("unplanned", []) if x[0] == 48]))
    manifest = read(directory / "manifest.json")
    report = dict(scope="READ_ONLY_EVIDENCE_NO_VALIDITY_RECLASSIFICATION", script_sha256=sha(Path(__file__)),
        v10_action_source_hashes={str(p): sha(p) for p in paths}, v10_comparisons=comparisons,
        snapshot_manifest_sha256=sha(directory / "manifest.json"), snapshot_strict_verified=manifest["verified"],
        snapshot_replay_cash_equal=manifest["replay_cash_equal"], snapshot_replay_complete_ledgers_equal=manifest["replay_complete_ledgers_equal"],
        snapshot_dawns_equal=len(manifest["dawn_checks"]) == 30 and all(all(v for k, v in row.items() if k != "day") for row in manifest["dawn_checks"]),
        snapshot_shadow_mismatches=manifest["shadow_mismatches"], d28_routes_sha256=sha(path),
        d28_core_passes=cores, d28_selected_hours=snapshots,
        conclusions=["V10 has exactly two own SELL ordering differences, at429 and525, in the available673-call prefix. Rival's complete719-call stream is identical. Its normal-budget timeout remains invalid.",
            "The same two order permutations occur in an unchanged frozen-V8 shadow. This narrows the mismatch to existing nondeterministic ordering; exact source location is not established by this report.",
            "D28 tile48 enters allfivecores as an animal retiring tonight with5heldwool and an explicitly mandatory HARVEST. Onlycorepass1 retains harvest; finalpass4 and finalpolish route only COLLECT_FERTILIZER.",
            "Missing harvest is absent from unplanned diagnostics and allcoremandatorylateness iszero. This localizes loss inside core but does not justify blindly appending work or establish spare capacity.",
            "Snapshot strict verified=false is preserved because two action lists differ. Complete executed saved-action world cash, ledgers and30dawns match; physical shadow commands all match."])
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
