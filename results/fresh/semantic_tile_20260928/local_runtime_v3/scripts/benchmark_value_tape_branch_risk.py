"""Is the known losing switch bad in expectation or in its realized future?

The route was selected before these 16 independent future-shop draws. Both
policies face the same shop sequence and a fully responsive V56 in each pair.
This is a conditional diagnostic of one checkpoint, not a general holdout.
"""
from concurrent.futures import ProcessPoolExecutor,as_completed
from copy import deepcopy
import json
import os
import random
import statistics
import time
import traceback

import research_labour_profit as R
import value_tape_search as V
from benchmark_value_tape_search import OPPONENT

OUT=V.ROOT/'results/fresh/value_tape_followup_20260923/branch_risk'
SEED=1329978515


def worker(job):
    index,shops,route=job;target=OUT/f'{index}-{route}.json';started=time.perf_counter()
    with target.with_suffix('.log').open('w',encoding='utf-8') as log:
        saved=[os.dup(1),os.dup(2)]
        try:
            os.dup2(log.fileno(),1);os.dup2(log.fileno(),2)
            from kaggle_environments.agent import get_last_callable
            E=R.engine();ours=V.fresh_agent();rival=get_last_callable(OPPONENT.read_text(encoding='utf-8'),path=str(OPPONENT))
            game=dict(seed=SEED,seat=0,episode=0,shops=[shops[:min(8,d//3)] for d in range(31)])
            with R.Simulator(game) as sim:
                state=deepcopy(sim.initial)
                for t in range(719):
                    sim.t=t;sim.seats={id(f):s for s,f in enumerate(state[0].observation.farms)}
                    for s in state:s.observation.step=t
                    if t%24==0:state[0].observation.town['unlocked_shops'][:]=game['shops'][t//24]
                    if t==360 and route is not None:
                        chassis=ours.__globals__['_MGT_IMPL'].chassis;parent=chassis.router
                        def committed(obs,step,memory):
                            if step<432:memory['route']=route;return route
                            return parent(obs,step,memory)
                        chassis.router=committed
                    state[0].action=ours(deepcopy(state[0].observation));state[1].action=rival(deepcopy(state[1].observation))
                    E.interpreter(state,sim.env)
                cash=[s.reward for s in state]
                for s in range(2):
                    econ=R.economic(sim.events,s)
                    assert 3000+sum(econ['revenue'].values())-sum(econ['spend'].values())==cash[s]
            row=dict(index=index,route=route,shops=shops,cash=cash,margin=cash[0]-cash[1],completed=True,ledger_verified=True)
        except Exception:row=dict(index=index,route=route,completed=False,error=traceback.format_exc())
        finally:
            os.dup2(saved[0],1);os.dup2(saved[1],2)
            for fd in saved:os.close(fd)
    row['seconds']=time.perf_counter()-started;target.write_text(json.dumps(row,indent=2),encoding='utf-8')
    return row


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    prefix=['SMOOTHIE_SHOP','PIZZA_SHOP','PET_CAFE','YARN_STORE','ICE_CREAM_SHOP']
    types_=sorted(('BAKERY','PIZZA_SHOP','BRUNCH_SPOT','YARN_STORE','ICE_CREAM_SHOP','PET_CAFE','SMOOTHIE_SHOP','FARMERS_MARKET'))
    rng=random.Random(29531709);worlds=[prefix+[rng.choice(types_) for _ in range(3)] for _ in range(16)]
    design=dict(seed=SEED,route=196,worlds=worlds,sampling_seed=29531709,protocol=__doc__)
    (OUT/'design.json').write_text(json.dumps(design,indent=2),encoding='utf-8')
    rows=[]
    with ProcessPoolExecutor(max_workers=3,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(worker,(i,shops,route)) for i,shops in enumerate(worlds) for route in (None,196)]):
            row=f.result();rows.append(row)
            if len(rows)%4==0 or not row['completed']:print(json.dumps(dict(done=len(rows),latest=row)),flush=True)
    assert all(r['completed'] for r in rows)
    lookup={(r['index'],r['route']):r for r in rows};pairs=[]
    for i in range(16):
        a,b=lookup[i,None],lookup[i,196]
        pairs.append(dict(index=i,shops=worlds[i],baseline_margin=a['margin'],candidate_margin=b['margin'],
            margin_delta=b['margin']-a['margin'],cash_delta=b['cash'][0]-a['cash'][0],rival_delta=b['cash'][1]-a['cash'][1]))
    vals=[r['margin_delta'] for r in pairs]
    result=dict(pairs=pairs,mean=statistics.mean(vals),minimum=min(vals),maximum=max(vals),positive=sum(x>0 for x in vals),negative=sum(x<0 for x in vals))
    (OUT/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='pairs'}),flush=True)


if __name__=='__main__':main()
