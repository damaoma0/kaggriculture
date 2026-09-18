# Event-based delivery-price forecasting

**Forecast gate: passed**. V45 + our sale ordering remains the competitive baseline. No policy was changed or submitted.

## What was tested

A causal model predicts future aggregate market inventory, then converts it through the exact engine price curve. Production features cover both visible farms: crop maturity and potential watering yield, animal production dates and care potential, recent observed harvests, candidate direct/12-hour/midnight delivery windows, and our observable shed/cargo. Historical market flow and hour-of-day selling rhythms provide context. Opponent private holdings, actions and future routes are never read. Unknown future-shop demand uses its expectation under uniform replacement draws.

Production events are estimates: care, watering, harvesting and selling are not guaranteed. The model does not simulate a known rival policy. Linear ridge calibration learns how strongly each feature predicts the subsequent inventory; it is fitted separately by product and horizon.

Controls: current quote; the prior 24/48-hour blended flow forecast; an hourly flow forecast; and an identically trained ridge model without farm-event or own-stock features. Comparing event versus base isolates the added feature group, not any single event feature.

## Frozen evaluation

Native RNG; unchanged V45 hybrid; four training seeds, eight held-out seeds; both seats; three rivals. Ridge regularization selected only by training leave-one-seed-out validation.

72 complete games: 24 training and 48 held-out games. Forecasts are issued every 12 turns from turn 216 through 636, regardless of whether an investment is accepted. Products: wheat, carrots, milk and wool; horizons: 12/24/48/72 turns. Primary endpoint: wheat/carrot MAE at 24/48/72 turns. Repeated forecasts and related rivals are correlated; the effective held-out seed count is eight. Hyperparameters use only leave-one-training-seed-out validation.

| Method | Primary absolute price error |
|---|---:|
| current | 1.269 |
| flow | 0.723 |
| clock | 0.801 |
| base | 0.576 |
| event | 0.320 |

## Product and horizon

| Product / turns | Current | Flow | Clock | Calibrated without events | Calibrated events |
|---|---:|---:|---:|---:|---:|
| WHEAT/12 | 0.455 | 0.433 | 0.435 | 0.344 | 0.300 |
| WHEAT/24 | 0.683 | 0.557 | 0.613 | 0.476 | 0.376 |
| WHEAT/48 | 1.156 | 1.082 | 1.214 | 0.689 | 0.420 |
| WHEAT/72 | 1.709 | 1.568 | 1.847 | 0.995 | 0.578 |
| CARROT/12 | 0.322 | 0.000 | 0.000 | 0.000 | 0.000 |
| CARROT/24 | 0.657 | 0.018 | 0.018 | 0.030 | 0.030 |
| CARROT/48 | 1.331 | 0.252 | 0.252 | 0.269 | 0.167 |
| CARROT/72 | 2.076 | 0.860 | 0.860 | 0.994 | 0.351 |
| MILK/12 | 10.189 | 11.690 | 10.170 | 9.499 | 7.882 |
| MILK/24 | 14.675 | 17.528 | 13.490 | 12.170 | 8.123 |
| MILK/48 | 21.118 | 26.126 | 18.902 | 14.497 | 8.911 |
| MILK/72 | 26.860 | 30.824 | 22.377 | 17.174 | 11.076 |
| WOOL/12 | 8.567 | 11.125 | 9.615 | 9.277 | 7.312 |
| WOOL/24 | 12.700 | 18.166 | 14.292 | 12.231 | 8.646 |
| WOOL/48 | 17.404 | 21.517 | 16.366 | 14.398 | 10.800 |
| WOOL/72 | 23.733 | 29.354 | 21.853 | 19.234 | 14.250 |

## Seed consistency

| Seed | Current | Flow | Clock | Without events | With events |
|---|---:|---:|---:|---:|---:|
| 146000 | 0.897 | 0.648 | 0.710 | 0.520 | 0.318 |
| 146001 | 1.843 | 0.742 | 0.747 | 0.693 | 0.498 |
| 146002 | 1.210 | 0.818 | 0.949 | 0.699 | 0.296 |
| 146003 | 1.301 | 0.585 | 0.685 | 0.449 | 0.292 |
| 146004 | 0.935 | 0.640 | 0.722 | 0.492 | 0.262 |
| 146005 | 1.057 | 0.727 | 0.801 | 0.468 | 0.245 |
| 146006 | 0.931 | 0.612 | 0.731 | 0.499 | 0.274 |
| 146007 | 1.977 | 1.011 | 1.060 | 0.784 | 0.375 |

## Gate and execution

Primary: WHEAT/CARROT at 24/48/72 turns. Event model must improve MAE >=5% versus current, flow and no-event calibrated control; beat each on >=6/8 held-out seeds; neither crop MAE >5% worse versus best control for that crop. No policy integration unless passed.

- five_percent_vs_current: True
- five_percent_vs_flow: True
- five_percent_vs_base: True
- six_seeds_vs_current: True
- six_seeds_vs_flow: True
- six_seeds_vs_base: True
- WHEAT_no_regression: True
- CARROT_no_regression: True
- no_execution_failures: True

All 72 games completed 720 valid states with exact cash ledgers and per-turn wheat conservation. Maximum observation/feature call under concurrent load: 0.337s. Nonzero execution error/fallback counters: 0.

## Limits

This evaluates price prediction, not winning margin or investment returns. Potential production ignores future replanting, assumes continued maintenance, and only approximately represents delivery times. Observed yield disappearance may include digging; midnight and decay-ambiguous harvests are excluded. The opponent families remain limited and related. A passing forecast must still survive a new policy-level test before adoption.

## Files

- Research module: `agents/event_price_forecast.py` (uses local engine constants; not a standalone submission).
- Corpus: `scripts/research_event_prices.py --phase train`, then `--phase test` after freezing models.
- Calibration: `scripts/evaluate_event_prices.py --mode train`; evaluation: `--mode report`.
- Frozen sources, model coefficients, per-game features/labels and errors: `results/fresh/event_prices/`.
