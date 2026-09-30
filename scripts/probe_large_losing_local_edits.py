"""Screen intact-tape day-18 wheat changes in a larger losing world.

The recorded m1 episode loses 6,063 cash margin. Each trial changes one
successful wheat replant to PASS, CARROT, or STRAWBERRY, buys one replacement
seed when needed, and keeps the rest of the tape and opponent fixed. Extra
sell orders only occur at hours where m1 already sells that product.
"""
from collections import Counter
from copy import deepcopy
import gzip
import json

import research_labour_profit as R
from probe_semantic_handoff import ROOT


OUT=ROOT/"results/fresh/semantic_tapes/large_losing_local_edits.json"
EPISODE,DAY,END=111287532,18,719
START=DAY*24
SEED_STEP=433


def evaluate(game,pair,seat,plant=None):
    with R.Simulator(game) as sim:
        result=sim.run(sim.initial,0,END,pair,capture=True)
    obs=result["state"][seat].observation
    cash=float(obs.farms[seat]["money"])
    rival=float(obs.farms[1-seat]["money"])
    output=Counter()
    feeds=Counter()
    plants=Counter()
    tilework=[]
    for w in result["work"]:
        if w["seat"]!=seat or w["t"]<START:
            continue
        op=w["cmd"][0]
        if op in ("HARVEST","COLLECT_FERTILIZER"):
            output.update({p:n for p,n in w["delta"].items() if n>0})
        if op=="FEED":
            feeds[w["t"]//24]+=1
        if op=="PLANT":
            plants[w["cmd"][1]]+=1
        if plant and tuple(w["pos"])==tuple(plant["pos"]) and w["t"]>=plant["t"] and op in ("HARVEST","PLANT"):
            tilework.append({"t":w["t"],"cmd":w["cmd"],"delta":w["delta"]})
    econ=R.economic(result["events"],seat)
    return {"cash":cash,"rival_cash":rival,"margin":cash-rival,
            "output":dict(output),"feeds":dict(feeds),"plants":dict(plants),
            "revenue":econ["revenue"],"spend":econ["spend"],
            "final_shed":{p:obs.private["shed"].get(p,0) for p in ("WHEAT","CARROT","STRAWBERRY","MILK","EGG","WOOL")},
            "tilework":tilework}


def main():
    with gzip.open(ROOT/f"data/ladder_panel/56395605/{EPISODE}.json.gz","rt",encoding="utf-8") as f:
        game=json.load(f)
    seat=int(game["seat"])
    original=[deepcopy(game["our_actions"] if i==seat else game["opp_actions"]) for i in range(2)]
    inspection=json.loads((ROOT/"results/fresh/semantic_tapes/large_losing_case_inspection.json").read_text(encoding="utf-8"))
    plantings=inspection["wheat_plantings"]
    assert len(plantings)==7
    assert inspection["start_seeds"]["STRAWBERRY"]>=1
    assert not any(cmd==["PLANT","STRAWBERRY"] for t in range(START,END)
                   for cmd in [original[seat][t]["farmer"],*original[seat][t]["hands"]])
    baseline=evaluate(game,original,seat)
    rows=[]
    for plant in plantings:
        t,unit,pos=plant["t"],plant["unit"],plant["pos"]
        for crop in ("PASS","CARROT","STRAWBERRY"):
            pair=deepcopy(original)
            field="farmer" if unit==0 else "hands"
            if unit==0:
                assert pair[seat][t][field]==["PLANT","WHEAT"]
                pair[seat][t][field]=["PASS"] if crop=="PASS" else ["PLANT",crop]
            else:
                assert pair[seat][t][field][unit-1]==["PLANT","WHEAT"]
                pair[seat][t][field][unit-1]=["PASS"] if crop=="PASS" else ["PLANT",crop]
            if crop!="PASS":
                if crop=="CARROT":
                    # Preserve the original later carrot-seed budget. The
                    # farm already holds one unused strawberry seed, so its
                    # strawberry substitution needs no purchase.
                    assert len(pair[seat][SEED_STEP]["market"])<10
                    pair[seat][SEED_STEP]["market"].append(["BUY_SEED",crop,1])
                for future in range(t+1,END):
                    if any(cmd[:2]==["SELL",crop] for cmd in original[seat][future]["market"]):
                        if len(pair[seat][future]["market"])<10:
                            pair[seat][future]["market"].append(["SELL",crop,10])
                pair[seat][718]["market"].append(["SELL",crop,10])
            result=evaluate(game,pair,seat,plant)
            result.update(t=t,unit=unit,pos=pos,crop=crop,
                          margin_delta=result["margin"]-baseline["margin"],
                          cash_delta=result["cash"]-baseline["cash"],
                          rival_cash_delta=result["rival_cash"]-baseline["rival_cash"],
                          output_delta={p:result["output"].get(p,0)-baseline["output"].get(p,0)
                                        for p in set(result["output"])|set(baseline["output"])
                                        if result["output"].get(p,0)!=baseline["output"].get(p,0)},
                          feed_delta=sum(result["feeds"].get(d,0)-baseline["feeds"].get(d,0)
                                         for d in set(result["feeds"])|set(baseline["feeds"])))
            rows.append(result)
            print(t,pos,crop,"margin",result["margin_delta"],"own",result["cash_delta"],
                  "rival",result["rival_cash_delta"],"feed",result["feed_delta"],flush=True)
    best=max(rows,key=lambda r:r["margin_delta"])
    OUT.write_text(json.dumps({"episode":EPISODE,"day":DAY,"baseline_margin":baseline["margin"],
        "baseline":baseline,"variants":rows,"best_tested":{"t":best["t"],"pos":best["pos"],
        "crop":best["crop"],"margin_delta":best["margin_delta"]},
        "limitation":"Single fixed recorded world and one-action edits; strawberry edits are demand-direction probes rather than donor calendar jobs. Variant ranking is post hoc."},indent=2),encoding="utf-8")


if __name__=="__main__":
    main()
