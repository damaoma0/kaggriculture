"""Public-input rival delivery-delay stress on the development checkpoint."""
from collections import Counter, defaultdict
from copy import deepcopy
import json
from pathlib import Path

from diagnose_repair_forecast import OLD, STUDY, N, replay


def delayed(world, start, hours):
    hourly=defaultdict(Counter)
    for t,flows in world['hourly'].items():
        for product,amount in flows.items():
            hour=min(718,t+hours) if amount>0 else t
            hourly[hour][product]+=amount
    return dict(world,hourly={t:dict(v) for t,v in hourly.items()},delivery_delay=hours)


def main():
    case='random-06-v56'
    spec=next(s for s in json.loads((STUDY/'r1/design.json').read_text())['specs'] if s['id']==case)
    base=replay(OLD,case,spec,True)
    obs,mem=base['obs'],base['memory'];runner=N.runtime();runner.prepare(obs)
    selection=(408,((9,1,'TOMATO',13),));rows=[]
    for i in range(8):
        world=runner.world_batch.world(obs,i)
        for delay in (6,12,24):
            w=delayed(world,int(obs['step']),delay)
            a=runner.rollout(obs,mem,None,w)
            b=runner.rollout(obs,mem,selection,w)
            delta=b['margin_gain']-a['margin_gain']
            rows.append(dict(index=i,delay=delay,margin=delta,own=b['cash_gain']-a['cash_gain'],
                             rival=b['rival_gain']-a['rival_gain']))
            print(i,delay,delta,flush=True)
    (STUDY/'delivery_stress_probe.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')


if __name__=='__main__':main()
