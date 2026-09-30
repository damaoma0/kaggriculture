"""Bounded exact-engine diagnostic of a persisted development world."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import run_coherent_opening_study as H
from coherent_opening_v2 import make_policy


def trace(case,arm,stop):
    spec=next(s for s in H.freeze_design('development')['specs'] if s['id']==case)
    seat=spec['seat'];shops=spec['world']['shops'];E=H.R.engine()
    entries=[None,None];policy=make_policy(arm);entries[seat]=policy
    entries[1-seat]=H.load_callable(H.OPPONENTS[spec['opponent']],spec['opponent'])
    sim=H.R.Simulator({'seed':spec['world']['seed'],'seat':seat});rows=[]
    with sim:
        state=deepcopy(sim.initial)
        for t in range(stop):
            sim.t=t;sim.seats={id(f):i for i,f in enumerate(state[0].observation.farms)}
            for s in state:s.observation.step=t
            for i,s in enumerate(state):s.action=entries[i](deepcopy(s.observation))
            f=state[seat].observation.farms[seat];p=state[seat].observation.private
            route=policy._route(state[seat].observation)
            row={'step':t,'route':route,'cash':f['money'],'private':deepcopy(p),'positions':[deepcopy(f['farmer']),*deepcopy(f['hands'])],
                'action':deepcopy(state[seat].action),'source_action':policy.references[route]['actions'][t],
                'source_fills':policy.references[route]['market_success_by_order'][t],
                'source_jobs':[j for j in policy.references[route]['jobs'] if j['step']==t],
                'tiles_before':deepcopy(f['tiles'])}
            start=len(sim.events);E.interpreter(state,sim.env)
            state[0].observation.town.unlocked_shops[:]=shops[:min(8,((t+1)//24)//3)]
            row.update(cash_after=f['money'],private_after=deepcopy(p),tiles_after=deepcopy(f['tiles']),events=sim.events[start:])
            rows.append(row)
    path=H.OUT/'diagnostics'/f'{case}-{arm}-{stop}.json';path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({'spec':spec,'arm':arm,'rows':rows,'history':policy.history},indent=2))
    return path


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--case',required=True);ap.add_argument('--arm',default='latest');ap.add_argument('--stop',type=int,default=72)
    args=ap.parse_args();print(trace(args.case,args.arm,args.stop))
