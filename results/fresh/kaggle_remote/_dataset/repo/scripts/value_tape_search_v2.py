"""Economic tape search with public-cohort rival sale trajectories.

V1 is retained unchanged. Decisions see only our observation and our own agent
memory. Eight stratified shop futures and different older rival continuations
are common random worlds for paired candidate comparisons.
"""
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import statistics
import time

import research_labour_profit as R
import value_tape_search as V
import rival_trajectory_model as M
from test_labour_selfplay import project_input

PLANNER_SHA256=sha256(Path(__file__).read_bytes()).hexdigest()


def rollout(obs,memory,route,world,until=None):
    E=V.isolated_engine()
    start,seat=int(obs['step']),int(obs['player']);day=start//24
    until=min(719,(day+3)*24) if until is None else until
    entry=V.fresh_agent(memory,route,until)
    public,state=project_input(obs);env=public.env
    initial_money=[f['money'] for f in state[0].observation.farms]
    state[0].observation.farms[1-seat]['money']=10_000_000
    surviving,output,feeds,failures=None,Counter(),Counter(),Counter()
    starting_animals={(x,y,tile['animal'],tile['placed_day'])
        for y,row in enumerate(obs['farms'][seat]['tiles']) for x,tile in enumerate(row)
        if isinstance(tile,dict) and tile.get('animal')}
    events=[]
    old_commit,old_unit,old_hire=E._commit_unit,E._apply_unit_action,E._do_hire
    t=start
    def commit(op,p,price,farm,private,market,cap=100):
        ok=old_commit(op,p,price,farm,private,market,cap)
        if ok:events.append((t,0 if farm is state[0].observation.farms[seat] else 1,op,p,price))
        elif farm is state[0].observation.farms[seat] and op!='SELL':failures[op]+=1
        return ok
    def unit(farm,private,u,cmd,*args,**kwargs):
        ours=farm is state[0].observation.farms[seat]
        pos=E._farmer_position(farm,u)
        before=dict(private['inventories'][u]) if ours and pos is not None else None
        tile=farm['tiles'][pos[1]][pos[0]] if ours and pos is not None else None
        retained=(isinstance(tile,dict) and tile.get('animal') and (*pos,tile['animal'],tile['placed_day']) in starting_animals)
        result=old_unit(farm,private,u,cmd,*args,**kwargs)
        if before is not None and cmd:
            after=private['inventories'][u]
            if cmd[0] in ('HARVEST','COLLECT_FERTILIZER'):
                output.update({p:n-before.get(p,0) for p,n in after.items() if n>before.get(p,0)})
            if cmd[0]=='FEED' and retained and before.get('WHEAT',0)>after.get('WHEAT',0) and t<until:
                feeds[(t//24,*pos)]+=1
        return result
    def hire(farm,private,size,*args,**kwargs):
        old=len(farm['hands']);result=old_hire(farm,private,size,*args,**kwargs)
        if farm is state[0].observation.farms[seat] and old==len(farm['hands']):failures['HIRE']+=1
        return result
    E._commit_unit,E._apply_unit_action,E._do_hire=commit,unit,hire
    try:
        for t in range(start,719):
            d,h=divmod(t,24)
            for s in state:s.observation.step=t
            if h==0:
                state[0].observation.town['unlocked_shops'][:]=world['shops'][d]
                predicted=world['farms'][d]
                rival_farm=state[0].observation.farms[1-seat]
                rival_farm['tiles']=deepcopy(predicted['tiles'])
                rival_farm['unlocked_quadrants']=deepcopy(predicted['unlocked_quadrants'])
            state[seat].action=entry(deepcopy(state[seat].observation))
            flows=world['hourly'].get(t,{})
            private=state[1-seat].observation.private
            private['shed']={p:n for p,n in flows.items() if n>0}
            state[1-seat].action={'farmer':['PASS'],'hands':[],
                'market':[['SELL' if n>0 else 'BUY_PRODUCT',p,abs(n)] for p,n in flows.items() if n]}
            E.interpreter(state,env)
            if t+1==until:surviving=V.asset_keys(state[0].observation.farms[seat])
    finally:E._commit_unit,E._apply_unit_action,E._do_hire=old_commit,old_unit,old_hire
    own=state[0].observation.farms[seat]['money']-initial_money[seat]
    rival=state[0].observation.farms[1-seat]['money']-10_000_000
    revenues=[Counter(),Counter()]
    for _,s,op,p,price in events:
        if op=='SELL':revenues[s][p]+=price
    return dict(cash_gain=own,rival_gain=rival,margin_gain=own-rival,
        output=dict(output),failures=dict(failures),survives=sorted(surviving or ()),
        feeds={str(k):v for k,v in feeds.items()},revenue=dict(revenues[0]),rival_revenue=dict(revenues[1]))


def assess(candidate,predictions,base,existing):
    deltas=[p['margin_gain']-b['margin_gain'] for p,b in zip(predictions,base)]
    cash=[p['cash_gain']-b['cash_gain'] for p,b in zip(predictions,base)]
    failures=[]
    for i,(p,b) in enumerate(zip(predictions,base)):
        protected=existing & set(map(tuple,b['survives']))
        missing=protected-set(map(tuple,p['survives']))
        if missing:failures.append(dict(scenario=i,assets=sorted(missing)))
        extra=Counter(p['failures'])-Counter(b['failures'])
        if extra.get('HIRE',0):failures.append(dict(scenario=i,extra_failed_hires=extra['HIRE']))
    mean=statistics.mean(deltas);score=mean-.5*statistics.pstdev(deltas)
    return dict(candidate,predictions=predictions,margin_deltas=deltas,cash_deltas=cash,
        mean_margin=mean,risk_score=score,minimum_margin=min(deltas),protection_failures=failures,
        admitted=not failures and min(deltas)>=-500 and statistics.mean(cash)>0 and score>350)


def choose(obs,memory,*,count=7):
    started=time.perf_counter()
    candidates=V.shortlist(obs,memory,count)
    existing=V.asset_keys(obs['farms'][int(obs['player'])])
    worlds=[M.world(obs,i) for i in range(8)]
    predictions={}
    for candidate in candidates:
        route=candidate['route']
        predictions[route]=[rollout(obs,memory,route,w) for w in worlds[:4]]
    base=predictions[None]
    screen=[assess(c,predictions[c['route']],base,existing) for c in candidates]
    # Spend the extra worlds on at most two economically promising survivors.
    finalists=sorted((r for r in screen if r['route'] is not None and not r['protection_failures']
        and r['risk_score']>0 and statistics.mean(r['cash_deltas'])>0),key=lambda r:r['risk_score'],reverse=True)[:2]
    active={None,*[r['route'] for r in finalists]}
    if finalists:
        for route in active:predictions[route].extend(rollout(obs,memory,route,w) for w in worlds[4:])
    rows=[]
    for c in candidates:
        route=c['route'];pred=predictions[route]
        row=assess(c,pred,predictions[None][:len(pred)],existing)
        row['fully_evaluated']=len(pred)==8
        row['admitted']=row['admitted'] and row['fully_evaluated']
        rows.append(row)
    allowed=[r for r in rows if r['admitted']]
    chosen=max(allowed,key=lambda r:r['risk_score']) if allowed else rows[0]
    decision=dict(day=int(obs['day']),selected=chosen['route'],selected_episode=chosen['episode'],
        candidates=rows,worlds=[dict(index=w['index'],shops=w['shops'][29],donor=w['donor']) for w in worlds],
        seconds=time.perf_counter()-started,until=min(719,(int(obs['day'])+3)*24),
        source_sha256=V.SOURCE_SHA256,planner_sha256=PLANNER_SHA256,model_sha256=M.MODEL_SHA256,
        input_sha256=sha256(json.dumps(V.canonical([obs,memory]),sort_keys=True,default=str).encode()).hexdigest(),
        protocol='Public-only; older training split rival sales, cohort quantity correction, eight stratified future shops; paired official own-farm rollouts; cohort survival and competitive margin; commit three days.')
    return chosen['route'],decision
