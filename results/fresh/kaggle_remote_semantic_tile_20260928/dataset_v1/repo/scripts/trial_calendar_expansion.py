"""Execute a newly generated ten-plot crop calendar beside the V45 base farm.

Research-only adapter: starts at day18, requests dedicated workers after native
early hiring, and preserves native worker indices. No submission is produced.
"""
from copy import deepcopy
from concurrent.futures import ProcessPoolExecutor,as_completed
import json,random,time
from crop_plan_evaluator import calendar,tours,HOME,distance
from research_fourth_quadrant import ROOT,OUT,BASE,CONFIGS,PATHS,configure,load,Ledger

def make_agent(parent,crop):
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    g=parent.__globals__;days={r['day']:r for r in calendar(crop,18,True)}
    state=dict(committed=False,workers={},day=-1,pending=None,credit=0,requested_day=-1)
    stats=dict(committed=0,hire_requests=0,hire_shortfalls=0,deadline_failures=0,infeasible_calendar=0,plant_requests=0,water_requests=0,harvest_requests=0,harvested_units=0,seed_requests=0,fertilizer_requests=0,plans={},budget_declines=0)
    shadow=g['_shadow_terminal']
    g['_shadow_terminal']=lambda obs,config:None if state['committed'] else shadow(obs,config)
    def walk(pos,target):
        x,y=pos;tx,ty=target
        return [['EAST']]*max(0,tx-x)+[['WEST']]*max(0,x-tx)+[['SOUTH']]*max(0,ty-y)+[['NORTH']]*max(0,y-ty)
    def agent(obs):
        action=parent(obs);step=int(obs['step']);day,hour=divmod(step,24)
        if day<18:return action
        f=obs['farms'][obs['player']];p=obs['private']
        if day!=state['day']:state.update(day=day,workers={},last={})
        for actor,prev in state['last'].items():
            if actor<len(p['inventories']) and prev[0]=='HARVEST':stats['harvested_units']+=max(0,p['inventories'][actor].get(crop,0)-prev[1])
        state['last']={}
        if state['pending']:
            pending=state.pop('pending');state['pending']=None
            if 'SE' not in f['unlocked_quadrants'] or len(f['hands'])<pending['first']+len(pending['tours'])-1:
                stats['hire_shortfalls']+=len(pending['tours'])
            else:
                for j,tour in enumerate(pending['tours']):
                    actor=pending['first']+j;pos=tuple(f['hands'][actor-1]);seq=[];row=days[day]
                    if row['fertilizer_per_tile']:seq.append(['PICKUP','FERTILIZER',len(tour['targets'])*row['fertilizer_per_tile']])
                    for target in tour['targets']:seq+=walk(pos,target)+deepcopy(row['commands']);pos=target
                    if row['harvest_per_tile']:
                        home=min(HOME,key=lambda h:distance(pos,h));seq+=walk(pos,home)+[['DROP']]
                    assert len(seq)<=pending['available']
                    state['workers'][actor]=seq
        if 3<=hour<=6 and state['requested_day']!=day and (state['committed'] or day==18):
            row=days[day];initial=not state['committed']
            valid=not initial or set(f['unlocked_quadrants'])=={'NW','NE','SW'}
            native=g['_IMPL'].chassis.players[int(obs['player'])]
            planned=g['_v219_native_day'](native,day)
            valid &= not any(o and o[0]=='HIRE' for a in planned[hour+1:] for o in a.get('market',[]))
            if valid and row['commands']:
                available=23-hour-int(day==29)
                try:paths=tours(row['commands'],available)
                except ValueError:
                    stats['infeasible_calendar']+=1
                    return action
                parent_hires=sum(o and o[0]=='HIRE' for o in action.get('market',[]));n=len(paths)
                extra=[['BUY_LAND']] if initial else []
                seeds=10*row['seeds_per_tile'];fert=10*row['fertilizer_per_tile']
                if seeds:extra.append(['BUY_SEED',crop,seeds])
                if fert:extra.append(['BUY_PRODUCT','FERTILIZER',fert])
                extra+=[['HIRE'] for _ in paths]
                hirecost=sum(E._fib(f['hires_today']+parent_hires+j) for j in range(n))
                cost=4000*initial+seeds*E.CROPS[crop]['seed']+fert*(obs['market']['prices']['FERTILIZER']+5)+hirecost
                if len(action['market'])+len(extra)<=10 and f['money']>=cost+3000:
                    action=deepcopy(action);action['market']+=extra
                    state['pending']={'first':len(f['hands'])+parent_hires+1,'tours':paths,'available':available};state['committed']=True;state['requested_day']=day
                    stats['committed']=1;stats['hire_requests']+=n;stats['seed_requests']+=seeds;stats['fertilizer_requests']+=fert;stats['plans'][day]=dict(workers=n,extra_hire_cost=hirecost)
                else:stats['budget_declines']+=1
            elif not valid:stats['deadline_failures']+=1
        if state['workers']:
            commands=[action.get('farmer',['PASS']),*action.get('hands',[])];commands += [['PASS'] for _ in range(len(f['hands'])+1-len(commands))]
            for actor,queue in state['workers'].items():
                cmd=queue.pop(0) if queue else ['PASS'];commands[actor]=cmd
                state['last'][actor]=(cmd[0],p['inventories'][actor].get(crop,0))
                key={'PLANT':'plant_requests','WATER':'water_requests','HARVEST':'harvest_requests'}.get(cmd[0])
                if key:stats[key]+=1
            action=deepcopy(action);action['farmer'],action['hands']=commands[0],commands[1:]
        if state['committed']:
            # Only liquidate output deposited by the added workers; preserve feed
            # and stock reserved by the original farm's own market plan.
            view=g['FarmView'](obs);after=g['projected_shed'](action,view).get(crop,0)
            without=deepcopy(action)
            for actor in state['workers']:
                if without['hands'][actor-1][0]=='DROP':without['hands'][actor-1]=['PASS']
            before=g['projected_shed'](without,view).get(crop,0)
            state['credit']+=max(0,after-before)
            scheduled=sum(int(o[2]) for o in action['market'] if o[:2]==['SELL',crop])
            state['credit']=max(0,state['credit']-max(0,scheduled-before))
            amount=min(state['credit'],max(0,after-scheduled))
            if amount and len(action['market'])<10:
                action=deepcopy(action);action['market'].append(['SELL',crop,amount]);state['credit']-=amount
        return action
    return agent,stats

def run(job):
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    seed,config,seat,opponent,crop=job
    own,stats=make_agent(configure(get_last_callable(BASE.read_text(encoding='utf-8'),path=str(BASE)),'none'),crop)
    rival=load('calendar_rival',PATHS[opponent]);env=make('kaggriculture',configuration={'seed':seed,'episodeSteps':720})
    schedule=CONFIGS[config]+random.Random(seed^0xFA19).choices(sorted(E.SHOPS),k=2);end=E._end_of_day
    def locked(state,environment,day):
        end(state,environment,day);shops=state[0].observation.town.unlocked_shops;shops[:]=schedule[:len(shops)]
    E._end_of_day=locked;players=[None,None];players[seat]=own;players[1-seat]=rival.agent
    try:
        with Ledger(E) as ledger:env.run(players)
    finally:E._end_of_day=end
    assert len(env.steps)==720 and all(s.status=='DONE' for s in env.state)
    assert all(isinstance(s[seat].action,dict) for s in env.steps[1:]),'Agent failed to return an action'
    for i in (0,1):assert 3000+sum(ledger.data[i]['revenue'].values())-sum(ledger.data[i]['spend'].values())==env.state[i].reward
    baseline=json.loads((OUT/'games'/f'discovery-{seed}-{config}-{seat}-{opponent}-none.json').read_text(encoding='utf-8'))
    cash=env.state[seat].reward;margin=cash-env.state[1-seat].reward
    row=dict(adapter_version=3,seed=seed,configuration=config,seat=seat,opponent=opponent,crop=crop,cash=cash,margin=margin,cash_delta=cash-baseline['cash'],margin_delta=margin-baseline['margin'],stats=stats,ledger=ledger.data)
    (OUT/'calendar_games'/('-'.join(map(str,job))+'.json')).write_text(json.dumps(row,indent=2),encoding='utf-8');print(json.dumps(row),flush=True)

if __name__=='__main__':
    (OUT/'calendar_games').mkdir(exist_ok=True)
    jobs=[(seed,config,s,o,crop) for seed,config,crop in [(155009,'carrot','CARROT'),(155003,'tomato3','TOMATO'),(155000,'no_tomato','WHEAT')] for s in (0,1) for o in ('v45','twocoins')]
    with ProcessPoolExecutor(max_workers=2,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run,j) for j in jobs]):f.result()
