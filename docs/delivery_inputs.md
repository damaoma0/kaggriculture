# V45 delivery-time input valuation

Selected **baseline** for `agents/v45_delivery_selected.py`. Existing `v45_our_selected.py` and the Kaggle submission remain unchanged.

Confirmation versus our selected hybrid: **+0.9 margin**, **+19.4 own cash**; 3/8 positive seed averages.

## Experiment

One frozen standalone candidate built on our V45 sale-ordering hybrid. It values optional wheat/carrot fertilizer-worker plans at estimated delivery-time prices. It compares the native plan, a bounded shortlist of joint worker tours, and no investment. Existing execution, feeding and general investment logic remain native.

Eight scenarios sample unrevealed shops uniformly with replacement using an independent local RNG. Public market changes over 24 or 48 turns, with known demand added back, estimate aggregate net trading by both farms. Scenarios extrapolate those rates and subtract known and sampled shop demand. Scores combine 75% mean and 25% lower-quartile proceeds, subtract fertilizer/hiring costs, and retain cash/capacity/profit guards.

Delivery is approximated by the harvest-day midnight cargo drop and the next native tape sale. Incremental output changes its own sale quotes. This is not an explicit opponent-stock forecast, learned price model, or joint crop/animal investment optimizer.

## Frozen evaluation

Development: two fresh seeds (142000-142001). Confirmation: eight different seeds (143000-143007). Both seats, three rivals, and three policies: public V45, our selected hybrid, and candidate. 180 panel games plus one smoke game. Common hidden shop schedules isolate strategy changes; weeds remain policy dependent. Seeds, not individual games, are the main independent sample; rivals include related routers. No tuning between panels.

| Panel | Control | Rival | Margin gain | Own-cash gain | Candidate wins | Control wins |
|---|---|---|---:|---:|---:|---:|
| development | public | all | -299.7 | -18.4 | 9/12 | 9/12 |
| development | public | v44 | -392.5 | -76.8 | 4/4 | 4/4 |
| development | public | v45 | -392.5 | -76.8 | 1/4 | 1/4 |
| development | public | twocoins | -114.0 | +98.2 | 4/4 | 4/4 |
| development | baseline | all | -332.3 | -95.4 | 9/12 | 11/12 |
| development | baseline | v44 | -425.5 | -182.5 | 4/4 | 4/4 |
| development | baseline | v45 | -425.5 | -182.5 | 1/4 | 3/4 |
| development | baseline | twocoins | -146.0 | +78.8 | 4/4 | 4/4 |
| confirmation | public | all | +91.8 | +69.2 | 44/48 | 32/48 |
| confirmation | public | v44 | +89.2 | +49.8 | 16/16 | 16/16 |
| confirmation | public | v45 | +90.4 | +50.2 | 12/16 | 0/16 |
| confirmation | public | twocoins | +95.8 | +107.5 | 16/16 | 16/16 |
| confirmation | baseline | all | +0.9 | +19.4 | 44/48 | 48/48 |
| confirmation | baseline | v44 | -14.1 | -7.9 | 16/16 | 16/16 |
| confirmation | baseline | v45 | -11.9 | -6.5 | 12/16 | 16/16 |
| confirmation | baseline | twocoins | +28.6 | +72.5 | 16/16 | 16/16 |

## Promotion gate

Versus selected hybrid: positive confirmation margin; nonnegative against each rival; positive on >=6/8 seed averages; no fewer wins; cash delta >=-500; no errors/fallbacks; max call <1s. Also positive overall margin gain against public V45. No tuning between panels. No submission.

- positive_margin: True
- nonnegative_each_rival: False
- six_positive_seeds: False
- no_fewer_wins: False
- cash_floor: True
- no_errors: True
- time_limit: True
- positive_vs_public: True

## Forecast and execution diagnostics

On 970 planned-output quote checks, forecast absolute error averaged 1.47; reusing the decision-time quote gave 1.14. These are selected-plan diagnostics on repeated/related decisions, not independent forecast validation or realized marginal-profit attribution.

Mean changed planning calls: 2.29; declined native plans: 1.12. Maximum candidate call: 0.274s. All panel games checked 720 valid states, exact cash accounting and per-turn wheat conservation. Nonzero error/fallback entries: 0.

## Cash-flow changes

| Cash flow | Candidate minus selected hybrid |
|---|---:|
| revenue:WHEAT | +220.38 |
| revenue:CARROT | -114.38 |
| revenue:FERTILIZER | +58.58 |
| cost:BUY_PRODUCT:FERTILIZER | +114.92 |
| cost:HIRE | +39.71 |

## Seed consistency

| Confirmation seed | Margin change versus selected hybrid |
|---|---:|
| 143000 | -62.7 |
| 143001 | +163.3 |
| 143002 | -103.3 |
| 143003 | -26.0 |
| 143004 | +21.0 |
| 143005 | -61.7 |
| 143006 | +278.0 |
| 143007 | -201.7 |

## Current-price diagnostic control

An additional 48 games used identical tour choices and guards, replacing only forecast proceeds with current-price proceeds. Forecast minus current-price margin: **+49.0**; own cash: **+40.8**. The current-price control itself changed margin by -48.2 versus our selected hybrid. This control was added for diagnosis and is not eligible for promotion.

The candidate also passed a native-shop-RNG full game through the official file-path loader (seed 144999) with exact cash and wheat accounting. Total full games including smoke, integration and diagnostic control: 230.

## Limits and interpretation

The candidate changes both valuation and the tour shortlist; the current-price diagnostic control isolates their effects. Flow extrapolation cannot predict discrete rival deliveries or policy changes. Native early-sale reservations and physical repairs can shift the actual delivery/sale time. Crop gains, storage availability and profit safety factors remain approximations inherited from the existing planner. The shortlist is still generated using current-price heuristics and may omit routes favored by future prices. No leaderboard/Elo claim follows from this panel.

## Decision and next research step

Retain the selected V45 sale-ranking hybrid. This candidate did not produce a consistent improvement and won fewer confirmation games. The diagnostic control shows that forecasting helped this particular tour selector recover its losses, but not enough to improve the retained agent.

Before extending the model to animals or land, measure delivery-time quote forecasts for all feasible investment opportunities, including rejected plans, on a fresh logged panel. Replace constant-flow extrapolation with forecasts of discrete harvest/delivery events from both visible farms, and model actual sale reservations. Validate forecast calibration and marginal-profit estimates before another policy promotion test. This is proposed follow-up work, not an implemented feature.

## Reproduction

- `scripts/build_delivery_inputs.py`
- `scripts/verify_delivery_inputs.py`
- `scripts/evaluate_delivery_inputs.py --phase smoke/development/confirmation` (one phase per invocation)
- `scripts/report_delivery_inputs.py`
- `results/fresh/delivery_inputs/manifest.json`, `summary.json` and individual game ledgers.
