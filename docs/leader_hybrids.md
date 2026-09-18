# Leader-inspired opening hybrids on V45

Best discovery variant: **berries**. Selected after fresh confirmation: **baseline**. Confirmation margin change: **-2009.3**; own cash: **-145.3**. Positive seed averages: 1/8.

## What was combined

All candidates are standalone derivatives of the submitted V45 event-forecast agent (submission 56280048). We transfer leader-inspired investment choices onto V45's existing coordinates and worker routes. This is not a replay splice or a reconstruction of the rank-1 agent.

- **berries:** buy strawberry seeds with available cash from turn 70, then replace eligible day-4 wheat replants at four sites that V45 will otherwise convert to strawberries on day 6. Existing seedlings are protected from incompatible early DIG/PLANT/HARVEST commands. Native later seed purchases are reduced to avoid buying the same four seeds twice.
- **herd:** change the third cow purchase to a sheep and omit the fourth cow. Purchase, pickup and placement are changed consistently; all movement and service routes remain native. Extra wool is offered at existing native wool-sale slots.
- **both:** combine those changes, purchasing the planned sheep before spending on early strawberry seeds.

Important scope: the first-day V45 board and its 12 early melons remain. We do not reproduce the leader's first-day extra sheep, staged six-melon opening, or 7-8 strawberries at six days. Those require a different startup schedule and compatible continuation. A failure here does not disprove that full opening.

## Frozen evaluation

Three frozen mechanism hybrids on submitted V45 event candidate. Eight forced first shops, both seats, two rivals for discovery. Best mean margin advances to eight fresh natural-frequency shop seeds, both seats, three rivals. No prefix splice or leader source reconstruction.

Discovery: 128 games, one seed per first-shop type, both seats, two rivals and four policies. Confirmation: 96 games, eight fresh seeds with natural-frequency hidden shop draws, both seats, three rivals, baseline plus the discovery winner. The shop-stratified screen is a coverage check, not enough evidence for a learned first-shop selection rule. No tuning after the discovery sources were frozen.

Eight earlier full-game smoke checks were used for implementation: the first four exposed that seed spending could prevent the intended sheep purchase. Purchase sequencing was corrected before freezing; the final four tested the revised code. They are not counted as independent performance evidence.

| Phase / candidate / rival | Margin gain | Own cash gain | Candidate wins | Baseline wins |
|---|---:|---:|---:|---:|
| screen/berries/all | -3827.9 | +679.9 | 12/32 | 31/32 |
| screen/herd/all | -5644.7 | -887.3 | 12/32 | 31/32 |
| screen/both/all | -5670.5 | -883.9 | 12/32 | 31/32 |
| confirmation/berries/all | -2009.3 | -145.3 | 29/48 | 46/48 |
| confirmation/berries/farmingv5 | +431.6 | +81.0 | 16/16 | 15/16 |
| confirmation/berries/twocoins | -3601.6 | -467.1 | 12/16 | 16/16 |
| confirmation/berries/v45 | -2857.9 | -49.8 | 1/16 | 15/16 |

## First-shop screen

| First shop | Berries | Herd | Both |
|---|---:|---:|---:|
| BAKERY | -2443.5 | -3636.5 | -3659.8 |
| BRUNCH_SPOT | -7512.5 | -13039.8 | -13309.0 |
| FARMERS_MARKET | -2518.5 | -3498.0 | -3643.5 |
| ICE_CREAM_SHOP | -2365.5 | -447.0 | -513.5 |
| PET_CAFE | -2723.5 | -1930.5 | -1763.0 |
| PIZZA_SHOP | -7124.0 | -13366.0 | -13504.5 |
| SMOOTHIE_SHOP | -3896.0 | -5537.5 | -5409.5 |
| YARN_STORE | -2040.0 | -3702.0 | -3561.0 |

## Six-day board checks

| Phase / policy | Cash | Cows | Sheep | Strawberries planted before native day | Early plants lost before handoff |
|---|---:|---:|---:|---:|---:|
| screen/baseline | 805.4 | 4.00 | 2.00 | 0.00 | 0.00 |
| screen/berries | 1022.4 | 3.00 | 2.00 | 2.00 | 0.00 |
| screen/herd | 922.4 | 2.00 | 3.00 | 0.00 | 0.00 |
| screen/both | 922.4 | 2.00 | 3.00 | 1.00 | 0.00 |
| confirmation/baseline | 815.5 | 3.96 | 2.00 | 0.00 | 0.00 |
| confirmation/berries | 972.3 | 3.31 | 2.00 | 2.00 | 0.00 |

The strawberry-only variant can crowd out a scheduled cow purchase even though each immediate seed purchase is affordable. These are competing uses of early capital; the six-day herd counts show the actual resulting policy, not just the intended planting change. A skipped animal leaves some native service visits unproductive. Crop ages also differ after handoff, so unchanged routes are legal but not necessarily optimal.

## Confirmation cash accounting

| Flow | Mean candidate minus baseline |
|---|---:|
| cost:BUY_ANIMAL:COW | -275.00 |
| cost:BUY_ANIMAL:SHEEP | +20.83 |
| cost:BUY_PRODUCT:FERTILIZER | +25.44 |
| cost:BUY_PRODUCT:WHEAT | +7.88 |
| cost:HIRE | -81.54 |
| revenue:CARROT | -10.23 |
| revenue:EGG | +33.75 |
| revenue:FERTILIZER | -286.08 |
| revenue:MILK | -303.90 |
| revenue:STRAWBERRY | +49.12 |
| revenue:WHEAT | +70.29 |
| revenue:WOOL | -0.65 |

## Promotion gate

Positive confirmation margin, nonnegative per rival, >=6/8 positive seed averages, no fewer wins, cash delta>=-500, zero execution errors/fallbacks, max call<1s. No automatic submission.

- positive_margin: False
- nonnegative_each_rival: False
- six_positive_seeds: False
- no_fewer_wins: False
- cash_floor: True
- no_errors: True
- max_call_below_one_second: True

Maximum confirmation candidate call: 0.297s. Nonzero execution error/fallback entries across discovery and confirmation: 0. All games checked 720 valid states, exact cash ledgers and per-turn wheat conservation. Focused contracts verify the paired purchase/pickup/place changes, seed affordability, observation immutability and early-crop protection.

## Interpretation

In confirmation, our cash changed by -145.3, while opponent cash changed by +1864.0. Thus most of the match-margin loss comes from a richer opponent, not a comparably large drop in our cash. Our milk sales changed by -16.5 units; opponent milk revenue changed by +1825.4. This is consistent with reduced milk supply benefiting rivals through the shared market; it is not a controlled causal decomposition of every changed action.

Retain the V45 policy. These selective transfers failed; the full leader opening remains untested as a hybrid. A fuller attempt would need coordinated first-day livestock, delayed melon planting and rewritten harvest/service schedules, not only earlier seeds or a different herd mix.

## Files

- `agents/leader_opening_overlay.py`; `scripts/build_leader_hybrids.py`.
- `scripts/evaluate_leader_hybrids.py --phase smoke/screen/select/confirmation` (one phase per invocation).
- `scripts/verify_leader_hybrids.py`; `scripts/report_leader_hybrids.py`.
- `results/fresh/leader_hybrids/`: source manifest, individual game ledgers, board snapshots, discovery selection and summary.
- `agents/v45_leader_selected.py`: exact file selected by the promotion gate. Existing agents and Kaggle submissions are unchanged.

## Packaging correction

The first file-loader check exposed a last-callable export bug: the loader selected the cash-budget helper and silently produced a no-op game. Named-agent performance tests were unaffected. The submission-ready copy explicitly re-exports the intended agent as the final callable; all 719 actions then matched the research entry point exactly in a native-shop-RNG game. The original frozen experiment sources remain unchanged. A completed valid-state game alone is not an adequate packaging check.

Corrected candidate package: `agents\v45_leader_berries_submission.py`. Total full games: 234 (224 performance-panel games, eight smoke/debug games, two packaging checks, one of which exposed the bug).

## Existing event-agent export issue

The audit also found that the previously submitted event agent exported its parent wrapper to Kaggle's last-callable loader. This bypassed forecast-history initialization: the original loader run left the event model uninitialized and its forecast planning calls reverted to the native input plan. Earlier packaging checks verified completion and accounting but did not verify entry-point/action parity, so they missed this.

Prepared `agents\v45_event_entrypoint_fixed.py` and verified all 719 actions against the research entry point in a further native-RNG game. The selected baseline copy in this study uses that corrected export. The prior submitted file is preserved, and no new submission was made. Including this audit, 235 full games were run.
