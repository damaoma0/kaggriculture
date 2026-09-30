"""Isolated crop-module execution probe; not a full-farm competition policy.

Rebuild daily routes from tile jobs. Module definitions contain relative-day work,
not recorded movement, worker identities, or future shop information.
"""
import itertools as _pm_it

PM_MODULES = [{'crop': 'CARROT', 'events': [{'day': 0, 'command': ['PLANT', 'CARROT']}, {'day': 0, 'command': ['WATER']}, {'day': 2, 'command': ['FERTILIZE']}, {'day': 2, 'command': ['WATER']}, {'day': 3, 'command': ['WATER']}, {'day': 3, 'command': ['HARVEST']}], 'expected_harvest': 4, 'source': {'leader': 'UMG56266758', 'submission': 56266758, 'episode': 109712554, 'tile': [4, 6], 'planting_day': 14}}, {'crop': 'CARROT', 'events': [{'day': 0, 'command': ['PLANT', 'CARROT']}, {'day': 0, 'command': ['WATER']}, {'day': 2, 'command': ['FERTILIZE']}, {'day': 2, 'command': ['WATER']}, {'day': 3, 'command': ['WATER']}, {'day': 3, 'command': ['HARVEST']}], 'expected_harvest': 4, 'source': {'leader': 'UMG56266758', 'submission': 56266758, 'episode': 109712554, 'tile': [2, 2], 'planting_day': 14}}, {'crop': 'CARROT', 'events': [{'day': 0, 'command': ['PLANT', 'CARROT']}, {'day': 0, 'command': ['WATER']}, {'day': 2, 'command': ['FERTILIZE']}, {'day': 2, 'command': ['WATER']}, {'day': 3, 'command': ['WATER']}, {'day': 3, 'command': ['HARVEST']}], 'expected_harvest': 4, 'source': {'leader': 'UMG56266758', 'submission': 56266758, 'episode': 109712554, 'tile': [4, 6], 'planting_day': 14}}, {'crop': 'CARROT', 'events': [{'day': 0, 'command': ['PLANT', 'CARROT']}, {'day': 0, 'command': ['WATER']}, {'day': 2, 'command': ['FERTILIZE']}, {'day': 2, 'command': ['WATER']}, {'day': 3, 'command': ['WATER']}, {'day': 3, 'command': ['HARVEST']}], 'expected_harvest': 4, 'source': {'leader': 'UMG56266758', 'submission': 56266758, 'episode': 109712554, 'tile': [2, 2], 'planting_day': 14}}]
PM_START_DAY = 12
PM_TILES = [(2, 3), (3, 2), (1, 3), (3, 1)]
PM_REPORT = {'days': [], 'rejections': [], 'missing_inputs': []}
_PM_STATE = {}


def _pm_walk(a, b):
    x,y=a;tx,ty=b;out=[]
    while x != tx:
        out.append(['EAST' if x<tx else 'WEST']);x+=1 if x<tx else -1
    while y != ty:
        out.append(['SOUTH' if y<ty else 'NORTH']);y+=1 if y<ty else -1
    return out


def _pm_compile(obs, day):
    seat=int(obs['player']);farm=obs['farms'][seat];private=obs['private']
    blocks=[];fert=0
    for i,m in enumerate(PM_MODULES):
        ops=[list(e['command']) for e in m['events'] if e['day']==day-PM_START_DAY]
        if not ops:continue
        tile=PM_TILES[i];v=farm['tiles'][tile[1]][tile[0]]
        if any(c[0]=='PLANT' for c in ops):
            if isinstance(v,dict) and v.get('kind')=='WEED':ops.insert(0,['DIG'])
            elif v is not None:
                PM_REPORT['rejections'].append([day,i,'occupied planting tile']);return []
        blocks.append((i,tile,ops));fert+=sum(c[0]=='FERTILIZE' for c in ops)
    if not blocks:return []
    available=private['shed'].get('FERTILIZER',0)+private['inventories'][0].get('FERTILIZER',0)
    if fert>available:PM_REPORT['missing_inputs'].append([day,'FERTILIZER',fert,available]);return []
    prefix=[]
    need=max(0,fert-private['inventories'][0].get('FERTILIZER',0))
    if need:prefix.append(['PICKUP','FERTILIZER',need])
    options=[]
    for order in _pm_it.permutations(blocks):
        route=list(prefix);pos=tuple(farm['farmer'])
        for _,tile,ops in order:
            route+=_pm_walk(pos,tile)+ops;pos=tile
        route+=_pm_walk(pos,(4,4))+[['DROP']]
        options.append((len(route),tuple(x[0] for x in order),route))
    length,order,route=min(options)
    # Starts at hour one; stop before the final game action or day reset.
    if length>22:PM_REPORT['rejections'].append([day,'route exceeds available hours',length]);return []
    PM_REPORT['days'].append({'day':day,'commands':length,'order':order,'permutations':len(options)})
    return route


def production_module_entry(obs):
    t=int(obs['step']);day,h=divmod(t,24)
    if t==0:
        _PM_STATE.clear();PM_REPORT.update(days=[],rejections=[],missing_inputs=[])
    action={'farmer':['PASS'],'hands':[],'market':[]}
    if h==0:
        seeds={};fert=0
        for m in PM_MODULES:
            for e in m['events']:
                if e['day']!=day-PM_START_DAY:continue
                c=e['command']
                if c[0]=='PLANT':seeds[c[1]]=seeds.get(c[1],0)+1
                if c[0]=='FERTILIZE':fert+=1
        for crop,n in seeds.items():
            need=max(0,n-obs['private']['seeds'].get(crop,0))
            if need:action['market'].append(['BUY_SEED',crop,need])
        need=max(0,fert-obs['private']['shed'].get('FERTILIZER',0))
        if need:action['market'].append(['BUY_PRODUCT','FERTILIZER',need])
    if h==1:_PM_STATE['route']=_pm_compile(obs,day)
    route=_PM_STATE.get('route',[])
    if h>=1 and h-1<len(route):action['farmer']=route[h-1]
    if h==23 or t==718:
        action['market'] += [['SELL',k,n] for k,n in obs['private']['shed'].items() if n>0 and k not in ('FERTILIZER',)]
    return action
