"""Mechanics and resource regression checks for cumulative plan inversion."""
import json
from pathlib import Path
from cumulative_engine_profiles import ENGINE,engine_profile,validate_profiles
from cumulative_plan_solver import solve,compile_checkpoint,_daily_capacity

def must_fail(snapshot,targets):
    try:solve(snapshot,targets)
    except RuntimeError:return
    raise AssertionError('unfunded/unsupported physical commitment was accepted')

def main():
    profile=validate_profiles()
    snapshot={'day':12,'season_days':30,'land_capacity':4,'seeds':{'MELON':4},'daily_action_capacity':24}
    impossible=solve(snapshot,[{'day':15,'product':'MELON','units':6},{'day':24,'product':'MELON','units':12}])
    assert impossible['target_deviations'][0]['under']==6 and impossible['routing_feasible'] is None
    out,_,_,_=engine_profile(None,12,30,new_crop='MELON')
    assert out['MELON'][22]==6
    tile=ENGINE._new_plant('WHEAT',0,24)
    early=solve({'day':2,'season_days':6,'land_capacity':1,'tiles':[[tile]],'daily_action_capacity':24},
        [{'day':3,'product':'WHEAT','units':2}])
    assert early['aggregate_feasible'] and early['daily']['2']['expected_output']['WHEAT']==2
    normalized=solve({'day':2,'season_days':6,'land_capacity':1,'cohorts':[{'kind':'crop','type':'WHEAT','planted_day':0}],
        'daily_action_capacity':24},[{'day':3,'product':'WHEAT','units':2}])
    assert normalized['aggregate_feasible']
    cow=ENGINE._new_animal('COW',0)
    must_fail({'day':12,'season_days':15,'land_capacity':1,'tiles':[[cow]],'daily_action_capacity':24},[])
    must_fail({'day':24,'season_days':30,'land_capacity':1,'seeds':{},'cash':0,
               'hire_schedule':{str(d):11 for d in range(24,30)},'daily_action_capacity':24},[])
    assert _daily_capacity({'daily_action_capacity':24,'hire_schedule':{'12':11}},12)==276
    assert _daily_capacity({'daily_action_capacity':24,'hire_schedule':{'29':11}},29)==264
    assert _daily_capacity({'daily_action_capacity':24,'hire_schedule':{'12':21}},12)==495
    assert _daily_capacity({'daily_action_capacity':24,'hire_schedule':{'29':21}},29)==473
    checkpoint={'day':24,'cumulative_output':{},'observation':{'day':24,'player':0,
        'farms':[{'tiles':[[None]],'money':1000}],'private':{'seeds':{'WHEAT':1},'shed':{}}}}
    end=compile_checkpoint(checkpoint,[{'horizon':'end','product':'WHEAT','units':4}])
    assert end['aggregate_feasible']
    fertilizer_only=solve({'day':28,'season_days':30,'land_capacity':1,'cash':2000,'daily_action_capacity':24,
        'animal_purchase_budget':{'SHEEP':1},'feed_purchase_budget':5,'fertilizer_budget':5},
        [{'day':30,'product':'FERTILIZER','units':1}])
    assert fertilizer_only['target_deviations'][0]['under']==1
    assert not any(x['buy_animal'] for x in fertilizer_only['daily'].values())
    result=dict(passed=True,engine_profile_checks=len(profile['checks']),
        regression_checks=['exclusive maturity deadline','existing early harvest','no free animal retirement/feed',
            'no unfunded hires','hire batch capacities11and21','horizon:end API','no fertilizer-only new herd'])
    p=Path('results/fresh/cumulative_planning/plans/solver_validation.json');p.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
