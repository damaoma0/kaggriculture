# What the leader matrices imply for production-plan imitation

## Recommendation

**Correction after auditing submitted `mgt_t10`:** choosing coherent UMG tapes by demand and board compatibility is already implemented. The diagnostic below compares simple output predictors, not the existing v10 router, and establishes no improvement over that submission. A new direction must generate or adapt production decisions for unseen conditions rather than merely repeat nearest-tape selection. See `docs/leader_policy_size_and_next_directions.md`.

Build a library of coherent UMG production continuations indexed by the current farm and revealed demand. Retain Majkel and M & M & P & Q as alternative plan families, selected only when their starting requirements fit. Compare complete plans before attempting combinations. The newest shop alone is an inadequate index, and pooled product-wise ranges are unsuitable as an executable target.

This conclusion concerns the September 17 recorded submissions and our UMG-derived starting state; it is not a claim about today's leaderboard or a proven competitive improvement. No agent was changed or submitted.

## Findings from the verified replays

The sample has 76 farm trajectories from 52 matches: UMG 56266758 (30), Majkel 56216119 (30), Majkel 56156662 (8), and M & M & P & Q 56254996 (8). Two included farms in one match are not independent worlds.

### Calendar and crop cohorts account for much of the immediate movement

Strawberry output increased at day 15 in every one of the 76 recorded farms, despite all eight possible shop types appearing. In UMG's day-18 records, a Farmers Market corresponds to a median increase of 17 strawberries (five farms), while other shops correspond to +18 (25 farms). These comparisons do not identify a causal shop effect.

The conspicuous +120 tomato change after a day-24 Yarn Store belongs to M & M & P & Q, episode 109756255, seat 0. Tomato output rose from 2 to 122. That farm had planted 23 tomatoes in days 15–17 and three in days 18–20, before the new shop. Yarn Store demands wool. The earlier tomato commitment is the relevant plan evidence.

### Leaders have different schedules that should be kept intact

Median within-game strawberry output changes:

| Submission | Day 15 | Day 18 | Day 21 | Day 24 |
|---|---:|---:|---:|---:|
| UMG 56266758 | +36 | +18 | +20.5 | −13.5 |
| Majkel 56216119 | +30.5 | +30.5 | −23.5 | −25.5 |
| Majkel 56156662 | +34 | +34.5 | −19.5 | −24.5 |
| M & M & P & Q 56254996 | +24 | +14 | +10.5 | −16 |

On day 21, UMG increases strawberry output in 22/30 games; Majkel 56216119 decreases it in 30/30. The earlier planting study records UMG adding a mean 10.6 strawberry plants from day 12 onward versus 4.5 for Majkel. These are distinct cohort schedules. Averaging their next-period output targets can conceal the planting and retirement decisions necessary to reach either one.

The earlier event study also found demand-associated changes in carrot, tomato and strawberry planting after new shops. Immediate harvested quantities and new planting decisions are different measurements; the matrices do not contradict that adaptation. See `docs/leader_segments.md` section 3a. Exact code-level decision rules remain unknown.

## Small held-out imitation diagnostic

Question: using only information available at a reveal, how accurately can a candidate method predict the recorded UMG farm's next three-day harvested output?

There are 120 test periods from 30 UMG games at days 15, 18, 21 and 24. Every test episode, including both seats, is excluded from donor candidates. Candidates share the same date. No future shop or final score ranks a candidate. The target period finishes before the next reveal.

The two median baselines predict the typical change and add it to the farm's previous-period output. Donor methods return one recorded farm's complete nine-product next-period output vector. They do not average incompatible individual products.

| Predictor | Mean absolute error, units per product per period |
|---|---:|
| UMG calendar median change | 6.33 |
| UMG calendar + newest-shop median change | 7.46 |
| UMG donor matched by cumulative revealed demand only | 8.53 |
| UMG donor matched by board, crop ages and previous output | 5.66 |
| UMG donor matched by those state features plus demand | 5.85 |
| All-leader donor library with the same state + demand matching | 5.85 |

The all-leader method chose UMG in all 120 cases. This gives no evidence that simply expanding the donor pool improves imitation from UMG states. The state-only donor error is 10.6% lower than the calendar baseline; uncertainty has not been quantified and no hyperparameters were tuned to maximize this result. Giving demand equal feature-group weight did not improve next-period imitation here. This is plausible because much of the immediate output is already committed; it does not establish that demand is unimportant for later planting or profit.

Distance is standardized absolute difference, averaged within each feature group and then equally across groups. Scales are fit using only the remaining UMG training examples, with a minimum of one unit. Features: current cumulative demand, standing crop/animal/empty/weed counts, crop ages in three-day buckets, and previous output. Animal ages, precise crop ages, routing, care status, inventories, prices and conversion costs remain omitted.

This is a diagnostic of predicting historical production, not a game benchmark or proof that a copied plan is reachable. The test hides episodes, not entire shop-history families. Mean absolute error weights products equally, not by value. Both the 30-game sample and model comparisons are small. Results must not be reported as win-rate or profit improvements.

## How to turn the evidence into a useful fallback

1. At the uncovered shop branch, describe the actual farm: crops and exact ages, herd and production phase, held output, inventories, available land, inputs, care obligations and current revealed demand. Preserve the current viable production commitments.
2. Retrieve several coherent donor continuations from compatible states. Use the donor's whole output, planting, care and retirement trajectory as a candidate; do not select each product's upper bound independently.
3. Check reachability and labor/input costs. Cash by day 12 can fund changes but cannot instantly provide mature crops or extra worker visits. Protect the harvest already funded by prior planting.
4. Plan to season end, execute the near-term portion, and update after the next reveal. A recorded donor suffix contains later decisions conditioned on its own future shops, so it is a conditional scenario rather than advance knowledge of our future world.
5. Start with UMG-compatible plans. Compare alternative Majkel or M & M & P & Q plans only when the expected benefit covers conversion and care costs. A mix should first mean choosing among coherent plans; simultaneous crop-plan combinations require a shared feasibility check.
6. Separate validation: reproduce a held-out donor plan from its recorded state; then follow it from our actual handover state; finally compare profit and wins in live-opponent tests on held-out shop histories. Compare UMG-only selection against all-leader selection and the current router.

The next implementation milestone is a state-aware plan selector and a feasibility report for each proposed whole-farm continuation, followed by the executor. This remains the corrected whole-production-plan mission, not another isolated crop substitution.

## Artifacts

`results/fresh/production_continuation/plan_imitation_analysis.json` contains the individual held-out predictions, donor identities, product errors and calendar summaries. `imitation_observed_features.json` stores crop age features read from the already verified replays. Reproduce with `scripts/analyze_plan_imitation.py`. Source matrices and per-version breakdowns are in `docs/leader_shop_matrices.md`.
