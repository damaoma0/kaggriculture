"""Official market stress sweep and paired, first-shop-stratified regressions."""
from copy import deepcopy
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
from statistics import mean
import json,random
from market_corpus import ROOT,load
from diagnose_bigangel import OUT,ARCHIVE

FIX=ROOT/'agents/v45_opening_capital_fixed.py'

def sweep():
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    env=make('kaggriculture');env.reset(2);initial=deepcopy(env.state)
    rows=[]
    for buy in range(101):
        for sell in range(buy+1):
            states=deepcopy(initial)
            states[0].action={'market':[['BUY_PRODUCT','WHEAT',5]]}
            states[1].action={'market':[['BUY_PRODUCT','WHEAT',buy],['SELL','WHEAT',sell]]}
            E._process_market(states,env)
            money=states[0].observation.farms[0]['money']
            assert states[0].observation.private.shed['WHEAT']==5
            # Five hires = 12; 2 cows + 2 sheep = 1800; 12 melon + 7 wheat seeds = 1030.
            rows.append(money-2842)
    return dict(cases=len(rows),minimum_cash_after_complete_day1=min(rows),maximum_cash_after_complete_day1=max(rows),scope='Opponent one initial wheat buy (0..100) followed by sale (0..bought); default rules. Not arbitrary order queues.')

def run(job):
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    seed,seat,rival_name,policy=job
    path=FIX if policy=='fixed' else ARCHIVE
    own=get_last_callable(path.read_text(encoding='utf-8'),path=str(path))
    named=load('capital_parity',FIX) if policy=='fixed' else None
    rival=load('capital_rival',ROOT/'data/router_refresh_20260916/v45/main.py')
    env=make('kaggriculture',configuration={'seed':seed,'episodeSteps':720})
    schedule=random.Random(seed).choices(sorted(E.SHOPS),k=8);schedule[0]=sorted(E.SHOPS)[seed-153000]
    end=E._end_of_day
    def locked(state,environment,day):
        end(state,environment,day);shops=state[0].observation.town.unlocked_shops;shops[:]=schedule[:len(shops)]
    E._end_of_day=locked
    count=[0];day1={}
    def ours(obs):
        if obs['step']==24:
            f=obs['farms'][seat]
            day1.update(cash=f['money'],crops=dict(Counter(v['crop'] for row in f['tiles'] for v in row if isinstance(v,dict) and v.get('crop'))))
        a=own(deepcopy(obs))
        if named:
            assert a==named.agent(deepcopy(obs)),obs['step']
            count[0]+=1
        return a
    def theirs(obs):
        a=rival.agent(obs)
        if rival_name=='small_flip':
            if obs['step']==0:a=dict(a,market=[['BUY_PRODUCT','WHEAT',14],['SELL','WHEAT',10]])
            elif obs['step']==1:a=dict(a,market=[['BUY_PRODUCT','WHEAT',1]]+a['market'][2:])
        return a
    players=[None,None];players[seat]=ours;players[1-seat]=theirs
    try:env.run(players)
    finally:E._end_of_day=end
    assert len(env.steps)==720 and all(s.status=='DONE' for s in env.state)
    if named:assert count[0]==719 and day1['crops']=={'WHEAT':7,'MELON':12}
    row=dict(seed=seed,seat=seat,opponent=rival_name,policy=policy,cash=env.state[seat].reward,opponent_cash=env.state[1-seat].reward,day1=day1,parity_actions=count[0],shops=schedule)
    (OUT/'regressions'/('-'.join(map(str,job))+'.json')).write_text(json.dumps(row,indent=2),encoding='utf-8')
    return row

if __name__=='__main__':
    (OUT/'regressions').mkdir(exist_ok=True)
    stress=sweep();print('stress',json.dumps(stress),flush=True)
    jobs=[(s,(s-153000)%2,r,p) for s in range(153000,153008) for r in ('v45','small_flip') for p in ('original','fixed')]
    rows=[]
    with ProcessPoolExecutor(max_workers=4,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run,j) for j in jobs]):
            row=f.result();rows.append(row);print(json.dumps(row),flush=True)
    base={(r['seed'],r['opponent']):r for r in rows if r['policy']=='original'}
    pairs=[]
    for r in rows:
        if r['policy']=='fixed':
            b=base[r['seed'],r['opponent']]
            pairs.append(dict(seed=r['seed'],opponent=r['opponent'],cash_delta=r['cash']-b['cash'],margin_delta=(r['cash']-r['opponent_cash'])-(b['cash']-b['opponent_cash'])))
    summary=dict(stress=stress,games=len(rows),pairs=pairs,mean_margin_delta=mean(r['margin_delta'] for r in pairs),mean_cash_delta=mean(r['cash_delta'] for r in pairs),positive_pairs=sum(r['margin_delta']>0 for r in pairs),wins={p:sum(r['cash']>r['opponent_cash'] for r in rows if r['policy']==p) for p in ('original','fixed')})
    (OUT/'verification.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary),flush=True)
