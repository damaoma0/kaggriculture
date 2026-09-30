"""Balanced first-shop configuration search with observed-shop policy selection."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from hashlib import sha256
import itertools
import json
import random
from statistics import mean
from search_growth_openings import ROOT, play

SHOPS=sorted(["BAKERY","PIZZA_SHOP","BRUNCH_SPOT","YARN_STORE","ICE_CREAM_SHOP","PET_CAFE","SMOOTHIE_SHOP","FARMERS_MARKET"])
OUT=ROOT/"results/fresh/shop_grid"


def grid():
    c={"public-router":{},"growth-control":{"cows":4,"sheep":4}}
    for cows,sheep in ((4,4),(8,4),(4,8),(8,8)):
        for crop,hands in itertools.product(("WHEAT","STRAWBERRY"),(8,10)):
            c[f"shop-c{cows}s{sheep}-{crop.lower()}-h{hands}"]={"default":{"COW":cows,"SHEEP":sheep,"crop":crop,"hands":hands}}
    return c


def run(job):
    name,cfg,seed,future,seat,first,schedule,save=job
    from kaggle_environments.envs.kaggriculture import kaggriculture as engine
    original=engine._end_of_day
    def end_day(state,env,day):
        original(state,env,day)
        shops=state[0].observation.town["unlocked_shops"]
        # Balanced experimental fixture: replace ONLY the newly revealed shop.
        # No future schedule is placed in observations or passed to policies.
        if (day+1)%3==0 and shops:
            shops[-1]=schedule[min((day+1)//3-1,7)]
    engine._end_of_day=end_day
    try:
        r=play((name,cfg,seed,future,seat,"replant",save,"replant"))
        r.update(first_shop=first,shop_schedule=schedule)
        return r
    finally: engine._end_of_day=original


def fit():
    rows=json.loads((OUT/"train.json").read_text())
    assert len(rows)==len(grid())*16, "Training panel is incomplete"
    candidates={n:c for n,c in grid().items() if n!="growth-control"}
    score=lambda n,rs:mean(r['margin'] for r in rs if r['name']==n)
    best=max(candidates,key=lambda n:score(n,rows))
    choice={}
    for shop in SHOPS:
        group=[r for r in rows if r['first_shop']==shop]
        # Shrink noisy two-scenario shop estimates toward the global mean.
        pick=max(candidates,key=lambda n:0.5*score(n,group)+0.5*score(n,rows))
        choice[shop]="router" if pick=="public-router" else candidates[pick]["default"]
    default="router" if best=="public-router" else candidates[best]["default"]
    learned={"fixed_name":best,"fixed":{"default":default},"adaptive":{"default":default,"by_shop":choice}}
    (OUT/"learned.json").write_text(json.dumps(learned,indent=2),encoding="utf-8")
    print(json.dumps(learned,indent=2))


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--stage",choices=("train","fit","validate","test"),required=True)
    ap.add_argument("--workers",type=int,default=3)
    args=ap.parse_args(); OUT.mkdir(parents=True,exist_ok=True)
    if args.stage=="fit": fit(); return
    if args.stage=="train": configs=grid()
    else:
        learned=json.loads((OUT/"learned.json").read_text())
        configs={"public-router":{},"growth-control":{"cows":4,"sheep":4},"shop-fixed":learned['fixed'],"shop-adaptive":learned['adaptive']}
    start={"train":87000,"validate":88000,"test":89000}[args.stage]
    jobs=[]
    # Training: two scenarios per shop with opposite seats. Validation/test:
    # two new scenario seeds per shop, BOTH seats (32 scenarios per policy).
    for index,shop in enumerate(SHOPS):
        for rep in range(2):
            seed=start+index*10+rep
            schedule=[shop]+random.Random(seed+40000).choices(SHOPS,k=7)
            for seat in ((rep,) if args.stage=="train" else (0,1)):
                for name,cfg in configs.items():
                    save=str(OUT/f"{args.stage}-{name}-{seed}-seat{seat}") if args.stage=="test" and index==0 and rep==0 else None
                    jobs.append((name,cfg,seed,seed+10000,seat,shop,schedule,save))
    files=["agents/shop_opening.py","agents/opening_v2.py","agents/opening_v1.py","agents/public/tschinkel_router_v31.py","scripts/search_shop_grid.py","scripts/search_growth_openings.py","scripts/evaluate_boards.py"]
    manifest={"configs":configs,"jobs":jobs,"hashes":{p:sha256((ROOT/p).read_bytes()).hexdigest() for p in files},"fixture":"balanced first shop; scheduled shop replacements at normal unlock times"}
    manifest_path=OUT/f"{args.stage}-manifest.json"
    if manifest_path.exists():
        prior=json.loads(manifest_path.read_text())
        assert prior['configs']==configs and prior['jobs']==json.loads(json.dumps(jobs))
        for p,h in prior['hashes'].items():
            if p!='scripts/search_shop_grid.py': assert h==manifest['hashes'][p], f"Source changed: {p}"
        (OUT/f"{args.stage}-resume-manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    else: manifest_path.write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    result_path=OUT/f"{args.stage}.json"
    rows=json.loads(result_path.read_text()) if result_path.exists() else []
    done={(r['name'],r['seed'],r['seat']) for r in rows}
    assert len(done)==len(rows)
    pending=[j for j in jobs if (j[0],j[2],j[4]) not in done]
    print(f"Resume: {len(rows)} saved; {len(pending)} pending",flush=True)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for f in as_completed([pool.submit(run,j) for j in pending]):
            r=f.result(); rows.append(r)
            temporary=result_path.with_suffix('.json.tmp')
            temporary.write_text(json.dumps(rows,indent=2),encoding="utf-8")
            temporary.replace(result_path)
            print(len(rows),"/",len(jobs),r['name'],r['first_shop'],r['seed'],r['seat'],"margin",r['margin'],flush=True)
    for n in sorted(configs,key=lambda n:-mean(r['margin'] for r in rows if r['name']==n)):
        g=[r for r in rows if r['name']==n]
        print(n,"margin",round(mean(r['margin'] for r in g)),"cash",round(mean(r['our_final'] for r in g)),"wins",sum(r['margin']>0 for r in g))


if __name__=="__main__":main()
