"""Freeze the user-selected KB115LT2 recipe over the exact V7 project."""
import copy
import datetime
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[4]
STUDY = ROOT / "results/fresh/semantic_strategy_20260928"
SOURCE = STUDY / "candidates/strategy_v7_blocks100_readiness"
TARGET = STUDY / "candidates/strategy_v8_kb115lt2_readiness"
EXECUTOR = "results/fresh/semantic_strategy_20260928/runtime/agents/mgt_lead_kb115lt.py"
RECIPE = "results/fresh/semantic_strategy_20260928/executor_recipe_online.json"
CHANGES = dict(sd_collect_at_floor=1, sd_polish=3000, sd_polish_final=1,
               sd_polish_xch=0.2, sd_polish_water_c=20,
               sd_tier_dawn_shape="learned2", sd_tier_anim_harv_frac=0.3)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

def main():
    assert not TARGET.exists(), "Never mutate or overwrite a frozen candidate"
    original = read(SOURCE / "manifest.json")
    expected = "527d4c48b5d6bbef7854d430797e8691858724242d50eeec1e1636665ee124e7"
    new_source = ROOT / "agents/mgt_lead_kb115lt2.py"
    assert sha(new_source) == expected
    for folder, key in (("project", "files"), ("harness", "harness_files")):
        for name, digest in original[key].items():
            old = SOURCE / folder / name
            assert sha(old) == digest, name
            new = TARGET / folder / name
            new.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old, new)
    shutil.copy2(new_source, TARGET / "project" / EXECUTOR)
    old_recipe = read(SOURCE / "project" / RECIPE)
    recipe = dict(old_recipe, **CHANGES)
    assert recipe["sd_days"] == [6, 29]
    assert recipe["sd_books_pace_map"] is None
    write(TARGET / "project" / RECIPE, recipe)
    manifest = copy.deepcopy(original)
    manifest.update(candidate_id=TARGET.name,
                    created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    manifest["files"] = {name: sha(TARGET / "project" / name) for name in original["files"]}
    changes = {name: dict(v7=old, v8=manifest["files"][name]) for name, old in original["files"].items()
               if old != manifest["files"][name]}
    assert set(changes) == {EXECUTOR, RECIPE}
    manifest["derived_from"] = dict(candidate=SOURCE.name, manifest_sha256=sha(SOURCE / "manifest.json"),
        only_source_changes=changes,
        executor_source=dict(original_path="agents/mgt_lead_kb115lt2.py", sha256=expected,
                             frozen_compatibility_path=EXECUTOR),
        recipe_changes=CHANGES,
        rationale="User-selected KB115LT2 lower layer; V7 causal semantic/readiness modules, wrapper and model preserved.")
    write(TARGET / "manifest.json", manifest)
    report = dict(candidate=TARGET.name, manifest_sha256=sha(TARGET / "manifest.json"),
        reference_manifest_sha256=sha(SOURCE / "manifest.json"), source_differences=changes,
        harness_differences={}, config_difference={},
        executor_recipe_difference={key: {"v7": old_recipe.get(key), "v8": value} for key, value in CHANGES.items()},
        sd_days=recipe["sd_days"], pooled_pace_preserved=True, recovery_enabled=False, hand_bonus_enabled=False)
    write(STUDY / "strategy_v8_vs_v7_freeze.json", report)
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
