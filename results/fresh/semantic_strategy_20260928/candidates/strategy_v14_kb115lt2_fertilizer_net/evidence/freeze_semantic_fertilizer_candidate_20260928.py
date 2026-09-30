"""Prepare V14 from exact V13. Never dispatch an engine or overwrite artifacts."""
import argparse
import ast
import copy
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
IDENTIFIER = 'strategy_v14_kb115lt2_fertilizer_net'
V13 = '82d5d5a2a3acc181705540a4acf2ed0a764294bba964122d888ec3634cbb0550'
CONFIG = 'results/fresh/semantic_strategy_20260928/candidate_config.json'
REPLACEMENTS = {
    'scripts/semantic_strategy_policy_20260928.py': 'e1117b7ee8011c5b5d415983aea1077b2adff1e49ee7f8ab6984f10c68ec83f0',
    'scripts/semantic_strategy_blocks_20260928.py': '88b5fd1e83125dc727b02b138e48977b0706f0dc7af2735bb3117915559ac80b',
    'scripts/semantic_strategy_fertilizer_net_20260928.py': 'e0cd64a9d35ec3f6e2b0ba30aebb406634c59b5cd019f2a920b7466721a42e2f',
}
AUDIT = ROOT/'results/fresh/semantic_kb115lt2_recovery/diagnostics/fertilizer_net'


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, value):
    assert not path.exists(), path
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study',type=Path,required=True)
    args=parser.parse_args();study=args.study.resolve()
    source=study/'candidates/strategy_v13_kb115lt2_harvest_exchange'
    target=study/'candidates'/IDENTIFIER
    assert not target.exists(), 'Never replace a candidate'
    assert sha(source/'manifest.json')==V13
    old=read(source/'manifest.json')
    assert old['protocol_sha256']==sha(study/'protocol.json')
    audit=read(AUDIT/'static_audit.json');binding=read(AUDIT/'manifest.json')
    assert audit['off_full_proposals_equal']==audit['off_public_states_equal']==audit['recorded_today_reproduced']==192
    assert binding['pure_tests_passed']==14 and binding['new_games']==0
    for name, expected in binding['files'].items(): assert sha(Path(name))==expected,name
    for name, expected in REPLACEMENTS.items(): assert sha(ROOT/name)==expected,name
    # Static OFF proof used V8. V13 retained those exact policy/model bytes.
    v8=study/'candidates/strategy_v8_kb115lt2_readiness/project'
    for name in ('scripts/semantic_strategy_policy_20260928.py','scripts/semantic_strategy_blocks_20260928.py',
                 'results/fresh/semantic_strategy_20260928/block_model_modern100.json'):
        assert sha(v8/name)==old['files'][name],name
    for folder,key in (('project','files'),('harness','harness_files')):
        for name,expected in old[key].items():
            original=source/folder/name;assert sha(original)==expected,name
            new=target/folder/name;new.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(original,new)
    for name in REPLACEMENTS: shutil.copy2(ROOT/name,target/'project'/name)
    config_path=target/'project'/CONFIG
    config=read(config_path);previous=copy.deepcopy(config)
    assert 'forecast_fertilizer_net' not in config['policy']
    config['policy']['forecast_fertilizer_net']=True
    reverse=copy.deepcopy(config);del reverse['policy']['forecast_fertilizer_net'];assert reverse==previous
    config_path.write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
    evidence={}
    evidence_sources=[AUDIT/'static_audit.json',AUDIT/'report.md',AUDIT/'manifest.json',
                      ROOT/'tests/test_semantic_fertilizer_net_20260928.py',
                      ROOT/'scripts/audit_semantic_fertilizer_net_20260928.py',Path(__file__).resolve()]
    (target/'evidence').mkdir()
    for path in evidence_sources:
        new=target/'evidence'/path.name;shutil.copy2(path,new);evidence['evidence/'+path.name]=sha(new)
    result=copy.deepcopy(old)
    result.update(candidate_id=IDENTIFIER,created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    result['files'].update(REPLACEMENTS);result['files'][CONFIG]=sha(config_path)
    changes={name:dict(v13=old['files'].get(name),v14=value)
             for name,value in result['files'].items() if value!=old['files'].get(name)}
    assert set(changes)==set(REPLACEMENTS)|{CONFIG}
    result['derived_from']=dict(candidate=source.name,manifest_sha256=V13,only_source_changes=changes,
        config_changes={'policy.forecast_fertilizer_net':True},evidence_sha256=evidence,
        executor_entry_model_tiler_recipe_harness_unchanged=True,
        status_at_freeze='PREPARED_UNRELEASED: no game dispatch authorized by this artifact',
        rationale='Net internal fertilizer use in current-cohort market forecast and consistent crop input costs; no retirement-bank, reveal or suffix-cash change.',
        limitations=['Future crop rotations absent','Suffix cash still gross at current-dawn prices',
                     'Added-cohort fertilizer consumption not accumulated in marginal market externality'])
    write(target/'manifest.json',result)
    # Import-only preflight: initialize static artifacts, never call an action.
    sys.dont_write_bytecode=True
    for name in result['files']:
        if name.endswith('.py'): ast.parse((target/'project'/name).read_text(encoding='utf-8'))
    spec=importlib.util.spec_from_file_location('_v14_import_preflight',target/'project'/result['entry'])
    entry=importlib.util.module_from_spec(spec);spec.loader.exec_module(entry)
    state=entry._initialize()
    assert state['policy'].config['forecast_fertilizer_net'] is True
    assert state['config']==config and state['config']['policy_kind']=='three_day_budget'
    helper=__import__('semantic_strategy_fertilizer_net_20260928')
    origins={name:str(Path(sys.modules[name].__file__).resolve()) for name in
        ('semantic_strategy_policy_20260928','semantic_strategy_blocks_20260928',
         'semantic_strategy_tiles_20260928','semantic_strategy_fertilizer_net_20260928')}
    project=(target/'project').resolve()
    for name,path in origins.items(): assert Path(path).is_relative_to(project),(name,path)
    for name,expected in result['files'].items(): assert sha(project/name)==expected,name
    proof=dict(candidate=IDENTIFIER,manifest_sha256=sha(target/'manifest.json'),
        reference_manifest_sha256=V13,status='PREPARED_UNRELEASED',engine_dispatched=False,
        source_differences=changes,config_changes={'policy.forecast_fertilizer_net':True},
        harness_differences={},entry_import_and_static_initialization_pass=True,module_origins=origins,
        off_equivalence_to_v8_and_byte_identical_v13_policy=dict(full_proposals=192,public_states=192),
        pure_tests_passed=14,game_dispatch_authorization=False)
    write(target/'preflight.json',proof)
    print(json.dumps(proof,indent=2))


if __name__=='__main__': main()
