# Opponent-aware sales research

## Decision

Keep [agents/market_priority_selected.py](../agents/market_priority_selected.py) as the new locally preferred candidate: the six-day router plus the existing milk/wool sales adapter and milk/wool-first market ordering. Independent confirmation on eight fresh seeds produced 64 wins in 64 games versus 45 wins, 12 ties and 7 losses for the previous baseline across the same opponent panel; mean cash improved by 459.5 and mean match margin by 1001.6. Keep forecast-driven holding experimental: its margin advantage over priority alone was only +16.4 in natural discovery and -25.1 under controlled shops. The previous selected file is preserved. No Kaggle submission was made.

## Main findings

- Visible-state delivery forecasts reduced held-out 12-turn error by 27.7% versus a recent-sales average (4.57 to 3.30 units).

- Nearly all competitive benefit came from putting milk/wool sales earlier in the market queue. Adding margin-aware holding changed margin by only +16.4 per natural test game and -25.1 per controlled-shop game relative to priority alone. The holding layer is not selected.

- The simple priority tactic does not condition on an opponent forecast. The opponent model remains a research component. A useful next experiment is adaptive product ordering: account for likely rival orders and the opportunity cost of delaying our other products. Test it against the fixed-priority candidate and different opponent families.

## Experiment

The frozen experiment compares the selected router with three variants: put milk/wool sales first (**priority**); add delivery-aware holding to maximize our revenue (**profit**); or add holding to maximize our revenue minus the opponent's (**margin**). Only one lot of at most six milk/wool units is reserved at a time, with a 12-turn hold target, 24-turn payoff horizon, cash and storage guards, and terminal liquidation. Farming actions come from the same router; later router choices can react to changed cash/prices.

The predictor uses public animal yields, observed yield decreases, public market inventory and our own stock changes. Hidden opponent inventory is estimated, never read. Three predictors were compared on 16 training games, then frozen before testing: recent average sales, time-of-day sales rhythm, and visible yields combined with that rhythm. Two additional training-seed smoke games exercised the holding policies.

Natural tests use four fresh seeds, both seats, four opponents and four policies (128 games). The separate controlled panel uses all eight first-shop types, fixed subsequent shop sequences, both seats, two selling behaviors and four policies (128 games). Opponents are the raw six-day router, E776 pasture, our prompt-selling baseline, and a synthetic daily stockpiler built on that baseline. The stockpiler is a behavior stress test, not a claim about a strong leaderboard agent.

## Delivery forecasts

Selected on training data: **visible**, minimizing 12-turn delivery error when the current price exceeds the floor. Values below are mean absolute errors in units per product and forecast window; they are not price errors.

| Panel | Predictor | 6 turns | 12 turns | 24 turns |
|---|---|---:|---:|---:|
| train | recent | 3.71 | 4.74 | 4.95 |
| train | clock | 3.20 | 4.09 | 4.95 |
| train | visible | 3.06 | 3.60 | 3.90 |
| test | recent | 3.55 | 4.57 | 4.64 |
| test | clock | 3.03 | 3.87 | 4.64 |
| test | visible | 2.71 | 3.30 | 3.51 |
| shops | recent | 3.65 | 4.40 | 4.57 |
| shops | clock | 3.02 | 3.55 | 4.57 |
| shops | visible | 2.69 | 3.06 | 3.61 |

Forecast diagnostics use baseline games only, avoiding repeated counting of forecasts from four policy variants. Checkpoints are every 24 turns from turn 216 through 672, so these errors describe forecasts made at midnight, not uniformly sampled decision times. Training covers only two seeds; held-out performance is the stronger check.

The market-inventory reconstruction is approximate near the price floor. A sale can hit $1 during a turn and town consumption can restore the price before the next observation; checking only the two observed prices does not fully identify those sales. Midnight overflow is also ambiguous. The audit therefore reports error even among observations flagged usable by the model. Animal growth forecasts assume continued feeding/care, and do not predict new animal purchases.

## Natural-shop held-out games

Each row compares the variant against its control on the same seed, seat and opponent. W/T/L is against the listed opponent, not a direct variant-versus-control match. Positive margin change improves our lead.

| Variant | Control | Opponent | Games | Cash change | Margin change | W/T/L | Control W/T/L |
|---|---|---|---:|---:|---:|---|---|
| priority | baseline | all | 32 | +292.7 | +696.1 | 30/0/2 | 22/4/6 |
| priority | baseline | pasture | 8 | -25.1 | -44.5 | 8/0/0 | 8/0/0 |
| priority | baseline | prompt | 8 | +778.2 | +1770.5 | 7/0/1 | 2/4/2 |
| priority | baseline | sixday | 8 | +620.8 | +1440.2 | 7/0/1 | 4/0/4 |
| priority | baseline | stockpiler | 8 | -203.1 | -381.8 | 8/0/0 | 8/0/0 |
| profit | baseline | all | 32 | +357.1 | +619.2 | 30/0/2 | 22/4/6 |
| profit | baseline | pasture | 8 | +13.9 | -98.2 | 8/0/0 | 8/0/0 |
| profit | baseline | prompt | 8 | +782.1 | +1537.8 | 7/0/1 | 2/4/2 |
| profit | baseline | sixday | 8 | +692.5 | +1303.2 | 7/0/1 | 4/0/4 |
| profit | baseline | stockpiler | 8 | -60.1 | -265.8 | 8/0/0 | 8/0/0 |
| margin | baseline | all | 32 | +332.7 | +712.5 | 30/0/2 | 22/4/6 |
| margin | baseline | pasture | 8 | -48.4 | -26.0 | 8/0/0 | 8/0/0 |
| margin | baseline | prompt | 8 | +798.6 | +1729.2 | 7/0/1 | 2/4/2 |
| margin | baseline | sixday | 8 | +660.5 | +1402.8 | 7/0/1 | 4/0/4 |
| margin | baseline | stockpiler | 8 | -79.9 | -256.0 | 8/0/0 | 8/0/0 |
| profit | priority | all | 32 | +64.4 | -76.9 | 30/0/2 | 30/0/2 |
| margin | priority | all | 32 | +40.0 | +16.4 | 30/0/2 | 30/0/2 |

Seed-level mean margin changes (seats and opponents averaged within seed):

- **priority:** 121000: +1173.8, 121001: -121.0, 121002: +1457.2, 121003: +274.5. Changed farming-action hashes: 0/32; changed final shops: 0/32. Holding statistics: `{}`.
- **profit:** 121000: +1124.8, 121001: -226.8, 121002: +1342.2, 121003: +236.8. Changed farming-action hashes: 0/32; changed final shops: 0/32. Holding statistics: `{"delayed_lots": 130, "held_unit_turns": 6098, "lots": 220}`.
- **margin:** 121000: +1203.5, 121001: -147.5, 121002: +1422.8, 121003: +371.2. Changed farming-action hashes: 0/32; changed final shops: 0/32. Holding statistics: `{"delayed_lots": 113, "held_unit_turns": 4882, "lots": 232}`.
## Controlled shop panel

Each row compares the variant against its control on the same seed, seat and opponent. W/T/L is against the listed opponent, not a direct variant-versus-control match. Positive margin change improves our lead.

| Variant | Control | Opponent | Games | Cash change | Margin change | W/T/L | Control W/T/L |
|---|---|---|---:|---:|---:|---|---|
| priority | baseline | all | 32 | +661.2 | +1445.7 | 32/0/0 | 18/12/2 |
| priority | baseline | prompt | 16 | +1462.0 | +3152.5 | 16/0/0 | 2/12/2 |
| priority | baseline | stockpiler | 16 | -139.6 | -261.2 | 16/0/0 | 16/0/0 |
| profit | baseline | all | 32 | +757.1 | +1377.3 | 32/0/0 | 18/12/2 |
| profit | baseline | prompt | 16 | +1447.0 | +2836.6 | 16/0/0 | 2/12/2 |
| profit | baseline | stockpiler | 16 | +67.2 | -81.9 | 16/0/0 | 16/0/0 |
| margin | baseline | all | 32 | +659.2 | +1420.5 | 32/0/0 | 18/12/2 |
| margin | baseline | prompt | 16 | +1292.0 | +2932.1 | 16/0/0 | 2/12/2 |
| margin | baseline | stockpiler | 16 | +26.4 | -91.1 | 16/0/0 | 16/0/0 |
| profit | priority | all | 32 | +95.9 | -68.3 | 32/0/0 | 32/0/0 |
| margin | priority | all | 32 | -2.0 | -25.1 | 32/0/0 | 32/0/0 |

Seed-level mean margin changes (seats and opponents averaged within seed):

- **priority:** 122000: +1664.0, 122001: +2395.5, 122002: +2229.5, 122003: +1510.5, 122004: +129.5, 122005: +1750.0, 122006: +213.2, 122007: +1673.0. Changed farming-action hashes: 0/32; changed final shops: 0/32. Holding statistics: `{}`.
- **profit:** 122000: +1500.0, 122001: +2408.5, 122002: +2217.0, 122003: +1437.5, 122004: +132.5, 122005: +1449.0, 122006: +325.8, 122007: +1548.5. Changed farming-action hashes: 0/32; changed final shops: 0/32. Holding statistics: `{"blocked_release": 2, "delayed_lots": 136, "held_unit_turns": 5588, "lots": 201}`.
- **margin:** 122000: +1604.0, 122001: +2462.5, 122002: +2235.0, 122003: +1473.0, 122004: +125.0, 122005: +1547.5, 122006: +342.2, 122007: +1575.0. Changed farming-action hashes: 0/32; changed final shops: 0/32. Holding statistics: `{"delayed_lots": 134, "held_unit_turns": 5106, "lots": 213}`.

Mean margin change by first shop (both seats and both opponent behaviors combined):

| First shop | Priority vs baseline | Profit vs baseline | Margin vs baseline |
|---|---:|---:|---:|
| BAKERY | +1664.0 | +1500.0 | +1604.0 |
| BRUNCH_SPOT | +2395.5 | +2408.5 | +2462.5 |
| FARMERS_MARKET | +2229.5 | +2217.0 | +2235.0 |
| ICE_CREAM_SHOP | +1510.5 | +1437.5 | +1473.0 |
| PET_CAFE | +129.5 | +132.5 | +125.0 |
| PIZZA_SHOP | +1750.0 | +1449.0 | +1547.5 |
| SMOOTHIE_SHOP | +213.2 | +325.8 | +342.2 |
| YARN_STORE | +1673.0 | +1548.5 | +1575.0 |

## Independent confirmation of the packaged candidate

After the discovery panel showed that nearly all of the gain came from order priority, the standalone priority candidate was compared with the existing selected agent on eight additional untouched natural seeds, both seats and all four opponents: 128 further games. No policy parameters were changed.

| Opponent | Games per policy | Cash change | Margin change | Candidate W/T/L | Baseline W/T/L |
|---|---:|---:|---:|---|---|
| all | 64 | +459.5 | +1001.6 | 64/0/0 | 45/12/7 |
| pasture | 16 | +24.2 | +58.8 | 16/0/0 | 16/0/0 |
| prompt | 16 | +1121.7 | +2406.9 | 16/0/0 | 2/12/2 |
| sixday | 16 | +797.7 | +1736.4 | 16/0/0 | 11/0/5 |
| stockpiler | 16 | -105.5 | -195.6 | 16/0/0 | 16/0/0 |

Seed-level mean margin changes: 123000: +785.0, 123001: +609.8, 123002: +833.2, 123003: +967.0, 123004: +1595.5, 123005: +832.6, 123006: +272.5, 123007: +2117.5.

Changed farming-action hashes: 0/64; changed shops: 0/64. Largest measured packaged-agent action time: 0.126 seconds (local timing, not a platform guarantee).

The formal evaluation totals 400 games: 16 training, 128 natural discovery, 128 controlled-shop, and 128 independent confirmation. Four additional smoke/parity games were used for implementation checks. The standalone candidate uses only the Python standard library, matched the research control on 1,438 actions, and passed its JSON stdin entry-point check.

## Why market order matters

The natural-test ledger isolates the priority-only effect: both players sold the same quantities, and our farming routes and final shops were unchanged. Against the raw six-day router, prioritizing milk/wool changed our milk revenue by +893.2 and its milk revenue by -1023.0 per game on average. Moving other products later has a cost, however. Against the synthetic stockpiler, milk rarely competes at the same time and that cost dominates. This points toward predicting the opponent's market-order positions and choosing which product to sell first, rather than relying only on aggregate shipment volume.


## Validation and interpretation

- All games completed 720 states with valid statuses. Both players' terminal cash reconciles exactly to initial cash plus actual sales minus spending. Every reserved lot was released by game end.

- 640 verification cases compare dynamic programming against exhaustive enumeration and same-product lockstep trades against the official engine. A synthetic case demonstrates a real objective difference: profit waits while margin sells immediately. This verifies the mechanism, not competitive strength.

- Market-order priority is tested separately so a gain from order placement cannot be attributed to forecasting. The scheduler approximates competing orders as aligned same-product trades; full matches use actual engine order positions. Opponent forecasts remain fixed inside each planning horizon and do not simulate retaliation.

- Same seed can yield different shops if farm trajectories diverge because weeds and shops share an RNG. The controlled panel holds revealed shop sequences equal; the policy sees no future shop draws. Natural results include these downstream effects.

- Both seats are paired checks, not independent seeds. Four discovery seeds, eight confirmation seeds and related public policy families do not establish leaderboard strength. The controlled panel covers all first shops but only one subsequent sequence per first shop.

- train inventory-inference audit: 20908/22976 product-turns flagged usable; mean absolute error on those = 0.0121 units. Of 38 mismatches, 38 are exactly explained by the two players' floor-price sales.
- test inventory-inference audit: 40852/45952 product-turns flagged usable; mean absolute error on those = 0.0052 units. Of 48 mismatches, 48 are exactly explained by the two players' floor-price sales.
- shops inventory-inference audit: 42996/45952 product-turns flagged usable; mean absolute error on those = 0.0107 units. Of 74 mismatches, 74 are exactly explained by the two players' floor-price sales.

## Artifacts

- Research policy: `agents/opponent_sales.py` (requires the local engine; not a standalone submission).

- Runner: `scripts/research_opponent_sales.py`; forecast selection: `scripts/select_delivery_forecast.py`; verification: `scripts/verify_opponent_sales.py`; this report: `scripts/report_opponent_sales.py`.

- Frozen source hashes, seeds, full-game results, ledger events, forecasts, and decision logs: `results/fresh/opponent_sales/`. Aggregate metrics: `summary.json`.

- Standalone priority candidate: `agents/market_priority_candidate.py`; builder/parity check: `scripts/build_market_priority.py`; independent confirmation runner: `scripts/confirm_market_priority.py`.
