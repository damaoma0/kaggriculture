"""Offline attribution of route 47: known shops, rival supply, weeds and costs.

All future observations in this script are oracle diagnostics only. Nothing is
imported by the playing challenger. Replay both actual live-game action streams
before supplying progressively more known information to the forecast model.
"""
from collections import Counter,defaultdict
from copy import deepcopy
import sys
import run_tape_margin_study as S

sys.path[:0]=[str(S.OUT/'payload/scripts'),str(S.OUT/'payload/vendor')]
import value_tape_repair_r1 as N

def replay(arm):
    case='fresh-12-v56'
    reference=S.read(S.FROZEN/'arms'/f'{case}-{arm}.json')
    actions=S.read(S.FROZEN/'actions'/f'{case}-{arm}.json')
    spec=reference['spec'];seat=spec['seat'];opp=1-seat
    game=dict(seed=spec['seed'],seat=seat,shops=[spec['shops'][:min(8,d//3)] for d in range(31)])
    entry=N.V.fresh_agent() if arm=='baseline' else None
    farms={};obs=memory=None
    with N.V.R.Simulator(game) as sim:
        state=deepcopy(sim.initial)
        for t in range(719):
            sim.t=t;sim.seats={id(f):s for s,f in enumerate(state[0].observation.farms)}
            for s in state:s.observation.step=t
            if t%24==0:
                state[0].observation.town['unlocked_shops'][:]=game['shops'][t//24]
                farms[t//24]=deepcopy(state[0].observation.farms[opp])
            if entry and t==288:obs=deepcopy(state[seat].observation);memory=N.V.memory_of(entry)
            if entry and t<288:assert entry(deepcopy(state[seat].observation))==actions[seat][t]
            for s in range(2):state[s].action=actions[s][t]
            N.V.R.engine().interpreter(state,sim.env)
        assert [s.reward for s in state]==reference['cash_by_seat']
        hourly=defaultdict(Counter);other_cost=0;directions=defaultdict(set);orders=defaultdict(list)
        for t,s,op,p,value in sim.events:
            if t<288 or s!=opp:continue
            if op in ('SELL','BUY_PRODUCT'):
                hourly[t][p]+=1 if op=='SELL' else -1;directions[(t,p)].add(op)
                if orders[t] and orders[t][-1][:2]==[op,p]:orders[t][-1][2]+=1
                else:orders[t].append([op,p,1])
            elif op!='SELL':other_cost+=value
        round_trips=[list(k) for k,v in directions.items() if len(v)>1]
        assert all(len(v)<=10 for v in orders.values())
    return dict(obs=obs,memory=memory,farms=farms,hourly={t:dict(v) for t,v in hourly.items()},
                shops={d:game['shops'][d] for d in range(12,30)},reference=reference,
                other_rival_cost=other_cost,actions=actions,orders=dict(orders),round_trips=round_trips)

def main():
    base,changed=replay('baseline'),replay('candidate')
    obs,memory=base['obs'],base['memory'];seat=obs['player'];opp=1-seat
    runtime=N.runtime();runtime.prepare(obs)
    runtime.world_batch._world.__globals__['M'].scenario_shops=lambda o,i:base['shops']
    results=[]
    def world(source):return dict(index=0,shops=source['shops'],farms=source['farms'],hourly=source['hourly'],donor={})
    def rollout(route,w,weed_source=None,ordered_source=None):
        E=N.V.isolated_engine();old_spawn=E._spawn_weeds;old_interpreter=E.interpreter;calls=0;collisions=[];filled=Counter()
        def weeds(farm,size,chance,rng):
            nonlocal calls
            day=12+calls//2;s=calls%2;calls+=1
            for x,y in weed_source['reference']['spawns'][s].get(str(day),[]):
                if farm['tiles'][y][x] is None:farm['tiles'][y][x]={'kind':'WEED'}
                else:collisions.append((s,day,x,y))
        if weed_source:E._spawn_weeds=weeds
        def ordered(state,env):
            t=state[0].observation.step;commands=ordered_source['orders'].get(t,[])
            balance=Counter();needed=Counter()
            for operation,p,n in commands:
                balance[p]+=n if operation=='BUY_PRODUCT' else -n
                needed[p]=max(needed[p],-balance[p])
            private=state[opp].observation.private
            private['shed']={p:n for p,n in needed.items() if n>0}
            state[opp].action={'farmer':['PASS'],'hands':[],'market':deepcopy(commands)}
            original_commit=E._commit_unit
            def track(operation,p,price,farm,private,market,cap=100):
                ok=original_commit(operation,p,price,farm,private,market,cap)
                if ok and farm is state[0].observation.farms[opp] and operation in ('SELL','BUY_PRODUCT'):
                    filled[(t,operation,p)]+=1
                return ok
            E._commit_unit=track
            try:return old_interpreter(state,env)
            finally:E._commit_unit=original_commit
        if ordered_source:E.interpreter=ordered
        try:p=runtime.rollout(obs,memory,route,w,360)
        finally:E._spawn_weeds=old_spawn;E.interpreter=old_interpreter
        p['oracle_weed_collisions']=collisions
        if ordered_source:
            expected=Counter()
            for t,commands in ordered_source['orders'].items():
                for operation,item,n in commands:expected[(t,operation,item)]+=n
            p['oracle_ordered_trade_shortfall']=sum((expected-filled).values())
            p['oracle_ordered_trade_excess']=sum((filled-expected).values())
        return p
    def add(label,a,b,adjust=False):
        own=b['cash_gain']-a['cash_gain'];rival=b['rival_gain']-a['rival_gain']
        adjustment=changed['other_rival_cost']-base['other_rival_cost'] if adjust else 0
        results.append(dict(label=label,own_delta=own,rival_delta=rival-adjustment,
                            margin_delta=own-rival+adjustment,omitted_rival_cost_delta=adjustment,
                            baseline=a,candidate=b))
    for i in (0,2,4):
        w=runtime.world_batch.world(obs,i)
        add(f'true_shops_model_{i}',rollout(None,w),rollout(47,w))
    a=rollout(None,world(base));b=rollout(47,world(base))
    add('true_baseline_netted_rival_supply_for_both',a,b)
    b=rollout(47,world(changed));add('branch_specific_true_netted_rival_supply',a,b)
    add('branch_specific_netted_supply_and_rival_costs',a,b,True)
    a=rollout(None,world(base),ordered_source=base);b=rollout(47,world(changed),ordered_source=changed)
    add('branch_specific_ordered_trades_and_rival_costs',a,b,True)
    a=rollout(None,world(base),base,base);b=rollout(47,world(changed),changed,changed)
    add('branch_specific_ordered_trades_weeds_and_rival_costs',a,b,True)
    ar,br=base['reference'],changed['reference']
    actual=dict(own_delta=br['cash']-ar['cash'],rival_delta=br['rival_cash']-ar['rival_cash'],margin_delta=br['margin']-ar['margin'])
    for row in results:
        row['margin_prediction_error']=row['margin_delta']-actual['margin_delta']
        row['own_prediction_error']=row['own_delta']-actual['own_delta']
        row['rival_prediction_error']=row['rival_delta']-actual['rival_delta']
    result=dict(case='fresh-12-v56',checkpoint=12,route=47,actual=actual,rows=results,
        same_hour_round_trips=dict(baseline=base['round_trips'],candidate=changed['round_trips']),
        limitation=__doc__,note='These nested oracle substitutions diagnose residual error. They are unavailable to a live selector and do not provide a fresh test. Weed collisions indicate a changed physical trajectory.')
    S.write(S.OUT/'forecast_regression_attribution.json',result)
    print(S.json.dumps(dict(actual=actual,rows=[{k:v for k,v in r.items() if k not in ('baseline','candidate')} for r in results]),indent=2))

if __name__=='__main__':main()
