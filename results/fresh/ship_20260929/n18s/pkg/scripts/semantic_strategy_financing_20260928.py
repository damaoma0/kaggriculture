"""Pure, optional release of early capital-funding goods from sell pacing.

No orders, globals, observations or plans are modified. Only today's admitted
inputs, current own inventory and current quotes are read. The existing seller
performs the sales. Whole-lot granularity and quote-based proceeds estimates are
explicit limitations; actual completion/cash is rechecked on the next call.
"""
from collections import Counter
from itertools import combinations

SEEDS = {"WHEAT":10,"CARROT":20,"TOMATO":50,"STRAWBERRY":100,"MELON":80}
ANIMALS = {"COW":400,"SHEEP":500,"GOOSE":300}
LAND = ("NW","NE","SW","SE")
LAND_COST = (1000,2000,4000)
FUNDING_PRODUCTS = ("WOOL","MILK","EGG","FERTILIZER")
DEFAULT_CONFIG = dict(enabled=False,start_day=6,end_day=10,price_floor=5,
                      proceeds_factor=.85,include_hires=True,include_feed=True)


def _get(value,key,default=None):
    return value.get(key,default) if isinstance(value,dict) else getattr(value,key,default)


def _today(plan,field,day):
    rows=_get(plan,field)
    return rows[day] if rows is not None else {}


def _tile(farm,index):
    return farm["tiles"][int(index)//10][int(index)%10]


def _quad(index):
    return ("N" if int(index)//10<5 else "S")+("W" if int(index)%10<5 else "E")


def _mapped(mapping,key,fallback):
    return int(mapping.get(key,mapping.get(str(key),fallback)))


def _fib(index):
    a,b=1,1
    for _ in range(max(0,int(index))):a,b=b,a+b
    return a


def capital_pacing_products(obs,tile_plan,executor_state,base_books,config=None,walk_cap=None):
    """Return (new paced-product list, diagnostics), leaving every input intact.

    ``tile_plan`` may be a TilePlanView or its plain dictionary. ``executor_state``
    is KB's current state, used only for observed completion/remapping and current
    retirement intent. ``walk_cap(product, market_inventory, floor, held)`` must
    approve the ENTIRE held shed lot; missing inputs/callback disable that lot.
    Only current own private stocks count. Unharvested and carried sale goods do
    not finance purchases until they actually reach the shed.
    """
    cfg=dict(DEFAULT_CONFIG);cfg.update(config or {})
    books=list(base_books or ())
    diag=dict(enabled=bool(cfg['enabled']),active=False,released_products=[],
              whole_lot_limitation=True,proceeds_are_estimates=True)
    if not cfg['enabled']:
        return books,dict(diag,reason='disabled')
    step=int(obs.get('step',24*int(obs.get('day',0))+int(obs.get('hour',0))))
    day,hour=divmod(step,24);diag.update(day=day,hour=hour)
    if not max(6,int(cfg['start_day']))<=day<=min(10,int(cfg['end_day'])):
        return books,dict(diag,reason='outside_early_window')
    farm=obs['farms'][int(obs['player'])];private=obs.get('private',{})
    shed=Counter(private.get('shed',{}));held=Counter(shed)
    for inventory in private.get('inventories',[]):held.update(inventory or {})
    seeds=private.get('seeds',{})
    state=executor_state or {};pmap=state.get('pmap',{});smap=state.get('smap',{})
    done=state.get('done',set())
    unlocked=set(farm.get('unlocked_quadrants',['NW']))
    land_days=_get(tile_plan,'land_day',{})
    due={q for q,d in land_days.items() if q in LAND and int(d)<=day}
    last_needed=max([LAND.index(q) for q in unlocked|due]+[0])
    due.update(LAND[:last_needed+1])

    def available(index,cell):
        if cell=='LOCKED':return _quad(index) in due
        # A live animal cannot be removed during today's work, including one
        # already committed to an overnight escape. Do not finance its slot.
        return not isinstance(cell,dict) or not cell.get('animal')

    remaining_seeds=Counter();remaining_animals=Counter();blocked=Counter()
    for tile,crop in _today(tile_plan,'plant',day).items():
        if crop not in SEEDS:continue
        tile=int(tile);key=(day,tile);index=_mapped(pmap,key,tile);cell=_tile(farm,index)
        if key in done or (isinstance(cell,dict) and cell.get('crop')==crop
                           and int(cell.get('planted_day',-1))>=day):continue
        if not available(index,cell):blocked['plant_live_animal_or_locked']+=1;continue
        remaining_seeds[crop]+=1
    wanted_animals={int(tile):sp for tile,sp in _today(tile_plan,'animals_by_day',day).items() if sp in ANIMALS}
    for tile,sp in wanted_animals.items():
        index=_mapped(smap,tile,tile);cell=_tile(farm,index)
        if isinstance(cell,dict) and cell.get('animal')==sp:continue
        if not available(index,cell):blocked['animal_live_animal_or_locked']+=1;continue
        remaining_animals[sp]+=1
    buy_seeds={sp:max(0,n-int(seeds.get(sp,0))) for sp,n in remaining_seeds.items()}
    buy_animals={sp:max(0,n-int(held.get(sp,0))) for sp,n in remaining_animals.items()}
    buy_seeds={s:n for s,n in buy_seeds.items() if n};buy_animals={s:n for s,n in buy_animals.items() if n}
    land_cost=sum(LAND_COST[i-1] for i,q in enumerate(LAND) if i and q in due and q not in unlocked)
    target_hands=int(_today(tile_plan,'hands',day) or 0)
    remaining_hires=max(0,target_hands-len(farm.get('hands',[]))) if cfg['include_hires'] and hour<=12 else 0
    hire_cost=sum(_fib(int(farm.get('hires_today',0))+i) for i in range(remaining_hires))
    prices=obs.get('market',{}).get('prices',{})
    feed_count=0
    if cfg['include_feed']:
        retire=state.get('_xretire',{}) if int(state.get('day',-1))==day else {}
        feed_count=sum(1 for y,row in enumerate(farm['tiles']) for x,t in enumerate(row)
            if isinstance(t,dict) and t.get('animal') in ANIMALS and not t.get('fed_today')
            and y*10+x not in retire and str(y*10+x) not in retire)
        feed_count+=sum(remaining_animals.values())
    feed_buy=max(0,feed_count-int(held.get('WHEAT',0)))
    costs=dict(seeds=sum(SEEDS[s]*n for s,n in buy_seeds.items()),
               animals=sum(ANIMALS[s]*n for s,n in buy_animals.items()),land=land_cost,
               hires=hire_cost,feed=feed_buy*(max(1,float(prices.get('WHEAT',25)))+2))
    required=sum(costs.values());cash=float(farm.get('money',0));shortfall=max(0.,required-cash)
    diag.update(remaining_inputs=dict(seeds=buy_seeds,animals=buy_animals,hires=remaining_hires,feed=feed_buy),
        remaining_jobs=dict(plants=dict(remaining_seeds),animals=dict(remaining_animals)),blocked_jobs=dict(blocked),
        remaining_cost=costs,required_cash=required,observed_cash=cash,shortfall=shortfall)
    if shortfall<=0:return books,dict(diag,reason='already_funded')
    if walk_cap is None:return books,dict(diag,reason='missing_price_floor_callback')
    market_inventory=obs.get('market',{}).get('inventory',{})
    factor=max(0.,min(1.,float(cfg['proceeds_factor'])));floor=max(0.,float(cfg['price_floor']))
    lots=[];rejected={}
    for product in FUNDING_PRODUCTS:
        if product not in books:continue
        quantity=max(0,int(shed.get(product,0)))
        if not quantity:continue
        if product not in market_inventory or product not in prices:
            rejected[product]='missing_current_market';continue
        if float(prices[product])<=floor:
            rejected[product]='current_quote_at_floor';continue
        if int(walk_cap(product,int(market_inventory[product]),floor,quantity))!=quantity:
            rejected[product]='whole_lot_crosses_price_floor';continue
        value=quantity*float(prices[product])*factor
        if value>0:lots.append(dict(product=product,quantity=quantity,estimated_proceeds=value))
    diag.update(eligible_lots=lots,rejected_lots=rejected)
    if not lots:return books,dict(diag,reason='no_eligible_shed_lot')
    subsets=[subset for n in range(1,len(lots)+1) for subset in combinations(lots,n)]
    enough=[s for s in subsets if sum(l['estimated_proceeds'] for l in s)>=shortfall]
    if enough:
        # Four products give at most fifteen subsets. Minimize excess proceeds
        # first, then order slots; deterministic ties use fixed product names.
        chosen=min(enough,key=lambda s:(sum(l['estimated_proceeds'] for l in s)-shortfall,
                                      len(s),tuple(l['product'] for l in s)))
    else:chosen=tuple(lots)
    released={lot['product'] for lot in chosen};credit=sum(lot['estimated_proceeds'] for lot in chosen)
    diag.update(active=True,reason='capital_shortfall',released_products=[p for p in books if p in released],
                selected_lots=list(chosen),estimated_released_proceeds=credit,
                estimated_excess=max(0.,credit-shortfall),estimated_remaining_shortfall=max(0.,shortfall-credit))
    return [product for product in books if product not in released],diag
