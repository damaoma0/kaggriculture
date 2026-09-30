"""Frozen-rule selection and reporting for adaptive market ordering."""
from collections import Counter
from statistics import mean
import argparse,json
from research_adaptive_order import OUT,ROOT
from report_opponent_sales import compare


def audit(rows):
    errors=[];usable=0;total=0;constraint_checks=0
    for r in rows:
        constraint_checks+=r['constraint_checks']
        if r['mode']!='fixed':continue
        actual=Counter()
        for step,seat,item,amount,price in r['events']:
            if seat!=r['seat']:actual[step,item]+=amount
        for rec in r['inferred']:
            for item,q in rec['net'].items():
                total+=1
                if q is not None:
                    usable+=1;errors.append(abs(q-actual[rec['step'],item]))
    return {'product_turns':total,'usable_product_turns':usable,'usable_mae':mean(errors),'usable_mismatches':sum(e!=0 for e in errors),'action_constraint_checks':constraint_checks}


def summarize(phase):
    rows=json.loads((OUT/(phase+'_results.json')).read_text())
    extra=OUT/(phase+'_available_results.json')
    if extra.exists():rows+=json.loads(extra.read_text())
    modes=sorted({r['mode'] for r in rows}-{'fixed'})
    result={'games':len(rows),'audit':audit(rows),'comparisons':{}}
    index={(r['seed'],r['seat'],r['opponent'],r['mode']):r for r in rows}
    for r in rows:
        baseline=index[r['seed'],r['seat'],r['opponent'],'fixed']
        assert r['opening_hash']==baseline['opening_hash'],'Opening changed'
        if phase=='shops':assert r['shops']==baseline['shops'],'Controlled shops changed'
    for mode in modes:
        for opponent in [None,*sorted({r['opponent'] for r in rows})]:
            result['comparisons'][f'{mode}/{opponent or "all"}']=compare(rows,mode,'fixed',opponent)
        pairs=[(r,index[r['seed'],r['seat'],r['opponent'],'fixed']) for r in rows if r['mode']==mode]
        result['comparisons'][mode+'/all']['changed_own_sale_volumes']=sum(a['ledger'][a['seat']]['sold_units']!=b['ledger'][b['seat']]['sold_units'] for a,b in pairs)
        result['comparisons'][mode+'/all']['changed_other_sale_volumes']=sum(a['ledger'][1-a['seat']]['sold_units']!=b['ledger'][1-b['seat']]['sold_units'] for a,b in pairs)
    if 'available' in modes:
        result['available_comparisons']={mode:compare(rows,mode,'available') for mode in modes if mode!='available'}
    result['packaged_parity_actions']=sum(r.get('packaged_parity_actions',0) for r in rows)
    return result,rows


def select(summary):
    plan=json.loads((OUT/'selection_plan.json').read_text())
    amendment=OUT/'selection_amendment.json'
    if amendment.exists():
        plan['amendment']=json.loads(amendment.read_text());plan['candidates']=['available','static','clock','visible']
    scores={};eligible=[]
    for mode in plan['candidates']:
        natural=summary['discovery']['comparisons'][f'{mode}/all'];shops=summary['shops']['comparisons'][f'{mode}/all']
        scores[mode]=(natural['margin_delta']+shops['margin_delta'])/2
        if min(natural['margin_delta'],shops['margin_delta'])>0 and natural['wins']>=natural['baseline_wins']:eligible.append(mode)
    mode=None
    if eligible:
        best=max(scores[m] for m in eligible)
        mode=next(m for m in plan['candidates'] if m in eligible and scores[m]>=best-50)
    result={'mode':mode,'scores':scores,'eligible':eligible,'rule':plan}
    path=OUT/'selection.json'
    if path.exists():assert json.loads(path.read_text())==result,'Frozen selection changed'
    else:path.write_text(json.dumps(result,indent=2))
    return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--select',action='store_true');args=ap.parse_args()
    summary={};datasets={}
    for phase in ('discovery','shops','confirmation'):
        if (OUT/(phase+'_results.json')).exists():summary[phase],datasets[phase]=summarize(phase)
    if args.select:selection=select(summary)
    else:selection=json.loads((OUT/'selection.json').read_text()) if (OUT/'selection.json').exists() else None
    summary['selection']=selection
    decision=json.loads((OUT/'decision.json').read_text()) if (OUT/'decision.json').exists() else {'summary':'Evaluation is in progress. The selected agent remains agents/market_priority_selected.py.'}
    summary['decision']=decision
    decision_text=decision['summary']
    if decision.get('selected'):decision_text=decision_text.replace(decision['selected'],f"[{decision['selected']}](../{decision['selected']})")
    parts=['# Adaptive market-order research\n','## Decision\n',decision_text+'\n','## Method\n',
      'All variants start from the selected six-day router with milk/wool-first selling. Through turn 215, actions are identical. Thereafter only existing SELL orders are permuted: quantities, farming actions and the positions of non-SELL orders are preserved relative to the base policy at the current observation. Later farming decisions can still react to changed cash or prices. There is no stock holding.\n',
      '| Policy | Ranking information |\n|---|---|\n| fixed | Existing milk/wool-first ordering |\n| available | Move empty sales behind available sales; preserve other relative order |\n| static | Current prices and our lot size, assuming the rival sells an equal-sized lot |\n| clock | Rival net trade inferred from public market changes minus our own net trades, using the last four days and the same hour of day |\n| visible | Clock estimate for all products, replaced for milk/wool by the previous study\'s visible-animal delivery estimate |\n',
      'For each of our lots, the ranking value is the difference in immediate cash margin between selling the whole lot before versus after the predicted rival lot. Negative rival flow represents buying wheat or fertilizer. Fractional forecasts interpolate adjacent integer scenarios. Orders with larger values go earlier; ties preserve existing order. This heuristic does not infer the rival\'s actual order positions or jointly optimize the complete queue. It uses current observations and past observations only; no opponent private state, current opponent action or future shop draw is available.\n',
      'Inference flags observations unusable at the price floor or ambiguous midnight overflow. It checks prices before town consumption as well as observed prices, addressing the previous study\'s floor-recovery ambiguity. Mixed buying and selling can still make inference uncertain. Unknown flows are excluded from historical averages.\n',
      '## Evaluation design\n',
      'Discovery: four fresh natural seeds, both seats, five opponents, four policies (160 games). Shop controls: all eight first shops, one fixed subsequent sequence each, both seats, fixed-priority and stockpiling opponents, four policies (128 games). Opponents are the raw six-day router, public E776 pasture, the previous prompt-selling adapter, our selected fixed-priority agent, and a synthetic stockpiler. The latter three are derived behaviors, not independent public-policy families.\n',
      'The original selection rule was frozen before discovery outcomes were inspected. Candidates need positive margin improvement in both panels and no fewer aggregate natural-panel wins. Rank by the equal-weight mean of the two panel improvements; prefer the simpler candidate when within 50 margin units of the best. Promotion requires positive mean confirmation margin, no fewer aggregate wins, and more wins than losses in direct matches against fixed priority.\n',
      '### Attribution control added during discovery\n',
      'Inspection of seed 124000, turn 517 revealed a stale nine-unit MILK order with no available milk: the earlier automatic-sales adapter had already liquidated it. The price-impact heuristic moved an eight-unit STRAWBERRY sale ahead of it; the engine recorded strawberry sales and no milk sale. Empty orders still occupy a queue position. This can explain gains without any useful price ranking or opponent forecast.\n',
      'We therefore added the availability-only control after examining partial logs, recording the amendment separately and leaving the original four policies and manifests unchanged. It adds 40 natural and 32 controlled-shop games. The amended simplicity order is available, static, clock, visible, retaining the original eligibility rule and 50-unit tolerance. Confirmation uses the original eight untouched seeds: fixed plus the selected candidate, and availability as a third policy if it was not selected. A more complex candidate must also improve confirmation margin over availability. This attribution addition is explicitly post hoc; confirmation remains untouched.\n']
    if selection:parts+=['## Selection\n',f"Chosen for confirmation: **{selection['mode'] or 'none'}**. Equal-panel scores: "+', '.join(f'{m} {v:+.1f}' for m,v in selection['scores'].items())+'.\n']
    for phase,data in summary.items():
        if phase not in datasets:continue
        parts += [f'## {phase.capitalize()} results\n',
          'Cash and margin changes compare matched seed/seat/opponent games against fixed priority. W/T/L is versus the listed opponent.\n',
          '| Variant | Opponent | Games | Cash change | Margin change | W/T/L | Fixed W/T/L |\n|---|---|---:|---:|---:|---|---|']
        for key,c in data['comparisons'].items():
            mode,opponent=key.split('/')
            parts.append(f"| {mode} | {opponent} | {c['n']} | {c['cash_delta']:+.1f} | {c['margin_delta']:+.1f} | {c['wins']}/{c['ties']}/{c['losses']} | {c['baseline_wins']}/{c['baseline_ties']}/{c['baseline_losses']} |")
        if data.get('available_comparisons'):
            parts+=['\nAdditional gain over availability-only ordering:\n',
              '| Variant | Cash change | Margin change |\n|---|---:|---:|']
            for mode,c in data['available_comparisons'].items():parts.append(f"| {mode} | {c['cash_delta']:+.1f} | {c['margin_delta']:+.1f} |")
        parts+=['\nSeed-level mean margin changes, averaging seats and opponents within each seed:\n']
        for key,c in data['comparisons'].items():
            if not key.endswith('/all'):continue
            parts.append(f"- **{key.split('/')[0]}:** "+', '.join(f'{s}: {v:+.1f}' for s,v in c['seed_margin_deltas'].items())+f". Changed farming-action hashes: {c['changed_routes']}/{c['n']}; changed shops: {c['changed_shops']}/{c['n']}. Reordered turns: {c['stats'].get('reordered_turns',0)}; opportunities: {c['stats'].get('opportunities',0)}. Maximum local action time: {c['max_action_seconds']:.3f}s.")
            parts.append(f"  Actual total product quantities sold changed in {c['changed_own_sale_volumes']}/{c['n']} own games and {c['changed_other_sale_volumes']}/{c['n']} opponent games.")
        a=data['audit'];parts.append(f"\nInference audit, fixed-policy games only: {a['usable_product_turns']}/{a['product_turns']} product-turns flagged usable, mean absolute error {a['usable_mae']:.4f} units, {a['usable_mismatches']} mismatches. Action-preservation assertions passed on {a['action_constraint_checks']} turns. Packaged-agent parity checks in this panel: {data['packaged_parity_actions']} actions.")
        if phase=='shops':
            rows=datasets[phase];modes=['available','static','clock','visible'] if 'available/all' in data['comparisons'] else ['static','clock','visible']
            parts+=['\n| First shop | '+' | '.join(m.title()+' margin change' for m in modes)+' |\n|---|'+'---:|'*len(modes)]
            for s in sorted({r['seed'] for r in rows}):
                shop=next(r['shops'][0] for r in rows if r['seed']==s)
                parts.append('| '+shop+' | '+' | '.join(f"{data['comparisons'][m+'/all']['seed_margin_deltas'][s]:+.1f}" for m in modes)+' |')
    parts+=['\n## Example with two available products\n',
      'In discovery seed 124000 against the raw six-day router, turn 625 offered nine milk units and 24 strawberries. The price-impact scores were 340 for milk and 798 for strawberries, so strawberries moved ahead of milk. Both products actually sold. This is a quantity-and-price-curve decision, beyond moving empty orders: a larger fruit lot can lose more to competing supply than a smaller milk lot. The scores compare hypothetical equal-sized rival lots; they are not realized match-profit gains. Detailed examples are in `results/fresh/adaptive_order/valid_order_examples.json`.\n',
      '\n## Checks and limits\n',
      '- Every scored game completed 720 states with valid statuses; both players\' cash reconciled exactly to initial money plus actual sales minus spending. Per-turn assertions preserve the base action\'s farming orders, market-order multiset and non-sale slots. Opening hashes match their controls. Controlled shops are identical across variants.\n',
      '- 444 ranking-value checks passed against the official market engine and fractional interpolation; two complete smoke games preceded discovery.\n',
      '- Reordering can affect affordability or shed space before a purchase, even when purchase slots are fixed. The full-game engine and ledger, not the ranking approximation, determine outcomes. Natural shops can diverge if changed farm trajectories change the shared RNG; changed-route/shop counts are reported above.\n',
      '- Seeds, not seats or individual turns, are the independent scenarios. These local opponents cover a limited set of behaviors. Forecast errors and ranking assumptions must not be confused with guaranteed knowledge of an opponent\'s future orders.\n',
      '## Reproducibility\n',
      'Research policy: `agents/adaptive_market_order.py` (requires the local engine). Runner: `scripts/research_adaptive_order.py`. Checks: `scripts/verify_adaptive_order.py`. Report and frozen-rule selection: `scripts/report_adaptive_order.py`. Full ledgers, decision logs, source hashes and seeds: `results/fresh/adaptive_order/`. Previous selected agent is preserved.\n']
    if (OUT/'package.json').exists():
        package=json.loads((OUT/'package.json').read_text())
        parts.append(f"\nStandalone candidate: `agents/adaptive_order_candidate.py`, built by `scripts/build_adaptive_order.py`; standard-library-only imports, JSON stdin check passed, {package['parity_actions']} parity actions across two pre-confirmation games. Candidate SHA-256: `{package['sha256']}`.")
    total=sum(summary[p]['games'] for p in datasets)
    parts.append(f'\nCompleted scored games in this report: **{total}**, plus two smoke games and two packaging-parity games when the package artifact is present.')
    (ROOT/'docs/adaptive_market_order.md').write_text('\n'.join(parts),encoding='utf-8')
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps({phase:{k:v for k,v in summary[phase]['comparisons'].items() if k.endswith('/all')} for phase in datasets},indent=2))
    if selection:print('SELECTED',selection['mode'])


if __name__=='__main__':main()
