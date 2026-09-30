"""Paired fixed-world evaluations of causal tape decisions; no outcome filtering."""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from hashlib import sha256
import argparse
import gzip
import json
import os
from pathlib import Path
import random
import statistics
import time
import traceback

import research_labour_profit as R
import value_tape_search as V

ROOT = V.ROOT
OUT = ROOT/'results/fresh/value_tape_search_20260923'
CASES = ((111287532,12),(111262874,12),(111269605,15),(111337545,15),
         (111324547,15),(111284610,15),(111261836,18))


def load(episode):
    with gzip.open(ROOT/f'data/ladder_panel/56395605/{episode}.json.gz','rt',encoding='utf-8') as f:
        game=json.load(f)
    pair=[None,None]
    pair[game['seat']],pair[1-game['seat']]=game['our_actions'],game['opp_actions']
    return game,pair


def checkpoint(game,pair,day):
    entry=V.fresh_agent()
    E=R.engine()
    mismatches=[]
    with R.Simulator(game) as sim:
        old=E.interpreter
        def update(state,env):
            obs=state[game['seat']].observation
            action=entry(deepcopy(obs))
            if action!=pair[game['seat']][obs.step]:
                mismatches.append(obs.step)
            return old(state,env)
        E.interpreter=update
        try:
            result=sim.run(sim.initial,0,day*24,pair)
        finally:
            E.interpreter=old
    assert not mismatches, ('native_prefix_does_not_reproduce',mismatches[:5])
    return result['state'],V.memory_of(entry)


def evaluate(game,pair,state,memory,route,day):
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
            result=sim.run(state,day*24,719,pair,capture=True)
        finally:
            E.interpreter=old
    own,rival=result['money'][seat],result['money'][1-seat]
    output=Counter()
    plants=Counter()
    for w in result['work']:
        if w['seat']!=seat:
            continue
        if w['cmd'][0] in ('HARVEST','COLLECT_FERTILIZER'):
            output.update({p:n for p,n in w['delta'].items() if n>0})
        if w['cmd'][0]=='PLANT':
            plants[w['cmd'][1]]+=1
    economics=R.economic(result['events'],seat)
    starting=state[0].observation.farms[seat]['money']
    assert starting+sum(economics['revenue'].values())-sum(economics['spend'].values())==own
    return dict(cash=own,rival_cash=rival,margin=own-rival,output=dict(output),plants=dict(plants),
                economics=economics,history=entry.__globals__['_MGT_HISTORY'],ledger_verified=True)


def case_impl(job):
    episode,day,count,scenarios,folder=job
    path=Path(folder)/f'{episode}-{day}.json'
    if path.exists():
        old=json.loads(path.read_text(encoding='utf-8'))
        return {k:old.get(k) for k in ('episode','day','completed','selected','margin_delta','seconds','error')}
    started=time.perf_counter()
    row=dict(episode=episode,day=day,completed=False)
    try:
        game,pair=load(episode)
        state,memory=checkpoint(game,pair,day)
        obs=deepcopy(state[game['seat']].observation)
        assert obs.step==day*24
        selected,decision=V.choose(obs,memory,count=count,scenarios=V.SCENARIOS[:scenarios])
        # The decision is made and stored before ANY actual future is evaluated.
        row.update(selected=selected,decision=decision,seat=game['seat'],shops=list(obs.town.unlocked_shops))
        path.with_suffix('.decision.json').write_text(json.dumps(row,indent=2,default=str),encoding='utf-8')
        evaluations={}
        for candidate in decision['candidates']:
            route=candidate['route']
            evaluations[str(route)]=evaluate(game,pair,state,memory,route,day)
        base=evaluations['None']
        assert [base['cash'],base['rival_cash']]==[game['rewards'][game['seat']],game['rewards'][1-game['seat']]], 'native suffix failed reproduction'
        for value in evaluations.values():
            value['margin_delta']=value['margin']-base['margin']
            value['cash_delta']=value['cash']-base['cash']
            value['rival_cash_delta']=value['rival_cash']-base['rival_cash']
        actual=evaluations[str(selected)]
        row.update(completed=True,margin_delta=actual['margin_delta'],cash_delta=actual['cash_delta'],
                   baseline_margin=base['margin'],margin=actual['margin'],evaluations=evaluations,
                   hindsight_best_margin_delta=max(x['margin_delta'] for x in evaluations.values()))
    except Exception:
        row['error']=traceback.format_exc()
    row['seconds']=time.perf_counter()-started
    path.write_text(json.dumps(row,indent=2,default=str),encoding='utf-8')
    return {k:row.get(k) for k in ('episode','day','completed','selected','margin_delta','seconds','error')}


def case(job):
    episode,day,_,_,folder=job
    lock=Path(folder)/f'{episode}-{day}.lock'
    try:
        handle=lock.open('x')
    except FileExistsError:
        return dict(episode=episode,day=day,in_progress=True)
    try:
        with (Path(folder)/f'{episode}-{day}.log').open('w',encoding='utf-8') as log:
            saved=[os.dup(1),os.dup(2)]
            try:
                os.dup2(log.fileno(),1)
                os.dup2(log.fileno(),2)
                return case_impl(job)
            finally:
                os.dup2(saved[0],1)
                os.dup2(saved[1],2)
                for fd in saved:
                    os.close(fd)
    finally:
        handle.close()
        lock.unlink()


def freeze_holdout(count):
    path=OUT/'holdout_design.json'
    if path.exists():
        design=json.loads(path.read_text(encoding='utf-8'))
        assert len(design['cases'])==count
        assert design['planner_sha256']==sha256((ROOT/'scripts/value_tape_search.py').read_bytes()).hexdigest()
        return design['cases']
    excluded={e for e,_ in CASES}
    paths=sorted((ROOT/'data/ladder_panel/56395605').glob('*.json.gz'))
    ids=[int(p.name.split('.')[0]) for p in paths if int(p.name.split('.')[0]) not in excluded]
    rng=random.Random(93231471)
    ids=rng.sample(ids,count)
    cases=[[ep,rng.choice((12,15,18))] for ep in ids]
    design=dict(cases=cases,source_sha256=V.SOURCE_SHA256,
                planner_sha256=sha256((ROOT/'scripts/value_tape_search.py').read_bytes()).hexdigest(),
                protocol='Uniform sample of historical games excluding seven diagnostic losses; no outcome selection; reveal day independently sampled; fixed opponent actions and actual shops only in evaluation.')
    path.write_text(json.dumps(design,indent=2),encoding='utf-8')
    return cases


def report(folder):
    rows=[json.loads(p.read_text(encoding='utf-8')) for p in folder.glob('*.json') if not p.name.endswith('.decision.json') and p.name!='summary.json']
    okay=[r for r in rows if r['completed']]
    changed=[r for r in okay if r['selected'] is not None]
    values=[r['margin_delta'] for r in okay]
    summary=dict(games=len(rows),completed=len(okay),changed=len(changed),
        mean_margin_delta=statistics.mean(values) if values else None,
        total_margin_delta=sum(values),better=sum(v>0 for v in values),worse=sum(v<0 for v in values),
        worst=min(values,default=None),best=max(values,default=None),
        cases=[{k:r.get(k) for k in ('episode','day','selected','baseline_margin','margin_delta','cash_delta','hindsight_best_margin_delta','error')} for r in rows])
    (folder/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2),flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--episodes')
    parser.add_argument('--day',type=int,default=12)
    parser.add_argument('--count',type=int,default=7)
    parser.add_argument('--scenarios',type=int,default=3)
    parser.add_argument('--workers',type=int,default=3)
    parser.add_argument('--folder',default='development')
    parser.add_argument('--holdout',type=int,default=0)
    parser.add_argument('--slice')
    parser.add_argument('--reverse',action='store_true')
    args=parser.parse_args()
    folder=OUT/args.folder
    folder.mkdir(parents=True,exist_ok=True)
    cases=freeze_holdout(args.holdout) if args.holdout else CASES
    if args.episodes:
        cases=[(int(ep),args.day) for ep in args.episodes.split(',')]
    if args.slice:
        first,last=map(int,args.slice.split(':'))
        cases=cases[first:last]
    if args.reverse:
        cases=list(reversed(cases))
    jobs=[(ep,day,args.count,args.scenarios,str(folder)) for ep,day in cases]
    with ProcessPoolExecutor(max_workers=args.workers,max_tasks_per_child=1) as pool:
        for result in as_completed([pool.submit(case,job) for job in jobs]):
            print(json.dumps(result.result()),flush=True)
    report(folder)


if __name__=='__main__':
    main()
