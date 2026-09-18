# Adaptive market-order research

## Decision

Keep [agents/market_impact_selected.py](../agents/market_impact_selected.py) as the locally preferred candidate. The confirmed static ordering policy produced 80 wins, 0 ties and 0 losses in 80 matches, versus 64 wins, 16 ties and 0 losses for fixed priority on the same panel. Mean cash changed by +701.9 and match margin by +1304.0. Its additional margin improvement over availability-only ordering was +1107.5. The selected price-impact rule uses current prices and available lot sizes; it does not use opponent forecasts. The previous selected files are preserved. No Kaggle submission was made.

## Method

All variants start from the selected six-day router with milk/wool-first selling. Through turn 215, actions are identical. Thereafter only existing SELL orders are permuted: quantities, farming actions and the positions of non-SELL orders are preserved relative to the base policy at the current observation. Later farming decisions can still react to changed cash or prices. There is no stock holding.

| Policy | Ranking information |
|---|---|
| fixed | Existing milk/wool-first ordering |
| available | Move empty sales behind available sales; preserve other relative order |
| static | Current prices and our lot size, assuming the rival sells an equal-sized lot |
| clock | Rival net trade inferred from public market changes minus our own net trades, using the last four days and the same hour of day |
| visible | Clock estimate for all products, replaced for milk/wool by the previous study's visible-animal delivery estimate |

For each of our lots, the ranking value is the difference in immediate cash margin between selling the whole lot before versus after the predicted rival lot. Negative rival flow represents buying wheat or fertilizer. Fractional forecasts interpolate adjacent integer scenarios. Orders with larger values go earlier; ties preserve existing order. This heuristic does not infer the rival's actual order positions or jointly optimize the complete queue. It uses current observations and past observations only; no opponent private state, current opponent action or future shop draw is available.

Inference flags observations unusable at the price floor or ambiguous midnight overflow. It checks prices before town consumption as well as observed prices, addressing the previous study's floor-recovery ambiguity. Mixed buying and selling can still make inference uncertain. Unknown flows are excluded from historical averages.

## Evaluation design

Discovery: four fresh natural seeds, both seats, five opponents, four policies (160 games). Shop controls: all eight first shops, one fixed subsequent sequence each, both seats, fixed-priority and stockpiling opponents, four policies (128 games). Opponents are the raw six-day router, public E776 pasture, the previous prompt-selling adapter, our selected fixed-priority agent, and a synthetic stockpiler. The latter three are derived behaviors, not independent public-policy families.

The original selection rule was frozen before discovery outcomes were inspected. Candidates need positive margin improvement in both panels and no fewer aggregate natural-panel wins. Rank by the equal-weight mean of the two panel improvements; prefer the simpler candidate when within 50 margin units of the best. Promotion requires positive mean confirmation margin, no fewer aggregate wins, and more wins than losses in direct matches against fixed priority.

### Attribution control added during discovery

Inspection of seed 124000, turn 517 revealed a stale nine-unit MILK order with no available milk: the earlier automatic-sales adapter had already liquidated it. The price-impact heuristic moved an eight-unit STRAWBERRY sale ahead of it; the engine recorded strawberry sales and no milk sale. Empty orders still occupy a queue position. This can explain gains without any useful price ranking or opponent forecast.

We therefore added the availability-only control after examining partial logs, recording the amendment separately and leaving the original four policies and manifests unchanged. It adds 40 natural and 32 controlled-shop games. The amended simplicity order is available, static, clock, visible, retaining the original eligibility rule and 50-unit tolerance. Confirmation uses the original eight untouched seeds: fixed plus the selected candidate, and availability as a third policy if it was not selected. A more complex candidate must also improve confirmation margin over availability. This attribution addition is explicitly post hoc; confirmation remains untouched.

## Selection

Chosen for confirmation: **static**. Equal-panel scores: available +332.7, static +1456.9, clock +882.1, visible +1084.6.

## Discovery results

Cash and margin changes compare matched seed/seat/opponent games against fixed priority. W/T/L is versus the listed opponent.

| Variant | Opponent | Games | Cash change | Margin change | W/T/L | Fixed W/T/L |
|---|---|---:|---:|---:|---|---|
| available | all | 40 | +121.7 | +237.2 | 40/0/0 | 32/8/0 |
| available | pasture | 8 | +23.0 | +39.5 | 8/0/0 | 8/0/0 |
| available | priority | 8 | +161.0 | +314.5 | 8/0/0 | 0/8/0 |
| available | prompt | 8 | +150.2 | +296.0 | 8/0/0 | 8/0/0 |
| available | sixday | 8 | +150.2 | +296.0 | 8/0/0 | 8/0/0 |
| available | stockpiler | 8 | +124.0 | +240.0 | 8/0/0 | 8/0/0 |
| clock | all | 40 | +296.9 | +650.5 | 40/0/0 | 32/8/0 |
| clock | pasture | 8 | +19.8 | +33.8 | 8/0/0 | 8/0/0 |
| clock | priority | 8 | +687.5 | +1538.2 | 8/0/0 | 0/8/0 |
| clock | prompt | 8 | +275.8 | +608.2 | 8/0/0 | 8/0/0 |
| clock | sixday | 8 | +254.8 | +583.0 | 8/0/0 | 8/0/0 |
| clock | stockpiler | 8 | +247.0 | +489.0 | 8/0/0 | 8/0/0 |
| static | all | 40 | +653.2 | +1317.5 | 40/0/0 | 32/8/0 |
| static | pasture | 8 | +15.5 | +25.8 | 8/0/0 | 8/0/0 |
| static | priority | 8 | +1292.8 | +2624.2 | 8/0/0 | 0/8/0 |
| static | prompt | 8 | +800.0 | +1608.0 | 8/0/0 | 8/0/0 |
| static | sixday | 8 | +779.0 | +1584.2 | 8/0/0 | 8/0/0 |
| static | stockpiler | 8 | +378.8 | +745.0 | 8/0/0 | 8/0/0 |
| visible | all | 40 | +403.7 | +874.5 | 40/0/0 | 32/8/0 |
| visible | pasture | 8 | +37.5 | +67.5 | 8/0/0 | 8/0/0 |
| visible | priority | 8 | +823.0 | +1849.0 | 8/0/0 | 0/8/0 |
| visible | prompt | 8 | +493.2 | +1051.5 | 8/0/0 | 8/0/0 |
| visible | sixday | 8 | +423.5 | +927.5 | 8/0/0 | 8/0/0 |
| visible | stockpiler | 8 | +241.2 | +477.0 | 8/0/0 | 8/0/0 |

Additional gain over availability-only ordering:

| Variant | Cash change | Margin change |
|---|---:|---:|
| clock | +175.2 | +413.2 |
| static | +531.5 | +1080.2 |
| visible | +282.0 | +637.3 |

Seed-level mean margin changes, averaging seats and opponents within each seed:

- **available:** 124000: +200.6, 124001: +146.4, 124002: +395.2, 124003: +206.6. Changed farming-action hashes: 0/40; changed shops: 0/40. Reordered turns: 512; opportunities: 2040. Maximum local action time: 0.198s.
  Actual total product quantities sold changed in 0/40 own games and 0/40 opponent games.
- **clock:** 124000: +1167.2, 124001: +1045.4, 124002: +728.0, 124003: -338.8. Changed farming-action hashes: 0/40; changed shops: 0/40. Reordered turns: 746; opportunities: 2040. Maximum local action time: 0.263s.
  Actual total product quantities sold changed in 0/40 own games and 0/40 opponent games.
- **static:** 124000: +1472.0, 124001: +2076.8, 124002: +1050.8, 124003: +670.2. Changed farming-action hashes: 0/40; changed shops: 0/40. Reordered turns: 754; opportunities: 2040. Maximum local action time: 0.178s.
  Actual total product quantities sold changed in 0/40 own games and 0/40 opponent games.
- **visible:** 124000: +1158.0, 124001: +1602.8, 124002: +716.8, 124003: +20.4. Changed farming-action hashes: 0/40; changed shops: 0/40. Reordered turns: 736; opportunities: 2040. Maximum local action time: 0.229s.
  Actual total product quantities sold changed in 0/40 own games and 0/40 opponent games.

Inference audit, fixed-policy games only: 249874/258480 product-turns flagged usable, mean absolute error 0.0000 units, 0 mismatches. Action-preservation assertions passed on 143800 turns. Packaged-agent parity checks in this panel: 0 actions.
## Shops results

Cash and margin changes compare matched seed/seat/opponent games against fixed priority. W/T/L is versus the listed opponent.

| Variant | Opponent | Games | Cash change | Margin change | W/T/L | Fixed W/T/L |
|---|---|---:|---:|---:|---|---|
| available | all | 32 | +207.9 | +428.2 | 32/0/0 | 17/14/1 |
| available | priority | 16 | +313.4 | +657.9 | 16/0/0 | 1/14/1 |
| available | stockpiler | 16 | +102.4 | +198.6 | 16/0/0 | 16/0/0 |
| clock | all | 32 | +511.5 | +1113.8 | 30/0/2 | 17/14/1 |
| clock | priority | 16 | +790.3 | +1771.8 | 14/0/2 | 1/14/1 |
| clock | stockpiler | 16 | +232.6 | +455.9 | 16/0/0 | 16/0/0 |
| static | all | 32 | +746.2 | +1596.4 | 32/0/0 | 17/14/1 |
| static | priority | 16 | +1226.4 | +2675.0 | 16/0/0 | 1/14/1 |
| static | stockpiler | 16 | +266.0 | +517.8 | 16/0/0 | 16/0/0 |
| visible | all | 32 | +598.3 | +1294.7 | 32/0/0 | 17/14/1 |
| visible | priority | 16 | +978.3 | +2160.8 | 16/0/0 | 1/14/1 |
| visible | stockpiler | 16 | +218.2 | +428.6 | 16/0/0 | 16/0/0 |

Additional gain over availability-only ordering:

| Variant | Cash change | Margin change |
|---|---:|---:|
| clock | +303.6 | +685.6 |
| static | +538.3 | +1168.1 |
| visible | +390.4 | +866.4 |

Seed-level mean margin changes, averaging seats and opponents within each seed:

- **available:** 125000: +192.0, 125001: +295.0, 125002: +220.5, 125003: +191.0, 125004: +221.0, 125005: +200.5, 125006: +905.0, 125007: +1201.0. Changed farming-action hashes: 0/32; changed shops: 0/32. Reordered turns: 412; opportunities: 1624. Maximum local action time: 0.150s.
  Actual total product quantities sold changed in 0/32 own games and 0/32 opponent games.
- **clock:** 125000: +645.5, 125001: +1569.0, 125002: +1423.5, 125003: +1650.0, 125004: +79.5, 125005: +533.0, 125006: +1567.5, 125007: +1442.5. Changed farming-action hashes: 0/32; changed shops: 0/32. Reordered turns: 660; opportunities: 1624. Maximum local action time: 0.151s.
  Actual total product quantities sold changed in 0/32 own games and 0/32 opponent games.
- **static:** 125000: +1697.0, 125001: +1822.0, 125002: +1456.0, 125003: +1706.0, 125004: +1199.5, 125005: +1136.5, 125006: +1898.0, 125007: +1856.0. Changed farming-action hashes: 0/32; changed shops: 0/32. Reordered turns: 630; opportunities: 1624. Maximum local action time: 0.168s.
  Actual total product quantities sold changed in 0/32 own games and 0/32 opponent games.
- **visible:** 125000: +956.5, 125001: +1722.5, 125002: +1402.0, 125003: +1636.0, 125004: +572.0, 125005: +813.5, 125006: +1627.5, 125007: +1627.5. Changed farming-action hashes: 0/32; changed shops: 0/32. Reordered turns: 644; opportunities: 1624. Maximum local action time: 0.183s.
  Actual total product quantities sold changed in 0/32 own games and 0/32 opponent games.

Inference audit, fixed-policy games only: 200265/206784 product-turns flagged usable, mean absolute error 0.0000 units, 0 mismatches. Action-preservation assertions passed on 115040 turns. Packaged-agent parity checks in this panel: 0 actions.

| First shop | Available margin change | Static margin change | Clock margin change | Visible margin change |
|---|---:|---:|---:|---:|
| BAKERY | +192.0 | +1697.0 | +645.5 | +956.5 |
| BRUNCH_SPOT | +295.0 | +1822.0 | +1569.0 | +1722.5 |
| FARMERS_MARKET | +220.5 | +1456.0 | +1423.5 | +1402.0 |
| ICE_CREAM_SHOP | +191.0 | +1706.0 | +1650.0 | +1636.0 |
| PET_CAFE | +221.0 | +1199.5 | +79.5 | +572.0 |
| PIZZA_SHOP | +200.5 | +1136.5 | +533.0 | +813.5 |
| SMOOTHIE_SHOP | +905.0 | +1898.0 | +1567.5 | +1627.5 |
| YARN_STORE | +1201.0 | +1856.0 | +1442.5 | +1627.5 |
## Confirmation results

Cash and margin changes compare matched seed/seat/opponent games against fixed priority. W/T/L is versus the listed opponent.

| Variant | Opponent | Games | Cash change | Margin change | W/T/L | Fixed W/T/L |
|---|---|---:|---:|---:|---|---|
| available | all | 80 | +153.4 | +196.5 | 80/0/0 | 64/16/0 |
| available | pasture | 16 | +15.6 | +30.1 | 16/0/0 | 16/0/0 |
| available | priority | 16 | +229.9 | +275.1 | 16/0/0 | 0/16/0 |
| available | prompt | 16 | +215.1 | +250.1 | 16/0/0 | 16/0/0 |
| available | sixday | 16 | +215.1 | +250.1 | 16/0/0 | 16/0/0 |
| available | stockpiler | 16 | +91.5 | +177.1 | 16/0/0 | 16/0/0 |
| static | all | 80 | +701.9 | +1304.0 | 80/0/0 | 64/16/0 |
| static | pasture | 16 | -0.1 | +3.0 | 16/0/0 | 16/0/0 |
| static | priority | 16 | +1179.4 | +2285.5 | 16/0/0 | 0/16/0 |
| static | prompt | 16 | +1049.9 | +1880.8 | 16/0/0 | 16/0/0 |
| static | sixday | 16 | +1019.2 | +1842.1 | 16/0/0 | 16/0/0 |
| static | stockpiler | 16 | +261.1 | +508.8 | 16/0/0 | 16/0/0 |

Additional gain over availability-only ordering:

| Variant | Cash change | Margin change |
|---|---:|---:|
| static | +548.5 | +1107.5 |

Seed-level mean margin changes, averaging seats and opponents within each seed:

- **available:** 126000: +289.2, 126001: +137.8, 126002: +196.4, 126003: +248.8, 126004: +139.0, 126005: +244.6, 126006: +143.0, 126007: +173.4. Changed farming-action hashes: 0/80; changed shops: 0/80. Reordered turns: 868; opportunities: 4060. Maximum local action time: 0.197s.
  Actual total product quantities sold changed in 0/80 own games and 0/80 opponent games.
- **static:** 126000: +1238.0, 126001: +1671.6, 126002: +441.4, 126003: +874.4, 126004: +589.0, 126005: +2240.2, 126006: +2669.4, 126007: +708.2. Changed farming-action hashes: 0/80; changed shops: 0/80. Reordered turns: 1556; opportunities: 4060. Maximum local action time: 0.304s.
  Actual total product quantities sold changed in 0/80 own games and 0/80 opponent games.

Inference audit, fixed-policy games only: 496386/516960 product-turns flagged usable, mean absolute error 0.0000 units, 0 mismatches. Action-preservation assertions passed on 172560 turns. Packaged-agent parity checks in this panel: 57520 actions.

## Example with two available products

In discovery seed 124000 against the raw six-day router, turn 625 offered nine milk units and 24 strawberries. The price-impact scores were 340 for milk and 798 for strawberries, so strawberries moved ahead of milk. Both products actually sold. This is a quantity-and-price-curve decision, beyond moving empty orders: a larger fruit lot can lose more to competing supply than a smaller milk lot. The scores compare hypothetical equal-sized rival lots; they are not realized match-profit gains. Detailed examples are in `results/fresh/adaptive_order/valid_order_examples.json`.


## Checks and limits

- Every scored game completed 720 states with valid statuses; both players' cash reconciled exactly to initial money plus actual sales minus spending. Per-turn assertions preserve the base action's farming orders, market-order multiset and non-sale slots. Opening hashes match their controls. Controlled shops are identical across variants.

- 444 ranking-value checks passed against the official market engine and fractional interpolation; two complete smoke games preceded discovery.

- Reordering can affect affordability or shed space before a purchase, even when purchase slots are fixed. The full-game engine and ledger, not the ranking approximation, determine outcomes. Natural shops can diverge if changed farm trajectories change the shared RNG; changed-route/shop counts are reported above.

- Seeds, not seats or individual turns, are the independent scenarios. These local opponents cover a limited set of behaviors. Forecast errors and ranking assumptions must not be confused with guaranteed knowledge of an opponent's future orders.

## Reproducibility

Research policy: `agents/adaptive_market_order.py` (requires the local engine). Runner: `scripts/research_adaptive_order.py`. Checks: `scripts/verify_adaptive_order.py`. Report and frozen-rule selection: `scripts/report_adaptive_order.py`. Full ledgers, decision logs, source hashes and seeds: `results/fresh/adaptive_order/`. Previous selected agent is preserved.


Standalone candidate: `agents/adaptive_order_candidate.py`, built by `scripts/build_adaptive_order.py`; standard-library-only imports, JSON stdin check passed, 1438 parity actions across two pre-confirmation games. Candidate SHA-256: `216ed6a3857187cbd7803e50e033069af0c6bdb88ddf4ffbc879b4b49cbb4c6b`.

Completed scored games in this report: **600**, plus two smoke games and two packaging-parity games when the package artifact is present.