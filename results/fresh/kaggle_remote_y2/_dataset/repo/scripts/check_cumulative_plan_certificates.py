"""Independent arithmetic/identity audit of rendered aggregate plan certificates."""
import ast
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/cumulative_planning'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main(guarded=False):
    from cumulative_engine_profiles import ENGINE,validate_profiles
    paths=[ROOT/'data/kaggriculture.py',ROOT/'.venv/Lib/site-packages/kaggle_environments/envs/kaggriculture/kaggriculture.py']
    funcs=['_apply_unit_action','_daily_refresh_plants','_daily_refresh_animals','_decay_plants','_new_plant','_new_animal']
    nodes=[{n.name:ast.dump(n,include_attributes=False) for n in ast.parse(p.read_text(encoding='utf-8')).body if isinstance(n,ast.FunctionDef)} for p in paths]
    for f in funcs:assert nodes[0][f]==nodes[1][f],f
    profile=validate_profiles();checks=[]
    case_dir='cases_guarded' if guarded else 'cases';suffix='_guarded' if guarded else ''
    for path in sorted((OUT/f'plans/{case_dir}').glob('*.json')):
        case=read(path);snapshot=case['snapshot'];start=case['day'];cash=snapshot['cash']
        for mode,plan in case['modes'].items():
            if 'error' in plan:continue
            stock=Counter(WHEAT=snapshot['wheat'],FERTILIZER=snapshot['fertilizer']);stock.update(plan['procurement'])
            seeds=Counter(snapshot['seeds']);new=Counter();animals=Counter();cumulative=Counter()
            for day,row in plan['daily'].items():
                assert row['land_used']<=snapshot['land_capacity'],(path.name,mode,day,'land')
                assert row['workload']<=row['action_capacity_after_travel'],(path.name,mode,day,'work')
                new.update(row['plant']);animals.update(row['buy_animal']);stock.update({p:q for p,q in row['expected_output'].items() if p in ['WHEAT','FERTILIZER']})
                stock.subtract(row['expected_inputs']);cumulative.update(row['expected_output'])
                assert stock['WHEAT']>=0 and stock['FERTILIZER']>=0,(path.name,mode,day,'stock',stock)
            cost=plan['labor']['total_hire_cost']+sum(new[p]*ENGINE.CROPS[p]['seed'] for p in new)+sum(animals[a]*ENGINE.ANIMALS[a]['cost'] for a in animals)
            cost+=sum(plan['procurement'][p]*snapshot['resource_prices'][p] for p in plan['procurement'])
            assert cost<=cash+1e-6,(path.name,mode,'cash',cost,cash)
            for p,n in new.items():assert n<=seeds[p]+snapshot['seed_purchase_budget'][p]
            for a,n in animals.items():assert n<=snapshot['animal_purchase_budget'][a]
            for t in plan['target_deviations']:
                actual=sum(row['expected_output'].get(t['target']['product'],0) for day,row in plan['daily'].items() if int(day)<t['target']['day'])
                assert actual==t['planned_remaining_units']
                assert actual+t['under']-t['over']==t['requested_remaining_units']
            # Every physical incumbent has one service choice; never disappears
            # for free due to choosing zero in the optimizer.
            groups=Counter()
            for s in plan['selections']:
                if s['decision'].startswith('keep_existing_'):
                    groups[int(s['decision'].split('_')[3])]+=s['quantity']
            incumbent=sum(isinstance(t,dict) and bool(t.get('crop') or t.get('animal')) for row in snapshot['tiles'] for t in row)
            assert len(groups)==incumbent and set(groups.values())=={1}
            checks.append(dict(case=path.name,mode=mode,cost=cost,cash=cash,max_land=max(x['land_used'] for x in plan['daily'].values()),
                highest_workload_ratio=max(x['workload']/x['action_capacity_after_travel'] for x in plan['daily'].values())))
    result=dict(passed=True,mechanics_functions_match_installed_engine=funcs,profile_check_count=len(profile['checks']),
                aggregate_certificates_checked=len(checks),certificates=checks,
                scope='Arithmetic verification of stated aggregate constraints. Does not certify orders, movement, shed space, weeds or actual paths.')
    (OUT/f'plans/certificate_audit{suffix}.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='certificates'},indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--guarded',action='store_true');a=p.parse_args();main(a.guarded)
