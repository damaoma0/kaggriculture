"""Exact-engine three-day replay of the directionally aligned donor calendar."""
from collections import Counter
from copy import deepcopy
import gzip
import json

import research_labour_profit as R
from probe_semantic_handoff import ROOT


OUT=ROOT/"results/fresh/semantic_tapes/directional_full_calendar_exact.json"
EPISODE,DAY=111289863,15
START,STOP=DAY*24,(DAY+3)*24


def evaluate(game,pair,seat,stop):
    with R.Simulator(game) as sim:
        result=sim.run(sim.initial,0,stop,pair,capture=True)
    obs=result["state"][seat].observation
    farm=obs.farms[seat]
    crops=Counter(t.get("crop") or t.get("animal") for row in farm["tiles"] for t in row
                  if isinstance(t,dict) and (t.get("crop") or t.get("animal")))
    plants=Counter(w["cmd"][1] for w in result["work"] if w["seat"]==seat and
                   START<=w["t"]<STOP and w["cmd"][0]=="PLANT")
    output=Counter()
    service=Counter()
    for w in result["work"]:
        if w["seat"]==seat and START<=w["t"]<stop:
            if w["cmd"][0] in ("HARVEST","COLLECT_FERTILIZER"):
                output.update({p:n for p,n in w["delta"].items() if n>0})
            if w["cmd"][0] in ("FEED","CARE"):
                service[(w["t"]//24,w["cmd"][0])]+=1
    own=float(farm["money"])
    rival=float(obs.farms[1-seat]["money"])
    return {"cash":own,"rival_cash":rival,"margin":own-rival,
            "assets":dict(crops),"plant_success":dict(plants),"output":dict(output),
            "service":{f"{day}:{op}":n for (day,op),n in sorted(service.items())},
            "worker_positions":[farm["farmer"],*farm["hands"]],
            "shed":obs.private["shed"],"seeds":obs.private.get("seeds"),
            "revenue":R.economic(result["events"],seat)["revenue"],
            "spend":R.economic(result["events"],seat)["spend"]}


def main():
    plans=json.loads((ROOT/"results/fresh/semantic_tapes/directional_full_calendar_probe.json").read_text(encoding="utf-8"))["rows"]
    with gzip.open(ROOT/f"data/ladder_panel/56395605/{EPISODE}.json.gz","rt",encoding="utf-8") as f:
        game=json.load(f)
    seat=int(game["seat"])
    original=[deepcopy(game["our_actions"] if i==seat else game["opp_actions"]) for i in range(2)]
    arms={"actual":original}
    for name in ("incumbent","retrieved"):
        assert plans[name]["ok"] and len(plans[name]["actions"])==72
        pair=deepcopy(original)
        pair[seat][START:STOP]=plans[name]["actions"]
        arms[name]=pair
    results={name:evaluate(game,pair,seat,STOP) for name,pair in arms.items()}
    baseline=results["actual"]
    for name,row in results.items():
        row["cash_delta"]=row["cash"]-baseline["cash"]
        row["margin_delta"]=row["margin"]-baseline["margin"]
        row["worker_position_mismatches"]=sum(a!=b for a,b in zip(row["worker_positions"],baseline["worker_positions"]))
        print(name,"cash",row["cash_delta"],"margin",row["margin_delta"],
              "plant",row["plant_success"],"positions",row["worker_position_mismatches"],flush=True)
    liquidated=deepcopy(arms["retrieved"])
    for t in range(STOP,719):
        if any(cmd[:2]==["SELL","TOMATO"] for cmd in original[seat][t]["market"]):
            if len(liquidated[seat][t]["market"])<10:
                liquidated[seat][t]["market"].append(["SELL","TOMATO",10])
    liquidated[seat][718]["market"].append(["SELL","TOMATO",10])
    full_arms={**arms,"retrieved_with_tomato_sales":liquidated}
    full={name:evaluate(game,pair,seat,719) for name,pair in full_arms.items()}
    base_full=full["actual"]
    for name,row in full.items():
        row["cash_delta"]=row["cash"]-base_full["cash"]
        row["margin_delta"]=row["margin"]-base_full["margin"]
        print("full",name,"cash",row["cash_delta"],"margin",row["margin_delta"],
              "tomato_shed",row["shed"].get("TOMATO"),flush=True)
    OUT.write_text(json.dumps({"episode":EPISODE,"day":DAY,"first_three_days":results,"full_season_graft":full,
        "limitation":"Exact fixed recorded world. Compiled arms replace only days 15-17, then replay m1 actions despite changed crop state; this is a graft diagnostic, not an adaptive switch policy."},indent=2),encoding="utf-8")


if __name__=="__main__":
    main()
