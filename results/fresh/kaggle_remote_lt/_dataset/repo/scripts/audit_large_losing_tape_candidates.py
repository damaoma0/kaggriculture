"""Rank recorded losing tapes with large revealed demand mismatches.

Report retrieval fit, live farm compatibility and whether requested crop
changes point toward the visible product-demand gap. This is a screening
audit, not evidence that a different tape would earn more money.
"""
from collections import Counter
import gzip
import json

from audit_production_plan_fit import ROOT, load_library


OUT = ROOT / "results/fresh/semantic_tapes/large_losing_candidates.json"
PRODUCTS = ("STRAWBERRY", "TOMATO", "WOOL", "CARROT", "MILK", "EGG", "WHEAT")
CROPS = ("STRAWBERRY", "TOMATO", "CARROT", "WHEAT")


def plants(profile, day):
    result=Counter()
    for key,n in profile["requested_plants"].items():
        t,p=key.split(":",1)
        if day<=int(t)<day+3:
            result[p]+=n
    return result


def main():
    ns,library=load_library()
    tapes={t["ep"]:t for t in library["tapes"]}
    profiles={p["episode"]:p for p in json.loads((ROOT/"results/fresh/semantic_tapes/compact_profiles.json").read_text(encoding="utf-8"))}
    audit=json.loads((ROOT/"results/fresh/semantic_tapes/retrieval_audit.json").read_text(encoding="utf-8"))
    queries={(q["episode"],q["day"]):q for q in json.loads((ROOT/"results/fresh/production_plan_fit/audit.json").read_text(encoding="utf-8"))["rows"]}
    margins={}
    rows=[]
    for row in audit["rows"]:
        ep,day=row["episode"],row["day"]
        if ep not in margins:
            with gzip.open(ROOT/f"data/ladder_panel/56395605/{ep}.json.gz","rt",encoding="utf-8") as f:
                game=json.load(f)
            seat=int(game["seat"])
            margins[ep]=float(game["rewards"][seat]-game["rewards"][1-seat])
        if margins[ep]>=-3000 or row["current"]["history"]<25:
            continue
        current_ep=row["current"]["episode"]
        current=row["current"]
        shops=queries[(ep,day)]["shops"]
        k=len(shops)
        actual_vec=ns["_mgt_vec"](shops,k)
        current_vec=tapes[current_ep]["vec"][k]
        demand_gap={p:actual_vec[i]-current_vec[i] for i,p in enumerate(PRODUCTS)}
        cur_plants=plants(profiles[current_ep],day)
        for candidate in (row["plan_edit_8"],row["plan_edit_16"],row["position_free"]):
            if candidate["episode"]==current_ep:
                continue
            candidate_ep=candidate["episode"]
            candidate_vec=tapes[candidate_ep]["vec"][k]
            plant_delta={p:plants(profiles[candidate_ep],day)[p]-cur_plants[p] for p in CROPS}
            aligned=[p for p in CROPS if plant_delta[p]*demand_gap[p]>0]
            opposed=[p for p in CROPS if plant_delta[p]*demand_gap[p]<0]
            rows.append({"episode":ep,"seat":row["seat"],"day":day,"margin":margins[ep],
                "current_episode":current_ep,"candidate_episode":candidate_ep,
                "current_history":current["history"],"candidate_history":candidate["history"],
                "history_gain":current["history"]-candidate["history"],
                "current_asset_gap":current["asset_gap"],"candidate_asset_gap":candidate["asset_gap"],
                "additional_animal_shortfall":candidate["animal_shortfall"]-current["animal_shortfall"],
                "plant_edit":candidate["plant_edit"],"demand_gap":demand_gap,"plant_delta":plant_delta,
                "aligned":aligned,"opposed":opposed,"actual_demand":actual_vec,
                "incumbent_demand":current_vec,"candidate_demand":candidate_vec})
    unique={}
    for r in rows:
        key=(r["episode"],r["day"],r["candidate_episode"])
        unique[key]=r
    rows=list(unique.values())
    eligible=[r for r in rows if r["history_gain"]>=8 and r["candidate_asset_gap"]<=r["current_asset_gap"]+6
              and r["additional_animal_shortfall"]<=0 and r["plant_edit"]<=16 and r["aligned"] and not r["opposed"]]
    eligible.sort(key=lambda r:(r["current_history"],r["history_gain"],-r["margin"]),reverse=True)
    OUT.write_text(json.dumps({"criteria":{"margin_below":-3000,"current_history_at_least":25,
        "history_gain_at_least":8,"asset_slack":6,"plant_edit_at_most":16,
        "no_additional_animal_shortfall":True,"crop_direction":"at least one aligned and no opposed"},
        "eligible":eligible,"all_candidate_rows":rows},indent=2),encoding="utf-8")
    print(json.dumps({"eligible_count":len(eligible),"top":[{k:r[k] for k in
        ("episode","day","margin","current_history","candidate_history","current_asset_gap",
         "candidate_asset_gap","plant_edit","demand_gap","plant_delta","aligned")}
         for r in eligible[:15]]},indent=2))


if __name__=="__main__":
    main()
