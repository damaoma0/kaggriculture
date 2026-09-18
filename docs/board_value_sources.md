# Public research used for board valuation

Reviewed 2026-09-15. These are external research reports, not instructions or
verified rankings. No external agent code was downloaded or incorporated.

## Official rules and engine

[Kaggle environment README](https://github.com/Kaggle/kaggle-environments/blob/master/kaggle_environments/envs/kaggriculture/README.md)

The season ends at a cash-only terminal objective. Crop age, finite production
cycles, shared nonlinear prices, and shed capacity make purchase-cost valuation
inadequate. The installed 1.32.7 interpreter is the executable authority for our
experiments; documentation prose alone is not treated as an exact specification.

Applied: continue through the real final action; include crop ages and stored
inventory in the checkpoint; let the engine enforce prices, action ordering,
care, feeding, storage, and final rewards.

## Keep the existing policy as a control

[Sellesta research log, N77-N78](https://github.com/Sellesta/Kaggriculture/blob/main/HISTORICAL_AGENT_COMPETITIONS_2026-08-21.md)

The author reports that choosing among a small set of coarse continuation plans
can fail because the established policy was absent from the candidates.

Applied: include native continuation for both original agents and restore each
agent's internal state by replaying its past observations. Verify that this
warmup reproduces its recorded actions. Common maintenance policies and native
policies are reported separately: controller quality affects estimated value.

## Labour, storage, and liquidity

[Seyamalam findings](https://github.com/Seyamalam/Kaggriculture/blob/main/docs/findings.md)

This report is pinned to engine 1.32.3, older than ours. It describes maintenance
failures from inadequate operating cash, storage losses, and seeds bought too
late to produce. Its measured scores are not transferred to our evaluation.

Applied: record labour spending, seed purchases, terminal unsold goods, and
premature crop/animal losses; test different crew caps. Seed and land purchase
costs are not credited at the end of the season.

## Coupled production and market execution

[amerob analysis](https://github.com/amerob/kaggriculture)

The author describes how changes to inventory sales can disrupt feeding and
fertilizer pickup, and how increased labour can exceed added crop revenue.
Broad claims about markets always being undersupplied are scenario-dependent.

Applied: run both farms together through the official engine and account for
successful transactions, rather than pricing requested sales at a static quote.
Replanting and expansion have their operating costs deducted. Market risk is
tested by changing the other farm's continuation as well as the future seed.

## What this first evaluator does not establish

It is an offline exact-private-state audit, not a live hidden-inventory model.
Future scenarios have equal weights by experimental choice, not because those
weights have been calibrated to the leaderboard. Results are achievable outcomes
under specified policies and sampled futures, not the optimal game-theoretic
value of a board. A policy that fails to service an asset can undervalue it.
