"""Reconcile both farms and successful work for the large strawberry recovery."""
from collections import Counter,defaultdict
from copy import deepcopy
import json
import os

import probe_value_tape_search as P
import research_labour_profit as R
import value_tape_search as V

OUT=P.ROOT/'results/fresh/value_tape_followup_20260923'


def run(game,pair,state,memory,route,day):
    seat=game['seat'];entry=V.fresh_agent(memory,route,(day+3)*24);E=R.engine();boundary=None
    with R.Simulator(game) as sim:
        old=E.interpreter
        def live(st,env):
            nonlocal boundary
            if st[seat].observation.step==(day+3)*24:boundary=sorted(V.asset_keys(st[0].observation.farms[seat]))
            st[seat].action=entry(deepcopy(st[seat].observation));return old(st,env)
        E.interpreter=live
        try:result=sim.run(state,day*24,719,pair,capture=True)
        finally:E.interpreter=old
    economics=[R.economic(result['events'],s) for s in range(2)]
    for s in range(2):
        assert state[0].observation.farms[s]['money']+sum(economics[s]['revenue'].values())-sum(economics[s]['spend'].values())==result['money'][s]
    daily=defaultdict(lambda:dict(output=Counter(),jobs=Counter(),changes=[],sales=[Counter(),Counter()],revenue=[Counter(),Counter()]))
    for w in result['work']:
        if w['seat']!=seat:continue
        d=w['t']//24;op=w['cmd'][0];daily[d]['jobs'][op]+=1
        if op in ('HARVEST','COLLECT_FERTILIZER'):daily[d]['output'].update({p:n for p,n in w['delta'].items() if n>0})
        if op=='PLANT' or op=='PLACE' and w['cmd'][1] in E.ANIMALS:
            daily[d]['changes'].append({k:w[k] for k in ('t','pos','cmd')})
    for t,s,op,p,price in result['events']:
        if op=='SELL':daily[t//24]['sales'][s][p]+=1;daily[t//24]['revenue'][s][p]+=price
    return dict(money=result['money'],margin=result['money'][seat]-result['money'][1-seat],economics=economics,daily=dict(daily),
        boundary_assets=boundary,animal_buys=[dict(day=t//24,hour=t%24,item=p,price=price) for t,s,op,p,price in result['events'] if s==seat and op=='BUY_ANIMAL'],
        history=entry.__globals__['_MGT_HISTORY'])


def main():
    row=json.loads((OUT/'v4_historical/111262874-12.json').read_text(encoding='utf-8'))
    assert row['completed'] and row['selected']==184
    target=OUT/'selected_strawberry_recovery_trace.json';saved=[os.dup(1),os.dup(2)]
    with target.with_suffix('.log').open('w',encoding='utf-8') as log:
        try:
            os.dup2(log.fileno(),1);os.dup2(log.fileno(),2)
            game,pair=P.load(row['episode']);state,memory=P.checkpoint(game,pair,row['day'])
            base=run(game,pair,state,memory,None,row['day']);changed=run(game,pair,state,memory,row['selected'],row['day'])
            seat=game['seat']
            assert base['money']==game['rewards']
            assert (changed['money'][seat],changed['money'][1-seat])==(row['candidate']['cash'],row['candidate']['rival_cash'])
            result=dict(episode=row['episode'],day=row['day'],seat=seat,route=row['selected'],baseline=base,candidate=changed,
                starting_assets=sorted(V.asset_keys(state[0].observation.farms[seat])),
                revealed_shops=game['shops'][row['day']],actual_shops=game['shops'][29],both_results_reproduced=True)
            target.write_text(json.dumps(result,indent=2,default=str),encoding='utf-8')
        finally:
            os.dup2(saved[0],1);os.dup2(saved[1],2)
            for fd in saved:os.close(fd)
    print(json.dumps(dict(path=str(target),verified=True,shops=result['revealed_shops'],
        cash_before=base['money'],cash_after=changed['money'],rival=1-seat,
        rival_revenue_delta={p:changed['economics'][1-seat]['revenue'].get(p,0)-base['economics'][1-seat]['revenue'].get(p,0)
            for p in set(changed['economics'][1-seat]['revenue'])|set(base['economics'][1-seat]['revenue'])}),indent=2),flush=True)


if __name__=='__main__':main()
