"""Exact fixed-world day-12/15 wheat-to-strawberry substitutions.

Every target is a verified successful wheat replant in the recorded losing
episode. Both purchased-seed and existing-stock cases are checked where a
later baseline strawberry planting might consume that seed.
"""
from collections import Counter
from copy import deepcopy
import gzip
import json

import research_labour_profit as R
from probe_semantic_handoff import ROOT


OUT=ROOT/"results/fresh/semantic_tapes/earlier_strawberry_shift.json"
EPISODE,END=111287532,719


def evaluate(game,pair,seat,plant=None):
    with R.Simulator(game) as sim:
        result=sim.run(sim.initial,0,END,pair,capture=True)
    obs=result["state"][seat].observation
    cash=float(obs.farms[seat]["money"])
    rival=float(obs.farms[1-seat]["money"])
    output=Counter()
    feeds=Counter()
    strawberry_plants=[]
    tilework=[]
    for w in result["work"]:
        if w["seat"]!=seat:
            continue
        op=w["cmd"][0]
        if op in ("HARVEST","COLLECT_FERTILIZER"):
            output.update({p:n for p,n in w["delta"].items() if n>0})
        if op=="FEED":
            feeds[w["t"]//24]+=1
        if w["cmd"]==["PLANT","STRAWBERRY"]:
            strawberry_plants.append({"t":w["t"],"pos":w["pos"]})
        if plant and w["t"]>=plant["t"] and tuple(w["pos"])==tuple(plant["pos"]) and op in ("HARVEST","PLANT"):
            tilework.append({"t":w["t"],"cmd":w["cmd"],"delta":w["delta"]})
    econ=R.economic(result["events"],seat)
    rival_econ=R.economic(result["events"],1-seat)
    return {"cash":cash,"rival_cash":rival,"margin":cash-rival,
            "output":dict(output),"feeds":dict(feeds),"strawberry_plants":strawberry_plants,
            "revenue":econ["revenue"],"spend":econ["spend"],"sold_units":econ["units"],
            "rival_revenue":rival_econ["revenue"],"rival_spend":rival_econ["spend"],
            "rival_sold_units":rival_econ["units"],
            "shed":{p:obs.private["shed"].get(p,0) for p in ("STRAWBERRY","WHEAT","CARROT","WOOL")},
            "tilework":tilework}


def main():
    with gzip.open(ROOT/f"data/ladder_panel/56395605/{EPISODE}.json.gz","rt",encoding="utf-8") as f:
        game=json.load(f)
    seat=int(game["seat"])
    original=[deepcopy(game["our_actions"] if i==seat else game["opp_actions"]) for i in range(2)]
    sites=json.loads((ROOT/"results/fresh/semantic_tapes/earlier_strawberry_sites.json").read_text(encoding="utf-8"))["days"]
    baseline=evaluate(game,original,seat)
    rows=[]
    for checkpoint in sites:
        day=checkpoint["day"]
        if day not in (12,15):
            continue
        for plant in checkpoint["wheat_plantings"]:
            for seed_mode in (("buy_seed", "use_stock") if day==12 else ("use_stock",)):
                t,u,pos=plant["t"],plant["unit"],plant["pos"]
                pair=deepcopy(original)
                if u==0:
                    assert pair[seat][t]["farmer"]==["PLANT","WHEAT"]
                    pair[seat][t]["farmer"]=["PLANT","STRAWBERRY"]
                else:
                    assert pair[seat][t]["hands"][u-1]==["PLANT","WHEAT"]
                    pair[seat][t]["hands"][u-1]=["PLANT","STRAWBERRY"]
                if seed_mode=="buy_seed":
                    buy_t=day*24+1
                    assert len(pair[seat][buy_t]["market"])<10
                    pair[seat][buy_t]["market"].append(["BUY_SEED","STRAWBERRY",1])
                for future in range((day+10)*24,END):
                    if any(cmd[:2]==["SELL","STRAWBERRY"] for cmd in original[seat][future]["market"]):
                        if len(pair[seat][future]["market"])<10:
                            pair[seat][future]["market"].append(["SELL","STRAWBERRY",10])
                pair[seat][718]["market"].append(["SELL","STRAWBERRY",10])
                row=evaluate(game,pair,seat,plant)
                row.update(day=day,t=t,unit=u,pos=pos,seed_mode=seed_mode,
                           margin_delta=row["margin"]-baseline["margin"],
                           cash_delta=row["cash"]-baseline["cash"],
                           rival_cash_delta=row["rival_cash"]-baseline["rival_cash"],
                           output_delta={p:row["output"].get(p,0)-baseline["output"].get(p,0)
                                         for p in set(row["output"])|set(baseline["output"])
                                         if row["output"].get(p,0)!=baseline["output"].get(p,0)},
                           feed_delta=sum(row["feeds"].get(d,0)-baseline["feeds"].get(d,0)
                                          for d in set(row["feeds"])|set(baseline["feeds"])),
                           baseline_strawberry_plants_preserved=all(p in row["strawberry_plants"]
                                                                      for p in baseline["strawberry_plants"]))
                rows.append(row)
                print(day,t,pos,seed_mode,"margin",row["margin_delta"],
                      "feed",row["feed_delta"],"baseline berries kept",row["baseline_strawberry_plants_preserved"],flush=True)
    eligible=[r for r in rows if r["baseline_strawberry_plants_preserved"]]
    best=max(eligible,key=lambda r:r["margin_delta"])
    OUT.write_text(json.dumps({"episode":EPISODE,"baseline_margin":baseline["margin"],
        "baseline":baseline,"rows":rows,"best_preserving_baseline":{k:best[k] for k in
            ("day","t","pos","seed_mode","margin_delta","cash_delta","rival_cash_delta","feed_delta")},
        "limitation":"Retrospective fixed-world one-tile search. Both checkpoints are shop reveals, but tile outcomes and the future rival continuation are known only to this audit."},indent=2),encoding="utf-8")


if __name__=="__main__":
    main()
