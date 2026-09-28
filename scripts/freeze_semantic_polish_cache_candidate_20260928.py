"""Freeze exactly V8 plus the reviewed per-call polish-cache executor."""
import argparse
import ast
import copy
import datetime
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = "cb85837fea85848092feb9e935f9a43d8758135163eb29785d682d57a24ae8aa"
EXECUTOR = "results/fresh/semantic_strategy_20260928/runtime/agents/mgt_lead_kb115lt.py"


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
    target = study / "candidates/strategy_v10_kb115lt2_polishcache"
    replacement = ROOT / "agents/mgt_lead_kb115lt2_polishcache.py"
    assert not target.exists(), "Never overwrite a candidate"
    assert sha(replacement) == EXPECTED
    old = read(source / "manifest.json")
    trees = [ast.parse(path.read_text(encoding="utf-8")) for path in (source / "project" / EXECUTOR, replacement)]
    for tree in trees:
        tree.body = [node for node in tree.body if not isinstance(node, ast.FunctionDef) or node.name != "_tier_polish"]
    assert ast.dump(trees[0], include_attributes=False) == ast.dump(trees[1], include_attributes=False)
    for folder, key in (("project", "files"), ("harness", "harness_files")):
        for name, expected in old[key].items():
            original = source / folder / name
            assert sha(original) == expected, name
            new = target / folder / name
            new.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, new)
    shutil.copy2(replacement, target / "project" / EXECUTOR)
    result = copy.deepcopy(old)
    result.update(candidate_id=target.name, created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    result["files"][EXECUTOR] = EXPECTED
    benchmark = study / "reports/kb115lt2_polishcache_fixture_benchmark_v1.json"
    result["derived_from"] = dict(candidate=source.name, manifest_sha256=sha(source / "manifest.json"),
        only_source_change=EXECUTOR, executor_original_sha256=old["files"][EXECUTOR],
        executor_sha256=EXPECTED, executor_source=str(replacement), changed_function="_tier_polish",
        recipe_policy_harness_unchanged=True, fixture_benchmark_sha256=sha(benchmark),
        purpose="Decision-equivalent speed experiment; one technical smoke, not a strength panel.")
    (target / "manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(benchmark, target / "fixture_benchmark_at_freeze.json")
    proof = dict(candidate=target.name, manifest_sha256=sha(target / "manifest.json"),
        reference_manifest_sha256=sha(source / "manifest.json"),
        source_differences={EXECUTOR: {"v8": old["files"][EXECUTOR], "v10": EXPECTED}},
        config_difference={}, recipe_difference={}, harness_differences={},
        changed_function="_tier_polish", technical_smoke_only="live-06")
    path = study / "strategy_v10_vs_v8_freeze.json"
    assert not path.exists()
    path.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    main()
