"""Freeze four outcome-blind V13-versus-canonical-V9-lite smoke worlds."""
import argparse
import ast
import datetime
import hashlib
import json
from pathlib import Path
import secrets
import shutil

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = "strategy_v13_kb115lt2_harvest_exchange"
CANDIDATE_SHA = "82d5d5a2a3acc181705540a4acf2ed0a764294bba964122d888ec3634cbb0550"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--study", type=Path, required=True)
    p.add_argument("--reference-scripts", type=Path, required=True)
    args = p.parse_args()
    study = args.study.resolve()
    target = study / "fresh_smokes/v13_canonical_v9lite_fresh4_v1"
    assert not target.exists(), "Never overwrite chosen seeds or smoke artifacts"
    protocol = read(study / "protocol.json")
    candidate = study / "candidates" / CANDIDATE
    assert sha(candidate / "manifest.json") == CANDIDATE_SHA
    cm = read(candidate / "manifest.json")
    for folder, key in (("project", "files"), ("harness", "harness_files")):
        for name, value in cm[key].items():
            assert sha(candidate / folder / name) == value
    opponent = protocol["opponent"]
    assert opponent["name"] == "mgt_v9lite" and len(opponent["files"]) == 185
    for name, value in opponent["files"].items():
        assert sha(study / "opponent/pkg" / name) == value
    entry = study / opponent["entry"]
    functions = [n.name for n in ast.parse(entry.read_text()).body if isinstance(n,ast.FunctionDef)]
    assert functions[-1] == "v9lite_agent"
    # Read only protocol/manifests. No outcomes or cash tables select seeds.
    sources = sorted(set([study / "protocol.json"] + list(study.rglob("manifest.json")) + list(study.rglob("*protocol*.json"))))
    excluded = set()
    def collect(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "seed" and isinstance(child, int):
                    excluded.add(child)
                else:
                    collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)
    for path in sources:
        collect(read(path))
    cases = []
    while len(cases) < 4:
        seed = secrets.randbits(32)
        if seed in excluded or any(case["seed"] == seed for case in cases):
            continue
        cases.append(dict(id=f"v9fresh-{len(cases):02}",seed=seed,seat=len(cases)%2))
    target.mkdir(parents=True)
    files = {}
    for path in (ROOT / "scripts/run_semantic_v9_fresh_smoke_20260928.py",
                 args.reference_scripts / "report_semantic_strategy_shipping_20260928.py",
                 args.reference_scripts / "audit_semantic_strategy_gate_20260928.py"):
        shutil.copy2(path, target/path.name)
        files[path.name] = sha(path)
    manifest = dict(scope="FOUR_FRESH_NATIVE_V9LITE_WORLDS_SMOKE_NOT_QUALIFICATION",
        created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),study=str(study),
        candidate=CANDIDATE,candidate_manifest_sha256=CANDIDATE_SHA,protocol_sha256=sha(study/"protocol.json"),
        cases=cases,minimum_free_gib=3.3,absolute_win_threshold=None,
        seed_selection=dict(method="secrets.randbits(32), rejection only for prior declared seed or duplicate",
            outcome_inspection=False,excluded_seed_count=len(excluded),excluded_seeds=sorted(excluded),
            metadata_sources={str(path):sha(path) for path in sources}),
        opponent=dict(name=opponent["name"],entry=opponent["entry"],entry_sha256=sha(entry),
            last_callable="v9lite_agent",files=opponent["files"],files_verified=185,configuration_changes={}),
        files=files,instrumentation="Read-only copies of existing harvest exchange summaries and opponent _V9_REPORT decisions; dawn copies charged inside existing callback.",
        release_condition="Root authorizes after current recorded16 finishes and audits, or clean technical stop; sole worker, normal runtime, no forced switches or seed replacement.",
        expected_previous_dispatch="recorded_dispatches/v12_v13_recorded_development_pair",
        qualification_dispatched=False,engine_dispatched=False)
    (target/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(dict(manifest=str(target/"manifest.json"),manifest_sha256=sha(target/"manifest.json"),cases=cases,
        excluded_seed_count=len(excluded),opponent_entry_sha256=sha(entry),launched=False),indent=2))


if __name__ == "__main__":
    main()
