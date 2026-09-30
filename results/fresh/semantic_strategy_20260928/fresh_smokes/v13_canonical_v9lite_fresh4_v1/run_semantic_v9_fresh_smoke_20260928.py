"""Four immutable fresh live worlds; no automatic qualification or seed replacement."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
MANIFEST = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
STUDY = Path(MANIFEST["study"])
FROZEN = STUDY / "candidates" / MANIFEST["candidate"]
sys.path.insert(0,str(FROZEN/"harness"))
import semantic_strategy_gate_20260928 as G

ORIGINAL_DIAGNOSTICS = G.diagnostics
ORIGINAL_LOAD = G.load_entry


def checked_load(path, project):
    result = ORIGINAL_LOAD(path,project)
    if Path(path).resolve() == (STUDY/MANIFEST["opponent"]["entry"]).resolve():
        assert result[0].__name__ == "v9lite_agent", "Wrong canonical opponent entry callable"
    return result


def diagnostics(fn):
    value = ORIGINAL_DIAGNOSTICS(fn)
    scope = getattr(fn,"__globals__",{})
    report = scope.get("_V9_REPORT")
    if isinstance(value,dict) and isinstance(report,dict):
        value["decisions"] = json.loads(json.dumps(report.get("decisions",[])))
        value["searches"] = len(report.get("seconds",[]))
        value["entry_callable"] = fn.__name__
    state = scope.get("_STATE")
    if isinstance(value,list) and isinstance(state,dict):
        kb_state = getattr(state.get("kb"),"_S",None) or {}
        days = kb_state.get("sd",{}).get("tier_days",{})
        for row in value:
            if isinstance(row,dict):
                exchange = (days.get(str(row.get("day")),{}).get("polish") or {}).get("harvest_exchange")
                if exchange is not None:
                    row["harvest_exchange"] = json.loads(json.dumps(exchange,default=str))
    return value


G.load_entry = checked_load
G.diagnostics = diagnostics


def check(case):
    from report_semantic_strategy_shipping_20260928 import technical_errors
    path = HERE/"results"/(case["id"]+".json")
    row = G.read(path)
    errors = technical_errors(row,G.read(path.with_suffix(".actions.json")))
    if row.get("case") != case or row.get("candidate_manifest_sha256") != MANIFEST["candidate_manifest_sha256"]:
        errors.append("case_or_candidate_identity")
    if row.get("protocol_sha256") != MANIFEST["protocol_sha256"] or not row.get("source_module_audit") or not row.get("eligible"):
        errors.append("protocol_import_or_live_eligibility")
    opponent = row.get("final_diagnostics",{}).get(str(1-case["seat"]),{})
    if opponent.get("entry_callable") != "v9lite_agent":
        errors.append("wrong_opponent_callable")
    seat = case["seat"]
    daily = []
    for day in range(30):
        start,end = row.get("daily",[[],[]])[seat][day:day+2] if row.get("completed") else ({},{})
        if start and end:
            daily.append(dict(day=day,cash=end["money"],
                collected_units={key.removeprefix("produced:"):value-start["physical"].get(key,0)
                    for key,value in end["physical"].items() if key.startswith("produced:")},
                sold_units={key:value-start["sold_units"].get(key,0) for key,value in end["sold_units"].items()},
                revenue={key:value-start["revenue"].get(key,0) for key,value in end["revenue"].items()}))
    return dict(case=case,technical_valid=not errors,technical_errors=errors,margin=row.get("margin"),
        cash=row.get("cash"),opponent_cash=row.get("opponent_cash"),opponent=opponent,
        decisions_were_not_forced=True,source_sha256=G.sha(path),actions_sha256=G.sha(path.with_suffix(".actions.json")),
        measured_overage=row.get("measured_overage_used"),engine=row.get("engine_audit"),
        own_daily_collection_and_sales=daily)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--released",action="store_true")
    args = p.parse_args()
    assert args.released, "Smoke remains held until its predecessor audit/resource release"
    import psutil
    G.verify_files(HERE,MANIFEST["files"])
    assert G.sha(FROZEN/"manifest.json") == MANIFEST["candidate_manifest_sha256"]
    assert G.sha(STUDY/"protocol.json") == MANIFEST["protocol_sha256"]
    G.verify_files(STUDY/"opponent/pkg",MANIFEST["opponent"]["files"])
    assert len(MANIFEST["opponent"]["files"]) == 185
    assert G.sha(STUDY/MANIFEST["opponent"]["entry"]) == MANIFEST["opponent"]["entry_sha256"]
    cases = MANIFEST["cases"]
    assert len(cases)==4 and len({r["seed"] for r in cases})==4 and sorted(r["seat"] for r in cases)==[0,0,1,1]
    assert not {r["seed"] for r in cases}.intersection(MANIFEST["seed_selection"]["excluded_seeds"])
    rows,stopped = [],None
    for case in cases:
        free = psutil.virtual_memory().available/2**30
        if free < MANIFEST["minimum_free_gib"]:
            stopped = f"Memory guard: free {free:.3f} GiB"
            break
        path = HERE/"results"/(case["id"]+".json")
        assert not path.exists(), "No rerun or replacement"
        print(json.dumps(dict(dispatch=case,free_gib=free)),flush=True)
        with ProcessPoolExecutor(max_workers=1,max_tasks_per_child=1) as pool:
            pool.submit(G.play_job,dict(study=str(STUDY),candidate=MANIFEST["candidate"],case=case,
                kind="live",output=str(path),harness_extension=dict(root=str(HERE),files=MANIFEST["files"]))).result()
        row = check(case)
        rows.append(row)
        if not row["technical_valid"]:
            stopped = "Technical invalidity; remaining original slots not dispatched"
        report = dict(scope=MANIFEST["scope"],manifest_sha256=G.sha(HERE/"manifest.json"),
            planned=4,completed=len(rows),stop_reason=stopped,rows=rows,
            wins=sum(r["technical_valid"] and (r["margin"] or 0)>0 for r in rows),
            absolute_win_threshold=None,opponent_identity=MANIFEST["opponent"],
            opponent_all185files_verified=True,qualification_dispatched=False)
        (HERE/"report.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
        print(json.dumps({k:v for k,v in row.items() if k!="own_daily_collection_and_sales"}),flush=True)
        if stopped:
            break
    print(json.dumps(dict(completed=len(rows),stop_reason=stopped)),flush=True)


if __name__ == "__main__":
    main()
