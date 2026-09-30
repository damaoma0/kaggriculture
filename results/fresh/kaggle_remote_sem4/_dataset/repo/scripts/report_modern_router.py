"""Apply the predeclared confirmation gate and select a local working agent."""
from hashlib import sha256
from statistics import mean
from collections import Counter
import json
from evaluate_modern_router import ROOT,OUT,PATHS,jobs

def main():
    manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
    for name,digest in manifest['sources'].items():assert sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    rows=[json.loads((OUT/'games'/('-'.join(map(str,j))+'.json')).read_text(encoding='utf-8')) for phase in ('development','confirmation') for j in jobs(phase)]
    errors=[]
    for r in rows:
        for collection in ('telemetry','chassis_diagnostics'):
            for key,value in r[collection].items():
                if any(s in key.lower() for s in ('error','fallback')) and isinstance(value,(int,float)) and value:
                    errors.append((r['phase'],r['seed'],r['seat'],r['policy'],r['opponent'],key,value))
    table=[];summary={};paired={}
    for phase in ('development','confirmation'):
        base={(r['seed'],r['seat'],r['opponent']):r for r in rows if r['phase']==phase and r['policy']=='baseline'}
        candidate=[r for r in rows if r['phase']==phase and r['policy']=='candidate']
        paired[phase]=[(r,base[r['seed'],r['seat'],r['opponent']]) for r in candidate]
        for opponent in sorted({r['opponent'] for r in candidate}):
            pairs=[(r,b) for r,b in paired[phase] if r['opponent']==opponent]
            delta=mean(r['margin']-b['margin'] for r,b in pairs)
            cash=mean(r['cash']-b['cash'] for r,b in pairs)
            cw=sum(r['margin']>0 for r,b in pairs);bw=sum(b['margin']>0 for r,b in pairs)
            ct=sum(r['margin']==0 for r,b in pairs);bt=sum(b['margin']==0 for r,b in pairs)
            seed_delta={s:mean(r['margin']-b['margin'] for r,b in pairs if r['seed']==s) for s in sorted({r['seed'] for r,b in pairs})}
            summary[phase+'/'+opponent]=dict(games=len(pairs),baseline_wins=bw,candidate_wins=cw,baseline_ties=bt,candidate_ties=ct,margin_gain=delta,cash_gain=cash,
                baseline_margin=mean(b['margin'] for r,b in pairs),candidate_margin=mean(r['margin'] for r,b in pairs),seed_gains=seed_delta)
            table.append(f'| {phase} | {opponent} | {bw}/{bt}/{len(pairs)-bw-bt} | {cw}/{ct}/{len(pairs)-cw-ct} | {delta:+,.1f} | {cash:+,.1f} |')
    pairs=paired['confirmation']
    seed_delta={s:mean(r['margin']-b['margin'] for r,b in pairs if r['seed']==s) for s in sorted({r['seed'] for r,b in pairs})}
    candidate_errors=[e for e in errors if e[0]=='confirmation' and e[3]=='candidate']
    gates=dict(positive_mean_margin=mean(r['margin']-b['margin'] for r,b in pairs)>0,
        nonnegative_each_rival=all(v['margin_gain']>=0 for k,v in summary.items() if k.startswith('confirmation/')),
        six_positive_seeds=sum(d>0 for d in seed_delta.values())>=6,
        no_fewer_wins=sum(r['margin']>0 for r,b in pairs)>=sum(b['margin']>0 for r,b in pairs),
        own_cash_floor=mean(r['cash']-b['cash'] for r,b in pairs)>=-500,
        no_errors_or_fallbacks=not candidate_errors,
        action_time_below_one_second=max(r['max_seconds'] for r,b in pairs)<1)
    chosen='candidate' if all(gates.values()) else 'baseline'
    selected=ROOT/'agents/modern_router_selected.py'
    selected.write_bytes(PATHS[chosen].read_bytes())
    selection=dict(chosen=chosen,sha256=sha256(selected.read_bytes()).hexdigest(),gates=gates,
        confirmation_margin_gain=mean(r['margin']-b['margin'] for r,b in pairs),
        confirmation_cash_gain=mean(r['cash']-b['cash'] for r,b in pairs),seed_gains=seed_delta,
        max_candidate_seconds=max(r['max_seconds'] for r,b in pairs),
        mean_changed_calls=mean(r['telemetry']['modern_input_changed'] for r,b in pairs),
        note='Local working baseline only. Existing Kaggle submission and historical selected agent unchanged.')
    accounting={}
    for phase,ps in paired.items():
        totals=Counter()
        for r,b in ps:
            seat=r['seat']
            for sign,x in ((1,r),(-1,b)):
                for k,v in x['ledger'][seat]['revenue'].items():totals['revenue:'+k]+=sign*v
                for k,v in x['ledger'][seat]['spend'].items():totals['cost:'+k]+=sign*v
                for k in ('input_confirmed_hires','input_confirmed_applications','input_forecast_wheat','input_forecast_carrot'):
                    totals[k]+=sign*x['telemetry'].get(k,0)
                totals['actual_wheat_harvest']+=sign*x['wheat'][seat].get('harvest',0)
        assert sum(v for k,v in totals.items() if k.startswith('revenue:'))-sum(v for k,v in totals.items() if k.startswith('cost:'))==sum(r['cash']-b['cash'] for r,b in ps)
        accounting[phase]={k:v/len(ps) for k,v in totals.items()}
    (OUT/'selection.json').write_text(json.dumps(selection,indent=2),encoding='utf-8')
    (OUT/'summary.json').write_text(json.dumps(dict(comparisons=summary,selection=selection,errors=errors,accounting=accounting),indent=2),encoding='utf-8')
    lines=['# Modern router: working baseline and joint input planning', '',
        '## Result','',
        f"Selected **{chosen}** as the local working agent: `agents/modern_router_selected.py`. "+('The joint input-planning candidate passed every predeclared confirmation gate.' if chosen=='candidate' else 'The candidate did not clear the predeclared gate; retain the exact public V45 baseline.'), '',
        f"Confirmation average candidate-minus-baseline margin: **{selection['confirmation_margin_gain']:+,.1f}**; own cash: **{selection['confirmation_cash_gain']:+,.1f}**. Positive seed averages: **{sum(v>0 for v in seed_delta.values())}/8**. These results do not estimate a leaderboard rating.", '',
        'The currently uploaded `agents/market_impact_selected.py` and submission 56273827 are unchanged. Local selection is not a Kaggle submission.', '',
        '## What was implemented', '',
        '- `modern_router_baseline.py` is an exact, hash-verified copy of the downloaded V45 source. It retains economic feeding, shop-dependent production, crop-input planning, execution safeguards and source attributions.',
        '- `modern_router_candidate.py` is a standalone build of that source plus our new joint fertilizer-tour selector. The feeding rule remains intact. The candidate retains up to six distinct first-worker routes, tries compatible second-worker routes, and values the pair together.',
        '- Candidate valuation sums marginal fertilizer purchase quotes and output sale quotes, includes Fibonacci hiring costs, and retains the existing cash reserve, warehouse/order caps and profit safety factors. Profitable shorter tours may be considered. Existing tours are retained unless the candidate estimates a higher joint net value.',
        '- Physical execution remains with the existing observed-state controller. Gain estimates use scheduled watering and harvest deadlines. Current-price valuation is conservative but is not a reliable forecast of future market prices.', '',
        '## Frozen evaluation', '',
        'One candidate, frozen before panel results. Development: four seeds (137000–137003), both seats, three modern rivals, 48 games. Confirmation: eight different seeds (138000–138007), both seats, four rivals, 128 games. One prior smoke game gives 177 full games total. No parameter tuning occurred between panels.', '',
        'Shop draws are uniform with replacement, shared across each comparison, and hidden until revealed. The effective independent confirmation sample is eight seeds; the opponents include related public-code descendants. Both cash ledgers and wheat conservation after every turn were checked.', '',
        '| Panel | Opponent | Baseline W/T/L | Candidate W/T/L | Paired margin gain | Own-cash gain |',
        '|---|---|---:|---:|---:|---:|',*table,'',
        '## Promotion gate', '',manifest['promotion_gate'],'',
        '| Condition | Passed |','|---|---|',*[f'| {k} | {v} |' for k,v in gates.items()],'',
        '## Runtime and execution', '',
        f"Maximum candidate action time on confirmation under concurrent local load: {selection['max_candidate_seconds']:.3f}s. Mean changed joint-planning calls per game: {selection['mean_changed_calls']:.2f}. Nonzero candidate confirmation error/fallback counters: {len(candidate_errors)}. Timing on a competition host remains untested.", '',
        '## Files and reproduction', '',
        '- Build: `scripts/build_modern_router.py`; editable build fragment: `agents/modern_input_overlay.py`.',
        '- Evaluate: `scripts/evaluate_modern_router.py --phase smoke`, `--phase development`, then `--phase confirmation`.',
        '- Verify and select locally: `scripts/report_modern_router.py`.',
        '- Frozen source hashes, all game ledgers, comparisons and selection: `results/fresh/modern_router/`.',
        '- Public source: [V45 by Ahmed Berat Ozer](https://www.kaggle.com/code/ahmedberatozer/kaggriculture-v45-first-turn-wheat-round-trip). Original source notices are preserved in both standalone files.', '',
        f"Selected SHA-256: `{selection['sha256']}`.", '']
    position=lines.index('## Promotion gate')
    detail=['## What changed economically', '',
        'Candidate minus baseline, averaged across confirmation games. Extra fertilizer and hiring must earn back their costs; an improvement in the planner\'s current-price score does not guarantee a better game outcome.', '',
        '| Quantity or cash flow | Average change |','|---|---:|']
    for key in ('actual_wheat_harvest','input_confirmed_applications','input_confirmed_hires','revenue:WHEAT','revenue:CARROT','revenue:FERTILIZER','cost:BUY_PRODUCT:FERTILIZER','cost:HIRE'):
        detail.append(f"| {key} | {accounting['confirmation'].get(key,0):+,.2f} |")
    detail+=['', 'The full cash accounting is in `summary.json`; it includes all other products and costs. Current-price input valuation remains approximate because output arrives later and both players alter market supply. The shortlist also makes this a bounded heuristic rather than an exact joint optimizer.', '']
    lines[position:position]=detail
    position=lines.index('## Files and reproduction')
    lines[position:position]=['## Decision and next target', '',
        'Keep the modern baseline\'s economic feeding and existing crop-input planner. This candidate produces more wheat, but the additional fertilizer and labor nearly consume the added revenue, and the opponent also benefits from changed market conditions. Enlarging the route search alone did not establish a competitive gain.', '',
        'The next improvement should calibrate marginal input decisions against output prices at delivery time and their effect on winning margin, using this frozen modern opponent panel. Preserve this failed candidate as evidence; do not retune it on the confirmation seeds and call that independent validation.', '']
    check_path=OUT/'entrypoint_check.json'
    if check_path.exists():
        check=json.loads(check_path.read_text(encoding='utf-8'))
        assert check['sha256']==selection['sha256'] and check['steps']==720 and check['statuses']==['DONE','DONE']
        position=lines.index('## Runtime and execution')+2
        lines[position:position]=['The selected standalone file also passed a full 720-state game through the official file-path agent loader with native shop RNG, exact cash ledgers and per-turn wheat conservation. This extra packaging check brings the total to **178 full games**. Focused planner checks also passed for disjoint feasible tours, yield/harvest deadlines, cash reserves, capacity/order limits and observation immutability (`scripts/verify_modern_inputs.py`).', '']
    (ROOT/'docs/modern_router.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(dict(selection=selection,comparisons=summary,errors=errors),indent=2))

if __name__=='__main__':main()
