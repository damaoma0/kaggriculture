"""Verify critical scheduler mechanics against the official game engine."""
from copy import deepcopy
import json
from evaluate_boards import ROOT,module_at,observation


def main():
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    splits=json.loads((ROOT/'results/fresh/midgame/splits.json').read_text())['splits']
    replay=json.loads(open(splits['train'][0]['path'],encoding='utf-8').read())
    obs=observation(replay['steps'][-1],0)
    mod=module_at('test_mid',ROOT/'agents/midgame_v1.py')
    actual={a:sum(1 for row in obs['farms'][0]['tiles'] for t in row if isinstance(t,dict) and t.get('animal')==a) for a in ('COW','SHEEP')}
    added=mod.Midgame(obs,{'extra_cows':4,'extra_sheep':4})
    assert added.herd['COW']==actual['COW']+4 and added.herd['SHEEP']==actual['SHEEP']+4
    farm=obs['farms'][0];farm['tiles']=[['LOCKED']*10 for _ in range(10)];farm['farmer']=[4,4];farm['hands']=[]
    farm['tiles'][4][4]=E._new_plant('STRAWBERRY',0,24)
    farm['tiles'][4][4]['consecutive_unwatered']=0
    obs['private']['inventories']=[{'FERTILIZER':1}];obs['private']['shed']={};obs['private']['seeds']={}
    policy=mod.Midgame(obs,{'fertilizer':'apply','hands_cap':0,'replant':None})
    before=deepcopy(obs);a=policy(obs)
    assert obs==before and a['farmer']==['FERTILIZE'],a
    E._apply_unit_action(farm,obs['private'],0,a['farmer'],10,9,24)
    a=policy(obs);assert a['farmer']==['WATER'],a
    E._apply_unit_action(farm,obs['private'],0,a['farmer'],10,9,24)
    E._daily_refresh_plants(farm,9,24)
    assert farm['tiles'][4][4]['yield_units']==2
    # An expiring-water deadline must override an optional fertilizer trip.
    farm['tiles'][4][4]=E._new_plant('STRAWBERRY',0,24)
    obs['private']['inventories']=[{}];obs['private']['shed']={'FERTILIZER':8}
    obs['hour']=23;obs['step']=239
    assert policy(obs)['farmer']==['WATER']
    print('PASS: no observation mutation; fertilizer then water produces two strawberries; survival overrides fertilizer pickup.')


if __name__=='__main__':main()
