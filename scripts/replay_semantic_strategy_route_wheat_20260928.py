"""One-day BUY-only continuation from a parity-checked frozen V5 idle case."""
from collections import Counter
from copy import deepcopy
import argparse
import gzip
import json
import os
from pathlib import Path
import sys
import time

from replay_semantic_strategy_idle_shadow_20260928 import ROOT,STUDY,load,safe,sha,route_snapshot,attach_context_hook
from semantic_strategy_route_wheat_20260928 import route_wheat_order


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',required=True)
    parser.add_argument('--day',type=int,default=10)
    parser.add_argument('--tiles',required=True)
    parser.add_argument('--external-workers',type=int,required=True)
    args=parser.parse_args()
    import psutil
    available=psutil.virtual_memory().available/2**30
    if args.external_workers>1 or available<2.5:
        raise RuntimeError(f'Insufficient allocated slot/memory: external={args.external_workers}, freeGiB={available:.3f}')
    candidate=STUDY/'candidates/strategy_v5_blocks100_finance'
    source=STUDY/'runs/strategy_v5_blocks100_finance/development/live'/f'{args.case}.json'
    actions_path=source.with_suffix('.actions.json')
    original=json.loads(source.read_text());recorded=json.loads(actions_path.read_text())
    manifest=json.loads((candidate/'manifest.json').read_text())
    assert original['candidate_manifest_sha256']==sha(candidate/'manifest.json')
    for rel,digest in manifest['files'].items():assert sha(candidate/'project'/rel)==digest,rel
    for rel,digest in manifest['harness_files'].items():assert sha(candidate/'harness'/rel)==digest,rel
    control_path=STUDY/'idle_shadows_v5'/f'{args.case}-d{args.day}-{args.day}.json.gz'
    with gzip.open(control_path,'rt') as f:control=json.load(f)
    assert control['source_sha256']==sha(source) and control['actions_sha256']==sha(actions_path)
    assert control['replay_cash_equal'] and control['replay_ledger_equal'] and not control['shadow_mismatches']
    shops=[original['shops'][:min(8,day//3)] for day in range(31)]
    project,harness=candidate/'project',candidate/'harness'
    sys.path[:0]=[str(harness),str(project/'scripts')]
    gate=load(harness/'semantic_strategy_gate_20260928.py','frozen_route_wheat_gate')
    import kaggle_environments
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    import tape_vs_bench as TV
    assert kaggle_environments.__version__=='1.32.7'
    os.chdir(project)
    fn,accepts_config,loading=gate.load_entry(project/manifest['entry'],project)
    env=make('kaggriculture',configuration={'episodeSteps':720,'actTimeout':1},info={'seed':original['case']['seed']})
    seat=original['case']['seat'];watch=set(map(int,args.tiles.split(',')))
    physical=[Counter(),Counter()];seats,active,step_box={},[False],[0]
    interpreter=env.interpreter
    old_unit,work=TV.instrument(E,physical,seats,active,step_box)
    old_end=E._end_of_day
    def real(state,environment):
        active[0]=True;seats.clear();seats.update({id(f):i for i,f in enumerate(state[0].observation.farms)})
        try:return interpreter(state,environment)
        finally:active[0]=False
    def fixed_end(state,environment,day):
        result=old_end(state,environment,day)
        state[0].observation.town.unlocked_shops[:]=shops[min(30,day+1)]
        return result
    snapshots,prefix_parity,events,timings=[],[],[],[]
    trigger=None;started=time.perf_counter()
    E._apply_unit_action,E._end_of_day,env.interpreter=work,fixed_end,real
    try:
        with TV.Ledger(E) as ledger:
            env.reset(2);stop=(args.day+1)*24
            for step in range(stop):
                step_box[0]=step;obs=env._Environment__get_shared_state(seat).observation
                assert int(obs['step'])==step
                day,hour=divmod(step,24)
                if day==args.day:attach_context_hook(fn)
                tick=time.perf_counter()
                shadow=fn(deepcopy(obs),env.configuration) if accepts_config else fn(deepcopy(obs))
                call_seconds=time.perf_counter()-tick
                state=fn.__globals__.get('_STATE');chosen=deepcopy(shadow);audit=None
                if trigger is None:
                    assert shadow==recorded[seat][step],('Shadow prefix diverged',step)
                    prefix_parity.append(step)
                if day==args.day:
                    kb=state['kb'];context=getattr(kb,'_audit_context',None)
                    assert context is not None and context['step']==step
                    chosen,audit=route_wheat_order(obs,shadow,kb._S,kb._sd_state(kb._S).get('routes',{}),
                        rolling=not kb.CFG['sd_tier'],tasks=context['tasks'],
                        retirement_intents=state['daily_diagnostic'].get('retirements'),
                        config={'enabled':True},price_at=kb._mkt_price)
                    assert chosen['farmer']==shadow['farmer'] and chosen['hands']==shadow['hands']
                    if audit['active']:
                        events.append(dict(step=step,**audit))
                        if trigger is None:trigger=dict(step=step,**audit)
                    farm=obs['farms'][seat]
                    snapshots.append(dict(step=step,day=day,hour=hour,cash=farm['money'],private=deepcopy(obs['private']),
                        market=deepcopy(obs['market']),positions=dict(farmer=deepcopy(farm['farmer']),hands=deepcopy(farm['hands'])),
                        all_tiles=deepcopy(farm['tiles']),tiles={str(t):deepcopy(farm['tiles'][t//10][t%10]) for t in watch},
                        executed_action=chosen,base_candidate_action=shadow,recorded_action=recorded[seat][step],
                        replenishment=audit,call_seconds=call_seconds,state=route_snapshot(fn,day,hour,watch)))
                timings.append(dict(step=step,seconds=call_seconds))
                actions=[deepcopy(recorded[i][step]) for i in range(2)];actions[seat]=chosen
                env.step(actions)
            final=env._Environment__get_shared_state(seat).observation
            original_next=original['diagnostics'][seat][args.day+1]['current_observation']
            own=final['farms'][seat]
            current_ledgers=[dict(money=final['farms'][i]['money'],physical=dict(physical[i]),
                revenue=dict(ledger.data[i]['revenue']),sold_units=dict(ledger.data[i]['sold_units']),
                spend=dict(ledger.data[i]['spend'])) for i in range(2)]
            baseline=original['daily'][seat][args.day+1];differences={}
            for key in ('physical','revenue','sold_units','spend'):
                ours=current_ledgers[seat][key]
                differences[key]={k:ours.get(k,0)-baseline[key].get(k,0) for k in set(ours)|set(baseline[key])
                                  if ours.get(k,0)!=baseline[key].get(k,0)}
            payload=dict(scope='ONE_DAY_BUY_ONLY_COMPONENT_CONTINUATION_RECORDED_OPPONENT',case=original['case'],
                source_sha256=sha(source),actions_sha256=sha(actions_path),candidate_manifest_sha256=sha(candidate/'manifest.json'),
                script_sha256=sha(Path(__file__)),helper_sha256=sha(ROOT/'scripts/semantic_strategy_route_wheat_20260928.py'),
                control_sha256=sha(control_path),day=args.day,stop_step=stop,live_opponent_calls=0,
                trigger=trigger,events=events,exact_shadow_prefix_calls=len(prefix_parity),watched_tiles=sorted(watch),
                snapshots=snapshots,baseline_end_farm=original_next['own_farm'],continuation_end_farm=deepcopy(own),
                baseline_end_private=original_next['private'],continuation_end_private=deepcopy(final['private']),
                baseline_end_cash=[original['daily'][i][args.day+1]['money'] for i in range(2)],
                continuation_end_cash=[r['money'] for r in current_ledgers],own_ledger_delta=differences,
                current_ledgers=current_ledgers,call_timings=timings,elapsed_seconds=time.perf_counter()-started,
                loading_seconds=loading,memory_available_before_GiB=available,
                limitation='No full-season profit or responsive-opponent claim. Unit actions come unchanged from frozen V5; only causal current route-head wheat purchases are appended.')
    finally:E._apply_unit_action,E._end_of_day,env.interpreter=old_unit,old_end,interpreter
    assert trigger is not None
    out=STUDY/'idle_shadows_v5'/f'{args.case}-d{args.day}-route-wheat.json.gz'
    if out.exists():raise FileExistsError(out)
    with gzip.open(out,'wt',encoding='utf-8') as f:json.dump(safe(payload),f,separators=(',',':'))
    print(json.dumps({k:payload[k] for k in ('case','trigger','events','exact_shadow_prefix_calls','baseline_end_cash',
        'continuation_end_cash','own_ledger_delta','elapsed_seconds')}))
    print(str(out))


if __name__=='__main__':main()
