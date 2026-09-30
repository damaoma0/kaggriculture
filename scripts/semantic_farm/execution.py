"""Fresh routes, staged funding, complete job checks and state-based recovery.

Uses the existing continuation scheduler's chain packing and path primitives.
Purchases, sales and hiring are projected with real cash; no credit is injected.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import time
from fragments import continuation_executor as scheduler
from fragments.continuation_projection import project_step, physical_step
from .common import E, PASS, physical_key, hired_cost
from .economics import input_needs, sell_orders


def advance(obs, action):
    # BUY_LAND is the only extra market operation absent from the inherited own
    # projection. Isolate it in its own pass turn; preceding sales are a turn earlier.
    if any(o[0]=='BUY_LAND' for o in action.get('market',[])):
        if action != dict(PASS,market=[['BUY_LAND']]):raise ValueError('land_requires_separate_turn')
        copied=deepcopy(obs)
        farm=copied['farms'][copied['player']]
        before=len(farm['unlocked_quadrants'])
        E._do_buy_land(farm,len(farm['tiles']))
        result,report=project_step(copied,PASS)
        if len(farm['unlocked_quadrants'])==before:report['failures'].append('land_shortfall')
        return result,report
    return project_step(obs,action)


def quote_buy(obs,op,item,n):
    farm=deepcopy(obs['farms'][obs['player']]);private=deepcopy(obs['private']);market=deepcopy(obs['market'])
    before=farm['money'];filled=0
    for _ in range(n):
        price=(E.CROPS[item]['seed'] if op=='BUY_SEED' else E.ANIMALS[item]['cost']
               if op=='BUY_ANIMAL' else E.market_price(item,market['inventory'][item]-1,market.get('params')))
        if not E._commit_unit(op,item,price,farm,private,market,100):break
        filled+=1
    return before-farm['money'],filled


def financial_orders(obs,jobs,workers,reserve):
    seeds,stock=input_needs(jobs)
    private=obs['private'];farm=obs['farms'][obs['player']]
    for inv in private['inventories']:
        for p,n in inv.items():stock[p]=max(0,stock[p]-n)
    sales=sell_orders(obs,stock)
    # Liquidate existing output before buying or hiring. No seed resale exists.
    if sales:return sales[:10]
    orders=[];virtual=deepcopy(obs)
    vfarm=virtual['farms'][virtual['player']]
    for _ in range(max(0,workers-len(farm['hands'])-1)):
        cost=E._hire_cost(vfarm['hires_today'])
        if vfarm['money']-cost<reserve:return None
        E._do_hire(vfarm,virtual['private'],len(farm['tiles']))
        orders.append(['HIRE'])
        if len(orders)==10:return orders
    for op,needs,inventory in (('BUY_SEED',seeds,private['seeds']),('BUY_PRODUCT',stock,private['shed'])):
        for item,need in sorted(needs.items()):
            missing=max(0,need-inventory.get(item,0))
            if not missing:continue
            buy='BUY_ANIMAL' if item in E.ANIMALS else op
            cost,filled=quote_buy(virtual,buy,item,missing)
            if filled!=missing or vfarm['money']-cost<reserve:return None
            vfarm['money']-=cost
            orders.append([buy,item,missing])
            if len(orders)==10:return orders
    return orders


def remaining_jobs(jobs,positions):
    groups=defaultdict(list)
    for i,job in enumerate(jobs):
        j=dict(job,id=i)
        groups[tuple(j['tile'])].append(j)
    return [scheduler._chain(group) for group in groups.values()]


def batch(obs,jobs,workers,*,reserve=0,collect=False,deadline=None):
    """Compile and execute a batch in a private projection, returning checkpoints.

    All requested jobs must succeed; finance/capacity failures return no actions.
    A collection batch returns all output immediately and can finance the next
    batch. A normal batch may use verified overnight delivery except on day 29.
    """
    projected=deepcopy(obs);actions=[];checkpoints=[];completed=set();commands_count=0
    previous=scheduler.set_deadline(deadline)
    end=23 if obs['day']==29 else 24
    try:
        for _ in range(6):
            scheduler.check_budget()
            orders=financial_orders(projected,jobs,workers,reserve)
            if orders is None:return dict(ok=False,reason='funding_shortfall')
            if not orders:break
            if projected['hour']>=end-1:return dict(ok=False,reason='no_time_for_finance')
            checkpoints.append(physical_key(projected))
            action=dict(PASS,market=orders)
            projected,report=advance(projected,action);actions.append(action)
            if report['failures'] or report['overflow']:return dict(ok=False,reason='finance_projection',report=report)
        else:return dict(ok=False,reason='finance_queue_limit')
        farm=projected['farms'][projected['player']];private=projected['private']
        positions=[tuple(farm['farmer']),*map(tuple,farm['hands'])]
        invs=private['inventories']
        chains=remaining_jobs(jobs,positions)
        if not chains:return dict(ok=True,actions=actions,checkpoints=checkpoints,end=projected,completed=0)
        limit=end-projected['hour']
        if collect:limit=min(limit,16)
        midnight=0 if collect or obs['day']==29 else max(0,100-sum(private['shed'].values()))
        packed=scheduler._pack(chains,positions,invs,len(farm['tiles']),limit,midnight,obs['day'])
        score,routes,infos=packed
        if score[0] or score[1]:return dict(ok=False,reason='route_capacity',score=score)
        streams=[];tags=[]
        for u,route in enumerate(routes):
            pos=positions[u];commands=[];ids=[]
            def append(cmds,identities=None):
                commands.extend(cmds);ids.extend(identities if identities is not None else [None]*len(cmds))
            if any(infos[u][3].values()):
                home=scheduler._nearest_shed(pos,len(farm['tiles']))
                append(scheduler._walk(pos,home));pos=home
                append([['PICKUP',p,n] for p,n in sorted(infos[u][3].items()) if n])
            for chain in route:
                append(scheduler._walk(pos,chain['pos']));pos=chain['pos']
                append([j['cmd'] for j in chain['jobs']],[j['id'] for j in chain['jobs']])
            if infos[u][2]:append(scheduler._walk(pos,scheduler._nearest_shed(pos,len(farm['tiles'])))+[['DROP']])
            streams.append(commands);tags.append(ids)
        length=max(map(len,streams),default=0)
        for offset in range(length):
            scheduler.check_budget()
            checkpoints.append(physical_key(projected))
            commands=[row[offset] if offset<len(row) else ['PASS'] for row in streams]
            physical=dict(farmer=commands[0],hands=commands[1:])
            # Sell actual post-physical shed output while preserving inputs still
            # needed by any remaining pickup. This handles intraday capacity.
            pf,pp,_,_,_=physical_step(projected,physical)
            view=dict(projected,private=pp)
            needed=Counter()
            for row in streams:
                for cmd in row[offset+1:]:
                    if cmd[0]=='PICKUP':needed[cmd[1]]+=cmd[2]
            action=dict(physical,market=sell_orders(view,needed)[:10])
            projected,report=advance(projected,action)
            if report['failures'] or report['overflow']:return dict(ok=False,reason='execution_projection',report=report)
            for u,cmd in enumerate(commands):
                jid=tags[u][offset] if offset<len(tags[u]) else None
                if jid is not None:
                    if u>=len(report['changes']) or not report['changes'][u]:
                        return dict(ok=False,reason='unfulfilled_job',job=jobs[jid],hour=obs['hour']+len(actions))
                    completed.add(jid)
            actions.append(action)
        if len(completed)!=len(jobs):return dict(ok=False,reason='incomplete_jobs')
        return dict(ok=True,actions=actions,checkpoints=checkpoints,end=projected,completed=len(completed))
    except scheduler.PlanningBudgetExceeded:
        return dict(ok=False,reason='planning_budget')
    finally:scheduler.set_deadline(previous)


def idle_to_dawn(obs,*,reserve_stock=None):
    actions=[];checkpoints=[];projected=deepcopy(obs);end=23 if obs['day']==29 else 24
    while projected['day']==obs['day'] and projected['hour']<end:
        checkpoints.append(physical_key(projected))
        action=dict(PASS,market=sell_orders(projected,reserve_stock)[:10])
        projected,_=advance(projected,action);actions.append(action)
    return dict(ok=True,actions=actions,checkpoints=checkpoints,end=projected,completed=0)
