"""Public-observation inventory forecasts and a bounded sale-allocation DP."""
from functools import lru_cache
from kaggle_environments.envs.kaggriculture import kaggriculture as E

def demand(shops,item):
    return sum((2 if len(E.SHOPS[s])==1 else 1) for s in shops if item in E.SHOPS[s])

def consumption(step,shops,item):
    return (demand(shops,item) if step%4==0 else 0)+(int(item!='FERTILIZER') if step%24==0 else 0)

def forecast(obs,history,horizon=72,method='flow',alpha=0.5,future='mean'):
    """Return inventory paths. History contains only earlier public states.

    Uses default engine consumption intervals (4/24) and uniform new shops.
    'low' and 'high' are extreme future-demand scenarios, not quantiles.
    """
    t=int(obs['step']);inv=obs['market']['inventory'];shops=obs['town']['unlocked_shops']
    start=max(0,t-48);past=history[start:t]
    rates={}
    for item in E.PRODUCTS:
        flows=inv[item]-history[start]['inventory'][item] if past else 0
        flows+=sum(consumption(start+j,v['shops'],item) for j,v in enumerate(past))
        rates[item]=flows/max(1,len(past))
    visible={p:0.0 for p in E.PRODUCTS}
    if method=='visible':
        for farm in obs['farms']:
            for row in farm['tiles']:
                for tile in row:
                    if not isinstance(tile,dict):continue
                    if tile.get('animal'):
                        a=E.ANIMALS[tile['animal']];visible[a['product']]+=2/a['interval']/24
                        visible['FERTILIZER']+=1/24;visible['WHEAT']-=1/24
                    elif tile.get('kind')=='PLANT':
                        cd=E.CROPS[tile['crop']];age=obs['day']-tile['planted_day']
                        if cd['ongoing']:
                            if cd['first_yield_day']<=age<=cd['first_yield_day']+3*cd['interval']:
                                visible[tile['crop']]+=1.5/cd['interval']/24
                        elif age>=cd['first_yield_day']-1:
                            visible[tile['crop']]+=tile.get('yield_units',0)/24
        rates={p:(1-alpha)*rates[p]+alpha*visible[p] for p in E.PRODUCTS}
    result={p:[float(inv[p])] for p in E.PRODUCTS}
    for dt in range(horizon):
        u=t+dt
        new=max(0,min(8,u//72)-len(shops))
        for item in E.PRODUCTS:
            if method=='current':delta=0
            elif method=='trend':delta=(inv[item]-history[start]['inventory'][item])/max(1,t-start)
            else:
                extra=(sum(demand([s],item) for s in E.SHOPS)/len(E.SHOPS) if future=='mean' else
                       min(demand([s],item) for s in E.SHOPS) if future=='low' else max(demand([s],item) for s in E.SHOPS))
                delta=rates[item]-consumption(u,shops,item)-(new*extra if u%4==0 else 0)
            result[item].append(result[item][-1]+delta)
    return result

def sell_value(item,inventory,quantity,params=None):
    revenue=0;added=0
    for _ in range(quantity):
        price=E.market_price(item,inventory+added,params);revenue+=price;added+=price>1
    return revenue,added

def sale_dp(item,inventory_path,quantity,params=None,plan=False):
    """Allocate a small lot across fixed sale times with own price impact.

    State is (time index, remaining units, cumulative market additions).
    Background market flows are fixed by the supplied scenario; all remaining
    units are sold at the horizon. Returns value and first sale quantity.
    """
    @lru_cache(None)
    def value(k,left,added):
        if k==len(inventory_path)-1:
            return sell_value(item,inventory_path[k]+added,left,params)[0],left
        best=(-1,0)
        for n in range(left+1):
            revenue,inc=sell_value(item,inventory_path[k]+added,n,params)
            candidate=revenue+value(k+1,left-n,added+inc)[0]
            if candidate>best[0] or candidate==best[0] and n>best[1]:best=(candidate,n)
        return best
    answer=value(0,quantity,0)
    if not plan:return answer
    actions=[];left=quantity;added=0
    for k in range(len(inventory_path)):
        n=value(k,left,added)[1];actions.append(n)
        _,inc=sell_value(item,inventory_path[k]+added,n,params);added+=inc;left-=n
    return answer[0],actions
