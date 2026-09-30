"""Research: one route-compatible pasture investment and a finite-season feed DP.

Requires the workspace forecaster and official engine; not a packaged submission.
"""
from copy import deepcopy
from functools import lru_cache
from collections import Counter
from market_forecast import E, forecast, sell_value


def calendar(obs, tape, original):
    """Predict the next pickup/placement and service visits using known route code.

    Movement and hire spawning are deterministic; assume planned hires succeed.
    Freeze the current tape across later portfolio boundaries. No future replay
    observations or opponent actions are used.
    """
    t=obs['step'];f=deepcopy(obs['farms'][obs['player']]);tag=None;target=None;placed=None;events={}
    for u in range(t,719):
        a=tape[u];acts=[a['farmer'],*a['hands']]
        for i,act in enumerate(acts):
            pos=E._farmer_position(f,i)
            if pos is None:continue
            if u>t and target is None:
                if act[0]=='PICKUP' and len(act)>1 and act[1]==original and tag is None:tag=i
                if act[0]=='PLACE' and len(act)>1 and act[1]==original and tag==i:
                    target=tuple(pos);placed=u
            if target==tuple(pos) and act[0] in ('FEED','CARE','HARVEST','COLLECT_FERTILIZER'):
                events.setdefault(u//24,[]).append((u,act[0]))
            if act[0] in E.FARMER_MOVES:
                dx,dy=E.FARMER_MOVES[act[0]];x,y=pos[0]+dx,pos[1]+dy
                if 0<=x<10 and 0<=y<10:E._set_farmer_position(f,i,(x,y))
        for o in a.get('market',[])[:10]:
            if o[0]=='HIRE':f['hands'].append(E._spawn_hand(f,10))
        if (u+1)%24==0:
            f['farmer']=[4,4];f['hands']=[]
            if target is None:tag=None
        if target is None and u>t+48:return None
    return {'position':target,'placed':placed,'events':events} if target else None


def lifecycle_dp(species, cal, obs, paths):
    """Optimize daily feed/abandon choices for one animal under fixed service.

    State: day, held yield, accumulated care bonus, missed feeds, own market
    additions. Labor is sunk in the frozen route; feed has its forecast value.
    Product is valued at the day's last usable turn (delivery approximation).
    """
    a=E.ANIMALS[species];product=a['product'];start=cal['placed']//24;t=obs['step']
    def inv(p,u):return paths[p][max(0,min(len(paths[p])-1,u-t))]
    herd=[tile for row in obs['farms'][obs['player']]['tiles'] for tile in row
          if isinstance(tile,dict) and tile.get('animal')==species]
    def baseline_units(day):
        # Existing herd output under daily care; a portfolio-externality proxy,
        # not an exact prediction of all other animals' routing and deliveries.
        return sum(1+a['interval'] for tile in herd
          if day-tile['placed_day']>=a['first_yield_day'] and
          (day-tile['placed_day']-a['first_yield_day'])%a['interval']==0)
    def harvest_value(day,amount,added):
        inventory=inv(product,min(718,day*24+23));q=baseline_units(day)
        without,ib=sell_value(product,inventory,q)
        with_extra,it=sell_value(product,inventory+added,q+amount)
        return with_extra-without,it-ib
    @lru_cache(None)
    def tail(day,added):
        if day>=30:return 0.0
        reward,inc=harvest_value(day,0,added)
        return reward+tail(day+1,added+inc)
    @lru_cache(None)
    def solve(day,held,bonus,missed,added):
        if day>=30:return 0.0,False
        events=cal['events'].get(day,[]);ops={op for _,op in events}
        options=(False,True) if 'FEED' in ops else (False,)
        best=(-1e100,False)
        for fed in options:
            amount=held if 'HARVEST' in ops else 0
            revenue,inc=harvest_value(day,amount,added)
            # Fertilizer is available from the day after placement.
            if day>start and 'COLLECT_FERTILIZER' in ops:
                revenue+=E.market_price('FERTILIZER',inv('FERTILIZER',min(718,day*24+23)))
            if fed:revenue-=E.market_price('WHEAT',inv('WHEAT',min(718,day*24+12)))
            nh=held-amount;nb=bonus;nm=0 if fed else missed+1
            if nm<2 and day<29:
                age=day+1-start-a['first_yield_day']
                if age>=0 and age%a['interval']==0:
                    nh=min(a['max_held'],nh+1+(nb if fed else 0));nb=0
                if fed and 'CARE' in ops:nb+=1
                revenue+=solve(day+1,nh,nb,nm,added+inc)[0]
            elif day<29:
                revenue+=tail(day+1,added+inc)
            # Prefer feeding on ties, keeping physical execution conservative.
            if revenue>best[0] or revenue==best[0] and fed:best=(revenue,fed)
        return best
    value=solve(start,0,0,0,0)[0]-a['cost']
    plan={};state=(0,0,0,0)
    for day in range(start,30):
        held,bonus,missed,added=state;_,fed=solve(day,*state);plan[day]=fed
        ops={op for _,op in cal['events'].get(day,[])}
        amount=held if 'HARVEST' in ops else 0
        _,inc=harvest_value(day,amount,added)
        held-=amount;missed=0 if fed else missed+1
        if missed>=2:break
        age=day+1-start-a['first_yield_day']
        if age>=0 and age%a['interval']==0:held=min(a['max_held'],held+1+(bonus if fed else 0));bonus=0
        if fed and 'CARE' in ops:bonus+=1
        state=(held,bonus,missed,added+inc)
    return {'value':value,'feed_plan':plan,'states':solve.cache_info().currsize}


class PasturePolicy:
    def __init__(self,router,mode='dp',method='visible'):
        self.router=router;self.mode=mode;self.method=method
        self.history=[];self.decision=None;self.target=None;self.carrier=None
        self.stats=Counter();self.max_seconds=0

    def act(self,obs):
        import time
        begun=time.perf_counter();t=obs['step'];me=obs['player'];f=obs['farms'][me];p=obs['private']
        base=self.router.agent(obs);action=deepcopy(base)
        assert len(self.history)==t
        self.history.append({'inventory':dict(obs['market']['inventory']),'shops':list(obs['town']['unlocked_shops'])})
        if self.mode=='raw':return action
        if self.decision is None and 144<=t<=288 and f['money']>=500:
            # An unambiguous single purchase, with no animal already in transit.
            in_transit=any(v.get(a,0) for v in [p['shed'],*p['inventories']] for a in ('COW','SHEEP'))
            buys=[o for o in action['market'] if o[0]=='BUY_ANIMAL']
            if not in_transit and len(buys)==1 and buys[0][1] in ('COW','SHEEP') and int(buys[0][2])==1:
                original=buys[0][1];tape=self.router._TAPES[self.router._SESSIONS[me][1]]
                cal=calendar(obs,tape,original)
                if cal is not None:
                    # Seven days is the longest horizon evaluated previously.
                    # Hold its final inventory prediction beyond that horizon.
                    paths=forecast(obs,self.history,min(168,719-t),self.method)
                    for path in paths.values():path.extend([path[-1]]*(720-t-len(path)))
                    scores={s:lifecycle_dp(s,cal,obs,paths) for s in ('COW','SHEEP')}
                    # Reserve cash for all other requested spending, ignoring
                    # same-turn sale income. Earlier hires must not consume the
                    # replacement animal's budget as happened in the pilot.
                    budget=f['money'];hires=f.get('hires_today',0)
                    for order in action['market'][:10]:
                        op=order[0]
                        if op=='HIRE':budget-=E._hire_cost(hires);hires+=1
                        elif op=='BUY_SEED':budget-=E.CROPS[order[1]]['seed']*int(order[2])
                        elif op=='BUY_PRODUCT':budget-=obs['market']['prices'][order[1]]*int(order[2])
                        elif op=='BUY_LAND':budget-=E.LAND_PRICES[len(f['unlocked_quadrants'])-1]
                    feasible=[s for s in scores if E.ANIMALS[s]['cost']<=budget]
                    if not feasible:
                        feasible=[original]
                    selected=original if self.mode=='original' else self.mode.upper() if self.mode in ('cow','sheep') else max(feasible,key=lambda s:scores[s]['value'])
                    if selected not in feasible:selected=original
                    if self.mode=='dp' and scores[selected]['value']<=0:selected='SKIP'
                    self.decision={'step':t,'original':original,'selected':selected,'scores':scores,'calendar':cal,'feasible':feasible,'budget':budget}
                    if selected=='SKIP':action['market'].remove(buys[0])
                    else:buys[0][1]=selected
                    self.stats['decisions']+=1
        acts=[action['farmer'],*action['hands']]
        if self.decision:
            d=self.decision;original=d['original'];selected=d['selected']
            positions=[f['farmer'],*f['hands']]
            for i,a in enumerate(acts):
                if i>=len(positions):continue
                inv=p['inventories'][i] if i<len(p['inventories']) else {}
                if self.target is None and t>d['step']:
                    if a[0]=='PICKUP' and len(a)>1 and a[1]==original and self.carrier is None:
                        self.carrier=i
                        if selected=='SKIP':a[:]=['PASS']
                        elif p['shed'].get(selected,0):a[1]=selected
                    if a[0]=='PLACE' and len(a)>1 and a[1]==original and self.carrier==i:
                        if selected=='SKIP':a[:]=['PASS'];self.target=tuple(positions[i])
                        elif inv.get(selected,0):a[1]=selected;self.target=tuple(positions[i]);self.stats['placements']+=1
                if self.target==tuple(positions[i]) and a[0] in ('FEED','CARE') and self.mode!='original':
                    plan=d['scores'][selected]['feed_plan'] if selected!='SKIP' else {}
                    if not plan.get(obs['day'],False):a[:]=['PASS'];self.stats['feed_or_care_skipped']+=1
            if t>d['step']+48 and self.target is None:self.stats['placement_overdue']+=1
        # Same liquidation adapter for every non-raw control/candidate. Preserve
        # route orders and sell leftover milk/wool after legal physical actions.
        pf,pp=deepcopy(f),deepcopy(p)
        for i,a in enumerate(acts):E._apply_unit_action(pf,pp,i,a,10,obs['day'],24)
        for item in ('MILK','WOOL'):
            planned=sum(int(o[2]) for o in action['market'] if o[0]=='SELL' and o[1]==item)
            extra=pp['shed'].get(item,0)-planned
            if extra>0:
                existing=next((o for o in action['market'] if o[0]=='SELL' and o[1]==item),None)
                if existing is not None:existing[2]+=extra
                elif len(action['market'])<10:action['market'].append(['SELL',item,extra])
                else:self.stats['liquidation_blocked']+=1
        self.stats['changed_turns']+=action!=base
        self.max_seconds=max(self.max_seconds,time.perf_counter()-begun)
        return action
