"""Diagnostic decomposition of forecast error, explicitly including oracles.

Oracle inputs are evaluation-only. A policy must receive only `observation`
and `memory`, never this module's future shops, rival trades, or game seed.
The original value_tape_search implementation and frozen results stay intact.
"""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
from copy import deepcopy
import gzip
import json
import os
import pickle
import time
import traceback

import research_labour_profit as R
import value_tape_search as V
from benchmark_value_tape_search import OPPONENT
from probe_value_tape_search import load,checkpoint

OUT=V.ROOT/'results/fresh/value_tape_followup_20260923'
CASES={'wool':dict(kind='historical',episode=111269605,day=15,route=0),
       'false_positive':dict(kind='live',seed=1329978515,day=15,route=196)}


def context(name):
    path=OUT/f'{name}-context.pkl.gz'
    R.engine()
    if path.exists():
        with gzip.open(path,'rb') as f:return pickle.load(f)
    spec=CASES[name]
    E=R.engine()
    if spec['kind']=='historical':
        game,pair=load(spec['episode'])
        seat=game['seat']
        state,memory=checkpoint(game,pair,spec['day'])
        obs=deepcopy(state[seat].observation)
        with R.Simulator(game) as sim:
            result=sim.run(sim.initial,0,719,pair)
        assert result['money']==game['rewards']
        events=result['events']
        shops={d:game['shops'][d] for d in range(30)}
    else:
        seat=0
        base=json.loads((V.ROOT/f"results/fresh/value_tape_search_20260923/live/{spec['seed']}-0-baseline.json").read_text())
        shops={d:base['shops'][:min(8,d//3)] for d in range(30)}
        game=dict(seed=spec['seed'],seat=0,episode=0,shops=[shops.get(d,shops[29]) for d in range(31)])
        ours=V.fresh_agent()
        from kaggle_environments.agent import get_last_callable
        rival=get_last_callable(OPPONENT.read_text(encoding='utf-8'),path=str(OPPONENT))
        with R.Simulator(game) as sim:
            state=deepcopy(sim.initial)
            for t in range(719):
                sim.t=t
                sim.seats={id(f):s for s,f in enumerate(state[0].observation.farms)}
                for s in state:s.observation.step=t
                if t%24==0:state[0].observation.town.unlocked_shops[:]=shops[t//24]
                if t==24*spec['day']:
                    obs,memory=deepcopy(state[0].observation),V.memory_of(ours)
                state[0].action=ours(deepcopy(state[0].observation))
                state[1].action=rival(deepcopy(state[1].observation))
                E.interpreter(state,sim.env)
            events=list(sim.events)
            assert [s.reward for s in state]==[base['cash'],base['rival_cash']]
    daily={d:Counter() for d in range(spec['day'],30)}
    hourly={t:Counter() for t in range(spec['day']*24,719)}
    for t,s,op,p,price in events:
        if s==1-seat and t>=24*spec['day'] and op in ('SELL','BUY_PRODUCT'):
            n=1 if op=='SELL' else -1
            daily[t//24][p]+=n
            hourly[t][p]+=n
    data=dict(observation=obs,memory=memory,spec=spec,shops=shops,daily=daily,hourly=hourly)
    with gzip.open(path,'wb') as f:pickle.dump(data,f)
    return data


def worker(name):
    target=OUT/f'{name}-components.json'
    started=time.perf_counter()
    with target.with_suffix('.log').open('w',encoding='utf-8') as log:
        saved=[os.dup(1),os.dup(2)]
        try:
            os.dup2(log.fileno(),1);os.dup2(log.fileno(),2)
            ctx=context(name)
            obs,memory=ctx['observation'],ctx['memory']
            route=ctx['spec']['route']
            original_shops,original_schedule=V.future_shops,V.rival_schedule
            rows=[]
            for mode in ('sampled','oracle_shops','oracle_shops_and_daily_flow'):
                V.future_shops=(original_shops if mode=='sampled' else lambda obs,seed:deepcopy(ctx['shops']))
                V.rival_schedule=(original_schedule if mode!='oracle_shops_and_daily_flow' else lambda obs,scale:deepcopy(ctx['daily']))
                scenarios=V.SCENARIOS if mode!='oracle_shops_and_daily_flow' else ((39461,1.0),)
                for scenario in scenarios:
                    base=V.rollout(obs,memory,None,scenario)
                    changed=V.rollout(obs,memory,route,scenario)
                    rows.append(dict(mode=mode,scenario=scenario,margin_delta=changed['margin_gain']-base['margin_gain'],
                        own_delta=changed['cash_gain']-base['cash_gain'],rival_delta=changed['rival_gain']-base['rival_gain'],
                        base=base,candidate=changed))
            V.future_shops,V.rival_schedule=original_shops,original_schedule
            projected=original_schedule(obs,1.0)
            expected=sum((Counter(v) for v in projected.values()),Counter())
            actual=sum((Counter(v) for v in ctx['daily'].values()),Counter())
            # Counter addition drops negatives, so retain signed net flow here.
            expected={p:sum(v.get(p,0) for v in projected.values()) for p in V.isolated_engine().PRODUCTS}
            actual={p:sum(v.get(p,0) for v in ctx['daily'].values()) for p in V.isolated_engine().PRODUCTS}
            result=dict(name=name,completed=True,spec=ctx['spec'],rows=rows,
                        projected_rival_net_sales=expected,actual_rival_net_sales=actual,
                        limitation='Oracle shop and flow rows use future data solely to diagnose prediction error; they are not policy decisions.')
        except Exception:
            result=dict(name=name,completed=False,error=traceback.format_exc())
        finally:
            os.dup2(saved[0],1);os.dup2(saved[1],2)
            for fd in saved:os.close(fd)
    result['seconds']=time.perf_counter()-started
    target.write_text(json.dumps(result,indent=2),encoding='utf-8')
    return {k:result[k] for k in result if k not in ('rows',)}|{'rows':[{k:r[k] for k in ('mode','scenario','margin_delta','own_delta','rival_delta')} for r in result.get('rows',[])]}


if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    with ProcessPoolExecutor(max_workers=2,max_tasks_per_child=1) as pool:
        for future in as_completed([pool.submit(worker,name) for name in CASES]):
            print(json.dumps(future.result(),indent=2),flush=True)
