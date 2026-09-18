# Board value: the day-9 opening comparison

## What value means

V(policy, opponent, state) = mean final cash across the registered synthetic futures. Final cash is starting cash plus successfully executed sale proceeds minus all subsequent purchases and hires. Land, animals, plants, and seeds receive no separate terminal purchase-cost credit.

This is an offline full-state audit: both private inventories are known at the checkpoint. The policies themselves only receive their normal observations. Future seeds are replaced after day 9 and never exposed to policies. A live evaluator would need a belief model for the opponent's hidden inventory.

## Result

The router's low-cash day-9 board produces substantially more terminal cash under common continuation rules as well as under its own policy. Early bank balance therefore gave the wrong impression of the relative positions. The numerical value depends materially on how well the continuation services and reinvests in the farm.

![Projected cash paths](C:/Users/xyygl/Documents/kaggriculture/results/fresh/board_value/cash_paths.png)

## Common continuation comparison

Three recorded day-9 positions x three synthetic future seeds = nine scenarios per row. The common controller uses the same workload-based staffing rule on each farm, capped at ten hired hands. These are conditional scenario means, not calibrated leaderboard forecasts.

| Continuation on both boards | Our final cash, mean | Router final cash, mean | Our scenario range | Router scenario range |
|---|---:|---:|---:|---:|
| Maintain existing assets | 36,152 | 93,411 | 14,576-53,319 | 62,947-117,898 |
| Replant wheat | 48,981 | 101,538 | 25,826-63,341 | 76,281-123,878 |
| Expand land + wheat | 47,814 | 98,999 | 26,275-62,735 | 70,984-118,818 |
| Keep original policies | 34,533 | 159,864 | 24,730-46,860 | 146,546-170,195 |

Native means each board retains its own original controller. It is a useful achievable-policy control, not an identical-controller comparison. The generic controllers do not apply new fertilizer or buy new animals; replanting uses wheat, and expansion buys at most three total quadrants. Native policies retain their original decisions.

## A single current board pair

Root: sheep6-seed20261201-seat0, step 216. The following averages vary only the three synthetic futures, not the root board.

| Mode on both boards | Our value | Router value |
|---|---:|---:|
| Maintain existing assets | 50,570 | 112,606 |
| Replant wheat | 61,961 | 121,614 |
| Keep original policies | 46,640 | 169,775 |

## Where the money comes from: original-policy continuation

These components are observed successful transactions in the engine, not requested order quantities times a quoted price. Each rollout's ledger reconciles exactly to terminal cash. Displayed means are rounded.

| Component | Ours | Router |
|---|---:|---:|
| Starting cash at day 9 | 8,896 | 891 |
| Future sale revenue | 31,127 | 176,670 |
| Future purchases and hiring | -5,490 | -17,697 |
| Final cash | 34,533 | 159,864 |

Future sales include output from newly purchased/replanted assets when the continuation allows them. They are not an intrinsic valuation of the starting assets alone. The maintenance row is the stricter existing-production comparison.

## Our choices against the unchanged router

The opponent uses its original router policy in every row. Select a policy by its mean across scenarios, not by choosing the best action separately after seeing each future.

| Our continuation | Mean final cash | Minimum | Mean cash margin versus router |
|---|---:|---:|---:|
| Maintain existing assets | 30,498 | 14,965 | -129,889 |
| Replant wheat | 45,966 | 28,572 | -110,853 |
| Expand land + wheat | 44,219 | 27,648 | -113,874 |
| Keep original policies | 34,533 | 24,730 | -125,331 |

## Labour and execution sensitivity

Premature losses count plants becoming weeds before their normal last-production/expiry age. They do not count natural expiry; harvests missed after expiry can still waste value and are not fully captured by this counter.

| Common policy | Crew cap | Our mean cash | Router mean cash | Premature crop losses, ours/router, total across 9 runs |
|---|---:|---:|---:|---:|
| Maintain existing assets | 6 | 35,058 | 88,924 | 0 / 72 |
| Maintain existing assets | 10 | 36,152 | 93,411 | 0 / 63 |
| Maintain existing assets | 12 | 37,455 | 93,675 | 0 / 72 |
| Replant wheat | 6 | 51,126 | 101,786 | 0 / 126 |
| Replant wheat | 10 | 48,981 | 101,538 | 0 / 99 |
| Replant wheat | 12 | 48,864 | 100,200 | 0 / 117 |

The common scheduler sometimes fails to service the router's larger farm. Those results are policy-limited outcomes, not proof that the lost plants have no value. The native control checks the size and direction of this bias. None of these controllers establishes an optimal value or an upper bound.

## Validation and scope

- 180 full-season continuations: 144 policy-pair scenarios plus 36 labour-sensitivity scenarios. All reach state 719 and every cash ledger reconciles.
- A separate 419-transition restore test reproduces terminal farms, market, town, inventories, and rewards from a saved full replay.
- Restoring a checkpoint does not change its board/private state; replacing the future seed leaves the root unchanged. The preserved prefix keeps absolute turn numbering intact.
- Native agents are warmed using past observations only, with exact action agreement required over all 216 prior decisions.
- Liquidating shed inventory through the nonlinear price curve was checked against actual engine sales. Carried goods and seeds are not treated as immediately sellable cash.
- Three root positions and three synthetic future seeds are a small sensitivity panel. The ranges are scenario ranges, not confidence intervals; the opponent-policy weights are not learned from the live population.
- The current continuation scheduler covers the crops present in these roots; it explicitly rejects tomato roots. No new fertilizer optimization, opponent inventory inference, or policy learning is included.
- No original opening code, submitted bot, or leaderboard entry was changed by this experiment.

## How to use this evaluator next

For an opening candidate, capture a day-9 state against the same reference opponent. Run the same frozen continuation/scenario panel and compare final cash margins, execution losses, and downside scenarios. Improve the continuation library where native controls reveal systematic undervaluation. Only then use the scalar to select openings or train a faster heuristic.

[Public-source notes](board_value_sources.md) · [Raw panel](../results/fresh/board_value/panel.json) · [Machine-readable values](../results/fresh/board_value/values.json)

## Reproduce

```powershell
.venv/Scripts/python.exe scripts/evaluate_boards.py --stage smoke --workers 3
.venv/Scripts/python.exe scripts/verify_board_value.py
.venv/Scripts/python.exe scripts/evaluate_boards.py --stage panel --workers 3
.venv/Scripts/python.exe scripts/report_board_value.py
```
