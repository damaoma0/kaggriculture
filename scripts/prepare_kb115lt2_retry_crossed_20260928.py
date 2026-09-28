"""Prepare/run a declared eight-game responsive-opponent retry component study.

Preparation only freezes files. Run mode requires a separately released sole
engine slot; each game uses a fresh process, normal budgets and >=3.3 GiB free.
"""
from copy import deepcopy
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

WORK=Path(r'C:\Users\xyygl\.codex\worktrees\semantic-kb115lt2\kaggriculture')
MAIN=Path(r'C:\Users\xyygl\Documents\kaggriculture')
STUDY=MAIN/'results/fresh/semantic_strategy_20260928'
DEFAULT=WORK/'results/fresh/semantic_kb115lt2_recovery/retry_crossed_shops_v2'
BASE='strategy_v12_kb115lt2_runtime_fast'
CONTEXTS={'v8_natural':'strategy_v8_kb115lt2_readiness','v12_natural':BASE}
EXECUTOR='results/fresh/semantic_strategy_20260928/runtime/agents/mgt_lead_kb115lt.py'
CONFIG='results/fresh/semantic_strategy_20260928/candidate_config.json'
EXECUTOR_SHA='d6769c6994a9445f96a34e6c517e4fdee8d3bd3160d349e7d480bdc89871452b'

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()
def write(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    temp=p.with_suffix(p.suffix+'.tmp');temp.write_text(json.dumps(v,indent=2,default=str)+'\n',encoding='utf-8');temp.replace(p)
def copy_bound(source,target,expected=None):
    if expected is not None:assert sha(source)==expected,source
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
def schedules(row):
    days={int(x['day']):x['current_observation']['town']['unlocked_shops'] for x in row['diagnostics'][row['case']['seat']]}
    assert set(days)==set(range(30))
    return [days[d] for d in range(30)]+[row['shops']]
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module

def prepare(root):
    if root.exists():raise FileExistsError(root)
    frozen=STUDY/'candidates'/BASE;base_manifest=read(frozen/'manifest.json')
    assert base_manifest['files'][EXECUTOR]==EXECUTOR_SHA
    protocol=read(STUDY/'protocol.json');assert base_manifest['protocol_sha256']==sha(STUDY/'protocol.json')
    cases=[x for x in protocol['development']['live'] if x['id'] in ('live-01','live-07')]
    assert [x['id'] for x in cases]==['live-01','live-07']
    root.mkdir(parents=True)
    copy_bound(Path(__file__),root/'driver.py')
    copy_bound(STUDY/'protocol.json',root/'study/protocol.json')
    for rel,h in protocol['opponent']['files'].items():copy_bound(STUDY/'opponent/pkg'/rel,root/'study/opponent/pkg'/rel,h)
    arms={}
    for arm,flag in (('retry_off',0),('retry_on',1)):
        dst=root/'candidates'/arm
        for folder,key in (('project','files'),('harness','harness_files')):
            for rel,h in base_manifest[key].items():copy_bound(frozen/folder/rel,dst/folder/rel,h)
        config=read(dst/'project'/CONFIG);assert config['executor']['sd_tier_wheat_retry']==1
        if not flag:
            config['executor']['sd_tier_wheat_retry']=0;write(dst/'project'/CONFIG,config)
        manifest=deepcopy(base_manifest)
        manifest.update(candidate_id=arm,component_scope='RETRY_CROSSED_SHOPS_DEVELOPMENT_ONLY',
            copied_from_candidate=BASE,copied_from_manifest_sha256=sha(frozen/'manifest.json'))
        manifest['files'][CONFIG]=sha(dst/'project'/CONFIG)
        write(dst/'manifest.json',manifest)
        arms[arm]=dict(retry_flag=flag,candidate_root=str(dst),manifest_sha256=sha(dst/'manifest.json'))
    on,off=[read(root/'candidates'/arm/'manifest.json') for arm in ('retry_on','retry_off')]
    assert {p for p in on['files'] if on['files'][p]!=off['files'][p]}=={CONFIG}
    sources=[];jobs=[]
    for case in cases:
        for context,version in CONTEXTS.items():
            src=STUDY/'runs'/version/'development/live'/(case['id']+'.json');row=read(src)
            assert row['case']==case and row['completed'] and row['eligible'] and row['measured_runtime_valid']
            source_manifest=STUDY/'candidates'/version/'manifest.json'
            assert row['candidate_manifest_sha256']==sha(source_manifest)
            dst=root/'native_inputs'/context/(case['id']+'.json')
            copy_bound(src,dst);copy_bound(src.with_suffix('.actions.json'),dst.with_suffix('.actions.json'))
            source=dict(case=case,context=context,native_candidate=version,
                result=dst.relative_to(root).as_posix(),result_sha256=sha(dst),
                actions_sha256=sha(dst.with_suffix('.actions.json')),candidate_manifest_sha256=sha(source_manifest),
                shops=schedules(row),shops_sha256=digest(schedules(row)))
            sources.append(source)
            # Both arms run fresh. Counterbalance order within each source-world.
            order=('retry_off','retry_on') if (case['id']=='live-01')==(context=='v8_natural') else ('retry_on','retry_off')
            for arm in order:jobs.append(dict(id=f"{case['id']}__{context}__{arm}",case=case,context=context,arm=arm))
    files={p.relative_to(root).as_posix():sha(p) for p in root.rglob('*') if p.is_file()}
    value=dict(schema=1,scope='PREPARED_NOT_RUN_DEVELOPMENT_COMPONENT',
        objective='Isolate the bounded partial-wheat-pickup retry under both previously observed shop contexts with a live responsive frozen MGT V9lite.',
        expected_games=8,expected_pairs=4,selected_cases=cases,source_contexts=sources,arms=arms,jobs=jobs,files=files,
        base_candidate_manifest_sha256=sha(frozen/'manifest.json'),source_executor_sha256=EXECUTOR_SHA,
        selection='Purposeful mechanism cases live01/live07 selected because the already observed V12 retry changed them; not an independent broad improvement sample.',
        intervention='Only candidate_config.executor.sd_tier_wheat_retry 0 versus1. Same optimized V12 executor, model, opening, financing, layouts and live opponent in both arms.',
        engine=dict(version='1.32.7',episodeSteps=720,actTimeout=1,remainingOverageTime=60,workers=1,
            min_free_memory_GiB=3.3,extra_money=0,forced_weeds=False),
        supersedes_preparation=dict(id='retry_crossed_shops_v1',manifest_sha256='8f6e56594f8bcfabf9e925581ddfda35dab5200c3230f48e402e6a33fb0fbc35',
            reason='Parent requires >=3.3 GiB free memory for a responsive MGT worker; the earlier prepared-only2.5 GiB bundle must not be dispatched.'),
        source_control='Full-sequence schedules are harness-only. Both agents receive current official observation/configuration. The agents never receive experiment IDs, native future actions, source outcomes or unrevealed shops.',
        same_prefix='Hash current official observations (excluding only the runtime bank) and both action streams through the first accepted ON retry. Any earlier difference is an explicit prefix failure, retained and not interpreted as an isolated repair effect.',
        reuse='Disabled. Execute all eight fresh. Native diagonals are compared only after execution; even strict equality is a reproduction diagnostic and never retrospectively replaces original development outcomes.',
        invalid_rule='Stop dispatch on engine/runtime/ledger/opponent health failure. Retain every failed attempt and the full planned denominator; no win-count stop, substitutions or discarded losses.',
        reporting='Four paired differences, stratified by seed and shop source; successful quantities/revenue/spend, intentional retirement and route-retry events. These selected fixed-shop development worlds are never pooled with natural or qualification gates.',
        qualification='No qualification games are scheduled or read.',
        execution_status='Preparation does not authorize dispatch; obtain an explicitly coordinated sole-worker window.')
    write(root/'manifest.json',value)
    print(json.dumps(dict(root=str(root),manifest_sha256=sha(root/'manifest.json'),expected_games=8,prepared=True)))

def verify(root):
    manifest=read(root/'manifest.json')
    assert manifest['expected_games']==8 and len(manifest['jobs'])==8
    for rel,h in manifest['files'].items():assert sha(root/rel)==h,rel
    assert Path(__file__).resolve()==root/'driver.py','Use the frozen driver.'
    for arm,data in manifest['arms'].items():assert sha(root/'candidates'/arm/'manifest.json')==data['manifest_sha256']
    return manifest

def guard(external_workers):
    import psutil
    free=psutil.virtual_memory().available/2**30
    if external_workers!=0 or free<3.3:raise RuntimeError(f'Sole worker slot and >=3.3 GiB required; external={external_workers}, free={free:.3f}')
    return free

def run_one(root,job_id,external_workers):
    manifest=verify(root);free=guard(external_workers)
    job=next(j for j in manifest['jobs'] if j['id']==job_id)
    out=root/'runs'/(job_id+'.json')
    if out.exists() or out.with_suffix('.paired_inputs.json').exists():raise FileExistsError(out)
    candidate=root/'candidates'/job['arm'];harness=candidate/'harness'
    sys.path[:0]=[str(harness),str(candidate/'project/scripts')]
    G=load(harness/'semantic_strategy_gate_20260928.py','retry_crossed_frozen_gate')
    source=next(s for s in manifest['source_contexts'] if s['case']==job['case'] and s['context']==job['context'])
    fingerprints=[[],[]];retry_events=[];original_loader=G.load_entry
    class AuditCallable:
        def __init__(self,fn,index,accepts):self.fn=fn;self.index=index;self.accepts=accepts
        @property
        def __globals__(self):return self.fn.__globals__
        def __call__(self,obs,config=None):
            visible=deepcopy(dict(obs));visible.pop('remainingOverageTime',None)
            fingerprints[self.index].append(dict(step=int(obs['step']),sha256=digest(visible)))
            action=self.fn(obs,config) if self.accepts else self.fn(obs)
            if self.index==job['case']['seat']:
                state=self.fn.__globals__.get('_STATE')
                kb=state.get('kb') if state else None
                tier=(kb._S or {}).get('tier',{}) if kb else {}
                for event in tier.get('_wheat_retry_audit',[]):
                    if event.get('step')==int(obs['step']):retry_events.append(deepcopy(event))
            return action
    def audited_loader(path,project):
        fn,accepts,elapsed=original_loader(path,project)
        index=job['case']['seat'] if Path(path).resolve().is_relative_to((candidate/'project').resolve()) else 1-job['case']['seat']
        return AuditCallable(fn,index,accepts),True,elapsed
    G.load_entry=audited_loader
    original_audit=G.source_module_audit
    def strict_source_audit(*args,**kwargs):
        checked=original_audit(*args,**kwargs)
        allowed={str((root/rel).resolve()).lower() for rel in manifest['files']}
        for name,module in list(sys.modules.items()):
            path=getattr(module,'__file__',None)
            if not path:continue
            path=Path(path).resolve()
            if path.is_relative_to(MAIN/'.venv'):continue
            if any(path.is_relative_to(r) for r in (MAIN,WORK)):
                assert str(path).lower() in allowed,('Unfrozen repository import',name,str(path))
        return checked
    G.source_module_audit=strict_source_audit
    work=dict(study=str(root/'study'),candidate=job['arm'],candidate_root=str(candidate),case=job['case'],kind='live_fixed',output=str(out),
        force_shops=source['shops'],fixed_world=dict(experiment_manifest_sha256=sha(root/'manifest.json'),component='partial_wheat_pickup_retry',
            context=job['context'],arm=job['arm'],natural_source_sha256=source['result_sha256']),
        harness_extension=dict(root=str(root),files=manifest['files']))
    started=time.perf_counter();result=G.play_job(work)
    row=read(out)
    write(out.with_suffix('.paired_inputs.json'),dict(experiment_manifest_sha256=sha(root/'manifest.json'),
        result_sha256=sha(out),actions_sha256=sha(out.with_suffix('.actions.json')),job=job,observable_fingerprints=fingerprints,
        retry_events=retry_events,memory_available_before_GiB=free,wall_seconds=time.perf_counter()-started,
        boundary='Read-only pre-call observation hashes and post-call internal retry logs; nothing added to agent observations or configuration.'))
    print(json.dumps(result))
    if not row.get('completed') or not row.get('eligible') or not row.get('measured_runtime_valid'):raise SystemExit(2)

def run(root,external_workers):
    manifest=verify(root)
    for job in manifest['jobs']:
        guard(external_workers)
        out=root/'runs'/(job['id']+'.json')
        if out.exists():
            row=read(out)
            assert row.get('fixed_world',{}).get('experiment_manifest_sha256')==sha(root/'manifest.json')
            assert row.get('completed') and row.get('eligible') and row.get('measured_runtime_valid'),'Earlier failure retained; stop.'
            assert out.with_suffix('.paired_inputs.json').exists(),'Earlier audit incomplete; stop.'
            continue
        code=subprocess.call([sys.executable,str(root/'driver.py'),'run-one','--root',str(root),
            '--job-id',job['id'],'--external-workers','0'],cwd=root)
        if code:raise SystemExit(code)
    report(root)

def report(root):
    manifest=verify(root);pairs=[];native_reproductions=[]
    for source in manifest['source_contexts']:
        name=source['case']['id']+'__'+source['context'];loaded={}
        for arm in ('retry_off','retry_on'):
            p=root/'runs'/(name+'__'+arm+'.json')
            if not p.exists():continue
            row=read(p);side=p.with_suffix('.paired_inputs.json')
            if not side.exists():continue
            audit=read(side);actions=read(p.with_suffix('.actions.json'))
            assert audit['result_sha256']==sha(p) and audit['actions_sha256']==sha(p.with_suffix('.actions.json'))
            assert row['fixed_world']['experiment_manifest_sha256']==sha(root/'manifest.json')
            assert row['candidate_manifest_sha256']==manifest['arms'][arm]['manifest_sha256']
            assert row['forced_shops_sha256']==source['shops_sha256']
            loaded[arm]=(row,audit,actions)
            native=read(root/source['result'])
            native_reproductions.append(dict(case=source['case']['id'],context=source['context'],arm=arm,
                both_action_streams_equal=actions==read((root/source['result']).with_suffix('.actions.json')),
                cash_equal=row.get('cash_by_seat')==native['cash_by_seat'],source_reused=False))
        pair=dict(case=source['case'],context=source['context'],both_runs_available=len(loaded)==2)
        if len(loaded)==2:
            off,on=loaded['retry_off'],loaded['retry_on']
            accepted=[e for e in on[1]['retry_events'] if e.get('reason')=='picked']
            first=min((e['step'] for e in accepted),default=719)
            prefix_actions=all(off[2][s][:first]==on[2][s][:first] for s in (0,1))
            prefix_obs=all(off[1]['observable_fingerprints'][s][:first+1]==on[1]['observable_fingerprints'][s][:first+1] for s in (0,1))
            valid=all(r[0].get('completed') and r[0].get('eligible') and r[0].get('measured_runtime_valid') for r in (off,on))
            pair.update(engine_runtime_ledger_valid=valid,first_accepted_retry=first if accepted else None,
                exact_both_action_prefix=prefix_actions,exact_both_observation_prefix=prefix_obs,accepted_retries=accepted,
                interpretable_component_pair=valid and prefix_actions and prefix_obs,
                margins=dict(off=off[0].get('margin'),on=on[0].get('margin')),
                paired_margin_delta=on[0]['margin']-off[0]['margin'] if valid else None,
                own_cash_delta=on[0]['cash']-off[0]['cash'] if valid else None,
                rival_cash_delta=on[0]['opponent_cash']-off[0]['opponent_cash'] if valid else None)
        pairs.append(pair)
    result=dict(scope=manifest['scope'],experiment_manifest_sha256=sha(root/'manifest.json'),
        planned_games=8,planned_pairs=4,pairs=pairs,native_reproductions=native_reproductions,
        complete=len(pairs)==4 and all(p.get('interpretable_component_pair') for p in pairs),
        warning='Selected development mechanism cases, crossed fixed shops, live responsive rival. No natural/qualification outcome is replaced; timing/prefix failures remain explicit.')
    write(root/'report.json',result);print(json.dumps(result,indent=2));return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('prepare','verify','run','run-one','report'))
    p.add_argument('--root',type=Path,default=DEFAULT);p.add_argument('--external-workers',type=int);p.add_argument('--job-id')
    a=p.parse_args();root=a.root.resolve()
    if a.mode=='prepare':prepare(root)
    elif a.mode=='verify':print(json.dumps(dict(verified=True,jobs=len(verify(root)['jobs']),manifest_sha256=sha(root/'manifest.json'))))
    elif a.mode=='report':report(root)
    else:
        if a.external_workers is None:p.error('Explicit coordinated --external-workers 0 is required')
        if a.mode=='run':run(root,a.external_workers)
        else:run_one(root,a.job_id,a.external_workers)

if __name__=='__main__':main()
