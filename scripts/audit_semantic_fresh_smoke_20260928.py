"""Independent saved-artifact audit of the four fresh V9-lite smoke worlds."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys


def read(path):return json.loads(path.read_text(encoding="utf-8"))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--smoke",type=Path,required=True)
    args=p.parse_args();directory=args.smoke.resolve();m=read(directory/"manifest.json");study=Path(m["study"])
    sys.path.insert(0,str(directory))
    from report_semantic_strategy_shipping_20260928 import technical_errors
    errors=[]
    def check(ok,message):
        if not ok:errors.append(message)
    check(sha(study/"protocol.json")==m["protocol_sha256"],"protocol binding")
    candidate=study/"candidates"/m["candidate"]
    check(sha(candidate/"manifest.json")==m["candidate_manifest_sha256"],"candidate binding")
    cm=read(candidate/"manifest.json")
    for folder,key in (("project","files"),("harness","harness_files")):
        for name,value in cm[key].items():check(sha(candidate/folder/name)==value,"candidate file:"+name)
    for name,value in m["files"].items():check(sha(directory/name)==value,"adapter file:"+name)
    for name,value in m["opponent"]["files"].items():check(sha(study/"opponent/pkg"/name)==value,"opponent file:"+name)
    check(len(m["opponent"]["files"])==185,"canonical opponent file count")
    entry=study/m["opponent"]["entry"]
    check(sha(entry)==m["opponent"]["entry_sha256"],"canonical main binding")
    funcs=[n.name for n in ast.parse(entry.read_text()).body if isinstance(n,ast.FunctionDef)]
    check(funcs[-1]=="v9lite_agent","last new source callable")
    cases=m["cases"];seeds={c["seed"] for c in cases}
    check(len(cases)==len(seeds)==4 and sorted(c["seat"] for c in cases)==[0,0,1,1],"case balance/identity")
    check(not seeds.intersection(m["seed_selection"]["excluded_seeds"]),"prior seed overlap")
    rows=[]
    for case in cases:
        path=directory/"results"/(case["id"]+".json")
        if not path.exists():errors.append("missing:"+case["id"]);continue
        r=read(path);actions=read(path.with_suffix(".actions.json"));issues=technical_errors(r,actions)
        if r.get("case")!=case or r.get("candidate_manifest_sha256")!=m["candidate_manifest_sha256"]:issues.append("identity")
        if r.get("protocol_sha256")!=m["protocol_sha256"] or not r.get("source_module_audit") or not r.get("eligible"):issues.append("provenance/eligibility")
        seat=case["seat"];opponent=r.get("final_diagnostics",{}).get(str(1-seat),{})
        if opponent.get("entry_callable")!="v9lite_agent":issues.append("runtime callable")
        decisions=opponent.get("decisions",[])
        if len(decisions)!=opponent.get("searches") or len(decisions)!=len(opponent.get("seconds",[])):issues.append("search diagnostics count")
        for item in decisions:
            if not isinstance(item,list) or len(item)!=3 or item[0] not in (12,15,18):issues.append("decision shape")
        errors.extend(case["id"]+":"+x for x in issues)
        adaptation=[]
        for day in (12,15,18):
            diagnostic=next(x for x in r["diagnostics"][seat] if x["day"]==day)
            observation=diagnostic["current_observation"]
            proposal=next(x for x in r["final_diagnostics"][str(seat)] if x["day"]==day)
            a,b=r["daily"][seat][day],r["daily"][seat][day+3]
            adaptation.append(dict(day=day,current_shops=observation["town"].get("unlocked_shops"),
                current_prices=observation["market"]["prices"],semantic_proposal=proposal.get("proposal"),
                policy_diagnostics=proposal.get("policy"),next3days_collected_units={k.removeprefix("produced:"):v-a["physical"].get(k,0)
                    for k,v in b["physical"].items() if k.startswith("produced:")},
                next3days_sold_units={k:v-a["sold_units"].get(k,0) for k,v in b["sold_units"].items()},
                next3days_revenue={k:v-a["revenue"].get(k,0) for k,v in b["revenue"].items()}))
        rows.append(dict(case=case,technical_valid=not issues,margin=r.get("margin"),cash=r.get("cash"),opponent_cash=r.get("opponent_cash"),
            opponent_searches=opponent.get("searches"),opponent_extra_search_driven_overrides=opponent.get("switches"),
            opponent_decisions=decisions,opponent_errors=opponent.get("errors"),opponent_runtime_callable=opponent.get("entry_callable"),
            overage=r.get("measured_overage_used"),remaining_overage=r.get("engine_audit",{}).get("remaining_overage"),
            public_reveal_and_own_output_snapshots=adaptation,result_sha256=sha(path),actions_sha256=sha(path.with_suffix(".actions.json"))))
    out=dict(scope=m["scope"],audit_pass=not errors,errors=errors,planned=4,completed=len(rows),
        manifest_sha256=sha(directory/"manifest.json"),candidate_manifest_sha256=m["candidate_manifest_sha256"],
        opponent_entry_sha256=sha(entry),opponent_package_files_verified=185,opponent_last_callable="v9lite_agent",
        seed_selection_outcome_blind=True,prior_declared_seed_count=m["seed_selection"]["excluded_seed_count"],
        wins=sum(x["technical_valid"] and x["margin"]>0 for x in rows),
        mean_margin=sum(x["margin"] for x in rows)/len(rows) if rows and not errors else None,rows=rows,
        interpretation="V9 switches counts extra search-driven overrides, not all native tape-router changes. Native routing and market response remain active at zero overrides. Collected units are HARVEST inventory gains, not biological production. Four fresh worlds are a smoke, not qualification or an isolated treatment-effect estimate.",
        qualification_dispatched=False,script_sha256=sha(Path(__file__)))
    path=directory/"independent-audit.json";assert not path.exists();path.write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in out.items() if k not in ("rows","interpretation")},indent=2))


if __name__=="__main__":main()
