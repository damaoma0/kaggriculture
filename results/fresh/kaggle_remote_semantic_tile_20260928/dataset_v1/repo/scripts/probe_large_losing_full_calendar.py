"""Compile and exact-replay the donor calendar for a large losing mismatch."""
from collections import Counter
from copy import deepcopy
import gzip
import json
import time

from fragments.continuation_calendar import adapt_calendar
from fragments.continuation_projection import check_window
from fragments import continuation_executor as executor
import research_labour_profit as R
from probe_semantic_handoff import ROOT, donor_window


OUT=ROOT/"results/fresh/semantic_tapes/large_losing_full_calendar.json"
EPISODE,DAY=111287532,18
START,STOP=DAY*24,(DAY+3)*24


def compile_plan(obs,profile,drop_carrots=0,drop_one_day18_wheat=False):
    donor=donor_window(profile,DAY)
    for _ in range(drop_carrots):
        target=next(i for i,job in enumerate(donor["jobs"])
                    if job["day"]==2 and job["cmd"]==["PLANT","CARROT"])
        donor["jobs"].pop(target)
    if drop_one_day18_wheat:
        target=next(i for i,job in enumerate(donor["jobs"])
                    if job["day"]==0 and job["cmd"]==["PLANT","WHEAT"])
        donor["jobs"].pop(target)
    node=adapt_calendar(obs,donor)
    node["hire_to"]=12
    executor.set_deadline(time.perf_counter()+5.0)
    started=time.perf_counter()
    try:
        result=check_window(obs,node,executor)
    except executor.PlanningBudgetExceeded:
        result={"ok":False,"failure":{"reason":"planning_budget"}}
    finally:
        executor.set_deadline(None)
    return {"ok":bool(result["ok"]),"seconds":time.perf_counter()-started,
            "failure":result.get("failure"),"slack":node["calendar_slack"],
            "actions":result.get("actions")}


def evaluate(game,pair,seat,stop):
    with R.Simulator(game) as sim:
        result=sim.run(sim.initial,0,stop,pair,capture=True)
    obs=result["state"][seat].observation
    farm=obs.farms[seat]
    own=float(farm["money"])
    rival=float(obs.farms[1-seat]["money"])
    plants=Counter()
    output=Counter()
    feed=Counter()
    for w in result["work"]:
        if w["seat"]!=seat or w["t"]<START:
            continue
        op=w["cmd"][0]
        if op=="PLANT" and w["t"]<STOP:
            plants[w["cmd"][1]]+=1
        if op in ("HARVEST","COLLECT_FERTILIZER"):
            output.update({p:n for p,n in w["delta"].items() if n>0})
        if op=="FEED":
            feed[w["t"]//24]+=1
    assets=Counter(t.get("crop") or t.get("animal") for row in farm["tiles"] for t in row
                   if isinstance(t,dict) and (t.get("crop") or t.get("animal")))
    return {"cash":own,"rival_cash":rival,"margin":own-rival,
            "plants_first_three_days":dict(plants),"output":dict(output),"feed":dict(feed),
            "assets":dict(assets),"shed":obs.private["shed"],
            "revenue":R.economic(result["events"],seat)["revenue"],
            "spend":R.economic(result["events"],seat)["spend"]}


def main():
    profiles={p["episode"]:p for p in json.loads((ROOT/"results/fresh/semantic_tapes/compact_profiles.json").read_text(encoding="utf-8"))}
    data=next(g for g in json.loads((ROOT/"results/fresh/tape_gap_plans/dataset_primary.json").read_text(encoding="utf-8"))["games"]
              if g["episode"]==EPISODE)
    obs=data["checkpoints"][str(DAY)]["observation"]
    with gzip.open(ROOT/f"data/ladder_panel/56395605/{EPISODE}.json.gz","rt",encoding="utf-8") as f:
        game=json.load(f)
    seat=int(game["seat"])
    original=[deepcopy(game["our_actions"] if i==seat else game["opp_actions"]) for i in range(2)]
    plans={"incumbent":compile_plan(obs,profiles[110344290]),
           "retrieved":compile_plan(obs,profiles[109736053]),
           "retrieved_minus_one_carrot":compile_plan(obs,profiles[109736053],drop_carrots=1),
           "retrieved_minus_two_carrots":compile_plan(obs,profiles[109736053],drop_carrots=2),
           "retrieved_minus_three_carrots":compile_plan(obs,profiles[109736053],drop_carrots=3),
           "retrieved_minus_one_day18_wheat":compile_plan(obs,profiles[109736053],drop_one_day18_wheat=True)}
    pairs={"actual":original}
    for name,plan in plans.items():
        print("compile",name,plan["ok"],plan["seconds"],plan["failure"],flush=True)
        if plan["ok"]:
            assert len(plan["actions"])==72
            pair=deepcopy(original)
            pair[seat][START:STOP]=plan["actions"]
            pairs[name]=pair
    evaluations={}
    for stop in (STOP,719):
        rows={name:evaluate(game,pair,seat,stop) for name,pair in pairs.items()}
        base=rows["actual"]
        for name,row in rows.items():
            row["cash_delta"]=row["cash"]-base["cash"]
            row["rival_cash_delta"]=row["rival_cash"]-base["rival_cash"]
            row["margin_delta"]=row["margin"]-base["margin"]
            print("stop",stop,name,"cash",row["cash_delta"],"margin",row["margin_delta"],flush=True)
        evaluations[str(stop)]=rows
    OUT.write_text(json.dumps({"episode":EPISODE,"day":DAY,"seat":seat,
        "plans":plans,"evaluations":evaluations,
        "limitation":"Candidate and incumbent first-three-day plans are compiled from same actual checkpoint. After day21, replay fixed m1 actions on changed farm state; not an adaptive policy."},indent=2),encoding="utf-8")


if __name__=="__main__":
    main()
