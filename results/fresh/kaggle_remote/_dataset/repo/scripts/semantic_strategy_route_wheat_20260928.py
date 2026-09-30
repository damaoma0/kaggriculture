"""Optional early route-local wheat purchase; no changes to KB or unit commands.

The rolling evaluator may retain a route whose first animal job has no executable
operation without wheat. Count only observed PASSes on those exact route heads.
Wheat carried by another worker is deliberately not treated as local supply.
"""
from copy import deepcopy

SEEDS = {'WHEAT':10,'CARROT':20,'TOMATO':50,'STRAWBERRY':100,'MELON':80}
ANIMALS = {'GOOSE':300,'COW':400,'SHEEP':500}
LAND_COST = (1000,2000,4000)
DEFAULT_CONFIG = dict(enabled=False,start_day=6,end_day=10,last_hour=20,
                      max_buy_per_call=4,quote_buffer=2)


def _fib(n):
    a,b=1,1
    for _ in range(max(0,int(n))):a,b=b,a+b
    return a


def capture_route_context(kb):
    """Install an observational hook once; forwards all arguments/result unchanged."""
    if getattr(kb,'_route_wheat_hook_installed',False):return
    original=kb._sd_pre
    names=original.__code__.co_varnames[:original.__code__.co_argcount]
    def observe(*args,**kwargs):
        values=dict(zip(names,args));values.update(kwargs)
        result=original(*args,**kwargs)
        kb._route_wheat_context=dict(step=values['step'],tasks=values['tasks'])
        return result
    kb._sd_pre=observe
    kb._route_wheat_hook_installed=True


def route_wheat_order(obs, action, executor_state, routes, *, rolling=False, tasks=None,
                      retirement_intents=None, config=None, price_at=None,
                      max_orders=10, shed_capacity=100, hire_multiplier=1):
    """Return copied action + audit; append at most one wheat purchase.

    Call after the normal executor, with its current rolling routes. This never
    changes their order, clears planner state, or forces a worker command. A
    current PASS, unfed animal under that worker, matching integer route head,
    and zero wheat in its own inventory are all required. Any current retirement
    intent disables the helper. Default is OFF; hard window remains days 6–10.

    Native purchases reserve current cash without credit for requested sales.
    Product quotes are walked using the supplied current-market price function;
    a per-unit buffer is reserved for simultaneous rival trades. Actual engine
    affordability remains authoritative and is reobserved next hour.
    """
    cfg=dict(DEFAULT_CONFIG);cfg.update(config or {})
    out=deepcopy(action)
    diag=dict(enabled=bool(cfg['enabled']),active=False,blocked=[],buy=0)
    def stop(reason):return out,dict(diag,reason=reason)
    if not cfg['enabled']:return stop('disabled')
    day,hour=divmod(int(obs['step']),24);diag.update(day=day,hour=hour)
    if not max(6,int(cfg['start_day']))<=day<=min(10,int(cfg['end_day'])) or hour>min(20,int(cfg['last_hour'])):
        return stop('outside_early_window')
    if not rolling:return stop('not_rolling')
    if tasks is None:return stop('missing_current_tasks')
    if (executor_state or {}).get('_xretire') or retirement_intents:
        return stop('preserve_retirement')
    farm=obs['farms'][int(obs['player'])];private=obs.get('private',{})
    positions=[farm['farmer']]+list(farm.get('hands',[]))
    inventories=private.get('inventories',[])
    commands=[action.get('farmer',[])]+list(action.get('hands',[]))
    seen=set()
    for unit,(position,inventory,command) in enumerate(zip(positions,inventories,commands)):
        route=routes.get(unit,routes.get(str(unit),[]))
        if not route or type(route[0]) is not int or command!=['PASS'] or int((inventory or {}).get('WHEAT',0))>0:
            continue
        tile=int(route[0]);x,y=position
        if tile!=int(y)*10+int(x) or tile in seen:continue
        task=tasks.get(tile,tasks.get(str(tile)))
        if not task or not any(op and op[0]=='FEED' for op in task[0]):continue
        cell=farm['tiles'][int(y)][int(x)]
        if not isinstance(cell,dict) or cell.get('animal') not in ANIMALS or cell.get('fed_today'):continue
        seen.add(tile);diag['blocked'].append(dict(unit=unit,tile=tile,animal=cell['animal']))
    if not seen:return stop('no_observed_blocked_head')
    orders=out.setdefault('market',[])
    if len(orders)>=min(10,int(max_orders)):return stop('order_cap')
    shed=private.get('shed',{})
    pending_wheat=sum(int(o[2]) for o in orders if len(o)>=3 and o[:2]==['BUY_PRODUCT','WHEAT'])
    deficit=max(0,len(seen)-int(shed.get('WHEAT',0))-pending_wheat)
    diag.update(local_deficit=deficit,shed_wheat=int(shed.get('WHEAT',0)),pending_wheat=pending_wheat)
    if not deficit:return stop('already_supplied_or_ordered')
    if price_at is None:return stop('missing_price_callback')
    market_inventory=dict(obs.get('market',{}).get('inventory',{}))
    if 'WHEAT' not in market_inventory:return stop('missing_market_inventory')
    buffer=max(0,int(cfg['quote_buffer']))
    cash=int(farm.get('money',0));reserve=0
    capacity=int(shed_capacity)-sum(max(0,int(v)) for v in shed.values())
    hires=int(farm.get('hires_today',0));land=max(0,len(farm.get('unlocked_quadrants',['NW']))-1)
    for order in orders:
        if not order:continue
        op=order[0]
        if op=='SELL':continue  # Never finance this repair with a requested sale.
        if op=='HIRE':reserve+=int(hire_multiplier)*_fib(hires);hires+=1
        elif op=='BUY_LAND':
            if land<len(LAND_COST):reserve+=LAND_COST[land];land+=1
        elif len(order)>=3:
            item,n=order[1],max(0,int(order[2]))
            if op=='BUY_SEED' and item in SEEDS:reserve+=SEEDS[item]*n
            elif op=='BUY_ANIMAL' and item in ANIMALS:reserve+=ANIMALS[item]*n;capacity-=n
            elif op=='BUY_PRODUCT' and item in ('WHEAT','FERTILIZER'):
                if item not in market_inventory:return stop('missing_market_inventory')
                for _ in range(n):
                    market_inventory[item]-=1
                    reserve+=int(price_at(item,market_inventory[item]))+buffer
                capacity-=n
            else:return stop('unknown_native_order')
        else:return stop('unknown_native_order')
    free_cash=max(0,cash-reserve);quantity=0;cost=0
    limit=min(deficit,max(0,int(cfg['max_buy_per_call'])),max(0,capacity))
    for n in range(1,limit+1):
        next_cost=int(price_at('WHEAT',market_inventory['WHEAT']-n))+buffer
        if cost+next_cost>free_cash:break
        cost+=next_cost;quantity=n
    diag.update(observed_cash=cash,native_cash_reserve=reserve,unreserved_cash=free_cash,
                additional_cost_with_buffer=cost,available_capacity=max(0,capacity))
    if not quantity:return stop('cash_or_capacity')
    orders.append(['BUY_PRODUCT','WHEAT',quantity])
    diag.update(active=True,buy=quantity)
    return stop('observed_route_head_shortfall')
