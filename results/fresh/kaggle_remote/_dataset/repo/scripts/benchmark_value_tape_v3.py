"""Frozen V3 independent fixed-shop live panel and historical diagnostics."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from copy import deepcopy
from hashlib import sha256
import argparse
import json
import os
from pathlib import Path
import random
import secrets
import statistics
import time
import traceback

import probe_value_tape_search as P
import research_labour_profit as R
import rival_trajectory_model_v3 as M
import value_tape_search as V
import value_tape_search_v3 as V3
from benchmark_value_tape_search import OPPONENT

OUT=V.ROOT/'results/fresh/value_tape_followup_20260923'
SOURCES=['value_tape_search_v3.py','rival_trajectory_model_v3.py','value_tape_search_v2.py',
    'rival_trajectory_model.py','value_tape_search.py','benchmark_value_tape_v3.py']


def hashes():
    return {name:sha256((V.ROOT/'scripts'/name).read_bytes()).hexdigest() for name in SOURCES}


def live_game(spec,search):
    from kaggle_environments.agent import get_last_callable
    E=R.engine();seat=spec['seat'];day=spec['day'];ours=V.fresh_agent()
    rival=get_last_callable(OPPONENT.read_text(encoding='utf-8'),path=str(OPPONENT))
    shops=spec['shops'];game=dict(seed=spec['seed'],seat=seat,episode=0,shops=[shops[:min(8,d//3)] for d in range(31)])
    decision=None;prefix=[]
    with R.Simulator(game) as sim:
        state=deepcopy(sim.initial)
        for t in range(719):
            sim.t=t;sim.seats={id(f):s for s,f in enumerate(state[0].observation.farms)}
            for s in state:s.observation.step=t
            if t%24==0:state[0].observation.town['unlocked_shops'][:]=game['shops'][t//24]
            if t==day*24 and search:
                route,decision=V3.choose(deepcopy(state[seat].observation),V.memory_of(ours))
                target=OUT/'v3_live'/f"{spec['seed']}-{seat}.decision.json"
                target.write_text(json.dumps(dict(spec=spec,decision=decision),indent=2,default=str),encoding='utf-8')
                if route is not None:
                    chassis=ours.__globals__['_MGT_IMPL'].chassis;parent=chassis.router;until=(day+3)*24
                    def committed(obs,step,memory):
                        if step<until:memory['route']=route;return route
                        return parent(obs,step,memory)
                    chassis.router=committed
            state[seat].action=ours(deepcopy(state[seat].observation));state[1-seat].action=rival(deepcopy(state[1-seat].observation))
            if t<day*24:prefix.append([deepcopy(s.action) for s in state])
            E.interpreter(state,sim.env)
        cash=[s.reward for s in state];econ=[R.economic(sim.events,s) for s in range(2)]
        for s in range(2):assert 3000+sum(econ[s]['revenue'].values())-sum(econ[s]['spend'].values())==cash[s]
        assert all(s.status=='DONE' for s in state)
    return dict(cash=cash[seat],rival_cash=cash[1-seat],margin=cash[seat]-cash[1-seat],economics=econ,
        shops=shops,ledger_verified=True,prefix_sha256=sha256(json.dumps(prefix,sort_keys=True).encode()).hexdigest(),decision=decision)


def worker(job):
    kind,spec,folder=job
    stem=f"{spec['seed']}-{spec['seat']}" if kind=='live' else f"{spec['episode']}-{spec['day']}"
    target=Path(folder)/f'{stem}.json'
    if target.exists():
        row=json.loads(target.read_text(encoding='utf-8'))
        return {k:row.get(k) for k in ('spec','completed','selected','margin_delta','seconds','error')}
    started=time.perf_counter()
    with target.with_suffix('.log').open('w',encoding='utf-8') as log:
        saved=[os.dup(1),os.dup(2)]
        try:
            os.dup2(log.fileno(),1);os.dup2(log.fileno(),2)
            if kind=='live':
                # Keep the decision independent of the paired baseline result.
                changed=live_game(spec,True);decision=changed['decision'];selected=decision['selected']
                base=live_game(spec,False)
                assert base['prefix_sha256']==changed['prefix_sha256']
            else:
                game,pair=P.load(spec['episode']);state,memory=P.checkpoint(game,pair,spec['day'])
                selected,decision=V3.choose(deepcopy(state[game['seat']].observation),memory)
                target.with_suffix('.decision.json').write_text(json.dumps(dict(spec=spec,decision=decision),indent=2,default=str),encoding='utf-8')
                base=P.evaluate(game,pair,state,memory,None,spec['day'])
                assert [base['cash'],base['rival_cash']]==[game['rewards'][game['seat']],game['rewards'][1-game['seat']]]
                changed=P.evaluate(game,pair,state,memory,selected,spec['day']) if selected is not None else deepcopy(base)
            row=dict(spec=spec,completed=True,selected=selected,strict_selected=decision['strict_selected'],decision=decision,
                baseline=base,candidate=changed,margin_delta=changed['margin']-base['margin'],
                cash_delta=changed['cash']-base['cash'],rival_delta=changed['rival_cash']-base['rival_cash'])
            if kind=='live':row['candidate'].pop('decision',None)
        except Exception:row=dict(spec=spec,completed=False,error=traceback.format_exc())
        finally:
            os.dup2(saved[0],1);os.dup2(saved[1],2)
            for fd in saved:os.close(fd)
    row['seconds']=time.perf_counter()-started;target.write_text(json.dumps(row,indent=2,default=str),encoding='utf-8')
    return {k:row.get(k) for k in ('spec','completed','selected','strict_selected','margin_delta','cash_delta','seconds','error')}


def design(kind,folder):
    path=folder/'design.json'
    if path.exists():
        data=json.loads(path.read_text(encoding='utf-8'));assert data['hashes']==hashes();return data
    if kind=='live':
        master=secrets.randbits(128);rng=random.Random(master)
        seeds=rng.sample(range(2_000_000_000,4_000_000_000),12)
        types_=sorted(M.M.DEMAND)
        specs=[dict(seed=seed,seat=i%2,day=(12,15,18)[i%3],shops=[rng.choice(types_) for _ in range(8)]) for i,seed in enumerate(seeds)]
    else:
        master=None;specs=[dict(episode=e,day=d) for e,d in P.CASES]
    data=dict(kind=kind,specs=specs,master_seed=master,hashes=hashes(),
        source_sha256=V.SOURCE_SHA256,opponent_sha256=sha256(OPPONENT.read_bytes()).hexdigest(),
        training_manifests={str(p):sha256(p.read_bytes()).hexdigest() for p in (M.M.LIBRARY/'manifest.json',M.MODERN/'manifest.json')},
        protocol='Twelve fresh independent random worlds, balanced D12/D15/D18 and seat; same fixed shop draws within each pair; responsive V56. Policy and all worlds frozen before results. All games retained.' if kind=='live' else 'Retrospective seven-case historical development panel; recorded rival actions, fixed actual shops in evaluation only.')
    path.write_text(json.dumps(data,indent=2),encoding='utf-8')
    source=folder/'sources';source.mkdir(exist_ok=True)
    for name in SOURCES:(source/name).write_bytes((V.ROOT/'scripts'/name).read_bytes())
    return data


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--kind',choices=['live','historical'],default='live')
    parser.add_argument('--workers',type=int,default=3);args=parser.parse_args()
    folder=OUT/f'v3_{args.kind}';folder.mkdir(parents=True,exist_ok=True);specs=design(args.kind,folder)['specs'];rows=[]
    with ProcessPoolExecutor(max_workers=args.workers,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(worker,(args.kind,spec,str(folder))) for spec in specs]):
            row=f.result();rows.append(row);print(json.dumps(row),flush=True)
    vals=[r['margin_delta'] for r in rows if r['completed']]
    result=dict(games=len(rows),completed=len(vals),changed=sum(r.get('selected') is not None for r in rows),
        mean=statistics.mean(vals) if vals else None,total=sum(vals),minimum=min(vals,default=None),maximum=max(vals,default=None),
        positive=sum(x>0 for x in vals),negative=sum(x<0 for x in vals),rows=rows)
    (folder/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k!='rows'}),flush=True)


if __name__=='__main__':main()
