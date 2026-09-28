"""Static OFF-equivalence/ON-admission replay of saved V8 public observations."""
from collections import Counter
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
MAIN=Path(r'C:\Users\xyygl\Documents\kaggriculture')
STUDY=MAIN/'results/fresh/semantic_strategy_20260928'
FROZEN=STUDY/'candidates/strategy_v8_kb115lt2_readiness/project'
OUT=ROOT/'results/fresh/semantic_kb115lt2_recovery/diagnostics/fertilizer_net'
SEMANTIC=('plant_counts','animal_add_counts','animal_retire_counts','hands','land_add_count',
          'target_land_count','build_counts','remove_structure_counts')


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


def observations(g,s,d):
    o=deepcopy(g['diagnostics'][s][d]['current_observation'])
    o.update(day=d,hour=0,farms=[g['diagnostics'][t][d]['current_observation']['own_farm'] for t in range(2)])
    return o


def flat(o):return [t if isinstance(t,dict) else {} for row in o['own_farm']['tiles'] for t in row]


def feature_memory(g,s,d,memory,intents,P):
    m=deepcopy(memory);m['public_history']={}
    for t in range(max(0,d-3),d):
        a,b=g['daily'][1-s][t:t+2]
        m['public_history'][str(t)]={'rival_harvest':{p:b['physical'].get('produced:'+p,0)-a['physical'].get('produced:'+p,0) for p in P.PRODUCTS}}
    current=flat(g['diagnostics'][s][d]['current_observation']);valid={}
    for key,rec in intents.items():
        t=current[int(key)]
        if t.get('animal')==rec['animal'] and t.get('placed_day')==rec['placed_day']:valid[key]=rec
    m['committed_retirement_counts']=dict(Counter(r['animal'] for r in valid.values()))
    return m,valid


def semantic(row):return {k:row.get(k) for k in SEMANTIC}


def calibrate(g,s,P,cfg):
    state=P.public_state(observations(g,s,12),fertilizer_details=True)
    memory,_=feature_memory(g,s,12,{}, {},P)
    hist={'rival_net_daily':{p:sum(r['rival_harvest'][p] for r in memory['public_history'].values())/3 for p in P.PRODUCTS},'rival_flow_kind':'harvest'}
    off,_=P.forecast_market(state,dict(cfg,forecast_fertilizer_net=False),hist)
    on,_=P.forecast_market(state,dict(cfg,forecast_fertilizer_net=True),hist)
    rows=[]
    for d in range(12,29):
        actual=g['diagnostics'][s][d+1]['current_observation']['market']['prices']['FERTILIZER']
        rows.append(dict(day=d,actual_next_dawn=actual,
            off=P.market_price('FERTILIZER',off[d]['FERTILIZER'],state['market_params']),
            on=P.market_price('FERTILIZER',on[d]['FERTILIZER'],state['market_params'])))
    return dict(rows=rows,off_mae=sum(abs(r['off']-r['actual_next_dawn']) for r in rows)/len(rows),
                on_mae=sum(abs(r['on']-r['actual_next_dawn']) for r in rows)/len(rows))


def main():
    sys.path.insert(0,str(ROOT/'scripts'))
    oldP=load('semantic_strategy_policy_20260928',FROZEN/'scripts/semantic_strategy_policy_20260928.py')
    oldB=load('frozen_block_fertilizer_audit',FROZEN/'scripts/semantic_strategy_blocks_20260928.py')
    P=load('semantic_strategy_policy_20260928',ROOT/'scripts/semantic_strategy_policy_20260928.py')
    B=load('candidate_block_fertilizer_audit',ROOT/'scripts/semantic_strategy_blocks_20260928.py')
    from semantic_strategy_tiles_20260928 import build_plan
    cfg=json.loads((FROZEN/'results/fresh/semantic_strategy_20260928/candidate_config.json').read_text())['policy']
    model=FROZEN/'results/fresh/semantic_strategy_20260928/block_model_modern100.json'
    policies=[oldB.SemanticBlockPolicy(model,cfg),B.SemanticBlockPolicy(model,cfg),
              B.SemanticBlockPolicy(model,dict(cfg,forecast_fertilizer_net=True))]
    allrows=[];tiling=[];cases=[];times=[[],[],[]];started=time.perf_counter();hashes={}
    for path in sorted((STUDY/'runs/strategy_v8_kb115lt2_readiness/development/live').glob('live-??.json')):
        raw=path.read_bytes();hashes[str(path)]=hashlib.sha256(raw).hexdigest();g=json.loads(raw);s=g['case']['seat']
        memories=[{}, {}, {}];intents={};rows=[];selected=0
        for d in range(6,30):
            o=observations(g,s,d)
            assert oldP.public_state(o)==P.public_state(o)
            results=[];valid={}
            for k,policy in enumerate(policies):
                m,valid=feature_memory(g,s,d,memories[k],intents,P)
                ts=time.perf_counter();result=policy.propose(o,m);times[k].append(time.perf_counter()-ts)
                results.append(result);memories[k]=result['memory']
            assert results[0]==results[1],(g['case']['id'],d,'OFF full proposal differs from frozen V8')
            a,b=results[1:];today=semantic(a['today'])!=semantic(b['today'])
            future=[{'day':x['day'],'off':semantic(x),'on':semantic(y)}
                    for x,y in zip(a['forecast'],b['forecast']) if semantic(x)!=semantic(y)]
            row=dict(case=g['case']['id'],day=d,today_changed=today,
                today_off=semantic(a['today']),today_on=semantic(b['today']),forecast_changes=future,
                reconstructed_off_today_matches_recorded=semantic(a['today'])==semantic(g['final_diagnostics'][str(s)][d]['proposal']))
            if future and selected<2:
                pair=[]
                for prop in (a,b):
                    plan,_,diag=build_plan(o,prop,{'retirements':deepcopy(valid)},dict(release_age=cfg['release_age']))
                    pair.append((plan,diag))
                today_tiles=pair[0][1]['today']['tiles']!=pair[1][1]['today']['tiles']
                full_plan=any(pair[0][0][k]!=pair[1][0][k] for k in ('plant','animals_by_day','board','hands','land_day'))
                tiling.append(dict(case=g['case']['id'],day=d,today_semantics_changed=today,
                    today_tiles_changed=today_tiles,full_plan_changed=full_plan,
                    note='Paired empty historical prefix plus actual current retirement intentions; not a replay of the saved full internal tile memory.'))
                selected+=1
            rows.append(row);allrows.append(row)
            for rec in g['final_diagnostics'][str(s)][d]['retirements']:
                t=flat(g['diagnostics'][s][d]['current_observation'])[int(rec['tile'])]
                intents[str(rec['tile'])]=dict(animal=rec['animal'],placed_day=t['placed_day'],first_unfed_day=rec['first_unfed_day'])
        cal=calibrate(g,s,P,policies[2].config)
        cases.append(dict(case=g['case']['id'],today_changed=sum(r['today_changed'] for r in rows),
            forecast_only_changed=sum(bool(r['forecast_changes']) and not r['today_changed'] for r in rows),calibration=cal))
        print(g['case']['id'],'today',cases[-1]['today_changed'],'forecast_only',cases[-1]['forecast_only_changed'],flush=True)
    result=dict(new_games=0,off_full_proposals_equal=192,off_public_states_equal=192,
        recorded_today_reproduced=sum(r['reconstructed_off_today_matches_recorded'] for r in allrows),
        today_changed=sum(r['today_changed'] for r in allrows),
        forecast_only_changed=sum(bool(r['forecast_changes']) and not r['today_changed'] for r in allrows),
        cases=cases,rows=allrows,selected_tile_checks=tiling,input_hashes=hashes,
        timing={label:dict(total=sum(v),max=max(v),mean=sum(v)/len(v)) for label,v in zip(['frozen','off','on'],times)},
        elapsed_seconds=time.perf_counter()-started,
        limitations=['Saved hourly public observer memory is absent. Prior3-day public harvest totals approximate it; retirement identities are reconstructed from previously recorded own intentions and checked against current public cohorts.',
            'ON and OFF see identical actual observations, not their own counterfactual farms. These are static policy changes, not game outcomes.',
            'All future forecast count/hire/land differences are compared, since they can affect current spatial compilation.',
            'Output timing/care/rotations and missing future input cohorts remain assumptions. Quote error is development calibration, not performance.'])
    OUT.mkdir(parents=True,exist_ok=True);dest=OUT/'static_audit.json';dest.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('off_full_proposals_equal','recorded_today_reproduced','today_changed','forecast_only_changed','timing','elapsed_seconds')}),flush=True)


if __name__=='__main__':main()
