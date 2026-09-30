"""Frozen natural-world research panel against a responsive V56 opponent.

One public-information decision on day 15, both seats, fresh agents/processes.
The slow research selector has no competition timeout qualification.
"""
from concurrent.futures import ProcessPoolExecutor, as_completed
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

import research_labour_profit as R
import value_tape_search as V
from value_tape_policies import cohort_policy

ROOT=V.ROOT
OUT=ROOT/'results/fresh/value_tape_search_20260923/live'
OPPONENT=ROOT/'data/router_refresh_20260922/v56/main.py'


def prepare():
    OUT.mkdir(parents=True,exist_ok=True)
    path=OUT/'design.json'
    if path.exists():
        result=json.loads(path.read_text(encoding='utf-8'))
        assert result['planner_sha256']==V.PLANNER_SHA256
        assert result['source_sha256']==V.SOURCE_SHA256
        assert result['opponent_sha256']==sha256(OPPONENT.read_bytes()).hexdigest()
        return result
    master=secrets.randbits(128)
    rng=random.Random(master)
    result=dict(master=master,seeds=rng.sample(range(1_000_000_000,2_000_000_000),4),seats=[0,1],
                decision_day=15,planner_sha256=V.PLANNER_SHA256,source_sha256=V.SOURCE_SHA256,
                opponent_sha256=sha256(OPPONENT.read_bytes()).hexdigest(),
                protocol='Four fresh random natural-RNG worlds, both seats, baseline and candidate; all 16 games retained; one day-15 reveal decision; responsive V56; research runtime, no competition timeout qualification.')
    path.write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


def worker(job):
    seed,seat,mode,design=job
    target=OUT/f'{seed}-{seat}-{mode}.json'
    if target.exists():
        row=json.loads(target.read_text(encoding='utf-8'))
        return {k:row.get(k) for k in ('seed','seat','mode','completed','margin','selected','error')}
    row=dict(seed=seed,seat=seat,mode=mode,completed=False,planner_sha256=V.PLANNER_SHA256)
    started=time.perf_counter()
    with target.with_suffix('.log').open('w',encoding='utf-8') as log:
        saved=[os.dup(1),os.dup(2)]
        try:
            os.dup2(log.fileno(),1);os.dup2(log.fileno(),2)
            E=R.engine()
            from kaggle_environments.agent import get_last_callable
            ours=V.fresh_agent()
            rival=get_last_callable(OPPONENT.read_text(encoding='utf-8'),path=str(OPPONENT))
            game=dict(seed=seed,seat=seat,episode=0,shops=[[] for _ in range(31)])
            # Manually step the official interpreter; keep its natural RNG and
            # shops. Simulator hooks here only observe successful transactions.
            with R.Simulator(game) as sim:
                state=deepcopy(sim.initial)
                decision=None
                for t in range(719):
                    sim.t=t
                    sim.seats={id(f):i for i,f in enumerate(state[0].observation.farms)}
                    for s in state:
                        s.observation.step=t
                    if mode in ('candidate','cohort') and t==design['decision_day']*24:
                        route,decision=V.choose(deepcopy(state[seat].observation),V.memory_of(ours))
                        if mode=='cohort':
                            route,decision=cohort_policy(decision)
                        row['decision']=decision
                        target.with_suffix('.decision.json').write_text(json.dumps(row,indent=2,default=str),encoding='utf-8')
                        if route is not None:
                            chassis=ours.__globals__['_MGT_IMPL'].chassis
                            parent=chassis.router
                            until=(design['decision_day']+3)*24
                            def committed(obs,step,memory):
                                if step<until:
                                    memory['route']=route
                                    return route
                                return parent(obs,step,memory)
                            chassis.router=committed
                    state[seat].action=ours(deepcopy(state[seat].observation))
                    state[1-seat].action=rival(deepcopy(state[1-seat].observation))
                    E.interpreter(state,sim.env)
                money=[s.reward for s in state]
                econ=[R.economic(sim.events,s) for s in range(2)]
                for s in range(2):
                    assert 3000+sum(econ[s]['revenue'].values())-sum(econ[s]['spend'].values())==money[s]
                assert all(s.status=='DONE' for s in state)
                row.update(completed=True,cash=money[seat],rival_cash=money[1-seat],margin=money[seat]-money[1-seat],
                    selected=decision['selected'] if decision else None,
                    shops=list(state[0].observation.town.unlocked_shops),economics=econ,ledger_verified=True,
                    history=ours.__globals__['_MGT_HISTORY'],overlay=ours.__globals__['_SHP_REPORT'])
        except Exception:
            row['error']=traceback.format_exc()
        finally:
            os.dup2(saved[0],1);os.dup2(saved[1],2)
            for fd in saved:os.close(fd)
    row['seconds']=time.perf_counter()-started
    target.write_text(json.dumps(row,indent=2,default=str),encoding='utf-8')
    return {k:row.get(k) for k in ('seed','seat','mode','completed','margin','selected','seconds','error')}


def report(design,mode='candidate'):
    rows=[]
    for seed in design['seeds']:
        for seat in design['seats']:
            base=json.loads((OUT/f'{seed}-{seat}-baseline.json').read_text(encoding='utf-8'))
            candidate=json.loads((OUT/f'{seed}-{seat}-{mode}.json').read_text(encoding='utf-8'))
            okay=base['completed'] and candidate['completed']
            row=dict(seed=seed,seat=seat,completed=okay)
            if okay:
                row.update(baseline_margin=base['margin'],margin=candidate['margin'],margin_delta=candidate['margin']-base['margin'],
                           cash_delta=candidate['cash']-base['cash'],selected=candidate['selected'],
                           shops_equal=base['shops']==candidate['shops'])
            rows.append(row)
    values=[r['margin_delta'] for r in rows if r['completed']]
    summary=dict(pairs=len(rows),completed=len(values),mean_margin_delta=statistics.mean(values) if values else None,
                 changed=sum(r.get('selected') is not None for r in rows),better=sum(v>0 for v in values),worse=sum(v<0 for v in values),
                 minimum=min(values,default=None),maximum=max(values,default=None),rows=rows)
    name='summary.json' if mode=='candidate' else f'summary-{mode}.json'
    (OUT/name).write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2),flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--workers',type=int,default=3)
    parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--mode',choices=['candidate','cohort'],default='candidate')
    args=parser.parse_args()
    design=prepare()
    if args.mode=='cohort':
        path=OUT/'cohort_design.json'
        extension=dict(parent='design.json',admission='cohort_survival_and_economics',
            policy_sha256=sha256((ROOT/'scripts/value_tape_policies.py').read_bytes()).hexdigest(),
            registered_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
            validation='Same four independent live seeds; policy frozen after historical replays and before inspecting live candidate outcomes. Historical validation is development evidence for this variant.')
        if path.exists():
            assert json.loads(path.read_text(encoding='utf-8'))['policy_sha256']==extension['policy_sha256']
        else:
            path.write_text(json.dumps(extension,indent=2),encoding='utf-8')
    if args.prepare_only:
        print(json.dumps(design,indent=2));return
    jobs=[(seed,seat,mode,design) for seed in design['seeds'] for seat in design['seats'] for mode in ('baseline',args.mode)]
    with ProcessPoolExecutor(max_workers=args.workers,max_tasks_per_child=1) as pool:
        for future in as_completed([pool.submit(worker,job) for job in jobs]):
            print(json.dumps(future.result()),flush=True)
    report(design,args.mode)


if __name__=='__main__':
    main()
