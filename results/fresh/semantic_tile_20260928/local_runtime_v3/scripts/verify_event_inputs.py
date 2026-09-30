"""Feature parity, native-planner equivalence and standalone integration."""
from copy import deepcopy
from hashlib import sha256
import json
from market_corpus import ROOT,load
from evaluate_boards import Ledger
from research_wheat_economy import WheatAudit

def main():
    m=load('event_input_contract',ROOT/'agents/v45_event_candidate.py')
    research=load('event_research_contract',ROOT/'agents/event_price_forecast.py')
    tiles=[[None for _ in range(10)] for _ in range(10)]
    targets={xy:{'crop':'WHEAT','birth':10,'yield':1,'until':-1,'watered':False,
                 'water':[294,318,342],'harvest':344,'first':2,'last':4,'cap':6}
             for xy in ((3,3),(3,4),(3,5),(4,3),(5,3),(6,3),(6,4),(6,5))}
    for x,y in targets:tiles[y][x]=dict(kind='PLANT',crop='WHEAT',yield_units=1,planted_day=10,watered_today=False,fertilized_until_day=-1)
    obs=dict(step=289,player=0,farms=[dict(farmer=[4,4],hands=[],hires_today=0,money=20000,tiles=tiles),dict(tiles=deepcopy(tiles))],
        market=dict(prices=dict(WHEAT=45,CARROT=50,FERTILIZER=1,MILK=160,WOOL=200),inventory=dict(WHEAT=9800,CARROT=9800,FERTILIZER=20000,MILK=10000,WOOL=10000)),
        town=dict(unlocked_shops=['BAKERY']*4),private=dict(shed={},inventories=[{}]))
    action=dict(farmer=['PASS'],hands=[],market=[]);before=deepcopy((obs,action,targets))
    m._EVENT_MODEL=m._EVENT_NS['EventModel']();r=research.EventModel()
    for item in ('WHEAT','CARROT'):
        for h in (12,24,48,72):assert m._EVENT_MODEL.features(obs,item,h)==r.features(obs,item,h)
    m._IMPL.chassis.players[0]={'route':2}
    original=m._EVENT_NATIVE_JOINT(obs,action,targets,{},0,0)
    inventory=m._event_inventory
    m._event_inventory=lambda o,item,h:o['market']['inventory'][item]
    assert m._event_joint_candidate(obs,action,targets,{},0,0)==original
    m._event_inventory=inventory
    m._r68_joint_plans(obs,action,targets,{},0,0)
    assert (obs,action,targets)==before and m._EVENT_STATS['errors']==0
    poor=deepcopy(obs);poor['farms'][0]['money']=2999
    assert not m._r68_joint_plans(poor,action,targets,{},0,0)[0]
    assert not m._r68_joint_plans(obs,action,targets,{'FERTILIZER':95},0,0)[0]
    full=deepcopy(action);full['market']=[['SELL','WHEAT',0]]*10
    assert not m._r68_joint_plans(obs,full,targets,{},0,0)[0]
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    path=ROOT/'agents/v45_event_candidate.py'
    env=make('kaggriculture',configuration={'seed':148999,'episodeSteps':720})
    with Ledger(E) as ledger:
        with WheatAudit(E,env):env.run([str(path),str(ROOT/'agents/v45_our_selected.py')])
    assert len(env.steps)==720 and all(s.status in ('ACTIVE','DONE') for ss in env.steps for s in ss)
    for i in (0,1):assert 3000+sum(ledger.data[i]['revenue'].values())-sum(ledger.data[i]['spend'].values())==env.state[i].reward
    out=ROOT/'results/fresh/event_inputs';out.mkdir(parents=True,exist_ok=True)
    result=dict(sha256=sha256(path.read_bytes()).hexdigest(),seed=148999,steps=len(env.steps),statuses=[s.status for s in env.state],cash=[s.reward for s in env.state],
                contracts='Feature parity; exact native-plan equivalence with current quotes; immutable inputs; cash/capacity/order limits; no contract errors; native-RNG file-path game and full ledgers.')
    (out/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))

if __name__=='__main__':main()
