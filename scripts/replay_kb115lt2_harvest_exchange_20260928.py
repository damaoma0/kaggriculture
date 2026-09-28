"""Prepare/run a bounded D18 exchange component diagnostic against saved V8.

Preparation is file-only. Both runs require a separately coordinated worker slot.
Shadow controls replay both saved streams. Continuation changes our D18-D19
actions, enabling only the D18 harvest pass; the rival remains recorded.
"""
from collections import Counter
from copy import deepcopy
import argparse
import ast
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import traceback

WORK = Path(r'C:\Users\xyygl\.codex\worktrees\semantic-kb115lt2\kaggriculture')
MAIN = Path(r'C:\Users\xyygl\Documents\kaggriculture')
STUDY = MAIN/'results/fresh/semantic_strategy_20260928'
DEFAULT = WORK/'results/fresh/semantic_kb115lt2_recovery/harvest_exchange_component_v1'
EXPERIMENT_SHA = '1770e5ab8edf4ae1c7bdd50959349579acba6f1226a0fad8951700e5e4e3119e'
ORIGINAL_SHA = '527d4c48b5d6bbef7854d430797e8691858724242d50eeec1e1636665ee124e7'


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text(encoding='utf-8'))
def plain(value):
    if value is None or isinstance(value, (str, float, int, bool)): return value
    if isinstance(value, dict): return {str(k):plain(v) for k,v in value.items()}
    if isinstance(value, (list, tuple, set)): return [plain(v) for v in value]
    return repr(value)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def prepare(bundle):
    if bundle.exists(): raise FileExistsError(bundle)
    executor = WORK/'agents/mgt_lead_kb115lt2_harvestx_fast.py'
    assert sha(executor) == EXPERIMENT_SHA
    candidate = STUDY/'candidates/strategy_v8_kb115lt2_readiness'
    source = STUDY/'runs/strategy_v8_kb115lt2_readiness/development/live/live-01.json'
    actions = source.with_suffix('.actions.json')
    bundle.mkdir(parents=True)
    (bundle/'executor.py').write_bytes(executor.read_bytes())
    (bundle/'driver.py').write_bytes(Path(__file__).read_bytes())
    manifest = dict(scope='PREPARED_NOT_RUN_RECORDED_COMPONENT_DIAGNOSTIC', case='live-01',
        day=18, stop_day=20, candidate=str(candidate), source=str(source), actions=str(actions),
        candidate_manifest_sha256=sha(candidate/'manifest.json'), source_sha256=sha(source),
        actions_sha256=sha(actions), executor_sha256=sha(bundle/'executor.py'),
        driver_sha256=sha(bundle/'driver.py'), live_opponent_calls=0,
        baseline='Frozen V8 policy/model/opening. Performance-preserving executor changes only until D18.',
        treatment='One bounded rest-harvest exchange on D18; normal causal policy continues through D19, feature OFF on D19.',
        next_steps=['Wait until parent/cloud release the sole engine slot.',
                    'Run shadow first; require complete action/public/private/ledger prefix match through D20.',
                    'Run continue only after shadow is verified. Inspect D19 receipt, both cash ledgers, actual sales and deleted stock.'])
    (bundle/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(dict(bundle=str(bundle), manifest_sha256=sha(bundle/'manifest.json'), prepared=True)))


def install(fn, source):
    state = fn.__globals__.get('_STATE')
    if not state: return
    kb = state['kb']
    if getattr(kb, '_harvest_component_installed', False): return
    names = {'_tier_eval', '_tier_eval_reference', '_tier_search', '_tier_deliver', '_tier_polish',
             '_tier_harvest_exchange', '_tier_cmd', '_tier_override', '_tier_wheat_retry_targets',
             '_tier_wheat_retry_finish', '_tier_wheat_retry'}
    tree = ast.parse(source.read_text())
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in nodes} == names
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), kb.__dict__)
    kb.CFG.update(sd_polish_harvest_exchange=0, sd_polish_harvest_exchange_cap=96,
                  sd_tier_wheat_retry=0, sd_tier_eval_fast=1, sd_tier_search_cache=1)
    kb._harvest_component_installed = True


def run(bundle, mode, external_workers):
    import psutil
    available = psutil.virtual_memory().available/2**30
    if external_workers != 0 or available < 2.5:
        raise RuntimeError(f'Requires released sole engine slot and >=2.5GiB: external={external_workers}, free={available:.3f}')
    manifest = read(bundle/'manifest.json')
    assert sha(bundle/'executor.py') == manifest['executor_sha256'] == EXPERIMENT_SHA
    assert sha(Path(__file__)) == manifest['driver_sha256'], 'Run the frozen bundle driver.'
    candidate = Path(manifest['candidate']); source = Path(manifest['source']); actions_path = Path(manifest['actions'])
    assert sha(source) == manifest['source_sha256'] and sha(actions_path) == manifest['actions_sha256']
    assert sha(candidate/'manifest.json') == manifest['candidate_manifest_sha256']
    original, recorded = read(source), read(actions_path)
    frozen = read(candidate/'manifest.json')
    for folder,key in (('project','files'), ('harness','harness_files')):
        for path,digest in frozen[key].items(): assert sha(candidate/folder/path) == digest, path
    assert sha(candidate/'project/results/fresh/semantic_strategy_20260928/runtime/agents/mgt_lead_kb115lt.py') == ORIGINAL_SHA
    out = bundle/(mode+'.json.gz')
    if out.exists(): raise FileExistsError(out)
    control = None
    if mode == 'continue':
        control_path = bundle/'shadow.json.gz'
        with gzip.open(control_path, 'rt') as handle: control = json.load(handle)
        assert control['verified_control'] and control['bundle_manifest_sha256'] == sha(bundle/'manifest.json')
    project, harness = candidate/'project', candidate/'harness'
    sys.path[:0] = [str(harness), str(project/'scripts')]
    gate = load(harness/'semantic_strategy_gate_20260928.py', 'frozen_harvest_component_gate')
    import kaggle_environments
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    import tape_vs_bench as TV
    assert kaggle_environments.__version__ == '1.32.7'
    os.chdir(project)
    fn, accepts_config, loading = gate.load_entry(project/frozen['entry'], project)
    env = make('kaggriculture', configuration={'episodeSteps':720, 'actTimeout':1}, info={'seed':original['case']['seed']})
    seat = original['case']['seat']; day_start=manifest['day']; stop=manifest['stop_day']*24
    shops = [original['shops'][:min(8,d//3)] for d in range(31)]
    physical=[Counter(),Counter()]; seats={}; private_seats={}; active=[False]; step_box=[0]
    interpreter=env.interpreter
    old_unit,work=TV.instrument(E,physical,seats,active,step_box)
    old_end,old_dump=E._end_of_day,E._drop_inventories_to_shed
    dumps=[]; sales=[]; snapshots=[]; checks=[]; timings=[]; daily=[]; parity=0; trigger=None
    def real(states, environment):
        active[0]=True;seats.clear();private_seats.clear()
        seats.update({id(f):i for i,f in enumerate(states[0].observation.farms)})
        private_seats.update({id(states[i].observation.private):i for i in range(2)})
        try:return interpreter(states,environment)
        finally:active[0]=False
    def fixed_end(states,environment,day):
        value=old_end(states,environment,day)
        states[0].observation.town.unlocked_shops[:]=shops[min(30,day+1)]
        return value
    def dump(private,capacity):
        i=private_seats.get(id(private));before=deepcopy(private['shed'])
        carried=Counter()
        for inv in private['inventories']:carried.update(inv)
        value=old_dump(private,capacity)
        if step_box[0]>=day_start*24:
            transferred={k:int(private['shed'].get(k,0))-int(before.get(k,0)) for k in carried}
            deleted={k:int(v)-transferred[k] for k,v in carried.items() if int(v)!=transferred[k]}
            dumps.append(dict(step=step_box[0],seat=i,capacity=capacity,before_shed=before,
                carried=dict(carried),after_shed=deepcopy(private['shed']),transferred=transferred,deleted=deleted))
        return value
    E._apply_unit_action,E._end_of_day,E._drop_inventories_to_shed,env.interpreter=work,fixed_end,dump,real
    started=time.perf_counter()
    try:
        with TV.Ledger(E) as ledger:
            old_commit=E._commit_unit
            def commit(op,item,price,farm,private,market,shed_capacity=100):
                before_cash=farm['money'];before_shed=private['shed'].get(item,0)
                ok=old_commit(op,item,price,farm,private,market,shed_capacity)
                if step_box[0]>=day_start*24 and op=='SELL':
                    sales.append(dict(step=step_box[0],seat=seats.get(id(farm)),item=item,price=price,
                        success=bool(ok),cash_delta=farm['money']-before_cash,
                        shed_delta=private['shed'].get(item,0)-before_shed))
                return ok
            E._commit_unit=commit
            def ledgers(obs):
                return [dict(money=obs['farms'][i]['money'],physical=dict(physical[i]),
                    revenue=dict(ledger.data[i]['revenue']),sold_units=dict(ledger.data[i]['sold_units']),
                    spend=dict(ledger.data[i]['spend'])) for i in range(2)]
            try:
                env.reset(2)
                for step in range(stop):
                    step_box[0]=step;obs=env._Environment__get_shared_state(seat).observation
                    assert int(obs['step'])==step
                    day,hour=divmod(step,24)
                    if hour==0:
                        cur=ledgers(obs);daily.append(dict(day=day,ledgers=cur))
                        if trigger is None:
                            expected=original['diagnostics'][seat][day]['current_observation']
                            check=dict(day=day,public=obs['farms'][seat]==expected['own_farm'],
                                private=obs['private']==expected['private'],market=obs['market']==expected['market'],
                                shops=obs['town']['unlocked_shops']==expected['town']['unlocked_shops'],
                                ledgers=all(all(cur[i][k]==original['daily'][i][day][k]
                                    for k in ('money','physical','revenue','sold_units','spend')) for i in range(2)))
                            assert all(v for k,v in check.items() if k!='day'),check
                            checks.append(check)
                    install(fn,bundle/'executor.py')
                    state=fn.__globals__.get('_STATE')
                    if state:state['kb'].CFG['sd_polish_harvest_exchange']=int(mode=='continue' and day==day_start)
                    tick=time.perf_counter()
                    chosen=fn(deepcopy(obs),env.configuration) if accepts_config else fn(deepcopy(obs))
                    elapsed=time.perf_counter()-tick;timings.append(dict(step=step,seconds=elapsed))
                    state=fn.__globals__.get('_STATE');kb=state['kb'];tier=kb._S.get('tier',{}) if kb._S else {}
                    decision=(tier.get('summary',{}).get('polish') or {}).get('harvest_exchange')
                    if mode=='continue' and trigger is None and decision and decision.get('accepted'):
                        trigger=dict(step=step,decision=deepcopy(decision))
                    if trigger is None:
                        assert chosen==recorded[seat][step],('Pre-treatment action mismatch',step,chosen,recorded[seat][step])
                        parity+=1
                    if day>=day_start:
                        snapshots.append(dict(step=step,own_farm=deepcopy(obs['farms'][seat]),private=deepcopy(obs['private']),
                            market=deepcopy(obs['market']),action=deepcopy(chosen),recorded_action=deepcopy(recorded[seat][step]),
                            retirement=plain(kb._S.get('_xretire')),tier_routes=plain(tier.get('routes')),
                            tier_summary=plain(tier.get('summary')),daily_diagnostic=plain(state.get('daily_diagnostic')),
                            ledgers=ledgers(obs)))
                    actions=[deepcopy(recorded[i][step]) for i in range(2)]
                    actions[seat]=deepcopy(recorded[seat][step] if mode=='shadow' else chosen)
                    env.step(actions)
                final=env._Environment__get_shared_state(seat).observation
                actual=ledgers(final);daily.append(dict(day=manifest['stop_day'],ledgers=actual))
                expected=original['diagnostics'][seat][manifest['stop_day']]['current_observation']
                control_equal=(final['farms'][seat]==expected['own_farm'] and final['private']==expected['private']
                    and all(all(actual[i][k]==original['daily'][i][manifest['stop_day']][k]
                        for k in ('money','physical','revenue','sold_units','spend')) for i in range(2)))
                for row in actual:
                    assert 3000+sum(row['revenue'].values())-sum(row['spend'].values())==row['money']
                if mode=='shadow':assert control_equal
                result=dict(scope='CONTROLLED_RECORDED_D18_EXCHANGE_D19_FOLLOWTHROUGH',mode=mode,
                    case=original['case'],bundle_manifest_sha256=sha(bundle/'manifest.json'),
                    source_executor_sha256=EXPERIMENT_SHA,engine_sha256=sha(Path(E.__file__)),
                    control_sha256=sha(bundle/'shadow.json.gz') if control else None,
                    verified_control=mode=='shadow' and control_equal and parity==stop,
                    exact_pre_treatment_action_calls=parity,trigger=trigger,checks=checks,daily=daily,
                    snapshots=snapshots,dumps=dumps,sales=sales,timings=timings,stop_step=stop,
                    final_own_farm=deepcopy(final['farms'][seat]),final_private=deepcopy(final['private']),
                    current_ledgers=actual,live_opponent_calls=0,
                    elapsed_seconds=time.perf_counter()-started,loading_seconds=loading,
                    memory_available_before_GiB=available,
                    limitation='Recorded-rival component diagnostic through D20 morning, not a full-season profit gate.')
            finally:E._commit_unit=old_commit
    except BaseException:
        failure=dict(scope='FAILED_COMPONENT_DIAGNOSTIC_PRESERVED',mode=mode,
            bundle_manifest_sha256=sha(bundle/'manifest.json'),step=step_box[0],
            error=traceback.format_exc(),exact_pre_treatment_action_calls=parity,
            trigger=trigger,checks=checks,daily=daily,snapshots=snapshots,
            dumps=dumps,sales=sales,timings=timings,
            elapsed_seconds=time.perf_counter()-started)
        with gzip.open(bundle/(mode+'.failure.json.gz'),'wt',encoding='utf-8') as handle:
            json.dump(plain(failure),handle,separators=(',',':'))
        raise
    finally:
        E._apply_unit_action,E._end_of_day,E._drop_inventories_to_shed,env.interpreter=old_unit,old_end,old_dump,interpreter
    with gzip.open(out,'wt',encoding='utf-8') as handle:json.dump(plain(result),handle,separators=(',',':'))
    print(json.dumps({k:result[k] for k in ('mode','verified_control','exact_pre_treatment_action_calls','trigger','stop_step','elapsed_seconds')}))
    print(out)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('prepare','shadow','continue'))
    parser.add_argument('--bundle',type=Path,default=DEFAULT)
    parser.add_argument('--external-workers',type=int,default=None)
    args=parser.parse_args();bundle=args.bundle.resolve()
    if args.mode=='prepare':prepare(bundle)
    else:
        if args.external_workers is None:raise ValueError('Explicit worker allocation required')
        run(bundle,args.mode,args.external_workers)


if __name__=='__main__':main()
