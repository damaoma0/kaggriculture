"""Post hoc site sweep at the first strawberry-buying shop reveal, day 9.

The day-9 FARMERS_MARKET is visible before all edits. Tile ranking uses the
recorded future and is diagnostic only; it is not a live selection rule.
"""
from copy import deepcopy
import gzip
import json

import research_labour_profit as R
from probe_semantic_handoff import ROOT
from probe_earlier_strawberry_shift import evaluate, EPISODE, END


OUT=ROOT/"results/fresh/semantic_tapes/first_strawberry_reveal_probe.json"
DAY=9


def main():
    with gzip.open(ROOT/f"data/ladder_panel/56395605/{EPISODE}.json.gz","rt",encoding="utf-8") as f:
        game=json.load(f)
    seat=int(game["seat"])
    original=[deepcopy(game["our_actions"] if i==seat else game["opp_actions"]) for i in range(2)]
    with R.Simulator(game) as sim:
        work=sim.run(sim.initial,0,END,original,capture=True)["work"]
    sites=[w for w in work if w["seat"]==seat and DAY*24<=w["t"]<(DAY+1)*24
           and w["cmd"]==["PLANT","WHEAT"]]
    baseline=evaluate(game,original,seat)
    rows=[]
    for w in sites:
        for seed_mode in ("use_stock","buy_seed"):
            pair=deepcopy(original)
            t,u,pos=w["t"],w["unit"],w["pos"]
            if u==0:
                pair[seat][t]["farmer"]=["PLANT","STRAWBERRY"]
            else:
                pair[seat][t]["hands"][u-1]=["PLANT","STRAWBERRY"]
            if seed_mode=="buy_seed":
                pair[seat][DAY*24+1]["market"].append(["BUY_SEED","STRAWBERRY",1])
            for future in range((DAY+10)*24,END):
                if any(cmd[:2]==["SELL","STRAWBERRY"] for cmd in original[seat][future]["market"]):
                    if len(pair[seat][future]["market"])<10:
                        pair[seat][future]["market"].append(["SELL","STRAWBERRY",10])
            pair[seat][718]["market"].append(["SELL","STRAWBERRY",10])
            v=evaluate(game,pair,seat)
            plant_ok=any(p["t"]==t and p["pos"]==pos for p in v["strawberry_plants"])
            baseline_ok=all(p in v["strawberry_plants"] for p in baseline["strawberry_plants"])
            feed_days=set(v["feeds"])|set(baseline["feeds"])
            feed_ok=all(v["feeds"].get(d,0)>=baseline["feeds"].get(d,0) for d in feed_days)
            rows.append({"t":t,"unit":u,"pos":pos,"seed_mode":seed_mode,
                         "margin_delta":v["margin"]-baseline["margin"],
                         "cash_delta":v["cash"]-baseline["cash"],
                         "rival_cash_delta":v["rival_cash"]-baseline["rival_cash"],
                         "strawberry_output_delta":v["output"].get("STRAWBERRY",0)-baseline["output"].get("STRAWBERRY",0),
                         "wheat_output_delta":v["output"].get("WHEAT",0)-baseline["output"].get("WHEAT",0),
                         "plant_ok":plant_ok,"baseline_plants_preserved":baseline_ok,"daily_feeds_preserved":feed_ok})
    eligible=[r for r in rows if r["plant_ok"] and r["baseline_plants_preserved"] and r["daily_feeds_preserved"]]
    result={"episode":EPISODE,"day":DAY,"shop_reveal":"FARMERS_MARKET",
            "baseline_margin":baseline["margin"],"sites":len(sites),"tested":len(rows),
            "eligible":len(eligible),"ranked":sorted(eligible,key=lambda x:x["margin_delta"],reverse=True),
            "all":rows,"limitation":"Sites are ranked with recorded outcomes and future shop sequence. No prospective profitability threshold is established."}
    OUT.write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps({"sites":len(sites),"eligible":len(eligible),"ranked":result["ranked"][:8]},indent=2))


if __name__=="__main__":
    main()
