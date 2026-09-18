"""Exercise both per-base selected standalone files through the official loader."""
from concurrent.futures import ProcessPoolExecutor
from hashlib import sha256
import json
from market_corpus import ROOT
from evaluate_boards import Ledger
from research_wheat_economy import WheatAudit

OUT=ROOT/'results/fresh/modern_sales'

def run(base):
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    selection=json.loads((OUT/'selection.json').read_text(encoding='utf-8'))[base]
    path=ROOT/selection['path'];assert sha256(path.read_bytes()).hexdigest()==selection['sha256']
    rival='v45' if base=='v44' else 'v44'
    seed=142998 if base=='v44' else 142999
    env=make('kaggriculture',configuration={'seed':seed,'episodeSteps':720})
    with Ledger(E) as ledger:
        with WheatAudit(E,env):env.run([str(path),str(ROOT/f'data/router_refresh_20260916/{rival}/main.py')])
    assert len(env.steps)==720 and all(s.status in ('ACTIVE','DONE') for ss in env.steps for s in ss),(base,len(env.steps),env.logs[-2:])
    for i in (0,1):assert 3000+sum(ledger.data[i]['revenue'].values())-sum(ledger.data[i]['spend'].values())==env.state[i].reward
    return dict(base=base,seed=seed,sha256=selection['sha256'],steps=len(env.steps),statuses=[s.status for s in env.state],cash=[s.reward for s in env.state])

def main():
    with ProcessPoolExecutor(max_workers=2,max_tasks_per_child=1) as pool:results=list(pool.map(run,('v44','v45')))
    (OUT/'entrypoint_checks.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(json.dumps(results,indent=2))

if __name__=='__main__':main()
