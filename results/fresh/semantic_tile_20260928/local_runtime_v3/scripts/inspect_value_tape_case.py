"""Explain the selected transition using exact successful jobs and ledgers."""
from collections import Counter
from copy import deepcopy
import json

import research_labour_profit as R
import value_tape_search as V
from probe_value_tape_search import load,checkpoint,OUT


def trace(game,pair,state,memory,route,day):
    seat=game['seat']
    entry=V.fresh_agent(memory,route,(day+3)*24)
    E=R.engine()
    with R.Simulator(game) as sim:
        old=E.interpreter
        def live(state,env):
            state[seat].action=entry(deepcopy(state[seat].observation))
            return old(state,env)
        E.interpreter=live
        try:
            result=sim.run(state,day*24,719,pair,capture=True,snapshots=True)
        finally:
            E.interpreter=old
    daily=[]
    for d in range(day,30):
        work=[w for w in result['work'] if w['seat']==seat and w['t']//24==d]
        events=[e for e in result['events'] if e[1]==seat and e[0]//24==d]
        output=sum((Counter({p:n for p,n in w['delta'].items() if n>0}) for w in work
                    if w['cmd'][0] in ('HARVEST','COLLECT_FERTILIZER')),Counter())
        obs=result['snapshots'][d*24][seat].observation
        assets=Counter(t.get('crop') or t.get('animal') for row in obs.farms[seat]['tiles']
                       for t in row if isinstance(t,dict) and (t.get('crop') or t.get('animal')))
        daily.append(dict(day=d,assets=dict(assets),money=obs.farms[seat]['money'],output=dict(output),
            feed=sum(w['cmd'][0]=='FEED' for w in work),care=sum(w['cmd'][0]=='CARE' for w in work),
            plant=[dict(hour=w['t']%24,tile=w['pos'],crop=w['cmd'][1]) for w in work if w['cmd'][0]=='PLANT'],
            place=[dict(hour=w['t']%24,tile=w['pos'],animal=w['cmd'][1]) for w in work
                   if w['cmd'][0]=='PLACE' and w['cmd'][1] in E.ANIMALS],
            buys=[dict(hour=t%24,op=op,item=p,price=price) for t,s,op,p,price in events if op=='BUY_ANIMAL'],
            sold=dict(Counter(p for t,s,op,p,price in events if op=='SELL')),
            revenue=dict(sum((Counter({p:price}) for t,s,op,p,price in events if op=='SELL'),Counter())),
            wages=sum(price for t,s,op,p,price in events if op=='HIRE')))
    return daily


def main():
    row=json.loads((OUT/'revised_development/111269605-15.json').read_text(encoding='utf-8'))
    game,pair=load(row['episode'])
    state,memory=checkpoint(game,pair,row['day'])
    traces={name:trace(game,pair,state,memory,route,row['day'])
            for name,route in [('baseline',None),('selected',row['selected'])]}
    base=row['evaluations']['None']
    selected=row['evaluations'][str(row['selected'])]
    delta={}
    for field in ('revenue','spend','units'):
        a,b=base['economics'][field],selected['economics'][field]
        delta[field]={p:b.get(p,0)-a.get(p,0) for p in sorted(set(a)|set(b)) if a.get(p,0)!=b.get(p,0)}
    result=dict(episode=row['episode'],day=row['day'],selected=row['selected'],deltas=delta,traces=traces)
    (OUT/'selected_wool_case_trace.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(dict(deltas=delta,changes=[dict(day=a['day'],baseline_sheep=a['assets'].get('SHEEP',0),
        selected_sheep=b['assets'].get('SHEEP',0),baseline_buys=a['buys'],selected_buys=b['buys'],
        baseline_wool=a['output'].get('WOOL',0),selected_wool=b['output'].get('WOOL',0),
        wage_delta=b['wages']-a['wages']) for a,b in zip(traces['baseline'],traces['selected'])]),indent=2))


if __name__=='__main__':
    main()
