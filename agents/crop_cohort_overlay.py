"""Research overlay: tiny existing-land cohorts, serviced by native worker slack.

Appended to the frozen corrected V45 source by build_crop_cohorts.py. No extra
hires or land orders. A hand can leave its route only after its last native
command of the day; hands disappear at midnight. New crops are sold separately.
"""
_COHORT_PARENT = agent
_COHORT_CONFIG = dict(crop='CARROT', start=20, plots=4, per_day=1, gate=False)
_COHORT_STATE = {}
_COHORT_STATS = {}
_COHORT_HOME = ((4,4),(5,4),(4,5),(5,5))

def _cohort_walk(a,b):
    x,y=a;u,v=b
    return [['EAST'] for _ in range(max(0,u-x))]+[['WEST'] for _ in range(max(0,x-u))]+[['SOUTH'] for _ in range(max(0,v-y))]+[['NORTH'] for _ in range(max(0,y-v))]

def _cohort_distance(a,b):return abs(a[0]-b[0])+abs(a[1]-b[1])

def _cohort_ops(tile,crop,day,seed_count,initial=False):
    """Observed-state obligations, including planting-day water and ripe harvest."""
    ops=[];cd=_PLANNER_NS['CROPS'][crop]
    if initial:
        if isinstance(tile,dict) and tile.get('yield_units',0):ops.append(['HARVEST'])
        if tile is not None:ops.append(['DIG'])
        return ops+[['PLANT',crop],['WATER']] if seed_count else []
    if isinstance(tile,dict) and tile.get('crop')==crop:
        age=day-tile['planted_day']
        ready=tile.get('yield_units',0)>0 and age>=cd['first_yield_day'] and (cd['ongoing'] or age>=cd['max_yield_day'] or day==29)
        need_water=not tile.get('watered_today') and (tile.get('consecutive_unwatered',0)>=1 or age==0 or not cd['ongoing'] and age>=2)
        # A native visit may provide only one action. On the final lifespan day,
        # collect existing carrot yield before attempting one more growth bonus.
        if ready and not cd['ongoing']:
            return [['HARVEST']]+([['PLANT',crop],['WATER']] if day+cd['first_yield_day']<=29 and seed_count else [])
        if need_water and (day<29 or not cd['ongoing']):ops.append(['WATER'])
        if ready:
            ops.append(['HARVEST'])
            if not cd['ongoing'] and day+cd['first_yield_day']<=29 and seed_count:ops += [['PLANT',crop],['WATER']]
        return ops
    if day+cd['first_yield_day']>29 or not seed_count:return []
    if tile is not None:ops.append(['DIG'])
    return ops+[['PLANT',crop],['WATER']]

def _cohort_native_free(obs,actor):
    t=int(obs['step']);end=min(719,(t//24+1)*24)
    farm,private=_PLANNER_NS['_clone_state'](obs['farms'][obs['player']],obs['private'])
    for u in range(t,end):
        commands=_r128_commands(_r128_future(obs,u-t))
        c=commands[actor] if actor<len(commands) else ['PASS']
        if c[0] in ('PASS','DROP'):continue
        if c[0] in MOVES:
            _PLANNER_NS['_apply_unit_action'](farm,private,actor,c,10,t//24,24,100)
            continue
        x,y=farm['hands'][actor-1]
        if (x,y) in _COHORT_STATE['managed'] and c[0] in ('WATER','HARVEST','FERTILIZE','DIG','PLANT'):continue
        # Reject any remaining potential productive operation. Empty-field
        # water/harvest visits may be bypassed; future seed purchases are unknown.
        tile=farm['tiles'][y][x]
        if c[0] in ('WATER','HARVEST','FERTILIZE') and not isinstance(tile,dict):continue
        if c[0]=='WATER' and isinstance(tile,dict) and tile.get('watered_today'):continue
        if c[0]=='HARVEST' and isinstance(tile,dict) and not tile.get('yield_units',0):continue
        return False
    return True

def _cohort_run(obs,action):
    global _COHORT_STATE
    t=int(obs['step']);day,hour=divmod(t,24);cfg=_COHORT_CONFIG
    if t==0 or not _COHORT_STATE:
        _COHORT_STATE=dict(day=-1,managed={},queues={},pending=[],daily_new=0,credit=0,last_harvest=[],lost=set())
        _COHORT_STATS.clear();_COHORT_STATS.update(commitments=[],harvested_units=0,seed_orders=0,borrowed_hands=0,commands=0,plant_failures=0,missing_plants=0,errors=0,sales_requested=0,free_windows=0,options=0)
    state=_COHORT_STATE
    if day<cfg['start']:return action
    farm=obs['farms'][obs['player']];private=obs['private'];crop=cfg['crop'];positions=[farm['farmer'],*farm['hands']]
    if state['day']!=day:
        state['credit']+=min(private['shed'].get(crop,0),state.pop('night_credit',0))
        state.update(day=day,queues={},daily_new=0)
        for xy,meta in state['managed'].items():
            x,y=xy;tile=farm['tiles'][y][x]
            if isinstance(tile,dict) and tile.get('kind')=='WEED' and xy not in state['lost']:
                state['lost'].add(xy);_COHORT_STATS['missing_plants']+=1
    for actor,before,item in state['last_harvest']:
        if actor<len(private['inventories']):_COHORT_STATS['harvested_units']+=max(0,private['inventories'][actor].get(item,0)-before)
    state['last_harvest']=[]
    for due,xy in state['pending']:
        if due==t:
            x,y=xy;tile=farm['tiles'][y][x]
            if not isinstance(tile,dict) or tile.get('crop')!=crop:_COHORT_STATS['plant_failures']+=1
    state['pending']=[]
    result=copy.deepcopy(action);commands=_r128_commands(result)
    commands += [['PASS'] for _ in range(len(positions)-len(commands))]
    # Preserve route movements. Only tile operations on our explicitly managed
    # cells change; existing care visits can satisfy the new crop's obligations.
    reserved={tuple(q['target']) for q in state['queues'].values() if q['ops']}
    for actor,xy in enumerate(positions):
        xy=tuple(xy)
        if xy in state['managed'] and actor not in state['queues'] and commands[actor][0] in ('PLANT','DIG','WATER','HARVEST','FERTILIZE'):
            x,y=xy;ops=_cohort_ops(farm['tiles'][y][x],crop,day,private['seeds'].get(crop,0))
            commands[actor]=ops[0] if ops and xy not in reserved else ['PASS']
            reserved.add(xy)
    # Buy only a small seed reserve; purchases execute after unit commands.
    seeds=private['seeds'].get(crop,0)
    can_start=len(state['managed'])<cfg['plots'] and state['daily_new']<cfg['per_day'] and day<=min(29-_PLANNER_NS['CROPS'][crop]['first_yield_day'],cfg['start']+3)
    if cfg['gate']:
        shops=obs['town']['unlocked_shops']
        can_start &= (sum(s in ('PIZZA_SHOP','FARMERS_MARKET') for s in shops)>=3 if crop=='TOMATO' else sum(s in ('PET_CAFE','FARMERS_MARKET') for s in shops)>=1)
    if seeds<2 and (can_start or state['managed']) and day+_PLANNER_NS['CROPS'][crop]['first_yield_day']<=29 and farm['money']>4000 and len(result['market'])<10:
        n=2-seeds;result['market'].append(['BUY_SEED',crop,n]);_COHORT_STATS['seed_orders']+=n
    for actor in range(1,len(positions)):
        if actor in state['queues']:continue
        if commands[actor][0] not in ('PASS','DROP',*MOVES) or hour<8 or not _cohort_native_free(obs,actor):continue
        # Expansion workers have their own dynamic routes, not the native tape.
        native=_IMPL.chassis.players[int(obs['player'])]
        native_count=max((len(a.get('hands',[])) for a in _v219_native_day(native,day)),default=0)
        if actor>native_count:continue
        _COHORT_STATS['free_windows']+=1
        options=[];available=min(24-hour,719-t)
        for xy in state['managed']:
            if xy in reserved:continue
            x,y=xy;ops=_cohort_ops(farm['tiles'][y][x],crop,day,seeds)
            if ops:options.append((False,xy,ops))
        if can_start and seeds>0:
            for y,row in enumerate(farm['tiles']):
                for x,tile in enumerate(row):
                    xy=(x,y)
                    if xy in state['managed'] or xy in reserved:continue
                    if not isinstance(tile,dict) or tile.get('crop')!='STRAWBERRY' or tile.get('yield_units',0)>0:continue
                    if day-tile['planted_day']<12:continue
                    options.append((True,xy,_cohort_ops(tile,crop,day,seeds,True)))
        best=None
        _COHORT_STATS['options']+=len(options)
        for initial,xy,ops in options:
            seq=_cohort_walk(positions[actor],xy)+ops
            home=min(_COHORT_HOME,key=lambda h:_cohort_distance(xy,h))
            delivery=_cohort_walk(xy,home)+[['DROP']]
            # Ordinary days automatically deposit hand inventories at midnight.
            # The final day has no midnight: explicitly return and DROP then.
            if day==29 or len(seq)+len(delivery)<=available:seq += delivery
            if len(seq)>available:continue
            priority=(initial,len(seq),xy)
            if best is None or priority<best[0]:best=(priority,xy,seq,initial)
        if best:
            _,xy,seq,initial=best
            state['queues'][actor]=dict(target=xy,ops=seq);reserved.add(xy);_COHORT_STATS['borrowed_hands']+=1
            seeds-=sum(c[0]=='PLANT' for c in seq)
            if initial:
                state['managed'][xy]=dict(day=day);state['daily_new']+=1
                _COHORT_STATS['commitments'].append(dict(day=day,xy=list(xy),crop=crop))
                can_start=len(state['managed'])<cfg['plots'] and state['daily_new']<cfg['per_day']
    for actor,q in state['queues'].items():
        if actor<len(commands):commands[actor]=q['ops'].pop(0) if q['ops'] else ['PASS']
    for actor,cmd in enumerate(commands[:len(positions)]):
        xy=tuple(positions[actor])
        if xy in state['managed']:
            if cmd==['HARVEST']:state['last_harvest'].append((actor,private['inventories'][actor].get(crop,0),crop))
            if cmd==['PLANT',crop]:state['pending'].append((t+1,xy))
    result['farmer'],result['hands']=commands[0],commands[1:]
    if hour==23:
        _,after=_r127_fields(obs,result)
        state['night_credit']=sum(after['inventories'][i].get(crop,0) for i in state['queues'] if i<len(after['inventories']))
    _COHORT_STATS['commands']+=sum(a!=b for a,b in zip(commands,_r128_commands(action)))
    # Sell incremental crop deliveries immediately, leaving the baseline's stock
    # reservation untouched. Compare projected stock with and without cohort DROP.
    projected=projected_shed(result,FarmView(obs)).get(crop,0)
    without=copy.deepcopy(result)
    for actor in state['queues']:
        if actor<=len(without['hands']) and without['hands'][actor-1]==['DROP']:without['hands'][actor-1]=['PASS']
    other=projected_shed(without,FarmView(obs)).get(crop,0)
    state['credit']+=max(0,projected-other)
    scheduled=sum(int(o[2]) for o in result['market'] if o[:2]==['SELL',crop])
    state['credit']=max(0,state['credit']-max(0,scheduled-other))
    amount=min(state['credit'],max(0,projected-scheduled))
    if amount and len(result['market'])<10:
        result['market'].append(['SELL',crop,amount]);state['credit']-=amount;_COHORT_STATS['sales_requested']+=amount
    return result

def agent(observation,configuration=None):
    action=_COHORT_PARENT(observation,configuration)
    return _cohort_run(observation,action)

agent=globals().pop('agent')
