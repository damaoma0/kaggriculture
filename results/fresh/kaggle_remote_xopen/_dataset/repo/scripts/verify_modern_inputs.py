"""Focused contracts for the generated crop-input planner."""
from copy import deepcopy
from market_corpus import ROOT,load

def main():
    module=load('modern_contract',ROOT/'agents/modern_router_candidate.py')
    obs={'step':289,'player':0,'farms':[{'farmer':[4,4],'hands':[],'hires_today':0,'money':20000}],
         'market':{'prices':{'WHEAT':45,'CARROT':50,'FERTILIZER':1},
                   'inventory':{'WHEAT':9800,'CARROT':9800,'FERTILIZER':20000}}}
    action={'farmer':['PASS'],'hands':[],'market':[]}
    targets={xy:{'crop':'WHEAT','birth':10,'yield':1,'until':-1,'watered':False,
                 'water':[294,318,342],'harvest':344,'first':2,'last':4,'cap':6}
             for xy in ((3,3),(3,4),(3,5),(4,3),(5,3),(6,3),(6,4),(6,5))}
    before=deepcopy((obs,action,targets))
    plans,q,cost,units=module._r68_joint_plans(obs,action,targets,{},0,0)
    assert plans and units['WHEAT']>0
    visited=set()
    for i,plan in enumerate(plans):
        now,pos=module._r62_input_start(obs,action,i)
        assert plan['quantity']==len(plan['path'])
        for x,y,crop,birth in plan['path']:
            xy=(x,y);assert xy not in visited;visited.add(xy)
            now+=abs(pos[0]-x)+abs(pos[1]-y)
            assert now<311 and module._r51_input_gain(targets[xy],now,12)>0
            now+=1;pos=xy
    assert q==sum(p['quantity'] for p in plans) and cost<=17000
    assert (obs,action,targets)==before
    poor=deepcopy(obs);poor['farms'][0]['money']=2999
    assert not module._r68_joint_plans(poor,action,targets,{},0,0)[0]
    assert not module._r68_joint_plans(obs,action,targets,{'FERTILIZER':95},0,0)[0]
    full_orders=deepcopy(action);full_orders['market']=[['SELL','WHEAT',0]]*10
    assert not module._r68_joint_plans(obs,full_orders,targets,{},0,0)[0]
    expired=deepcopy(targets)
    for target in expired.values():target['harvest']=288
    assert not module._r68_joint_plans(obs,action,expired,{},0,0)[0]
    capped=deepcopy(targets)
    for target in capped.values():target['yield']=6
    assert not module._r68_joint_plans(obs,action,capped,{},0,0)[0]
    assert module._MODERN_INPUT_STATS['errors']==0
    print('PASS: disjoint feasible tours, positive harvest gain, immutable observations, cash reserve, warehouse limit, order cap, expired harvests, yield cap, no fallback errors')

if __name__=='__main__':main()
