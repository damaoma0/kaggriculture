"""Find successful wheat replants after the day-12 and day-15 shop reveals."""
from collections import Counter
from copy import deepcopy
import gzip
import json

import research_labour_profit as R
from probe_semantic_handoff import ROOT


OUT=ROOT/"results/fresh/semantic_tapes/earlier_strawberry_sites.json"
EPISODE=111287532
DAYS=(12,15)


def main():
    with gzip.open(ROOT/f"data/ladder_panel/56395605/{EPISODE}.json.gz","rt",encoding="utf-8") as f:
        game=json.load(f)
    seat=int(game["seat"])
    pair=[deepcopy(game["our_actions"] if i==seat else game["opp_actions"]) for i in range(2)]
    with R.Simulator(game) as sim:
        result=sim.run(sim.initial,0,719,pair,capture=True,snapshots=True)
    own=[w for w in result["work"] if w["seat"]==seat]
    rows=[]
    for day in DAYS:
        start=day*24
        obs=result["snapshots"][start][seat].observation
        crops=Counter(t.get("crop") or t.get("animal") for line in obs.farms[seat]["tiles"] for t in line
                      if isinstance(t,dict) and (t.get("crop") or t.get("animal")))
        wheat=[{"t":w["t"],"unit":w["unit"],"pos":w["pos"]}
               for w in own if start<=w["t"]<start+24 and w["cmd"]==["PLANT","WHEAT"]]
        strawberry=[{"t":w["t"],"pos":w["pos"]} for w in own
                    if start<=w["t"]<719 and w["cmd"]==["PLANT","STRAWBERRY"]]
        row={"day":day,"money":obs.farms[seat]["money"],"assets":dict(crops),
             "seed_strawberry":obs.private["seeds"].get("STRAWBERRY",0),
             "seed_wheat":obs.private["seeds"].get("WHEAT",0),
             "wheat_plantings":wheat,"later_strawberry_plantings":strawberry}
        rows.append(row)
        print(day,"wheat sites",len(wheat),"strawberry seed",row["seed_strawberry"],
              "later strawberry plantings",len(strawberry),"money",row["money"],flush=True)
    OUT.write_text(json.dumps({"episode":EPISODE,"seat":seat,"days":rows},indent=2),encoding="utf-8")


if __name__=="__main__":
    main()
