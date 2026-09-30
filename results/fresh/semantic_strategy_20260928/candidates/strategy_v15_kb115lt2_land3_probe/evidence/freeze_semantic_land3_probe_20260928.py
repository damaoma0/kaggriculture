"""Prepare a config-only V15 land3 diagnostic from exact frozen V13; no games."""
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

ROOT=Path(__file__).resolve().parents[1]
IDENTIFIER='strategy_v15_kb115lt2_land3_probe'
BASE='82d5d5a2a3acc181705540a4acf2ed0a764294bba964122d888ec3634cbb0550'
CONFIG='results/fresh/semantic_strategy_20260928/candidate_config.json'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path,value):
    assert not path.exists(),path
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def static_checks(entry,state,project):
    policy=sys.modules['semantic_strategy_policy_20260928'];tiles=sys.modules['semantic_strategy_tiles_20260928']
    text=(project/'agents/semantic_strategy_20260928.py').read_text(encoding='utf-8')
    tree=ast.parse(text)
    branch=next(n for n in ast.walk(tree) if isinstance(n,ast.If)
                and ast.unparse(n.test)=='step < 144')
    assert not any(isinstance(n,ast.Attribute) and n.attr=='propose'
                   for b in branch.body for n in ast.walk(b))
    opening_calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call)
                   and isinstance(n.func,ast.Name) and n.func.id=='make_opening']
    assert len(opening_calls)==1 and not opening_calls[0].args and not opening_calls[0].keywords
    # A funded, empty synthetic farm isolates the geometric admission effect.
    synthetic=dict(day=10,own_crop_cohorts=[],own_animal_cohorts=[],own_structures={},
        owned_quadrants=3,cash=100000,prices={p:100 for p in policy.PRODUCTS},stock={},seeds={})
    request=dict(day=10,features={},target=dict(plant_counts={'WHEAT':90},end_crop_counts={'WHEAT':90},
        end_animal_counts={},hands=6,target_land_count=4))
    values={s:100 for s in (*policy.CROPS,*policy.ANIMALS)}
    capped=state['policy']._proposal(synthetic,request,values)
    assert capped['target_land_count']==3 and capped['land_add_count']==0
    assert capped['plant_counts']=={'WHEAT':75}
    owned4=state['policy']._proposal(dict(synthetic,owned_quadrants=4),request,values)
    assert owned4['target_land_count']==4 and owned4['land_add_count']==0
    assert owned4['plant_counts']=={'WHEAT':90}
    spatial=[]
    for quadrants in (['NW','NE','SW'],['NW','NE','SW','SE']):
        board=[[('LOCKED' if y>=5 and x>=5 and len(quadrants)==3 else {})
                for x in range(10)] for y in range(10)]
        if len(quadrants)==4:
            board[9][9]=dict(kind='PLANT',crop='STRAWBERRY',planted_day=20,yield_units=1)
        farm=dict(tiles=board,unlocked_quadrants=quadrants,hands=[])
        obs=dict(step=27*24,player=0,farms=[farm,{}])
        proposal=dict(forecast=[dict(day=27,plant_counts={'WHEAT':1},target_land_count=3,land_add_count=0,hands=6)])
        plan,_,audit=tiles.build_plan(obs,proposal,{},state['config']['tiles'])
        assert not audit['capacity_adjustments']
        assert plan['board'][27].count(' L')==(25 if len(quadrants)==3 else 0)
        assert all(int(t)//10<5 or int(t)%10<5 for t in plan['plant'][27]) if len(quadrants)==3 else True
        assert ('SE' in plan['land_day'])==(len(quadrants)==4)
        if len(quadrants)==4:assert plan['board'][27][99]=='ST'
        spatial.append(dict(observed_quadrants=len(quadrants),locked_cells=plan['board'][27].count(' L'),
                            new_land_requested=audit['semantic_today']['land_add_count'],
                            fourth_quadrant_retained='SE' in plan['land_day']))
    return dict(opening_branch_before144_unchanged=True,opening_receives_no_policy_config=True,
        synthetic_three_quadrants=dict(target=capped['target_land_count'],land_add=capped['land_add_count'],plants=capped['plant_counts']),
        synthetic_four_already_owned=dict(target=owned4['target_land_count'],land_add=owned4['land_add_count'],plants=owned4['plant_counts']),
        spatial_cases=spatial,engines_invoked=0,full_policy_recomputations=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--study',required=True,type=Path)
    args=parser.parse_args();study=args.study.resolve()
    source=study/'candidates/strategy_v13_kb115lt2_harvest_exchange';target=study/'candidates'/IDENTIFIER
    assert not target.exists(),'Never replace a candidate'
    assert sha(source/'manifest.json')==BASE
    old=read(source/'manifest.json');assert old['protocol_sha256']==sha(study/'protocol.json')
    for folder,key in (('project','files'),('harness','harness_files')):
        for name,expected in old[key].items():
            original=source/folder/name;assert sha(original)==expected,name
            new=target/folder/name;new.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(original,new)
    config_path=target/'project'/CONFIG;config=read(config_path);previous=copy.deepcopy(config)
    assert config['policy']['land_limit']==4
    assert 'forecast_fertilizer_net' not in config['policy'] and config['policy_kind']=='three_day_budget'
    config['policy']['land_limit']=3
    reverse=copy.deepcopy(config);reverse['policy']['land_limit']=4;assert reverse==previous
    config_path.write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
    evidence={};(target/'evidence').mkdir()
    for path in (ROOT/'docs/semantic_land3_probe_20260928.md',Path(__file__).resolve()):
        new=target/'evidence'/path.name;shutil.copy2(path,new);evidence['evidence/'+path.name]=sha(new)
    result=copy.deepcopy(old)
    result.update(candidate_id=IDENTIFIER,created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    result['files'][CONFIG]=sha(config_path)
    changes={name:dict(v13=old['files'][name],v15=value) for name,value in result['files'].items() if value!=old['files'][name]}
    assert set(changes)=={CONFIG} and result['harness_files']==old['harness_files']
    result['derived_from']=dict(candidate=source.name,manifest_sha256=BASE,only_source_changes=changes,
        config_changes={'policy.land_limit':{'before':4,'after':3}},evidence_sha256=evidence,
        all_runtime_sources_model_recipe_harness_unchanged=True,
        status_at_freeze='PREPARED_UNRELEASED: diagnostic only; no dispatch authorized',
        rationale='Prospective farm-scale probe from pre-existing V8 cost/capacity diagnosis; quantities must reshape to75 tiles, not a free land-cost saving.')
    write(target/'manifest.json',result)
    sys.dont_write_bytecode=True
    spec=importlib.util.spec_from_file_location('_v15_import_preflight',target/'project'/result['entry'])
    entry=importlib.util.module_from_spec(spec);spec.loader.exec_module(entry);state=entry._initialize()
    assert state['policy'].config['land_limit']==3 and state['config']==config
    assert not state['policy'].config.get('forecast_fertilizer_net',False)
    assert state['config']['executor']==previous['executor'] and state['config']['tiles']==previous['tiles']
    checks=static_checks(entry,state,target/'project')
    origins={name:str(Path(sys.modules[name].__file__).resolve()) for name in
        ('semantic_strategy_policy_20260928','semantic_strategy_blocks_20260928','semantic_strategy_tiles_20260928')}
    for path in origins.values():assert Path(path).is_relative_to((target/'project').resolve())
    for name,expected in result['files'].items():assert sha(target/'project'/name)==expected,name
    proof=dict(candidate=IDENTIFIER,manifest_sha256=sha(target/'manifest.json'),reference_manifest_sha256=BASE,
        status='PREPARED_UNRELEASED',engine_dispatched=False,game_dispatch_authorization=False,
        source_differences=changes,config_changes={'policy.land_limit':{'before':4,'after':3}},
        harness_differences={},entry_import_and_static_initialization_pass=True,module_origins=origins,static_checks=checks)
    write(target/'preflight.json',proof);print(json.dumps(proof,indent=2))


if __name__=='__main__':main()
