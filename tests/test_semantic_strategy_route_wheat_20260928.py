from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from semantic_strategy_route_wheat_20260928 import route_wheat_order


def fixture():
    farm=dict(tiles=[[None]*10 for _ in range(10)],farmer=[4,4],hands=[[5,4]],money=100,
              hires_today=0,unlocked_quadrants=['NW'])
    farm['tiles'][4][4]=dict(kind='PASTURE',animal='COW',fed_today=False)
    farm['tiles'][4][5]=dict(kind='PASTURE',animal='SHEEP',fed_today=False)
    obs=dict(step=252,player=0,farms=[farm,{}],private=dict(shed={},inventories=[{}, {'WHEAT':100}]),
             market=dict(inventory={'WHEAT':10000}))
    return obs,dict(farmer=['PASS'],hands=[['PASS']],market=[]),{0:[44,10],1:[45]}


def run(obs,action,routes,**kwargs):
    return route_wheat_order(obs,action,kwargs.pop('state',{}),routes,rolling=True,
        tasks=kwargs.pop('tasks',{44:([['FEED'],['CARE']],{'WHEAT':1},0),45:([['FEED']],{'WHEAT':1},0)}),
        config=dict(enabled=True),price_at=lambda item,inv:25,**kwargs)


class RouteWheatTests(unittest.TestCase):
    def test_default_off_and_exact_local_deficit_no_mutation(self):
        obs,act,routes=fixture();saved=deepcopy((obs,act,routes))
        self.assertEqual(route_wheat_order(obs,act,{},routes)[0],act)
        out,d=run(obs,act,routes)
        self.assertEqual(out['market'],[['BUY_PRODUCT','WHEAT',1]])
        self.assertEqual(d['blocked'],[dict(unit=0,tile=44,animal='COW')])
        self.assertEqual((obs,act,routes),saved)
        self.assertEqual(out['farmer'],act['farmer']);self.assertEqual(out['hands'],act['hands'])

    def test_retirement_false_value_and_intents_defer(self):
        obs,act,routes=fixture()
        for kw in (dict(state={'_xretire':{44:False}}),dict(retirement_intents=[{'tile':45}])):
            self.assertFalse(run(obs,act,routes,**kw)[1]['active'])

    def test_head_observation_and_action_are_required(self):
        for change in ('fed','elsewhere','working','predicted','empty_route'):
            obs,act,routes=fixture()
            if change=='fed':obs['farms'][0]['tiles'][4][4]['fed_today']=True
            if change=='elsewhere':obs['farms'][0]['farmer']=[3,4]
            if change=='working':act['farmer']=['COLLECT_FERTILIZER']
            if change=='predicted':routes[0]=[('W',44)]
            if change=='empty_route':routes[0]=[]
            self.assertFalse(run(obs,act,routes)[1]['active'],change)
        obs,act,routes=fixture()
        self.assertFalse(run(obs,act,routes,tasks={44:([['CARE']],{},0)})[1]['active'])
        self.assertFalse(run(obs,act,routes,tasks=None)[1]['active'])

    def test_hard_day_hour_window_and_rolling_guard(self):
        for step in (143,264,261):
            obs,act,routes=fixture();obs['step']=step
            self.assertFalse(run(obs,act,routes)[1]['active'])
        obs,act,routes=fixture()
        self.assertFalse(route_wheat_order(obs,act,{},routes,config={'enabled':True})[1]['active'])

    def test_cash_does_not_credit_sell_and_reserves_native_spend(self):
        obs,act,routes=fixture();obs['farms'][0]['money']=26
        act['market']=[['SELL','MILK',50]]
        self.assertFalse(run(obs,act,routes)[1]['active'])
        obs['farms'][0]['money']=100;act['market']=[['BUY_SEED','WHEAT',8]]
        self.assertFalse(run(obs,act,routes)[1]['active'])

    def test_order_cap_capacity_and_existing_supply(self):
        for kind in ('cap','capacity','shed','pending'):
            obs,act,routes=fixture()
            if kind=='cap':act['market']=[['SELL','MILK',1]]*10
            if kind=='capacity':obs['private']['shed']={'MILK':100}
            if kind=='shed':obs['private']['shed']={'WHEAT':1}
            if kind=='pending':act['market']=[['BUY_PRODUCT','WHEAT',1]]
            self.assertFalse(run(obs,act,routes)[1]['active'],kind)


if __name__=='__main__':unittest.main()
