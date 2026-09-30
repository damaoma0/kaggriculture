"""Production columns simulated through the checked-in Kaggriculture mechanics.

Each column describes a worker servicing one tile; transportation/procurement
is accounted elsewhere. Harvest labels are actual successful inventory gains.
The only engine shim replaces episode-seed resolution, unused by these pure
tile operations. No installed modules are replaced in sys.modules.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import types

ENGINE_PATH=Path(__file__).resolve().parents[1]/'data/kaggriculture.py'
SOURCE=ENGINE_PATH.read_text(encoding='utf-8')
ENGINE_SHA256=sha256(ENGINE_PATH.read_bytes()).hexdigest()
ENGINE=types.ModuleType('_cumulative_exact_tile_engine')
ENGINE.__file__=str(ENGINE_PATH)
_prefix=SOURCE.split('\njson_path =',1)[0].replace(
    'from kaggle_environments.utils import resolve_episode_seed',
    'def resolve_episode_seed(env): return env.info.get("seed", 0)')
exec(compile(_prefix,str(ENGINE_PATH),'exec'),ENGINE.__dict__)
PRODUCTS=ENGINE.PRODUCTS

def engine_profile(tile,start,end,*,fertilize=False,new_crop=None,harvest_age=None,care=True,collect_fertilizer=True,return_trace=False):
    """Return (product->day->units, day->actions, day->inputs, release_day).

    End and release_day are exclusive. A freed tile can be reused the following
    day; same-day harvest/replant is deliberately outside these columns. Plant,
    build, PLACE, PICKUP and travel are caller-side commitments. Native current
    tile fields are preserved. Fertilizer and feed are symbolically supplied to
    the servicing worker, then charged only when the engine consumes them.
    """
    if new_crop:tile=ENGINE._new_plant(new_crop,start,24)
    tile=deepcopy(tile)
    if not isinstance(tile,dict):raise ValueError('profile needs an existing native tile or new_crop')
    farm={'tiles':[[tile]],'farmer':[0,0],'hands':[]}
    private={'inventories':[{}],'seeds':{},'shed':{}}
    output=defaultdict(lambda:defaultdict(int));work=defaultdict(Counter);inputs=defaultdict(Counter)
    trace=[];release=end
    for day in range(start,end):
        hour=0;hours=23 if day==29 else 24
        def act(action):
            nonlocal hour
            if hour>=hours:raise AssertionError('tile service exceeds a day')
            inv=private['inventories'][0]
            op=action[0]
            resource={'FEED':'WHEAT','FERTILIZE':'FERTILIZER'}.get(op)
            if resource:inv[resource]=inv.get(resource,0)+1
            before=Counter(inv)
            ENGINE._apply_unit_action(farm,private,0,action,1,day,24)
            after=Counter(inv)
            work[day][op.lower()]+=1
            if resource:inputs[day][resource]+=before[resource]-after[resource]
            if op in ('HARVEST','COLLECT_FERTILIZER'):
                for p in PRODUCTS:
                    if after[p]>before[p]:output[p][day]+=after[p]-before[p]
            trace.append({'day':day,'hour':hour,'action':action,'gain':dict(after-before),
                          'tile_after':deepcopy(farm['tiles'][0][0])})
            ENGINE._decay_plants(farm,24*day+hour)
            hour+=1
        current=farm['tiles'][0][0]
        if isinstance(current,dict) and current.get('kind')=='PLANT':
            crop=current['crop'];cd=ENGINE.CROPS[crop];age=day-current['planted_day']
            one_time=not cd['ongoing']
            grow=one_time and (cd['max_yield_day']+1)//2<=age<=cd['max_yield_day'] and current['yield_units']<cd['max_yield']
            next_age=age+1-cd['first_yield_day']
            produces_tonight=(not one_time and next_age>=0 and next_age%cd['interval']==0
                              and next_age//cd['interval']<cd['max_yield'] and day+1<end)
            if fertilize and (grow or produces_tonight) and current.get('fertilized_until_day',-1)<day:
                act(['FERTILIZE'])
            current=farm['tiles'][0][0]
            # Survival needs a drink after a missed day, and on the planting day.
            # Yield growth and an active fertilizer bonus can require extra water.
            if isinstance(current,dict) and current.get('kind')=='PLANT':
                need_water=(grow or (produces_tonight and current.get('fertilized_until_day',-1)>=day)
                            or (day<end-1 and current.get('consecutive_unwatered',0)>=1))
                if need_water and not current.get('watered_today'):act(['WATER'])
            current=farm['tiles'][0][0]
            if isinstance(current,dict) and current.get('kind')=='PLANT':
                ready=age>=cd['first_yield_day'] and current.get('yield_units',0)>0
                chosen_age=cd['max_yield_day'] if harvest_age is None else max(cd['first_yield_day'],harvest_age)
                if ready and (not one_time or age>=chosen_age or current['yield_units']>=cd['max_yield']):act(['HARVEST'])
            current=farm['tiles'][0][0]
            # Ongoing crops finish after exactly max_yield production events.
            last_age=cd['first_yield_day']+(cd['max_yield']-1)*cd['interval'] if cd['ongoing'] else cd['max_yield_day']
            if isinstance(current,dict) and current.get('kind')=='PLANT' and cd['ongoing'] and age>=last_age and current.get('yield_units',0)==0:
                act(['DIG'])
        elif isinstance(current,dict) and current.get('animal'):
            ad=ENGINE.ANIMALS[current['animal']]
            if day<end-1 and not current.get('fed_today'):act(['FEED'])
            # Today's care is banked after tonight's production. It only helps
            # a later collection if a productive refresh is still ahead.
            future_bonus=any(d>day+1 and d<end and d-current['placed_day']>=ad['first_yield_day']
                             and (d-current['placed_day']-ad['first_yield_day'])%ad['interval']==0
                             for d in range(day+2,end))
            if care and future_bonus and not current.get('cared_today'):act(['CARE'])
            if collect_fertilizer and current.get('fertilizer_available'):act(['COLLECT_FERTILIZER'])
            if current.get('yield_units',0):act(['HARVEST'])
        current=farm['tiles'][0][0]
        if isinstance(current,dict) and current.get('kind')=='WEED':act(['DIG'])
        if farm['tiles'][0][0] is None:
            release=day+1
            break
        while hour<hours:
            ENGINE._decay_plants(farm,24*day+hour);hour+=1
        if day!=29:
            ENGINE._daily_refresh_plants(farm,day,24)
            ENGINE._daily_refresh_animals(farm,day)
    answer=(output,work,inputs,release)
    return (*answer,trace) if return_trace else answer

def validate_profiles():
    checks=[]
    for crop,expected in [('WHEAT',4),('CARROT',3),('TOMATO',4),('STRAWBERRY',4),('MELON',6)]:
        out,work,inputs,release=engine_profile(None,0,30,new_crop=crop)
        assert sum(out[crop].values())==expected,(crop,dict(out[crop]))
        assert release<30,(crop,release)
        checks.append(dict(asset=crop,mode='unfertilized',output=dict(out[crop]),release=release,
                           actions=sum(sum(x.values()) for x in work.values())))
    for crop,expected in [('WHEAT',6),('CARROT',4),('TOMATO',8),('STRAWBERRY',8),('MELON',6)]:
        out,work,inputs,release=engine_profile(None,0,30,new_crop=crop,fertilize=True)
        assert sum(out[crop].values())==expected,(crop,dict(out[crop]))
        assert sum(x['FERTILIZER'] for x in inputs.values())>0
        checks.append(dict(asset=crop,mode='fertilized',output=dict(out[crop]),release=release))
    for animal,first,second in [('GOOSE',4,5),('COW',8,10),('SHEEP',6,9)]:
        out,work,inputs,release=engine_profile(ENGINE._new_animal(animal,0),0,30)
        product=ENGINE.ANIMALS[animal]['product'];cap=ENGINE.ANIMALS[animal]['max_held']
        assert min(out[product])==first,(animal,out[product])
        assert out[product][first]==min(cap,first),(animal,out[product])
        assert out[product][second]==1+ENGINE.ANIMALS[animal]['interval'],(animal,out[product])
        assert sum(x['WHEAT'] for x in inputs.values())==29
        assert sum(out['FERTILIZER'].values())==29
        checks.append(dict(asset=animal,output=dict(out[product]),fertilizer=sum(out['FERTILIZER'].values())))
    # Existing dry crop, fertilizer window, held yield and care bank are consumed
    # from the actual tile rather than reset to a new cohort's nominal state.
    wheat=ENGINE._new_plant('WHEAT',0,24);wheat.update(yield_units=3,consecutive_unwatered=1)
    out,work,_,release=engine_profile(wheat,3,6)
    assert out['WHEAT'][4]==5 and work[3]['water']==1 and release==5
    sheep=ENGINE._new_animal('SHEEP',0);sheep.update(pending_care_bonus=2,yield_units=1,fertilizer_available=True)
    out,_,_,_=engine_profile(sheep,5,10)
    assert out['WOOL'][5]==1 and out['WOOL'][6]==3 and out['WOOL'][9]==4
    # End is exclusive: no day-10 harvest is credited to a horizon ending at10.
    out,_,_,_=engine_profile(None,0,10,new_crop='MELON')
    assert not out['MELON']
    return dict(engine_sha256=ENGINE_SHA256,checks=checks,passed=True,
                note='Exact checked-in unit/decay/nightly mechanics; tile service only, transportation excluded.')

if __name__=='__main__':
    import json
    print(json.dumps(validate_profiles(),indent=2))
