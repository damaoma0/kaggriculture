"""Screen funded strawberry shifts only at the day-12 and day-15 reveals.

Candidate sites are the one-tile edits that gained margin individually without
losing feed. This retrospective subset search tests whether their gains add
up; it does not select tiles from information available to a live agent.
"""
from copy import deepcopy
import gzip
from itertools import combinations
import json

from probe_semantic_handoff import ROOT
from probe_earlier_strawberry_shift import evaluate, EPISODE, END


OUT=ROOT/"results/fresh/semantic_tapes/reveal_aligned_strawberry_portfolio.json"
SITES=((302,(2,3)),(306,(1,9)),(307,(0,9)),
       (365,(4,6)),(374,(1,6)),(381,(0,0)))


def main():
    with gzip.open(ROOT/f"data/ladder_panel/56395605/{EPISODE}.json.gz","rt",encoding="utf-8") as f:
        game=json.load(f)
    seat=int(game["seat"])
    original=[deepcopy(game["our_actions"] if i==seat else game["opp_actions"]) for i in range(2)]
    inspections=json.loads((ROOT/"results/fresh/semantic_tapes/earlier_strawberry_sites.json").read_text(encoding="utf-8"))["days"]
    by_site={(p["t"],tuple(p["pos"])):p for day in inspections for p in day["wheat_plantings"]}
    assert all(site in by_site for site in SITES)
    baseline=evaluate(game,original,seat)
    rows=[]
    for n in range(1,len(SITES)+1):
        for subset in combinations(SITES,n):
            pair=deepcopy(original)
            n12=sum(t//24==12 for t,_ in subset)
            n15=n-n12
            for t,pos in subset:
                unit=by_site[(t,pos)]["unit"]
                assert unit>0 and pair[seat][t]["hands"][unit-1]==["PLANT","WHEAT"]
                pair[seat][t]["hands"][unit-1]=["PLANT","STRAWBERRY"]
            add12=max(0,n12-1)
            add15=(n15 if n12 else max(0,n15-1))
            if add12:
                order=next(cmd for cmd in pair[seat][298]["market"]
                           if cmd[:2]==["BUY_SEED","STRAWBERRY"])
                order[2]+=add12
            if add15:
                assert len(pair[seat][361]["market"])<10
                pair[seat][361]["market"].append(["BUY_SEED","STRAWBERRY",add15])
            first_maturity=min(t//24+10 for t,_ in subset)*24
            for future in range(first_maturity,END):
                if any(cmd[:2]==["SELL","STRAWBERRY"] for cmd in original[seat][future]["market"]):
                    if len(pair[seat][future]["market"])<10:
                        pair[seat][future]["market"].append(["SELL","STRAWBERRY",10])
            pair[seat][718]["market"].append(["SELL","STRAWBERRY",10])
            v=evaluate(game,pair,seat)
            target_ok=all(any(p["t"]==t and tuple(p["pos"])==pos for p in v["strawberry_plants"])
                          for t,pos in subset)
            baseline_ok=all(p in v["strawberry_plants"] for p in baseline["strawberry_plants"])
            feed_days=set(v["feeds"])|set(baseline["feeds"])
            feed_delta=sum(v["feeds"].get(d,0)-baseline["feeds"].get(d,0)
                           for d in feed_days)
            feeds_preserved=all(v["feeds"].get(d,0)>=baseline["feeds"].get(d,0)
                                for d in feed_days)
            rows.append({"sites":[{"t":t,"pos":pos} for t,pos in subset],
                         "n12":n12,"n15":n15,"seed_additions":{"day12":add12,"day15":add15},
                         "margin_delta":v["margin"]-baseline["margin"],
                         "cash_delta":v["cash"]-baseline["cash"],
                         "rival_cash_delta":v["rival_cash"]-baseline["rival_cash"],
                         "feed_delta":feed_delta,"feeds_preserved":feeds_preserved,
                         "target_success":target_ok,
                         "baseline_plants_preserved":baseline_ok,
                         "strawberry_output_delta":v["output"].get("STRAWBERRY",0)-baseline["output"].get("STRAWBERRY",0),
                         "strawberry_revenue_delta":v["revenue"].get("STRAWBERRY",0)-baseline["revenue"].get("STRAWBERRY",0),
                         "wheat_output_delta":v["output"].get("WHEAT",0)-baseline["output"].get("WHEAT",0),
                         "carrot_output_delta":v["output"].get("CARROT",0)-baseline["output"].get("CARROT",0),
                         "final_strawberry_shed":v["shed"]["STRAWBERRY"]})
        print("finished subset size",n,flush=True)
    eligible=[r for r in rows if r["target_success"] and r["baseline_plants_preserved"] and r["feeds_preserved"]]
    ranked=sorted(eligible,key=lambda r:r["margin_delta"],reverse=True)
    OUT.write_text(json.dumps({"episode":EPISODE,"baseline_margin":baseline["margin"],
        "tested":len(rows),"eligible":len(eligible),"best_tested":ranked[0],
        "top_ten":ranked[:10],"all":rows,
        "limitation":"Post hoc search among six sites chosen from their positive individual outcomes in one world; not a prospective selector or generalized result."},indent=2),encoding="utf-8")
    print(json.dumps({"tested":len(rows),"eligible":len(eligible),"best":ranked[0],
                      "top_margin_deltas":[r["margin_delta"] for r in ranked[:10]]},indent=2),flush=True)


if __name__=="__main__":
    main()
