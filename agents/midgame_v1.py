"""Observed-state midgame scheduler; local research, uses the installed engine.

Only our own farm/private state is projected to allocate simultaneous actions.
No seed, future shops, or opponent private state is used.
"""
from copy import deepcopy
from math import ceil
from kaggle_environments.envs.kaggriculture import kaggriculture as E

SHEDS=((4,4),(5,4),(4,5),(5,5))
DEFAULT={"hands_cap":12,"work_per_hand":16,"fertilizer":"sell","extra_cows":0,"extra_sheep":0,
         "reserve":300,"replant":"WHEAT","land":False,"sell_floor":0,"stop_day":22}


def distance(a,b):return abs(a[0]-b[0])+abs(a[1]-b[1])
def move(a,b):
    if a[0]!=b[0]:return ["EAST" if a[0]<b[0] else "WEST"]
    if a[1]!=b[1]:return ["SOUTH" if a[1]<b[1] else "NORTH"]
    return ["PASS"]


class Midgame:
    def __init__(self,initial,config=None):
        self.cfg=dict(DEFAULT,**(config or {}))
        f=initial['farms'][initial['player']]
        self.slots={(x,y):t.get('animal') or t.get('crop') for y,row in enumerate(f['tiles']) for x,t in enumerate(row) if isinstance(t,dict) and (t.get('animal') or t.get('kind')=='PLANT')}
        self.herd={a:sum(v==a for v in self.slots.values())+self.cfg.get('extra_cows' if a=='COW' else 'extra_'+a.lower(),0) for a in E.ANIMALS}
        self.targets={}
        self.day=-1

    def layout(self,f,day):
        result={}
        for y,row in enumerate(f['tiles']):
            for x,t in enumerate(row):
                if isinstance(t,dict) and (t.get('animal') or t.get('kind')=='PLANT'):
                    result[x,y]=t.get('animal') or t['crop']
        free=sorted(((x,y) for y,row in enumerate(f['tiles']) for x,t in enumerate(row) if t!='LOCKED' and (x,y) not in result),key=lambda p:(min(distance(p,s) for s in SHEDS),p))
        for animal,target in self.herd.items():
            if day+E.ANIMALS[animal]['first_yield_day']+2>29 or day>self.cfg['stop_day']:continue
            for p in free[:max(0,target-sum(v==animal for v in result.values()))]:result[p]=animal
            free=[p for p in free if p not in result]
        crop=self.cfg['replant']
        if crop and day+max(E.CROPS[crop]['first_yield_day'],E.CROPS[crop]['max_yield_day'])<=28:
            for p in free:
                if p in self.slots or self.cfg['land']:result[p]=crop
        return result

    def __call__(self,obs):
        day,hour,step=obs['day'],obs['hour'],obs['step']
        f=deepcopy(obs['farms'][obs['player']]); private=deepcopy(obs['private'])
        if self.day!=day:self.targets={}; self.day=day
        layout=self.layout(f,day); claimed=set(); actions=[]
        positions=[f['farmer'],*f['hands']]
        def shed(pos):return min(SHEDS,key=lambda s:distance(pos,s))
        def job(pos,inv,p,item):
            tile=f['tiles'][p[1]][p[0]]; travel=distance(pos,p)
            if isinstance(tile,dict) and tile.get('kind')=='PLANT':
                cd=E.CROPS[tile['crop']]; age=day-tile['planted_day']
                due=age>=cd['first_yield_day']
                urgent=tile['consecutive_unwatered']>=1
                production=cd['ongoing'] and age+1>=cd['first_yield_day'] and (age+1-cd['first_yield_day'])%cd['interval']==0
                want_fert=self.cfg['fertilizer']=='apply' and tile.get('fertilized_until_day',-1)<day and (production or not cd['ongoing'] and age>=(cd['max_yield_day']+1)//2) and not tile['watered_today']
                if want_fert and inv.get('FERTILIZER',0) and not (urgent and hour+travel>=22):return 150,['FERTILIZE'],p
                if want_fert and not inv.get('FERTILIZER',0) and private['shed'].get('FERTILIZER',0) and not urgent and hour+distance(pos,shed(pos))+distance(shed(pos),p)+2<20:
                    return 120,['PICKUP','FERTILIZER',min(3,private['shed']['FERTILIZER'])],shed(pos)
                bonus=not cd['ongoing'] and (cd['max_yield_day']+1)//2<=age<=cd['max_yield_day'] and tile['yield_units']<cd['max_yield']
                if not tile['watered_today'] and (urgent or bonus or production and tile.get('fertilized_until_day',-1)>=day):
                    return (1000 if urgent else 140),['WATER'],p
                if due and tile['yield_units'] and (cd['ongoing'] or age>=cd['max_yield_day'] or tile['yield_units']>=cd['max_yield']):return 130,['HARVEST'],p
                if want_fert and private['shed'].get('FERTILIZER',0):return 40,['PICKUP','FERTILIZER',min(3,private['shed']['FERTILIZER'])],shed(pos)
                if not tile['watered_today']:return 25,['WATER'],p
                return None
            if isinstance(tile,dict) and tile.get('animal'):
                if not tile['fed_today']:
                    priority=1000 if tile['consecutive_unfed']>=1 else 160
                    if inv.get('WHEAT',0):return priority,['FEED'],p
                    if private['shed'].get('WHEAT',0):return priority,['PICKUP','WHEAT',min(6,private['shed']['WHEAT'])],shed(pos)
                if not tile['cared_today']:return 100,['CARE'],p
                if tile['yield_units']:return 125,['HARVEST'],p
                if tile['fertilizer_available']:return 65,['COLLECT_FERTILIZER'],p
                return None
            if hour+travel+4>=24:return None
            if item in E.ANIMALS:
                if inv.get(item,0):
                    if tile is None:return 45,['BUILD_'+('COOP' if item=='GOOSE' else 'PASTURE')],p
                    if tile.get('kind')=='WEED':return 45,['DIG'],p
                    return 45,['PLACE',item,1],p
                if private['shed'].get(item,0):return 45,['PICKUP',item,1],shed(pos)
            elif private['seeds'].get(item,0):
                if tile is None:return 60,['PLANT',item],p
                if isinstance(tile,dict) and tile.get('kind') in ('WEED','PASTURE','COOP'):return 55,['DIG'],p
            return None
        for i,pos in enumerate(positions):
            inv=private['inventories'][i]
            goods=sum(n for p,n in inv.items() if p not in E.ANIMALS and p not in ('WHEAT','FERTILIZER'))
            total_carried=sum(sum(n for p,n in v.items() if p not in E.ANIMALS) for v in private['inventories'])
            carrying=next((a for a in E.ANIMALS if inv.get(a,0)),None)
            choices=[]
            for p,item in layout.items():
                if p in claimed or carrying and item!=carrying:continue
                task=job(pos,inv,p,item)
                if not task:continue
                priority,op,goal=task
                travel=distance(pos,goal)+(distance(goal,p) if op[0]=='PICKUP' else 0)
                if hour+travel>=24:continue
                score=priority/(1+travel*.35)+(18 if tuple(pos)==p else 0)+(6 if self.targets.get(i)==p else 0)
                choices.append((score,p,goal,op))
            if goods and (goods>=10 or total_carried+sum(private['shed'].values())>80 or step>=712):
                goal=shed(pos); priority=2000 if step>=712 else 145
                choices.append((priority/(1+distance(pos,goal)*.35),None,goal,['DROP']))
            if choices:
                _,p,goal,op=max(choices,key=lambda x:x[0])
                if p is not None:claimed.add(p); self.targets[i]=p
                act=op if tuple(pos)==tuple(goal) else move(pos,goal)
            else:act=['PASS']
            if step>=712 and any(inv.values()) and not carrying:
                goal=shed(pos)
                if distance(pos,goal)<=718-step:act=['DROP'] if tuple(pos)==goal else move(pos,goal)
            actions.append(act)
            E._apply_unit_action(f,private,i,act,len(f['tiles']),day,24)
        animals=sum(1 for row in f['tiles'] for t in row if isinstance(t,dict) and t.get('animal'))
        plants=sum(1 for row in f['tiles'] for t in row if isinstance(t,dict) and t.get('kind')=='PLANT')
        empty_jobs=sum(1 for p,crop in layout.items() if crop in E.CROPS and not (isinstance(f['tiles'][p[1]][p[0]],dict) and f['tiles'][p[1]][p[0]].get('kind')=='PLANT'))
        target=min(self.cfg['hands_cap'],max(1,ceil((animals*7+plants*3+empty_jobs*4)/self.cfg['work_per_hand'])-1))
        market=[]; cash=f['money']
        feed_keep=animals*2
        fert_keep=plants//2 if self.cfg['fertilizer']=='apply' else 0
        for p,n in private['shed'].items():
            keep=feed_keep if p=='WHEAT' else fert_keep if p=='FERTILIZER' else 0
            if p in E.PRODUCTS and n>keep and (obs['market']['prices'][p]>=self.cfg['sell_floor'] or day>=27):market.append(['SELL',p,n-keep])
        if hour<12 and len(f['hands'])<target:
            a,b=1,1
            for _ in range(f['hires_today']):a,b=b,a+b
            if cash>=a:market.append(['HIRE']);cash-=a
        wheat=private['shed'].get('WHEAT',0)+sum(v.get('WHEAT',0) for v in private['inventories'])
        need=max(0,feed_keep-wheat)
        price=obs['market']['prices']['WHEAT']+10
        buy=min(need,int(cash//price))
        if buy:market.append(['BUY_PRODUCT','WHEAT',buy]);cash-=buy*price
        for animal in E.ANIMALS:
            wanted=sum(v==animal for v in layout.values())
            owned=sum(1 for row in f['tiles'] for t in row if isinstance(t,dict) and t.get('animal')==animal)+private['shed'].get(animal,0)+sum(v.get(animal,0) for v in private['inventories'])
            cost=E.ANIMALS[animal]['cost'] if 'cost' in E.ANIMALS[animal] else {'COW':400,'SHEEP':500,'GOOSE':300}[animal]
            count=min(max(0,wanted-owned),max(0,int((cash-self.cfg['reserve'])//cost)))
            if count:market.append(['BUY_ANIMAL',animal,count]);cash-=count*cost
        needs={}
        for p,crop in layout.items():
            tile=f['tiles'][p[1]][p[0]]
            if crop in E.CROPS and (tile is None or isinstance(tile,dict) and tile.get('kind') in ('WEED','PASTURE','COOP')):needs[crop]=needs.get(crop,0)+1
        for crop,n in needs.items():
            count=min(n-private['seeds'].get(crop,0),max(0,int((cash-50)//E.CROPS[crop]['seed'])))
            if count>0:market.append(['BUY_SEED',crop,count]);cash-=count*E.CROPS[crop]['seed']
        if self.cfg['land'] and day<=18 and len(f['unlocked_quadrants'])<3:
            cost=1000 if len(f['unlocked_quadrants'])==1 else 2000
            if cash>=cost+self.cfg['reserve']:market.append(['BUY_LAND'])
        if step>=712:market=[['SELL',p,n] for p,n in private['shed'].items() if p in E.PRODUCTS and n>0]
        return {'farmer':actions[0],'hands':actions[1:],'market':market[:10]}
