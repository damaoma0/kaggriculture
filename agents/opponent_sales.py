"""Causal opponent delivery estimates and bounded competitive sale scheduling.

Research module. Opponent private inventory and actions are never inspected.
"""
from collections import deque,Counter
from copy import deepcopy
from functools import lru_cache
from kaggle_environments.envs.kaggriculture import kaggriculture as E
from market_forecast import consumption,demand

GOODS=('MILK','WOOL')

def project(obs,action):
    farm=deepcopy(obs['farms'][obs['player']]);private=deepcopy(obs['private'])
    for i,a in enumerate([action['farmer'],*action['hands']]):
        E._apply_unit_action(farm,private,i,a,10,obs['day'],24)
    return farm,private

class DeliveryModel:
    def __init__(self):
        self.previous=None;self.projected=None;self.history=deque(maxlen=96)
        self.latent=dict.fromkeys(GOODS,0.0);self.stats=Counter()

    def observe(self,obs):
        if self.previous is None:return
        old=self.previous;t=old['step'];rival=1-obs['player'];night=(t+1)%24==0
        harvest=dict.fromkeys(GOODS,0.0);ready=dict.fromkeys(GOODS,0.0)
        for y,row in enumerate(old['farms'][rival]['tiles']):
            for x,tile in enumerate(row):
                if not isinstance(tile,dict) or not tile.get('animal'):continue
                p=E.ANIMALS[tile['animal']]['product']
                if p not in GOODS:continue
                ready[p]+=tile['yield_units']
                after=obs['farms'][rival]['tiles'][y][x]
                if not night and isinstance(after,dict) and after.get('animal')==tile['animal']:
                    harvest[p]+=max(0,tile['yield_units']-after['yield_units'])
        record={'step':t,'own':{},'other':{},'harvest':harvest,'ready':ready,'stock':{},'known':{}}
        for p in GOODS:
            projected=self.projected['shed'].get(p,0)
            if night:projected+=sum(v.get(p,0) for v in self.projected['inventories'])
            own=projected-obs['private']['shed'].get(p,0)
            overflow_ambiguous=night and sum(obs['private']['shed'].values())>=100
            price_before=old['market']['prices'][p];price_after=obs['market']['prices'][p]
            known=not overflow_ambiguous and price_before>1 and price_after>1
            total=obs['market']['inventory'][p]-old['market']['inventory'][p]+consumption(t,old['town']['unlocked_shops'],p)
            other=max(0,total-own) if known else harvest[p]
            record['stock'][p]=min(100,self.latent[p]+harvest[p])
            self.latent[p]=max(0,min(100,record['stock'][p]-other))
            record['own'][p]=max(0,own) if not overflow_ambiguous else 0
            record['other'][p]=other;record['known'][p]=known
            if not known:self.stats['ambiguous_product_turns']+=1
        self.history.append(record)

    def commit(self,obs,private):
        self.previous=deepcopy(obs);self.projected=deepcopy(private)

    def predict(self,obs,horizon=24,method='visible'):
        records=list(self.history);farm=deepcopy(obs['farms'][1-obs['player']]);stock=dict(self.latent)
        result={p:[] for p in GOODS};own={p:[] for p in GOODS}
        for k in range(horizon+1):
            t=obs['step']+k;hour=t%24
            same=[r for r in records if r['step']%24==hour]
            for p in GOODS:
                rate=sum(r['other'][p] for r in records)/max(1,len(records))
                hourly=(sum(r['other'][p] for r in same)+rate)/(len(same)+1)
                ownrate=sum(r['own'][p] for r in records)/max(1,len(records))
                own[p].append((sum(r['own'][p] for r in same)+ownrate)/(len(same)+1))
                if method=='recent':q=rate
                elif method=='clock':q=hourly
                else:
                    tiles=[tile for row in farm['tiles'] for tile in row if isinstance(tile,dict)
                           and tile.get('animal') and E.ANIMALS[tile['animal']]['product']==p]
                    harvest_hazard=min(1,(sum(r['harvest'][p] for r in same)+0.25)/(sum(r['ready'][p] for r in same)+4))
                    for tile in tiles:
                        take=tile['yield_units']*harvest_hazard;tile['yield_units']-=take;stock[p]+=take
                    sale_hazard=min(1,(sum(r['other'][p] for r in same)+0.25)/(sum(r['stock'][p] for r in same)+4))
                    q=min(stock[p],stock[p]*sale_hazard)
                    stock[p]-=q
                    # Shrink uncertain hidden-stock estimates toward observed
                    # sale rhythms instead of treating them as exact inventory.
                    q=0.5*q+0.5*hourly
                result[p].append(q)
            if (t+1)%24==0:
                for row in farm['tiles']:
                    for tile in row:
                        if isinstance(tile,dict) and tile.get('animal'):
                            tile['fed_today']=True;tile['cared_today']=True
                # Exact accumulated-care growth, conditional on continued care.
                E._daily_refresh_animals(farm,t//24)
        return own,result

def integer_flow(values):
    result=[];total=0;last=0
    for v in values:
        total+=max(0,v);now=round(total);result.append(now-last);last=now
    return result

def trade_round(item,inventory,ours,theirs):
    """Same-product unit lockstep; both quotes precede each round's commits."""
    own=other=0
    for k in range(max(ours,theirs)):
        price=E.market_price(item,inventory)
        if k<ours:own+=price;inventory+=price>1
        if k<theirs:other+=price;inventory+=price>1
    return own,other,inventory

def schedule(item,inventory,quantity,ours,theirs,drain,objective='margin',deadline=12):
    """Small DP: sell a bounded lot now or at four-turn checkpoints.

    Background shipments are fixed predictions. Includes effects on both
    players' later revenues, not just the sale value of the isolated lot.
    """
    horizon=len(ours)-1
    @lru_cache(None)
    def value(k,left,inv):
        if k>horizon:return 0.0,0
        choices=range(left+1) if k<deadline and k%4==0 else (left,) if k==deadline else (0,)
        best=(-1e100,0)
        for n in choices:
            a,b,end=trade_round(item,inv,ours[k]+n,theirs[k])
            score=a-(b if objective=='margin' else 0)
            score+=value(k+1,left-n,end-drain[k])[0]
            if score>best[0] or score==best[0] and n>best[1]:best=(score,n)
        return best
    return value(0,quantity,float(inventory))

class OpponentPolicy:
    def __init__(self,base,mode='baseline',method='visible'):
        self.base=base;self.mode=mode;self.method=method;self.model=DeliveryModel()
        self.lot=None;self.stats=Counter();self.forecasts=[];self.decisions=[]

    def act(self,obs):
        t=obs['step'];self.model.observe(obs);action=self.base.agent(obs)
        farm,private=project(obs,action);self.model.commit(obs,private)
        if t>=216 and t%24==0 and t<=672:
            predictions={m:self.model.predict(obs,24,m)[1] for m in ('recent','clock','visible')}
            self.forecasts.append({'step':t,'predictions':predictions,'prices':{p:obs['market']['prices'][p] for p in GOODS}})
        if self.mode=='baseline':return action
        # An unconditional priority control isolates the effect of putting these
        # sales first from the additional effect of delivery-aware holding.
        def prioritize():
            action['market'].sort(key=lambda o:0 if o[0]=='SELL' and o[1] in GOODS else 1)
        if self.mode=='priority':prioritize();return action
        stock=private['shed'];burden=sum(stock.values())+sum(sum(v.values()) for v in private['inventories'])
        started=False
        if self.lot is None and 216<=t<=702 and farm['money']>=2500 and burden<=60:
            for o in action['market']:
                if o[0]=='SELL' and o[1] in GOODS:
                    q=min(6,int(o[2]),stock.get(o[1],0))
                    if q>0:self.lot=[o[1],q,min(t+12,718)];started=True;self.stats['lots']+=1;break
        if self.lot is None:prioritize();return action
        item,left,deadline=self.lot
        if stock.get(item,0)<left:self.stats['reservation_shortfall']+=left-stock.get(item,0);left=stock.get(item,0)
        sell=0
        forced=t>=deadline or farm['money']<2500 or burden>=75
        if forced:sell=left
        elif started or t%4==0:
            own,opponent=self.model.predict(obs,min(24,718-t),self.method)
            ours=integer_flow(own[item]);theirs=integer_flow(opponent[item])
            ours[0]=max(0,sum(int(o[2]) for o in action['market'] if o[0]=='SELL' and o[1]==item)-left)
            shops=obs['town']['unlocked_shops'];drain=[]
            expected=sum(demand([s],item) for s in E.SHOPS)/len(E.SHOPS)
            for k in range(len(ours)):
                u=t+k;new=max(0,min(8,u//72)-len(shops))
                drain.append(consumption(u,shops,item)+(new*expected if u%4==0 else 0))
            _,sell=schedule(item,obs['market']['inventory'][item],left,ours,theirs,drain,self.mode,min(deadline-t,len(ours)-1))
            if started:self.decisions.append({'step':t,'item':item,'quantity':left,'sell_now':sell,'predicted_opp_12':sum(theirs[:13])})
        available=max(0,stock.get(item,0)-left);orders=[]
        for o in action['market']:
            if o[0]=='SELL' and o[1]==item:
                n=min(int(o[2]),available);available-=n
                if n:orders.append(['SELL',item,n])
            else:orders.append(list(o))
        if sell:
            existing=next((o for o in orders if o[0]=='SELL' and o[1]==item),None)
            if existing is not None:existing[2]+=sell
            elif len(orders)<10:orders.append(['SELL',item,sell])
            else:sell=0;self.stats['blocked_release']+=1
        if not (started and sell==left):action['market']=orders
        self.stats['delayed_lots']+=int(started and sell<left);self.stats['held_unit_turns']+=left-sell
        left-=sell;self.lot=[item,left,deadline] if left else None
        prioritize();return action

class Stockpiler:
    """Benchmark behavior: same farm routes, batched milk/wool sales."""
    def __init__(self,base):self.base=base
    def agent(self,obs):
        a=self.base.agent(obs);f,p=project(obs,a)
        release=obs['step']%24==12 or obs['step']>=712 or f['money']<2500 or sum(p['shed'].values())>=75
        a['market']=[o for o in a['market'] if not(o[0]=='SELL' and o[1] in GOODS)]
        if release:
            for item in GOODS:
                q=p['shed'].get(item,0)
                if q and len(a['market'])<10:a['market'].append(['SELL',item,q])
        return a
