"""Independent saved-artifact audit; executes no agent or simulation."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def audit(study, candidate):
    protocol_path = study / "protocol.json"
    protocol = read(protocol_path)
    directory = study / "candidates" / candidate
    manifest_path = directory / "manifest.json"
    manifest = read(manifest_path)
    project = directory / "project"
    errors = []

    def check(ok, message):
        if not ok:
            errors.append(message)

    check(manifest["protocol_sha256"] == sha(protocol_path), "Candidate protocol hash differs")
    for root, hashes in ((project, manifest["files"]), (directory/"harness", manifest["harness_files"]),
                         (study/"opponent/pkg", protocol["opponent"]["files"])):
        for name, expected in hashes.items():
            check(sha(root/name) == expected, "Frozen file changed: " + str(root/name))
    heldouts = protocol["development"]["recorded"] + protocol["qualification"]["recorded"] + protocol["recorded_reserve"]
    heldout_ids = {case["episode"] for case in heldouts}
    check(len(heldout_ids) == len(heldouts), "Recorded panels/reserves overlap")
    live = protocol["development"]["live"] + protocol["qualification"]["live"]
    check(len({row["seed"] for row in live}) == len(live), "Live panels share seeds")
    check([x["seat"] for x in protocol["qualification"]["live"]].count(0) == 20, "Live gate not balanced")
    training = set(manifest["training_episodes"])
    check(not training.intersection(heldout_ids), "Training intersects a recorded panel/reserve")
    candidate_config = read(project/"results/fresh/semantic_strategy_20260928/candidate_config.json")
    model_file = candidate_config.get("model_file", "causal_daily_rows.json")
    model = read(project/"results/fresh/semantic_strategy_20260928"/model_file)
    model_rows = model.get("rows", [])
    if candidate_config.get("policy_kind") == "three_day_budget":
        bound = manifest["model_training_provenance"]
        source_manifest = read(project/bound["training_file"])
        check(sha(project/bound["model_file"]) == bound["model_sha256"], "Block model hash binding differs")
        check(sha(project/bound["training_file"]) == bound["training_sha256"], "Block training manifest binding differs")
        check(bound["model_file"] == "results/fresh/semantic_strategy_20260928/"+model_file,
              "Selected block model differs from provenance binding")
        check(source_manifest["source_sha256"] == model["source_sha256"] == bound["source_sha256"],
              "Block model training source hash differs")
        row_episodes = {str(ep) for ep in source_manifest["episodes"]}
        check(not model_rows, "Block runtime artifact unexpectedly includes source rows")
    else:
        row_episodes = {str(row["meta"]["episode"]) for row in model_rows}
        check(bool(model_rows), "Nearest model has no training rows")
    check(row_episodes <= training, "Model training episode missing from candidate manifest")
    forbidden = {"episode", "seed", "reward", "rewards", "source", "future_shops", "end_board", "x", "y", "tile"}
    feature_keys = set()
    for row in model_rows:
        feature_keys.update(row["features"])
        check(not forbidden.intersection(row["features"]), "Model has a forbidden top-level feature")
    if candidate_config.get("policy_kind") == "three_day_budget":
        feature_keys.update(model["demand_features"])
        check(not forbidden.intersection(feature_keys), "Block model has a forbidden demand feature")
    opening_path = project/"data/semantic_strategy/opening_v5_contracts_20260928.json.gz"
    opening = json.loads(gzip.decompress(opening_path.read_bytes()))
    opening_ids = {str(row["ep"]) for row in opening["library"]["tapes"]}
    check(not opening_ids.intersection(heldout_ids), "Opening source intersects a recorded panel/reserve")
    pace_source = read(study/"pace_training_provenance.json")
    pace_ids = set(pace_source["episodes"])
    check(sha(project/"results/fresh/semantic_strategy_20260928/runtime/results/fresh/threads_20260928/dsm_sell_pace.json")
          == pace_source["table_sha256"], "Pace training provenance is for a different table")
    check(not pace_ids.intersection(heldout_ids), "Pooled pace source intersects a recorded panel/reserve")
    inputs = dict(training_episodes=len(training), model_episodes=len(row_episodes), opening_episodes=len(opening_ids),
                  model_file=model_file,
                  recorded_panel_and_reserve_episodes=len(heldout_ids), live_seeds=len(live),
                  model_feature_keys=sorted(feature_keys), opening_permitted_steps=opening["permitted_steps"],
                  pooled_pace_training_episodes=len(pace_ids), pooled_pace_heldout_overlap=sorted(pace_ids.intersection(heldout_ids)),
                  training_heldout_overlap=sorted(training.intersection(heldout_ids)),
                  opening_heldout_overlap=sorted(opening_ids.intersection(heldout_ids)))
    modes = {}
    for split in ("development", "qualification"):
        for mode in ("live", "recorded"):
            cases = protocol[split][mode]
            selection = study/"selections"/f"{split}.json"
            if mode == "recorded" and selection.exists():
                chosen = read(selection)
                check(chosen["protocol_sha256"] == sha(protocol_path), "Selection protocol hash differs")
                check(chosen["selection_blind_to_candidate"] is True, "Selection not marked blind")
                cases = chosen["cases"]
                for case in cases:
                    control_path = study/"controls"/f'{case["id"]}.json'
                    check(sha(control_path) == chosen["control_sha256"][case["id"]], "Source control changed")
                    control = read(control_path)
                    recording = json.loads(gzip.decompress((study/case["file"]).read_bytes()))
                    check(control["cash_by_seat"] == recording["rewards"], "Original source cash mismatch")
                    check(control["eligible"] and control["completed"], "Selected original control invalid")
            expected = {row["id"]: row for row in cases}
            rows = []
            runtime, missing_private = [], []
            directory_run = study/"runs"/candidate/split/mode
            for path in sorted(directory_run.glob("*.json")):
                if path.name.endswith(".actions.json"):
                    continue
                row = read(path)
                case = row["case"]
                tag = split + "/" + mode + "/" + case["id"]
                check(expected.get(case["id"]) == case, tag + " unexpected case/input")
                check(row.get("candidate_manifest_sha256") == sha(manifest_path), tag + " source manifest differs")
                check(row.get("protocol_sha256") == sha(protocol_path), tag + " protocol hash differs")
                if row.get("completed"):
                    engine = row["engine_audit"]
                    check(engine["statuses"] == ["DONE", "DONE"] and engine["steps"] == 720 and engine["final_step"] == 719,
                          tag + " invalid engine completion")
                    actions = read(path.with_suffix(".actions.json"))
                    check([len(x) for x in actions] == [719, 719], tag + " incomplete action streams")
                    check([digest(x) for x in actions] == row["action_sha256"], tag + " action hash mismatch")
                    for seat in (0, 1):
                        check(len(row["daily"][seat]) == 31, tag + " missing ledger snapshots")
                        for day, ledger in enumerate(row["daily"][seat]):
                            check(3000 + sum(ledger["revenue"].values()) - sum(ledger["spend"].values()) == ledger["money"],
                                  tag + f" seat{seat} day{day} cash fails arithmetic")
                        final = row["daily"][seat][-1]["money"]
                        check(final == row["cash_by_seat"][seat], tag + " final ledger differs from cash")
                        used = sum(max(0.0, x - 1.0) for x in row["timings"][seat])
                        check(math.isclose(used, row["measured_overage_used"][seat], abs_tol=1e-8), tag + " runtime sum differs")
                        runtime.append(used)
                    for day in row["diagnostics"][case["seat"]]:
                        if "private" not in day.get("current_observation", {}):
                            missing_private.append(case["id"])
                    check(row["margin"] == row["cash"] - row["opponent_cash"], tag + " margin arithmetic differs")
                    health = row.get("live_opponent_internal_health") or {}
                    check(not row["eligible"] or all(not x.get("errors",0) for x in health.values()),
                          tag + " internally failed live opponent incorrectly eligible")
                    if mode == "recorded":
                        control_path = study/"controls"/f'{case["id"]}.json'
                        check(row["recorded_rival_audit"]["control_sha256"] == sha(control_path), tag + " different control")
                        check(not row["eligible"] or not row["recorded_rival_audit"]["material_command_break"],
                              tag + " broken rival incorrectly eligible")
                rows.append(row)
            valid = [row for row in rows if row.get("completed") and row.get("eligible")]
            summary = dict(expected=len(cases), recorded=len(rows), valid=len(valid),
                gate_complete=len(rows)==len(cases) and len(valid)==len(cases),
                eligible_wins=sum(row["margin"]>0 for row in valid),
                mean_valid_margin=sum(row["margin"] for row in valid)/len(valid) if valid else None,
                invalid=[row["case"]["id"] for row in rows if row not in valid],
                max_measured_overage_seconds=max(runtime, default=None),
                diagnostic_private_omitted_cases=sorted(set(missing_private)))
            report_path = study/"reports"/f"{candidate}-{split}-{mode}.json"
            if report_path.exists() and len(rows) == len(cases):
                reported = read(report_path)
                for key in ("expected", "recorded", "valid", "gate_complete", "eligible_wins", "mean_valid_margin"):
                    check(summary[key] == reported[key], f"{split}/{mode} report field {key} differs")
            modes[split+"/"+mode] = summary
    return dict(candidate=candidate, candidate_manifest_sha256=sha(manifest_path),
        independent_of_runner=True, audit_pass=not errors, errors=errors, inputs=inputs, results=modes,
        limitations=["Static feature-key/source checks complement the causal-input code review; they do not prove absence of every possible hidden data path.",
                     "smoke_v1 omitted the separately stored obs.private from diagnostic snapshots; gameplay received the full observation.",
                     "Recorded opponents cannot react to changed prices, even when the failed-command screen passes."])


def audit_fixed(study, identifier):
    """Check fixed-world artifacts without importing either execution harness."""
    directory = study/"fixed_experiments"/identifier
    manifest_path = directory/"manifest.json"
    manifest = read(manifest_path)
    protocol = read(study/"protocol.json")
    errors = []

    def check(ok, message):
        if not ok:
            errors.append(message)

    check(manifest["scope"] == "DEVELOPMENT_ONLY", "Wrong fixed-world scope")
    check(manifest["protocol_sha256"] == sha(study/"protocol.json"), "Fixed protocol changed")
    check([x["case"] for x in manifest["cases"]] == protocol["development"]["live"], "Fixed cases differ from development panel")
    for name, expected in manifest["harness_files"].items():
        check(sha(directory/"harness"/name) == expected, "Fixed harness changed: " + name)
    metrics, native_exact, fixed_reference_valid = {}, {}, {}
    paired = []
    reference = manifest["reference_candidate"]
    for item in manifest["cases"]:
        case = item["case"]
        native_path = study/item["source"]
        check(sha(native_path) == item["source_sha256"], "Native source result changed")
        check(sha(native_path.with_suffix(".actions.json")) == item["source_actions_sha256"], "Native source actions changed")
        native = read(native_path)
        natural_shops = [x["current_observation"]["town"]["unlocked_shops"] for x in native["diagnostics"][case["seat"]]]+[native["shops"]]
        check(natural_shops == item["shops"], "Declared fixed shops differ from source")
        reference_path = directory/"runs"/reference/f'{case["id"]}.json'
        reference_row = read(reference_path) if reference_path.exists() else None
        if reference_row:
            native_exact[case["id"]] = (reference_row.get("cash_by_seat")==native["cash_by_seat"]
                                        and reference_row.get("action_sha256")==native["action_sha256"])
        for candidate, expected_manifest in manifest["candidate_manifest_sha256"].items():
            check(sha(study/"candidates"/candidate/"manifest.json") == expected_manifest, "Bound candidate changed")
            output = directory/"runs"/candidate/f'{case["id"]}.json'
            metric = metrics.setdefault(candidate,{"expected":len(manifest["cases"]),"recorded":0,"valid":0,"wins":0,"margins":[]})
            if not output.exists():
                continue
            row = read(output)
            metric["recorded"] += 1
            tag = candidate+"/"+case["id"]
            check(row["case"] == case, tag+" case mismatch")
            check(row.get("candidate_manifest_sha256") == expected_manifest, tag+" candidate mismatch")
            check(row.get("forced_shops_sha256") == digest(item["shops"]), tag+" forced input mismatch")
            check(row.get("fixed_world",{}).get("experiment_manifest_sha256") == sha(manifest_path), tag+" experiment mismatch")
            if not row.get("completed"):
                continue
            check(row["engine_audit"]["statuses"] == ["DONE","DONE"] and row["engine_audit"]["steps"]==720, tag+" engine incomplete")
            actual_shops = [x["current_observation"]["town"]["unlocked_shops"] for x in row["diagnostics"][case["seat"]]]+[row["shops"]]
            check(actual_shops == item["shops"], tag+" actual shop history differs")
            actions = read(output.with_suffix(".actions.json"))
            check([len(x) for x in actions] == [719,719] and [digest(x) for x in actions] == row["action_sha256"], tag+" action hash/length mismatch")
            for seat in (0,1):
                for day, ledger in enumerate(row["daily"][seat]):
                    check(3000+sum(ledger["revenue"].values())-sum(ledger["spend"].values())==ledger["money"], tag+f" cash arithmetic seat{seat}day{day}")
                check(row["daily"][seat][-1]["money"]==row["cash_by_seat"][seat], tag+" final cash mismatch")
                overage = sum(max(0.0,x-1.0) for x in row["timings"][seat])
                check(math.isclose(overage,row["measured_overage_used"][seat],abs_tol=1e-8), tag+" timing mismatch")
            if row.get("eligible"):
                metric["valid"] += 1
                metric["wins"] += row["margin"]>0
                metric["margins"].append(row["margin"])
                if candidate == reference:
                    fixed_reference_valid[case["id"]] = True
                elif reference_row and reference_row.get("completed") and reference_row.get("eligible"):
                    paired.append(dict(case=case["id"],candidate=candidate,margin_delta=row["margin"]-reference_row["margin"],
                                       own_cash_delta=row["cash"]-reference_row["cash"],rival_cash_delta=row["opponent_cash"]-reference_row["opponent_cash"]))
    for value in metrics.values():
        margins = value.pop("margins")
        value["mean_margin"] = sum(margins)/len(margins) if margins else None
        value["complete"] = value["recorded"]==value["expected"]==value["valid"]
    return dict(experiment=identifier,scope="DEVELOPMENT_ONLY",independent_of_runner=True,audit_pass=not errors,errors=errors,
        valid_forced_references=len(fixed_reference_valid),native_exact_reproductions=sum(native_exact.values()),
        native_divergences=[key for key,value in native_exact.items() if not value],results=metrics,paired=paired,
        note="Paired values use newly executed forced references; natural outcomes are not reused. All comparisons remain development evidence.")


def audit_oracle(study,identifier):
    """Independently check the separate oracle inputs, handoff and full ledgers."""
    directory=study/"oracle_diagnostics"/identifier
    manifest=read(directory/"manifest.json")
    errors=[]
    def check(ok,message):
        if not ok: errors.append(message)
    check(manifest["scope"]=="COMPONENT_DIAGNOSTIC_NOT_POLICY","Wrong oracle scope")
    check(manifest["protocol_sha256"]==sha(study/"protocol.json"),"Oracle protocol changed")
    reused=manifest.get("reused_exact_reference")
    reference_directory=study/"oracle_diagnostics"/reused["id"] if reused else directory
    if reused:
        check(sha(reference_directory/"manifest.json")==reused["manifest_sha256"],"Reused oracle reference changed")
        for name,expected in reused["files"].items():check(sha(study/name)==expected,"Reused source/result changed: "+name)
        old=read(reference_directory/"manifest.json")
        check(old["options"]==manifest["options"],"Reused exact options differ")
        check(read(reference_directory/"exact_plans.json")==read(directory/"exact_plans.json"),"Reused exact plans differ")
        check(read(reference_directory/"candidates/exact/manifest.json")["files"]==read(directory/"candidates/exact/manifest.json")["files"],"Reused exact executor differs")
    for folder,key in (("harness","harness_files"),("compiler","compiler_files"),(".","input_files")):
        for name,expected in manifest[key].items():
            check(sha(directory/folder/name)==expected,"Oracle frozen file changed: "+name)
    expected_order=sorted(manifest["universe"],key=lambda ep:digest(["oracle6-component-20260928",ep]))
    check(len(expected_order)==40 and [x["episode"] for x in manifest["cases"]]==expected_order[:8],"Oracle selection differs")
    protocol=read(study/"protocol.json")
    heldout={x["episode"] for split in ("development","qualification") for x in protocol[split]["recorded"]}
    heldout.update(x["episode"] for x in protocol["recorded_reserve"])
    check(not heldout.intersection(expected_order),"Oracle universe overlaps reserved causal cases")
    inputs=read(directory/"semantic_inputs.json")
    plans={arm:read(directory/f"{arm}_plans.json") for arm in manifest["arms"]}
    for ep,sem in inputs.items():
        check(sem["handoff_day"]==6 and sem["semantic_scope"]=="tile_changes_only","Non-strict D6 semantic input")
        initial=sem["initial_state"]
        check(all((label==" L")==bool(initial["tiles"].get(str(t),{}).get("locked"))
            for t,label in enumerate(initial["board"])),ep+" observed locked cells are missing from semantic state")
        check(all("first_harvest_counts" not in day for day in sem["days"]),"Future first-harvest information present")
        a,b=plans["exact"][ep],plans["retile"][ep]
        check(len(a["cum_sold"])==6 and a["cum_sold"]==b["cum_sold"],"Future sales or different prefix sales")
        check(a["hands"]==b["hands"] and a["land_day"]==b["land_day"],"Different hires or land calendar")
        check(not b["planner_metadata"]["warnings"],"Retile compiler warnings")
        placements=[(d,int(t),crop) for d,t,crop in b["events"] if d>=6]
        for key in ("struct_by_day","animals_by_day"):
            placements.extend((d,int(t),kind) for d in range(6,30) for t,kind in b[key][d].items()
                if b[key][d-1].get(t)!=kind)
        premature=[]
        for day,tile,kind in placements:
            quadrant=("N" if tile//10<5 else "S")+("W" if tile%10<5 else "E")
            if day < (0 if quadrant=="NW" else b["land_day"].get(quadrant,99)):
                premature.append((day,tile,kind))
        check(not premature,ep+f" retile has {len(premature)} placements before land purchase")
    def game_audit(path,row,tag):
        before=len(errors)
        check(row["protocol_sha256"]==sha(study/"protocol.json"),tag+" protocol differs")
        if not row.get("completed"):return False
        a=read(path.with_suffix(".actions.json"))
        check([len(x) for x in a]==[719,719] and [digest(x) for x in a]==row["action_sha256"],tag+" actions differ")
        engine=row["engine_audit"]
        check(engine["statuses"]==["DONE","DONE"] and engine["steps"]==720 and engine["final_step"]==719,tag+" engine incomplete")
        for seat in (0,1):
            check(len(row["daily"][seat])==31,tag+" missing ledger days")
            for day in row["daily"][seat]:
                check(3000+sum(day["revenue"].values())-sum(day["spend"].values())==day["money"],tag+" ledger arithmetic differs")
            check(row["daily"][seat][-1]["money"]==row["cash_by_seat"][seat],tag+" final cash differs")
            used=sum(max(0.0,t-1.0) for t in row["timings"][seat])
            check(math.isclose(used,row["measured_overage_used"][seat],abs_tol=1e-8),tag+" timing arithmetic differs")
            check(not row["eligible"] or used<=60,tag+" over-budget game eligible")
        return len(errors)==before and bool(row.get("eligible"))
    controls={}
    for case in manifest["cases"]:
        check(sha(study/case["file"])==case["sha256"],"Oracle recording changed")
        path=reference_directory/"controls"/f'{case["id"]}.json'
        if path.exists():
            row=read(path);recording=json.loads(gzip.decompress((study/case["file"]).read_bytes()))
            check(row["case"]==case,"Oracle source identity differs")
            check(row.get("cash_by_seat")==recording["rewards"],"Original source cash differs")
            valid=game_audit(path,row,"source/"+case["id"])
            if valid and row.get("cash_by_seat")==recording["rewards"]:controls[case["id"]]=(path,row)
    metrics={};by_arm={}
    for arm in manifest["arms"]:
        candidate=directory/"candidates"/arm
        cm=read(candidate/"manifest.json")
        check(sha(candidate/"manifest.json")==manifest["candidate_manifest_sha256"][arm],"Oracle candidate changed")
        for folder,key in (("project","files"),("harness","harness_files")):
            for name,expected in cm[key].items():check(sha(candidate/folder/name)==expected,"Oracle dependency changed: "+name)
        rows=[];recorded=0;by_arm[arm]={}
        for case in manifest["cases"]:
            path=(reference_directory if reused and arm=="exact" else directory)/"runs"/arm/f'{case["id"]}.json'
            if not path.exists():continue
            recorded+=1;row=read(path);tag=arm+"/"+case["id"];before=len(errors)
            valid=game_audit(path,row,tag)
            check(row["case"]==case,tag+" case differs")
            expected_candidate=reused["exact_candidate_manifest_sha256"] if reused and arm=="exact" else manifest["candidate_manifest_sha256"][arm]
            check(row["candidate_manifest_sha256"]==expected_candidate,tag+" candidate differs")
            if case["id"] not in controls:valid=False
            elif row.get("completed"):
                cp,control=controls[case["id"]]
                actions,original=read(path.with_suffix(".actions.json")),read(cp.with_suffix(".actions.json"))
                check(all(actions[i][:144]==original[i][:144] for i in (0,1)),tag+" original prefix differs")
                check(row.get("handoff_observation_sha256")==control.get("handoff_observation_sha256")
                    and set(row.get("handoff_observation_sha256",{}))=={"0","1"},tag+" D6 private/public handoff differs")
                check(row["recorded_rival_audit"]["control_sha256"]==sha(cp),tag+" source control hash differs")
                bound=row.get("oracle_world",{})
                expected_experiment=reused["manifest_sha256"] if reused and arm=="exact" else sha(directory/"manifest.json")
                check(bound.get("experiment_manifest_sha256")==expected_experiment,tag+" experiment binding differs")
                check(bound.get("plan_sha256")==digest(plans[arm][case["episode"]]),tag+" supplied plan differs")
            if valid and len(errors)==before:rows.append(row);by_arm[arm][case["id"]]=row
        metrics[arm]=dict(expected=8,recorded=recorded,valid=len(rows),complete=len(rows)==8,
            wins=sum(x["margin"]>0 for x in rows),mean_margin=sum(x["margin"] for x in rows)/len(rows) if rows else None)
    paired=[dict(case=k,margin_delta=b["margin"]-by_arm["exact"][k]["margin"],
        own_cash_delta=b["cash"]-by_arm["exact"][k]["cash"],rival_cash_delta=b["opponent_cash"]-by_arm["exact"][k]["opponent_cash"])
        for k,b in by_arm["retile"].items() if k in by_arm["exact"]]
    return dict(experiment=identifier,scope=manifest["scope"],independent_of_runner=True,audit_pass=not errors,
        errors=errors,valid_source_controls=len(controls),results=metrics,paired=paired,
        note="Old training/development worlds with future oracle intent; no causal policy or qualification claim.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, default=ROOT/"results/fresh/semantic_strategy_20260928")
    parser.add_argument("--candidate")
    parser.add_argument("--fixed-experiment")
    parser.add_argument("--oracle-experiment")
    args = parser.parse_args()
    if sum(bool(x) for x in (args.candidate,args.fixed_experiment,args.oracle_experiment))!=1:
        parser.error("Specify exactly one of --candidate, --fixed-experiment or --oracle-experiment")
    if args.oracle_experiment:
        result = audit_oracle(args.study.resolve(), args.oracle_experiment)
        output = args.study/"oracle_diagnostics"/args.oracle_experiment/"independent-audit.json"
    elif args.fixed_experiment:
        result = audit_fixed(args.study.resolve(), args.fixed_experiment)
        output = args.study/"fixed_experiments"/args.fixed_experiment/"independent-audit.json"
    else:
        result = audit(args.study.resolve(), args.candidate)
        output = args.study/"reports"/f"{args.candidate}-independent-audit.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
