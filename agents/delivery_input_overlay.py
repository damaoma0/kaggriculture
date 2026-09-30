"""Build fragment: delivery-price valuation of optional V45 fertilizer tours.

Uses only past public inventory and revealed shops. Scenario RNG is local and
independent of the environment seed. No engine imports in the built agent.
"""
import random as _delivery_random

_DELIVERY_SHOPS = {
    'BAKERY': ('EGG','WHEAT'), 'PIZZA_SHOP': ('MILK','TOMATO','WHEAT'),
    'BRUNCH_SPOT': ('EGG','WHEAT','STRAWBERRY'), 'YARN_STORE': ('WOOL',),
    'ICE_CREAM_SHOP': ('STRAWBERRY','MILK','WHEAT'), 'PET_CAFE': ('CARROT',),
    'SMOOTHIE_SHOP': ('STRAWBERRY','MILK'),
    'FARMERS_MARKET': ('WHEAT','CARROT','TOMATO','STRAWBERRY')}
_DELIVERY_HISTORY = []
_DELIVERY_STATS = dict(calls=0,changed=0,declined=0,errors=0,scenarios=0,
                      quotes_checked=0,forecast_abs_error=0,current_abs_error=0)
_DELIVERY_RECORDS = []
_DELIVERY_NATIVE = _r68_joint_plans


def _delivery_consumption(step, shops, item):
    return (sum(2 if len(_DELIVERY_SHOPS[s])==1 else 1 for s in shops
                if item in _DELIVERY_SHOPS[s]) if step%4==0 else 0) + int(step%24==0)


def _delivery_scenarios(obs, horizon=160):
    step=int(obs['step']); inventory=obs['market']['inventory']
    shops=list(obs['town']['unlocked_shops']); paths=[]
    for k in range(8):
        past=[v for v in _DELIVERY_HISTORY if step-(24 if k%2 else 48)<=v[0]<step]
        rate={p:0.0 for p in ('WHEAT','CARROT')}
        if past:
            for p in rate:
                consumed=sum(_delivery_consumption(t,s,p) for t,inv,s in past)
                rate[p]=(inventory[p]-past[0][1][p]+consumed)/(step-past[0][0])
        rng=_delivery_random.Random(91373+step*31+k*1009)
        future=list(shops); path={p:[float(inventory[p])] for p in rate}
        for dt in range(horizon):
            t=step+dt
            for p in rate:
                path[p].append(path[p][-1]+rate[p]-_delivery_consumption(t,future,p))
            if (t+1)%72==0 and len(future)<8:
                future.append(rng.choice(sorted(_DELIVERY_SHOPS)))
        paths.append(path)
    return paths


def _delivery_sale_turn(obs, target):
    # Midnight automatically delivers worker cargo. Find the next native sale
    # after that delivery; reservations may sell earlier, making this approximate.
    ready=(int(target['harvest'])//24+1)*24
    native=_IMPL.chassis.players[int(obs['player'])]
    for t in range(ready,min(719,ready+73)):
        route=2 if t>=648 else native['route']
        if any(len(o)>2 and o[0]=='SELL' and o[1]==target['crop'] and o[2]>0
               for o in _IMPL.chassis.routes[route][t].get('market',[])):
            return t
    return None


def _delivery_lots(obs, action, paths, targets):
    lots=[];day=int(obs['step'])//24
    for i,(path,units) in enumerate(paths):
        now,pos=_r62_input_start(obs,action,i)
        for x,y,crop,birth in path:
            now+=abs(pos[0]-x)+abs(pos[1]-y)
            target=targets[x,y]; gain=_r51_input_gain(target,now,day)
            sale=_delivery_sale_turn(obs,target) if gain else None
            if sale is not None:lots.append((sale,crop,gain))
            now+=1;pos=(x,y)
    return sorted(lots)


def _delivery_value(obs, lots, scenarios):
    values=[];step=int(obs['step'])
    for scenario in scenarios:
        added={'WHEAT':0,'CARROT':0}; value=0
        for sale,item,qty in lots:
            dt=sale-step
            if not 0<=dt<len(scenario[item]):continue
            for _ in range(qty):
                quote=_r37_market_price(item,scenario[item][dt]+added[item])
                value+=max(1,quote-2)
                added[item]+=int(quote>1)
        values.append(value)
    # Expected proceeds with a modest downside discount, not calibrated quantiles.
    return .75*sum(values)/len(values)+.25*sorted(values)[len(values)//4]


def _r68_joint_plans(obs,action,targets,stock,purchases,topup):
    original=_DELIVERY_NATIVE(obs,action,targets,stock,purchases,topup)
    _DELIVERY_STATS['calls']+=1
    try:
        scenarios=_delivery_scenarios(obs);_DELIVERY_STATS['scenarios']+=len(scenarios)
        farm=obs['farms'][obs['player']]
        best=([],0,0,{'WHEAT':0,'CARROT':0});best_score=0;best_lots=[]
        def consider(paths):
            nonlocal best,best_score,best_lots
            cost,unused,qty,units=_modern_cost_value(obs,action,paths,topup)
            n=len(paths)
            if len(action.get('market',[]))+1+n>10:return
            if sum(stock.values())+purchases+qty+topup>95:return
            lots=_delivery_lots(obs,action,paths,targets)
            value=_delivery_value(obs,lots,scenarios)
            if farm['money']<cost+3000 or value<1.5*cost+50*n:return
            if value-cost<=best_score+1:return
            best_score=value-cost;best_lots=lots
            best=([{'path':path,'quantity':len(path),'loaded':False} for path,u in paths],qty,cost,units)
        # Include the original feasible plan as well as the bounded tour shortlist.
        if original[0]:
            paths=[]
            for i,plan in enumerate(original[0]):
                now,pos=_r62_input_start(obs,action,i);u={'WHEAT':0,'CARROT':0}
                for x,y,crop,birth in plan['path']:
                    now+=abs(pos[0]-x)+abs(pos[1]-y)
                    u[crop]+=_r51_input_gain(targets[x,y],now,int(obs['step'])//24)
                    now+=1;pos=(x,y)
                paths.append((plan['path'],u))
            consider(paths)
        for first in _modern_tours(obs,targets,action,0):
            consider([first]);used={(x,y) for x,y,_,_ in first[0]}
            remaining={xy:t for xy,t in targets.items() if xy not in used}
            for second in _modern_tours(obs,remaining,action,1):consider([first,second])
        if best[0]!=original[0]:_DELIVERY_STATS['changed']+=1
        if original[0] and not best[0]:_DELIVERY_STATS['declined']+=1
        for sale,item,qty in best_lots:
            _DELIVERY_RECORDS.append(dict(step=int(obs['step']),sale=sale,item=item,quantity=qty,
                current_price=obs['market']['prices'][item],
                forecast_price=sum(_r37_market_price(item,s[item][sale-int(obs['step'])]) for s in scenarios)/len(scenarios)))
        return best
    except Exception:
        _DELIVERY_STATS['errors']+=1
        return original


_DELIVERY_PARENT=agent
def agent(observation,configuration=None):
    step=int(observation['step'])
    if step==0:
        _DELIVERY_HISTORY.clear();_DELIVERY_RECORDS.clear()
        for key in _DELIVERY_STATS:_DELIVERY_STATS[key]=0
    for record in _DELIVERY_RECORDS:
        if record['sale']==step:
            actual=observation['market']['prices'][record['item']]
            _DELIVERY_STATS['quotes_checked']+=1
            _DELIVERY_STATS['forecast_abs_error']+=abs(actual-record['forecast_price'])
            _DELIVERY_STATS['current_abs_error']+=abs(actual-record['current_price'])
    result=_DELIVERY_PARENT(observation,configuration)
    _DELIVERY_HISTORY.append((step,dict(observation['market']['inventory']),list(observation['town']['unlocked_shops'])))
    if len(_DELIVERY_HISTORY)>48:del _DELIVERY_HISTORY[0]
    agent.telemetry=dict(getattr(_DELIVERY_PARENT,'telemetry',{}),**{'delivery_'+k:v for k,v in _DELIVERY_STATS.items()})
    return result
agent.telemetry={}
