"""Build fragment: our sale policies adapted to V44/V45's reservation layer."""
_PORT_STATS={'priority_calls':0,'liquid_turns':0,'liquid_units':0,'reserved_units':0,'errors':0}
_PORT_NATIVE_PRIORITY=_r37_quote_priority
_PORT_NATIVE_RESERVE=_r36_reserve

def _port_quote_priority(obs,order,stock):
    item=order[1]
    q=min(max(0,int(order[2])),max(0,int(stock.get(item,0))))
    if item not in _R37_MARKET_PARAMS or q<=0:return 0
    params={k:dict(v) for k,v in _R37_MARKET_PARAMS.items()}
    for k,patch in obs['market'].get('params',{}).items():
        if k in params:params[k].update(patch)
    _PORT_STATS['priority_calls']+=1
    return _port_priority_value(item,obs['market']['inventory'][item],q,q,params)

def _port_liquidate(obs,action):
    step=int(obs['step'])
    if not 216<=step<696:return action
    native=_IMPL.chassis.players[int(obs['player'])]
    view=FarmView(obs)
    commands=[action.get('farmer') or ['PASS'],*(action.get('hands') or [])]
    if any(len(c)>1 and c[0]=='PLACE' and c[1] in ANIMAL_STRUCTURE and view.inv(i).get(c[1],0)>0
           for i,c in enumerate(commands[:len(view.positions)])):return action
    stock=projected_shed(action,view)
    market=action.get('market',[])
    changes=[]
    for item in ('MILK','WOOL'):
        if view.prices.get(item,0)<2:continue
        if any(len(o)>1 and o[:2]==['BUY_PRODUCT',item] for o in market):continue
        if any(len(c)>1 and c[:2]==['PICKUP',item] for c in commands):continue
        if any(len(c)>1 and c[:2]==['PICKUP',item] for queue in native['pending'].values() for pos,c in queue):continue
        existing=next((i for i,o in enumerate(market) if len(o)>2 and o[:2]==['SELL',item]),None)
        if existing is None and len(market)+sum(i is None for _,_,i,_ in changes)>=10:continue
        planned=sum(max(0,int(o[2])) for o in market if len(o)>2 and o[:2]==['SELL',item])
        extra=max(0,int(stock.get(item,0))-planned)
        if not extra:continue
        remaining=extra; reservations=[];blocked=False
        debts=native['sell_state'].get('r36_debts',{})
        for due in range(step+1,719):
            tape=_IMPL.chassis.routes[2 if due>=648 else native['route']]
            future=tape[due]
            if any(len(c)>1 and c[:2]==['PICKUP',item] for c in [future.get('farmer') or ['PASS'],*(future.get('hands') or [])]):
                blocked=True;break
            future_sale=sum(max(0,int(o[2])) for o in future.get('market',[]) if len(o)>2 and o[:2]==['SELL',item])
            amount=min(remaining,max(0,future_sale-debts.get(due,{}).get(item,0)))
            if amount:reservations.append((due,amount));remaining-=amount
            if not remaining:break
        if not blocked:changes.append((item,extra,existing,reservations))
    if not changes:return action
    result=dict(action,market=[list(o) for o in market])
    debts=native['sell_state'].setdefault('r36_debts',{})
    for item,extra,index,reservations in changes:
        if index is None:result['market'].append(['SELL',item,extra])
        else:result['market'][index][2]+=extra
        for due,amount in reservations:
            owed=debts.setdefault(due,{})
            owed[item]=owed.get(item,0)+amount
            _PORT_STATS['reserved_units']+=amount
        _PORT_STATS['liquid_units']+=extra
    _PORT_STATS['liquid_turns']+=1
    return result

def _port_reserve(obs,action):
    action=_PORT_NATIVE_RESERVE(obs,action)
    try:return _port_liquidate(obs,action)
    except Exception:
        _PORT_STATS['errors']+=1
        return action

if _PORT_MODE in ('order','both'):_r37_quote_priority=_port_quote_priority
if _PORT_MODE in ('liquid','both'):_r36_reserve=_port_reserve

_PORT_PARENT=agent
def agent(observation,configuration=None):
    if int(observation['step'])==0:
        for key in _PORT_STATS:_PORT_STATS[key]=0
    action=_PORT_PARENT(observation,configuration)
    agent.telemetry=dict(getattr(_PORT_PARENT,'telemetry',{}),**{'port_'+k:v for k,v in _PORT_STATS.items()})
    return action
agent.telemetry={}
