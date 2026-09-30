"""Summarize frozen opponent-aware sales experiments without tuning policies."""
from collections import Counter
from statistics import mean
import json
from research_opponent_sales import OUT, ROOT
from select_delivery_forecast import score


def margin(r):return r['cash']-r['opponent_cash']


def revenue_audit(rows):
    index={(r['seed'],r['seat'],r['opponent'],r['mode']):r for r in rows};out={}
    for opponent in sorted({r['opponent'] for r in rows}):
        pairs=[(r,index[r['seed'],r['seat'],r['opponent'],'baseline']) for r in rows if r['mode']=='priority' and r['opponent']==opponent]
        by={}
        for who in ('own','other'):
            totals={category:Counter() for category in ('revenue','sold_units','spend')}
            for a,b in pairs:
                i=a['seat'] if who=='own' else 1-a['seat']
                for category,total in totals.items():
                    for k in set(a['ledger'][i][category])|set(b['ledger'][i][category]):
                        total[k]+=a['ledger'][i][category].get(k,0)-b['ledger'][i][category].get(k,0)
            by[who]={category:{k:v/len(pairs) for k,v in total.items() if v} for category,total in totals.items()}
        out[opponent]=by
    return out


def compare(rows,mode,control,opponent=None):
    index={(r['seed'],r['seat'],r['opponent'],r['mode']):r for r in rows}
    pairs=[(r,index[r['seed'],r['seat'],r['opponent'],control]) for r in rows
           if r['mode']==mode and (opponent is None or r['opponent']==opponent)]
    seedmeans={s:mean(margin(a)-margin(b) for a,b in pairs if a['seed']==s) for s in sorted({a['seed'] for a,b in pairs})}
    stats=Counter()
    for a,b in pairs:stats.update(a['stats'])
    return {'n':len(pairs),'cash_delta':mean(a['cash']-b['cash'] for a,b in pairs),
      'margin_delta':mean(margin(a)-margin(b) for a,b in pairs),
      'wins':sum(margin(a)>0 for a,b in pairs),'ties':sum(margin(a)==0 for a,b in pairs),'losses':sum(margin(a)<0 for a,b in pairs),
      'baseline_wins':sum(margin(b)>0 for a,b in pairs),'baseline_ties':sum(margin(b)==0 for a,b in pairs),'baseline_losses':sum(margin(b)<0 for a,b in pairs),
      'seed_margin_deltas':seedmeans,'changed_routes':sum(a['physical_hash']!=b['physical_hash'] for a,b in pairs),
      'changed_shops':sum(a['shops']!=b['shops'] for a,b in pairs),'stats':dict(stats),
      'max_action_seconds':max(a['max_action_seconds'] for a,b in pairs)}


def main():
    decision_path=OUT/'decision.json'
    decision=json.loads(decision_path.read_text()) if decision_path.exists() else {'summary':'Evaluation in progress; retain the existing selected agent pending confirmation.'}
    summary={'decision':decision};parts=['# Opponent-aware sales research\n','## Decision\n',
      decision['summary'].replace('agents/market_priority_selected.py','[agents/market_priority_selected.py](../agents/market_priority_selected.py)')+' No Kaggle submission was made.\n',
      '## Experiment\n',
      'The frozen experiment compares the selected router with three variants: put milk/wool sales first (**priority**); add delivery-aware holding to maximize our revenue (**profit**); or add holding to maximize our revenue minus the opponent\'s (**margin**). Only one lot of at most six milk/wool units is reserved at a time, with a 12-turn hold target, 24-turn payoff horizon, cash and storage guards, and terminal liquidation. Farming actions come from the same router; later router choices can react to changed cash/prices.\n',
      'The predictor uses public animal yields, observed yield decreases, public market inventory and our own stock changes. Hidden opponent inventory is estimated, never read. Three predictors were compared on 16 training games, then frozen before testing: recent average sales, time-of-day sales rhythm, and visible yields combined with that rhythm. Two additional training-seed smoke games exercised the holding policies.\n',
      'Natural tests use four fresh seeds, both seats, four opponents and four policies (128 games). The separate controlled panel uses all eight first-shop types, fixed subsequent shop sequences, both seats, two selling behaviors and four policies (128 games). Opponents are the raw six-day router, E776 pasture, our prompt-selling baseline, and a synthetic daily stockpiler built on that baseline. The stockpiler is a behavior stress test, not a claim about a strong leaderboard agent.\n']
    selection=json.loads((OUT/'forecast_selection.json').read_text())
    parts+=['## Delivery forecasts\n',f"Selected on training data: **{selection['method']}**, minimizing 12-turn delivery error when the current price exceeds the floor. Values below are mean absolute errors in units per product and forecast window; they are not price errors.\n",
      '| Panel | Predictor | 6 turns | 12 turns | 24 turns |\n|---|---|---:|---:|---:|']
    for phase in ('train','test','shops'):
        rows=json.loads((OUT/f'{phase}_results.json').read_text())
        metrics,inference,_=score([r for r in rows if r['mode']=='baseline'])
        summary[phase]={'forecast':metrics,'inference':inference,'comparisons':{}}
        for method in ('recent','clock','visible'):
            vals=[next(x['above_floor_mae'] for x in metrics if x['method']==method and x['horizon']==h) for h in (6,12,24)]
            parts.append(f"| {phase} | {method} | {vals[0]:.2f} | {vals[1]:.2f} | {vals[2]:.2f} |")
        if phase=='train':continue
        for control in ('baseline','priority'):
            for mode in ('priority','profit','margin'):
                if mode==control:continue
                for opponent in [None,*sorted({r['opponent'] for r in rows})]:
                    summary[phase]['comparisons'][f'{mode}/{control}/{opponent or "all"}']=compare(rows,mode,control,opponent)
        if phase=='shops':assert all(c['changed_shops']==0 for c in summary[phase]['comparisons'].values())
    parts+=['\nForecast diagnostics use baseline games only, avoiding repeated counting of forecasts from four policy variants. Checkpoints are every 24 turns from turn 216 through 672, so these errors describe forecasts made at midnight, not uniformly sampled decision times. Training covers only two seeds; held-out performance is the stronger check.\n',
      'The market-inventory reconstruction is approximate near the price floor. A sale can hit $1 during a turn and town consumption can restore the price before the next observation; checking only the two observed prices does not fully identify those sales. Midnight overflow is also ambiguous. The audit therefore reports error even among observations flagged usable by the model. Animal growth forecasts assume continued feeding/care, and do not predict new animal purchases.\n']
    for phase in ('test','shops'):
        parts += [f'## {"Natural-shop held-out games" if phase=="test" else "Controlled shop panel"}\n',
          'Each row compares the variant against its control on the same seed, seat and opponent. W/T/L is against the listed opponent, not a direct variant-versus-control match. Positive margin change improves our lead.\n',
          '| Variant | Control | Opponent | Games | Cash change | Margin change | W/T/L | Control W/T/L |\n|---|---|---|---:|---:|---:|---|---|']
        for key,c in summary[phase]['comparisons'].items():
            mode,control,opponent=key.split('/')
            if control=='priority' and opponent!='all':continue
            parts.append(f"| {mode} | {control} | {opponent} | {c['n']} | {c['cash_delta']:+.1f} | {c['margin_delta']:+.1f} | {c['wins']}/{c['ties']}/{c['losses']} | {c['baseline_wins']}/{c['baseline_ties']}/{c['baseline_losses']} |")
        parts+=['\nSeed-level mean margin changes (seats and opponents averaged within seed):\n']
        for mode in ('priority','profit','margin'):
            c=summary[phase]['comparisons'][f'{mode}/baseline/all']
            parts.append(f"- **{mode}:** {', '.join(str(k)+': '+format(v,'+.1f') for k,v in c['seed_margin_deltas'].items())}. Changed farming-action hashes: {c['changed_routes']}/{c['n']}; changed final shops: {c['changed_shops']}/{c['n']}. Holding statistics: `{json.dumps(c['stats'],sort_keys=True)}`.")
        if phase=='shops':
            rows=json.loads((OUT/'shops_results.json').read_text())
            parts+=['\nMean margin change by first shop (both seats and both opponent behaviors combined):\n',
              '| First shop | Priority vs baseline | Profit vs baseline | Margin vs baseline |\n|---|---:|---:|---:|']
            for seed in sorted({r['seed'] for r in rows}):
                shop=next(r['shops'][0] for r in rows if r['seed']==seed)
                vals=[summary[phase]['comparisons'][f'{mode}/baseline/all']['seed_margin_deltas'][seed] for mode in ('priority','profit','margin')]
                parts.append(f'| {shop} | {vals[0]:+.1f} | {vals[1]:+.1f} | {vals[2]:+.1f} |')
    confirmation_path=OUT/'confirmation_results.json'
    if confirmation_path.exists():
        rows=json.loads(confirmation_path.read_text())
        summary['confirmation']={opponent or 'all':compare(rows,'priority','baseline',opponent) for opponent in [None,*sorted({r['opponent'] for r in rows})]}
        parts+=['\n## Independent confirmation of the packaged candidate\n',
          'After the discovery panel showed that nearly all of the gain came from order priority, the standalone priority candidate was compared with the existing selected agent on eight additional untouched natural seeds, both seats and all four opponents: 128 further games. No policy parameters were changed.\n',
          '| Opponent | Games per policy | Cash change | Margin change | Candidate W/T/L | Baseline W/T/L |\n|---|---:|---:|---:|---|---|']
        for opponent,c in summary['confirmation'].items():
            parts.append(f"| {opponent} | {c['n']} | {c['cash_delta']:+.1f} | {c['margin_delta']:+.1f} | {c['wins']}/{c['ties']}/{c['losses']} | {c['baseline_wins']}/{c['baseline_ties']}/{c['baseline_losses']} |")
        c=summary['confirmation']['all']
        parts.append('\nSeed-level mean margin changes: '+', '.join(str(k)+': '+format(v,'+.1f') for k,v in c['seed_margin_deltas'].items())+'.')
        parts.append(f"\nChanged farming-action hashes: {c['changed_routes']}/{c['n']}; changed shops: {c['changed_shops']}/{c['n']}. Largest measured packaged-agent action time: {c['max_action_seconds']:.3f} seconds (local timing, not a platform guarantee).")
        parts.append('\nThe formal evaluation totals 400 games: 16 training, 128 natural discovery, 128 controlled-shop, and 128 independent confirmation. Four additional smoke/parity games were used for implementation checks. The standalone candidate uses only the Python standard library, matched the research control on 1,438 actions, and passed its JSON stdin entry-point check.')
    natural=json.loads((OUT/'test_results.json').read_text())
    index={(r['seed'],r['seat'],r['opponent'],r['mode']):r for r in natural}
    for a in natural:
        if a['mode']=='priority':
            b=index[a['seed'],a['seat'],a['opponent'],'baseline']
            assert all(a['ledger'][i]['sold_units']==b['ledger'][i]['sold_units'] for i in (0,1))
    audit=revenue_audit(natural)
    summary['priority_revenue_audit']=audit
    parts+=['\n## Why market order matters\n',
      'The natural-test ledger isolates the priority-only effect: both players sold the same quantities, and our farming routes and final shops were unchanged. Against the raw six-day router, prioritizing milk/wool changed our milk revenue by '+format(audit['sixday']['own']['revenue'].get('MILK',0),'+.1f')+' and its milk revenue by '+format(audit['sixday']['other']['revenue'].get('MILK',0),'+.1f')+' per game on average. Moving other products later has a cost, however. Against the synthetic stockpiler, milk rarely competes at the same time and that cost dominates. This points toward predicting the opponent\'s market-order positions and choosing which product to sell first, rather than relying only on aggregate shipment volume.\n',
      '\n## Validation and interpretation\n',
      '- All games completed 720 states with valid statuses. Both players\' terminal cash reconciles exactly to initial cash plus actual sales minus spending. Every reserved lot was released by game end.\n',
      '- 640 verification cases compare dynamic programming against exhaustive enumeration and same-product lockstep trades against the official engine. A synthetic case demonstrates a real objective difference: profit waits while margin sells immediately. This verifies the mechanism, not competitive strength.\n',
      '- Market-order priority is tested separately so a gain from order placement cannot be attributed to forecasting. The scheduler approximates competing orders as aligned same-product trades; full matches use actual engine order positions. Opponent forecasts remain fixed inside each planning horizon and do not simulate retaliation.\n',
      '- Same seed can yield different shops if farm trajectories diverge because weeds and shops share an RNG. The controlled panel holds revealed shop sequences equal; the policy sees no future shop draws. Natural results include these downstream effects.\n',
      '- Both seats are paired checks, not independent seeds. Four discovery seeds, eight confirmation seeds and related public policy families do not establish leaderboard strength. The controlled panel covers all first shops but only one subsequent sequence per first shop.\n']
    for phase in ('train','test','shops'):
        a=summary[phase]['inference'];parts.append(f"- {phase} inventory-inference audit: {a['identifiable_turns']}/{a['total_product_turns']} product-turns flagged usable; mean absolute error on those = {a['known_mae']:.4f} units. Of {a['known_mismatches']} mismatches, {a['explained_by_floor_sales']} are exactly explained by the two players' floor-price sales.")
    parts+=['\n## Artifacts\n',
      '- Research policy: `agents/opponent_sales.py` (requires the local engine; not a standalone submission).\n',
      '- Runner: `scripts/research_opponent_sales.py`; forecast selection: `scripts/select_delivery_forecast.py`; verification: `scripts/verify_opponent_sales.py`; this report: `scripts/report_opponent_sales.py`.\n',
      '- Frozen source hashes, seeds, full-game results, ledger events, forecasts, and decision logs: `results/fresh/opponent_sales/`. Aggregate metrics: `summary.json`.\n']
    parts+=['- Standalone priority candidate: `agents/market_priority_candidate.py`; builder/parity check: `scripts/build_market_priority.py`; independent confirmation runner: `scripts/confirm_market_priority.py`.\n']
    natural_extra=summary['test']['comparisons']['margin/priority/all']['margin_delta']
    shop_extra=summary['shops']['comparisons']['margin/priority/all']['margin_delta']
    forecast=summary['test']['forecast']
    recent=next(x['above_floor_mae'] for x in forecast if x['method']=='recent' and x['horizon']==12)
    visible=next(x['above_floor_mae'] for x in forecast if x['method']=='visible' and x['horizon']==12)
    parts[3:3]=['## Main findings\n',
      f'- Visible-state delivery forecasts reduced held-out 12-turn error by {(1-visible/recent)*100:.1f}% versus a recent-sales average ({recent:.2f} to {visible:.2f} units).\n',
      f'- Nearly all competitive benefit came from putting milk/wool sales earlier in the market queue. Adding margin-aware holding changed margin by only {natural_extra:+.1f} per natural test game and {shop_extra:+.1f} per controlled-shop game relative to priority alone. The holding layer is not selected.\n',
      '- The simple priority tactic does not condition on an opponent forecast. The opponent model remains a research component. A useful next experiment is adaptive product ordering: account for likely rival orders and the opportunity cost of delaying our other products. Test it against the fixed-priority candidate and different opponent families.\n']
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2))
    (ROOT/'docs/opponent_sales.md').write_text('\n'.join(parts),encoding='utf-8')
    print(json.dumps({p:{k:v for k,v in summary[p]['comparisons'].items() if k.endswith('/all')} for p in ('test','shops')},indent=2))


if __name__=='__main__':main()
