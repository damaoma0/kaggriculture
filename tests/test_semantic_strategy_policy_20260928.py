import ast
from copy import deepcopy
import json
import math
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import semantic_strategy_policy_20260928 as P


def observation(day=12,crops=(),animals=(),structures=0):
    tiles=[[None for _ in range(10)] for _ in range(10)]
    index=0
    for s,b,n in crops:
        for _ in range(n):
            tiles[index//10][index%10]=dict(kind='PLANT',crop=s,planted_day=b,yield_units=6);index+=1
    for s,b,n in animals:
        for _ in range(n):
            tiles[index//10][index%10]=dict(kind=P.ANIMALS[s]['structure'],animal=s,placed_day=b,yield_units=0);index+=1
    for _ in range(structures):
        tiles[index//10][index%10]=dict(kind='PASTURE');index+=1
    own=dict(tiles=tiles,money=50000,unlocked_quadrants=['NW'],hands=[])
    rival=dict(tiles=[[None for _ in range(10)] for _ in range(10)],money=50000,unlocked_quadrants=['NW'],hands=[])
    return dict(day=day,hour=0,step=day*24,player=0,farms=[own,rival],town={'unlocked_shops':['YARN_STORE','PET_CAFE','BAKERY','SMOOTHIE_SHOP'][:day//3]},
                market=dict(prices={p:100 for p in P.PRODUCTS},inventory={p:10000 for p in P.PRODUCTS}),private=dict(shed={},inventories=[{}]))


def row(day=12,plants=None,end=None,animals=None,retire=None):
    return dict(day=day,meta=dict(episode=123,seed=9,reward=999),features=dict(shops_prefix=['YARN_STORE','PET_CAFE','BAKERY','SMOOTHIE_SHOP'][:day//3],
        own_crop_cohorts=[],own_animal_cohorts=[],own_structures={},cash=50000,owned_quadrants=1),target=dict(plant_counts=plants or {},
        end_crop_counts=end or plants or {},animal_add_counts=animals or {},end_animal_counts=animals or {},animal_retire_counts=retire or {},hands=10,land_add_count=0,owned_quadrants=1))


class PolicyTests(unittest.TestCase):
    def policy(self,r,**config):
        return P.SemanticStrategyPolicy({'rows':[r]},dict(forecast=False,**config))

    def test_mature_wheat_does_not_suppress_replant(self):
        obs=observation(crops=[('WHEAT',9,5),('WHEAT',11,5)])
        result=self.policy(row(plants={'WHEAT':5},end={'WHEAT':10})).propose(obs)
        self.assertEqual(result['today']['plant_counts'],{'WHEAT':5})
        self.assertEqual(result['today']['target_crop_counts'],{'WHEAT':10})

    def test_existing_young_cohorts_suppress_duplicate_investment(self):
        obs=observation(crops=[('WHEAT',11,15)])
        self.assertEqual(self.policy(row(plants={'WHEAT':5},end={'WHEAT':10})).propose(obs)['today']['plant_counts'],{})

    def test_retiring_animals_remain_occupied(self):
        obs=observation(animals=[('COW',0,25)])
        r=row(plants={'WHEAT':5},retire={'COW':5});r['target']['end_animal_counts']={'COW':25}
        result=self.policy(r).propose(obs)['today']
        self.assertEqual(result['animal_retire_counts'],{'COW':5})
        self.assertEqual(result['plant_counts'],{})
        self.assertEqual(result['modeled_free_tiles'],0)

    def test_retirement_guard_allows_donor_intended_active_herd_reduction(self):
        obs=observation(animals=[('SHEEP',0,5)])
        r=row(retire={'SHEEP':2});r['target']['end_animal_counts']={'SHEEP':5}
        p=self.policy(r,retirement_active_target_guard=True)
        self.assertEqual(p.propose(obs)['today']['animal_retire_counts'],{'SHEEP':2})
        obs=observation(animals=[('SHEEP',0,4)])
        self.assertEqual(p.propose(obs)['today']['animal_retire_counts'],{'SHEEP':1})
        memory={'committed_retirement_counts':{'SHEEP':1}}
        self.assertEqual(p.propose(obs,memory)['today']['animal_retire_counts'],{})

    def test_guard_prevents_repeated_donor_retirements_before_and_after_exit(self):
        rows=[]
        for d in range(18,30):
            r=row(day=d,retire={'SHEEP':1});r['target']['end_animal_counts']={'SHEEP':3};rows.append(r)
        p=P.SemanticStrategyPolicy({'rows':rows},dict(retirement_active_target_guard=True))
        result=p.propose(observation(day=18,animals=[('SHEEP',0,3)]))
        self.assertEqual(result['forecast'][0]['animal_retire_counts'],{'SHEEP':1})
        self.assertTrue(all(not r['animal_retire_counts'] for r in result['forecast'][1:]))
        self.assertEqual([r['target_animals']['SHEEP'] for r in result['forecast'][:3]],[3,3,2])
        known=p.propose(observation(day=18,animals=[('SHEEP',0,3)]),
            {'committed_retirement_counts':{'SHEEP':1}})
        self.assertTrue(all(not r['animal_retire_counts'] for r in known['forecast']))
        self.assertEqual([r['target_animals']['SHEEP'] for r in known['forecast'][:3]],[3,3,2])
        self.assertTrue(all(not r['animal_add_counts'] for r in known['forecast']))

    def test_accidental_unfed_animal_is_not_committed_retirement(self):
        obs=observation(animals=[('SHEEP',0,3)])
        obs['farms'][0]['tiles'][0][0]['consecutive_unfed']=1
        r=row(retire={'SHEEP':1});r['target']['end_animal_counts']={'SHEEP':3}
        p=self.policy(r,retirement_active_target_guard=True)
        self.assertEqual(p.propose(obs)['today']['animal_retire_counts'],{'SHEEP':1})
        self.assertEqual(p.propose(obs,{'committed_retirement_counts':{'SHEEP':1}})
                         ['today']['animal_retire_counts'],{})

    def test_retirement_guard_is_off_by_default_and_commitments_are_not_capacity(self):
        obs=observation(animals=[('SHEEP',0,25)])
        r=row(plants={'WHEAT':5},retire={'SHEEP':1});r['target']['end_animal_counts']={'SHEEP':25}
        memory={'committed_retirement_counts':{'SHEEP':1,'UNKNOWN':99}}
        self.assertEqual(self.policy(r).propose(obs,memory)['today']['animal_retire_counts'],{'SHEEP':1})
        guarded=self.policy(r,retirement_active_target_guard=True).propose(obs,memory)['today']
        self.assertEqual(guarded['animal_retire_counts'],{})
        self.assertEqual(guarded['plant_counts'],{})
        self.assertEqual(guarded['modeled_free_tiles'],0)

    def test_empty_pens_can_be_reclaimed(self):
        obs=observation(structures=25)
        result=self.policy(row(plants={'WHEAT':5})).propose(obs)['today']
        self.assertEqual(result['plant_counts'],{'WHEAT':5})
        self.assertEqual(result['remove_structure_counts'],{'PASTURE':5})

    def test_no_useless_late_animal_purchase(self):
        obs=observation(day=25)
        result=self.policy(row(day=25,animals={'COW':3,'GOOSE':2})).propose(obs)['today']
        self.assertEqual(result['animal_add_counts'],{})

    def test_future_identity_and_coordinates_are_not_runtime_features(self):
        obs=observation();r=row(plants={'WHEAT':5});before=deepcopy(obs)
        a=self.policy(r).propose(obs)
        obs.update(episode=999,seed=333,actual_future_shops=['PET_CAFE']*8,reward=-999999)
        r['meta'].update(episode=888,reward=-100000)
        r['features']['future_shops']=['YARN_STORE']*8
        r['target']['source_tiles']=[99,98,97]
        b=self.policy(r).propose(obs)
        self.assertEqual(a,b)
        self.assertEqual(before['farms'],obs['farms'])
        changed=deepcopy(before);changed['farms'][0]['tiles']=list(reversed(changed['farms'][0]['tiles']))
        self.assertEqual(a,self.policy(r).propose(changed))

    def test_public_rival_harvest_and_consumption_accounting(self):
        obs=observation();obs['hour']=1;obs['step']=289
        obs['farms'][1]['tiles'][0][0]=dict(kind='PASTURE',animal='SHEEP',placed_day=0,yield_units=6,fed_today=False,cared_today=False)
        memory=P.observe(obs)
        nxt=deepcopy(obs);nxt['hour']=2;nxt['step']=290
        nxt['farms'][1]['tiles'][0][0].update(yield_units=0,fed_today=True,cared_today=True)
        nxt['market']['inventory']['WOOL']+=4
        memory=P.observe(nxt,memory,{'market':[['SELL','WOOL',99]]})
        h=memory['public_history']['12']
        self.assertEqual(h['rival_harvest']['WOOL'],6)
        self.assertEqual(h['rival_feed']['SHEEP'],1)
        self.assertEqual(h['combined_net_market']['WOOL'],4)
        self.assertNotIn('rival_net_market',h)
        self.assertEqual(P.observe(nxt,memory),memory)

    def test_visible_rival_cohorts_change_economic_estimate(self):
        obs=observation();r=row(plants={'WHEAT':2})
        a=self.policy(r).propose(obs)['diagnostics']['cohort_values']['SHEEP']
        for i in range(20):
            obs['farms'][1]['tiles'][i//10][i%10]=dict(kind='PASTURE',animal='SHEEP',placed_day=0)
        b=self.policy(r).propose(obs)['diagnostics']['cohort_values']['SHEEP']
        self.assertNotEqual(a,b)

    def test_visible_first_harvest_finances_daily_capital(self):
        obs=observation(day=6,animals=[('SHEEP',0,3)]);obs['farms'][0]['money']=200
        obs['market']['prices']['WOOL']=220
        for i in range(3):obs['farms'][0]['tiles'][0][i].update(yield_units=6,fertilizer_available=True)
        r=row(day=6,animals={'COW':4});r['target']['end_animal_counts']={'COW':4,'SHEEP':3}
        result=self.policy(r).propose(obs)['today']
        self.assertEqual(result['animal_add_counts'],{'COW':4})
        self.assertGreater(result['estimated_capital_cost'],200)

    def test_joint_supply_value_accounts_for_shared_price_impact(self):
        obs=observation(day=12);state=P.public_state(obs);cfg=dict(P.DEFAULT_CONFIG)
        paths,rival=P.forecast_market(state,cfg)
        values={s:P.cohort_value(state,s,paths,rival,cfg) for s in (*P.CROPS,*P.ANIMALS)}
        choice={'plant_counts':{'STRAWBERRY':20},'animal_add_counts':{}}
        joint=P.bundle_value(state,choice,paths,rival,cfg,values)
        self.assertLess(joint,20*values['STRAWBERRY'])

    def test_feed_reduces_projected_wheat_inventory_for_both_farms(self):
        obs=observation();state=P.public_state(obs);cfg=dict(P.DEFAULT_CONFIG)
        none,_=P.forecast_market(state,cfg)
        state['own_animal_cohorts']=[dict(species='SHEEP',birth=0,count=3)]
        state['rival_animal_cohorts']=[dict(species='COW',birth=0,count=4)]
        herd,_=P.forecast_market(state,cfg)
        self.assertEqual(none[12]['WHEAT']-herd[12]['WHEAT'],7)
        self.assertEqual(none[14]['WHEAT']-herd[14]['WHEAT'],21)
        state['stock']={'WHEAT':6}
        stocked,_=P.forecast_market(state,cfg)
        self.assertEqual(stocked[12]['WHEAT']-herd[12]['WHEAT'],3)
        self.assertEqual(stocked[14]['WHEAT']-herd[14]['WHEAT'],6)

    def test_low_yield_observed_wheat_defers_one_day_but_ready_wheat_releases(self):
        obs=observation(crops=[('WHEAT',9,2)])
        obs['farms'][0]['tiles'][0][0]['yield_units']=1
        obs['farms'][0]['tiles'][0][1]['yield_units']=5
        state=P.public_state(obs)
        self.assertEqual(P.crop_survivors(state['own_crop_cohorts'],12),{'WHEAT':1})
        self.assertEqual(P.crop_survivors(state['own_crop_cohorts'],13),{})
        out=P.output_calendar(state['own_crop_cohorts'],[],12)
        self.assertEqual(out[12]['WHEAT'],5)
        self.assertEqual(out[13]['WHEAT'],6)

    def test_feed_rotation_option_is_off_by_default_and_bounded(self):
        obs=observation(animals=[('COW',0,10)])
        r=row();r['target']['end_animal_counts']={'COW':10}
        base=self.policy(r).propose(obs)['today']
        option=self.policy(r,wheat_reserve_days=6,wheat_reserve_max_add=4).propose(obs)['today']
        self.assertEqual(base['plant_counts'],{})
        self.assertEqual(option['plant_counts'],{'WHEAT':4})
        self.assertEqual(option['wheat_reserve_extra_requested'],4)

    def test_reserve_window_is_exact_feed_nights_and_excludes_committed_herd(self):
        obs=observation(animals=[('COW',0,1)]);obs['private']['shed']={'WHEAT':9}
        r=row();r['target']['end_animal_counts']={'COW':1}
        cfg=dict(wheat_reserve_days=6,wheat_reserve_max_add=4)
        exact=self.policy(r,**cfg).propose(obs)['today']
        self.assertEqual(exact['wheat_reserve_extra_requested'],0)  # six feeds + buffer three
        obs=observation(animals=[('COW',0,3)]);obs['private']['shed']={'WHEAT':12}
        r['target']['end_animal_counts']={'COW':2}
        cfg.update(retirement_active_target_guard=True,wheat_reserve_buffer=0)
        known=self.policy(r,**cfg).propose(obs,{'committed_retirement_counts':{'COW':1}})['today']
        self.assertEqual(known['animal_retire_counts'],{})
        self.assertEqual(known['animal_add_counts'],{})
        self.assertEqual(known['wheat_reserve_extra_requested'],0)  # six feeds for two active cows

    def test_land_cap_never_removes_observed_owned_land(self):
        obs=observation();obs['farms'][0]['unlocked_quadrants']=['NW','NE','SW','SE']
        out=self.policy(row(),land_limit=3).propose(obs)['today']
        self.assertEqual(out['target_land_count'],4)
        self.assertEqual(out['land_add_count'],0)
        self.assertEqual(out['modeled_free_tiles'],100)

    def test_reserve_promotes_only_extra_lots_and_honors_start_day(self):
        obs=observation(crops=[('STRAWBERRY',10,20)],animals=[('COW',0,3)])
        r=row(plants={'WHEAT':2,'STRAWBERRY':1},end={'WHEAT':2,'STRAWBERRY':21})
        r['target']['end_animal_counts']={'COW':3}
        p=self.policy(r,wheat_reserve_days=6,wheat_reserve_max_add=1,wheat_reserve_buffer=0)
        chosen=p._proposal(P.public_state(obs),p.byday[12][0],{'WHEAT':0,'STRAWBERRY':1000})
        self.assertEqual(chosen['wheat_reserve_extra_requested'],1)
        self.assertEqual(chosen['plant_counts'],{'WHEAT':1,'STRAWBERRY':1})
        p.config['wheat_reserve_start_day']=15
        delayed=p._proposal(P.public_state(obs),p.byday[12][0],{'WHEAT':0,'STRAWBERRY':1000})
        self.assertEqual(delayed['wheat_reserve_extra_requested'],0)

    def test_ordinary_service_yield_is_five_wheat_and_six_melon(self):
        output=P.output_calendar([dict(crop='WHEAT',birth=12,count=1),dict(crop='MELON',birth=12,count=1)],[],12)
        self.assertEqual(output[15]['WHEAT'],5)
        self.assertEqual(output[22]['MELON'],6)

    def test_price_curves_match_official_engine_without_running_games(self):
        path=ROOT/'.venv/Lib/site-packages/kaggle_environments/envs/kaggriculture/kaggriculture.py'
        tree=ast.parse(path.read_text(encoding='utf-8'))
        names={'MARKET_PARAMS','MARKET_I0','PRICE_FLOOR','HINGE_GAIN'}
        nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('_shape','market_price') or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in names for t in n.targets)]
        ns={'math':math};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),ns)
        for p in P.PRODUCTS:
            for inv in (9000,9700,9999,10000,10001,10100,10500):
                self.assertEqual(P.market_price(p,inv),ns['market_price'](p,inv),(p,inv))


if __name__=='__main__':unittest.main()
