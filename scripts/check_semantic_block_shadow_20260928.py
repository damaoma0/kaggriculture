"""Frozen block-policy shadow decisions on saved development observations.

This is an off-policy diagnostic: observed progress and retirement commitments
belong to the recorded policy. It is not a candidate gameplay counterfactual.
"""
from collections import Counter,defaultdict
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import time

import semantic_strategy_policy_20260928 as P
from semantic_strategy_blocks_20260928 import SemanticBlockPolicy

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/fresh/semantic_strategy_20260928'
FROZEN_PROJECT=BASE/'candidates/strategy_v5_blocks100_finance/project'
FILES=dict(policy=FROZEN_PROJECT/'scripts/semantic_strategy_blocks_20260928.py',
           base_policy=FROZEN_PROJECT/'scripts/semantic_strategy_policy_20260928.py',
           model=FROZEN_PROJECT/'results/fresh/semantic_strategy_20260928/block_model_modern100.json')
GROUPS=dict(v2_fixed_B=BASE/'fixed_experiments/nearest_shops_v2/runs/strategy_v2_unlock',
            v3_natural=BASE/'runs/strategy_v3_modern4/development/live')
FIELDS=('plant_counts','animal_add_counts','animal_retire_counts')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize(rows):
    out={}
    for name,subset in [('all',rows),('D6_11',[r for r in rows if r['day']<=11]),
                        ('D12_20',[r for r in rows if 12<=r['day']<=20]),
                        ('D21_29',[r for r in rows if r['day']>=21])]:
        totals={}
        for key in ('baseline','requested','shadow','unlimited_cash'):
            totals[key]={field:dict(sum((Counter(r[key].get(field,{})) for r in subset),Counter())) for field in FIELDS}
        out[name]=dict(days=len(subset),daily_request_totals_include_backlogs=totals,
            cash_clipped_days=sum(r['cash_clipped'] for r in subset),
            any_admission_clip_days=sum(r['admission_clipped'] for r in subset),
            admission_clipped_units=sum(r['admission_clipped_units'] for r in subset),
            cash_clipped_units=sum(r['cash_clipped_units'] for r in subset),
            land_add_days=sum(r['shadow']['land_add_count']>0 for r in subset),
            original_admitted_land_add_days=sum(r['baseline'].get('land_add_count',0)>0 for r in subset),
            held_animals=sum(sum(r['held_animals'].values()) for r in subset))
    return out


def main():
    spec=importlib.util.spec_from_file_location('frozen_shadow_block',FILES['policy'])
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    policy_class=module.SemanticBlockPolicy
    started=time.perf_counter();hashes={k:sha(p) for k,p in FILES.items()}
    frozen=json.loads((BASE/'block_prototype_manifest.json').read_text())['files']
    for p in FILES.values():assert sha(p)==frozen[str(p.relative_to(FROZEN_PROJECT)).replace('\\','/')]
    assert sha(Path(P.__file__))==hashes['base_policy']
    output=dict(purpose=__doc__,source_hashes=hashes,groups={})
    for name,folder in GROUPS.items():
        paths=sorted(p for p in folder.glob('live-*.json') if not p.name.endswith('.actions.json'))
        assert len(paths)==8,(name,len(paths))
        rows=[];block_rows=[];fresh_retirements=[];case_rows=[];input_hashes={}
        for path in paths:
            raw=json.loads(path.read_text());assert raw['completed'] and raw['ledger_verified']
            input_hashes[str(path.relative_to(ROOT))]=sha(path);seat=int(raw['case']['seat'])
            snapshots={r['day']:r for r in raw['diagnostics'][seat]}
            rival={r['day']:r for r in raw['diagnostics'][1-seat]}
            policy=policy_class(FILES['model'],{'forecast':False,'land_limit':4})
            forecast_policy=policy_class(FILES['model'],{'forecast':True,'land_limit':4})
            memory={};intents={};last_block=None;before_rows=len(rows)
            for day in range(6,30):
                saved=snapshots[day]['current_observation'];assert 'private' in saved
                farms=[None,None];farms[seat]=deepcopy(saved['own_farm'])
                farms[1-seat]=deepcopy(rival[day]['current_observation']['own_farm'])
                obs=dict(day=day,hour=0,step=24*day,player=seat,farms=farms,
                    private=deepcopy(saved['private']),market=deepcopy(saved['market']),town=deepcopy(saved['town']))
                cells={y*10+x:t for y,row in enumerate(farms[seat]['tiles']) for x,t in enumerate(row) if isinstance(t,dict)}
                intents={tile:c for tile,c in intents.items() if tile in cells
                    and (cells[tile].get('animal'),cells[tile].get('placed_day'))==(c['species'],c['birth'])}
                memory['committed_retirement_counts']=dict(Counter(c['species'] for c in intents.values()))
                before=deepcopy(memory)
                result=policy.propose(obs,before);memory=result['memory']
                rich=deepcopy(obs);rich['farms'][seat]['money']=1e9
                unlimited=policy.propose(rich,before)['today']
                plan=snapshots[day]['diagnostics'][-1]
                baseline=plan['proposal'];requested=result['diagnostics']['requested'];chosen=result['today']
                admission_clip=sum(max(0,n-chosen[field].get(sp,0)) for field in ('plant_counts','animal_add_counts')
                    for sp,n in requested[field].items())
                cash_clip=sum(max(0,n-chosen[field].get(sp,0)) for field in ('plant_counts','animal_add_counts')
                    for sp,n in unlimited[field].items())
                held=Counter(saved['private'].get('shed',{}))
                for inv in saved['private'].get('inventories',[]):held.update(inv)
                rows.append(dict(case=raw['case']['id'],day=day,cash=farms[seat]['money'],
                    shops=P._shops(obs),
                    owned_land=len(farms[seat]['unlocked_quadrants']),
                    held_animals={s:held[s] for s in P.ANIMALS if held[s]},
                    committed_retirements=memory['committed_retirement_counts'],
                    baseline={k:baseline.get(k,{}) for k in (*FIELDS,'land_add_count')},
                    baseline_neighbor=plan['policy'].get('row_index'),
                    shadow={k:chosen[k] for k in (*FIELDS,'land_add_count','estimated_capital_cost','hands')},
                    requested={k:requested[k] for k in FIELDS},unlimited_cash={k:unlimited[k] for k in FIELDS},
                    cohort_values=result['diagnostics']['cohort_values'],
                    admission_clipped=admission_clip>0,admission_clipped_units=admission_clip,
                    cash_clipped=cash_clip>0,cash_clipped_units=cash_clip,
                    completed=result['diagnostics']['completed'],block_totals=result['diagnostics']['totals']))
                if day%3==0:
                    forecast=forecast_policy.propose(obs,before)
                    admitted={field:dict(sum((Counter(r[field]) for r in forecast['forecast'][:3]),Counter())) for field in FIELDS}
                    rich_forecast=forecast_policy.propose(rich,before)
                    rich_admitted={field:dict(sum((Counter(r[field]) for r in rich_forecast['forecast'][:3]),Counter())) for field in FIELDS}
                    block_rows.append(dict(case=raw['case']['id'],start=day,budget=result['diagnostics']['totals'],
                        model_success_admission=admitted,unlimited_cash_model_admission=rich_admitted,
                        physical_state_and_cash='observed block-start; future delivery/care/cash modeled'))
                for intent in plan.get('retirements',[]):
                    tile=int(intent['tile']);cell=cells.get(tile)
                    if cell and cell.get('animal')==intent['animal']:
                        sp=cell['animal'];birth=int(cell['placed_day'])
                        intents[tile]=dict(species=sp,birth=birth)
                        if day-birth<=6:
                            fresh_retirements.append(dict(case=raw['case']['id'],day=day,species=sp,birth=birth,
                                age=day-birth,before_first_production=day+1-birth<P.ANIMALS[sp]['first'],
                                baseline_retirement_count=baseline['animal_retire_counts'].get(sp,0),
                                shadow_retirement_count=chosen['animal_retire_counts'].get(sp,0),
                                interpretation='Same-species quantity only; alternate retirement identity is unknown'))
            case=rows[before_rows:]
            neighbor_changes=sum(a['baseline_neighbor']!=b['baseline_neighbor'] for a,b in zip(case,case[1:]) if a['day']//3==b['day']//3)
            budget_changes=sum(a['block_totals']!=b['block_totals'] for a,b in zip(case,case[1:]) if a['day']//3==b['day']//3)
            case_rows.append(dict(case=raw['case']['id'],baseline_neighbor_changes_within_blocks=neighbor_changes,
                                  shadow_budget_changes_within_blocks=budget_changes))
        totals={}
        for field,species in [('plant_counts',P.CROPS),('animal_add_counts',P.ANIMALS),('animal_retire_counts',P.ANIMALS)]:
            totals[field]={sp:dict(budget=sum(b['budget'].get('RETIRE_'+sp if field=='animal_retire_counts' else sp,0) for b in block_rows),
                model_success_admitted=sum(b['model_success_admission'][field].get(sp,0) for b in block_rows),
                unlimited_cash_admitted=sum(b['unlimited_cash_model_admission'][field].get(sp,0) for b in block_rows)) for sp in species}
        output['groups'][name]=dict(input_hashes=input_hashes,cases=len(paths),summary=summarize(rows),
            within_block_reference_changes=case_rows,distinct_block_budgets_vs_modeled_admission=totals,
            recent_actual_retirements=fresh_retirements,blocks=block_rows,rows=rows)
    assert hashes=={k:sha(p) for k,p in FILES.items()}
    output.update(elapsed_seconds=time.perf_counter()-started,limitations=[
        'Shadow proposals are evaluated against another policy actual progress; not a closed-loop game or profit prediction.',
        'Both public farm snapshots, actual current prices, own seeds/shed/inventories are supplied; no future raw observations enter a decision.',
        'Hourly public inferred rival-flow history is absent in these daily snapshots and is left empty.',
        'The shadow has land limit4 in both groups; v2 fixed B was land limit3 and an older daily training library.',
        'Daily outstanding-request sums count carried jobs repeatedly. Separate block budget totals are unique per block.',
        'Modeled three-day admission assumes its prior actions succeed; this isolates model admission, not execution feasibility.',
        'Actual recorded retirement commitments are preserved; a shadow cannot undo animals already retired by the recorded policy.'])
    dst=BASE/'block_shadow_development_diagnostic.json';dst.write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps(dict(path=str(dst),elapsed=output['elapsed_seconds'],groups=list(output['groups'])),indent=2))


if __name__=='__main__':main()
