"""Prepare/run one immutable, observational V13 live05 D6-D7 shadow capture.

Preparation is file-only. Run requires an explicit dispatch release and sole
worker slot. Both recorded action streams are executed; the frozen candidate is
called only in shadow and must match every one of its first 192 actions.
"""
import argparse
from collections import Counter
from copy import deepcopy
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import time
import traceback

MAIN=Path(r'C:\Users\xyygl\Documents\kaggriculture')
WORK=Path(r'C:\Users\xyygl\.codex\worktrees\semantic-kb115lt2\kaggriculture')
STUDY=MAIN/'results/fresh/semantic_strategy_20260928'


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def plain(v):
    if v is None or isinstance(v,(str,int,float,bool)):return v
    if isinstance(v,dict):return {str(k):plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple,set)):return [plain(x) for x in v]
    return repr(v)


def load(p,name):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m


def prepare(bundle):
    bundle.mkdir(parents=True,exist_ok=False)
    candidate=STUDY/'candidates/strategy_v13_kb115lt2_harvest_exchange'
    result=STUDY/'runs/strategy_v13_kb115lt2_harvest_exchange/development/live/live-05.json'
    source=json.loads(result.read_text());frozen=json.loads((candidate/'manifest.json').read_text())
    assert source['candidate_manifest_sha256']==sha(candidate/'manifest.json')
    inputs=[candidate/'manifest.json',result,result.with_suffix('.actions.json'),
        MAIN/'.venv/Lib/site-packages/kaggle_environments/envs/kaggriculture/kaggriculture.py',STUDY/'protocol.json']
    for group,root in (('files',candidate/'project'),('harness_files',candidate/'harness')):
        for name,digest in frozen[group].items():
            assert sha(root/name)==digest,name
    shutil.copyfile(Path(__file__),bundle/'driver.py')
    manifest=dict(scope=__doc__,status='PREPARED_NOT_DISPATCHED',candidate=str(candidate),source=str(result),
        case=source['case'],stop_step=192,capture_days=[6,7],minimum_free_gib=2.5,max_external_workers=0,
        normal_act_timeout=1.0,normal_overage_bank=60.0,intervention=None,live_opponent_calls=0,
        candidate_manifest_sha256=sha(candidate/'manifest.json'),input_hashes={str(p):sha(p) for p in inputs},
        files={'driver.py':sha(bundle/'driver.py')},
        constraints=['Never tune or fit using fresh smoke cases. This capture uses the predeclared development live05 only.',
            'No executor/config edits. Instrumentation wrappers return original results unchanged.',
            'Stop on first strict own-action mismatch, failed dawn/ledger parity or ordinary runtime-bank exhaustion; preserve failure artifact.',
            'Capture all core inputs/final dawn routes and every D6-D7 tier dispatch cursor, stock and check decision.'])
    (bundle/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(bundle=str(bundle),manifest_sha256=sha(bundle/'manifest.json'),status=manifest['status'])))


def install(fn,captures,clock):
    state=fn.__globals__.get('_STATE')
    if not state:return
    kb=state['kb']
    if getattr(kb,'_newborn_capture_installed',False):return
    core,cmd,check,pre,market=kb._tier_core,kb._tier_cmd,kb._tier_check,kb._tier_pre,kb._market
    context=[None]

    def tier_state(TP):
        # Do not copy _pol: it temporarily holds the build_route closure.
        return plain({k:v for k,v in (TP or {}).items() if k!='_pol'})

    def route_claims(TP):
        rows=[]
        for u,R in (TP or {}).get('routes',{}).items():
            k=int(R.get('k',0));pending=[];feeds=[]
            for j,item in enumerate(R.get('items',[])):
                if j<k:continue
                if item.get('kind')=='pick':pending.append(dict(index=j,item=item.get('item'),quantity=item.get('n')))
                start=int(R.get('sub',0)) if j==k else 0
                for op in item.get('ops',[])[start:]:
                    if op and op[0]=='FEED':feeds.append(item.get('tile'))
            rows.append(dict(unit=u,cursor=k,sub=R.get('sub',0),pending_pickups=pending,remaining_feeds=feeds))
        return plain(rows)

    def pre_hook(S,L,obs,step,day,hour,last_day,tiles,pos,invs,tasks,jobs,shed,seeds,prices,assign,
                 deliv_u,fert_keep,demand):
        watch=day in (6,7) and hour==0
        if watch:
            tick=time.perf_counter();row=dict(step=step,day=day,hour=hour,money=plain(obs['farms'][obs['player']]['money']),
                positions=plain(pos),inventories=plain(invs),shed=plain(shed),seeds=plain(seeds),prices=plain(prices),
                demand=plain(demand),retirements_before=plain(S.get('_xretire')),counters_before=plain(L.get('st')))
            clock['capture_seconds']+=time.perf_counter()-tick
        result=pre(S,L,obs,step,day,hour,last_day,tiles,pos,invs,tasks,jobs,shed,seeds,prices,assign,deliv_u,fert_keep,demand)
        if watch:
            tick=time.perf_counter();row.update(final_tier=tier_state(S.get('tier')),retirements_after=plain(S.get('_xretire')),
                counters_after=plain(L.get('st')))
            captures['dawn_plans'].append(row);clock['capture_seconds']+=time.perf_counter()-tick
        return result

    def market_hook(S,obs,day,hour,money,shed,seeds,carried,invs,tasks,jobs,demand,prices,unlocked,farm,pos,last_day):
        watch=day in (6,7)
        if watch:
            tick=time.perf_counter();TP=S.get('tier') or {}
            row=dict(day=day,hour=hour,step=day*24+hour,money=money,shed=plain(shed),carried=plain(carried),
                inventories=plain(invs),positions=plain(pos),seeds=plain(seeds),prices=plain(prices),demand=plain(demand),
                private=plain(obs.get('private')),wheat_buy_before=TP.get('wheat_buy'),wheat_bought_before=TP.get('wheat_bought'),
                route_claims=route_claims(TP),retirements=plain(S.get('_xretire')))
            clock['capture_seconds']+=time.perf_counter()-tick
        result=market(S,obs,day,hour,money,shed,seeds,carried,invs,tasks,jobs,demand,prices,unlocked,farm,pos,last_day)
        if watch:
            tick=time.perf_counter();TP=S.get('tier') or {};row.update(orders=plain(result),wheat_buy_after=TP.get('wheat_buy'),
                wheat_bought_after=TP.get('wheat_bought'))
            captures['markets'].append(row);clock['capture_seconds']+=time.perf_counter()-tick
        return result

    def core_hook(S,L,st,day,tiles,rec,units,want,t_start):
        watch=day in (6,7)
        if watch:
            tick=time.perf_counter()
            row=dict(day=day,call=len(captures['cores']),rec_before=plain(rec),units=plain(units),want=want,
                public_tiles=plain(tiles),retirements=plain(S.get('_xretire')),counters_before=plain(st),
                nfeed=sum(1 for r in rec.values() for o in r['ops'] if o['c'][0]=='FEED'))
            clock['capture_seconds']+=time.perf_counter()-tick
        result=core(S,L,st,day,tiles,rec,units,want,t_start)
        if watch:
            tick=time.perf_counter();row.update(rec_after=plain(rec),routes=plain(result.get('routes')),summary=plain(result.get('summary')),
                counters_after=plain(st))
            captures['cores'].append(row);clock['capture_seconds']+=time.perf_counter()-tick
        return result

    def check_hook(c,t,inv,day,seeds_left):
        result=check(c,t,inv,day,seeds_left)
        if context[0] is not None:
            tick=time.perf_counter();context[0].append(dict(command=plain(c),tile=plain(t),inventory=plain(inv),result=result))
            clock['capture_seconds']+=time.perf_counter()-tick
        return result

    def cmd_hook(TP,R,u,p,inv,tiles,day,hour,step,seeds_left,shed_left):
        if day not in (6,7):return cmd(TP,R,u,p,inv,tiles,day,hour,step,seeds_left,shed_left)
        tick=time.perf_counter();row=dict(step=step,day=day,hour=hour,unit=u,position=plain(p),inventory=plain(inv),
            shed_left_before=plain(shed_left),route_before=plain(R),retirements=plain(kb._S.get('_xretire')),
            retired_route_targets=plain(TP.get('_wheat_retry_retired')),checks=[])
        log_n=len(TP['log']);context[0]=row['checks'];clock['capture_seconds']+=time.perf_counter()-tick
        try:result=cmd(TP,R,u,p,inv,tiles,day,hour,step,seeds_left,shed_left)
        finally:context[0]=None
        tick=time.perf_counter();row.update(command=plain(result),route_after=plain(R),new_log=plain(TP['log'][log_n:]),
            shed_left_after=plain(shed_left));captures['dispatches'].append(row);clock['capture_seconds']+=time.perf_counter()-tick
        return result

    kb._tier_core=core_hook;kb._tier_cmd=cmd_hook;kb._tier_check=check_hook;kb._tier_pre=pre_hook;kb._market=market_hook
    kb._newborn_capture_installed=True


def run(released,external_workers):
    if not released or external_workers!=0:raise RuntimeError('Explicit release and sole worker slot required')
    here=Path(__file__).resolve().parent;manifest=json.loads((here/'manifest.json').read_text())
    for rel,digest in manifest['files'].items():assert sha(here/rel)==digest,rel
    for path,digest in manifest['input_hashes'].items():assert sha(Path(path))==digest,path
    out=here/'capture.json.gz';failure_out=here/'capture.failure.json.gz'
    assert not out.exists() and not failure_out.exists(),'Do not overwrite a prior capture or failure'
    import psutil
    free=psutil.virtual_memory().available/2**30
    if free<manifest['minimum_free_gib']:raise RuntimeError(f'Memory guard: {free:.3f} GiB available')
    candidate=Path(manifest['candidate']);project=candidate/'project';harness=candidate/'harness'
    frozen=json.loads((candidate/'manifest.json').read_text())
    for group,root in (('files',project),('harness_files',harness)):
        for rel,digest in frozen[group].items():assert sha(root/rel)==digest,rel
    source=Path(manifest['source']);original=json.loads(source.read_text());recorded=json.loads(source.with_suffix('.actions.json').read_text())
    sys.path[:0]=[str(harness),str(project/'scripts')]
    gate=load(harness/'semantic_strategy_gate_20260928.py','newborn_frozen_gate')
    import kaggle_environments
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    import tape_vs_bench as TV
    assert kaggle_environments.__version__=='1.32.7'
    os.chdir(project);fn,accepts_config,loading=gate.load_entry(project/frozen['entry'],project)
    env=make('kaggriculture',configuration={'episodeSteps':720,'actTimeout':1},info={'seed':original['case']['seed']})
    seat=original['case']['seat'];physical=[Counter(),Counter()];seats={};active=[False];step_box=[0]
    interpreter=env.interpreter;old_unit,work=TV.instrument(E,physical,seats,active,step_box);old_end=E._end_of_day
    shops=[original['shops'][:min(8,d//3)] for d in range(31)]
    def real(states,environment):
        active[0]=True;seats.clear();seats.update({id(f):i for i,f in enumerate(states[0].observation.farms)})
        try:return interpreter(states,environment)
        finally:active[0]=False
    def fixed_end(states,environment,day):
        result=old_end(states,environment,day);states[0].observation.town.unlocked_shops[:]=shops[min(30,day+1)];return result
    captures=dict(cores=[],dawn_plans=[],markets=[],dispatches=[],snapshots=[]);clock=dict(capture_seconds=0.0);bank=60.0
    payload=dict(scope=manifest['scope'],manifest_sha256=sha(here/'manifest.json'),case=original['case'],
        source_sha256=sha(source),actions_sha256=sha(source.with_suffix('.actions.json')),candidate_manifest_sha256=sha(candidate/'manifest.json'),
        captures=captures,clock=clock,loading_seconds=loading,memory_free_before_gib=free,live_opponent_calls=0,
        intervention=None,own_actions_matched=0,dawn_checks=[],call_timings=[],verified=False)
    error=None;E._apply_unit_action,E._end_of_day,env.interpreter=work,fixed_end,real
    try:
        with TV.Ledger(E) as ledger:
            env.reset(2)
            for step in range(193):
                step_box[0]=step;obs=env._Environment__get_shared_state(seat).observation;day,hour=divmod(step,24)
                assert obs['step']==step
                if hour==0:
                    checks={}
                    for s in range(2):
                        expected=original['diagnostics'][s][day]['current_observation']
                        checks[f'farm_{s}']=obs['farms'][s]==expected['own_farm']
                    expected=original['diagnostics'][seat][day]['current_observation']
                    checks.update(private=obs['private']==expected['private'],market=obs['market']==expected['market'],town=obs['town']==expected['town'])
                    payload['dawn_checks'].append(dict(day=day,**checks));assert all(checks.values()),(day,checks)
                if step==192:break
                obs['remainingOverageTime']=bank;install(fn,captures,clock)
                tick=time.perf_counter();chosen=fn(deepcopy(obs),env.configuration) if accepts_config else fn(deepcopy(obs));elapsed=time.perf_counter()-tick
                bank-=max(0.0,elapsed-1.0);payload['call_timings'].append(dict(step=step,seconds=elapsed,remaining_bank=bank))
                if bank<0:raise RuntimeError(('Normal 60-second overage exhausted',step,bank))
                if chosen!=recorded[seat][step]:
                    payload['first_action_mismatch']=dict(step=step,chosen=plain(chosen),recorded=recorded[seat][step])
                    raise AssertionError(('Strict shadow action mismatch',step))
                payload['own_actions_matched']+=1
                if day in (6,7):
                    state=fn.__globals__['_STATE'];kb=state['kb'];tier=kb._S.get('tier',{})
                    captures['snapshots'].append(dict(step=step,day=day,hour=hour,own_farm=plain(obs['farms'][seat]),private=plain(obs['private']),
                        market=plain(obs['market']),command=plain(chosen),retirements=plain(kb._S.get('_xretire')),
                        route_state=plain(tier.get('routes')),tier_log=plain(tier.get('log')),tier_counts=plain(tier.get('cnt')),
                        tier_summary=plain(tier.get('summary')) if hour in (0,23) else None,daily_diagnostic=plain(state.get('daily_diagnostic')) if hour==0 else None,
                        executor_cfg=plain(kb.CFG) if hour==0 else None))
                env.step([deepcopy(recorded[i][step]) for i in range(2)])
            actual=[dict(money=obs['farms'][i]['money'],physical=dict(physical[i]),revenue=dict(ledger.data[i]['revenue']),
                sold_units=dict(ledger.data[i]['sold_units']),spend=dict(ledger.data[i]['spend'])) for i in range(2)]
            checks={str(i):{k:Counter(v)==Counter(original['daily'][i][8][k]) if isinstance(v,dict) else v==original['daily'][i][8][k] for k,v in row.items()} for i,row in enumerate(actual)}
            payload['final_ledgers']=actual;payload['final_ledger_checks']=checks
            assert all(all(row.values()) for row in checks.values()),checks
            payload['source_module_audit']=gate.source_module_audit(frozen,project,STUDY,harness,dict(root=str(here),files=manifest['files']))
            payload['verified']=True
    except BaseException:
        error=traceback.format_exc();payload['failure']=error
    finally:
        E._apply_unit_action,E._end_of_day,env.interpreter=old_unit,old_end,interpreter
    payload['remaining_overage_bank']=bank
    destination=failure_out if error else out
    with gzip.open(destination,'wt',encoding='utf-8') as f:json.dump(plain(payload),f,separators=(',',':'))
    print(json.dumps(dict(output=str(destination),sha256=sha(destination),verified=payload['verified'],
        own_actions_matched=payload['own_actions_matched'],remaining_bank=bank,core_calls=len(captures['cores']),dispatch_calls=len(captures['dispatches']))))
    if error:raise RuntimeError(error)


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('prepare');a.add_argument('--bundle',type=Path,default=WORK/'results/fresh/semantic_kb115lt2_recovery/v13_newborn_shadow_live05_v1')
    a=sub.add_parser('run');a.add_argument('--released',action='store_true');a.add_argument('--external-workers',type=int,required=True)
    args=p.parse_args()
    if args.command=='prepare':prepare(args.bundle)
    else:run(args.released,args.external_workers)


if __name__=='__main__':main()
