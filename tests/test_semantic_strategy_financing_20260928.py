from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from semantic_strategy_financing_20260928 import capital_pacing_products

BOOKS=['WHEAT','WOOL','MILK','EGG','FERTILIZER','STRAWBERRY']


def fixture(day=6):
    own=dict(tiles=[[None]*10 for _ in range(10)],money=0,hands=[],hires_today=0,unlocked_quadrants=['NW'])
    obs=dict(step=24*day,player=0,farms=[own,{}],private=dict(seeds={},shed={},inventories=[{}]),
        market=dict(prices={'WHEAT':25,'WOOL':200,'MILK':160,'EGG':50,'FERTILIZER':100},
                    inventory={s:10000 for s in BOOKS}))
    plan=SimpleNamespace(plant=[{} for _ in range(30)],animals_by_day=[{} for _ in range(30)],
                         hands=[0]*30,land_day={})
    return obs,plan


def run(obs,plan,state=None,config=None,walk=None):
    cfg=dict(enabled=True,include_hires=False,include_feed=False);cfg.update(config or {})
    return capital_pacing_products(obs,plan,state or {},BOOKS,cfg,
                                   walk or (lambda product,inventory,floor,held:held))


class FinancingTests(unittest.TestCase):
    def test_off_by_default_and_outside_window(self):
        self.assertEqual(capital_pacing_products({},None,None,BOOKS)[0],BOOKS)
        for day in (5,11):
            obs,plan=fixture(day);obs['private']['shed']={'WOOL':10}
            plan.plant[day]={0:'STRAWBERRY'}
            books,diag=run(obs,plan)
            self.assertEqual(books,BOOKS)
            self.assertEqual(diag['reason'],'outside_early_window')
            self.assertEqual(run(obs,plan,config={'start_day':0,'end_day':29})[0],BOOKS)

    def test_bought_but_unplaced_animals_are_not_recounted(self):
        obs,plan=fixture();plan.animals_by_day[6]={0:'COW',1:'COW'}
        obs['private'].update(shed={'COW':1,'WOOL':10},inventories=[{'COW':1}])
        books,diag=run(obs,plan)
        self.assertEqual(diag['remaining_jobs']['animals'],{'COW':2})
        self.assertEqual(diag['remaining_inputs']['animals'],{})
        self.assertEqual(diag['remaining_cost']['animals'],0)
        self.assertEqual(books,BOOKS)

    def test_already_planted_tiles_and_remaining_private_seeds(self):
        obs,plan=fixture();plan.plant[6]={0:'WHEAT',1:'WHEAT',2:'WHEAT'}
        for tile in (0,1):obs['farms'][0]['tiles'][0][tile]=dict(kind='PLANT',crop='WHEAT',planted_day=6)
        obs['private'].update(seeds={'WHEAT':1},shed={'WOOL':10})
        books,diag=run(obs,plan)
        self.assertEqual(diag['remaining_jobs']['plants'],{'WHEAT':1})
        self.assertEqual(diag['remaining_inputs']['seeds'],{})
        self.assertEqual(books,BOOKS)

    def test_whole_lot_floor_guard_and_no_wheat_release(self):
        obs,plan=fixture();plan.plant[6]={0:'STRAWBERRY',1:'STRAWBERRY'}
        obs['private']['shed']={'WOOL':5,'FERTILIZER':1,'WHEAT':100}
        calls=[]
        def walk(p,i,f,n):
            calls.append((p,i,f,n));return n-1 if p=='WOOL' else n
        books,diag=run(obs,plan,walk=walk)
        self.assertIn('WHEAT',books);self.assertIn('WOOL',books)
        self.assertNotIn('FERTILIZER',books)
        self.assertEqual(diag['rejected_lots']['WOOL'],'whole_lot_crosses_price_floor')
        self.assertTrue(all(c[0]!='WHEAT' for c in calls))

    def test_selects_only_sufficient_lots_and_restores_after_funding(self):
        obs,plan=fixture();plan.plant[6]={0:'STRAWBERRY'}
        obs['private']['shed']={'WOOL':10,'MILK':1,'EGG':1,'FERTILIZER':1}
        books,diag=run(obs,plan)
        # Fertilizer + egg = 127.5 estimated proceeds; milk alone = 136.
        self.assertEqual(diag['released_products'],['EGG','FERTILIZER'])
        self.assertAlmostEqual(diag['estimated_excess'],27.5)
        obs['farms'][0]['money']=100
        self.assertEqual(run(obs,plan)[0],BOOKS)

    def test_carried_or_unharvested_goods_do_not_finance(self):
        obs,plan=fixture();plan.plant[6]={1:'STRAWBERRY'}
        obs['private']['inventories']=[{'WOOL':20}]
        obs['farms'][0]['tiles'][0][0]=dict(kind='PASTURE',animal='SHEEP',placed_day=0,yield_units=6)
        books,diag=run(obs,plan)
        self.assertEqual(books,BOOKS);self.assertEqual(diag['reason'],'no_eligible_shed_lot')

    def test_own_remaps_completions_and_blocked_live_animal(self):
        obs,plan=fixture();plan.plant[6]={0:'WHEAT',1:'STRAWBERRY',3:'WHEAT'}
        plan.animals_by_day[6]={4:'COW',5:'GOOSE'}
        obs['farms'][0]['tiles'][0][2]=dict(kind='PLANT',crop='WHEAT',planted_day=6)
        obs['farms'][0]['tiles'][0][1]=dict(kind='PASTURE',animal='COW',placed_day=0)
        obs['farms'][0]['tiles'][0][6]=dict(kind='PASTURE',animal='COW',placed_day=2)
        obs['farms'][0]['tiles'][0][5]=dict(kind='PASTURE',animal='SHEEP',placed_day=2)
        state=dict(pmap={(6,0):2},smap={4:6},done={(6,3)})
        _,diag=run(obs,plan,state)
        self.assertEqual(diag['required_cash'],0)
        self.assertEqual(sum(diag['blocked_jobs'].values()),2)

    def test_unbought_land_and_remaining_hires_feed_costs(self):
        obs,plan=fixture();plan.land_day={'NE':6,'SW':9};plan.hands[6]=3
        obs['farms'][0].update(hands=[[4,4]],hires_today=1)
        for x in (0,1,2):obs['farms'][0]['tiles'][0][x]=dict(kind='PASTURE',animal='COW',placed_day=0,fed_today=x==0)
        obs['private']['inventories']=[{'WHEAT':1}]
        _,diag=run(obs,plan,config={'include_hires':True,'include_feed':True})
        self.assertEqual(diag['remaining_cost'],dict(seeds=0,animals=0,land=1000,hires=3,feed=27))
        obs['farms'][0]['unlocked_quadrants'].append('NE')
        _,diag=run(obs,plan,dict(day=6,_xretire={1:False}),{'include_feed':True})
        self.assertEqual(diag['remaining_cost']['land'],0)
        self.assertEqual(diag['remaining_cost']['feed'],0)

    def test_no_mutation_identity_suffix_or_non_today_plan_reads(self):
        obs,plan=fixture();plan.plant[6]={0:'STRAWBERRY'};obs['private']['shed']={'WOOL':1}
        state=dict(pmap={},smap={},done=set());before=deepcopy((obs,plan.__dict__,state,BOOKS))
        a=run(obs,plan,state)
        self.assertEqual(before,(obs,plan.__dict__,state,BOOKS))
        obs.update(episode=999,seed=123,actual_future_shops=['YARN_STORE']*8,reward=1e9)
        obs['farms'][1]={'private':{'shed':{'WOOL':999999}}}
        class TodayOnly:
            def __init__(self,value):self.value=value
            def __getitem__(self,key):
                if key!=6:raise AssertionError('non-today plan read')
                return self.value
        strict=SimpleNamespace(plant=TodayOnly(plan.plant[6]),animals_by_day=TodayOnly({}),
                               hands=TodayOnly(0),land_day={})
        self.assertEqual(a,run(obs,strict,state))


if __name__=='__main__':unittest.main()
