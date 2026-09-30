"""Visible-state market scenarios, marginal cohort values and funding reserves."""
from collections import Counter, defaultdict
from copy import deepcopy
from functools import lru_cache
import json
import math
from cumulative_engine_profiles import engine_profile
from .common import E, tiles, species, output_product, hired_cost
from .layout import service_load


@lru_cache(maxsize=8192)
def profile(encoded,day):
    out,work,inputs,release=engine_profile(json.loads(encoded),day,30,fertilize=True)
    return dict(output={p:dict(v) for p,v in out.items()},
                work={d:dict(v) for d,v in work.items()},
                inputs={d:dict(v) for d,v in inputs.items()},release=release)


def tile_profile(tile,day):
    return profile(json.dumps(tile,sort_keys=True),day)


def market_scenarios(obs):
    """Price paths for low/central/high rival supply, with future-shop priors.

    All actual future shops remain inaccessible. These are transparent supply
    scenarios, not a fitted rival policy or a claim to predict precise prices.
    """
    day=obs['day']; revealed=obs['town']['unlocked_shops']
    demand=Counter()
    for shop in revealed:
        for p in E.SHOPS[shop]: demand[p]+=6*(2 if len(E.SHOPS[shop])==1 else 1)
    prior=Counter()
    for goods in E.SHOPS.values():
        for p in goods: prior[p]+=6*(2 if len(goods)==1 else 1)/len(E.SHOPS)
    supply=[defaultdict(Counter),defaultdict(Counter)]
    for seat,farm in enumerate(obs['farms']):
        for row in farm['tiles']:
            for tile in row:
                if not species(tile):continue
                for p,by_day in tile_profile(tile,day)['output'].items():
                    for d,n in by_day.items(): supply[seat][d][p]+=n
    paths=[]
    for rival_scale in (.6,1.,1.4):
        inv=deepcopy(obs['market']['inventory']); curve={}
        for d in range(day,30):
            unknown=max(0,min(8,d//3)-len(revealed))
            for p in E.PRODUCTS:
                inv[p]+=supply[obs['player']][d][p]+rival_scale*supply[1-obs['player']][d][p]
                inv[p]-=demand[p]+prior[p]*unknown+(p in E.TOWN_CENTER_PRODUCTS)
            curve[d]=dict(inv)
        paths.append(curve)
    return paths


def quantity_value(obs,quantities,paths=None):
    paths=paths or market_scenarios(obs)
    scores=[]
    for path in paths:
        extra=defaultdict(Counter)
        costs=0
        for s,n in quantities.items():
            if n<=0:continue
            tile=E._new_plant(s,obs['day'],24) if s in E.CROPS else E._new_animal(s,obs['day'])
            pr=tile_profile(tile,obs['day'])
            costs+=n*(E.CROPS[s]['seed'] if s in E.CROPS else E.ANIMALS[s]['cost'])
            for d,inputs in pr['inputs'].items():
                for p,count in inputs.items():
                    costs+=n*count*E.market_price(p,path[d][p],obs['market'].get('params'))
            for p,by_day in pr['output'].items():
                for d,count in by_day.items():extra[d][p]+=n*count
            costs+=n*service_load(s,obs['day'])*2.0
        value=-costs; accumulated=Counter()
        for d in sorted(extra):
            for p,n in extra[d].items():
                # Marginal own receipts plus a conservative rival-price effect
                # is left to full-game evaluation; no linear n*spot valuation.
                for _ in range(n):
                    accumulated[p]+=1
                    value+=E.market_price(p,path[d][p]+accumulated[p],obs['market'].get('params'))
        scores.append(value)
    return dict(mean=sum(scores)/len(scores),low=min(scores),high=max(scores),
                objective=.7*sum(scores)/len(scores)+.3*min(scores))


def reserve_plan(obs,workers,days=3):
    """Conservative cash path for current commitments, with credited deliveries.

    Only half forecast output receipts support new capital; no future shop is
    required for this reserve. Gross new investment is handled by the compiler.
    """
    start=obs['day']; daily=defaultdict(lambda:dict(inputs=Counter(),output=Counter()))
    for _,tile in tiles(obs):
        if not species(tile):continue
        p=tile_profile(tile,start)
        for d,items in p['inputs'].items():daily[d]['inputs'].update(items)
        for product,values in p['output'].items():
            for d,n in values.items():daily[d]['output'][product]+=n
    balance=0.;minimum=0.;rows=[]
    stock=Counter(obs['private']['shed'])
    for inv in obs['private']['inventories']:stock.update(inv)
    for d in range(start+1,min(30,start+days+1)):
        wages=hired_cost(0,max(0,workers-1))
        cost=wages
        for product,n in daily[d]['inputs'].items():
            used=min(stock[product],n);stock[product]-=used
            cost+=(n-used)*obs['market']['prices'].get(product,0)
        balance-=cost;minimum=min(minimum,balance)
        income=.5*sum(n*obs['market']['prices'].get(p,0) for p,n in daily[d]['output'].items())
        balance+=income
        rows.append(dict(day=d,cost=cost,discounted_income=income,balance=balance))
    # Opening financing is staged on daily fertilizer income, with a wage floor.
    floor=hired_cost(0,max(0,workers-1)) if start<29 else 0
    return dict(reserve=max(floor,math.ceil(-minimum)),wage_floor=floor,days=rows)


def input_needs(jobs):
    seeds,stock=Counter(),Counter()
    for j in jobs:
        cmd=j['cmd'];op=cmd[0]
        if op=='PLANT':seeds[cmd[1]]+=1
        elif op=='FEED':stock['WHEAT']+=1
        elif op=='FERTILIZE':stock['FERTILIZER']+=1
        elif op=='PLACE' and cmd[1] in E.ANIMALS:stock[cmd[1]]+=1
    return seeds,stock


def sell_orders(obs,stock_reserve=None):
    reserve=Counter(stock_reserve or {})
    shed=obs['private']['shed']
    return [['SELL',p,int(shed[p]-reserve[p])] for p in sorted(E.PRODUCTS,
        key=lambda p:(-obs['market']['prices'][p],p)) if shed.get(p,0)>reserve[p]]
