"""Research-only causal event features. No rival private state or future tapes.

Engine crop/animal constants define potential production, not promised harvests.
Regression calibration maps these uncertain events to aggregate net market flow.
"""
from math import sin,cos,pi
from kaggle_environments.envs.kaggriculture import kaggriculture as E

ITEMS=('WHEAT','CARROT','MILK','WOOL')
HORIZONS=(12,24,48,72)

def consume(t,shops,item):
    return (sum(2 if len(E.SHOPS[s])==1 else 1 for s in shops if item in E.SHOPS[s]) if t%4==0 else 0)+int(t%24==0)

def demand_forecast(t,shops,item,horizon):
    expected=sum(sum(2 if len(E.SHOPS[s])==1 else 1 for s in [name] if item in E.SHOPS[s]) for name in E.SHOPS)/len(E.SHOPS)
    return sum(consume(u,shops,item)+(max(0,min(8,u//72)-len(shops))*expected if u%4==0 else 0) for u in range(t,t+horizon))

def product(tile):
    if not isinstance(tile,dict):return None
    if tile.get('animal'):return E.ANIMALS[tile['animal']]['product']
    return tile.get('crop')

class EventModel:
    def __init__(self):self.previous=None;self.records=[]

    def observe(self,obs):
        if self.previous is not None:
            old=self.previous;t=old['step'];harvest={p:[0.,0.] for p in ITEMS}
            for side in (0,1):
                for y,row in enumerate(old['farms'][side]['tiles']):
                    for x,tile in enumerate(row):
                        p=product(tile)
                        if p not in ITEMS:continue
                        after=obs['farms'][side]['tiles'][y][x]
                        q=tile.get('yield_units',0)
                        # Exclude decay and midnight production/death ambiguity.
                        if (t+1)%24==0 or 0<=tile.get('max_lifespan_step',-1)<=t:continue
                        if product(after)==p:
                            harvest[p][side]+=max(0,q-after.get('yield_units',0))
                        elif after is None:harvest[p][side]+=q
            flows={p:obs['market']['inventory'][p]-old['market']['inventory'][p]+consume(t,old['town']['unlocked_shops'],p) for p in ITEMS}
            self.records.append(dict(step=t,flows=flows,harvest=harvest))
            self.records=self.records[-96:]
        # Save public fields only; caller can never expose rival private holdings.
        from copy import deepcopy
        self.previous=deepcopy({k:obs[k] for k in ('step','farms','market','town')})

    def production(self,obs,item,horizon,side):
        t=int(obs['step']);day=t//24;ready=0.;count=0;early=0.;late=0.;arrivals=[0.,0.,0.]
        for row in obs['farms'][side]['tiles']:
            for tile in row:
                if product(tile)!=item:continue
                count+=1;q=float(tile.get('yield_units',0))
                animal=tile.get('animal')
                if animal:
                    cd=E.ANIMALS[animal];first=tile['placed_day']+cd['first_yield_day']
                    ready+=q
                    events=[(t,q)] if q else []
                    first_future=True
                    for d in range(day+1,(t+horizon)//24+1):
                        if d>=first and (d-first)%cd['interval']==0:
                            # Conditional care: first observed pending bonus, later
                            # one care per day. Calibration can downweight it.
                            bonus=tile.get('pending_care_bonus',0) if first_future else cd['interval']
                            events.append((d*24,min(cd['max_held'],1+bonus)));first_future=False
                    early+=sum(n for when,n in events if when<t+horizon)
                    late+=sum(n for when,n in events if when+24<t+horizon)
                else:
                    cd=E.CROPS[item];birth=tile['planted_day'];first=birth+cd['first_yield_day'];last=birth+cd['max_yield_day']
                    if day>=first:ready+=q
                    early_day=max(day,first);late_day=max(day,last)
                    def potential(d):
                        extra=sum(2 if k<=tile.get('fertilized_until_day',-1) else 1
                                  for k in range(day,d+1) if (cd['max_yield_day']+1)//2<=k-birth<=cd['max_yield_day']
                                  and not(k==day and tile.get('watered_today')))
                        return min(cd['max_yield'],q+extra)
                    early_q=potential(early_day);late_q=potential(late_day)
                    early+=early_q if early_day*24<t+horizon else 0
                    late+=late_q if late_day*24<t+horizon else 0
                    events=[(max(t,late_day*24),late_q)]
                for when,n in events:
                    # Three possible routes to market: direct, +12h, midnight.
                    for i,arrival in enumerate((when,when+12,(when//24+1)*24)):
                        if arrival<t+horizon:arrivals[i]+=n
        return [count,ready,early,late,*arrivals]

    def features(self,obs,item,horizon):
        t=int(obs['step']);inv=obs['market']['inventory'][item];shops=obs['town']['unlocked_shops']
        drain=demand_forecast(t,shops,item,horizon)
        rates=[];signed=[]
        for window in (12,24,48,96):
            rows=[r for r in self.records if r['step']>=t-window]
            rates.append(sum(r['flows'][item] for r in rows)/max(1,len(rows)))
            signed += [sum(max(0,r['flows'][item]) for r in rows)/max(1,len(rows)),sum(min(0,r['flows'][item]) for r in rows)/max(1,len(rows))]
        clock=0.
        for u in range(t,t+horizon):
            rows=[r for r in self.records if r['step']%24==u%24]
            clock+=(sum(r['flows'][item] for r in rows)+rates[-1])/(len(rows)+1)
        base=[t/720,inv-10000,obs['market']['prices'][item],drain,sin(2*pi*(t%24)/24),cos(2*pi*(t%24)/24),
              *[v*horizon for v in rates],*[v*horizon for v in signed],clock]
        events=[];seat=int(obs['player'])
        for side in (seat,1-seat):
            events+=self.production(obs,item,horizon,side)
            for window in (12,24,48,96):
                events.append(sum(r['harvest'][item][side] for r in self.records if r['step']>=t-window))
        own=obs.get('private',{});events += [own.get('shed',{}).get(item,0),sum(v.get(item,0) for v in own.get('inventories',[]))]
        return dict(base=base,event=base+events,drain=drain,inventory=inv,
                    current=inv,flow=inv+.5*(rates[1]+rates[2])*horizon-drain,
                    clock=inv+clock-drain)
