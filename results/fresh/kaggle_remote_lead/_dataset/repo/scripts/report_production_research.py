"""Account for the completed four-stage production-policy experiment."""
from collections import Counter
from statistics import mean
from hashlib import sha256
import json
from audit_router_advantage import ROOT,OUT
from market_corpus import PATHS

def read(name):return json.loads((OUT/name).read_text())

def compare(rows,baseline):
    bases={(r['seed'],r['seat'],r['opponent']):r for r in rows if r['mode']==baseline}
    result={}
    for mode in sorted({r['mode'] for r in rows}):
        subset=[r for r in rows if r['mode']==mode];details=[]
        for r in subset:
            b=bases[r['seed'],r['seat'],r['opponent']]
            details.append({'seed':r['seed'],'seat':r['seat'],'opponent':r['opponent'],
              'cash_delta':r['cash']-b['cash'],'relative_delta':100*(r['cash']/b['cash']-1),
              'margin_delta':r['cash']-r['opponent_cash']-b['cash']+b['opponent_cash'],
              'shops_changed':r.get('shops')!=b.get('shops'),'branches_changed':r.get('branches')!=b.get('branches')})
        result[mode]={'games':len(subset),'mean_cash_delta':mean(x['cash_delta'] for x in details),
          'mean_relative_delta':mean(x['relative_delta'] for x in details),'mean_margin_delta':mean(x['margin_delta'] for x in details),
          'better':sum(x['cash_delta']>0 for x in details),'same':sum(x['cash_delta']==0 for x in details),
          'worse':sum(x['cash_delta']<0 for x in details),'worst':min(x['cash_delta'] for x in details),'best':max(x['cash_delta'] for x in details),
          'wins':sum(r['cash']>r['opponent_cash'] for r in subset),'ties':sum(r['cash']==r['opponent_cash'] for r in subset),
          'losses':sum(r['cash']<r['opponent_cash'] for r in subset),
          'placement_failures':sum(r.get('placement_failed',False) for r in subset),
          'decisions':sum(r.get('decision') is not None for r in subset),
          'species_changes':sum(r.get('decision') is not None and r['decision']['original']!=r['decision']['selected'] for r in subset),
          'shop_changes':sum(x['shops_changed'] for x in details),'route_changes':sum(x['branches_changed'] for x in details),
          'max_action_seconds':max(r['max_action_seconds'] for r in subset),
          'seed_cash_deltas':{str(s):mean(x['cash_delta'] for x in details if x['seed']==s) for s in sorted({x['seed'] for x in details})},
          'opponents':{o:{'cash_delta':mean(x['cash_delta'] for x in details if x['opponent']==o),
            'margin_delta':mean(x['margin_delta'] for x in details if x['opponent']==o),
            'wins':sum(r['cash']>r['opponent_cash'] for r in subset if r['opponent']==o),
            'ties':sum(r['cash']==r['opponent_cash'] for r in subset if r['opponent']==o),
            'losses':sum(r['cash']<r['opponent_cash'] for r in subset if r['opponent']==o)} for o in sorted({x['opponent'] for x in details})},
          'details':details}
    return result

def main():
    audit=read('advantage_summary.json');selection=read('selection.json')
    natural=read('test_results.json');controlled=read('shops_results.json')
    assert len(natural)==120 and len(controlled)==64
    tests=compare(natural,'raw');incremental=compare(natural,'original');shops=compare(controlled,'original')
    assert shops['sheep']['shop_changes']==0
    summary={'audit':audit,'development':selection,'natural_vs_raw':tests,'natural_vs_adapter':incremental,'controlled_shops':shops}
    confirmation=read('confirmation_results.json') if (OUT/'confirmation_results.json').exists() else None
    confirmed=compare(confirmation,'raw') if confirmation else None
    if confirmed:summary['confirmation']=confirmed
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2))
    labels={'raw':'Six-day router','original':'Router + liquidation adapter','current':'DP, current prices','dp':'DP, market-flow forecast','sheep':'Sheep-biased pasture + feed DP'}
    lines=['# Production choices: router audit, valuation, DP, and held-out games','',
      'Completed 2026-09-16. This study executes all four stages of the approved plan. No leaderboard submission was made.', '',
      '## 1. Where the stronger router earns its advantage','',
      f"Eight audited matches (four new seeds, both seats) show a mean six-day-router advantage of **{audit['mean_gap']:,.0f} cash** over v31. All revenue and spending comes from successful official-engine transactions.", '',
      '| Product | Extra revenue | Quantity component | Realized-price component |', '|---|---:|---:|---:|']
    for p in sorted(audit['revenue_gap'],key=lambda p:-audit['revenue_gap'][p]):
        lines.append(f"| {p} | {audit['revenue_gap'][p]:+,.0f} | {audit['volume_component'][p]:+,.0f} | {audit['price_component'][p]:+,.0f} |")
    lines += ['', 'The quantity/price split uses a symmetric decomposition: quantity difference times mean realized price, plus price difference times mean quantity. It sums exactly to the revenue gap, but is descriptive, not a causal counterfactual.', '',
      f"Milk and wool account for **{audit['revenue_gap']['MILK']+audit['revenue_gap']['WOOL']:,.0f}** extra revenue. Net extra spending is **{sum(audit['spend_gap'].values()):,.0f}**; additional wheat purchases alone cost **{audit['spend_gap']['BUY_PRODUCT:WHEAT']:,.0f}**. Thus, gross wheat sales cannot be treated as extra farm production or profit. This led us to investigate pasture investments.", '',
      'Mean cash advantage develops over time: '+', '.join(f"turn {t}: {v:+,.0f}" for t,v in audit['cash_gap_at_turn'].items())+'.', '',
      '## 2. Production-choice continuations','',
      'We test one unambiguous single cow/sheep purchase during turns 144-288, with no other pasture animal in transit. Choices use the same existing movement and service routes. Candidate executions share identical action prefixes up to the decision; hashes and decision steps are checked. The router can subsequently choose different six-day routes in response to changed observations.', '',
      'Changing animal type changes the product harvested. A common adapter sells accessible milk/wool left over from the route orders. The adapter-only control retains the original animal and feeding actions; raw-router controls identify any effect from the adapter itself.', '',
      'The pilot ran 24 full continuations on four development seeds, both seats, against old v31. Two sheep purchases failed because preceding hires consumed their cash. Those failures are retained in the pilot data. The revised policy reserves funds for other requested spending and falls back to the original animal when the substitution is unaffordable.', '',
      'A second development round ran 32 games on those same development seeds. This is iterative development, not a held-out result. It also adds the price effect of the new animal on forecast revenue from our existing herd, and holds the seven-day inventory forecast constant beyond its validated horizon.', '',
      f"The revised analytical values correctly ranked **{selection['ranking_agreement']}/{selection['comparable_pairs']}** non-tied, affordable cow-versus-sheep comparisons. Seats are correlated: these are six comparisons on three seeds. The sheep-biased policy's development mean was {selection['development_means']['sheep']:,.0f}, versus {selection['development_means']['original']:,.0f} for the adapter control. This development gain was not used as proof of generalization.", '',
      '## 3. Small finite-season DP','',
      'The DP tracks day, held produce, accumulated care bonus, consecutive missed feeds, and the additional market inventory generated by the investment. It chooses whether to feed or allow abandonment, values harvests and fertilizer, charges the opportunity cost of wheat, and subtracts purchase cost. It compares cow, sheep and skipping the investment.', '',
      'Growth, care accumulation, yield caps and escape timing follow the official engine. Existing labor is treated as committed because the physical route and hiring schedule are reused. The selected feed plan is executed only at service visits already present in that route. The sheep comparator uses the same feed DP with a fixed species preference, so it is not a pure species-only ablation.', '',
      '**Model limits:** the current route is frozen when forecasting future service visits, but actual route selection can change every six days. Existing-herd production and delivery timing are approximations. The model does not predict opponent adaptations, full-farm liquidity effects, all storage losses or policy-induced changes in future shop draws. Mathematical optimality within this model does not imply optimal game play.', '',
      'Two concrete forecast limitations matter here. The earlier forecast benchmark began at turn 216, while many investment decisions occur at turn 169. Also, its visible-animal rate uses two units per production interval: a mature cow fed and cared for daily can produce three units per two-day interval, and a sheep four per three-day interval because care accumulates. Thus the production planner applies a rough supply forecast outside part of its evaluated time range and can understate cared-herd supply. These are plausible sources of decision error, not an isolated causal explanation for every result.', '',
      'Verification: the DP matches exhaustive feed schedules in eight scenarios using the official animal-refresh function, including both animal types, high/low inventory, and presence/absence of care. The implementation uses only public history, our private state, and embedded route code; it receives no future seed, shops, observations or opponent actions.', '',
      '## 4. Frozen full-policy evaluation','',
      'Natural-game test: six unseen seeds (112000-112005), both seats, and two opponents not used in development: sixday and pasture. Five policies produce **120 full games**. The fixed sheep preference was selected before these games. No policy parameters were changed after starting this test.', '',
      '| Policy | Mean cash vs raw router | Mean relative change | Better / same / worse | Worst / best | Species changes |',
      '|---|---:|---:|---:|---:|---:|']
    for m in ('raw','original','current','dp','sheep'):
        r=tests[m];lines.append(f"| {labels[m]} | {r['mean_cash_delta']:+,.0f} | {r['mean_relative_delta']:+.2f}% | {r['better']} / {r['same']} / {r['worse']} | {r['worst']:+,.0f} / {r['best']:+,.0f} | {r['species_changes']}/{r['games']} |")
    lines += ['', 'No revised production policy changed animal species in these 24 natural test games. The affordability guard and existing router choices prevented substitutions. Therefore this test does not establish the value of changing production: the flow-DP and sheep candidates exactly matched the adapter-only control in final cash. This coverage limitation is explicit, not counted as successful production optimization.', '',
      'Every policy has 24 games. Cash comparisons use matching seed, seat and opponent; they are not 24 independent samples. Competition performance also depends on the opponent’s cash:', '',
      '| Policy | Opponent | Wins / ties / losses | Mean cash change vs raw | Mean match-margin change vs raw |',
      '|---|---|---:|---:|---:|']
    for m in ('raw','original','current','dp','sheep'):
        for o,r in tests[m]['opponents'].items():lines.append(f"| {labels[m]} | {o} | {r['wins']} / {r['ties']} / {r['losses']} | {r['cash_delta']:+,.0f} | {r['margin_delta']:+,.0f} |")
    lines += ['', '### All first-shop types, with matched future shops','',
      'The game couples shop draws to weed randomness, so identical seeds need not give identical shops after a policy change. A separate robustness test fixes the shop sequence across compared policies while retaining natural farm/weed evolution. Its first shop is stratified across all eight shop types; the remaining shops are independently sampled with replacement. Only already revealed shops are visible to the policies.', '',
      'Eight new seeds (113000-113007), both seats, two opponents and two policies give **64 games**. This is a controlled environment diagnostic, separate from the official-rule natural-game test.', '',
      '| Comparison against adapter control | Mean cash change | Better / same / worse | Worst / best |', '|---|---:|---:|---:|']
    r=shops['sheep'];lines.append(f"| Sheep-biased pasture + feed DP | {r['mean_cash_delta']:+,.0f} | {r['better']} / {r['same']} / {r['worse']} | {r['worst']:+,.0f} / {r['best']:+,.0f} |")
    lines += ['', '| First shop | Mean cash change |', '|---|---:|']
    for seed in sorted({r['seed'] for r in controlled}):
        first=next(r['shops'][0] for r in controlled if r['seed']==seed)
        lines.append(f"| {first} | {shops['sheep']['seed_cash_deltas'][str(seed)]:+,.0f} |")
    lines += ['', f"The controlled test does exercise species changes: {shops['sheep']['species_changes']}/32 games. It raises mean cash by {shops['sheep']['mean_cash_delta']:,.0f}, but mean match margin improves by only {shops['sheep']['mean_margin_delta']:.1f}; against sixday it wins {shops['sheep']['opponents']['sixday']['wins']}/16, versus {shops['original']['opponents']['sixday']['wins']}/16 for the adapter control. More farm income alone does not identify the stronger competitive policy.", '',
      '### Validation and limitations','',
      '- The eight audit games and all pilot, development, natural-test and controlled-shop games reach 720 states without an engine error status. Cash reconciles with actual sales, purchases, hires and land costs.',
      f"- Revised natural test: {sum(r.get('placement_failed',False) for r in natural)} placement failures. Controlled-shop test: {sum(r.get('placement_failed',False) for r in controlled)} placement failures.",
      f"- Maximum observed action time in the natural test: {max(r['max_action_seconds'] for r in natural):.3f} seconds on this machine. This is a local callable measurement, not a Kaggle sandbox runtime guarantee.",
      f"- Relative to raw, the sheep candidate changes the revealed shop sequence in {tests['sheep']['shop_changes']}/24 natural games and later route selections in {tests['sheep']['route_changes']}/24. These downstream effects are included in measured outcomes, not attributed solely to the new animal's direct yield.",
      '- Six natural test seeds and one controlled sequence per first-shop type are limited samples. Opponent policies can share route ancestry. No leaderboard-strength claim follows from these local experiments.', '',
      '## Competitive sales adapter and fresh confirmation','',
      'The natural-game test isolated an unexpected benefit from the milk/wool sales adapter: it won 12/12 against sixday and 12/12 against pasture, despite slightly lower average own cash. This is a relative-payoff effect in the shared market. The investment DP was not needed for those results.', '',
      'We therefore packaged only the six-day router plus this adapter as `agents/production_candidate.py`, with deterministic physical-action projection extracted from the installed official engine. It is self-contained and imports only Python standard-library modules. The investment and forecasting modules are absent. The [original public router](https://www.kaggle.com/code/thomastschinkel/kaggriculture-93-8-win-rate-public-state-router) and official engine remain the attributed sources; this is an adapter around their code, not an independently developed router.', '']
    if confirmed:
        lines += ['After choosing this simpler candidate, a separate frozen confirmation used eight new seeds (114000-114007), both seats, both opponents, raw-router controls and the packaged adapter: **64 additional full games**.', '',
          '| Opponent | Adapter wins / ties / losses | Raw-router wins / ties / losses | Own-cash change | Match-margin change |', '|---|---:|---:|---:|---:|']
        for o,r in confirmed['adapter']['opponents'].items():
            b=confirmed['raw']['opponents'][o]
            lines.append(f"| {o} | {r['wins']} / {r['ties']} / {r['losses']} | {b['wins']} / {b['ties']} / {b['losses']} | {r['cash_delta']:+,.1f} | {r['margin_delta']:+,.1f} |")
        lines += ['',f"Packaged-policy parity: {sum(r['parity_actions'] for r in confirmation):,} actions exactly match the research adapter across four full games. All confirmation games finish without an engine error and reconcile cash. Maximum measured adapter action time is {confirmed['adapter']['max_action_seconds']:.3f} seconds. The loader's final callable is verified as `agent`; only standard-library imports are present.", '']
    else:lines += ['Fresh confirmation is still pending; this report will be regenerated when it completes.', '']
    lines += ['## Decision','',
      'The confirmed adapter is frozen as **`agents/production_selected.py`**, the selected local competitive candidate. It uses the public six-day router plus the milk/wool liquidation adapter; it contains no investment DP. Its content hash matches the confirmed candidate, and its standalone JSON input/output entry point has been verified. The older midgame selection remains a historical experiment. No Kaggle submission was made.', '',
      'Retain the production DP as a research prototype. It solved the small mathematical problem correctly, but its investment rankings and execution coverage do not establish a competitive production upgrade. The simpler sales adapter is evaluated separately on match outcomes, with absolute cash changes reported alongside them.', '',
      'See `summary.json` for all seed-level results, comparisons against the adapter control, and match margins. Candidate promotion depends on unseen-game performance against the stronger reference, not development gains or the correctness of the DP recurrence.', '',
      'The main modeling lesson is to evaluate an investment as a change to both farms and the shared market. Better unconditional price forecasts did not automatically rank production decisions correctly. Future model work should first correct cared-herd maturation/supply forecasts, then use paired full-game continuations to learn changes in match margin, including route and opponent responses. Public-state production rates can inform this, but cannot substitute for testing the decisions they produce.', '',
      '## Files and reproduction','',
      '- Audit: `scripts/audit_router_advantage.py`.',
      '- Policies: `agents/pasture_investment_v1.py` (pilot snapshot) and `agents/pasture_investment_dp.py` (revised experiment). These are research modules with workspace/engine dependencies.',
      '- Experiment: `scripts/research_pasture_dp.py --phase train|validate|test|shops`; manifests freeze seeds, sources and policy hashes. Development has its own preserved pilot policy.',
      '- Selection: `scripts/select_pasture_policy.py`; verification: `scripts/verify_pasture_dp.py`; report: `scripts/report_production_research.py`.',
      '- Results and manifests: `results/fresh/production_research/`. The formal study contains 248 games: 8 audit + 24 pilot + 32 revised development + 120 natural test + 64 controlled-shop games. Additional smoke checks are separate.', '']
    if confirmed:lines += ['The adapter confirmation adds 64 games, bringing the formal recorded total to **312**. Build with `scripts/build_production_selected.py`; confirm with `scripts/confirm_production_adapter.py`; freeze with `scripts/select_production_adapter.py`. Candidate/source hashes are saved in `candidate_build.json`, `confirmation_manifest.json` and `selected_policy.json`. No submission is performed by these scripts.', '']
    (ROOT/'docs/production_research.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({'natural':{m:{k:v for k,v in r.items() if k not in ('details','seed_cash_deltas','opponents')} for m,r in tests.items()},'controlled':{k:v for k,v in shops['sheep'].items() if k not in ('details','seed_cash_deltas')}},indent=2))

if __name__=='__main__':main()
