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

OUT = Path('C:\\Users\\xyygl\\Documents\\kaggriculture\\results\\fresh\\tape_opportunity_20260924_01a0')
PAYLOAD = Path('C:\\Users\\xyygl\\Documents\\kaggriculture\\results\\fresh\\tape_repair_20260924_01a0\\r3holdout24\\payload')
REFERENCE = Path('C:\\Users\\xyygl\\Documents\\kaggriculture\\results\\fresh\\value_tape_wide_20260923_01a0')

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=True), encoding='utf-8')
    tmp.replace(path)

def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',',':')).encode()).hexdigest()

def verify():
    manifest = json.loads((Path('C:\\Users\\xyygl\\Documents\\kaggriculture\\results\\fresh\\tape_repair_20260924_01a0\\r3holdout24') / 'source_manifest.json').read_text())
    for name, expected in manifest['sha256'].items():
        assert sha256((PAYLOAD/name).read_bytes()).hexdigest() == expected, name

def specs():
    return json.loads((OUT/'design.json').read_text())['specs']


def physical_key(farm):
    return digest([farm[k] for k in ('tiles','farmer','hands','unlocked_quadrants','hires_today')])

def clean_observation(obs):
    return {k:v for k,v in obs.items() if k not in ('remainingOverageTime','step')}

def run_game(spec, arm):
    verify()
    sys.path[:0] = [str(PAYLOAD/'scripts'),str(PAYLOAD/'vendor')]
    imported = time.perf_counter()
    N = importlib.import_module('value_tape_repair_r3' if arm=='candidate' else 'value_tape_search_v9')
    import_seconds = time.perf_counter()-imported
    V,R = N.V,N.V.R
    E = R.engine()
    import psutil
    process=psutil.Process()
    peak_rss=process.memory_info().rss
    assert set(importlib.import_module('rival_trajectory_model_v3').M.DEMAND)==set(E.SHOPS)
    recording = None
    if spec['kind']=='replay':
        with gzip.open(REFERENCE/'recordings'/f'{spec["episode"]}.json.gz','rt',encoding='utf-8') as f:
            recording=json.load(f)
        world=dict(seed=recording['seed'],seat=spec['seat'],episode=spec['episode'],shops=recording['shops'])
    else:
        assert all(shop in E.SHOPS for shop in spec['shops'])
        world=dict(seed=spec['seed'],seat=spec['seat'],episode=0,
            shops=[spec['shops'][:min(8,d//3)] for d in range(31)])
    seat=spec['seat']; opp=1-seat
    initialization = time.perf_counter()
    ours = None if arm=='recording' else V.fresh_agent()
    if arm=='candidate': N.install(ours)
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
        reference=json.loads((REFERENCE/'arms'/f'{spec["id"]}-recording.json').read_text())
        assert reference['completed'] and reference['reproduced_exactly']
    chassis=None if ours is None else ours.__globals__['_MGT_IMPL'].chassis
    router=None if chassis is None else chassis.router
    decisions=[]; actions=[[],[]]; prefix=[]; daily=[]; timings=[]; repair_execution=[]
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
                    daily[-1]['assets']=[sorted(V.asset_keys(f)) for f in state[0].observation.farms]
                    daily[-1]['inventories']=[deepcopy(s.observation.private) for s in state]
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
                searched=(t==spec['checkpoint'] or (spec.get('continuation')=='r3' and t>spec['checkpoint'] and t in (288,360,432)))
                if t==spec['checkpoint'] and spec.get('collect'):
                    collect_candidates(N, ours, deepcopy(state[seat].observation), spec)
                    raise CheckpointComplete()
                if arm=='candidate':
                    repair=N.install(ours)
                    if repair.targets and t==repair.until:
                        repair_execution.append(dict(until=t,assets=list(repair.targets.values()),stats=dict(repair.stats)))
                if searched:
                    obs=deepcopy(state[seat].observation);mem=V.memory_of(ours)
                    before=digest(V.canonical([obs,mem]))
                    if t==spec['checkpoint']:
                        selected=spec['forced']
                        decision=dict(selected=selected,until=t+72,day=t//24,forced_diagnostic=True)
                    else:
                        selected,decision=N.choose(obs,mem,budget_seconds=None)
                    assert digest(V.canonical([obs,mem]))==before,'Planner mutated its inputs'
                    decisions.append(decision)
                    chassis.router=router
                    if arm=='candidate':
                        N.commit(ours,selected,decision['until'],router)
                    elif selected is not None:
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
                    write(OUT/'decisions'/f'{spec["id"]}-{arm}-d{t//24}.json',decisions[-1])
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
                if t<spec['checkpoint']:prefix.append(deepcopy(pair))
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
        repair_execution=repair_execution,native_telemetry=V.canonical(ours.__globals__['_SHP_REPORT']) if ours else {},
        sale_requested=[dict(p) for p in requested],daily=daily,
        selected=[d['selected'] for d in decisions],prefix_sha256=digest(prefix),actions_sha256=digest(actions),
        timings=timings,remaining_overage_seconds=bank,measured_bank_exhausted=bank<0,
        import_and_initialization_seconds=setup_seconds,peak_rss_gib=peak_rss/2**30,
        board_keys=keys,private_keys=private_keys,spawns=logged_spawns,
        replay_divergence=divergence,reproduced_exactly=arm=='recording',observation_checks=observation_checks,
        limitation='Local synchronous engine; elapsed timing bank measured but not enforced. Replay counterfactual freezes opponent actions and opponent weed spawns; its policy cannot react to changed prices.')
