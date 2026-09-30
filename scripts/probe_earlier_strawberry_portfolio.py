"""Funded multi-day strawberry planting shifts in the same losing world."""
from copy import deepcopy
import gzip
import json

from probe_semantic_handoff import ROOT
from probe_earlier_strawberry_shift import evaluate, EPISODE, END


OUT=ROOT/"results/fresh/semantic_tapes/earlier_strawberry_portfolio.json"
RECIPES={
    "day12_pair": {"plant_times":[302,306],"seed_additions":{298:1}},
    "day15_pair": {"plant_times":[365,374],"seed_additions":{361:1}},
    "day12_day15": {"plant_times":[302,365],"seed_additions":{361:1}},
    "day12_pair_day15_pair": {"plant_times":[302,306,365,374],"seed_additions":{298:1,361:2}},
}


def main():
    with gzip.open(ROOT/f"data/ladder_panel/56395605/{EPISODE}.json.gz","rt",encoding="utf-8") as f:
        game=json.load(f)
    seat=int(game["seat"])
    original=[deepcopy(game["our_actions"] if i==seat else game["opp_actions"]) for i in range(2)]
    sites=json.loads((ROOT/"results/fresh/semantic_tapes/earlier_strawberry_sites.json").read_text(encoding="utf-8"))["days"]
    by_time={p["t"]:p for day in sites for p in day["wheat_plantings"]}
    baseline=evaluate(game,original,seat)
    rows={}
    for name,recipe in RECIPES.items():
        pair=deepcopy(original)
        for t in recipe["plant_times"]:
            p=by_time[t]
            u=p["unit"]
            assert u>0 and pair[seat][t]["hands"][u-1]==["PLANT","WHEAT"]
            pair[seat][t]["hands"][u-1]=["PLANT","STRAWBERRY"]
        for t,amount in recipe["seed_additions"].items():
            strawberry_order=next((cmd for cmd in pair[seat][t]["market"]
                                   if cmd[:2]==["BUY_SEED","STRAWBERRY"]),None)
            if strawberry_order:
                strawberry_order[2]+=amount
            else:
                assert len(pair[seat][t]["market"])<10
                pair[seat][t]["market"].append(["BUY_SEED","STRAWBERRY",amount])
        first_maturity=min(by_time[t]["t"]//24+10 for t in recipe["plant_times"])*24
        for future in range(first_maturity,END):
            if any(cmd[:2]==["SELL","STRAWBERRY"] for cmd in original[seat][future]["market"]):
                if len(pair[seat][future]["market"])<10:
                    pair[seat][future]["market"].append(["SELL","STRAWBERRY",10])
        pair[seat][718]["market"].append(["SELL","STRAWBERRY",10])
        result=evaluate(game,pair,seat)
        result.update(plant_times=recipe["plant_times"],seed_additions=recipe["seed_additions"],
            margin_delta=result["margin"]-baseline["margin"],
            cash_delta=result["cash"]-baseline["cash"],
            rival_cash_delta=result["rival_cash"]-baseline["rival_cash"],
            feed_delta=sum(result["feeds"].get(d,0)-baseline["feeds"].get(d,0)
                           for d in set(result["feeds"])|set(baseline["feeds"])),
            baseline_strawberry_plants_preserved=all(p in result["strawberry_plants"]
                                                     for p in baseline["strawberry_plants"]),
            target_plantings_successful=all(any(p["t"]==t and tuple(p["pos"])==tuple(by_time[t]["pos"])
                                                for p in result["strawberry_plants"])
                                            for t in recipe["plant_times"]))
        rows[name]=result
        print(name,"margin",result["margin_delta"],"cash",result["cash_delta"],
              "rival",result["rival_cash_delta"],"feed",result["feed_delta"],
              "target",result["target_plantings_successful"],
              "baseline",result["baseline_strawberry_plants_preserved"],flush=True)
    OUT.write_text(json.dumps({"episode":EPISODE,"baseline_margin":baseline["margin"],
        "baseline":baseline,
        "recipes":rows,"limitation":"Retrospective hand-picked combinations in one recorded world, with edits only after day-12 and day-15 shop reveals."},indent=2),encoding="utf-8")


if __name__=="__main__":
    main()
