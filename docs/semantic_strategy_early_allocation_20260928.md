# Early paid backlog and labor diagnosis

Read-only accounting of complete v4 and v5 development recordings finds an
execution bottleneck after inputs have been paid. The block policy improves
planting, but the remaining bottleneck mixes busy workers with several workers
whose dispatch does not pick up available work. No new games or qualification
observations were used.

## D6–10, eight games each

| Measure | v4 modern daily policy | v5 block policy |
|---|---:|---:|
| Successful crop establishments | 324 | 363 |
| Unfinished crop requests | 140 | 134 |
| Unfinished crops with seeds already held | 121 | 113 |
| Unfinished animal placements | 51 | 61 |
| Unfinished placements with animals already bought | 32 | 40 |
| Days with unbought seeds and held animals | 4 | 4 |

These are sums of daily outstanding jobs, so carryover can count again on the
following day. Actual completion uses observed planted/placed-day identities.
All40 daily animal-order totals and all40 seed-order totals in each group match
successful purchases independently derived from ledger spending. Thus order
rejection does not explain these seed and animal backlogs.

The frozen executor spends on hires, feed, land, animals, then seeds. In tier
mode, it includes animal purchases for structures not yet built. The source is
`runtime/agents/mgt_lead_kb115lt.py:3547–3665` under this study. This can crowd out
seeds: in four days per group, held-animal value exceeds the cost of missing
seeds. But most unfinished seeds were already purchased, so changing buying
order alone cannot explain most of the problem.

## D10 expansion

Both policies unlock their fourth quadrant at hour12 or13 in every game. v4
plans164 new crops and establishes105; v5 plans210 and establishes149. All59 v4
and all61 v5 unfinished D10 crop jobs have paid seeds at the next dawn.

v4 uses11–14 hands, with all target hires available by hour2 in six games and
the last hire delayed to hour12 in two. v5 uses12 or13 hands and has all of them
available by hour2. Its dawn herd is125 animals across eight farms, versus123
for v4; the count model has not yet substantially reduced early service burden.

| Actions after land unlock | v4 | v5 | Native DSM oracle8 |
|---|---:|---:|---:|
| All worker/farmer actions | 1,135 | 1,216 | 960 |
| Movement | 505 | 485 | 445 |
| Feed, care, collect fertilizer | 181 | 188 | 78 |
| Plant | 75 | 114 | 119 |
| Water | 193 | 229 | 249 |
| PASS | 51 | 88 | 0 |

Native oracle8 are different source worlds, not matched counterfactuals. They
use11–13 hands, median12, and unlock even later at hour14 or15. All native hires
are available by hour2. Native actual D10 planting is133 total; the comparison
shows a feasible reference workload, not a causal estimate of a staffing change.

Only seven v4 PASS actions occur before hour23. In v5,43 do, with33 concentrated
in two games. The richer v5 hourly private logs show a hand waiting at the shed
through hours12–22 in one case, despite bought wheat/carrot seeds and ample cash
from hour13. Another hand in a different case waits hours15–21 while wheat and
tomato seeds are held. These observations make a general labor-shortage diagnosis
incomplete. They also mean extra hands cannot be assumed to fix every case.

At v4 unlock,13–21 plants,1–6 builds and1–6 placements remain per world. Workers'
median distance to the newly unlocked quadrant is2–3 moves. Movement and spawn
arithmetic was independently reconstructed from actions and actual hand-count
changes; it exactly matches192 native hourly positions and all192 v5 D10 hourly
positions. No game simulation was run for this reconstruction. All D10 unit
commands in these v4/v5 recordings have zero reported no-effect operations.

## Optional extra-hand ablation

`scripts/semantic_strategy_labor_20260928.py` and a conditional block-policy hook
implement `early_hands_bonus`, **OFF by default**. Hard limits are days6–10, at
most one extra hand, and the existing14-hand cap. It applies after the baseline
forecast is constructed and changes only each day's hands field. Crop, animal,
retirement quantities and the committed block budget remain identical.

Diagnostics show incremental Fibonacci wages and the current-cash gap against
capital plus wages. This gap excludes feed and prospective sales; it is not a
complete funding forecast. Future quantity admission deliberately retains the
baseline cash forecast until the next actual daily replan, so the ablation does
not indirectly become a different production policy.

On v5's saved proposals it adds one hand on all40 early mornings, costing$4,270
in aggregate, or$533.75 per game. D10 accounts for$2,296 of that total. Actual
morning cash is below even the additional wage in11 of40 observations. Because
the executor funds hires before buying land, extra hires can delay expansion;
there is no claim that these extra costs are covered or profitable. Four new
tests pass, and disabled behavior still matches frozen v6 on384 saved decisions.
The flag has not been enabled, frozen into a candidate, or played.

## Artifacts

- `early_allocation_v4_diagnostic.json` and `early_allocation_v5_diagnostic.json`
- `d10_labor_v4_diagnostic.json` and `d10_labor_v5_diagnostic.json`
- `early_allocation_v4_v5_comparison.json`
- `early_hands_prototype_audit.json`, with exact source hashes and per-day costs
- `oracle_diagnostics/d6_exact_vs_retile_v3/native_d10_labor_audit.json`

All artifacts are under `results/fresh/semantic_strategy_20260928/`. Reproducers
are `scripts/check_semantic_early_allocation_20260928.py` and
`scripts/check_semantic_d10_labor_20260928.py`; both accept candidate and label
arguments. Paired development seeds may have naturally diverging later shops,
so these physical comparisons are descriptive rather than isolated profit gains.
