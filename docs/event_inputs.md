# Event forecast: V45 investment-policy test

Selected **baseline** as `agents/v45_event_selected.py`. The original hybrid and Kaggle submission are unchanged.

Candidate versus selected hybrid: **+11.7 mean margin**, **+16.6 own cash**; 3/8 positive seed averages.

## Forecast result

The preceding independent forecast test passed: primary wheat/carrot price MAE was 0.320, versus 0.723 for market flow and 0.576 for a calibrated model without production/stock features. Event forecasts improved all eight held-out seeds. Milk/wool diagnostics also improved. See [forecast report](event_prices.md).

## What changed in the policy

One candidate. Eight fresh policy-test seeds after forecast gate; both seats; 3 rivals; hidden common shops. Native tour generation, costs, safety factors and sale ordering unchanged. Only output valuation uses frozen event forecasts, interpolated for 12-72h deliveries within turns216-636; otherwise current-price valuation retained.

The original three native tour modes, minimum tour length, two-worker limit, costs, end-of-lot price-impact convention, cash reserve and profitability thresholds are preserved. Forecast output is estimated to enter the shed at harvest-day midnight and sell at the next native tape slot. Predicted inventory is interpolated between trained horizons. If delivery is outside the tested window or has no matched sale slot, native current-price valuation is used. No aggressive liquidation or expanded joint-tour selector was added.

The code embeds the frozen coefficients and exact research feature code with engine constants, so the candidate is a single standalone file with no local engine import. Synthetic feature parity and exact native-plan equivalence with current quotes were verified.

## Fresh policy test

Eight new seeds (147000-147007), both seats, three rivals, two policies: 96 complete games. Shops use common hidden draws per seed; neither policy sees future shops. The forecast coefficients and policy were frozen before this panel. A separate native-RNG game tested the official file-path loader. Combined with the 72 forecast-research games, this study contains 169 full games.

| Rival | Margin gain | Cash gain | Candidate wins/ties | Baseline wins/ties |
|---|---:|---:|---:|---:|
| all | +11.7 | +16.6 | 48/0 of 48 | 48/0 of 48 |
| v45 | +21.1 | +24.5 | 16/0 of 16 | 16/0 of 16 |
| twocoins | +0.0 | +0.0 | 16/0 of 16 | 16/0 of 16 |
| farmingv5 | +13.9 | +25.2 | 16/0 of 16 | 16/0 of 16 |

## Seed consistency

| Seed | Margin change |
|---|---:|
| 147000 | +0.0 |
| 147001 | +0.0 |
| 147002 | +0.0 |
| 147003 | +22.7 |
| 147004 | +0.0 |
| 147005 | +0.0 |
| 147006 | +28.7 |
| 147007 | +42.0 |

## Cash-flow changes

| Cash flow | Mean change |
|---|---:|
| revenue:WHEAT | -55.12 |
| revenue:CARROT | -14.92 |
| revenue:FERTILIZER | -13.42 |
| cost:BUY_PRODUCT:FERTILIZER | -32.08 |
| cost:HIRE | -33.71 |

## Promotion gate

Positive average margin; nonnegative margin change per rival; positive seed averages >=6/8; no fewer wins; own cash delta >=-500; zero errors/fallbacks; max call <1sec. Otherwise retain prior hybrid. No automatic submission.

- positive_margin: True
- nonnegative_each_rival: True
- six_positive_seeds: False
- no_fewer_wins: True
- cash_floor: True
- no_errors: True
- call_below_one_second: True

Mean changed planning calls per game: 0.25. Forecast-valued lot evaluations: 107.2; current-price lot evaluations: 193.8. These counters include alternative plans, not distinct purchases. Maximum candidate call: 0.299s. Nonzero candidate error/fallback counters: 0. All games passed valid-state, cash-ledger and wheat-conservation checks.

## Interpretation and limits

A better quote forecast is not an estimate of the causal profit from an extra unit of production. Delivery timing is approximate, action changes can shift future market flow, and the native route shortlist and profit thresholds remain fixed. Training snapshots were at 12-hour intervals; actual investment decisions occur at hours 1-3. Policy evaluation tests that timing shift directly. Both studies cover only a few related opponent families; they do not imply a leaderboard rating.

## Decision

Keep the validated event forecast and its frozen coefficients for further research. Retain the existing competitive hybrid: the candidate misses the predeclared six-positive-seeds gate. This is a sparse-impact result rather than evidence of a negative average effect: three seed averages improved, five were unchanged, and none fell. Only 0.25 planning calls changed per game on this panel; the original planner is insensitive to many quote improvements. Do not relax the gate after seeing the results.

A promising next application is bounded sale timing, where the forecast can affect more decisions and milk/wool price changes are larger. That requires its own fresh competitive test, explicit inventory/cash limits and a comparison with our existing price-impact sale ordering. It has not been implemented in this study.

## Files

- `agents/v45_event_candidate.py`: standalone experimental policy.
- `agents/v45_event_selected.py`: outcome of the frozen promotion gate.
- `agents/event_input_overlay.py`, `scripts/build_event_inputs.py`: editable source and build.
- `scripts/verify_event_inputs.py`, `scripts/evaluate_event_inputs.py`, `scripts/report_event_inputs.py`.
- `results/fresh/event_inputs/`: manifests, ledgers, verification and summary.
