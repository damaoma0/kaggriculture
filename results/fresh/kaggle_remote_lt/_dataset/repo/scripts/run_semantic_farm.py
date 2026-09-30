"""Serial full-interpreter integration and paired recorded/live benchmarks.

No future shop schedule enters policy input. Evaluation interpreter is isolated
from the planner's engine and its projections. Both cash ledgers reconcile.
"""
from collections import Counter
from copy import deepcopy
from datetime import datetime,timezone
from hashlib import sha256
import argparse,gzip,json,random,statistics,sys,time,types
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
VENDOR=ROOT/'results/fresh/tape_margin_20260924_01a0/payload/vendor'
sys.path.insert(0,str(VENDOR))
from semantic_farm.policy import SemanticFarm
from semantic_farm.common import species


class Dot(dict):
    def __getattr__(self,name):
        try:return self[name]
        except KeyError as exc:raise AttributeError(name) from exc
    def __setattr__(self,name,value):self[name]=value


def structify(value):
    # Kaggle supplies recursive attribute access; some existing controls depend
    # on observation.town.unlocked_shops, not only the top-level wrapper.
    if isinstance(value,dict):return Dot({k:structify(v) for k,v in value.items()})
    if isinstance(value,list):return [structify(v) for v in value]
    return value


def rules():
    source=(ROOT/'data/kaggriculture.py').read_text(encoding='utf8')
    source=source.split('\njson_path =',1)[0].replace(
        'from kaggle_environments.utils import resolve_episode_seed',
        'def resolve_episode_seed(env): return env.info.get("seed",0)')
    e=types.ModuleType('semantic_evaluation_engine');e.__file__=str(ROOT/'data/kaggriculture.py')
    exec(compile(source,e.__file__,'exec'),e.__dict__)
    return e


def load_agent(name):
    if name.startswith('semantic'):
        return SemanticFarm(care=name!='semantic_fullcare',layout=name!='semantic_uniform')
    if name=='pass':return lambda obs:dict(farmer=['PASS'],hands=[],market=[])
    paths={'v56':ROOT/'data/router_refresh_20260922/v56/main.py',
           'm1':ROOT/'agents/mgt_m1.py','y3':ROOT/'agents/mgt_y3.py',
           'v9lite':ROOT/'agents/mgt_v9lite.py'}
    from kaggle_environments.agent import get_last_callable
    path=paths[name]
    return get_last_callable(path.read_text(encoding='utf8'),path=str(path))


def hashes():
    files=[*sorted((ROOT/'scripts/semantic_farm').glob('*.py')),
        ROOT/'scripts/semantic_strategy.py',ROOT/'scripts/run_semantic_farm.py',
        ROOT/'scripts/cumulative_engine_profiles.py',ROOT/'data/semantic_farm/model.json',
        ROOT/'data/kaggriculture.py',ROOT/'agents/semantic_farm_v1.py',
        ROOT/'scripts/fragments/continuation_executor.py',
        ROOT/'scripts/fragments/continuation_projection.py',
        ROOT/'scripts/fragments/segment_job_executor_v3.py',
        ROOT/'agents/mgt_m1.py',ROOT/'agents/mgt_y3.py',ROOT/'agents/mgt_v9lite.py',
        ROOT/'data/router_refresh_20260922/v56/main.py']
    return {str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in files}


def play(seed,seat,arm,opponent,*,record=None,shops=None,stop=719):
    e=rules();our=load_agent(arm)
    if record is not None:
        rival=lambda obs:deepcopy(record['opp_actions'][obs['step']])
        shops=record['shops']
    else:rival=load_agent(opponent)
    state=[Dot(observation=Dot(step=0,player=s),status='ACTIVE',reward=None,action={}) for s in (0,1)]
    cfg=Dot(episodeSteps=720,boardSize=10,turnsPerDay=24,shedCapacity=100,
        maxMarketOrdersPerTurn=10,farmHandCostMult=1,townShopUnlockInterval=3,
        townShopSellInterval=4,townCenterSellInterval=24,weedSpawnChance=.005)
    env=types.SimpleNamespace(done=False,info={'seed':seed},configuration=cfg)
    e.interpreter(state,env)
    entries=[None,None];entries[seat]=our;entries[1-seat]=rival
    ledger=[dict(revenue=Counter(),spend=Counter()) for _ in (0,1)]
    failure=[Counter(),Counter()];noops=[Counter(),Counter()];current={'step':0}
    seatmap={id(f):s for s,f in enumerate(state[0].observation.farms)}
    original_commit=e._commit_unit;original_hire=e._do_hire;original_land=e._do_buy_land;original_unit=e._apply_unit_action
    def commit(op,item,price,farm,*args,**kwargs):
        result=original_commit(op,item,price,farm,*args,**kwargs)
        s=seatmap[id(farm)]
        if result:ledger[s]['revenue' if op=='SELL' else 'spend'][op+':'+item]+=price
        elif op!='SELL':failure[s][op+':'+item]+=1
        return result
    def atomic(original,label):
        def wrapped(farm,*args,**kwargs):
            before=farm['money'];result=original(farm,*args,**kwargs);s=seatmap[id(farm)]
            if farm['money']!=before:ledger[s]['spend'][label]+=before-farm['money']
            else:failure[s][label]+=1
            return result
        return wrapped
    def unit(farm,private,index,cmd,*args,**kwargs):
        op=cmd[0] if isinstance(cmd,list) and cmd else 'PASS'
        if op in ('PASS','NORTH','SOUTH','EAST','WEST'):return original_unit(farm,private,index,cmd,*args,**kwargs)
        pos=e._farmer_position(farm,index)
        before=deepcopy((farm['tiles'][pos[1]][pos[0]],private)) if pos else None
        result=original_unit(farm,private,index,cmd,*args,**kwargs)
        after=(farm['tiles'][pos[1]][pos[0]],private) if pos else None
        if before==after:noops[seatmap[id(farm)]][op]+=1
        return result
    e._commit_unit=commit;e._do_hire=atomic(original_hire,'HIRE');e._do_buy_land=atomic(original_land,'BUY_LAND');e._apply_unit_action=unit
    timings=[[],[]];daily=[];digest=sha256();started=time.perf_counter()
    def snapshot(t):
        daily.append(dict(step=t,seats=[dict(cash=f['money'],
            counts=dict(Counter(species(tile) for row in f['tiles'] for tile in row if species(tile))),
            cohorts=dict(Counter(f"{species(tile)}:{tile.get('planted_day',tile.get('placed_day'))}"
                for row in f['tiles'] for tile in row if species(tile))),
            land=len(f['unlocked_quadrants']),shed=deepcopy(state[s].observation.private['shed']))
            for s,f in enumerate(state[0].observation.farms)]))
    for t in range(stop):
        day=t//24
        for s in state:s.observation.step=t
        if shops is not None:
            prefix=shops[day] if isinstance(shops[0],list) else shops[:min(8,day//3)]
            state[0].observation.town['unlocked_shops']=list(prefix)
        if t%24==0:snapshot(t)
        for s in (0,1):
            start=time.perf_counter();state[s].action=entries[s](structify(deepcopy(state[s].observation)))
            timings[s].append(time.perf_counter()-start)
        digest.update(json.dumps([s.action for s in state],sort_keys=True).encode())
        e.interpreter(state,env)
        if t and t%144==0:
            print(json.dumps(dict(progress=day,arm=arm,seat=seat,seed=seed,
                cash=state[seat].observation.farms[seat]['money'],elapsed=round(time.perf_counter()-started,1))),flush=True)
    snapshot(stop)
    cash=[f['money'] for f in state[0].observation.farms]
    for s in (0,1):
        assert 3000+sum(ledger[s]['revenue'].values())-sum(ledger[s]['spend'].values())==cash[s]
    return dict(arm=arm,opponent=opponent,seed=seed,seat=seat,episode=record.get('episode') if record else None,
        cash=cash,margin=cash[seat]-cash[1-seat],score=1 if cash[seat]>cash[1-seat] else .5 if cash[seat]==cash[1-seat] else 0,
        completed=all(s.status=='DONE' for s in state),steps=stop,ledger=ledger,ledger_verified=True,
        failed_orders=failure,no_effect=noops,daily=daily,action_sha256=digest.hexdigest(),
        timing=[dict(max=max(ts),p95=sorted(ts)[int(.95*len(ts))],total=sum(ts)) for ts in timings],
        seconds=time.perf_counter()-started,stats=dict(getattr(our,'stats',{})),history=getattr(our,'history',[]))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',required=True);parser.add_argument('--arms',default='semantic')
    parser.add_argument('--opponent',default='v56');parser.add_argument('--seeds',default='924601')
    parser.add_argument('--seats',default='0,1');parser.add_argument('--stop',type=int,default=719)
    parser.add_argument('--panel-limit',type=int,default=0);parser.add_argument('--panel-offset',type=int,default=0)
    args=parser.parse_args();out=ROOT/args.out;out.mkdir(parents=True,exist_ok=True)
    source_hashes=hashes();manifest=out/'manifest.json'
    if manifest.exists():
        if json.loads(manifest.read_text())['hashes']!=source_hashes:raise ValueError('sources_changed_use_new_output')
    else:manifest.write_text(json.dumps(dict(hashes=source_hashes,args=vars(args),created=datetime.now(timezone.utc).isoformat()),indent=2))
    specs=[]
    if args.panel_limit:
        folder=ROOT/'data/ladder_panel/p2750'
        index=json.loads((folder/'index.json').read_text(encoding='utf8'))['games']
        # Deterministic team interleave, no selection using game outcomes.
        groups=defaultdict(list)
        for ep,row in index.items():groups[row['band_team_id']].append(ep)
        ordered=[]
        while any(groups.values()):
            for team in sorted(groups):
                if groups[team]:ordered.append(groups[team].pop(0))
        for ep in ordered[args.panel_offset:args.panel_offset+args.panel_limit]:
            with gzip.open(folder/f'{ep}.json.gz','rt',encoding='utf8') as f:record=json.load(f)
            specs.append((record['seed'],record['seat'],record,None))
    else:
        e=rules()
        for seed in map(int,args.seeds.split(',')):
            rng=random.Random(seed);shops=[rng.choice(sorted(e.SHOPS)) for _ in range(8)]
            for seat in map(int,args.seats.split(',')):specs.append((seed,seat,None,shops))
    for seed,seat,record,shops in specs:
        for arm in args.arms.split(','):
            path=out/f"{record['episode'] if record else seed}-s{seat}-{arm}.json"
            if path.exists():continue
            try:
                result=play(seed,seat,arm,args.opponent,record=record,shops=shops,stop=args.stop)
            except Exception:
                import traceback
                result=dict(completed=False,seed=seed,seat=seat,arm=arm,error=traceback.format_exc())
            path.write_text(json.dumps(result,indent=2),encoding='utf8')
            print(json.dumps({k:result.get(k) for k in ('arm','seed','seat','episode','completed','cash','margin','stats','seconds','error')}),flush=True)
    if source_hashes!=hashes():raise ValueError('sources_changed_during_run')


if __name__=='__main__':
    from collections import defaultdict
    main()
