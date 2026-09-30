"""Paired future-shop stress test for reveal-triggered crop substitutions.

Known shops and the full farm state at each reveal are fixed. Remaining shop
instances are drawn uniformly with replacement, as in the engine. Both farms'
recorded future actions stay fixed. Tile choices are retrospective, so this
tests future-shop sensitivity, not a prospective policy.
"""
from copy import deepcopy
import gzip
import json
import random
from statistics import mean,median

import research_labour_profit as R
from probe_semantic_handoff import ROOT
from probe_earlier_strawberry_shift import EPISODE,END


OUT=ROOT/"results/fresh/semantic_tapes/conditional_shop_strawberry_scenarios.json"
N_RANDOM=48
PROBES={
    "day9_low_displacement": {"day":9,"times":[227],"seed_additions":{}},
    "day12_pair": {"day":12,"times":[302,306],"seed_additions":{298:1}},
    "day15_pair": {"day":15,"times":[365,374],"seed_additions":{361:1}},
}


def variant(original, seat, sites, spec):
    pair=deepcopy(original)
    for t in spec["times"]:
        unit=sites[t]["unit"]
        if unit==0:
            assert pair[seat][t]["farmer"]==["PLANT","WHEAT"]
            pair[seat][t]["farmer"]=["PLANT","STRAWBERRY"]
        else:
            assert pair[seat][t]["hands"][unit-1]==["PLANT","WHEAT"]
            pair[seat][t]["hands"][unit-1]=["PLANT","STRAWBERRY"]
    for t,n in spec["seed_additions"].items():
        order=next((cmd for cmd in pair[seat][t]["market"] if cmd[:2]==["BUY_SEED","STRAWBERRY"]),None)
        if order:
            order[2]+=n
        else:
            pair[seat][t]["market"].append(["BUY_SEED","STRAWBERRY",n])
    first_maturity=(spec["day"]+10)*24
    for t in range(first_maturity,END):
        if any(cmd[:2]==["SELL","STRAWBERRY"] for cmd in original[seat][t]["market"]):
            if len(pair[seat][t]["market"])<10:
                pair[seat][t]["market"].append(["SELL","STRAWBERRY",10])
    pair[seat][718]["market"].append(["SELL","STRAWBERRY",10])
    return pair


def scenario_shops(recorded, day, future_draws):
    sequence=deepcopy(recorded)
    current=list(recorded[day])
    i=0
    for d in range(day+1,len(sequence)):
        if d in range(3,25,3):
            current.append(future_draws[i])
            i+=1
        sequence[d]=list(current)
    assert i==len(future_draws)
    return sequence


def summarize(rows):
    values=sorted(r["margin_delta"] for r in rows)
    n=len(values)
    return {"n":n,"mean_margin_delta":mean(values),"median_margin_delta":median(values),
            "positive":sum(x>0 for x in values),"negative":sum(x<0 for x in values),
            "minimum":values[0],"p10":values[int(.1*(n-1))],
            "p90":values[int(.9*(n-1))],"maximum":values[-1]}


def main():
    with gzip.open(ROOT/f"data/ladder_panel/56395605/{EPISODE}.json.gz","rt",encoding="utf-8") as f:
        game=json.load(f)
    recorded_shops=deepcopy(game["shops"])
    seat=int(game["seat"])
    original=[deepcopy(game["our_actions"] if i==seat else game["opp_actions"]) for i in range(2)]
    with R.Simulator(game) as sim:
        work=sim.run(sim.initial,0,END,original,capture=True)["work"]
    sites={w["t"]:w for w in work if w["seat"]==seat and w["cmd"]==["PLANT","WHEAT"]}
    shop_types=sorted(R.engine().SHOPS)
    all_rows={}
    summaries={}
    with R.Simulator(game) as sim:
        for name,spec in PROBES.items():
            day=spec["day"]
            sim.game["shops"]=recorded_shops
            state=sim.run(sim.initial,0,day*24,original)["state"]
            pair=variant(original,seat,sites,spec)
            rng=random.Random(2026092300+day)
            n_future=sum(r>day for r in range(3,25,3))
            actual=recorded_shops[24][8-n_future:]
            draws=[list(actual)]+[[rng.choice(shop_types) for _ in range(n_future)] for _ in range(N_RANDOM)]
            rows=[]
            for j,draw in enumerate(draws):
                sim.game["shops"]=scenario_shops(recorded_shops,day,draw)
                a=sim.run(state,day*24,END,original)["money"]
                b=sim.run(state,day*24,END,pair)["money"]
                rows.append({"scenario":"recorded" if j==0 else f"random_{j}",
                             "future_shops":draw,"margin_delta":(b[seat]-b[1-seat])-(a[seat]-a[1-seat]),
                             "cash_delta":b[seat]-a[seat],"rival_cash_delta":b[1-seat]-a[1-seat]})
            sim.game["shops"]=recorded_shops
            all_rows[name]=rows
            summaries[name]={"day":day,"sites":spec["times"],"recorded_margin_delta":rows[0]["margin_delta"],
                             "random_future":summarize(rows[1:])}
            print(name,summaries[name],flush=True)
    result={"episode":EPISODE,"scenario_seed":2026092300,
            "random_futures_per_probe":N_RANDOM,"summary":summaries,"rows":all_rows,
            "limitation":"Retrospectively chosen sites and fixed recorded action streams for both players. Future shops change market demand but agents do not replan; this is not a calibrated live-policy return distribution."}
    OUT.write_text(json.dumps(result,indent=2),encoding="utf-8")


if __name__=="__main__":
    main()
