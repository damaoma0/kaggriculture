"""Report the live labor scheduling ablation without pooling its pilot."""
import argparse
import json
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', default='live_m1_wage_confirmation_v1')
    args = parser.parse_args()
    folder = ROOT / 'results/fresh/labour_profit' / args.tag
    result = json.loads((folder / 'summary.json').read_text())
    verification = json.loads((folder / 'verification.json').read_text())
    assert verification['passed']
    rows = [json.loads(p.read_text()) for p in folder.glob('[0-9]*.json')]
    controls = {r['seed']: r for r in rows if r['treatment'] == -1}
    treated = [r for r in rows if r['treatment'] >= 0]
    wages, revenues, other, rival, quantities = [], [], [], [], []
    for r in treated:
        s = r['treatment']
        b = controls[r['seed']]
        before, after = b['economics'][s], r['economics'][s]
        wage = before['spend'].get('HIRE', 0) - after['spend'].get('HIRE', 0)
        revenue = sum(after['revenue'].values()) - sum(before['revenue'].values())
        rest = sum(before['spend'].values()) - sum(after['spend'].values()) - wage
        assert wage + revenue + rest == r['cash'][s] - b['cash'][s]
        wages.append(wage)
        revenues.append(revenue)
        other.append(rest)
        rival.append(r['cash'][1-s] - b['cash'][1-s])
        quantities.append(before['sold_units'] != after['sold_units'])
    result.update(mean_wage_saving=st.mean(wages), mean_revenue_change=st.mean(revenues),
                  mean_other_input_saving=st.mean(other), mean_rival_cash_change=st.mean(rival),
                  games_with_changed_sold_quantities=sum(quantities))
    gains = [r['cash'][r['treatment']] - controls[r['seed']]['cash'][r['treatment']] for r in treated]
    result.update(own_profit_improved=sum(g > 0 for g in gains), own_profit_unchanged=sum(g == 0 for g in gains),
                  own_profit_worsened=sum(g < 0 for g in gains))
    (folder / 'analysis.json').write_text(json.dumps(result, indent=2))
    per_seed = []
    for seed in sorted(controls):
        rr = sorted([r for r in treated if r['seed'] == seed], key=lambda r: r['treatment'])
        margins = [r['cash'][r['treatment']] - r['cash'][1-r['treatment']] for r in rr]
        per_seed.append(f'| {seed} | {margins[0]:+.0f} | {margins[1]:+.0f} | {st.mean(margins):+.1f} |')
    diagnostic = ROOT / 'results/fresh/labour_profit/live_m1_wage_shop_diagnostic/summary.json'
    diagnostic_text = ''
    if diagnostic.exists():
        d = json.loads(diagnostic.read_text())
        diagnostic_text = f'''## Losing-world diagnostic

Seed {d['seed']} changed the last two shops from Smoothie/Yarn to Bakery/Ice Cream in the natural panel. A post-hoc rerun forces the mirror control's original shop history in the evaluator while keeping scheduling decisions observation-only. This diagnostic is excluded from the primary statistics.

Even with shops fixed, enabled scheduling changes own cash by {d['treated'][0]['own_gain']:+.0f} in seat 0 and {d['treated'][1]['own_gain']:+.0f} in seat 1. Direct margins are {d['treated'][0]['margin']:+.0f} and {d['treated'][1]['margin']:+.0f}. Sold wheat falls by 15 and 19 units respectively. Thus the live adapter has a real regression beyond the altered shop draw; projected fixed-plan equivalence does not ensure equivalence after the adaptive policy resumes.

Recommendation: **keep scheduling disabled in the retained live agent**. The observed mean margin is positive, but its interval crosses zero, this regression remains, and timing exceeds the competition limit. Preserve the scheduler as a research candidate.

Diagnostic artifacts: [fixed-shop reruns](../results/fresh/labour_profit/live_m1_wage_shop_diagnostic/). Reproduce with `scripts/diagnose_live_labour_shops.py`.

'''
    text = f'''# Live mgt_m1: labor scheduling enabled versus disabled

22 September 2026. This is a new live-agent experiment, separate from the earlier supplied-plan study.

Scheduling enabled scores **{result['wins']} wins, {result['ties']} ties, {result['losses']} losses** in {result['games']} direct matches against unchanged `agents/mgt_m1.py`, across {result['seeds']} fresh seeds and both seats. Mean match margin is **{result['mean_margin']:+.2f}**, with a seed-clustered 95% bootstrap interval of **{result['paired_seed_ci95'][0]:+.2f} to {result['paired_seed_ci95'][1]:+.2f}**. The separate one-seed engineering pilot is excluded.

| Measure | Scheduling enabled | Scheduling disabled |
|---|---:|---:|
| Mean final cash in direct matches | {result['mean_enabled_cash']:,.2f} | {result['mean_disabled_cash']:,.2f} |
| Match wins | {result['wins']} | {result['losses']} |

Matched baseline-versus-baseline controls distinguish own profit from opponent effects:

Own profit improves in {result['own_profit_improved']} games, ties in {result['own_profit_unchanged']}, and worsens in {result['own_profit_worsened']}. A head-to-head loss can coexist with positive own profit improvement because the unscheduled mirror control may already favor the other seat.

| Mean change per treated game | Cash |
|---|---:|
| Own final cash | {result['mean_own_gain_vs_control']:+.2f} |
| Wages saved | {result['mean_wage_saving']:+.2f} |
| Revenue change | {result['mean_revenue_change']:+.2f} |
| Other input saving | {result['mean_other_input_saving']:+.2f} |
| Rival cash change | {result['mean_rival_cash_change']:+.2f} |

Sold quantities differ from the corresponding mirror control in {result['games_with_changed_sold_quantities']}/{result['games']} treated games. Shop histories differ in {result['changed_shop_histories']}/{result['games']}. Sold quantities are an economic check, not a complete production/terminal-state equivalence assertion.

## Method

- Both contestants load the exact same unchanged mgt_m1 source using Kaggle's last-callable loader. Only one has the experimental scheduling adapter enabled. Its opponent remains live and adaptive.
- At day boundaries 3, 5, ..., 27, project 48 hours of the current policy from the player's observation, with a PASS rival, unknown rival inventory empty, current shops held fixed and no new weeds. Save and restore mutable policy state around projection. No recorded future actions or future shops enter the decision.
- Apply the existing wage-only scheduler to that projected plan. Preserve projected sale times and quantities; the forecast sale-timing selector is disabled. Execute only an accepted first day, then resume the adaptive policy. The unchanged parent observes every actual turn to maintain its internal state.
- A rejected or unchanged schedule executes the live parent's original action. Accepted schedules commit a day's projected actions, so this experiment measures the adapter as implemented, including the cost of that commitment.
- Actual games use normal engine shops, weeds and shared market impact. Each seed has two on/off seat assignments and one off/off mirror control. Same seeds do not guarantee identical shops after altered physical actions; actual differences are reported above.
- All games finish with 720 states and both players DONE; successful transaction ledgers reconcile exactly to final cash. Source and action hashes are checked for every game. The first seed's mirror control matches the normal live loader action-for-action, and both treated action streams independently replay through the normal framework.

## Runtime and scope

The scheduler changed {result['changed_days']} of {result['decisions']} decision days. Fallback counts: `{json.dumps(result['fallbacks'], sort_keys=True)}`.

The maximum enabled call took **{result['max_enabled_seconds']:.2f} seconds**, with **{result['enabled_calls_over_one_second']} calls over one second** under the local multi-process run. The evaluator does not enforce the competition timeout. This is an offline live-policy ablation, **not a submission-ready improvement**. The agent and submission files are unchanged. Runtime must be reduced and checked under the competition limit before promotion. Results against itself do not establish strength against V56 or original UMG tapes.

{diagnostic_text}## Per-seed direct margin

| Seed | Enabled in seat 0 | Enabled in seat 1 | Average |
|---|---:|---:|---:|
{chr(10).join(per_seed)}

## Reproduction

```powershell
.venv/Scripts/python.exe scripts/compare_live_labour.py --seeds 8 --seed-base 226221 --workers 3 --tag {args.tag}
.venv/Scripts/python.exe scripts/check_live_labour.py --tag {args.tag}
.venv/Scripts/python.exe scripts/report_live_labour.py --tag {args.tag}
```

Frozen manifest, individual results, compressed executable action pairs, summary and verification: [experiment artifacts](../results/fresh/labour_profit/{args.tag}/).
'''
    (ROOT / 'docs/live_labour_comparison.md').write_text(text, encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
