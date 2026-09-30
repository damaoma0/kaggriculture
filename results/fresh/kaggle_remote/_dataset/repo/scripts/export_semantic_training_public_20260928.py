"""Replay only the authorized modern100 sources into causal public-state rows.

prepare freezes this exporter, its policy observer/ledger dependencies, targets
and both-seat tapes. run uses that immutable bundle, serially, at most10 sources
per checkpoint command. No agent decisions or qualification replays are run.
"""
from collections import Counter
from copy import deepcopy
import argparse
import gc
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
STUDY=ROOT/'results/fresh/semantic_strategy_20260928'
DEFAULT=STUDY/'enriched_modern100_v1'
ASSET_FIELDS=('kind','crop','animal','planted_day','placed_day','yield_units','watered_today',
    'consecutive_unwatered','fertilized_until_day','fed_today','cared_today','consecutive_unfed',
    'pending_care_bonus','fertilizer_available')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):
    with gzip.open(path,'rt',encoding='utf-8') if str(path).endswith('.gz') else open(path,encoding='utf-8') as f:return json.load(f)
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.tmp')
    data=json.dumps(value,separators=(',',':'),ensure_ascii=True).encode()
    if path.suffix=='.gz':
        with open(temporary,'wb') as raw:
            with gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as f:f.write(data)
    else:temporary.write_bytes(data)
    os.replace(temporary,path)
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module

def asset_states(farm):
    counts=Counter()
    for row in farm['tiles']:
        for tile in row:
            if not isinstance(tile,dict) or not (tile.get('crop') or tile.get('animal')):continue
            counts[json.dumps({k:tile[k] for k in ASSET_FIELDS if k in tile},sort_keys=True)]+=1
    return [dict(json.loads(key),count=n) for key,n in sorted(counts.items())]

def features(obs,memory,policy):
    """Only the current actor-visible observation and already observed memory."""
    state=policy.public_state(obs);day=int(obs['day']);seat=int(obs['player'])
    own,rival=obs['farms'][seat],obs['farms'][1-seat];private=obs['private']
    result=deepcopy(state)
    result.update(owned_quadrants=list(own['unlocked_quadrants']),hands=len(own['hands']),
        shed=deepcopy(private['shed']),seeds=deepcopy(private['seeds']),inventories=deepcopy(private['inventories']),
        opponent_crop_cohorts=deepcopy(state['rival_crop_cohorts']),
        opponent_animal_cohorts=deepcopy(state['rival_animal_cohorts']),
        opponent_structures=deepcopy(state['rival_structures']),opponent_cash=rival['money'],
        opponent_owned_quadrants=list(rival['unlocked_quadrants']),opponent_hands=len(rival['hands']),
        own_asset_state_cohorts=asset_states(own),opponent_asset_state_cohorts=asset_states(rival),
        public_history={str(d):deepcopy(memory.get('public_history',{}).get(str(d),{})) for d in range(max(0,day-3),day)})
    assert all(int(key)<day for key in result['public_history'])
    return result

def compare_known(old,new):
    fields=('own_animal_cohorts','own_structures','cash','owned_quadrants','hands','shops_prefix')
    checks={k:old[k]==new[k] for k in fields}
    checks['own_crop_cohorts']=old['own_crop_cohorts']==[
        {k:c[k] for k in ('crop','birth','count')} for c in new['own_crop_cohorts']]
    return checks

def prepare(bundle):
    if (bundle/'manifest.json').exists():raise FileExistsError(bundle/'manifest.json')
    source_manifest=STUDY/'training_episodes_modern100.json';model=STUDY/'causal_daily_rows_modern100.json'
    authorized=read(source_manifest);ids=sorted(map(int,authorized['episodes']))
    assert len(ids)==100 and len(set(ids))==100
    assert not set(ids)&set(map(int,authorized['excluded_episodes']))
    assert authorized['model_sha256']==sha(model)
    original=read(model);assert {int(r['meta']['episode']) for r in original['rows']}==set(ids)
    frozen=STUDY/'candidates/strategy_v8_kb115lt2_readiness'
    files={};provenance={}
    def copy(source,relative):
        target=bundle/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
        files[relative]=sha(target);provenance[relative]=dict(path=source.relative_to(ROOT).as_posix(),sha256=sha(source))
    copy(Path(__file__).resolve(),'exporter.py')
    copy(frozen/'project/scripts/semantic_strategy_policy_20260928.py','dependencies/policy.py')
    copy(frozen/'harness/evaluate_boards.py','dependencies/evaluate_boards.py')
    copy(model,'inputs/original_rows.json')
    copy(source_manifest,'inputs/authorized_training_manifest.json')
    records=[]
    for row in authorized['records']:
        episode=int(row['episode']);assert episode in ids
        for source in row['sources']:
            path=ROOT/source['path'];assert sha(path)==source['sha256']
            category='tapes' if 'leader_tapes/' in source['path'] else 'semantics'
            copy(path,f'inputs/{category}/{episode}.json.gz')
        tape=read(bundle/f'inputs/tapes/{episode}.json.gz')
        sem=read(bundle/f'inputs/semantics/{episode}.json.gz')
        assert episode==int(tape['episode'])==int(sem['meta']['episode'])
        assert int(row['seat'])==int(tape['seat'])==int(sem['meta']['seat'])
        records.append(dict(episode=episode,seat=int(row['seat'])))
    manifest=dict(schema=1,scope='AUTHORIZED_MODERN100_PUBLIC_STATE_ENRICHMENT',episodes=ids,records=records,
        original_rows_sha256=sha(model),authorized_manifest_sha256=sha(source_manifest),files=files,provenance=provenance,
        excluded_overlap=[],reserved_recordings_opened=0,policy_agents_invoked=0,engine_version='1.32.7',
        stage1_reuse='Old DSM40 explicitly authorized for stage2 training; new protocol183 excluded.',
        feature_time='D6..D29 hour0, before any action of that day; history is past3days only',
        source_policy_snapshot=sha(frozen/'manifest.json'))
    write(bundle/'manifest.json',manifest)
    print(json.dumps(dict(prepared=str(bundle),episodes=len(ids),manifest_sha256=sha(bundle/'manifest.json'))))

def verify_bundle(bundle):
    manifest=read(bundle/'manifest.json')
    for path,digest in manifest['files'].items():
        if sha(bundle/path)!=digest:raise RuntimeError('Changed frozen input: '+path)
    assert sha(Path(__file__))==manifest['files']['exporter.py'],'Run the frozen exporter.py, not an edited workspace script'
    return manifest

def run_one(bundle,manifest,episode,external_workers):
    import psutil
    available=psutil.virtual_memory().available/2**30
    if external_workers>1 or available<2.5:raise RuntimeError(f'No shared slot/headroom: external={external_workers}, freeGiB={available:.3f}')
    assert episode in manifest['episodes']
    out=bundle/'episodes'/f'{episode}.json.gz'
    if out.exists():
        existing=read(out)
        assert existing['bundle_manifest_sha256']==sha(bundle/'manifest.json') and existing['validation']['all_pass']
        print(json.dumps(dict(episode=episode,already_complete=True)),flush=True);return
    tape=read(bundle/f'inputs/tapes/{episode}.json.gz');seat=int(tape['seat'])
    baseline=[r for r in read(bundle/'inputs/original_rows.json')['rows'] if int(r['meta']['episode'])==episode]
    assert [r['day'] for r in baseline]==list(range(6,30));byday={r['day']:r for r in baseline}
    policy=load(bundle/'dependencies/policy.py','enrichment_policy')
    ledger_module=load(bundle/'dependencies/evaluate_boards.py','enrichment_ledger')
    import kaggle_environments
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    assert kaggle_environments.__version__==manifest['engine_version']
    engine_sha=sha(Path(E.__file__))
    env=make('kaggriculture',configuration={'episodeSteps':720,'actTimeout':1},info={'seed':int(tape['seed'])})
    actions=[None,None];actions[seat]=tape['actions'];actions[1-seat]=tape['opp_actions']
    assert all(len(a)==719 for a in actions)
    memory={};rows=[];feature_checks=[];shop_checks=[];ledger_dawns=[];calls=[0,0]
    original_end=E._end_of_day
    def end(state,environment,day):
        result=original_end(state,environment,day)
        state[0].observation.town.unlocked_shops[:]=tape['shops'][:min(8,(day+1)//3)]
        return result
    def actor(index):
        def recorded(obs):
            nonlocal memory
            step=int(obs['step']);day,hour=divmod(step,24);calls[index]+=1
            if index==seat:
                current=dict(obs);current.update(day=day,hour=hour)
                memory=policy.observe(current,memory)
                if hour==0:
                    shop_checks.append(obs['town']['unlocked_shops']==tape['shops'][:min(8,day//3)])
                    ledger_dawns.append(dict(day=day,cash=[f['money'] for f in obs['farms']],
                        ledger=deepcopy(ledger.data)))
                    if 6<=day<=29:
                        new=features(current,memory,policy);checks=compare_known(byday[day]['features'],new)
                        feature_checks.append(dict(day=day,checks=checks))
                        assert all(checks.values()),(episode,day,checks)
                        assert all(r.get('observed_ticks')==24 for r in new['public_history'].values())
                        row=deepcopy(byday[day]);row['features']=new;rows.append(row)
            return deepcopy(actions[index][step])
        return recorded
    start=time.perf_counter();E._end_of_day=end
    try:
        with ledger_module.Ledger(E) as ledger:
            env.run([actor(0),actor(1)])
            cash=[state.reward for state in env.state]
            reconciliation=[3000+sum(r['revenue'].values())-sum(r['spend'].values())==cash[i] for i,r in enumerate(ledger.data)]
            validation=dict(steps=len(env.steps),statuses=[s.status for s in env.state],action_calls=calls,
                native_cash_expected=tape['rewards'],replayed_cash=cash,native_both_cash_exact=cash==tape['rewards'],
                ledger_reconciled=reconciliation,ledger=deepcopy(ledger.data),dawn_feature_checks=feature_checks,
                visible_shop_checks=shop_checks,target_rows_unchanged=[r['target'] for r in rows]==[r['target'] for r in baseline])
    finally:E._end_of_day=original_end
    validation['all_pass']=(len(env.steps)==720 and validation['statuses']==['DONE','DONE'] and calls==[719,719]
        and cash==tape['rewards'] and all(reconciliation) and all(shop_checks) and len(rows)==24
        and all(all(r['checks'].values()) for r in feature_checks) and validation['target_rows_unchanged'])
    payload=dict(episode=episode,seat=seat,bundle_manifest_sha256=sha(bundle/'manifest.json'),engine_sha256=engine_sha,
        source_tape_sha256=sha(bundle/f'inputs/tapes/{episode}.json.gz'),rows=rows,validation=validation,
        dawn_ledgers=ledger_dawns,elapsed_seconds=time.perf_counter()-start,memory_available_before_GiB=available)
    if not validation['all_pass']:
        write(bundle/'failures'/f'{episode}.json',payload);raise AssertionError((episode,validation))
    write(out,payload)
    print(json.dumps(dict(episode=episode,rows=len(rows),cash=cash,all_pass=True,elapsed_seconds=payload['elapsed_seconds'],sha256=sha(out))),flush=True)
    del env,rows,payload;gc.collect()

def finalize(bundle):
    manifest=verify_bundle(bundle);rows=[];controls=[]
    for episode in manifest['episodes']:
        path=bundle/'episodes'/f'{episode}.json.gz';result=read(path)
        assert result['bundle_manifest_sha256']==sha(bundle/'manifest.json') and result['validation']['all_pass']
        rows.extend(result['rows']);controls.append(dict(episode=episode,seat=result['seat'],path=path.relative_to(bundle).as_posix(),
            sha256=sha(path),cash_exact=True,ledger_reconciled=True,steps=720,rows=len(result['rows'])))
    original=read(bundle/'inputs/original_rows.json');rows.sort(key=lambda r:r['row_id'])
    assert len(rows)==2400 and [r['target'] for r in rows]==[r['target'] for r in original['rows']]
    result=dict(schema_version=2,kind='modern100_verified_public_state_enrichment',rows=rows,training_games=100,
        training_seats=100,bundle_manifest_sha256=sha(bundle/'manifest.json'),original_rows_sha256=manifest['original_rows_sha256'],
        feature_time=manifest['feature_time'],label_time=original['label_time'],holdout_audit=original['holdout_audit'],
        limitations=['Public-history harvests are inferred from observed same-day yield decreases, not verified sales.',
            'Combined net market flow cannot be uniquely attributed to either player.',
            'Only our own private stock is included; opponent private state is never read.',
            'Current coordinates are used only for observation aggregation and removed from features.',
            'Original daily semantic targets are byte-value preserved; D29 missing boundaries remain missing.',
            'Original DSM40 is training, not independent validation for subsequent models.'],controls=controls)
    output=bundle/'causal_daily_rows_modern100_public_v1.json';write(output,result)
    summary=dict(result='PASS',episodes=100,rows=2400,bundle_manifest_sha256=sha(bundle/'manifest.json'),
        artifact=output.name,artifact_sha256=sha(output),all_native_cash_exact=True,all_ledgers_reconciled=True,
        all_steps_720_done=True,all_known_prefix_features_match=True,all_targets_unchanged=True,controls=controls)
    write(bundle/'completion_manifest.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k!='controls'}))

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('prepare','run','finalize'))
    parser.add_argument('--bundle',type=Path,default=DEFAULT);parser.add_argument('--episodes')
    parser.add_argument('--external-workers',type=int,default=1);args=parser.parse_args();bundle=args.bundle.resolve()
    if args.mode=='prepare':prepare(bundle);return
    manifest=verify_bundle(bundle)
    if args.mode=='finalize':finalize(bundle);return
    episodes=[int(x) for x in (args.episodes or '').split(',') if x]
    assert 1<=len(episodes)<=10 and len(set(episodes))==len(episodes),'Checkpoint commands accept1..10 unique episodes'
    assert set(episodes)<=set(manifest['episodes'])
    for episode in episodes:run_one(bundle,manifest,episode,args.external_workers)

if __name__=='__main__':main()
