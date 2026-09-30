"""Build fragment: only replace native input-plan output valuation."""
_EVENT_NATIVE_JOINT=_r68_joint_plans
_EVENT_MODEL=None
_EVENT_CACHE={}
_EVENT_STATS=dict(calls=0,changed=0,valued_lots=0,unchanged_lots=0,errors=0)

def _event_sale_time(obs,target):
    if target.get('harvest') is None:return None
    ready=(int(target['harvest'])//24+1)*24
    native=_IMPL.chassis.players[int(obs['player'])]
    for t in range(ready,min(719,ready+73)):
        route=2 if t>=648 else native['route']
        if any(len(o)>2 and o[0]=='SELL' and o[1]==target['crop'] and o[2]>0
               for o in _IMPL.chassis.routes[route][t].get('market',[])):return t
    return None

def _event_inventory(obs,item,horizon):
    key=(item,horizon)
    if key in _EVENT_CACHE:return _EVENT_CACHE[key]
    features=_EVENT_MODEL.features(obs,item,horizon)
    model=_EVENT_COEFFICIENTS[f'{item}/{horizon}/event']
    flow=model['bias']+sum((x-c)/s*b for x,c,s,b in zip(features['event'],model['center'],model['scale'],model['coef']))
    value=features['inventory']+flow-features['drain'];_EVENT_CACHE[key]=value
    return value

def _event_route_value(obs,action,path,targets,index,all_units,units):
    now,pos=_r62_input_start(obs,action,index);value=0;day=int(obs['step'])//24
    for x,y,item,birth in path:
        now+=abs(pos[0]-x)+abs(pos[1]-y)
        target=targets[x,y];gain=_r51_input_gain(target,now,day)
        sale=_event_sale_time(obs,target) if gain else None
        dt=None if sale is None else sale-int(obs['step'])
        inv=obs['market']['inventory'][item]
        if gain and 216<=obs['step']<=636 and dt is not None and 12<=dt<=72:
            lower=max(h for h in (12,24,48,72) if h<=dt)
            upper=min(h for h in (12,24,48,72) if h>=dt)
            inv=_event_inventory(obs,item,lower)
            if lower!=upper:inv+=(dt-lower)/(upper-lower)*(_event_inventory(obs,item,upper)-inv)
            _EVENT_STATS['valued_lots']+=1
        elif gain:_EVENT_STATS['unchanged_lots']+=1
        value+=gain*max(1,_r37_market_price(item,inv+all_units[item]+units[item])-2)
        now+=1;pos=(x,y)
    return value

def _r68_joint_plans(obs,action,targets,stock,purchases,topup):
    original=_EVENT_NATIVE_JOINT(obs,action,targets,stock,purchases,topup)
    _EVENT_STATS['calls']+=1;_EVENT_CACHE.clear()
    try:
        result=_event_joint_candidate(obs,action,targets,stock,purchases,topup)
        if result[0]!=original[0]:_EVENT_STATS['changed']+=1
        return result
    except Exception:
        _EVENT_STATS['errors']+=1
        return original

_EVENT_AGENT_PARENT=agent
def agent(observation,configuration=None):
    global _EVENT_MODEL
    if int(observation['step'])==0 or _EVENT_MODEL is None:
        _EVENT_MODEL=_EVENT_NS['EventModel']()
        for key in _EVENT_STATS:_EVENT_STATS[key]=0
    _EVENT_MODEL.observe(observation)
    result=_EVENT_AGENT_PARENT(observation,configuration)
    agent.telemetry=dict(getattr(_EVENT_AGENT_PARENT,'telemetry',{}),**{'event_'+k:v for k,v in _EVENT_STATS.items()})
    return result
agent.telemetry={}
