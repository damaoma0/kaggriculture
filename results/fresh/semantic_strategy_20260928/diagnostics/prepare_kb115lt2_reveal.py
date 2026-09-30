"""Freeze the reveal-feature ablation over exact V8, without dormant extras."""
import copy
import datetime
import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[4]
STUDY = ROOT / "results/fresh/semantic_strategy_20260928"
SOURCE = STUDY / "candidates/strategy_v8_kb115lt2_readiness"
TARGET = STUDY / "candidates/strategy_v9_kb115lt2_reveal"
PREFIX = "results/fresh/semantic_strategy_20260928/"
ADDITIONS = {
    "scripts/semantic_strategy_blocks_reveal_20260928.py": "125e32b4aff0cb4e7c12a825b03bbbdef6c55f525dcb15772a993861f3f4b5ec",
    PREFIX + "block_model_reveal_modern100.json": "a4a1ec12b60c1d37e2ceded1441dc6741a3d00669950edad7193622b08457e72",
    PREFIX + "block_model_reveal_modern100_training_manifest.json": "1ef9fa80d284c5d82d255a46e240d538780e766c6fa49c0647c452d4fc4c1e7d",
}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

def replace_once(source, old, new):
    assert source.count(old) == 1, old
    return source.replace(old, new)

def main():
    assert not TARGET.exists(), "Never overwrite an existing frozen candidate"
    original = read(SOURCE / "manifest.json")
    for folder, key in (("project", "files"), ("harness", "harness_files")):
        for name, digest in original[key].items():
            old = SOURCE / folder / name
            assert sha(old) == digest, name
            new = TARGET / folder / name
            new.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old, new)
    for name, digest in ADDITIONS.items():
        assert sha(ROOT / name) == digest, name
        new = TARGET / "project" / name
        new.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, new)
    entry = TARGET / "project/agents/semantic_strategy_20260928.py"
    old_code = entry.read_text(encoding="utf-8")
    code = replace_once(old_code, "from collections import Counter as _Counter\n",
                        "from collections import Counter as _Counter\nfrom copy import deepcopy as _deepcopy\n")
    code = replace_once(code, '    elif policy_kind == "daily_nearest":\n',
        '    elif policy_kind == "three_day_reveal":\n'
        '        from semantic_strategy_blocks_reveal_20260928 import SemanticRevealBlockPolicy\n'
        '        policy = SemanticRevealBlockPolicy(model, config.get("policy"))\n'
        '    elif policy_kind == "daily_nearest":\n')
    code = replace_once(code, '            proposal = state["policy"].propose(obs, state["policy_memory"])\n',
        '            policy_input_memory = {key: _deepcopy(state["policy_memory"][key]) for key in\n'
        '                ("committed_retirement_counts", "block_strategy") if key in state["policy_memory"]}\n'
        '            policy_input_memory["public_history"] = {key: _deepcopy(value) for key, value in\n'
        '                state["policy_memory"].get("public_history", {}).items() if day-3 <= int(key) < day}\n'
        '            proposal = state["policy"].propose(obs, state["policy_memory"])\n')
    code = replace_once(code, '                realized_plan=audit["semantic_today"], capacity_adjustments=audit["capacity_adjustments"],\n',
        '                policy_input_memory=policy_input_memory,\n'
        '                realized_plan=audit["semantic_today"], capacity_adjustments=audit["capacity_adjustments"],\n')
    compile(code, str(entry), "exec")
    entry.write_text(code, encoding="utf-8")
    config_path = TARGET / "project" / PREFIX / "candidate_config.json"
    config = read(config_path)
    assert "executor_file" not in config
    config["policy_kind"] = "three_day_reveal"
    config["model_file"] = "block_model_reveal_modern100.json"
    config.setdefault("policy", {})["reveal_features"] = True
    write(config_path, config)
    harness_name = "semantic_strategy_gate_20260928.py"
    shutil.copy2(ROOT / "scripts" / harness_name, TARGET / "harness" / harness_name)
    manifest = copy.deepcopy(original)
    manifest.update(candidate_id=TARGET.name, created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    manifest["files"] = {name: sha(TARGET / "project" / name) for name in sorted(set(original["files"]) | set(ADDITIONS))}
    manifest["harness_files"][harness_name] = sha(TARGET / "harness" / harness_name)
    changes = {name: dict(v8=original["files"].get(name), v9=digest) for name, digest in manifest["files"].items()
               if original["files"].get(name) != digest}
    assert set(changes) == set(ADDITIONS) | {"agents/semantic_strategy_20260928.py", PREFIX + "candidate_config.json"}
    model_name = PREFIX + "block_model_reveal_modern100.json"
    training_name = PREFIX + "block_model_reveal_modern100_training_manifest.json"
    manifest["model_training_provenance"] = dict(model_file=model_name, model_sha256=manifest["files"][model_name],
        training_file=training_name, training_sha256=manifest["files"][training_name],
        source_sha256=read(TARGET / "project" / training_name)["source_sha256"])
    manifest["derived_from"] = dict(candidate=SOURCE.name, manifest_sha256=sha(SOURCE / "manifest.json"),
        only_source_changes=changes, prototype_manifest_sha256=sha(STUDY / "reveal_feature_prototype_manifest.json"),
        rationale="Reveal features for fitted sheep/strawberry columns; minimal entry class selector and own-public-memory diagnostics. Exact V8 KB115LT2 recipe, base block/policy, tile modules and wrapper execution mechanics preserved.")
    write(TARGET / "manifest.json", manifest)
    diff = "\n".join(difflib.unified_diff(old_code.splitlines(), code.splitlines(), fromfile="V8 entry", tofile="V9 entry")) + "\n"
    (STUDY / "strategy_v9_vs_v8_entry.diff").write_text(diff, encoding="utf-8")
    report = dict(candidate=TARGET.name, manifest_sha256=sha(TARGET / "manifest.json"),
        reference_manifest_sha256=sha(SOURCE / "manifest.json"), source_differences=changes,
        harness_differences={name: dict(v8=old, v9=manifest["harness_files"][name]) for name, old in original["harness_files"].items()
                             if old != manifest["harness_files"][name]},
        config_changes={"policy_kind": "three_day_reveal", "model_file": "block_model_reveal_modern100.json", "policy.reveal_features": True},
        executor_recipe_unchanged=True, base_block_policy_unchanged=True, stock_recovery_enabled=False, hand_bonus_enabled=False)
    write(STUDY / "strategy_v9_vs_v8_freeze.json", report)
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
