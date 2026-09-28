"""Freeze exact V8 with the reviewed route retry plus exact polish cache."""
import argparse
import copy
import datetime
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = "5c2dfb70eaf68e1b415fe14fd6414774b467afa81b4f66f9d170e792e0dfe833"
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
    target = study / "candidates/strategy_v11_kb115lt2_routefix_fast"
    replacement = ROOT / "agents/mgt_lead_kb115lt2_routefix_fast.py"
    assert not target.exists(), "Never overwrite a candidate"
    assert sha(replacement) == EXPECTED
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
    result = copy.deepcopy(old)
    result.update(candidate_id=target.name, created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    result["files"][EXECUTOR] = EXPECTED
    result["files"][CONFIG] = sha(config_path)
    changes = {name: {"v8": old["files"][name], "v11": value} for name, value in result["files"].items()
               if value != old["files"][name]}
    assert set(changes) == {EXECUTOR, CONFIG}
    result["derived_from"] = dict(candidate=source.name, manifest_sha256=sha(source / "manifest.json"),
        only_source_changes=changes, executor_source=str(replacement),
        recipe_policy_harness_unchanged=True, config_changes={"executor.sd_tier_wheat_retry": 1},
        rationale="Observed residual-wheat fixed-route retry plus decision-equivalent polish cache; no semantic-policy or retirement-bank overlay.")
    (target / "manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    proof = dict(candidate=target.name, manifest_sha256=sha(target / "manifest.json"),
        reference_manifest_sha256=sha(source / "manifest.json"), source_differences=changes,
        config_changes={"executor.sd_tier_wheat_retry": 1}, recipe_difference={}, harness_differences={},
        semantic_policy_and_tile_sources_unchanged=True, engine_dispatch_requires_targeted_diagnostics=True)
    path = study / "strategy_v11_vs_v8_freeze.json"
    assert not path.exists()
    path.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    main()
