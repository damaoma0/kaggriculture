"""Search opening capital allocation with direct, symmetric replant evaluation."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from hashlib import sha256
import json
from statistics import mean
from search_growth_openings import ROOT, play


def candidates():
    c={"public-router":{}, "growth-control":{"cows":4,"sheep":4}}
    for animal in ("COW","SHEEP"):
        other="SHEEP" if animal=="COW" else "COW"
        c[f"route-all-{animal.lower()}"]={"mapping":{other:animal}}
    for a,b in (("MELON","STRAWBERRY"),("STRAWBERRY","MELON"),("MELON","WHEAT"),("STRAWBERRY","WHEAT"),("WHEAT","CARROT"),("MELON","TOMATO"),("STRAWBERRY","TOMATO")):
        c[f"route-{a.lower()}-to-{b.lower()}"]={"mapping":{a:b}}
    c["route-sell-fertilizer"]={"sell_fertilizer":True}
    c["route-sales-first"]={"sales_first":True}
    for cap in (6,8,10): c[f"route-hands{cap}"]={"hire_cap":cap}
    for initial in (2,4,6):
        for melons in (0,4,8):
            c[f"growth-i{initial}-m{melons}"]={"cows":4,"sheep":4,"initial_animals":initial,"melons":melons,"strawberries":8,"strawberry_day":3,"land_day":0,"land_buffer":50,"grow_day":1}
    for age in (2,3,4):
        for crop in ("WHEAT","CARROT"):
            c[f"growth-{crop.lower()}-age{age}"]={"cows":4,"sheep":4,"initial_animals":2,"melons":0,"strawberries":0,"land_day":0,"land_buffer":50,"grow_day":1,"cash_crop":crop,"harvest_age":age}
    return c


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--stage",choices=("screen","validate","confirm"),required=True)
    ap.add_argument("--names",nargs="*")
    args=ap.parse_args()
    variants={n:c for n,c in candidates().items() if not args.names or n in args.names}
    assert variants and (not args.names or set(args.names)==set(variants))
    out=ROOT/"results/fresh/capital_search"
    out.mkdir(parents=True,exist_ok=True)
    seeds=range(86401,86403) if args.stage=="screen" else range(86501,86505) if args.stage=="validate" else range(86601,86605)
    seats=(0,) if args.stage=="screen" else (0,1)
    jobs=[(n,c,s,s+10000,seat,"replant",str(out/f"{n}-{s}-seat{seat}") if args.stage=="confirm" and s==86601 else None,"replant") for n,c in variants.items() for s in seeds for seat in seats]
    hashes={p:sha256((ROOT/p).read_bytes()).hexdigest() for p in ("agents/router_opening_variant.py","agents/opening_v2.py","agents/opening_v1.py","agents/public/tschinkel_router_v31.py","scripts/evaluate_boards.py","scripts/search_growth_openings.py","scripts/search_capital.py")}
    (out/f"{args.stage}-manifest.json").write_text(json.dumps({"variants":variants,"jobs":jobs,"hashes":hashes},indent=2),encoding="utf-8")
    rows=[]
    with ProcessPoolExecutor(max_workers=3) as pool:
        for f in as_completed([pool.submit(play,j) for j in jobs]):
            r=f.result(); rows.append(r)
            (out/f"{args.stage}.json").write_text(json.dumps(rows,indent=2),encoding="utf-8")
            print(len(rows),"/",len(jobs),r["name"],r["seed"],r["seat"],"cash",r["our_final"],"margin",r["margin"],"losses",r["opening_losses"],flush=True)
    for n in sorted(variants,key=lambda n:-mean(r["margin"] for r in rows if r["name"]==n)):
        g=[r for r in rows if r["name"]==n]
        print(n,"margin",round(mean(r["margin"] for r in g)),"cash",round(mean(r["our_final"] for r in g)),"wins",sum(r["margin"]>0 for r in g))


if __name__=="__main__": main()
