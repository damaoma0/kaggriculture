"""Record visible demand and incumbent mismatch across this game's reveals."""
import gzip
import json

from audit_production_plan_fit import ROOT, load_library


OUT=ROOT/"results/fresh/semantic_tapes/reveal_aligned_shop_gaps.json"
EPISODE=111287532
PRODUCTS=("STRAWBERRY","TOMATO","WOOL","CARROT","MILK","EGG","WHEAT")


def main():
    ns,library=load_library()
    tapes={t["ep"]:t for t in library["tapes"]}
    audit=json.loads((ROOT/"results/fresh/semantic_tapes/retrieval_audit.json").read_text(encoding="utf-8"))
    queries=json.loads((ROOT/"results/fresh/production_plan_fit/audit.json").read_text(encoding="utf-8"))
    by_day={q["day"]:q for q in queries["rows"] if q["episode"]==EPISODE}
    current_by_day={r["day"]:r["current"] for r in audit["rows"] if r["episode"]==EPISODE}
    with gzip.open(ROOT/f"data/ladder_panel/56395605/{EPISODE}.json.gz","rt",encoding="utf-8") as f:
        game=json.load(f)
    rows=[]
    for day in range(30):
        shops=game["shops"][day]
        prior=game["shops"][day-1] if day else []
        if len(shops)==len(prior):
            continue
        assert len(shops)==len(prior)+1
        k=len(shops)
        actual=ns["_mgt_vec"](shops,k)
        row={"day":day,"shops":shops,"new_shop":shops[-1],
             "actual_demand":dict(zip(PRODUCTS,actual))}
        if day in current_by_day:
            assert by_day[day]["shops"]==shops
            route=current_by_day[day]["episode"]
            incumbent=tapes[route]["vec"][k]
            row.update(incumbent_tape=route,history_distance=current_by_day[day]["history"],
                       incumbent_demand=dict(zip(PRODUCTS,incumbent)),
                       gap=dict(zip(PRODUCTS,(x-y for x,y in zip(actual,incumbent)))))
        rows.append(row)
    OUT.write_text(json.dumps({"episode":EPISODE,"rows":rows},indent=2),encoding="utf-8")
    print(json.dumps(rows,indent=2))


if __name__=="__main__":
    main()
