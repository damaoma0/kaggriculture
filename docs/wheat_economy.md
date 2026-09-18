# Wheat economics and production choices

## Findings

**The newer agent converts wheat and farm labor into cash more efficiently.** On the fresh panel V45 beats our control 16/16 with mean margin +11,136; its wheat net-cash advantage is +4,225 per game. This advantage survives a different gross-sales breakdown from the previous panel.

- **Economic feeding is a consistent contributor:** enabling discretionary feed skipping adds +1,458 margin against ours and +1,452 against Two Coins. It frees about 56 wheat per game, mostly for sale, while the measured total cash gain includes lost animal-product value.
- **Shop-dependent production matters competitively:** full routing adds +2,308 margin against ours and +3,113 against Two Coins relative to fixed route 0. Own-cash changes are -635 and +54; much of the margin effect comes from the opponent's changed outcome. This is a total interaction effect, not proof of a deliberate sabotage tactic.
- **The newest route portfolio gives a smaller, variable increment:** forcing the older V39 shop lookup costs 883 / 1,288 margin on average, with unchanged routing in two seeds. Most wheat profitability is shared by both portfolios: their wheat net-cash difference is small.
- **Small purchase trimming is low priority:** it loses about 18 margin per game here. It removes purchases that would mostly have been sold later; fewer purchased units alone do not establish a benefit.
- **Extra fertilizer tours explain a measurable yield gain:** the follow-up measures +39.8 wheat and +1,261 margin against ours; see the diagnostic results below for costs and the second opponent.

**Accounting correction:** the earlier panel's wheat advantage appeared mainly in higher sale revenue. Here V45 sells fewer units and earns less gross wheat revenue, but spends much less on purchases. Most of the gross purchase-volume gap occurs in early buy/sell round trips that nearly cancel in cash. The net advantage mainly appears later: about 3,105 in turns 432–695. Gross sales or purchase totals by themselves are unreliable efficiency scores.

## What to build on

Use a modern conditional router as the working baseline and keep the uploaded agent as a historical control. Preserve economic feeding and profitable crop-input planning. Evaluate production choices by paired winning margin as well as own cash. The next development target is a joint short-horizon input planner that values extra crop output, feed, fertilizer and worker time against delivery deadlines; test it against several modern rivals on new shop draws. The eight-seed fertilizer follow-up needs independent confirmation before tuning or promotion. Tiny replenishment and terminal tweaks are lower priorities on this evidence.

## Design

192 games: eight new seeds (136000–136007), both seats, two reactive opponents (our submitted control and Two Coins), six V45 variants. All policy comparisons share identical shop sequences, drawn uniformly with replacement and hidden until revealed. Both seats share the same random world; the independent sample is eight seeds.

The wheat audit observes only real engine execution, excluding internal policy simulations. It tracks harvests, product purchases, feeding, sales, discarded wheat and final inventory. The conservation equation holds after every turn: **initial + harvested + bought = sold + fed + discarded + remaining**. Wheat seeds are accounted separately. A repeated previous full-agent game reproduces its exact cash, complete product ledgers and shop sequence.

All other V45 layers remain enabled. No feeding disables only discretionary economic feed skipping, not normal feeding. No trimming disables only the day-index-10/11 replenishment reduction. Older expert uses the V39 first-two-shop lookup for every pair; it retains the newer overlays. Fixed route uses route 0 until turn 647, then the normal terminal route 2; other reactive overlays still run. Neither route intervention recreates our original five-tape agent.

## Paired effects

Positive values mean the full policy is better than the disabled variant. These are total effects, including later production, prices and opponent reactions; they are not additive.

| Opponent | Variant | Wins / 16 | Variant mean margin | Full margin gain | Full own-cash gain | Seeds helped / hurt / tied |
|---|---|---:|---:|---:|---:|---:|
| selected | full | 16 | +11,136.2 | +0.0 | +0.0 | 0 / 0 / 8 |
| selected | no_feed | 16 | +9,678.6 | +1,457.6 | +1,447.0 | 7 / 1 / 0 |
| selected | no_trim | 16 | +11,153.9 | -17.8 | -14.6 | 0 / 6 / 2 |
| selected | no_feed_or_trim | 16 | +9,693.9 | +1,442.3 | +1,434.0 | 6 / 2 / 0 |
| selected | old_expert | 16 | +10,253.1 | +883.1 | +756.1 | 3 / 3 / 2 |
| selected | fixed_route | 14 | +8,828.0 | +2,308.2 | -635.1 | 5 / 3 / 0 |
| twocoins | full | 16 | +7,417.4 | +0.0 | +0.0 | 0 / 0 / 8 |
| twocoins | no_feed | 16 | +5,964.9 | +1,452.5 | +1,382.0 | 8 / 0 / 0 |
| twocoins | no_trim | 16 | +7,435.3 | -17.9 | -15.5 | 0 / 6 / 2 |
| twocoins | no_feed_or_trim | 16 | +5,978.8 | +1,438.6 | +1,369.4 | 8 / 0 / 0 |
| twocoins | old_expert | 16 | +6,129.0 | +1,288.4 | +825.3 | 5 / 1 / 2 |
| twocoins | fixed_route | 12 | +4,304.4 | +3,113.1 | +54.2 | 7 / 1 / 0 |

## Full V45 versus our submitted agent: wheat flow

| Metric, average per game | V45 | Ours | Difference |
|---|---:|---:|---:|
| harvest | 584.62 | 538.25 | +46.38 |
| bought | 183.75 | 341.88 | -158.12 |
| sold | 458.62 | 516.00 | -57.38 |
| fed | 306.88 | 352.62 | -45.75 |
| discarded | 2.88 | 8.88 | -6.00 |
| remaining | 0.00 | 2.62 | -2.62 |
| planted | 161.12 | 171.50 | -10.38 |
| sale_revenue | 16,906.62 | 17,581.12 | -674.50 |
| purchase_cost | 6,213.38 | 10,896.50 | -4,683.12 |
| seed_cost | 1,630.00 | 1,846.25 | -216.25 |
| Wheat net cash (sales − product purchases − seeds) | 9,063.25 | 4,838.38 | +4,224.88 |

Pooled sale price per wheat unit: V45 36.86, ours 34.07. A symmetric arithmetic decomposition attributes -2,035.0 of the gross sale-revenue difference to quantity and +1,360.5 to average realized price. This is an accounting identity, not a causal sale-timing estimate: production and both players' trades also change market prices.

Wheat is fungible. Gross sales include purchased-and-resold stock; harvested units cannot be assigned unique sale revenue without an arbitrary inventory convention. The net cash and physical flow identities avoid that assumption.

## When the wheat advantage arises

| Turns | V45 minus ours: harvest | Feed | Bought | Sold | Wheat net cash |
|---|---:|---:|---:|---:|---:|
| 0–71 | +0.0 | +0.0 | -144.0 | -143.0 | +67.0 |
| 72–215 | +0.0 | +0.6 | +5.0 | +3.0 | -1.5 |
| 216–431 | +3.5 | -8.1 | -17.2 | +1.6 | +810.6 |
| 432–695 | +76.6 | -38.2 | -1.9 | +73.2 | +3,104.6 |
| 696–718 | -33.8 | +0.0 | +0.0 | +7.8 | +244.2 |

## Mechanism coverage

| Opponent | Variant | Feed skips | Wheat units trimmed | Route differs from full / 16 |
|---|---|---:|---:|---:|
| selected | full | 56.6 | 9.8 | 0 |
| selected | no_feed | 0.0 | 9.8 | 0 |
| selected | no_trim | 56.8 | 0.0 | 0 |
| selected | no_feed_or_trim | 0.0 | 0.0 | 0 |
| selected | old_expert | 59.6 | 9.8 | 12 |
| selected | fixed_route | 58.4 | 13.0 | 16 |
| twocoins | full | 56.0 | 9.8 | 0 |
| twocoins | no_feed | 0.0 | 9.8 | 0 |
| twocoins | no_trim | 56.1 | 0.0 | 0 |
| twocoins | no_feed_or_trim | 0.0 | 0.0 | 0 |
| twocoins | old_expert | 58.9 | 9.8 | 12 |
| twocoins | fixed_route | 59.8 | 13.0 | 16 |

## What each mechanism changes in our own wheat economy

Full minus variant. Negative feed means the full policy consumed fewer units. Wheat net cash excludes labor, land and animal-product effects; compare it with the total cash gain above.

| Opponent | Disabled mechanism | Harvest | Feed | Bought | Sold | Wheat net cash |
|---|---|---:|---:|---:|---:|---:|
| selected | no_feed | -2.6 | -56.6 | -0.2 | +51.4 | +1,666.1 |
| selected | no_trim | +0.0 | +0.1 | -9.2 | -9.4 | -14.7 |
| selected | no_feed_or_trim | -2.6 | -56.6 | -9.2 | +42.4 | +1,653.1 |
| selected | old_expert | -5.9 | +1.8 | +0.5 | -3.4 | -81.7 |
| selected | fixed_route | -9.6 | -1.8 | -2.2 | -4.1 | -1.1 |
| twocoins | no_feed | -1.6 | -56.0 | -0.2 | +52.8 | +1,682.9 |
| twocoins | no_trim | +0.0 | +0.1 | -9.2 | -9.4 | -15.6 |
| twocoins | no_feed_or_trim | -1.6 | -56.0 | -9.2 | +43.8 | +1,670.2 |
| twocoins | old_expert | -6.0 | +1.6 | +0.5 | -2.0 | -40.2 |
| twocoins | fixed_route | -13.0 | +0.2 | -2.2 | -8.0 | -120.3 |

## Crop-cycle trace and fertilizer-planner follow-up

Sixteen repeated full-agent games reproduced the original cash, product ledgers and per-turn wheat flows. They additionally record each successful wheat harvest's age and yield.

| Harvest metric, average per game | V45 | Ours |
|---|---:|---:|
| Successful harvest actions | 161.12 | 169.88 |
| Units per successful harvest | 3.63 | 3.17 |
| Harvests yielding 5–6 units | 34.88 | 0.00 |

V45's extra crop-input planner forecasts native watering and harvest times, estimates fertilizer's marginal yield, and searches short worker tours. It includes fertilizer purchase price, labor, warehouse capacity and a cash reserve before committing. Wheat/carrot tours are separate from the tomato investment.

After observing the yield difference, a further 32 games disabled these extra fertilizer tours. This is an adaptive diagnostic on the same eight-seed panel, not independent confirmation or removal of all native fertilizer use.

| Opponent | Planner margin gain | Planner own-cash gain | Extra wheat harvested | Seeds helped / hurt / tied |
|---|---:|---:|---:|---:|
| selected | +1,261.1 | +1,099.1 | +39.8 | 8 / 0 / 0 |
| twocoins | +1,654.6 | +1,373.8 | +44.5 | 8 / 0 / 0 |

Selected cost and revenue changes from enabling the planner (averages; all other downstream effects are included in final cash above):

| Opponent | Wheat revenue | Carrot revenue | Fertilizer revenue | Extra fertilizer cost | Extra labor cost |
|---|---:|---:|---:|---:|---:|
| selected | +1,283.8 | +895.8 | +242.7 | +456.0 | +575.6 |
| twocoins | +1,400.8 | +887.2 | +233.2 | +478.4 | +597.9 |

All 32 follow-up games passed the same cash and per-turn wheat checks; disabled planner hires were zero. Together with the one initial instrumentation check, this study ran **241 full games** (192 main + 16 cycle repeats + 32 follow-up + 1 check). Follow-up runner: `scripts/check_crop_input_planner.py`; cycle tracer: `scripts/trace_wheat_cycles.py`.

## Validation and limits

All 192 games completed 720 valid states. Both cash ledgers reconcile; wheat conservation was checked after every executed turn. Frozen source hashes match. Disabled feed/trim counters are zero and fixed-route choices are verified. Nonzero telemetry error counters: 0.

This is a diagnostic study on eight new shop sequences, not a calibrated leaderboard prediction or exhaustive coverage of all 64 first-two-shop pairs. Keeping other overlays active measures these mechanisms inside the current V45 system. It does not identify the isolated quality of raw action tapes. No agent was promoted or submitted.

Reproduce: `scripts/research_wheat_economy.py --smoke`, `scripts/research_wheat_economy.py`, then `scripts/report_wheat_economy.py`, using the project virtual environment. Raw per-turn wheat flows, paired results and source hashes: `results/fresh/wheat_economy/`.
