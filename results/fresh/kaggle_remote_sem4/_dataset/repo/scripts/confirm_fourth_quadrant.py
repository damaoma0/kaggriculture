"""Fresh mixed-shop tests around tomato and wool expansion boundaries."""
from concurrent.futures import ProcessPoolExecutor,as_completed
import json,random
import research_fourth_quadrant as R

SHOPS=['BAKERY','PIZZA_SHOP','BRUNCH_SPOT','YARN_STORE','ICE_CREAM_SHOP','PET_CAFE','SMOOTHIE_SHOP','FARMERS_MARKET']

def configs():
    out={}
    for j,(kind,count) in enumerate([('tomato',2),('tomato',3),('yarn',2),('yarn',3)]):
        for replicate in range(2):
            seed=156000+2*j+replicate;rng=random.Random(seed)
            if kind=='tomato':
                prefix=rng.choices(['PIZZA_SHOP','FARMERS_MARKET'],k=count)+rng.choices([s for s in SHOPS if s not in ('PIZZA_SHOP','FARMERS_MARKET')],k=6-count);rng.shuffle(prefix)
            else:
                prefix=['YARN_STORE']*count+rng.choices([s for s in SHOPS if s!='YARN_STORE'],k=4-count);rng.shuffle(prefix);prefix+=rng.choices([s for s in SHOPS if s!='YARN_STORE'],k=2)
            out[f'{kind}{count}_r{replicate}']=(seed,prefix,'tomato' if kind=='tomato' else 'sheep')
    return out

def run(job):
    R.CONFIGS.update({k:v[1] for k,v in configs().items()})
    return R.run(job)

if __name__=='__main__':
    cs=configs();jobs=[('confirmation',seed,c,seat,o,m) for c,(seed,prefix,force) in cs.items() for seat in (0,1) for o in ('v45','twocoins') for m in ('none','native',force)]
    manifest=dict(design='Fresh mixed shop prefixes around 2/3 tomato shops at day18 and 2/3 yarn stores at day12. Each cell has two independent prefixes/seeds, both seats, two active opponents, no expansion/native/forced relevant plan. No gate tuning on this panel.',configs=cs,jobs=jobs)
    (R.OUT/'confirmation_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    pending=[j for j in jobs if not (R.OUT/'games'/('-'.join(map(str,j))+'.json')).exists()]
    with ProcessPoolExecutor(max_workers=2,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run,j) for j in pending]):f.result()
