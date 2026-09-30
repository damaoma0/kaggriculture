"""Saved-dawn decision sensitivity; exact admission, explicit history limitation.

No engine, games, qualification rows, requested rival trades, or policy edits.
The frozen recordings omit hourly public_history. Recorded cohort values permit
exact admission replay; forecast counterfactuals use an explicitly empty history.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
STUDY=ROOT/'results/fresh/semantic_strategy_20260928'
FIELDS=('plant_counts','animal_add_counts','animal_retire_counts','hands','land_add_count',
        'target_land_count','target_animals','target_crop_counts','build_counts','remove_structure_counts')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m
def decisions(proposal):return {k:proposal.get(k) for k in FIELDS}
def change(a,b):return {k:dict(before=a.get(k),after=b.get(k)) for k in FIELDS if a.get(k)!=b.get(k)}
def rowdiag(row):return next(x for x in row['diagnostics'] if x['day']==row['day'])

def main():
    base=STUDY/'candidates/strategy_v7_blocks100_readiness/project'
    scripts=base/'scripts';sys.path.insert(0,str(scripts))
    P=load(scripts/'semantic_strategy_policy_20260928.py','semantic_strategy_policy_20260928')
    B=load(scripts/'semantic_strategy_blocks_20260928.py','frozen_sensitivity_blocks')
    config=json.loads((base/'results/fresh/semantic_strategy_20260928/candidate_config.json').read_text())
    policy=B.SemanticBlockPolicy(base/'results/fresh/semantic_strategy_20260928'/config['model_file'],config['policy'])
    policy.config['forecast']=False  # Only removes synthetic suffix work; today's _choice is unchanged.
    products=list(P.CROPS)+list(P.ANIMALS)
    scenario_names=['rival_empty','rival_twice','rival_20_sheep','rival_20_strawberries',
                    'rival_current_yield_zero','rival_current_yield_full',
                    'inventory_glut','inventory_scarcity','rival_history_zero','rival_history_high',
                    'coherent_market_glut','coherent_market_scarcity']
    summary={name:Counter() for name in scenario_names}
    quote_summary={name:Counter() for name in ('quote_half','quote_double','quote_floor')}
    rank_summary=Counter();rows=[];sources=[];total=Counter();exact_fail=[];request_fail=[]
    for arm in ('strategy_v5_blocks100_finance','strategy_v7_blocks100_readiness'):
        for source in sorted((STUDY/'runs'/arm/'development/live').glob('live-*.json')):
            if '.actions.' in source.name:continue
            game=json.loads(source.read_text());seat=game['case']['seat'];memory={};intent={}
            sources.append(dict(path=source.relative_to(ROOT).as_posix(),sha256=sha(source)))
            for day in range(6,30):
                saved=game['diagnostics'][seat][day];record=rowdiag(saved)
                visible=saved['current_observation'];rival=game['diagnostics'][1-seat][day]['current_observation']['own_farm']
                farms=[None,None];farms[seat]=deepcopy(visible['own_farm']);farms[1-seat]=deepcopy(rival)
                obs=dict(step=day*24,day=day,hour=0,player=seat,farms=farms,market=deepcopy(visible['market']),
                         town=deepcopy(visible['town']),private=deepcopy(visible['private']))
                own=farms[seat]
                active_intents={tile:r for tile,r in intent.items() if isinstance(own['tiles'][tile//10][tile%10],dict)
                    and own['tiles'][tile//10][tile%10].get('animal')==r['animal']
                    and own['tiles'][tile//10][tile%10].get('placed_day')==r['placed_day']}
                intent=active_intents
                committed=dict(Counter(r['animal'] for r in intent.values()))
                memory['committed_retirement_counts']=committed
                state=P.public_state(obs);state['committed_retirement_counts']=committed
                # Match propose's anonymous retirement forecast on current live animals.
                for sp,n in committed.items():
                    for c in sorted(state['own_animal_cohorts'],key=P._birth):
                        if c['species']!=sp or 'retire_day' in c or n<=0:continue
                        take=min(n,c['count']);n-=take
                        if take<c['count']:state['own_animal_cohorts'].append(dict(c,count=c['count']-take));c['count']=take
                        c['retire_day']=day
                request=deepcopy(record['policy']['requested']);values=record['policy']['cohort_values']
                fixed_row=dict(day=day,features={},target=request)
                exact=policy._proposal(state,fixed_row,values)
                original=record['proposal'];exact_ok=exact==original
                total['dawns']+=1;total['exact_recorded_value_admission_matches']+=exact_ok
                if not exact_ok:exact_fail.append(dict(arm=arm,case=game['case']['id'],day=day,delta=change(original,exact),
                                                       reconstructed=exact,recorded=original,committed=committed))
                # Reconstruct block/seen-birth memory using only past own dawns.
                reconstructed=policy.propose(obs,memory);memory=reconstructed['memory']
                request_ok=reconstructed['diagnostics']['requested']==request
                total['block_requested_targets_match']+=request_ok
                if not request_ok:request_fail.append(dict(arm=arm,case=game['case']['id'],day=day,
                    recorded=request,reconstructed=reconstructed['diagnostics']['requested']))
                nohist=reconstructed['today'];total['empty_history_today_matches_recorded']+=nohist==original
                local=dict(arm=arm,case=game['case']['id'],day=day,exact_admission_match=exact_ok,
                    block_request_match=request_ok,empty_history_today_match=nohist==original,
                    recorded_proposal=decisions(original),committed_retirement_counts=committed,
                    raw_requested_counts={k:request[k] for k in ('plant_counts','animal_add_counts','animal_retire_counts','hands')},
                    synthetic_changes={},quote_changes={},adversarial_rank_changes={})
                nonpositive=[]
                for field in ('plant_counts','animal_add_counts'):
                    for species,n in original[field].items():
                        if values[species]>0:continue
                        held=state['stock' if field=='animal_add_counts' else 'seeds'].get(species,0)
                        nonpositive.append(dict(species=species,count=n,held=held,unbought=max(0,n-held),value=values[species]))
                        total['nonpositive_admitted:'+species]+=n
                        total['unbought_nonpositive_admitted:'+species]+=max(0,n-held)
                local['recorded_nonpositive_admissions']=nonpositive
                total['dawns_with_nonpositive_admitted']+=bool(nonpositive)
                # Values affect only greedy priority. Probe each species as the
                # first priority and the reverse current priority without guessing history.
                rank_vectors={sp:{s:(1e9 if s==sp else -1e9+i) for i,s in enumerate(products)} for sp in products}
                rank_vectors['reverse_baseline']={s:-float(values[s]) for s in products}
                for name,v in rank_vectors.items():
                    altered=policy._proposal(state,fixed_row,v)
                    rank_summary['evaluations']+=1
                    if decisions(altered)!=decisions(exact):
                        rank_summary['changed']+=1;local['adversarial_rank_changes'][name]=change(exact,altered)
                total['any_adversarial_rank_change']+=bool(local['adversarial_rank_changes'])
                # Current quote changes are exact admission effects at recorded
                # cohort values. Inventory and forecasts intentionally stay fixed.
                for name,factor in (('quote_half',.5),('quote_double',2.),('quote_floor',0.)):
                    alt=deepcopy(state);alt['prices']={p:max(1.,v*factor) for p,v in state['prices'].items()}
                    altered=policy._proposal(alt,fixed_row,values)
                    quote_summary[name]['evaluations']+=1
                    if decisions(altered)!=decisions(exact):
                        quote_summary[name]['changed']+=1;local['quote_changes'][name]=change(exact,altered)
                        for key in local['quote_changes'][name]:quote_summary[name]['field:'+key]+=1
                # Counterfactual forecast sensitivity, with empty-history control.
                base_paths,base_rival=P.forecast_market(state,policy.config,{})
                base_values={s:P.cohort_value(state,s,base_paths,base_rival,policy.config) for s in products}
                nohist_admission=policy._proposal(state,fixed_row,base_values)
                for name in scenario_names:
                    alt=deepcopy(state);history={}
                    if name=='rival_empty':alt['rival_crop_cohorts']=[];alt['rival_animal_cohorts']=[]
                    elif name=='rival_twice':
                        for c in alt['rival_crop_cohorts']+alt['rival_animal_cohorts']:c['count']*=2
                    elif name=='rival_20_sheep':
                        alt['rival_animal_cohorts'].append(dict(species='SHEEP',birth=max(0,day-6),count=20))
                    elif name=='rival_20_strawberries':
                        alt['rival_crop_cohorts'].append(dict(crop='STRAWBERRY',birth=max(0,day-10),count=20))
                    elif name.startswith('rival_current_yield'):
                        for c in alt['rival_animal_details']:
                            c['yield_units']=0 if name.endswith('zero') else P.ANIMALS[c['animal']]['held']
                            c['pending_care_bonus']=0 if name.endswith('zero') else 6
                    elif 'market_' in name or name.startswith('inventory_'):
                        glut=name.endswith('glut')
                        alt['inventory']={p:10000+(2 if glut else -2)*P._MARKET[p][1] for p in P.PRODUCTS}
                        if name.startswith('coherent_'):
                            alt['prices']={p:P.market_price(p,alt['inventory'][p],alt['market_params']) for p in P.PRODUCTS}
                    elif name.startswith('rival_history_'):
                        history={'rival_net_daily':{p:0 if name.endswith('zero') else 50 for p in P.PRODUCTS}}
                    paths,supply=P.forecast_market(alt,policy.config,history)
                    v={s:P.cohort_value(alt,s,paths,supply,policy.config) for s in products}
                    altered=policy._proposal(alt,fixed_row,v)
                    counts=summary[name];counts['evaluations']+=1
                    counts['values_changed']+=any(abs(v[s]-base_values[s])>1e-9 for s in products)
                    if decisions(altered)!=decisions(nohist_admission):
                        counts['today_changed']+=1
                        delta=change(nohist_admission,altered)
                        for key in delta:counts['field:'+key]+=1
                        local['synthetic_changes'][name]=delta
                # Strongly identify decisions that admission accepts in full.
                eligible_plants={s:int(n) for s,n in request['plant_counts'].items() if day+P.CROPS[s]['first']<=29 and n}
                eligible_animals={s:int(n) for s,n in request['animal_add_counts'].items() if day+P.ANIMALS[s]['first']<=28 and n}
                fully=original['plant_counts']==eligible_plants and original['animal_add_counts']==eligible_animals
                local['all_age_eligible_requested_additions_admitted']=fully;total['fully_admitted_dawns']+=fully
                assert not fully or not local['adversarial_rank_changes']
                rows.append(local)
                for retirement in record.get('retirements',[]):
                    tile=int(retirement['tile']);cell=own['tiles'][tile//10][tile%10]
                    intent[tile]=dict(animal=retirement['animal'],placed_day=(cell.get('placed_day',day)
                        if isinstance(cell,dict) and cell.get('animal')==retirement['animal'] else day))
            print(json.dumps(dict(case=game['case']['id'],arm=arm,processed=total['dawns'])),flush=True)
    payload=dict(scope='DEVELOPMENT_SAVED_DAWNS_SYNTHETIC_SENSITIVITY_NO_GAMES',
        limitations=['Hourly public_history was not logged. No claim of full propose/memory parity.',
            'Exact replay uses recorded rounded cohort values, current actual own state and recorded requested targets.',
            'Forecast counterfactuals compare against empty-history controls, never claim exact original-history sensitivity.',
            'Artificial inventory, prices, and rival cohorts are mechanism probes, not feasible games or profit estimates.',
            'Opening/block generation uses shops and own cohorts only; counterfactuals leave their requested budget fixed.'],
        source_files=sources,frozen_policy_sha256=sha(scripts/'semantic_strategy_policy_20260928.py'),
        frozen_blocks_sha256=sha(scripts/'semantic_strategy_blocks_20260928.py'),
        model_sha256=sha(base/'results/fresh/semantic_strategy_20260928'/config['model_file']),
        script_sha256=sha(Path(__file__)),totals=dict(total),exact_failures=exact_fail,block_request_failures=request_fail,
        forecast_scenarios={k:dict(v) for k,v in summary.items()},exact_quote_admission_scenarios={k:dict(v) for k,v in quote_summary.items()},
        adversarial_value_rank_tests=dict(rank_summary),rows=rows)
    by_arm={}
    for arm in sorted({r['arm'] for r in rows}):
        selected=[r for r in rows if r['arm']==arm]
        by_arm[arm]=dict(dawns=len(selected),fully_admitted=sum(r['all_age_eligible_requested_additions_admitted'] for r in selected),
            adversarial_rank_sensitive=sum(bool(r['adversarial_rank_changes']) for r in selected),
            empty_history_today_differences=sum(not r['empty_history_today_match'] for r in selected),
            forecast_scenario_today_changes={name:sum(name in r['synthetic_changes'] for r in selected) for name in scenario_names})
    payload['by_arm']=by_arm
    out=STUDY/'policy_sensitivity_v5_v7_saved_dawns.json'
    out.write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:payload[k] for k in ('totals','forecast_scenarios','exact_quote_admission_scenarios','adversarial_value_rank_tests')},indent=2))
    print(out)

if __name__=='__main__':main()
