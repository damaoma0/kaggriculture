"""Prepare V14 recorded8 with hash-bound completed V13 controls, no engine."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
V13 = "strategy_v13_kb115lt2_harvest_exchange"
V14 = "strategy_v14_kb115lt2_fertilizer_net"
HASHES = {V13:"82d5d5a2a3acc181705540a4acf2ed0a764294bba964122d888ec3634cbb0550",
          V14:"777116e0c9ac309d9481eac1e1da5621c926b380214e73a7c2aaac8b02024b5d"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--study",type=Path,required=True)
    p.add_argument("--reference-scripts",type=Path,required=True)
    args=p.parse_args();study=args.study.resolve()
    target=study/"recorded_dispatches/v14_net_fertilizer_development8"
    assert not target.exists()
    selection=study/"selections/development.json";selected=read(selection);cases=selected["cases"]
    assert len(cases)==8 and selected["protocol_sha256"]==sha(study/"protocol.json")
    for candidate,value in HASHES.items():
        folder=study/"candidates"/candidate
        assert sha(folder/"manifest.json")==value
        manifest=read(folder/"manifest.json")
        for directory,key in (("project","files"),("harness","harness_files")):
            for name,expected in manifest[key].items():assert sha(folder/directory/name)==expected
    control_files={};reference_files={}
    for case in cases:
        assert sha(study/case["file"])==case["sha256"]
        control=study/"controls"/(case["id"]+".json");c=read(control)
        assert c["recorded_cash_match"] and c["completed"] and c["ledger_verified"] and c["case"]==case
        assert sha(control)==selected["control_sha256"][case["id"]]
        for path in (control,control.with_suffix(".actions.json")):
            control_files[path.relative_to(study).as_posix()]=sha(path)
        reference=study/"runs"/V13/"development/recorded"/(case["id"]+".json");r=read(reference)
        assert r["completed"] and r["ledger_verified"] and r["case"]==case and r["candidate_manifest_sha256"]==HASHES[V13]
        for path in (reference,reference.with_suffix(".actions.json")):
            reference_files[path.relative_to(study).as_posix()]=sha(path)
    shipping=read(study/"reports"/(V13+"-development-shipping-scores.json"))
    assert shipping["panels"]["recorded"]["complete"] and shipping["panels"]["recorded"]["technically_valid"]==8
    target.mkdir(parents=True);files={}
    for path in (ROOT/"scripts/run_semantic_recorded_pair_20260928.py",
                 args.reference_scripts/"report_semantic_strategy_shipping_20260928.py",
                 args.reference_scripts/"audit_semantic_strategy_gate_20260928.py"):
        shutil.copy2(path,target/path.name);files[path.name]=sha(path)
    addendum=read(study/"shipping_score_addendum.json");doc=study.parents[2]/addendum["document"]
    assert sha(doc)==addendum["document_sha256"]
    manifest=dict(scope="V14_RECORDED_DEVELOPMENT8_INCREMENTAL_VS_COMPLETED_V13",
        created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),study=str(study),
        protocol_sha256=sha(study/"protocol.json"),selection_sha256=sha(selection),
        shipping_score_addendum_sha256=sha(study/"shipping_score_addendum.json"),addendum_document=str(doc),addendum_document_sha256=sha(doc),
        candidate_manifests=HASHES,cases=cases,control_files=control_files,reference_result_files=reference_files,
        reference_shipping_report_sha256=sha(study/"reports"/(V13+"-development-shipping-scores.json")),
        files=files,minimum_free_gib=3.3,absolute_win_threshold=None,stop_on_technical_invalidity=True,
        dispatch_order=[dict(candidate=V14,case=c["id"]) for c in cases],
        authorization="Root authorized after user-requested fresh4 completes/audits; no V13 baseline rerun, no V14 live8 or qualification release.",
        original_strict_fragility_screen_preserved=True,qualification_dispatched=False,engine_dispatched=False)
    (target/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(dict(manifest=str(target/"manifest.json"),sha256=sha(target/"manifest.json"),planned_new_games=8,baseline_reruns=0,launched=False)))


if __name__=="__main__":main()
