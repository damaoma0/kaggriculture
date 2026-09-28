"""Prepare a hash-bound recorded development pair; never launch games."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--study", type=Path, required=True)
    p.add_argument("--reference-scripts", type=Path, required=True)
    p.add_argument("--id", default="v12_v13_recorded_development_pair")
    p.add_argument("--candidates", nargs=2, default=["strategy_v12_kb115lt2_runtime_fast", "strategy_v13_kb115lt2_harvest_exchange"])
    args = p.parse_args()
    study = args.study.resolve()
    target = study / "recorded_dispatches" / args.id
    assert not target.exists(), "Never overwrite a prepared dispatch"
    selection = study / "selections/development.json"
    selected = read(selection)
    assert selected["protocol_sha256"] == sha(study / "protocol.json")
    cases = selected["cases"]
    assert len(cases) == 8 and len({c["id"] for c in cases}) == 8
    controls = {}
    for case in cases:
        assert sha(study / case["file"]) == case["sha256"]
        control = study / "controls" / (case["id"] + ".json")
        row = read(control)
        assert row["case"] == case and row["completed"] and row["recorded_cash_match"] and row["ledger_verified"]
        assert sha(control) == selected["control_sha256"][case["id"]]
        for path in (control, control.with_suffix(".actions.json")):
            controls[path.relative_to(study).as_posix()] = sha(path)
    candidate_hashes = {}
    for candidate in args.candidates:
        folder = study / "candidates" / candidate
        manifest = read(folder / "manifest.json")
        assert manifest["protocol_sha256"] == sha(study / "protocol.json")
        for directory, key in (("project", "files"), ("harness", "harness_files")):
            for name, value in manifest[key].items():
                assert sha(folder / directory / name) == value
        candidate_hashes[candidate] = sha(folder / "manifest.json")
    addendum_path = study / "shipping_score_addendum.json"
    addendum = read(addendum_path)
    doc = study.parents[2] / addendum["document"]
    assert addendum["original_protocol_sha256"] == sha(study / "protocol.json")
    assert sha(doc) == addendum["document_sha256"]
    target.mkdir(parents=True)
    files = {}
    for path in (ROOT / "scripts/run_semantic_recorded_pair_20260928.py",
                 args.reference_scripts / "report_semantic_strategy_shipping_20260928.py",
                 args.reference_scripts / "audit_semantic_strategy_gate_20260928.py"):
        shutil.copy2(path, target / path.name)
        files[path.name] = sha(path)
    value = dict(scope="PREPARED_UNRELEASED_FIXED_SHOP_RECORDED_DEVELOPMENT_PAIR_ONLY",
        created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), study=str(study),
        protocol_sha256=sha(study / "protocol.json"), selection_sha256=sha(selection),
        shipping_score_addendum_sha256=sha(addendum_path), addendum_document=str(doc),
        addendum_document_sha256=sha(doc), candidate_manifests=candidate_hashes,
        cases=cases, control_files=controls, files=files,
        minimum_free_gib=3.3, absolute_win_threshold=None, stop_on_technical_invalidity=True,
        original_strict_fragility_screen_preserved=True,
        dispatch_order=[dict(candidate=candidate, case=case["id"]) for candidate in args.candidates for case in cases],
        authorization="PREPARE ONLY. Separate explicit root release required after V13 live review.",
        instrumentation="Small existing harvest_exchange diagnostics copied inside dawn callback; no state mutation or clock exemption.",
        recorded_controls_reused_by_hash=True, existing_candidate_results_reused=False,
        qualification_dispatched=False, engine_dispatched=False)
    (target / "manifest.json").write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(manifest=str(target / "manifest.json"), sha256=sha(target / "manifest.json"), games=16, launched=False)))


if __name__ == "__main__":
    main()
