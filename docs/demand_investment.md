# Demand-aware pasture investment study

## Conclusion

**Keep `agents/market_impact_selected.py` unchanged.** Completed **256 full-season evaluation games** across 32 seeds: 48 training, 96 held-out, 48 adverse-shop controls and 64 additional trigger-coverage games. This is a study of one purchase, not a complete herd optimizer or price forecaster.

The trained rule switches the turn-265 purchase from sheep to cow when at least two milk-consuming shops have already appeared. On the initial held-out panel it improved average cash by **420.5** and match margin by **305.5**, but changed the decision on only **one of eight seeds**. The original promotion gate therefore failed; unchanged choices were not counted as evidence of improvement.

Additional testing specifically covered that rule's trigger. It averaged **+911.5 match margin**, but only **+113.8 own cash**, and lost margin in **three of eight seeds**, with a worst individual loss of **4,291**. That small, variable sample is insufficient for promotion. No uploaded artifact was changed and no new submission was made.

## What this tells us

1. **Shop uncertainty matters at harvest time.** In the additional coverage panel, all three losing seeds later received at least two yarn stores. That is a descriptive pattern, not information available to the agent when it buys. Even a promising current milk market can lose to future wool demand.
2. **Supply matters alongside demand.** In development seed 129000, replacing sheep with cow added 20 milk units but only 20 total milk revenue; it removed 21 wool units and 4,552 wool revenue. These are whole-portfolio revenue differences, including effects on existing sales, not isolated animal price quotes.
3. **Own profit and winning margin can disagree.** Skipping sometimes increased our cash in training, but reduced margin in all 16 training cases. Producing less can also improve the rival's selling prices. On the held-out panel, always skipping reduced own cash by 2,592.1 and margin by 3,881.5 relative to sheep.

The next valuation model should simulate independent future shop sequences conditioned on revealed shops, both farms' supply, and the actual delivery calendar. It should report expected own cash, expected margin and downside separately. These paired continuations now provide ground truth for testing that model. A binary “shop absent, don't invest” rule is not supported by this experiment.

## Scope

Change only the last planned pasture purchase at turn 265 (day 11): sheep, cow, or skip. Preserve the opening, routes, hiring and static market-order policy. A cow follows the same service route; skipping suppresses that animal’s pickup, placement, feed and care. No labor savings or terminal livestock salvage are assumed. Results use actual full-game cash, including feed, price effects on existing herds, capacity and subsequent router choices.

## Frozen decision rule

`{"feature": "MILK_demand", "threshold": 1.5, "left": "SHEEP", "right": "COW"}`

A single split was fitted on eight development seeds covering all first shops, both seats against the selected agent. Only currently revealed demand and prices can enter the rule. It was frozen before the held-out runs. This is an empirical investment policy, not a calibrated price forecaster.

## Results

| Panel | Choice | Cases | Cash gain vs sheep | Margin gain vs sheep | Worst margin change | Cash gain vs skip |
|---|---|---:|---:|---:|---:|---:|
| train | SHEEP | 16 | +0.0 | +0.0 | +0 | +712.0 |
| train | COW | 16 | -1174.4 | -1674.4 | -4829 | -462.4 |
| train | SKIP | 16 | -712.0 | -2280.1 | -4858 | +0.0 |
| train | learned | 16 | +156.0 | +257.0 | +0 | +868.0 |
| train | oracle | 16 | +189.4 | +291.2 | +0 | +901.4 |
| test | SHEEP | 32 | +0.0 | +0.0 | +0 | +2592.1 |
| test | COW | 32 | -2361.6 | -2884.0 | -5028 | +230.5 |
| test | SKIP | 32 | -2592.1 | -3881.5 | -5320 | +0.0 |
| test | learned | 32 | +420.5 | +305.5 | +0 | +3012.6 |
| test | oracle | 32 | +432.8 | +317.1 | +0 | +3024.9 |
| stress | SHEEP | 16 | +0.0 | +0.0 | +0 | +1088.0 |
| stress | COW | 16 | -1165.2 | -1184.4 | -5148 | -77.2 |
| stress | SKIP | 16 | -1088.0 | -1379.4 | -5567 | +0.0 |
| stress | learned | 16 | +0.0 | +0.0 | +0 | +1088.0 |
| stress | oracle | 16 | +133.2 | +112.8 | +0 | +1221.2 |
| test_selected | SHEEP | 16 | +0.0 | +0.0 | +0 | +2487.7 |
| test_selected | COW | 16 | -2313.8 | -2758.8 | -4966 | +173.9 |
| test_selected | SKIP | 16 | -2487.7 | -3625.2 | -5242 | +0.0 |
| test_selected | learned | 16 | +426.6 | +341.9 | +0 | +2914.3 |
| test_selected | oracle | 16 | +439.2 | +353.8 | +0 | +2926.9 |
| test_sixday | SHEEP | 16 | +0.0 | +0.0 | +0 | +2696.6 |
| test_sixday | COW | 16 | -2409.5 | -3009.2 | -5028 | +287.1 |
| test_sixday | SKIP | 16 | -2696.6 | -4137.8 | -5320 | +0.0 |
| test_sixday | learned | 16 | +414.4 | +269.1 | +0 | +3110.9 |
| test_sixday | oracle | 16 | +426.2 | +280.5 | +0 | +3122.8 |

The oracle chooses with hindsight and is only an upper bound for this one decision. Cases across choices, seats and opponents share seeds; they are not independent samples.

## Uncertainty and checks

- All variants within a seed use identical hidden shop schedules. Training covers all eight first shops; held-out schedules use independent uniform draws with replacement. Stress panels deliberately exclude wool demand, milk demand, both, or repeat a single shop. Stress frequencies are not natural probabilities.
- At turn 265, three shops are revealed and five draws remain. If yarn has not appeared, its chance of remaining absent is (7/8)^5 = 51.3%; if no milk shop has appeared, milk-shop absence is (5/8)^5 = 9.5%. Existing shops continue consuming; town-center demand remains.
- Both seats and two held-out opponents are tested. Every sheep control must match the current selected agent action-for-action. Every non-skip alternative must reach its pickup and placement with an animal in inventory. Both final cash ledgers must reconcile and all 720 states must complete.
- Shop draws are controlled because engine weed generation and shop selection share random state. Farm-dependent weeds still follow the engine. Only one investment and a small seed panel are studied; this does not establish an optimal herd policy.
- Future information is used only to score counterfactual outcomes, never as a decision input. The held-out oracle is not deployable.

## Decision

Frozen promotion gate: FAIL; retain the current selected agent. No Kaggle submission was made by this study.

## Additional trigger coverage

The initial held-out result prompted a separate coverage check, with the original rule and promotion gate left unchanged. Before running it, we selected the first eight seeds starting at 132000 whose first three shops contain at least two milk shops. Selection used shop draws only, never game outcomes. Later shops remained hidden and independently drawn. Each seed ran both seats against the selected agent and the public six-day router, comparing sheep and cow: **64 additional games**.

| Opponent | Paired cases | Own cash gain | Margin gain | Worse cases | Worst margin change |
|---|---:|---:|---:|---:|---:|
| Current selected agent | 16 | +54.7 | +809.3 | 6 | -3,988 |
| Public six-day router | 16 | +172.9 | +1,013.6 | 6 | -4,291 |
| Combined | 32 | +113.8 | +911.5 | 12 | -4,291 |

Five seed-average changes were positive and three negative. This deliberately enriched sample measures performance **when the rule fires**; its average cannot be interpreted as the gain across naturally sampled games. The conditional manifest records the seed-selection rule and source hashes.

The initial rule was scored by selecting the appropriate completed counterfactual branch from each identical predecision state. Because there is only one decision and all its inputs match across branches, this is equivalent to applying the frozen rule at that decision. The additional panel executes the cow branch in every case because its trigger is guaranteed by panel design. It is not a new fitted policy.

All **256** evaluations completed 720 valid states and reconciled both cash ledgers. All non-skip alternatives reached pickup and placement with the intended animal. The **96 sheep controls** matched the submitted agent across **69,024 action comparisons**. The selected agent's SHA-256 remains `216ed6a3857187cbd7803e50e033069af0c6bdb88ddf4ffbc879b4b49cbb4c6b`.

## Reproduction

Run `scripts/research_demand_investment.py train`, then `scripts/report_demand_investment.py fit`; run the `test` and `stress` panels, then `scripts/report_demand_investment.py report`. Data and frozen rule: `results/fresh/demand_investment/`.

Run `scripts/confirm_demand_investment.py` for the supplemental coverage panel and `conditional_summary.json`. The report generator reproduces the initial tables; the conclusion and supplemental interpretation above were added after that frozen analysis.
