"""Freeze V12 from exact V8, with reviewed retry and pure runtime changes."""
import argparse
import ast
import copy
import datetime
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = "d6769c6994a9445f96a34e6c517e4fdee8d3bd3160d349e7d480bdc89871452b"
EXECUTOR = "results/fresh/semantic_strategy_20260928/runtime/agents/mgt_lead_kb115lt.py"
CONFIG = "results/fresh/semantic_strategy_20260928/candidate_config.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    args = parser.parse_args()
    study = args.study.resolve()
    source = study / "candidates/strategy_v8_kb115lt2_readiness"
    target = study / "candidates/strategy_v12_kb115lt2_runtime_fast"
    replacement = ROOT / "agents/mgt_lead_kb115lt2_runtime_fast.py"
    assert not target.exists() and sha(replacement) == EXPECTED
    base = ROOT / "agents/mgt_lead_kb115lt2_routefix_fast.py"
    funcs = lambda p: {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(p.read_text(encoding="utf-8")).body if isinstance(n, ast.FunctionDef)}
    before, after = funcs(base), funcs(replacement)
    assert {k for k in before if before[k] != after[k]} == {"_tier_eval", "_tier_search"}
    assert set(after) - set(before) == {"_tier_eval_reference"}
    old = read(source / "manifest.json")
    for folder, key in (("project", "files"), ("harness", "harness_files")):
        for name, expected in old[key].items():
            original = source / folder / name
            assert sha(original) == expected, name
            new = target / folder / name
            new.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, new)
    shutil.copy2(replacement, target / "project" / EXECUTOR)
    config_path = target / "project" / CONFIG
    config = read(config_path)
    config.setdefault("executor", {})["sd_tier_wheat_retry"] = 1
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    benchmark = study / "reports/kb115lt2_runtime_fast_fixture_benchmark_v1.json"
    shutil.copy2(benchmark, target / "fixture_benchmark_at_freeze.json")
    review = dict(source_sha256=EXPECTED, base_sha256=sha(base),
        changed_functions_vs_routefix_fast=["_tier_eval", "_tier_search"], added_functions=["_tier_eval_reference"],
        review_pass=True, reviewer="cloud_harness", tests_rerun_pass=6,
        findings=["Scalar evaluator removes only counters unused by returned scalar costs; pickup timing, fertilizer shortages and mandatory lateness preserved.",
            "Hour queries retain the original evaluator. Feed-harvest credits and dynamic globals remain read per call.",
            "Search cache keys use segment identity plus ordered route IDs; catalog, segment inputs and scoring globals remain unchanged during a call. Cache is fresh per search and bounded16384.",
            "Wall-clock search termination remains timing-sensitive. Component parity does not establish whole-game byte equality or budget compliance."],
        benchmark_sha256=sha(benchmark), no_policy_retirement_bank_or_harvest_change=True)
    (target / "independent_source_review.json").write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")
    result = copy.deepcopy(old)
    result.update(candidate_id=target.name, created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    result["files"][EXECUTOR], result["files"][CONFIG] = EXPECTED, sha(config_path)
    changes = {name: {"v8": old["files"][name], "v12": value} for name, value in result["files"].items() if value != old["files"][name]}
    assert set(changes) == {EXECUTOR, CONFIG}
    result["derived_from"] = dict(candidate=source.name, manifest_sha256=sha(source / "manifest.json"),
        only_source_changes=changes, executor_source=str(replacement),
        recipe_policy_harness_unchanged=True, config_changes={"executor.sd_tier_wheat_retry": 1},
        fixture_benchmark_sha256=sha(benchmark), independent_review_sha256=sha(target / "independent_source_review.json"),
        rationale="V11 residual-wheat retry and polish cache plus exact scalar evaluation and per-search cost memoization. No semantic policy or retirement/harvest overlay.")
    (target / "manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    proof = dict(candidate=target.name, manifest_sha256=sha(target / "manifest.json"),
        reference_manifest_sha256=sha(source / "manifest.json"), source_differences=changes,
        config_changes={"executor.sd_tier_wheat_retry": 1}, recipe_difference={}, harness_differences={})
    path = study / "strategy_v12_vs_v8_freeze.json"
    assert not path.exists()
    path.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    driver_dir = study / "technical_smokes" / target.name
    assert not driver_dir.exists()
    driver_dir.mkdir(parents=True)
    # Reuse the exact hash-checked driver already used for V10; the external
    # immutable manifest supplies the new candidate identity.
    driver = ROOT / "scripts/run_semantic_v10_technical_smoke_20260928.py"
    driver_name = "run_semantic_v12_technical_smoke_20260928.py"
    shutil.copy2(driver, driver_dir / driver_name)
    smoke = dict(scope="ONE_NORMAL_BUDGET_TECHNICAL_SMOKE_NOT_STRENGTH_PANEL", created_utc=result["created_utc"],
        study=str(study), candidate=target.name, candidate_manifest_sha256=sha(target / "manifest.json"),
        protocol_sha256=sha(study / "protocol.json"), case=next(r for r in read(study / "protocol.json")["development"]["live"] if r["id"] == "live-06"),
        files={driver_name: sha(driver)}, original_script=str(driver))
    (driver_dir / "manifest.json").write_text(json.dumps(smoke, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(proof, indent=2))
    print(driver_dir / driver_name)


if __name__ == "__main__":
    main()
