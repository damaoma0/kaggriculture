"""Freeze V13 from exact V12; preparation never dispatches an engine."""
import argparse
import ast
import copy
import datetime
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
V12 = "aafa32c48bc4b32627855bd0f0bf18bf93f4f982c496f5ec5f7411dc43a938a1"
EXECUTOR = "results/fresh/semantic_strategy_20260928/runtime/agents/mgt_lead_kb115lt.py"
CONFIG = "results/fresh/semantic_strategy_20260928/candidate_config.json"
IDENTIFIER = "strategy_v13_kb115lt2_harvest_exchange"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    assert not path.exists(), str(path)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--executor", type=Path, required=True)
    parser.add_argument("--executor-sha256", required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--component-audit", type=Path, required=True)
    parser.add_argument("--guard-audit", type=Path, required=True)
    args = parser.parse_args()
    study = args.study.resolve()
    source = study / "candidates/strategy_v12_kb115lt2_runtime_fast"
    target = study / "candidates" / IDENTIFIER
    dispatch = study / "development_dispatches" / IDENTIFIER
    assert not target.exists() and not dispatch.exists(), "Never replace a candidate or run"
    assert sha(source / "manifest.json") == V12
    replacement = args.executor.resolve()
    assert sha(replacement) == args.executor_sha256
    review = read(args.review)
    assert review["review_pass"] and review["source_sha256"] == sha(replacement)
    before_ast = ast.parse((source / "project" / EXECUTOR).read_text(encoding="utf-8"))
    after_ast = ast.parse(replacement.read_text(encoding="utf-8"))
    def defs(tree):
        return {n.name: ast.dump(n, include_attributes=False) for n in tree.body
                if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    before, after = defs(before_ast), defs(after_ast)
    assert {key for key in before if before[key] != after[key]} == {"_tier_deliver", "_tier_polish"}
    assert set(after) - set(before) == {"_tier_harvest_exchange"}
    assert not set(before) - set(after)
    old = read(source / "manifest.json")
    assert old["protocol_sha256"] == sha(study / "protocol.json")
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
    original_config = copy.deepcopy(config)
    assert "sd_polish_harvest_exchange" not in config.get("executor", {})
    config.setdefault("executor", {})["sd_polish_harvest_exchange"] = 1
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    reverse = copy.deepcopy(config)
    del reverse["executor"]["sd_polish_harvest_exchange"]
    assert reverse == original_config
    evidence = {}
    for name, path in (("independent_source_review.json", args.review),
                       ("component_audit_at_freeze.json", args.component_audit),
                       ("guard_audit_at_freeze.json", args.guard_audit)):
        shutil.copy2(path, target / name)
        evidence[name] = sha(target / name)
    result = copy.deepcopy(old)
    result.update(candidate_id=IDENTIFIER, created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    result["files"][EXECUTOR], result["files"][CONFIG] = sha(replacement), sha(config_path)
    changes = {name: {"v12": old["files"][name], "v13": value}
               for name, value in result["files"].items() if value != old["files"][name]}
    assert set(changes) == {EXECUTOR, CONFIG}
    result["derived_from"] = dict(candidate=source.name, manifest_sha256=V12,
        only_source_changes=changes, executor_source=str(replacement), evidence_sha256=evidence,
        recipe_policy_base_harness_unchanged=True,
        config_changes={"executor.sd_polish_harvest_exchange": 1},
        status_at_freeze="component mechanism passed; eight-world paired incremental screen pending",
        rationale="One bounded optional held-animal-harvest exchange with unchanged fixed receipt and first-visit timestamps; no retirement-bank or fertilizer-valuation change.")
    write(target / "manifest.json", result)
    driver = ROOT / "scripts/run_semantic_v13_development_20260928.py"
    dispatch.mkdir(parents=True)
    shutil.copy2(driver, dispatch / driver.name)
    run = dict(scope="EIGHT_NATIVE_LIVE_DEVELOPMENT_CASES_PAIRED_INCREMENTAL_SCREEN",
        created_utc=result["created_utc"], study=str(study), candidate=IDENTIFIER,
        candidate_manifest_sha256=sha(target / "manifest.json"), protocol_sha256=sha(study / "protocol.json"),
        files={driver.name: sha(driver)}, cases=read(study / "protocol.json")["development"]["live"],
        reference_candidate=source.name, reference_manifest_sha256=V12,
        minimum_free_gib=3.3, stop_on_any_invalid=True, absolute_win_threshold=None,
        dispatch_authorization="User waived the absolute6/8 rule before freeze. Complete development8 if technically valid; assess paired regression and mechanisms versus V12. No automatic forty-world or recorded dispatch.",
        diagnostic_extension="Read-only copy of existing daily polish.harvest_exchange into diagnostic rows, within normal dawn callback budget; candidate, frozen base harness, RNG and observations unchanged.")
    write(dispatch / "manifest.json", run)
    proof = dict(candidate=IDENTIFIER, manifest_sha256=sha(target / "manifest.json"),
        dispatch_manifest_sha256=sha(dispatch / "manifest.json"), source_differences=changes,
        config_changes={"executor.sd_polish_harvest_exchange": 1}, recipe_difference={},
        base_harness_differences={}, declared_dispatch_extension_sha256=run["files"],
        qualification_dispatched=False, engine_dispatched=False)
    write(study / "strategy_v13_vs_v12_freeze.json", proof)
    print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    main()
