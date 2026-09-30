"""Frozen forecast policy versus controls, on fresh complete seasons."""
from concurrent.futures import ProcessPoolExecutor, as_completed
from hashlib import sha256
from importlib.metadata import version
import json, sys, time
from market_corpus import ROOT, OUT, PATHS, load
from evaluate_boards import Ledger


def run(job, deposit=False):
    seed, seat, opponent, mode = job
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    sys.path.insert(0,str(ROOT/'agents'))
    if deposit == 'products':
        from market_sales_dp_products import SalesPolicy
    elif deposit:
        from market_sales_dp_deposits import SalesPolicy
    else:
        from market_sales_dp import SalesPolicy
    base = load('sales_base',PATHS['old']).Agent()
    candidate = base if mode == 'baseline' else SalesPolicy(base,mode)
    opp = load('sales_opponent',PATHS[opponent])
    def own(o): return candidate.act(o)
    def other(o): return opp.agent(o)
    agents = [None,None];agents[seat]=own;agents[1-seat]=other
    env = make('kaggriculture',configuration={'seed':seed,'episodeSteps':720})
    initial = [f.money for f in env.state[0].observation.farms]
    start = time.perf_counter()
    with Ledger(E) as ledger: env.run(agents)
    assert len(env.steps)==720 and all(s.status in ('ACTIVE','DONE') for ss in env.steps for s in ss)
    for i in range(2):
        expected=initial[i]+sum(ledger.data[i]['revenue'].values())-sum(ledger.data[i]['spend'].values())
        assert expected == env.state[i].reward,(expected,env.state[i].reward)
    assert not getattr(candidate,'lot',None), 'Unsold reserved lot at season end'
    actions=[ss[seat].action for ss in env.steps[1:]]
    physical=[{k:a[k] for k in ('farmer','hands')} for a in actions]
    r={'seed':seed,'seat':seat,'opponent':opponent,'mode':mode,
       'cash':env.state[seat].reward,'opponent_cash':env.state[1-seat].reward,
       'stats':dict(getattr(candidate,'stats',{})), 'ledger':ledger.data[seat],
       'action_hash':sha256(json.dumps(actions,sort_keys=True).encode()).hexdigest(),
       'physical_hash':sha256(json.dumps(physical,sort_keys=True).encode()).hexdigest(),
       'seconds':time.perf_counter()-start}
    folder = 'product_sales_games' if deposit == 'products' else 'deposit_sales_games' if deposit else 'sales_games'
    p=OUT/folder/f'{seed}-{seat}-{opponent}-{mode}.json'
    p.write_text(json.dumps(r,indent=2))
    return r


def main():
    (OUT/'sales_games').mkdir(exist_ok=True)
    manifest={'engine':version('kaggle-environments'),'seeds':list(range(98000,98004)),
      'modes':['baseline','current','visible'],'opponents':['sixday','pasture'],
      'selection':json.loads((OUT/'forecast_selection.json').read_text()),
      'rules':'One crop lot <=10 units; day>=15; cash>=5000; 24-turn maximum hold; storage guard; force liquidate by718.',
      'sources':{str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in
        [ROOT/'agents/market_sales_dp.py',ROOT/'agents/market_forecast.py',*PATHS.values()]}}
    mp=OUT/'sales_manifest.json'
    if mp.exists(): assert json.loads(mp.read_text())==manifest,'Policy changed during frozen evaluation'
    else: mp.write_text(json.dumps(manifest,indent=2))
    jobs=[(s,i,o,m) for s in manifest['seeds'] for i in (0,1) for o in manifest['opponents'] for m in manifest['modes']]
    pending=[j for j in jobs if not (OUT/'sales_games'/('{}-{}-{}-{}.json'.format(*j))).exists()]
    with ProcessPoolExecutor(max_workers=4,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run,j) for j in pending]):
            r=f.result();print(r['seed'],r['seat'],r['opponent'],r['mode'],r['cash'],r['stats'],flush=True)
    rows=[json.loads(p.read_text()) for p in sorted((OUT/'sales_games').glob('*.json'))]
    (OUT/'sales_results.json').write_text(json.dumps(rows,indent=2))
    print('COMPLETE',len(rows),flush=True)

if __name__=='__main__':main()
