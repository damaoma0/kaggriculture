"""Focused checks for individual task transfers and delivery obligations."""
from copy import deepcopy
from evaluate_boards import ROOT,module_at
m=module_at('task_repair_checks',ROOT/'agents/router_task_repair.py')

def fixture(op='WATER',crop='STRAWBERRY'):
    tiles=[[None for _ in range(10)] for _ in range(10)]
    tiles[0][0]={'kind':'PLANT','crop':crop,'planted_day':0,'watered_today':False,'yield_units':2}
    obs={'step':392,'day':16,'player':0,'farms':[{'farmer':[4,0],'hands':[[0,0]],'tiles':tiles}],
         'private':{'inventories':[{},{}]}}
    orders={'0':[{'step':390,'target':[0,0],'action':[op]}],
            '1':[{'step':398,'target':[4,4],'action':['DROP']}]}
    route=[{'market':[]} for _ in range(720)]
    return obs,orders,route

def instance():
    a=m.Scheduler();a.start=384;a.assignment=[0,1];return a

def main():
    obs,orders,route=fixture()
    # Put helper's later delivery within reach after the one-turn assist.
    orders['1'][0]['step']=403
    a=instance();assert a.repair(obs,orders,route)=={1:['WATER']}
    assert (0,390,False) in a.completed
    obs['farms'][0]['hands'][0]=[1,0]
    a=instance();assert a.repair(obs,orders,route)=={1:['WEST']}
    assert not a.completed  # Approaching a task must not mark it done.
    orders['1'][0]['step']=393
    assert instance().repair(obs,orders,route)=={}  # Protect helper deadline.
    obs,orders,route=fixture('HARVEST');orders['1'][0]['step']=403
    assert instance().repair(obs,orders,route)=={1:['HARVEST']}
    orders['1']=[]
    assert instance().repair(obs,orders,route)=={}  # No promised delivery.
    obs,orders,route=fixture('HARVEST','WHEAT');orders['1'][0]['step']=403
    assert instance().repair(obs,orders,route)=={}  # Do not steal animal feed.
    obs,orders,route=fixture();orders['1'][0]['step']=403
    obs['farms'][0]['tiles'][0][0]['watered_today']=True
    assert instance().repair(obs,orders,route)=={}
    obs['farms'][0]['tiles'][0][0]['watered_today']=False
    route[393]['market']=[['HIRE']]
    assert instance().repair(obs,orders,route)=={}
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    for op in ('WATER','HARVEST'):
        obs,orders,route=fixture(op);orders['1'][0]['step']=403
        chosen=instance().repair(obs,orders,route)
        E._apply_unit_action(obs['farms'][0],obs['private'],1,chosen[1],10,16,24)
        if op=='WATER':assert obs['farms'][0]['tiles'][0][0]['watered_today']
        else:assert obs['private']['inventories'][1]['STRAWBERRY']==2
    print('Passed transfer constraints and official-engine watering/harvest checks.')

if __name__=='__main__':main()
