"""Explicitly released recorded pair, serial fresh processes, no case replacement."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
MANIFEST = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
STUDY = Path(MANIFEST["study"])


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def verify():
    for name, value in MANIFEST["files"].items():
        assert sha(HERE / name) == value
    assert sha(STUDY / "protocol.json") == MANIFEST["protocol_sha256"]
    assert sha(STUDY / "selections/development.json") == MANIFEST["selection_sha256"]
    assert sha(STUDY / "shipping_score_addendum.json") == MANIFEST["shipping_score_addendum_sha256"]
    assert sha(Path(MANIFEST["addendum_document"])) == MANIFEST["addendum_document_sha256"]
    for name, value in MANIFEST["control_files"].items():
        assert sha(STUDY / name) == value
    for name, value in MANIFEST["candidate_manifests"].items():
        assert sha(STUDY / "candidates" / name / "manifest.json") == value


def result_path(candidate, case):
    return STUDY / "runs" / candidate / "development/recorded" / (case["id"] + ".json")


def check(candidate, case):
    from report_semantic_strategy_shipping_20260928 import technical_errors
    path = result_path(candidate, case)
    row = read(path)
    actions = read(path.with_suffix(".actions.json"))
    errors = technical_errors(row, actions)
    if row.get("case") != case or row.get("candidate_manifest_sha256") != MANIFEST["candidate_manifests"][candidate]:
        errors.append("case_or_candidate_identity")
    if row.get("protocol_sha256") != MANIFEST["protocol_sha256"] or not row.get("source_module_audit"):
        errors.append("protocol_or_import_audit")
    control = STUDY / "controls" / (case["id"] + ".json")
    if row.get("recorded_rival_audit", {}).get("control_sha256") != sha(control):
        errors.append("source_control_binding")
    audit = row.get("recorded_rival_audit", {})
    if not row.get("eligible") and not audit.get("material_command_break"):
        errors.append("unexplained_ineligibility")
    return dict(candidate=candidate, case=case["id"], technical_valid=not errors, technical_errors=errors,
        original_strict_eligible=row.get("eligible"), recorded_rival_audit=audit,
        margin=row.get("margin"), cash=row.get("cash"), opponent_cash=row.get("opponent_cash"),
        result_sha256=sha(path), actions_sha256=sha(path.with_suffix(".actions.json")))


def single(candidate, case):
    # Each process imports only its candidate's hash-bound original harness.
    sys.path.insert(0, str(STUDY / "candidates" / candidate / "harness"))
    import semantic_strategy_gate_20260928 as G
    original = G.diagnostics
    def diagnostics(fn):
        value = original(fn)
        state = getattr(fn, "__globals__", {}).get("_STATE")
        if isinstance(value, list) and isinstance(state, dict):
            kb_state = getattr(state.get("kb"), "_S", None) or {}
            days = kb_state.get("sd", {}).get("tier_days", {})
            for row in value:
                if isinstance(row, dict):
                    exchange = (days.get(str(row.get("day")), {}).get("polish") or {}).get("harvest_exchange")
                    if exchange is not None:
                        row["harvest_exchange"] = json.loads(json.dumps(exchange, default=str))
        return value
    G.diagnostics = diagnostics
    path = result_path(candidate, case)
    assert not path.exists(), "Never rerun an existing outcome"
    print(json.dumps(G.play_job(dict(study=str(STUDY), candidate=candidate, case=case, kind="recorded", output=str(path),
        control=str(STUDY / "controls" / (case["id"] + ".json")),
        harness_extension=dict(root=str(HERE), files=MANIFEST["files"])))), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--released", action="store_true")
    p.add_argument("--single-candidate")
    p.add_argument("--single-case")
    args = p.parse_args()
    assert args.released, "This prepared experiment requires explicit release"
    verify()
    cases = {case["id"]:case for case in MANIFEST["cases"]}
    if args.single_candidate:
        assert args.single_candidate in MANIFEST["candidate_manifests"]
        single(args.single_candidate, cases[args.single_case])
        return
    import psutil
    rows, stopped = [], None
    for job in MANIFEST["dispatch_order"]:
        free = psutil.virtual_memory().available / 2**30
        if free < MANIFEST["minimum_free_gib"]:
            stopped = f"Memory guard: free {free:.3f} GiB"
            break
        case = cases[job["case"]]
        assert not result_path(job["candidate"], case).exists(), "No reruns or selective replacements"
        print(json.dumps(dict(dispatch=job, free_gib=free)), flush=True)
        subprocess.run([sys.executable, str(Path(__file__).resolve()), "--released", "--single-candidate", job["candidate"],
                        "--single-case", case["id"]], check=True)
        row = check(job["candidate"], case)
        rows.append(row)
        if not row["technical_valid"]:
            stopped = "Technical invalidity; remaining games not dispatched"
        value = dict(scope=MANIFEST["scope"], rows=rows, planned=16, completed=len(rows), stop_reason=stopped,
            absolute_win_threshold=None, qualification_dispatched=False)
        (HERE / "checkpoint.json").write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(row), flush=True)
        if stopped:
            break
    print(json.dumps(dict(completed=len(rows), stop_reason=stopped, qualification_dispatched=False)), flush=True)


if __name__ == "__main__":
    main()
