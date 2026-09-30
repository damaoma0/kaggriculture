"""Causality, production timing and calibration contracts."""
from copy import deepcopy
from market_corpus import ROOT,load

def main():
    m=load('event_contract',ROOT/'agents/event_price_forecast.py')
    tiles=[[None for _ in range(10)] for _ in range(10)]
    tiles[0][0]=dict(kind='PLANT',crop='WHEAT',yield_units=1,planted_day=10,
                     watered_today=False,fertilized_until_day=-1,max_lifespan_step=-1)
    tiles[0][1]=dict(kind='PASTURE',animal='COW',yield_units=0,placed_day=5,pending_care_bonus=1)
    obs=dict(step=264,player=0,farms=[dict(tiles=deepcopy(tiles)),dict(tiles=deepcopy(tiles))],
             market=dict(inventory={p:10000 for p in m.ITEMS},prices={p:50 for p in m.ITEMS}),
             town=dict(unlocked_shops=['BAKERY','BAKERY','PET_CAFE']),
             private=dict(shed={'WHEAT':3},inventories=[{'WHEAT':2}]))
    model=m.EventModel();original=deepcopy(obs);model.observe(obs)
    f=model.features(obs,'WHEAT',24)
    assert obs==original and len(f['event'])>len(f['base']) and f['event'][-2:]==[3,2]
    assert model.production(obs,'WHEAT',12,0)[2]==0 # immature
    assert model.production(obs,'WHEAT',48,0)[2]>0 # first mature day included
    assert model.production(obs,'MILK',48,0)[2]==0 # first production at endpoint
    assert model.production(obs,'MILK',72,0)[2]>0
    assert m.consume(264,['BAKERY','BAKERY'],'WHEAT')==3
    assert m.consume(264,['PET_CAFE'],'CARROT')==3
    after=deepcopy(obs);after['step']=265;after['farms'][1]['tiles'][0][0]=None
    after['market']['inventory']['WHEAT']+=2 # demand -3, aggregate trade +5
    model.observe(after)
    assert model.records[-1]['flows']['WHEAT']==5 and model.records[-1]['harvest']['WHEAT'][1]==1
    # Future input cannot affect a completed forecast. Neither caller mutation
    # nor any rival-private field is retained in history.
    before=model.features(after,'WHEAT',48)
    obs['farms'][1]['tiles'][0][0]['yield_units']=99999
    assert before==model.features(after,'WHEAT',48)
    altered=deepcopy(after);altered['rival_private']={'shed':{'WHEAT':99999}}
    assert before==model.features(altered,'WHEAT',48)
    assert 'private' not in model.previous
    from evaluate_event_prices import fit,predict
    rows=[dict(base=[i,1],target_flow=3*i+7,inventory=10000,drain=0) for i in range(10)]
    fitted=fit(rows,'base',.00001)
    assert abs(predict(rows[-1],'base',fitted)-10034)<.001
    print('PASS: immutable observations; causal copied history; no rival-private dependence; crop/animal timing; repeated-shop demand; harvest and trade inference; constant-feature ridge calibration')

if __name__=='__main__':main()
