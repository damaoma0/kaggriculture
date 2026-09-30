"""Inspect the larger losing episode and its day-18 wheat continuation."""
from collections import Counter
from copy import deepcopy
import gzip
import json

import research_labour_profit as R
from probe_semantic_handoff import ROOT


OUT=ROOT/"results/fresh/semantic_tapes/large_losing_case_inspection.json"
EPISODE,DAY=111287532,18
START=DAY*24


def main():
    with gzip.open(ROOT/f"data/ladder_panel/56395605/{EPISODE}.json.gz","rt",encoding="utf-8") as f:
        game=json.load(f)
    seat=int(game["seat"])
    pair=[deepcopy(game["our_actions"] if i==seat else game["opp_actions"]) for i in range(2)]
    with R.Simulator(game) as sim:
        result=sim.run(sim.initial,0,719,pair,capture=True,snapshots=True)
    start=result["snapshots"][START][seat].observation
    farm=start.farms[seat]
    assets=Counter(t.get("crop") or t.get("animal") for row in farm["tiles"] for t in row
                   if isinstance(t,dict) and (t.get("crop") or t.get("animal")))
    own_work=[w for w in result["work"] if w["seat"]==seat]
    plantings=[]
    for w in own_work:
        if START<=w["t"]<START+24 and w["cmd"]==["PLANT","WHEAT"]:
            pos=tuple(w["pos"])
            later=[{"t":x["t"],"cmd":x["cmd"],"delta":x["delta"]}
                   for x in own_work if x["t"]>w["t"] and tuple(x["pos"])==pos
                   and x["cmd"][0] in ("PLANT","HARVEST")]
            plantings.append({"t":w["t"],"unit":w["unit"],"pos":w["pos"],"later":later})
    sales={}
    for player in (seat,1-seat):
        econ=R.economic(result["events"],player)
        sales[str(player)]={"revenue":econ["revenue"],"spend":econ["spend"]}
    output={}
    for player in (seat,1-seat):
        c=Counter()
        for w in result["work"]:
            if w["seat"]==player and START<=w["t"] and w["cmd"][0] in ("HARVEST","COLLECT_FERTILIZER"):
                c.update({p:n for p,n in w["delta"].items() if n>0})
        output[str(player)]=dict(c)
    data={"episode":EPISODE,"day":DAY,"seat":seat,"rewards":game["rewards"],
          "start_money":farm["money"],"start_assets":dict(assets),
          "start_seeds":start.private.get("seeds"),"start_shed":start.private["shed"],
          "wheat_plantings":plantings,"sales":sales,"output_from_day18":output}
    OUT.write_text(json.dumps(data,indent=2),encoding="utf-8")
    print(json.dumps({"margin":game["rewards"][seat]-game["rewards"][1-seat],
        "start_money":data["start_money"],"start_assets":data["start_assets"],
        "start_shed":data["start_shed"],"start_seeds":data["start_seeds"],
        "wheat_plantings":[{k:p[k] for k in ("t","unit","pos")}
                            for p in plantings],"output":output},indent=2))


if __name__=="__main__":
    main()
