"""Successful-work and cash attribution for a completed live selected switch."""
from collections import Counter,defaultdict
from copy import deepcopy
import argparse
import json
import os
from pathlib import Path

import research_labour_profit as R
import value_tape_search as V
from benchmark_value_tape_search import OPPONENT


def trace(spec,route):
    from kaggle_environments.agent import get_last_callable
    E=R.engine();seat=spec['seat'];day=spec['day'];ours=V.fresh_agent()
    rival=get_last_callable(OPPONENT.read_text(encoding='utf-8'),path=str(OPPONENT))
    shops=spec['shops'];game=dict(seed=spec['seed'],seat=seat,episode=0,shops=[shops[:min(8,d//3)] for d in range(31)])
    with R.Simulator(game) as sim:
        state=deepcopy(sim.initial);checkpoint=None
        for t in range(719):
            sim.t=t;sim.seats={id(f):s for s,f in enumerate(state[0].observation.farms)};sim.capture=t>=day*24
            for s in state:s.observation.step=t
            if t%24==0:state[0].observation.town['unlocked_shops'][:]=game['shops'][t//24]
            if t==day*24:
                checkpoint=deepcopy(state[seat].observation)
                if route is not None:
                    chassis=ours.__globals__['_MGT_IMPL'].chassis;parent=chassis.router;until=(day+3)*24
                    def committed(obs,step,memory):
                        if step<until:memory['route']=route;return route
                        return parent(obs,step,memory)
                    chassis.router=committed
            state[seat].action=ours(deepcopy(state[seat].observation));state[1-seat].action=rival(deepcopy(state[1-seat].observation))
            E.interpreter(state,sim.env)
        cash=[s.reward for s in state];events=list(sim.events);work=list(sim.work)
    daily=defaultdict(lambda:dict(output=Counter(),sales=Counter(),revenue=Counter(),jobs=Counter(),changes=[]))
    for w in work:
        if w['seat']!=seat:continue
        d=w['t']//24;op=w['cmd'][0];daily[d]['jobs'][op]+=1
        if op in ('HARVEST','COLLECT_FERTILIZER'):daily[d]['output'].update({p:n for p,n in w['delta'].items() if n>0})
        if op=='PLANT' or op=='PLACE' and w['cmd'][1] in E.ANIMALS:
            daily[d]['changes'].append({k:w[k] for k in ('t','pos','cmd')})
    for t,s,op,p,price in events:
        if s==seat and op=='SELL' and t>=day*24:daily[t//24]['sales'][p]+=1;daily[t//24]['revenue'][p]+=price
    economics=[R.economic(events,s) for s in range(2)]
    for s in range(2):assert 3000+sum(economics[s]['revenue'].values())-sum(economics[s]['spend'].values())==cash[s]
    return dict(cash=cash[seat],rival_cash=cash[1-seat],margin=cash[seat]-cash[1-seat],daily=dict(daily),economics=economics,
        animal_buys=[dict(day=t//24,hour=t%24,item=p,price=price) for t,s,op,p,price in events if s==seat and op=='BUY_ANIMAL' and t>=day*24],
        history=ours.__globals__['_MGT_HISTORY'],checkpoint_farm=checkpoint['farms'][seat])


def main():
    parser=argparse.ArgumentParser();parser.add_argument('result');args=parser.parse_args();path=Path(args.result)
    old=json.loads(path.read_text(encoding='utf-8'));assert old['completed'] and old['selected'] is not None
    target=path.with_suffix('.trace.json');saved=[os.dup(1),os.dup(2)]
    with target.with_suffix('.log').open('w',encoding='utf-8') as log:
        try:
            os.dup2(log.fileno(),1);os.dup2(log.fileno(),2)
            result=dict(spec=old['spec'],selected=old['selected'],baseline=trace(old['spec'],None),candidate=trace(old['spec'],old['selected']))
            for mode in ('baseline','candidate'):
                for key in ('cash','rival_cash','margin'):assert result[mode][key]==old[mode][key]
            result['both_original_results_reproduced']=True
            target.write_text(json.dumps(result,indent=2,default=str),encoding='utf-8')
        finally:
            os.dup2(saved[0],1);os.dup2(saved[1],2)
            for fd in saved:os.close(fd)
    summary={mode:dict(buys=result[mode]['animal_buys'],
        output=dict(sum((Counter(d['output']) for d in result[mode]['daily'].values()),Counter())),
        jobs=dict(sum((Counter(d['jobs']) for d in result[mode]['daily'].values()),Counter()))) for mode in ('baseline','candidate')}
    print(json.dumps(dict(verified=True,path=str(target),summary=summary),indent=2),flush=True)


if __name__=='__main__':main()
