# Live mgt_m1: labor scheduling enabled versus disabled

22 September 2026. This is a new live-agent experiment, separate from the earlier supplied-plan study.

Scheduling enabled scores **13 wins, 0 ties, 3 losses** in 16 direct matches against unchanged `agents/mgt_m1.py`, across 8 fresh seeds and both seats. Mean match margin is **+119.25**, with a seed-clustered 95% bootstrap interval of **-32.12 to +238.62**. The separate one-seed engineering pilot is excluded.

| Measure | Scheduling enabled | Scheduling disabled |
|---|---:|---:|
| Mean final cash in direct matches | 105,205.50 | 105,086.25 |
| Match wins | 13 | 3 |

Matched baseline-versus-baseline controls distinguish own profit from opponent effects:

Own profit improves in 14 games, ties in 0, and worsens in 2. A head-to-head loss can coexist with positive own profit improvement because the unscheduled mirror control may already favor the other seat.

| Mean change per treated game | Cash |
|---|---:|
| Own final cash | -402.62 |
| Wages saved | +198.38 |
| Revenue change | -586.06 |
| Other input saving | -14.94 |
| Rival cash change | -521.88 |

Sold quantities differ from the corresponding mirror control in 2/16 treated games. Shop histories differ in 2/16. Sold quantities are an economic check, not a complete production/terminal-state equivalence assertion.

## Method

- Both contestants load the exact same unchanged mgt_m1 source using Kaggle's last-callable loader. Only one has the experimental scheduling adapter enabled. Its opponent remains live and adaptive.
- At day boundaries 3, 5, ..., 27, project 48 hours of the current policy from the player's observation, with a PASS rival, unknown rival inventory empty, current shops held fixed and no new weeds. Save and restore mutable policy state around projection. No recorded future actions or future shops enter the decision.
- Apply the existing wage-only scheduler to that projected plan. Preserve projected sale times and quantities; the forecast sale-timing selector is disabled. Execute only an accepted first day, then resume the adaptive policy. The unchanged parent observes every actual turn to maintain its internal state.
- A rejected or unchanged schedule executes the live parent's original action. Accepted schedules commit a day's projected actions, so this experiment measures the adapter as implemented, including the cost of that commitment.
- Actual games use normal engine shops, weeds and shared market impact. Each seed has two on/off seat assignments and one off/off mirror control. Same seeds do not guarantee identical shops after altered physical actions; actual differences are reported above.
- All games finish with 720 states and both players DONE; successful transaction ledgers reconcile exactly to final cash. Source and action hashes are checked for every game. The first seed's mirror control matches the normal live loader action-for-action, and both treated action streams independently replay through the normal framework.

## Runtime and scope

The scheduler changed 54 of 208 decision days. Fallback counts: `{"none": 194, "projected_input_shortfall": 14}`.

The maximum enabled call took **15.62 seconds**, with **158 calls over one second** under the local multi-process run. The evaluator does not enforce the competition timeout. This is an offline live-policy ablation, **not a submission-ready improvement**. The agent and submission files are unchanged. Runtime must be reduced and checked under the competition limit before promotion. Results against itself do not establish strength against V56 or original UMG tapes.

## Losing-world diagnostic

Seed 226226 changed the last two shops from Smoothie/Yarn to Bakery/Ice Cream in the natural panel. A post-hoc rerun forces the mirror control's original shop history in the evaluator while keeping scheduling decisions observation-only. This diagnostic is excluded from the primary statistics.

Even with shops fixed, enabled scheduling changes own cash by -235 in seat 0 and -419 in seat 1. Direct margins are -228 and -488. Sold wheat falls by 15 and 19 units respectively. Thus the live adapter has a real regression beyond the altered shop draw; projected fixed-plan equivalence does not ensure equivalence after the adaptive policy resumes.

Recommendation: **keep scheduling disabled in the retained live agent**. The observed mean margin is positive, but its interval crosses zero, this regression remains, and timing exceeds the competition limit. Preserve the scheduler as a research candidate.

Diagnostic artifacts: [fixed-shop reruns](../results/fresh/labour_profit/live_m1_wage_shop_diagnostic/). Reproduce with `scripts/diagnose_live_labour_shops.py`.

## Per-seed direct margin

| Seed | Enabled in seat 0 | Enabled in seat 1 | Average |
|---|---:|---:|---:|
| 226221 | +94 | +94 | +94.0 |
| 226222 | +192 | +352 | +272.0 |
| 226223 | +94 | +94 | +94.0 |
| 226224 | +382 | -194 | +94.0 |
| 226225 | +361 | +361 | +361.0 |
| 226226 | -227 | -495 | -361.0 |
| 226227 | +217 | +217 | +217.0 |
| 226228 | +183 | +183 | +183.0 |

## Reproduction

```powershell
.venv/Scripts/python.exe scripts/compare_live_labour.py --seeds 8 --seed-base 226221 --workers 3 --tag live_m1_wage_confirmation_v1
.venv/Scripts/python.exe scripts/check_live_labour.py --tag live_m1_wage_confirmation_v1
.venv/Scripts/python.exe scripts/report_live_labour.py --tag live_m1_wage_confirmation_v1
```

Frozen manifest, individual results, compressed executable action pairs, summary and verification: [experiment artifacts](../results/fresh/labour_profit/live_m1_wage_confirmation_v1/).
