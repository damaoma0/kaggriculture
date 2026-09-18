"""Focused temporal and economic contracts; no future observation access."""
from copy import deepcopy
from market_corpus import ROOT,load

def main():
    m=load('delivery_contract',ROOT/'agents/v45_delivery_candidate.py')
    obs={'step':289,'player':0,'farms':[{'farmer':[4,4],'hands':[],'hires_today':0,'money':20000}],
         'market':{'prices':{'WHEAT':45,'CARROT':50,'FERTILIZER':1},
                   'inventory':{'WHEAT':9800,'CARROT':9800,'FERTILIZER':20000}},
         'town':{'unlocked_shops':['BAKERY','PET_CAFE','BAKERY','YARN_STORE']}}
    action={'farmer':['PASS'],'hands':[],'market':[]}
    targets={xy:{'crop':'WHEAT','birth':10,'yield':1,'until':-1,'watered':False,
                 'water':[294,318,342],'harvest':344,'first':2,'last':4,'cap':6}
             for xy in ((3,3),(3,4),(3,5),(4,3),(5,3),(6,3),(6,4),(6,5))}
    m._IMPL.chassis.players[0]={'route':2}
    before=deepcopy((obs,action,targets))
    a=m._delivery_scenarios(obs);b=m._delivery_scenarios(obs)
    assert a==b and len(a)==8 and all(s['WHEAT'][0]==9800 for s in a)
    assert m._delivery_consumption(288,['BAKERY','BAKERY'],'WHEAT')==3
    assert m._delivery_consumption(288,['PET_CAFE'],'CARROT')==3
    # No-flow inventory must fall only by shop/center demand before next unlock.
    assert a[0]['WHEAT'][1]==9800 and a[0]['WHEAT'][4]==9798
    # Reconstruct a synthetic constant +3-unit/turn market supply exactly.
    shops=obs['town']['unlocked_shops'];inv={'WHEAT':9700,'CARROT':9700}
    for t in range(241,289):
        m._DELIVERY_HISTORY.append((t,dict(inv),list(shops)))
        for item in inv:inv[item]+=3-m._delivery_consumption(t,shops,item)
    flowing=deepcopy(obs);flowing['market']['inventory'].update(inv)
    fp=m._delivery_scenarios(flowing)
    assert all(s['WHEAT'][1]==inv['WHEAT']+3 for s in fp)
    m._DELIVERY_HISTORY.clear()
    # More background supply must never increase the marginal sale valuation.
    lots=[(300,'WHEAT',4)]
    abundant=[{p:[x+100 for x in path] for p,path in s.items()} for s in a]
    assert m._delivery_value(obs,lots,abundant)<=m._delivery_value(obs,lots,a)
    assert m._delivery_value(obs,[],a)==0
    plans,q,cost,units=m._r68_joint_plans(obs,action,targets,{},0,0)
    assert plans and units['WHEAT']>0
    visited=set()
    for i,p in enumerate(plans):
        now,pos=m._r62_input_start(obs,action,i)
        for x,y,crop,birth in p['path']:
            assert (x,y) not in visited;visited.add((x,y))
            now+=abs(pos[0]-x)+abs(pos[1]-y)
            assert now<311 and m._r51_input_gain(targets[x,y],now,12)>0
            sale=m._delivery_sale_turn(obs,targets[x,y])
            assert sale is None or 360<=sale<=718
            now+=1;pos=(x,y)
    assert q==len(visited) and cost<=17000 and (obs,action,targets)==before
    poor=deepcopy(obs);poor['farms'][0]['money']=2999
    assert not m._r68_joint_plans(poor,action,targets,{},0,0)[0]
    assert not m._r68_joint_plans(obs,action,targets,{'FERTILIZER':95},0,0)[0]
    full=deepcopy(action);full['market']=[['SELL','WHEAT',0]]*10
    assert not m._r68_joint_plans(obs,full,targets,{},0,0)[0]
    expired=deepcopy(targets)
    for t in expired.values():t['harvest']=288
    assert not m._r68_joint_plans(obs,action,expired,{},0,0)[0]
    # With no planned sale after harvest, extra production has zero credit.
    original_sale=m._delivery_sale_turn
    m._delivery_sale_turn=lambda obs,target:None
    assert not m._r68_joint_plans(obs,action,targets,{},0,0)[0]
    m._delivery_sale_turn=original_sale
    assert m._DELIVERY_STATS['errors']==0
    print('PASS: deterministic scenarios, repeated-shop demand, timing, immutable inputs, feasible disjoint tours, cash/capacity/order constraints, expired harvests, no fallbacks')

if __name__=='__main__':main()
