"""Research prototype: engine-derived crop calendar plus feasible extra-worker tours.

Not a submission agent. Values a ten-cell SE block, with explicit assumptions about
native hiring, release time, inputs and shed room. No inferred leader algorithm.
"""
from functools import lru_cache
from copy import deepcopy
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/fourth_quadrant'
TARGETS=[(x,5) for x in range(5,10)]+[(x,6) for x in range(9,4,-1)]
HOME=[(4,4),(5,4),(4,5),(5,5)]

def calendar(crop,start_day,fertilize):
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    farm=E._new_farm(10,3000);farm['farmer']=[0,0]
    private=E._new_private();private['seeds'][crop]=100
    private['inventories'][0]['FERTILIZER']=100
    cd=E.CROPS[crop];days=[]
    for day in range(start_day,30):
        commands=[];harvest=0;seed=0;fert=0
        def act(cmd):
            nonlocal harvest,seed,fert
            inv=private['inventories'][0];before=inv.get(crop,0);s0=private['seeds'][crop];f0=inv.get('FERTILIZER',0)
            E._apply_unit_action(farm,private,0,cmd,10,day,24)
            harvest+=inv.get(crop,0)-before;seed+=s0-private['seeds'][crop];fert+=f0-inv.get('FERTILIZER',0);commands.append(cmd)
        tile=farm['tiles'][0][0]
        if isinstance(tile,dict) and (tile.get('kind')=='WEED' or cd['ongoing'] and day>tile['planted_day']+cd['first_yield_day']+(cd['max_yield']-1)*cd['interval']):
            act(['DIG']);tile=None
        if tile is None and day+cd['first_yield_day']<=29:act(['PLANT',crop])
        tile=farm['tiles'][0][0]
        if isinstance(tile,dict) and tile.get('crop')==crop:
            age=day-tile['planted_day']
            if cd['ongoing']:
                tomorrow=age+1-cd['first_yield_day']
                productive_tomorrow=tomorrow>=0 and tomorrow%cd['interval']==0 and tomorrow//cd['interval']<cd['max_yield']
                need_fert=productive_tomorrow and day<29
            else:need_fert=(cd['max_yield_day']+1)//2<=age<=cd['max_yield_day']
            if fertilize and need_fert and tile['fertilized_until_day']<day:act(['FERTILIZE'])
            if day<29 or not cd['ongoing']:act(['WATER'])
            if tile['yield_units']>0 and age>=cd['first_yield_day'] and (cd['ongoing'] or age>=cd['max_yield_day'] or day==29):
                act(['HARVEST'])
                if not cd['ongoing'] and day+cd['first_yield_day']<=29:
                    act(['PLANT',crop]);act(['WATER'])
        days.append(dict(day=day,commands=commands,harvest_per_tile=harvest,seeds_per_tile=seed,fertilizer_per_tile=fert))
        E._daily_refresh_plants(farm,day,24)
        # Checked at the beginning of the next day's physical loop in the real engine.
        E._decay_plants(farm,(day+1)*24)
    assert private['inventories'][0].get(crop,0)==sum(d['harvest_per_tile'] for d in days)
    return days

def distance(a,b):return abs(a[0]-b[0])+abs(a[1]-b[1])

def tours(commands,available=20):
    if not commands:return []
    fertilizer=any(c[0]=='FERTILIZE' for c in commands)
    cargo=any(c[0]=='HARVEST' for c in commands)
    @lru_cache(None)
    def split(begin):
        if begin==len(TARGETS):return ()
        best=None
        for end in range(begin+1,len(TARGETS)+1):
            path=TARGETS[begin:end]
            # All four legal shed spawns are supported; agents cannot choose spawn.
            length=max(distance(s,path[0]) for s in HOME)+sum(distance(a,b) for a,b in zip(path,path[1:]))
            length+=len(path)*len(commands)+int(fertilizer)
            if cargo:length+=min(distance(path[-1],h) for h in HOME)+1
            if length>available:continue
            tail=split(end)
            if tail is not None:
                candidate=((begin,end,length),)+tail
                if best is None or len(candidate)<len(best):best=candidate
        return best
    result=split(0)
    if result is None:raise ValueError('No feasible partition')
    return [dict(targets=TARGETS[a:b],worst_spawn_turns=n) for a,b,n in result]

def evaluate(crop,start_day,fertilize,native_hands=8,fertilizer_price=50,available=20):
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    rows=calendar(crop,start_day,fertilize)
    hire=0
    for row in rows:
        row['available_turns']=available-int(row['day']==29)
        row['tours']=tours(row['commands'],row['available_turns'])
        row['hire_cost']=sum(E._fib(native_hands+i) for i in range(len(row['tours'])))
        hire+=row['hire_cost']
    units=10*sum(d['harvest_per_tile'] for d in rows)
    seeds=10*sum(d['seeds_per_tile'] for d in rows);fert=10*sum(d['fertilizer_per_tile'] for d in rows)
    total=4000+seeds*E.CROPS[crop]['seed']+fert*fertilizer_price+hire
    return dict(crop=crop,start_day=start_day,fertilized=fertilize,native_hands=native_hands,available_turns=available,plots=10,harvest_units=units,seeds=seeds,fertilizer=fert,land_cost=4000,seed_cost=seeds*E.CROPS[crop]['seed'],fertilizer_cost=fert*fertilizer_price,hire_cost=hire,total_cost=total,break_even_average_sale_price=total/units if units else None,days=rows)

def verify_plan(plan):
    """Execute every proposed tour in the official physical engine, including growth."""
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    farm=E._new_farm(10,1000000);private=E._new_private();crop=plan['crop']
    for _ in range(3):E._do_buy_land(farm,10)
    private['seeds'][crop]=plan['seeds'];private['shed']['FERTILIZER']=plan['fertilizer']
    acquired=0
    def walk(pos,target):
        x,y=pos;tx,ty=target
        return [['EAST']]*(max(tx-x,0))+[['WEST']]*(max(x-tx,0))+[['SOUTH']]*(max(ty-y,0))+[['NORTH']]*(max(y-ty,0))
    for row in plan['days']:
        farm['hands']=[];farm['hires_today']=0;private['inventories']=[{}];day=row['day']
        for tour in row['tours']:
            # Worst-distance spawn is used to exercise the conservative time bound.
            start=max(HOME,key=lambda h:distance(h,tour['targets'][0]));farm['hands'].append(list(start));private['inventories'].append({})
        sequences=[]
        for tour in row['tours']:
            pos=max(HOME,key=lambda h:distance(h,tour['targets'][0]));seq=[]
            if row['fertilizer_per_tile']:seq.append(['PICKUP','FERTILIZER',len(tour['targets'])*row['fertilizer_per_tile']])
            for target in tour['targets']:
                seq+=walk(pos,target)+deepcopy(row['commands']);pos=target
            if row['harvest_per_tile']:
                target=min(HOME,key=lambda h:distance(pos,h));seq+=walk(pos,target)+[['DROP']]
            assert len(seq)<=row['available_turns'];sequences.append(seq)
        before=private['shed'].get(crop,0)
        for h in range(row['available_turns']):
            for i,seq in enumerate(sequences):
                if h<len(seq):E._apply_unit_action(farm,private,i+1,seq[h],10,day,24)
            E._decay_plants(farm,day*24+(24-plan['available_turns'])+h)
        delta=private['shed'].get(crop,0)-before
        assert delta==10*row['harvest_per_tile'],(crop,day,delta,row)
        acquired+=delta
        private['shed'][crop]=0  # Sell delivered output; shared market valuation is separate.
        E._daily_refresh_plants(farm,day,24)
        E._decay_plants(farm,(day+1)*24)
    assert acquired==plan['harvest_units']
    return acquired

def value_plan(plan,inventory_by_day,fertilizer_inventory_by_day):
    """Value explicit delivery calendar against a supplied BASELINE inventory forecast.

    Added crop sales and input purchases move their own quoted prices. The forecast
    must exclude this candidate's trades. Returns net cash, not a full-game margin.
    """
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    sold=0;bought=0;revenue=0;fert_cost=0;deliveries=[]
    for row in plan['days']:
        day=row['day'];qty=plan['plots']*row['harvest_per_tile'];income=0
        for _ in range(qty):
            price=E.market_price(plan['crop'],inventory_by_day[day]+sold)
            income+=price
            if price>1:sold+=1
        revenue+=income
        for _ in range(plan['plots']*row['fertilizer_per_tile']):
            bought+=1;fert_cost+=E.market_price('FERTILIZER',fertilizer_inventory_by_day[day]-bought)
        if qty:deliveries.append(dict(day=day,units=qty,revenue=income))
    cost=plan['land_cost']+plan['seed_cost']+plan['hire_cost']+fert_cost
    return dict(net_cash=revenue-cost,revenue=revenue,total_cost=cost,fertilizer_cost=fert_cost,deliveries=deliveries)

if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True);plans=[]
    for day in (12,18):
        for crop in ('WHEAT','CARROT','TOMATO','STRAWBERRY'):
            for fert in (False,True):
                for hands in (8,10):
                    plan=evaluate(crop,day,fert,hands);plan['engine_verified_harvest']=verify_plan(plan);plans.append(plan)
    (OUT/'crop_plans.json').write_text(json.dumps(plans,indent=2),encoding='utf-8')
    print(json.dumps([{k:v for k,v in p.items() if k!='days'} for p in plans],indent=2))
