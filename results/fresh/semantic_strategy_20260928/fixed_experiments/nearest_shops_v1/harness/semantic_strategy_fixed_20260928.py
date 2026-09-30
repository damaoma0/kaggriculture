"""Development-only responsive live opponents under a frozen shop schedule.

prepare --id NAME --reference CANDIDATE --candidates CANDIDATE,...
run --id NAME --candidate CANDIDATE [--workers 1]
report --id NAME --candidate CANDIDATE

The reference's natural development result supplies shop schedules only to the
harness. A forced reference must reproduce both native action streams and cash
totals before another candidate is eligible in that world. No qualification
worlds, source snapshots, or original outputs are changed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

import semantic_strategy_gate_20260928 as G

ROOT = Path(__file__).resolve().parents[1]


def schedules(row):
    seat = row["case"]["seat"]
    snapshots = {int(x["day"]): x["current_observation"]["town"]["unlocked_shops"]
                 for x in row["diagnostics"][seat]}
    if set(snapshots) != set(range(30)):
        raise ValueError("Reference must include every day0–29 shop snapshot")
    return [snapshots[day] for day in range(30)] + [row["shops"]]


def prepare(study, identifier, reference, candidates):
    if not identifier or not identifier.replace("_", "").replace("-", "").isalnum():
        raise ValueError("A simple --id is required")
    destination = study/"fixed_experiments"/identifier
    if destination.exists():
        raise ValueError("Experiment already exists; use a new immutable ID")
    protocol = G.read(study/"protocol.json")
    hashes = {candidate: G.sha(study/"candidates"/candidate/"manifest.json")
              for candidate in sorted(set([reference, *candidates]))}
    cases = []
    for case in protocol["development"]["live"]:
        source = study/"runs"/reference/"development/live"/f'{case["id"]}.json'
        row = G.read(source)
        if not row.get("completed") or not row.get("eligible") or row["case"] != case:
            raise ValueError("Reference development result is incomplete/invalid")
        if row["candidate_manifest_sha256"] != hashes[reference]:
            raise ValueError("Reference source manifest differs")
        cases.append(dict(case=case, source=source.relative_to(study).as_posix(), source_sha256=G.sha(source),
                          source_actions_sha256=G.sha(source.with_suffix(".actions.json")),
                          shops=schedules(row)))
    destination.mkdir(parents=True)
    harness = destination/"harness"
    harness.mkdir()
    harness_files = {}
    for name in (Path(__file__).name, "semantic_strategy_gate_20260928.py", *G.HELPERS):
        shutil.copy2(ROOT/"scripts"/name, harness/name)
        harness_files[name] = G.sha(harness/name)
    manifest = dict(id=identifier, created_utc=G.utc(), scope="DEVELOPMENT_ONLY", mode="live_fixed",
        reference_candidate=reference, candidate_manifest_sha256=hashes,
        protocol_sha256=G.sha(study/"protocol.json"), cases=cases, harness_files=harness_files,
        source_control="Force the native reference's daily shops, require both719-action streams and both final cash totals exactly equal to native reference; normal engine and ledger checks must also pass.",
        input_boundary="Only the harness receives the fixed shop schedule. Candidate and live V9lite receive current official observation/configuration.",
        differences="Shop schedules fixed to reference natural worlds; weeds remain natural. This estimates candidate differences in those shop worlds, separately from natural full-policy performance.")
    G.write(destination/"manifest.json", manifest)
    return manifest


def verify(study, identifier):
    directory = study/"fixed_experiments"/identifier
    manifest = G.read(directory/"manifest.json")
    if manifest["scope"] != "DEVELOPMENT_ONLY" or manifest["protocol_sha256"] != G.sha(study/"protocol.json"):
        raise ValueError("Fixed experiment scope/protocol changed")
    G.verify_files(directory/"harness", manifest["harness_files"])
    protocol = G.read(study/"protocol.json")
    if [x["case"] for x in manifest["cases"]] != protocol["development"]["live"]:
        raise ValueError("Fixed experiments must use exactly the eight development live cases")
    for candidate, expected in manifest["candidate_manifest_sha256"].items():
        if G.sha(study/"candidates"/candidate/"manifest.json") != expected:
            raise ValueError("Bound candidate manifest changed")
    for item in manifest["cases"]:
        source = study/item["source"]
        if G.sha(source) != item["source_sha256"] or G.sha(source.with_suffix(".actions.json")) != item["source_actions_sha256"]:
            raise ValueError("Bound natural reference result/actions changed")
        if schedules(G.read(source)) != item["shops"]:
            raise ValueError("Fixed shops do not match bound reference snapshots")
    return directory, manifest


def certify_reference(study, directory, manifest):
    rows = []
    candidate = manifest["reference_candidate"]
    for item in manifest["cases"]:
        output = directory/"runs"/candidate/f'{item["case"]["id"]}.json'
        if not output.exists():
            continue
        row, source = G.read(output), G.read(study/item["source"])
        check = dict(case=item["case"], reference_result_sha256=G.sha(output),
            native_source_sha256=item["source_sha256"], cash_equal=row.get("cash_by_seat")==source["cash_by_seat"],
            both_action_streams_equal=row.get("action_sha256")==source["action_sha256"],
            fixed_input_matches=row.get("forced_shops_sha256")==G.digest(item["shops"])
                and row.get("fixed_world",{}).get("experiment_manifest_sha256")==G.sha(directory/"manifest.json")
                and row.get("case")==item["case"]
                and row.get("candidate_manifest_sha256")==manifest["candidate_manifest_sha256"][candidate],
            engine_ledger_runtime_valid=bool(row.get("completed") and row.get("eligible")))
        check["reproduced"] = all(check[key] for key in ("cash_equal", "both_action_streams_equal", "engine_ledger_runtime_valid", "fixed_input_matches"))
        rows.append(check)
    G.write(directory/"reference_reproduction.json", rows)
    return {x["case"]["id"]:x for x in rows}


def run(study, identifier, candidate, workers, external_workers):
    directory, manifest = verify(study, identifier)
    if candidate not in manifest["candidate_manifest_sha256"]:
        raise ValueError("Candidate was not bound before fixed-world execution")
    import psutil
    free = psutil.virtual_memory().available/2**30
    workers = min(workers, max(0,4-external_workers), int((free-1.5)/1.8))
    if workers < 1:
        raise ValueError("Insufficient memory or shared worker slots")
    reference = manifest["reference_candidate"]

    def jobs_for(agent, approved=None):
        jobs = []
        for item in manifest["cases"]:
            case = item["case"]
            if approved is not None and not approved.get(case["id"],{}).get("reproduced"):
                continue
            output = directory/"runs"/agent/f'{case["id"]}.json'
            if output.exists():
                row = G.read(output)
                if row.get("candidate_manifest_sha256") != manifest["candidate_manifest_sha256"][agent]:
                    raise ValueError("Existing result has a different candidate")
                continue
            jobs.append(dict(study=str(study), candidate=agent, case=case, kind="live_fixed", output=str(output),
                force_shops=item["shops"], fixed_world=dict(experiment_id=identifier,
                    experiment_manifest_sha256=G.sha(directory/"manifest.json"),
                    reference_candidate=reference, reference_source_sha256=item["source_sha256"]),
                harness_extension=dict(root=str(directory/"harness"), files=manifest["harness_files"])))
        return jobs

    # Controls are run first, irrespective of requested candidate, and never replaced.
    G.pool_run(jobs_for(reference), workers)
    controls = certify_reference(study, directory, manifest)
    if candidate != reference:
        G.pool_run(jobs_for(candidate, controls), workers)
    return report(study, identifier, candidate)


def report(study, identifier, candidate):
    directory, manifest = verify(study, identifier)
    controls = certify_reference(study, directory, manifest)
    rows = [G.read(p) for p in (directory/"runs"/candidate).glob("*.json") if not p.name.endswith(".actions.json")]
    expected = {x["case"]["id"]:x for x in manifest["cases"]}
    valid = [r for r in rows if r.get("completed") and r.get("eligible") and controls.get(r["case"]["id"],{}).get("reproduced")
             and r["case"]==expected[r["case"]["id"]]["case"]
             and r.get("candidate_manifest_sha256")==manifest["candidate_manifest_sha256"][candidate]
             and r.get("forced_shops_sha256")==G.digest(expected[r["case"]["id"]]["shops"])
             and r.get("fixed_world",{}).get("experiment_manifest_sha256")==G.sha(directory/"manifest.json")]
    result = dict(experiment=identifier, candidate=candidate, mode="live_fixed", scope="DEVELOPMENT_ONLY",
        expected=len(manifest["cases"]), recorded=len(rows), valid=len(valid),
        reference_reproductions=sum(x["reproduced"] for x in controls.values()),
        gate_complete=len(valid)==len(manifest["cases"]) and len(rows)==len(manifest["cases"]),
        eligible_wins=sum(r["margin"]>0 for r in valid),
        mean_valid_margin=sum(r["margin"] for r in valid)/len(valid) if valid else None,
        invalid_or_missing_cases=[x["case"]["id"] for x in manifest["cases"] if x["case"]["id"] not in {r["case"]["id"] for r in valid}],
        warning="Separate development fixed-shop evidence; never pool with natural or qualification results. Failed source reproduction leaves the planned denominator incomplete.")
    G.write(directory/"reports"/f"{candidate}.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare","run","report"))
    parser.add_argument("--study", type=Path, default=ROOT/"results/fresh/semantic_strategy_20260928")
    parser.add_argument("--id", required=True)
    parser.add_argument("--reference")
    parser.add_argument("--candidates", default="")
    parser.add_argument("--candidate")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--external-workers", type=int, default=0)
    parser.add_argument("--frozen", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 1 <= args.workers <= 4 or not 0 <= args.external_workers <= 3:
        parser.error("--workers must be 1..4 and --external-workers 0..3")
    study = args.study.resolve()
    if args.command == "prepare":
        if not args.reference:
            parser.error("prepare requires --reference")
        value = prepare(study,args.id,args.reference,[x for x in args.candidates.split(",") if x])
        print(G.digest(value))
    elif not args.candidate:
        parser.error("run/report requires --candidate")
    elif args.command == "run" and not args.frozen:
        script = study/"fixed_experiments"/args.id/"harness"/Path(__file__).name
        raise SystemExit(subprocess.call([sys.executable,str(script),"run","--study",str(study),"--id",args.id,
            "--candidate",args.candidate,"--workers",str(args.workers),"--external-workers",str(args.external_workers),"--frozen"]))
    elif args.command == "run":
        print(json.dumps(run(study,args.id,args.candidate,args.workers,args.external_workers),indent=2))
    else:
        print(json.dumps(report(study,args.id,args.candidate),indent=2))


if __name__ == "__main__":
    main()
