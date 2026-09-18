"""Report frozen paired results; preserve existing selected agents."""
from collections import Counter
from hashlib import sha256
from statistics import mean
import json
from evaluate_delivery_inputs import ROOT,OUT,PATHS,jobs

def main():
    manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
    for name,h in manifest['sources'].items():assert sha256((ROOT/name).read_bytes()).hexdigest()==h,name
    rows=[json.loads((OUT/'games'/('-'.join(map(str,j))+'.json')).read_text(encoding='utf-8'))
          for phase in ('development','confirmation') for j in jobs(phase)]
    summary={};table=[];errors=[]
    for r in rows:
        for group in ('telemetry','chassis_diagnostics'):
            for k,v in r[group].items():
                if not k.endswith('_abs_error') and any(s in k.lower() for s in ('error','fallback')) and isinstance(v,(int,float)) and v:
                    errors.append((r['phase'],r['policy'],r['seed'],k,v))
    for phase in ('development','confirmation'):
        for control in ('public','baseline'):
            lookup={(r['seed'],r['seat'],r['opponent']):r for r in rows if r['phase']==phase and r['policy']==control}
            ps=[(r,lookup[r['seed'],r['seat'],r['opponent']]) for r in rows if r['phase']==phase and r['policy']=='candidate']
            for rival in ('all','v44','v45','twocoins'):
                pairs=[(r,b) for r,b in ps if rival=='all' or r['opponent']==rival]
                seed={s:mean(r['margin']-b['margin'] for r,b in pairs if r['seed']==s) for s in sorted({r['seed'] for r,b in pairs})}
                value=dict(games=len(pairs),margin_gain=mean(r['margin']-b['margin'] for r,b in pairs),
                    cash_gain=mean(r['cash']-b['cash'] for r,b in pairs),seed_gains=seed,
                    candidate_wins=sum(r['margin']>0 for r,b in pairs),control_wins=sum(b['margin']>0 for r,b in pairs))
                summary[phase+'/'+control+'/'+rival]=value
                table.append(f"| {phase} | {control} | {rival} | {value['margin_gain']:+.1f} | {value['cash_gain']:+.1f} | {value['candidate_wins']}/{len(pairs)} | {value['control_wins']}/{len(pairs)} |")
    conf=[r for r in rows if r['phase']=='confirmation' and r['policy']=='candidate']
    v=summary['confirmation/baseline/all']
    gates=dict(positive_margin=v['margin_gain']>0,
        nonnegative_each_rival=all(summary['confirmation/baseline/'+o]['margin_gain']>=0 for o in ('v44','v45','twocoins')),
        six_positive_seeds=sum(x>0 for x in v['seed_gains'].values())>=6,
        no_fewer_wins=v['candidate_wins']>=v['control_wins'],cash_floor=v['cash_gain']>=-500,
        no_errors=not [e for e in errors if e[0]=='confirmation' and e[1]=='candidate'],
        time_limit=max(r['max_seconds'] for r in conf)<1,
        positive_vs_public=summary['confirmation/public/all']['margin_gain']>0)
    chosen='candidate' if all(gates.values()) else 'baseline'
    selected=ROOT/'agents/v45_delivery_selected.py';selected.write_bytes(PATHS[chosen].read_bytes())
    lookup={(r['seed'],r['seat'],r['opponent']):r for r in rows if r['phase']=='confirmation' and r['policy']=='baseline'}
    totals=Counter()
    for r in conf:
        b=lookup[r['seed'],r['seat'],r['opponent']]
        for sign,x in ((1,r),(-1,b)):
            for k,val in x['ledger'][x['seat']]['revenue'].items():totals['revenue:'+k]+=sign*val
            for k,val in x['ledger'][x['seat']]['spend'].items():totals['cost:'+k]+=sign*val
    assert abs(sum(val for k,val in totals.items() if k.startswith('revenue:'))-sum(val for k,val in totals.items() if k.startswith('cost:'))-v['cash_gain']*len(conf))<1e-6
    checks=sum(r['telemetry'].get('delivery_quotes_checked',0) for r in conf)
    diagnostics=dict(max_seconds=max(r['max_seconds'] for r in conf),
        mean_changed=mean(r['telemetry']['delivery_changed'] for r in conf),
        mean_declined=mean(r['telemetry']['delivery_declined'] for r in conf),quotes_checked=checks,
        forecast_mae=sum(r['telemetry']['delivery_forecast_abs_error'] for r in conf)/max(1,checks),
        current_mae=sum(r['telemetry']['delivery_current_abs_error'] for r in conf)/max(1,checks))
    selection=dict(chosen=chosen,gates=gates,sha256=sha256(selected.read_bytes()).hexdigest())
    result=dict(selection=selection,comparisons=summary,diagnostics=diagnostics,errors=errors,
                accounting={k:val/len(conf) for k,val in totals.items()})
    ablation=[]
    for r in conf:
        path=OUT/'games'/f"confirmation-{r['seed']}-{r['seat']}-ablation-{r['opponent']}.json"
        if path.exists():ablation.append((r,json.loads(path.read_text(encoding='utf-8'))))
    if ablation:
        assert len(ablation)==len(conf)
        am=json.loads((OUT/'ablation_manifest.json').read_text(encoding='utf-8'))
        assert sha256((ROOT/'agents/v45_delivery_current_control.py').read_bytes()).hexdigest()==am['sha256']
        result['ablation']=dict(games=len(ablation),forecast_minus_current_margin=mean(r['margin']-a['margin'] for r,a in ablation),
            forecast_minus_current_cash=mean(r['cash']-a['cash'] for r,a in ablation),
            current_minus_baseline_margin=mean(a['margin']-lookup[a['seed'],a['seat'],a['opponent']]['margin'] for r,a in ablation))
        for r,a in ablation:
            for group in ('telemetry','chassis_diagnostics'):
                for key,val in a[group].items():
                    if not key.endswith('_abs_error') and any(s in key.lower() for s in ('error','fallback')) and isinstance(val,(int,float)) and val:
                        errors.append(('confirmation','ablation',a['seed'],key,val))
    (OUT/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    lines=['# V45 delivery-time input valuation','',
        f"Selected **{chosen}** for `agents/v45_delivery_selected.py`. Existing `v45_our_selected.py` and the Kaggle submission remain unchanged.",'',
        f"Confirmation versus our selected hybrid: **{v['margin_gain']:+.1f} margin**, **{v['cash_gain']:+.1f} own cash**; {sum(x>0 for x in v['seed_gains'].values())}/8 positive seed averages.",'',
        '## Experiment','',
        'One frozen standalone candidate built on our V45 sale-ordering hybrid. It values optional wheat/carrot fertilizer-worker plans at estimated delivery-time prices. It compares the native plan, a bounded shortlist of joint worker tours, and no investment. Existing execution, feeding and general investment logic remain native.', '',
        'Eight scenarios sample unrevealed shops uniformly with replacement using an independent local RNG. Public market changes over 24 or 48 turns, with known demand added back, estimate aggregate net trading by both farms. Scenarios extrapolate those rates and subtract known and sampled shop demand. Scores combine 75% mean and 25% lower-quartile proceeds, subtract fertilizer/hiring costs, and retain cash/capacity/profit guards.', '',
        'Delivery is approximated by the harvest-day midnight cargo drop and the next native tape sale. Incremental output changes its own sale quotes. This is not an explicit opponent-stock forecast, learned price model, or joint crop/animal investment optimizer.', '',
        '## Frozen evaluation','',
        'Development: two fresh seeds (142000-142001). Confirmation: eight different seeds (143000-143007). Both seats, three rivals, and three policies: public V45, our selected hybrid, and candidate. 180 panel games plus one smoke game. Common hidden shop schedules isolate strategy changes; weeds remain policy dependent. Seeds, not individual games, are the main independent sample; rivals include related routers. No tuning between panels.', '',
        '| Panel | Control | Rival | Margin gain | Own-cash gain | Candidate wins | Control wins |',
        '|---|---|---|---:|---:|---:|---:|',*table,'',
        '## Promotion gate','',manifest['gate'],'',
        *[f'- {k}: {passed}' for k,passed in gates.items()],'',
        '## Forecast and execution diagnostics','',
        f"On {checks} planned-output quote checks, forecast absolute error averaged {diagnostics['forecast_mae']:.2f}; reusing the decision-time quote gave {diagnostics['current_mae']:.2f}. These are selected-plan diagnostics on repeated/related decisions, not independent forecast validation or realized marginal-profit attribution.",'',
        f"Mean changed planning calls: {diagnostics['mean_changed']:.2f}; declined native plans: {diagnostics['mean_declined']:.2f}. Maximum candidate call: {diagnostics['max_seconds']:.3f}s. All panel games checked 720 valid states, exact cash accounting and per-turn wheat conservation. Nonzero error/fallback entries: {len(errors)}.",'',
        '## Limits and interpretation','',
        'The candidate changes both valuation and the tour shortlist; the current-price diagnostic control isolates their effects. Flow extrapolation cannot predict discrete rival deliveries or policy changes. Native early-sale reservations and physical repairs can shift the actual delivery/sale time. Crop gains, storage availability and profit safety factors remain approximations inherited from the existing planner. The shortlist is still generated using current-price heuristics and may omit routes favored by future prices. No leaderboard/Elo claim follows from this panel.', '',
        '## Reproduction','',
        '- `scripts/build_delivery_inputs.py`',
        '- `scripts/verify_delivery_inputs.py`',
        '- `scripts/evaluate_delivery_inputs.py --phase smoke/development/confirmation` (one phase per invocation)',
        '- `scripts/report_delivery_inputs.py`',
        '- `results/fresh/delivery_inputs/manifest.json`, `summary.json` and individual game ledgers.','']
    index=lines.index('## Limits and interpretation')
    details=['## Cash-flow changes','', '| Cash flow | Candidate minus selected hybrid |','|---|---:|']
    for k in ('revenue:WHEAT','revenue:CARROT','revenue:FERTILIZER','cost:BUY_PRODUCT:FERTILIZER','cost:HIRE'):
        details.append(f"| {k} | {result['accounting'].get(k,0):+.2f} |")
    details+=['']
    details+=['## Seed consistency','', '| Confirmation seed | Margin change versus selected hybrid |','|---|---:|',
              *[f'| {seed} | {gain:+.1f} |' for seed,gain in v['seed_gains'].items()], '']
    if ablation:
        a=result['ablation']
        details+=['## Current-price diagnostic control','',
            f"An additional {a['games']} games used identical tour choices and guards, replacing only forecast proceeds with current-price proceeds. Forecast minus current-price margin: **{a['forecast_minus_current_margin']:+.1f}**; own cash: **{a['forecast_minus_current_cash']:+.1f}**. The current-price control itself changed margin by {a['current_minus_baseline_margin']:+.1f} versus our selected hybrid. This control was added for diagnosis and is not eligible for promotion.",'']
    check_path=OUT/'entrypoint.json'
    if check_path.exists():
        check=json.loads(check_path.read_text(encoding='utf-8'))
        assert check['sha256']==sha256(PATHS['candidate'].read_bytes()).hexdigest()
        assert check['steps']==720 and check['statuses']==['DONE','DONE']
        details += [f"The candidate also passed a native-shop-RNG full game through the official file-path loader (seed {check['seed']}) with exact cash and wheat accounting. Total full games including smoke, integration and diagnostic control: {182+len(ablation)}.",'']
    lines[index:index]=details
    index=lines.index('## Reproduction')
    lines[index:index]=['## Decision and next research step','',
        'Retain the selected V45 sale-ranking hybrid. This candidate did not produce a consistent improvement and won fewer confirmation games. The diagnostic control shows that forecasting helped this particular tour selector recover its losses, but not enough to improve the retained agent.', '',
        'Before extending the model to animals or land, measure delivery-time quote forecasts for all feasible investment opportunities, including rejected plans, on a fresh logged panel. Replace constant-flow extrapolation with forecasts of discrete harvest/delivery events from both visible farms, and model actual sale reservations. Validate forecast calibration and marginal-profit estimates before another policy promotion test. This is proposed follow-up work, not an implemented feature.', '']
    (ROOT/'docs/delivery_inputs.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
