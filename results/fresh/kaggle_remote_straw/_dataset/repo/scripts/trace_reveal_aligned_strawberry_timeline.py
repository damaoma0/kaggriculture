"""Trace daily production and work in the exact four-tile replay."""
from collections import Counter, defaultdict
from copy import deepcopy
import gzip
import json

import research_labour_profit as R
from probe_semantic_handoff import ROOT
from probe_earlier_strawberry_portfolio import EPISODE, END, RECIPES


OUT=ROOT/"results/fresh/semantic_tapes/reveal_aligned_strawberry_timeline.json"
GOODS=("STRAWBERRY","WHEAT","CARROT","FERTILIZER","WOOL","MILK","TOMATO")


def variant(original, seat, sites):
    pair=deepcopy(original)
    recipe=RECIPES["day12_pair_day15_pair"]
    for t in recipe["plant_times"]:
        unit=sites[t]["unit"]
        assert pair[seat][t]["hands"][unit-1]==["PLANT","WHEAT"]
        pair[seat][t]["hands"][unit-1]=["PLANT","STRAWBERRY"]
    for t,n in recipe["seed_additions"].items():
        strawberry_order=next((cmd for cmd in pair[seat][t]["market"]
                               if cmd[:2]==["BUY_SEED","STRAWBERRY"]),None)
        if strawberry_order:
            strawberry_order[2]+=n
        else:
            pair[seat][t]["market"].append(["BUY_SEED","STRAWBERRY",n])
    first_maturity=min(t//24+10 for t in recipe["plant_times"])*24
    for t in range(first_maturity,END):
        if any(cmd[:2]==["SELL","STRAWBERRY"] for cmd in original[seat][t]["market"]):
            if len(pair[seat][t]["market"])<10:
                pair[seat][t]["market"].append(["SELL","STRAWBERRY",10])
    pair[seat][718]["market"].append(["SELL","STRAWBERRY",10])
    return pair


def trace(game, pair):
    with R.Simulator(game) as sim:
        result=sim.run(sim.initial,0,END,pair,capture=True,snapshots=True)
    work=defaultdict(list)
    events=defaultdict(list)
    for w in result["work"]:
        work[w["t"]//24,w["seat"]].append(w)
    for event in result["events"]:
        events[event[0]//24,event[1]].append(event)
    daily=[]
    for day in range(30):
        snapshot=result["snapshots"][day*24]
        farms=[]
        for seat in range(2):
            obs=snapshot[seat].observation
            farm=obs.farms[seat]
            private=obs.private
            tiles=Counter(tile.get("crop") or tile.get("animal") for row in farm["tiles"] for tile in row
                          if isinstance(tile,dict) and (tile.get("crop") or tile.get("animal")))
            empty_pastures=sum(isinstance(tile,dict) and tile.get("kind")=="PASTURE" and not tile.get("animal")
                               for row in farm["tiles"] for tile in row)
            physical=work[day,seat]
            trades=events[day,seat]
            harvested=Counter()
            collected=Counter()
            ops=Counter(w["cmd"][0] for w in physical)
            planted=Counter(w["cmd"][1] for w in physical if w["cmd"][0]=="PLANT")
            for w in physical:
                if w["cmd"][0]=="HARVEST":
                    harvested.update({p:n for p,n in w["delta"].items() if n>0})
                if w["cmd"][0]=="COLLECT_FERTILIZER":
                    collected.update({p:n for p,n in w["delta"].items() if n>0})
            sold=Counter()
            sale_value=Counter()
            spend=Counter()
            for _,_,op,item,price in trades:
                if op=="SELL":
                    sold[item]+=1
                    sale_value[item]+=price
                else:
                    spend[op+(":"+item if item else "")]+=price
            held_fertilizer=sum(inv.get("FERTILIZER",0) for inv in private["inventories"])
            farms.append({"cash_start":farm["money"],
                          "empty_pastures_start":empty_pastures,
                          "sheep_start":tiles["SHEEP"],
                          "strawberry_tiles_start":tiles["STRAWBERRY"],
                          "wheat_tiles_start":tiles["WHEAT"],
                          "carrot_tiles_start":tiles["CARROT"],
                          "strawberry_seed_start":private["seeds"].get("STRAWBERRY",0),
                          "shed_strawberry_start":private["shed"].get("STRAWBERRY",0),
                          "fertilizer_shed_start":private["shed"].get("FERTILIZER",0),
                          "fertilizer_held_start":held_fertilizer,
                          "harvested":{p:harvested[p] for p in GOODS if harvested[p]},
                          "planted":dict(planted),
                          "collected":{p:collected[p] for p in GOODS if collected[p]},
                          "sold":{p:sold[p] for p in GOODS if sold[p]},
                          "sale_value":{p:sale_value[p] for p in GOODS if sale_value[p]},
                          "spend":dict(spend),"work_ops":dict(ops)})
        shops=game["shops"][day]
        prior=game["shops"][day-1] if day else []
        prior_counts=Counter(prior)
        new_shops=[]
        for shop in shops:
            if prior_counts[shop]:
                prior_counts[shop]-=1
            else:
                new_shops.append(shop)
        daily.append({"day":day,"new_shops":new_shops,
                      "visible_shops":shops,"farms":farms})
    final=result["state"][0].observation
    return {"daily":daily,"final_cash":[f["money"] for f in final.farms],
            "final_stock":{str(s):{
                "strawberry_shed":result["state"][s].observation.private["shed"].get("STRAWBERRY",0),
                "strawberry_held":sum(inv.get("STRAWBERRY",0) for inv in result["state"][s].observation.private["inventories"]),
                "fertilizer_shed":result["state"][s].observation.private["shed"].get("FERTILIZER",0),
                "fertilizer_held":sum(inv.get("FERTILIZER",0) for inv in result["state"][s].observation.private["inventories"])}
                for s in range(2)},
            "successful_work_by_seat":{str(s):dict(Counter(w["cmd"][0] for w in result["work"] if w["seat"]==s))
                                       for s in range(2)}},result["work"]


def main():
    with gzip.open(ROOT/f"data/ladder_panel/56395605/{EPISODE}.json.gz","rt",encoding="utf-8") as f:
        game=json.load(f)
    seat=int(game["seat"])
    original=[deepcopy(game["our_actions"] if i==seat else game["opp_actions"]) for i in range(2)]
    inspections=json.loads((ROOT/"results/fresh/semantic_tapes/earlier_strawberry_sites.json").read_text(encoding="utf-8"))
    sites={p["t"]:p for day in inspections["days"] for p in day["wheat_plantings"]}
    baseline,baseline_work=trace(game,original)
    shifted,shifted_work=trace(game,variant(original,seat,sites))
    target_positions={tuple(sites[t]["pos"]) for t in RECIPES["day12_pair_day15_pair"]["plant_times"]}
    def target_work(work):
        return [{"t":w["t"],"pos":w["pos"],"unit":w["unit"],"cmd":w["cmd"],"delta":w["delta"]}
                for w in work if w["seat"]==seat and tuple(w["pos"]) in target_positions
                and w["t"]>=288 and w["cmd"][0] in ("PLANT","HARVEST","FERTILIZE")]
    OUT.write_text(json.dumps({"episode":EPISODE,"our_seat":seat,
                               "baseline":baseline,"shifted":shifted,
                               "target_work":{"baseline":target_work(baseline_work),
                                              "shifted":target_work(shifted_work)}},indent=2),encoding="utf-8")
    print(json.dumps({"our_seat":seat,"final_cash":shifted["final_cash"],
                      "reveals":[{"day":d["day"],"new":d["new_shops"]}
                                 for d in shifted["daily"] if d["new_shops"]],
                      "work_baseline":baseline["successful_work_by_seat"],
                      "work_shifted":shifted["successful_work_by_seat"]},indent=2))


if __name__=="__main__":
    main()
