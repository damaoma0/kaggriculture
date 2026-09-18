# Market forecasts and sales DP

Completed 2026-09-16. Engine: kaggle-environments 1.32.7; default Kaggriculture rules.

## Conclusion

Keep the public-state forecaster as a research component. It improves held-out price predictions, but the bounded sales experiments do not establish a competitive upgrade. The strongest immediate lead is the newly downloaded six-day router; use it as the stronger reference for the next production-policy work. The selected submission policy has not been changed.

## Public agents and provenance

- [Six-day public-state router](https://www.kaggle.com/code/thomastschinkel/kaggriculture-93-8-win-rate-public-state-router): Python route portfolio with public-state selection every 144 turns. This differs from our older v31 reference.
- [Shape the shop, work the pasture](https://www.kaggle.com/code/indarkarhana/shape-the-shop-work-the-pasture-top-10): Python E776 policy with pasture logic, inherited route tapes and repairs.
- [Adaptive Route V2](https://www.kaggle.com/code/reyhanksatria/adaptive-route-agent-v2): extracted archive contains a Linux shared library, without its implementation source. Excluded from Windows execution.

Notebook setup cells were not executed. Archives were inspected, extracted as data, and checked against their embedded hashes. Python entry points were then evaluated locally. Source hashes are saved in the extraction and experiment manifests. Public score claims are not treated as current verified leaderboard results. The two usable policies have different decision logic but may share route ancestry; they are not guaranteed independent strategy families.

| Downloaded opponent | Local wins against old v31 | Mean cash advantage over v31 | Mean relative advantage |
|---|---:|---:|---:|
| sixday | 40/40 | +19,540.7 | +26.26% |
| pasture | 0/40 | -9,244.9 | -10.91% |

These are direct local matches across 20 seeds and both seats, not estimates of leaderboard win rate. Only unmodified baseline games enter this table.

## Forecast method and evaluation

Forecast inventory, then apply the official nonlinear price curve. The selected heuristic blends the last 48 turns of inferred net market flow with a rough production rate from visible crops and animals (50/50), subtracts known shop/center consumption, and uses expected demand for unrevealed future shops. It sees current public state and past markets only. It does not read opponent private inventory, future observations, seeds, or future actions.

Visible production is a rate approximation, not an exact simulation of future care, harvest, routing, stockpiling or planting. Net-flow history includes both players. Supply shocks, sale batching, and strategic reactions remain unresolved.

Four fixed models were compared: constant inventory/current price, linear inventory trend, recent flow plus shop mechanics, and flow blended with visible production. Selection used only normalized 24-turn MAE on seeds 97000–97003 against sixday. No fitted model parameters or test-set tuning were used. Seeds 97004–97007 form the same-opponent test and the held-out pasture-policy test. Both seats are included; rows within a seed are correlated.

The corpus contains 32 complete games. Eight sixday games select the method; eight sixday and eight pasture games evaluate it; eight pasture games on training seeds are unused for selection and forecast scoring. Forecast checkpoints start at turn 216. Every horizon uses only checkpoints with enough season remaining.

**Metric:** mean absolute price error divided by each product’s fixed base price, then averaged over products and checkpoints. The percentages below are not percentage errors relative to the actual market price.

| Test opponent | Horizon | Current-price error | Selected forecast error | Error reduction |
|---|---:|---:|---:|---:|
| sixday | 6 turns | 4.57% | 4.10% | 10.4% |
| sixday | 24 turns | 6.77% | 4.75% | 29.8% |
| sixday | 72 turns | 16.23% | 8.17% | 49.7% |
| sixday | 168 turns | 32.50% | 22.04% | 32.2% |
| pasture | 6 turns | 3.16% | 2.77% | 12.3% |
| pasture | 24 turns | 5.86% | 3.93% | 32.9% |
| pasture | 72 turns | 14.38% | 6.76% | 53.0% |
| pasture | 168 turns | 29.32% | 17.19% | 41.4% |

At 24 turns, raw mean absolute price error also falls: sixday 8.64 → 7.23, pasture 7.69 → 6.19 cash per unit. Long-horizon errors remain substantial. This is a useful first benchmark, not a claim of best-in-class forecasting.

## Small dynamic program

The DP allocates a lot of at most 10 units among sale times within 24 turns. Its state tracks time, units left and cumulative additions to market inventory. It models each unit’s own price impact and the engine’s price-floor behavior. It sells the remainder at the horizon and prefers earlier sales on ties. It is exact only for its fixed background-flow model, not for the full two-player game.

An offline diagnostic adds a hypothetical 10-unit crop lot to recorded external market flows. Mean extra revenue versus selling immediately is +12.18 against sixday and +9.65 against pasture. Perfect knowledge of those fixed flows gives +36.28 and +34.43 respectively. These are per-lot diagnostic values, not game-profit estimates: the recorded flows do not react to the added lot, and there are no storage, liquidity or routing costs.

## Full-game decision tests

Three sequential experiments each use four new seeds, both seats, both opponents, and three modes (unmodified v31, DP with constant-price forecast, DP with the selected forecast): 48 games per experiment, 144 in total. Together with the corpus, this research records 176 complete games.

The first experiment (98000–98003) considers only crops already in the shed and rarely acts. The second (99000–99003) also considers same-turn deposits. The third (100000–100003) includes eggs, milk and wool, covering all non-input products. Each expansion was frozen before running its new seeds; forecasts and numerical limits were unchanged. These are sequential exploratory experiments, not independent model-selection trials.

Common limits: start at turn 360 or later, cash at least 5,000, one lot of at most 10 units, conservative storage guard, and a 24-turn planning horizon. Wheat and fertilizer are excluded because the physical route consumes them. The policy replans every four turns and requests release for cash/storage pressure or the deadline; a full market-order list can postpone release until a slot is available. All lots must be liquidated before the season ends.

| Eligible goods | Mean final-cash change | Mean relative change | Better / same / worse | Worst / best | Delayed lots |
|---|---:|---:|---:|---:|---:|
| Stored crops | -10.25 | -0.002% | 2 / 11 / 3 | -175 / +118 | 7 |
| Deposited crops | +30.75 | +0.033% | 6 / 6 / 4 | -30 / +257 | 20 |
| All non-input products | +70.00 | +0.052% | 11 / 0 / 5 | -506 / +495 | 45 |

Each row compares 16 forecast-policy games with matched baseline games. Seats and opponents sharing a seed are correlated; four independent seeds per experiment are too few for a strong generalization claim. Seed-level changes and opponent breakdowns are saved in `research_summary.json`.

### Validation

- The constant-price control exactly matches every baseline action in all 48 paired comparisons.
- All 176 recorded games reach all 720 states without an error status. In the 144 sales-policy evaluation games, final cash also reconciles with successful engine trades, hires and land purchases.
- No reserved-lot shortfalls; no reserved goods left at season end. Full market-order lists can block individual sale requests, counted below.
- The DP matches exhaustive enumeration on 30 small cases. History-mutation checks confirm all four forecast methods ignore unavailable future records. A controlled no-trade scenario matches exact known shop consumption for 12 consecutive turns (`verification.json`).

- Stored crops: physical action sequence unchanged in 16/16 games; total units sold unchanged in 16/16; spending unchanged in 16/16; 0 sale requests postponed by full order lists.
- Deposited crops: physical action sequence unchanged in 16/16 games; total units sold unchanged in 16/16; spending unchanged in 16/16; 0 sale requests postponed by full order lists.
- All non-input products: physical action sequence unchanged in 16/16 games; total units sold unchanged in 16/16; spending unchanged in 16/16; 4 sale requests postponed by full order lists.

### Interpretation and next priority

The broadest sales policy averages -65.13 cash against sixday and +205.13 against pasture. Its pooled +70 cash result therefore does not demonstrate an improvement against the stronger opponent. Physical action sequences, quantities sold and spending match the controls, so these measured differences arise from market outcomes rather than increased production.

A smaller price error does not guarantee a better trading decision. A sale depends on the direction and timing of price changes for that particular product, and our own sale changes the price. Averaging over products and days can hide mistakes at sale times. Conservative 10-unit holding also captures only a small part of total economic value.

1. Use the six-day router as the stronger benchmark and study its route/production choices against v31. Its observed advantage is far larger than the tested sale-timing effects.
2. Retain the forecast module for counterfactual crop/animal production choices. Predict marginal revenue at plausible harvest times, with costs for care, route time, labor and tied-up cash; use a small DP to compare feasible alternatives.
3. Before increasing model complexity, improve supply-event timing: visible harvest readiness, delivery batches, animal collection and opponent selling behavior. Evaluate decision-weighted errors at real sale/planting opportunities and use more fresh seeds and genuinely different opponents.

This completes the extraction, forecast, DP diagnostic, and full-game evaluation stage. It does not establish that price forecasting is the largest remaining source of competitive improvement or justify promoting the sales overlay.

## Reproduce and inspect

Use the existing `.venv/Scripts/python.exe`. Run, in order: `scripts/extract_market_opponents.py`, `scripts/market_corpus.py`, `scripts/evaluate_market_forecast.py`, `scripts/evaluate_market_sales.py`, `scripts/evaluate_market_deposits.py`, `scripts/evaluate_market_products.py`, `scripts/report_market_research.py`. Corpus and full-game runners resume saved games; manifests reject changed policies within a frozen experiment.

Artifacts: `results/fresh/market_research/` contains corpus, source/split manifests, forecast errors, DP diagnostics, individual audited games and `research_summary.json`. Source extraction manifests are in `data/public_candidates/`. Experimental policies are `agents/market_forecast.py` and the three `agents/market_sales_dp*.py` variants. They depend on the installed official engine and are research modules, not a packaged Kaggle submission.
