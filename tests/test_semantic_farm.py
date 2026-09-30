"""Module gates and full-interpreter parity for the integrated architecture."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import json,sys,time,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from semantic_farm.common import E,physical_key
from semantic_farm.care import existing_jobs,establishment_jobs,choose_service,job_chain
from semantic_farm.layout import assign,service_load
from semantic_farm.economics import quantity_value,market_scenarios,reserve_plan
from semantic_farm.execution import batch,advance,financial_orders
from semantic_farm.model import DecisionModel
from semantic_farm.policy import SemanticFarm
from run_semantic_farm import Dot,rules


def observation(day=0):
    return Dot(step=24*day,day=day,hour=0,player=0,farms=[E._new_farm(10,3000),E._new_farm(10,3000)],
        private=E._new_private(),market=E._new_market(),town=E._new_town())


def interpreter_actions(obs,actions):
    import types
    e=rules();a=deepcopy(obs);b=Dot(a,player=1,private=E._new_private())
    states=[Dot(observation=a,status='ACTIVE',reward=None),Dot(observation=b,status='ACTIVE',reward=None)]
    env=types.SimpleNamespace(done=False,info={'seed':1},configuration=Dot(episodeSteps=720,
        boardSize=10,turnsPerDay=24,shedCapacity=100,maxMarketOrdersPerTurn=10,farmHandCostMult=1,
        weedSpawnChance=0,townShopUnlockInterval=10000))
    for at,action in enumerate(actions):
        for s in states:s.observation.step=obs['step']+at
        states[0].action=deepcopy(action);states[1].action={'farmer':['PASS'],'market':[],'hands':[]}
        e.interpreter(states,env)
    return states[0].observation


class ModuleTests(unittest.TestCase):
    def test_local_entry_loads_without_file_global(self):
        from kaggle_environments.agent import get_last_callable
        path=ROOT/'agents/semantic_farm.py'
        entry=get_last_callable(path.read_text(encoding='utf8'),path=str(path))
        action=entry(observation())
        self.assertIn('farmer',action);self.assertIn('market',action)

    def test_expert_proposals_do_not_buy_missing_historical_cohorts(self):
        model=DecisionModel();obs=observation(12)
        for proposal in model.proposals(obs):
            source=next(r for r in model.rows if r['episode']==proposal['source_episode'] and r['day']==12)
            for s,n in proposal['quantities'].items():
                self.assertLessEqual(n,source['additions'].get(s,0))

    def test_future_service_rejects_overloaded_farm(self):
        obs=observation(12)
        for y in range(10):
            for x in range(10):obs.farms[0]['tiles'][y][x]=E._new_animal('COW',10)
        result=SemanticFarm().future_service(obs,time.perf_counter()+1)
        self.assertFalse(result['ok']);self.assertEqual(result['reason'],'future_labor_peak')

    def test_future_service_checks_final_day_delivery(self):
        obs=observation(29);obs.farms[0]['tiles'][4][4]=E._new_animal('COW',25)
        obs.farms[0]['tiles'][4][4]['yield_units']=2
        result=SemanticFarm().future_service(obs,time.perf_counter()+1)
        self.assertTrue(result['ok'],result)
        # The last playable hour is 22; the final projection is day 29/hour 23.
        self.assertEqual(result['checked_through_day'],29)

    def test_final_day_output_is_dropped_and_sold_before_terminal(self):
        obs=observation(29);tile=E._new_animal('COW',25);tile['yield_units']=2
        obs.farms[0]['tiles'][4][4]=tile
        jobs=job_chain((4,4),[['HARVEST']],tile)
        result=batch(obs,jobs,1,deadline=time.perf_counter()+1)
        self.assertTrue(result['ok'],result)
        official=interpreter_actions(obs,result['actions'])
        self.assertEqual(official.farms[0]['money'],result['end']['farms'][0]['money'])
        self.assertGreater(official.farms[0]['money'],3000)
        self.assertEqual(official.private['inventories'][0].get('MILK',0),0)

    def test_model_never_establishes_assets_maturing_after_season(self):
        model=DecisionModel();obs=observation(28)
        for row in model.proposals(obs):
            for s,n in row['quantities'].items():
                self.assertLessEqual(28+(E.CROPS[s]['first_yield_day'] if s in E.CROPS else E.ANIMALS[s]['first_yield_day']),29)

    def test_shop_features_change_proposals_without_future_input(self):
        model=DecisionModel();obs=observation(12)
        obs.farms[0]['money']=5000
        a=model.proposals(obs,exclude_episode=112802103)
        obs.town['unlocked_shops']=['YARN_STORE']*4
        b=model.proposals(obs,exclude_episode=112802103)
        self.assertNotEqual(a,b)
        self.assertTrue(all(r['source_episode']!=112802103 for r in a+b))

    def test_service_load_accounts_for_future_strawberry_replacement(self):
        obs=observation();placed=assign(obs,{'WHEAT':2,'MELON':2})
        self.assertEqual([r['species'] for r in placed[:2]],['WHEAT','WHEAT'])
        self.assertGreater(service_load('COW',0),service_load('MELON',0))

    def test_layout_does_not_destroy_productive_crop(self):
        obs=observation(12);obs.farms[0]['tiles'][4][4]=E._new_plant('STRAWBERRY',2,24)
        placed=assign(obs,{'SHEEP':1})
        self.assertNotEqual(placed[0]['tile'],[4,4])

    def test_fertilizer_remains_default_when_marginal_output_is_valuable(self):
        tile=E._new_plant('STRAWBERRY',0,24)
        prices=dict(E._new_market()['prices'],FERTILIZER=1,STRAWBERRY=300)
        commands,_=choose_service(tile,9,prices)
        self.assertIn(['FERTILIZE'],commands)

    def test_market_value_rejects_nonproductive_late_animal(self):
        obs=observation(29)
        value=quantity_value(obs,{'COW':1})
        self.assertLess(value['high'],0)

    def test_more_revealed_yarn_increases_wool_demand_forecast(self):
        obs=observation(12)
        a=market_scenarios(obs)
        obs.town['unlocked_shops']=['YARN_STORE']*4
        b=market_scenarios(obs)
        self.assertLess(b[1][13]['WOOL'],a[1][13]['WOOL'])

    def test_future_funding_reserve_increases_with_crew(self):
        obs=observation(15)
        self.assertGreater(reserve_plan(obs,12)['reserve'],reserve_plan(obs,5)['reserve'])

    def test_market_procurement_cannot_spend_next_morning_reserve(self):
        obs=observation();obs.farms[0]['money']=100
        jobs=[dict(tile=[4,4],cmd=['PLANT','STRAWBERRY'])]
        self.assertIsNone(financial_orders(obs,jobs,1,1))
        self.assertEqual(financial_orders(obs,jobs,1,0),[['BUY_SEED','STRAWBERRY',1]])

    def test_harvest_plant_water_chain_is_executed_in_one_visit(self):
        obs=observation(3)
        wheat=E._new_plant('WHEAT',0,24);wheat['yield_units']=3
        obs.farms[0]['tiles'][4][4]=wheat
        jobs=job_chain((4,4),[['HARVEST'],['PLANT','STRAWBERRY'],['WATER']],wheat)
        result=batch(obs,jobs,1,deadline=time.perf_counter()+2)
        self.assertTrue(result['ok'],result)
        official=interpreter_actions(obs,result['actions'])
        self.assertEqual(official.farms[0],result['end']['farms'][0])
        self.assertEqual(official.private,result['end']['private'])
        self.assertEqual(official.farms[0]['tiles'][4][4]['crop'],'STRAWBERRY')
        self.assertTrue(official.farms[0]['tiles'][4][4]['watered_today'])

    def test_funding_collection_finances_seed_purchase(self):
        obs=observation(2);obs.farms[0]['money']=1
        tile=E._new_animal('COW',0);tile['fertilizer_available']=True
        obs.farms[0]['tiles'][4][4]=tile
        jobs=job_chain((4,4),[['COLLECT_FERTILIZER']],tile)
        result=batch(obs,jobs,1,collect=True,deadline=time.perf_counter()+2)
        self.assertTrue(result['ok'],result)
        self.assertGreater(result['end']['farms'][0]['money'],90)
        follow=batch(result['end'],[dict(tile=[3,4],cmd=['PLANT','WHEAT'])],1,deadline=time.perf_counter()+2)
        self.assertTrue(follow['ok'],follow)

    def test_failed_feed_is_not_counted_as_completed(self):
        obs=observation(3)
        jobs=[dict(tile=[4,4],cmd=['FEED'])] # deliberately no animal
        result=batch(obs,jobs,1,deadline=time.perf_counter()+2)
        self.assertFalse(result['ok']);self.assertEqual(result['reason'],'unfulfilled_job')

    def test_land_projection_matches_full_interpreter(self):
        obs=observation(8);action={'farmer':['PASS'],'hands':[],'market':[['BUY_LAND']]}
        result,report=advance(obs,action)
        actual=interpreter_actions(obs,[action])
        self.assertFalse(report['failures'])
        self.assertEqual(actual.farms[0],result['farms'][0])

    def test_projection_does_not_mutate_input_or_global_engine(self):
        obs=observation();original=deepcopy(obs);fn=E._commit_unit
        batch(obs,[dict(tile=[4,4],cmd=['PLANT','WHEAT'])],1,deadline=time.perf_counter()+2)
        self.assertEqual(original,obs);self.assertIs(E._commit_unit,fn)

    def test_plan_repairs_displaced_worker_instead_of_replaying_stale_route(self):
        obs=observation();agent=SemanticFarm();agent(obs)
        result,_=advance(obs,agent.actions[0])
        result.farms[0]['farmer']=[0,0]
        agent(result)
        self.assertEqual(agent.stats['state_repairs'],1)


if __name__=='__main__':unittest.main()
