"""Account for the six-day router advantage with successful engine transactions."""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
import json
from market_corpus import ROOT, PATHS, load
from evaluate_boards import Ledger

OUT=ROOT/'results/fresh/production_research'

def run(job):
    seed,seat=job
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    mods=[None,None];mods[seat]=load('audit_old',PATHS['old']);mods[1-seat]=load('audit_sixday',PATHS['sixday'])
    env=make('kaggriculture',configuration={'seed':seed,'episodeSteps':720})
    start=[f.money for f in env.state[0].observation.farms]
    events=[];daily=[];clock=[0]
    with Ledger(E) as ledger:
        commit=E._commit_unit
        def tracked(op,item,price,f,p,m,shed_capacity=100):
            ok=commit(op,item,price,f,p,m,shed_capacity)
            if ok:events.append([clock[0],ledger.seats[id(f)],op,item,price])
            return ok
        E._commit_unit=tracked
        def wrap(i):
            def act(o):
                clock[0]=o['step']
                if i==0 and o['step']%24==0:
                    daily.append({'step':o['step'],'ledger':deepcopy(ledger.data),
                        'cash':[f['money'] for f in o['farms']],
                        'boards':[dict(Counter(t.get('animal') or t.get('crop') for row in f['tiles'] for t in row if isinstance(t,dict) and (t.get('animal') or t.get('kind')=='PLANT'))) for f in o['farms']]})
                return mods[i].agent(o)
            return act
        env.run([wrap(0),wrap(1)])
        E._commit_unit=commit
    assert len(env.steps)==720 and all(s.status in ('ACTIVE','DONE') for ss in env.steps for s in ss)
    for i in (0,1):assert start[i]+sum(ledger.data[i]['revenue'].values())-sum(ledger.data[i]['spend'].values())==env.state[i].reward
    row={'seed':seed,'old_seat':seat,'cash':[s.reward for s in env.state], 'ledger':ledger.data,'daily':daily,'events':events}
    (OUT/'audit'/f'{seed}-{seat}.json').write_text(json.dumps(row))
    if seat==0:(OUT/'audit'/f'replay-{seed}.json').write_text(json.dumps(env.toJSON()))
    return {'seed':seed,'old_seat':seat,'gap':env.state[1-seat].reward-env.state[seat].reward}

def main():
    (OUT/'audit').mkdir(parents=True,exist_ok=True)
    jobs=[(s,i) for s in range(110000,110004) for i in (0,1)]
    with ProcessPoolExecutor(max_workers=4,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run,j) for j in jobs if not (OUT/'audit'/f'{j[0]}-{j[1]}.json').exists()]):print(f.result(),flush=True)
    rows=[json.loads((OUT/'audit'/f'{s}-{i}.json').read_text()) for s,i in jobs]
    products=Counter();spend=Counter();volume=Counter();price=Counter();phases=Counter()
    for r in rows:
        a,b=r['ledger'][r['old_seat']],r['ledger'][1-r['old_seat']]
        for p in set(a['revenue'])|set(b['revenue']):
            qa,qb=a['sold_units'].get(p,0),b['sold_units'].get(p,0);ra,rb=a['revenue'].get(p,0),b['revenue'].get(p,0)
            pa=ra/qa if qa else rb/qb if qb else 0;pb=rb/qb if qb else pa
            products[p]+=rb-ra;volume[p]+=(qb-qa)*(pa+pb)/2;price[p]+=(pb-pa)*(qa+qb)/2
        for k in set(a['spend'])|set(b['spend']):spend[k]+=b['spend'].get(k,0)-a['spend'].get(k,0)
        for snap in r['daily']:
            if snap['step']%144==0:phases[snap['step']]+=snap['cash'][1-r['old_seat']]-snap['cash'][r['old_seat']]
    result={'games':len(rows),'mean_gap':sum(r['cash'][1-r['old_seat']]-r['cash'][r['old_seat']] for r in rows)/len(rows),
      'revenue_gap':{k:v/len(rows) for k,v in products.items()},'volume_component':{k:v/len(rows) for k,v in volume.items()},
      'price_component':{k:v/len(rows) for k,v in price.items()},'spend_gap':{k:v/len(rows) for k,v in spend.items()},
      'cash_gap_at_turn':{k:v/len(rows) for k,v in phases.items()}}
    assert abs(sum(result['revenue_gap'].values())-sum(result['spend_gap'].values())-result['mean_gap'])<1e-7
    (OUT/'advantage_summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

if __name__=='__main__':main()
