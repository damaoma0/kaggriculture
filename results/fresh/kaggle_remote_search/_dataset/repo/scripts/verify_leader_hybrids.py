"""Focused compatibility checks for the leader-inspired opening overlay."""
from copy import deepcopy
from market_corpus import ROOT,load

def main():
    for mode in ('berries','herd','both'):
        m=load('hybrid_contract_'+mode,ROOT/f'agents/v45_leader_{mode}.py')
        if mode in ('herd','both'):
            tape=m._IMPL.chassis.routes[0]
            assert ['BUY_ANIMAL','SHEEP',1] in tape[65]['market']
            assert not any(o[:2]==['BUY_ANIMAL','COW'] for o in tape[88]['market'])
            assert tape[66]['farmer']==['PICKUP','SHEEP'] and tape[69]['farmer']==['PLACE','SHEEP']
            assert tape[92]['hands'][2]==['PASS'] and tape[95]['hands'][2]==['PASS']
        m._HYBRID_PARENT=lambda obs,config:deepcopy(obs['test_action'])
        tiles=[[None for _ in range(10)] for _ in range(10)]
        obs=dict(step=0,player=0,farms=[dict(farmer=[0,3],hands=[],money=135,hires_today=0,tiles=tiles)],
            private=dict(seeds={'STRAWBERRY':0},shed={},inventories=[{}]),
            market=dict(inventory={'WHEAT':10000}),test_action=dict(farmer=['PASS'],hands=[],market=[]))
        m.agent(obs)
        obs['step']=70;before=deepcopy(obs);a=m.agent(obs)
        assert obs==before
        if mode!='herd':assert a['market']==[['BUY_SEED','STRAWBERRY',1]]
        obs['step']=71;obs['farms'][0]['money']=134
        assert not m.agent(obs)['market']
        if mode!='herd':
            obs['step']=80;obs['private']['seeds']['STRAWBERRY']=1;obs['test_action']['farmer']=['PLANT','WHEAT']
            assert m.agent(obs)['farmer']==['PLANT','STRAWBERRY']
            obs['step']=81;tiles[3][0]=dict(kind='PLANT',crop='STRAWBERRY',planted_day=3,watered_today=False)
            obs['test_action']['farmer']=['HARVEST']
            assert m.agent(obs)['farmer']==['WATER'] and m._HYBRID_STATS['confirmed_plants']==1
            obs['step']=82;tiles[3][0]['watered_today']=True;obs['test_action']['farmer']=['DIG']
            assert m.agent(obs)['farmer']==['PASS']
            obs['step']=144;m.agent(obs)
            assert m._HYBRID_STATS['lost_before_handoff']==0
        assert m._HYBRID_STATS['errors']==0
    print('PASS: native coordinate preservation; planned sheep purchase/pickup/place; skipped cow commands; affordability; immutable observations; seed-available planting; confirmed plants; watering/DIG protection; no contract errors')

if __name__=='__main__':main()
