"""Frozen 96-pair coverage panel. Every arm runs in a fresh local process."""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import argparse
import gzip
import importlib
import json
import os
import statistics
import subprocess
import sys
import time
import traceback

OUT = Path(__file__).resolve().parent
PAYLOAD = OUT / 'payload'

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=True), encoding='utf-8')
    tmp.replace(path)

def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',',':')).encode()).hexdigest()

def verify():
    manifest = json.loads((OUT / 'source_manifest.json').read_text())
    for name, expected in manifest['sha256'].items():
        assert sha256((PAYLOAD/name).read_bytes()).hexdigest() == expected, name

def specs():
    result = json.loads((OUT/'random_design.json').read_text())['specs']
    recording_path = OUT/'recording_design.json'
    if recording_path.exists():
        for team in json.loads(recording_path.read_text())['selected']:
            for ep in team['episodes']:
                opp = next(a['seat'] for a in ep['agents'] if a['submission']==team['submission']['id'])
                result.append(dict(id=f'replay-{ep["id"]}', world=ep['id'], kind='replay',
                    episode=ep['id'], seat=1-opp, opponent=team['team']['team'],
                    submission=team['submission']['id'], rating=team['submission']['score']))
    return result

def physical_key(farm):
    return digest([farm[k] for k in ('tiles','farmer','hands','unlocked_quadrants','hires_today')])

def clean_observation(obs):
    return {k:v for k,v in obs.items() if k not in ('remainingOverageTime','step')}

def run_game(spec, arm):
    verify()
    sys.path[:0] = [str(PAYLOAD/'scripts'),str(PAYLOAD/'vendor')]
    imported = time.perf_counter()
    N = importlib.import_module('value_tape_search_v9')
    import_seconds = time.perf_counter()-imported
    V,R = N.V,N.V.R
    E = R.engine()
    import psutil
    process=psutil.Process()
    peak_rss=process.memory_info().rss
    assert set(N.B.M.M.DEMAND)==set(E.SHOPS)
    recording = None
    if spec['kind']=='replay':
        with gzip.open(OUT/'recordings'/f'{spec["episode"]}.json.gz','rt',encoding='utf-8') as f:
            recording=json.load(f)
        world=dict(seed=recording['seed'],seat=spec['seat'],episode=spec['episode'],shops=recording['shops'])
    else:
        assert all(shop in E.SHOPS for shop in spec['shops'])
        world=dict(seed=spec['seed'],seat=spec['seat'],episode=0,
            shops=[spec['shops'][:min(8,d//3)] for d in range(31)])
    seat=spec['seat']; opp=1-seat
    initialization = time.perf_counter()
    ours = None if arm=='recording' else V.fresh_agent()
    setup_seconds=import_seconds+time.perf_counter()-initialization
    if spec['kind']=='live':
        if spec['opponent']=='original_m1':
            rival=V.fresh_agent()
            assert ours.__globals__ is not rival.__globals__
            assert ours.__globals__['_MGT_IMPL'] is not rival.__globals__['_MGT_IMPL']
        else:
            from kaggle_environments.agent import get_last_callable
            path=PAYLOAD/'data/router_refresh_20260922/v56/main.py'
            rival=get_last_callable(path.read_text(encoding='utf-8'),path=str(path))
            assert rival.__name__=='e410_agent'
    reference=None
    if recording is not None and arm!='recording':
        reference=json.loads((OUT/'arms'/f'{spec["id"]}-recording.json').read_text())
        assert reference['completed'] and reference['reproduced_exactly']
    chassis=None if ours is None else ours.__globals__['_MGT_IMPL'].chassis
    router=None if chassis is None else chassis.router
    decisions=[]; actions=[[],[]]; prefix=[]; daily=[]; timings=[]
    keys=[[],[]]; actual_keys=[[],[]]; private_keys=[[],[]]
    physical=[Counter(),Counter()]; requested=[Counter(),Counter()]
    physical_daily=[]; logged_spawns=[{},{}]
    bank=60.0; observation_checks=[]
    obs_by_step={} if recording is None else {x['step']:x['seats'] for x in recording['observations']}
    with R.Simulator(world) as sim:
        state=deepcopy(sim.initial)
        old_unit, old_spawn=E._apply_unit_action,E._spawn_weeds
        in_engine=False
        def work(farm, private, idx, action, *args, **kwargs):
            if not in_engine:
                return old_unit(farm,private,idx,action,*args,**kwargs)
            row=physical[sim.seats[id(farm)]]
            if idx>=len(private['inventories']):
                row['missing_worker_commands']+=1
                return old_unit(farm,private,idx,action,*args,**kwargs)
            if not isinstance(action,list) or not action or not isinstance(action[0],str):
                row['malformed_commands']+=1
                return old_unit(farm,private,idx,action,*args,**kwargs)
            op=action[0];row['commands']+=1;row['op:'+op]+=1
            if op in E.FARMER_MOVES or op=='PASS':
                return old_unit(farm,private,idx,action,*args,**kwargs)
            inv=deepcopy(private['inventories'][idx]); seeds=dict(private['seeds'])
            pos=E._farmer_position(farm,idx)
            tile=deepcopy(farm['tiles'][pos[1]][pos[0]]) if pos else None
            value=old_unit(farm,private,idx,action,*args,**kwargs)
            after=private['inventories'][idx]
            tile_after=farm['tiles'][pos[1]][pos[0]] if pos else None
            ineffective=(inv==after if op in ('DROP','PLACE','PICKUP') else
                         inv==after and tile==tile_after and seeds==private['seeds'])
            if ineffective:
                row['no_effect']+=1;row['no_effect:'+op]+=1
            else:
                row['effective']+=1
            if op in ('HARVEST','COLLECT_FERTILIZER'):
                for item in E.PRODUCTS:
                    gain=after.get(item,0)-inv.get(item,0)
                    if gain>0:row['produced:'+item]+=gain
            return value
        def spawn(farm,board_size,weed_chance,rng):
            s=sim.seats[id(farm)];day=str(sim.t//24)
            empty={(x,y) for y in range(board_size) for x in range(board_size) if farm['tiles'][y][x] is None}
            old_spawn(farm,board_size,weed_chance,rng)
            new=sorted((x,y) for x,y in empty if farm['tiles'][y][x] is not None)
            if reference is not None and s==opp:
                # Preserve the recorded opponent's exogenous weeds while consuming
                # the ordinary RNG draws, leaving our farm on the official path.
                for x,y in new:farm['tiles'][y][x]=None
                new=[]
                for x,y in reference['spawns'][s].get(day,[]):
                    if farm['tiles'][y][x] is None:
                        farm['tiles'][y][x]={'kind':'WEED'};new.append((x,y))
            logged_spawns[s][day]=new
        E._apply_unit_action,E._spawn_weeds=work,spawn
        try:
            for t in range(719):
                sim.t=t;sim.seats={id(f):s for s,f in enumerate(state[0].observation.farms)}
                for s in state:s.observation.step=t
                if t%24==0:
                    state[0].observation.town['unlocked_shops'][:]=world['shops'][t//24]
                    daily.append(dict(day=t//24,cash=[f['money'] for f in state[0].observation.farms],
                        economics=[R.economic(sim.events,s) for s in range(2)]))
                    physical_daily.append([dict(p) for p in physical])
                    peak_rss=max(peak_rss,process.memory_info().rss)
                if arm=='recording' and t in obs_by_step:
                    eq=[clean_observation(state[s].observation)==clean_observation(obs_by_step[t][s]) for s in range(2)]
                    observation_checks.append(dict(step=t,equal=eq))
                    assert all(eq), ('recording observation mismatch',t,eq)
                for s in range(2):
                    keys[s].append(physical_key(state[0].observation.farms[s]))
                    private_keys[s].append(digest(state[s].observation.private))
                started=time.perf_counter();cpu_started=time.process_time()
                searched=arm=='candidate' and t in (288,360,432)
                if searched:
                    obs=deepcopy(state[seat].observation);mem=V.memory_of(ours)
                    before=digest(V.canonical([obs,mem]))
                    selected,decision=N.choose(obs,mem)
                    assert digest(V.canonical([obs,mem]))==before,'Planner mutated its inputs'
                    decisions.append(decision)
                    chassis.router=router
                    if selected is not None:
                        def committed(obs,step,memory,route=selected,until=decision['until']):
                            if step<until:
                                memory['route']=route;return route
                            return router(obs,step,memory)
                        chassis.router=committed
                if arm=='recording':
                    state[seat].action=deepcopy(recording['actions'][seat][t])
                else:
                    state[seat].action=ours(deepcopy(state[seat].observation))
                elapsed=time.perf_counter()-started+(setup_seconds if t==0 else 0)
                cpu=time.process_time()-cpu_started
                bank-=max(0.0,elapsed-1.0)
                timings.append(dict(step=t,seconds=elapsed,cpu_seconds=cpu,searched=searched,remaining_overage_seconds=bank))
                if searched:
                    write(OUT/'decisions'/f'{spec["id"]}-d{t//24}.json',decisions[-1])
                    peak_rss=max(peak_rss,process.memory_info().rss)
                    print('REVEAL '+json.dumps(dict(case=spec['id'],day=t//24,
                          selected=selected,seconds=elapsed,bank=bank)),flush=True)
                state[opp].action=(deepcopy(recording['actions'][opp][t]) if recording is not None else
                                   rival(deepcopy(state[opp].observation)))
                pair=[s.action for s in state]
                for s in range(2):
                    actions[s].append(deepcopy(pair[s]))
                    for order in (pair[s] or {}).get('market') or []:
                        if len(order)>1 and order[0]=='SELL':
                            requested[s][order[1]]+=int(order[2]) if len(order)>2 else 1
                if t<288:prefix.append(deepcopy(pair))
                in_engine=True
                try:E.interpreter(state,sim.env)
                finally:in_engine=False
            if arm=='recording':
                eq=[clean_observation(state[s].observation)==clean_observation(obs_by_step[719][s]) for s in range(2)]
                observation_checks.append(dict(step=719,equal=eq));assert all(eq),('final observation',eq)
            cash=[s.reward for s in state]
            economics=[R.economic(sim.events,s) for s in range(2)]
            for s in range(2):
                assert 3000+sum(economics[s]['revenue'].values())-sum(economics[s]['spend'].values())==cash[s]
            assert all(s.status=='DONE' for s in state)
            if arm=='recording':assert cash==recording['rewards'],(cash,recording['rewards'])
        finally:E._apply_unit_action,E._spawn_weeds=old_unit,old_spawn
    divergence=None
    def failed(row):return sum(row.get(k,0) for k in ('no_effect','missing_worker_commands','malformed_commands'))
    if reference is not None:
        divergence=dict(first_board_difference=next((t for t,(a,b) in enumerate(zip(keys[opp],reference['board_keys'][opp])) if a!=b),None),
            first_private_difference=next((t for t,(a,b) in enumerate(zip(private_keys[opp],reference['private_keys'][opp])) if a!=b),None),
            extra_failed_commands=failed(physical[opp])-failed(reference['physical'][opp]),
            recorded_cash=reference['cash_by_seat'][opp],counterfactual_cash=cash[opp],
            sold_units_delta={p:economics[opp]['units'].get(p,0)-reference['economics'][opp]['units'].get(p,0) for p in E.PRODUCTS})
        divergence['material_command_break']=divergence['extra_failed_commands']>40
    write(OUT/'actions'/f'{spec["id"]}-{arm}.json',actions)
    return dict(spec=spec,arm=arm,completed=True,ledger_verified=True,
        cash=cash[seat],rival_cash=cash[opp],margin=cash[seat]-cash[opp],cash_by_seat=cash,
        economics=economics,physical=[dict(p) for p in physical],physical_daily=physical_daily,
        sale_requested=[dict(p) for p in requested],daily=daily,
        selected=[d['selected'] for d in decisions],prefix_sha256=digest(prefix),actions_sha256=digest(actions),
        timings=timings,remaining_overage_seconds=bank,measured_bank_exhausted=bank<0,
        import_and_initialization_seconds=setup_seconds,peak_rss_gib=peak_rss/2**30,
        board_keys=keys,private_keys=private_keys,spawns=logged_spawns,
        replay_divergence=divergence,reproduced_exactly=arm=='recording',observation_checks=observation_checks,
        limitation='Local synchronous engine; elapsed timing bank measured but not enforced. Replay counterfactual freezes opponent actions and opponent weed spawns; its policy cannot react to changed prices.')

def worker(case,arm):
    spec=next(s for s in specs() if s['id']==case)
    start=time.perf_counter()
    try:result=run_game(spec,arm)
    except Exception:result=dict(spec=spec,arm=arm,completed=False,error=traceback.format_exc())
    result['seconds']=time.perf_counter()-start
    write(OUT/'arms'/f'{case}-{arm}.json',result)
    print('ARM '+json.dumps({k:result.get(k) for k in ('spec','arm','completed','cash','rival_cash',
        'selected','seconds','peak_rss_gib','remaining_overage_seconds','error')}),flush=True)
    return 0 if result['completed'] else 1

def pair(spec):
    arms={a:json.loads((OUT/'arms'/f'{spec["id"]}-{a}.json').read_text()) for a in ('baseline','candidate')}
    b,c=arms['baseline'],arms['candidate']
    assert b['completed'] and c['completed']
    assert b['prefix_sha256']==c['prefix_sha256'], 'Pre-intervention prefix changed'
    if not any(r is not None for r in c['selected']):
        assert b['actions_sha256']==c['actions_sha256'] and b['cash_by_seat']==c['cash_by_seat']
    row=dict(spec=spec,completed=True,baseline_margin=b['margin'],candidate_margin=c['margin'],
        baseline_cash=b['cash'],candidate_cash=c['cash'],baseline_rival_cash=b['rival_cash'],candidate_rival_cash=c['rival_cash'],
        margin_delta=c['margin']-b['margin'],cash_delta=c['cash']-b['cash'],rival_delta=c['rival_cash']-b['rival_cash'],
        selected=c['selected'],intervened=any(r is not None for r in c['selected']),
        actions_changed=b['actions_sha256']!=c['actions_sha256'],
        baseline_bank=b['remaining_overage_seconds'],candidate_bank=c['remaining_overage_seconds'],
        baseline_divergence=b['replay_divergence'],candidate_divergence=c['replay_divergence'])
    write(OUT/'pairs'/f'{spec["id"]}.json',row)
    print('PAIR '+json.dumps(row),flush=True)
    return row

def launch(spec,arm):
    target=OUT/'arms'/f'{spec["id"]}-{arm}.json'
    if target.exists():
        return json.loads(target.read_text()).get('completed',False)
    import psutil
    # One child at a time; preserve headroom for the user's other agent systems.
    required = (1.7 if arm=='recording' else
                3.0 if spec['opponent']=='original_m1' and arm=='candidate' else
                2.5 if arm=='candidate' or spec['opponent']=='original_m1' else 2.0)
    for attempt in range(7):
        free=psutil.virtual_memory().available/2**30
        if free>=required:break
        if attempt==0:
            print('RESOURCE_PAUSE '+json.dumps(dict(free_gib=free,required_gib=required,next=spec['id'],arm=arm)),flush=True)
        if attempt==6:return None
        time.sleep(10)
    logpath=OUT/'logs'/f'{spec["id"]}-{arm}.log';logpath.parent.mkdir(exist_ok=True)
    with logpath.open('w',encoding='utf-8') as log:
        p=subprocess.run([sys.executable,str(Path(__file__)),'--case',spec['id'],'--arm',arm],stdout=log,stderr=subprocess.STDOUT)
    if p.returncode or not target.exists():
        print('ARM_FAILED '+json.dumps(dict(case=spec['id'],arm=arm,returncode=p.returncode)),flush=True)
        return False
    return True

def main():
    p=argparse.ArgumentParser();p.add_argument('--case');p.add_argument('--arm',choices=['recording','baseline','candidate'])
    p.add_argument('--kind',choices=['live','replay','all'],default='all');p.add_argument('--limit',type=int)
    p.add_argument('--audit-only',action='store_true')
    args=p.parse_args()
    if args.case and args.arm:return worker(args.case,args.arm)
    verify()
    todo=[s for s in specs() if (args.kind=='all' or s['kind']==args.kind) and (not args.case or s['id']==args.case)]
    if args.limit is not None:todo=todo[:args.limit]
    for spec in todo:
        if (OUT/'pairs'/f'{spec["id"]}.json').exists():continue
        order=['recording'] if spec['kind']=='replay' else []
        if not args.audit_only:order+=['candidate','baseline']
        success=True
        for arm in order:
            ok=launch(spec,arm)
            if ok is None:return 2
            if not ok:success=False;break
        if success and not args.audit_only:
            try:pair(spec)
            except Exception:
                write(OUT/'pairs'/f'{spec["id"]}.json',dict(spec=spec,completed=False,error=traceback.format_exc()))
                print('PAIR_FAILED '+spec['id'],flush=True)
    return 0

if __name__=='__main__':sys.exit(main())
