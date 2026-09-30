"""Exact remaining-shop demand priors for a recorded reveal sequence.

Shops are independent uniform draws with replacement. These are town market
withdrawals, not forecasts of profitable farm production or sale prices.
"""
from collections import Counter
import gzip
import json
from math import comb

from probe_semantic_handoff import ROOT
from research_labour_profit import engine


OUT=ROOT/"results/fresh/semantic_tapes/exact_shop_expectancy.json"
EPISODE=111287532
PRODUCTS=("STRAWBERRY","WOOL","WHEAT","CARROT","TOMATO","MILK","EGG")
REVEAL_DAYS=tuple(range(3,25,3))
SEASON_END_DAY=30
SHOP_INTERVAL=4


def multiplier(shop, product, shops):
    goods=shops[shop]
    return (2 if len(goods)==1 else 1) if product in goods else 0


def tail_probability(n, p, threshold):
    return sum(comb(n,k)*p**k*(1-p)**(n-k) for k in range(max(0,threshold),n+1))


def main():
    E=engine()
    shops=E.SHOPS
    assert len(shops)==8 and SHOP_INTERVAL==4
    with gzip.open(ROOT/f"data/ladder_panel/56395605/{EPISODE}.json.gz","rt",encoding="utf-8") as f:
        game=json.load(f)
    means={p:sum(multiplier(s,p,shops) for s in shops)/len(shops) for p in PRODUCTS}
    berry_prob=sum(multiplier(s,"STRAWBERRY",shops)>0 for s in shops)/len(shops)
    yarn_prob=1/len(shops)
    rows=[]
    for day in (9,12,15,18,21,24):
        visible=game["shops"][day]
        future=[r for r in REVEAL_DAYS if r>day]
        actual_final=game["shops"][24]
        known_berry=sum(multiplier(s,"STRAWBERRY",shops)>0 for s in visible)
        known_yarn=visible.count("YARN_STORE")
        known_future_withdrawals={}
        expected_unseen_withdrawals={}
        realized_unseen_withdrawals={}
        for p in PRODUCTS:
            known_future_withdrawals[p]=24//SHOP_INTERVAL*(SEASON_END_DAY-day)*sum(multiplier(s,p,shops) for s in visible)
            expected_unseen_withdrawals[p]=24//SHOP_INTERVAL*sum((SEASON_END_DAY-r)*means[p] for r in future)
            realized_unseen_withdrawals[p]=24//SHOP_INTERVAL*sum((SEASON_END_DAY-r)*multiplier(actual_final[i],p,shops)
                                                                 for i,r in enumerate(REVEAL_DAYS) if r>day)
        rows.append({"day":day,"visible":visible,"unseen_draws":len(future),
                     "strawberry_shop_count_known":known_berry,
                     "strawberry_shop_count_expected_final":known_berry+len(future)*berry_prob,
                     "prob_final_at_least_four_strawberry_shops":tail_probability(len(future),berry_prob,4-known_berry),
                     "yarn_shop_count_known":known_yarn,
                     "yarn_shop_count_expected_final":known_yarn+len(future)*yarn_prob,
                     "prob_final_at_least_two_yarn_stores":tail_probability(len(future),yarn_prob,2-known_yarn),
                     "known_shops_future_withdrawals":known_future_withdrawals,
                     "expected_unseen_shop_withdrawals":expected_unseen_withdrawals,
                     "realized_unseen_shop_withdrawals":realized_unseen_withdrawals})
    result={"episode":EPISODE,"shop_types":sorted(shops),"draws_uniform_with_replacement":True,
            "market_withdrawals_per_day_per_shop":24//SHOP_INTERVAL,
            "mean_per_draw_demand_multiplier":means,
            "actual_final_shop_counts":dict(Counter(game["shops"][24])),
            "rows":rows,
            "limitation":"Exact shop-draw and town-withdrawal expectation only; profitable production also depends on crop timing, upkeep, market price response, rival supply, labor, and displaced output."}
    OUT.write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps({"means":means,"actual_final_shop_counts":result["actual_final_shop_counts"],
                      "rows":[{k:r[k] for k in ("day","unseen_draws","strawberry_shop_count_known",
                                                "strawberry_shop_count_expected_final",
                                                "prob_final_at_least_four_strawberry_shops",
                                                "yarn_shop_count_known","yarn_shop_count_expected_final")}
                              for r in rows]},indent=2))


if __name__=="__main__":
    main()
