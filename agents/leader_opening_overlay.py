"""Leader-inspired mechanisms on V45's own geometry; not a leader replay splice.

Modes: berries advances four native strawberry sites; herd retains two initial
cows, changes the day-3 cow to a sheep and skips the day-4 cow; both combines.
"""
_HYBRID_TARGETS={(0,3),(1,1),(2,0),(0,2)}
_HYBRID_STATS={}
_HYBRID_PLANTED={}
_HYBRID_PENDING=[]
_HYBRID_PARENT=agent

# Mutate every native tape consistently, retaining all worker movement/service.
if _HYBRID_MODE in ('herd','both'):
    for _tape in _IMPL.chassis.routes.values():
        for _step in range(min(144,len(_tape))):
            _a=_tape[_step]
            if _step==65:
                _a['market']=[(['BUY_ANIMAL','SHEEP',o[2]] if o[:2]==['BUY_ANIMAL','COW'] else o) for o in _a.get('market',[])]
            if _step==88:
                _a['market']=[o for o in _a.get('market',[]) if o[:2]!=['BUY_ANIMAL','COW']]
            for _key in ('farmer','hands'):
                _commands=[_a.get('farmer',[])] if _key=='farmer' else _a.get('hands',[])
                for _c in _commands:
                    if len(_c)>1 and _c[1]=='COW':
                        if _step in (92,95):_c[:]=['PASS']
                        elif _step in (66,69):_c[1]='SHEEP'

def _hybrid_reserved_cash(obs,orders):
    # Conservative: do not credit requested sales; budget native orders first.
    cost=0;hires=int(obs['farms'][obs['player']]['hires_today'])
    for o in orders:
        if not o:continue
        if o[0]=='HIRE':cost+=_v219_fib(hires);hires+=1
        elif len(o)>2:
            if o[0]=='BUY_SEED':cost+=int(o[2])*{'WHEAT':10,'CARROT':20,'TOMATO':50,'STRAWBERRY':100,'MELON':80}.get(o[1],1000)
            elif o[0]=='BUY_ANIMAL':cost+=int(o[2])*{'COW':400,'SHEEP':500,'GOOSE':300}.get(o[1],1000)
            elif o[0]=='BUY_PRODUCT':cost+=int(o[2])*max(1,_r37_market_price(o[1],obs['market']['inventory'][o[1]]-int(o[2])))
        elif o[0]=='BUY_LAND':cost+=4000
    return cost

def agent(observation,configuration=None):
    step=int(observation['step']);farm=observation['farms'][observation['player']]
    if step==0:
        _HYBRID_PLANTED.clear();_HYBRID_PENDING.clear()
        _HYBRID_STATS.clear();_HYBRID_STATS.update(seed_buys=0,plant_requests=0,confirmed_plants=0,
            lost_before_handoff=0,protected_visits=0,extra_wool_requested=0,errors=0)
    for xy in _HYBRID_PENDING:
        tile=farm['tiles'][xy[1]][xy[0]]
        if isinstance(tile,dict) and tile.get('crop')=='STRAWBERRY':
            _HYBRID_PLANTED[xy]=tile['planted_day'];_HYBRID_STATS['confirmed_plants']+=1
    _HYBRID_PENDING.clear()
    result=_HYBRID_PARENT(observation,configuration)
    try:
        action=copy.deepcopy(result)
        if _HYBRID_MODE in ('berries','both'):
            seeds=int(observation['private']['seeds'].get('STRAWBERRY',0))
            positions=[farm['farmer'],*farm['hands']]
            commands=[action.get('farmer') or ['PASS'],*action.get('hands',[])]
            for actor,(pos,c) in enumerate(zip(positions,commands)):
                xy=tuple(pos);tile=farm['tiles'][pos[1]][pos[0]]
                if xy not in _HYBRID_TARGETS:continue
                is_berry=isinstance(tile,dict) and tile.get('crop')=='STRAWBERRY'
                if 72<=step<120 and c==['PLANT','WHEAT'] and tile is None and seeds>0:
                    commands[actor]=['PLANT','STRAWBERRY'];seeds-=1
                    _HYBRID_PENDING.append(xy);_HYBRID_STATS['plant_requests']+=1
                elif step<144 and xy in _HYBRID_PLANTED and is_berry and c and c[0] in ('DIG','PLANT','HARVEST'):
                    commands[actor]=['WATER'] if not tile.get('watered_today') else ['PASS']
                    _HYBRID_STATS['protected_visits']+=1
            action['farmer']=commands[0];action['hands']=commands[1:]
            missing=sum(not(isinstance(farm['tiles'][y][x],dict) and farm['tiles'][y][x].get('crop')=='STRAWBERRY') for x,y in _HYBRID_TARGETS)
            if 70<=step<85:
                room=max(0,missing-int(observation['private']['seeds'].get('STRAWBERRY',0))-len(_HYBRID_PENDING))
                money=farm['money']-_hybrid_reserved_cash(observation,action['market'])-35
                n=min(room,max(0,int(money)//100))
                if n and len(action['market'])<10:
                    action['market'].append(['BUY_SEED','STRAWBERRY',n]);_HYBRID_STATS['seed_buys']+=n
            if step in (130,135,136):
                need=max(0,missing-int(observation['private']['seeds'].get('STRAWBERRY',0)))
                orders=[]
                for o in action['market']:
                    if o[:2]==['BUY_SEED','STRAWBERRY']:
                        n=min(int(o[2]),need);need-=n
                        if n:orders.append(['BUY_SEED','STRAWBERRY',n])
                    else:orders.append(o)
                action['market']=orders
            if step==144:
                _HYBRID_STATS['lost_before_handoff']=sum(not(isinstance(farm['tiles'][y][x],dict) and farm['tiles'][y][x].get('crop')=='STRAWBERRY') for x,y in _HYBRID_PLANTED)
        if _HYBRID_MODE in ('herd','both') and any(o[:2]==['SELL','WOOL'] for o in action['market']):
            stock=projected_shed(action,FarmView(observation));left=max(0,int(stock.get('WOOL',0)))
            for o in action['market']:
                if o[:2]==['SELL','WOOL']:
                    if left>o[2]:_HYBRID_STATS['extra_wool_requested']+=left-o[2]
                    o[2]=left;left=0
        result=action
    except Exception:
        _HYBRID_STATS['errors']+=1
    agent.telemetry=dict(getattr(_HYBRID_PARENT,'telemetry',{}),**{'hybrid_'+k:v for k,v in _HYBRID_STATS.items()})
    return result
agent.telemetry={}
