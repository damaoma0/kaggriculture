"""Apply the frozen competitive gate after event-forecast validation."""
import json
from hashlib import sha256
from statistics import mean
from collections import Counter
from evaluate_event_inputs import ROOT,OUT,PATHS,jobs

def main():
    manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
    for name,h in manifest['sources'].items():assert sha256((ROOT/name).read_bytes()).hexdigest()==h,name
    rows=[json.loads((OUT/'games'/('-'.join(map(str,j))+'.json')).read_text(encoding='utf-8')) for j in jobs()]
    bases={(r['seed'],r['seat'],r['opponent']):r for r in rows if r['policy']=='baseline'}
    pairs=[(r,bases[r['seed'],r['seat'],r['opponent']]) for r in rows if r['policy']=='candidate']
    summary={}
    for opponent in ('all','v45','twocoins','farmingv5'):
        ps=[(r,b) for r,b in pairs if opponent=='all' or r['opponent']==opponent]
        summary[opponent]=dict(games=len(ps),margin_gain=mean(r['margin']-b['margin'] for r,b in ps),cash_gain=mean(r['cash']-b['cash'] for r,b in ps),
            candidate_wins=sum(r['margin']>0 for r,b in ps),baseline_wins=sum(b['margin']>0 for r,b in ps),
            candidate_ties=sum(r['margin']==0 for r,b in ps),baseline_ties=sum(b['margin']==0 for r,b in ps))
    seeds={s:mean(r['margin']-b['margin'] for r,b in pairs if r['seed']==s) for s in sorted({r['seed'] for r,b in pairs})}
    errors=[];totals=Counter()
    for r,b in pairs:
        for field in ('telemetry','chassis_diagnostics'):
            for k,v in r[field].items():
                if any(w in k.lower() for w in ('error','fallback')) and isinstance(v,(int,float)) and v:errors.append((r['seed'],r['seat'],r['opponent'],k,v))
        for sign,x in ((1,r),(-1,b)):
            for k,v in x['ledger'][x['seat']]['revenue'].items():totals['revenue:'+k]+=sign*v
            for k,v in x['ledger'][x['seat']]['spend'].items():totals['cost:'+k]+=sign*v
    assert abs(sum(v for k,v in totals.items() if k.startswith('revenue:'))-sum(v for k,v in totals.items() if k.startswith('cost:'))-summary['all']['cash_gain']*len(pairs))<1e-6
    diagnostics=dict(max_seconds=max(r['max_seconds'] for r,b in pairs),
        mean_changed_calls=mean(r['telemetry']['event_changed'] for r,b in pairs),
        mean_valued_lots=mean(r['telemetry']['event_valued_lots'] for r,b in pairs),
        mean_unchanged_lots=mean(r['telemetry']['event_unchanged_lots'] for r,b in pairs))
    gates=dict(positive_margin=summary['all']['margin_gain']>0,nonnegative_each_rival=all(summary[o]['margin_gain']>=0 for o in ('v45','twocoins','farmingv5')),
        six_positive_seeds=sum(v>0 for v in seeds.values())>=6,no_fewer_wins=summary['all']['candidate_wins']>=summary['all']['baseline_wins'],
        cash_floor=summary['all']['cash_gain']>=-500,no_errors=not errors,call_below_one_second=diagnostics['max_seconds']<1)
    verification=json.loads((OUT/'verification.json').read_text(encoding='utf-8'))
    assert verification['sha256']==sha256(PATHS['candidate'].read_bytes()).hexdigest() and verification['steps']==720
    chosen='candidate' if all(gates.values()) else 'baseline'
    selected=ROOT/'agents/v45_event_selected.py';selected.write_bytes(PATHS[chosen].read_bytes())
    result=dict(chosen=chosen,sha256=sha256(selected.read_bytes()).hexdigest(),comparisons=summary,seeds=seeds,gates=gates,diagnostics=diagnostics,errors=errors,
                accounting={k:v/len(pairs) for k,v in totals.items()})
    (OUT/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    forecasts=json.loads((ROOT/'results/fresh/event_prices/summary.json').read_text(encoding='utf-8'))['primary_mae']
    lines=['# Event forecast: V45 investment-policy test','',
        f"Selected **{chosen}** as `agents/v45_event_selected.py`. The original hybrid and Kaggle submission are unchanged.",'',
        f"Candidate versus selected hybrid: **{summary['all']['margin_gain']:+.1f} mean margin**, **{summary['all']['cash_gain']:+.1f} own cash**; {sum(v>0 for v in seeds.values())}/8 positive seed averages.",'',
        '## Forecast result','',
        f"The preceding independent forecast test passed: primary wheat/carrot price MAE was {forecasts['event']:.3f}, versus {forecasts['flow']:.3f} for market flow and {forecasts['base']:.3f} for a calibrated model without production/stock features. Event forecasts improved all eight held-out seeds. Milk/wool diagnostics also improved. See [forecast report](event_prices.md).",'',
        '## What changed in the policy','',manifest['design'],'',
        'The original three native tour modes, minimum tour length, two-worker limit, costs, end-of-lot price-impact convention, cash reserve and profitability thresholds are preserved. Forecast output is estimated to enter the shed at harvest-day midnight and sell at the next native tape slot. Predicted inventory is interpolated between trained horizons. If delivery is outside the tested window or has no matched sale slot, native current-price valuation is used. No aggressive liquidation or expanded joint-tour selector was added.','',
        'The code embeds the frozen coefficients and exact research feature code with engine constants, so the candidate is a single standalone file with no local engine import. Synthetic feature parity and exact native-plan equivalence with current quotes were verified.','',
        '## Fresh policy test','',
        'Eight new seeds (147000-147007), both seats, three rivals, two policies: 96 complete games. Shops use common hidden draws per seed; neither policy sees future shops. The forecast coefficients and policy were frozen before this panel. A separate native-RNG game tested the official file-path loader. Combined with the 72 forecast-research games, this study contains 169 full games.','',
        '| Rival | Margin gain | Cash gain | Candidate wins/ties | Baseline wins/ties |','|---|---:|---:|---:|---:|',
        *[f"| {o} | {v['margin_gain']:+.1f} | {v['cash_gain']:+.1f} | {v['candidate_wins']}/{v['candidate_ties']} of {v['games']} | {v['baseline_wins']}/{v['baseline_ties']} of {v['games']} |" for o,v in summary.items()],'',
        '## Seed consistency','', '| Seed | Margin change |','|---|---:|',*[f'| {s} | {v:+.1f} |' for s,v in seeds.items()],'',
        '## Cash-flow changes','', '| Cash flow | Mean change |','|---|---:|',
        *[f"| {k} | {result['accounting'].get(k,0):+.2f} |" for k in ('revenue:WHEAT','revenue:CARROT','revenue:FERTILIZER','cost:BUY_PRODUCT:FERTILIZER','cost:HIRE')],'',
        '## Promotion gate','',manifest['gate'],'',*[f'- {k}: {v}' for k,v in gates.items()],'',
        f"Mean changed planning calls per game: {diagnostics['mean_changed_calls']:.2f}. Forecast-valued lot evaluations: {diagnostics['mean_valued_lots']:.1f}; current-price lot evaluations: {diagnostics['mean_unchanged_lots']:.1f}. These counters include alternative plans, not distinct purchases. Maximum candidate call: {diagnostics['max_seconds']:.3f}s. Nonzero candidate error/fallback counters: {len(errors)}. All games passed valid-state, cash-ledger and wheat-conservation checks.",'',
        '## Interpretation and limits','',
        'A better quote forecast is not an estimate of the causal profit from an extra unit of production. Delivery timing is approximate, action changes can shift future market flow, and the native route shortlist and profit thresholds remain fixed. Training snapshots were at 12-hour intervals; actual investment decisions occur at hours 1-3. Policy evaluation tests that timing shift directly. Both studies cover only a few related opponent families; they do not imply a leaderboard rating.','',
        '## Decision','',
        'Keep the validated event forecast and its frozen coefficients for further research. Retain the existing competitive hybrid: the candidate misses the predeclared six-positive-seeds gate. This is a sparse-impact result rather than evidence of a negative average effect: three seed averages improved, five were unchanged, and none fell. Only 0.25 planning calls changed per game on this panel; the original planner is insensitive to many quote improvements. Do not relax the gate after seeing the results.', '',
        'A promising next application is bounded sale timing, where the forecast can affect more decisions and milk/wool price changes are larger. That requires its own fresh competitive test, explicit inventory/cash limits and a comparison with our existing price-impact sale ordering. It has not been implemented in this study.', '',
        '## Files','',
        '- `agents/v45_event_candidate.py`: standalone experimental policy.',
        '- `agents/v45_event_selected.py`: outcome of the frozen promotion gate.',
        '- `agents/event_input_overlay.py`, `scripts/build_event_inputs.py`: editable source and build.',
        '- `scripts/verify_event_inputs.py`, `scripts/evaluate_event_inputs.py`, `scripts/report_event_inputs.py`.',
        '- `results/fresh/event_inputs/`: manifests, ledgers, verification and summary.','']
    (ROOT/'docs/event_inputs.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
