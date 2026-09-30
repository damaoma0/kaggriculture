"""Test two- and three-tile wheat-to-strawberry edits in the losing case."""
from copy import deepcopy
import gzip
from itertools import combinations
import json

from probe_semantic_handoff import ROOT
from probe_large_losing_local_edits import evaluate, EPISODE, DAY, END, START, SEED_STEP


OUT=ROOT/"results/fresh/semantic_tapes/large_losing_multi_tile.json"


def main():
    with gzip.open(ROOT/f"data/ladder_panel/56395605/{EPISODE}.json.gz","rt",encoding="utf-8") as f:
        game=json.load(f)
    seat=int(game["seat"])
    original=[deepcopy(game["our_actions"] if i==seat else game["opp_actions"]) for i in range(2)]
    plants=json.loads((ROOT/"results/fresh/semantic_tapes/large_losing_case_inspection.json").read_text(encoding="utf-8"))["wheat_plantings"]
    plants=[p for p in plants if p["t"]!=435]  # That tile lost a successful feed in its one-tile replay.
    baseline=evaluate(game,original,seat)
    results=[]
    for n in (2,3):
        for group in combinations(plants,n):
            pair=deepcopy(original)
            pair[seat][SEED_STEP]["market"].append(["BUY_SEED","STRAWBERRY",n-1])
            for plant in group:
                t,u=plant["t"],plant["unit"]
                assert pair[seat][t]["hands"][u-1]==["PLANT","WHEAT"]
                pair[seat][t]["hands"][u-1]=["PLANT","STRAWBERRY"]
            for future in range(min(p["t"] for p in group)+1,END):
                if any(cmd[:2]==["SELL","STRAWBERRY"] for cmd in original[seat][future]["market"]):
                    if len(pair[seat][future]["market"])<10:
                        pair[seat][future]["market"].append(["SELL","STRAWBERRY",10])
            pair[seat][718]["market"].append(["SELL","STRAWBERRY",10])
            row=evaluate(game,pair,seat)
            row.update(plantings=[{"t":p["t"],"pos":p["pos"]} for p in group],
                       margin_delta=row["margin"]-baseline["margin"],
                       cash_delta=row["cash"]-baseline["cash"],
                       rival_cash_delta=row["rival_cash"]-baseline["rival_cash"],
                       feed_delta=sum(row["feeds"].get(d,0)-baseline["feeds"].get(d,0)
                                      for d in set(row["feeds"])|set(baseline["feeds"])))
            results.append(row)
            print(n,[p["t"] for p in group],row["margin_delta"],"feed",row["feed_delta"],flush=True)
    ranked=sorted(results,key=lambda r:r["margin_delta"],reverse=True)
    OUT.write_text(json.dumps({"episode":EPISODE,"day":DAY,"combinations":len(results),
        "best_tested":ranked[0],"top_ten":[{k:r[k] for k in
            ("plantings","margin_delta","cash_delta","rival_cash_delta","feed_delta")}
            for r in ranked[:10]],"all":results,
        "limitation":"Post hoc tile combination search in one fixed world, not a prospective policy estimate."},indent=2),encoding="utf-8")
    print("best",[p["t"] for p in ranked[0]["plantings"]],ranked[0]["margin_delta"],flush=True)


if __name__=="__main__":
    main()
