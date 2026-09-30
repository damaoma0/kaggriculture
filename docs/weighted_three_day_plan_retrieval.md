# Weighted retrieval of three-day leader production plans

Proposal, 22 September 2026. This is a new experiment design, not an implemented or benchmarked policy.

## What changes

Current `mgt_m1` chooses raw action tapes daily. It compares cumulative product demand at fixed shop-count checkpoints `(2, 4, 5, 6, 8)`, with fixed product weights, a small common-prefix preference, a board mismatch constraint, and an animal-stranding penalty. Thus it already measures demand history, but does not learn a separate early-versus-recent weighting or execute an independently compiled three-day production plan.

The offline nearest-continuation study instead retrieves three-day production targets from 105 full-state UMG runs. Its ranking is lexicographic: shop-count replacements, asset-count difference, committed output difference, board labels, then shop order. Later components cannot compensate for a worse earlier component. It is not a fitted weighted distance and is not in the submitted m1.

The proposed change is to choose a **whole-farm three-day plan** at each reveal and compile it against our own state. The window is `[day, day+3)`, with a final replan at day 27 even though no new shop appears then.

## Retrieval distance

Use nonnegative weights and comparable scales:

`distance = current_demand_distance + a*early_history_distance + b*recent_reveal_distance + c*farm_state_distance + switching_cost`

- **Current demand:** the demand induced by all currently open shops, expressed per product; this retains persistent demand from early shops rather than pretending they expire.
- **Early history:** the shop identities/demand trajectory through the first four reveals, using only reveals already observed. This helps identify the investments inherited from the opening.
- **Recent reveal:** the latest shop, or a short decaying history of the last two reveals, to identify the immediate adjustment the donor made.
- **Farm state:** productive asset counts, ages, held yields, stored animal-care bonuses, expected three- and six-day output from existing assets, inventories, and available cash. Near-term output alone can hide different future cohorts.
- **Switching cost:** additional investment and lost commitments needed to connect our state to the candidate plan. Retain the current plan unless the alternative clears this cost.

Normalize components using training data only. Fix the current-demand coefficient to one, so overall scale is not an extra meaningless parameter. Begin with three tunable relative weights and a fixed switching rule, rather than a different free weight for every shop, day, and product. Equal/current weighting, early-heavy, recent-heavy, and balanced settings form interpretable controls.

Early shops partly predict production because they created the current farm. Once current cohorts and inventory are represented well, some early-history information may be redundant. The earlier 77% shop-only predictive score is not a reason to hard-code a large early weight. Include an ablation with the early-history term removed while retaining farm state.

Current prices and visible rival inventory/production can rank or reject the few finalists by projected value. They need not all become new independent search knobs immediately. No future shops, future opponent actions, or donor final outcome enter the observation-side query.

## What a plan contains

A three-day harvest vector alone is insufficient. Store together:

1. Daily harvested/collected quantities.
2. Daily plantings, animal purchases/placements, buildings, fertilizer and servicing commitments.
3. Inputs, cash requirements, land, labor, and delivery needs.
4. Ending crop ages, remaining harvests, animal care/held yield, and usable inventory.

Retrieve only the donor's plan for the same game stage and the next three days. Its actions were produced against another opponent and another market path, so treat them as historical behavior, not a guaranteed open-loop continuation.

Adjust its output target using the already investigated rule:

`our target = max(0, maintained_output(our farm) + donor_observed_output - maintained_output(donor farm))`.

Then preserve feasible donor investment/servicing intentions and project them onto our resources. Buying a cow now cannot replace milk due tomorrow from a mature donor cow. Plans with unaffordable entry requirements or harmful terminal commitments should be rejected or shortened; an infeasible target should not trigger repeated purchases or destructive rebuilding.

The labor scheduler can rearrange a supplied feasible action window. The missing production-to-jobs adapter remains necessary for genuinely changed investment plans. Weighted retrieval by itself does not supply that adapter.

## Stitching across leaders

Start with one coherent donor per window. At the next reveal, select a new compatible donor using the actual resulting farm state. Require affordable entry conditions and a useful ending state at every join.

Keep leader and submission version attached to each window. Similar shop history is not enough to combine one leader's intensive crop plan with another's large animal herd: they may spend the same tiles, wheat, workers, fertilizer, and cash. Blending the highest output of each product independently can create a physically impossible plan.

A short look-ahead over two compatible windows can later penalize bad terminal states, but the second window must use scenarios for unrevealed shops rather than the donor's recorded future. Begin with measured connection costs and one-window selection before adding that complexity.

## Collect more useful data

The immediate gap is **584 compact UMG action tapes versus only 105 UMG full-state production donors**. More compact tapes are not automatically more usable production plans. Expand verified full-state windows, preserving both sides' actions, native checkpoint states, input/output ledgers, and submission version.

Refresh current leaderboard and public episode metadata first. Prefer a bounded initial batch of about 50 additional UMG runs and 25 runs from each of two other strong, behaviorally distinct leaders, subject to availability. Include completed wins and losses. Select by missing shop-composition coverage, useful cohort differences, recency/version, and opponent strength, without cherry-picking large final cash totals.

Deduplicate whole episodes and repeated production trajectories. A hundred near-identical opening branches add less than a smaller number of genuinely new day-15/18/21 farm states. Archive enough native state to reconstruct crop maturity and care; board labels alone lose those fields. Public replay download and the organizer's daily top-episodes resource are possible sources, with access checked before promising a batch.

### Live public inventory checked this turn

The Kaggle API returned the following on 22 September 2026. The chosen submission is each team's highest-scoring currently public submission, not necessarily its most recently uploaded one.

| Team | Selected submission | Score snapshot | Completed episodes returned |
|---|---:|---:|---:|
| DSM | 56444344 | 3124.4 | 108 |
| Vadim Vasilenko | 56443671 | 3085.0 | 112 |
| Majkel1337 | 56424800 | 3069.3 | 159 |
| Unknown Mother-Goose | 56417993 | 3042.4 | 179 |

These counts describe the API response window, not guaranteed complete history; they are submission-specific entries and may overlap in episode IDs. No new raw replays were downloaded or production-verified in this inventory step. The listing confirms candidates to fetch, not successful extraction of their production plans.

Our existing rich corpus also already has 30 Majkel1337 runs from submission 56216119, eight from its earlier submission 56156662, and eight M & M & P & Q runs from 56254996, alongside 105 UMG runs. Those can support an initial compatibility study, but should not be pooled silently with the newer versions above.

Snapshots: `results/fresh/leader_library_refresh_20260922/leaderboard.json` and `inventory.json`. Reproduction: `scripts/inventory_current_leaders.py`. [Public leaderboard](https://www.kaggle.com/competitions/kaggriculture/leaderboard).

## Controlled evaluation

Compare:

| Arm | Purpose |
|---|---|
| Current m1 | The executable baseline: 69.1% versus frozen V56 on the completed 128-world survey. |
| UMG production plans with fixed retrieval | Isolates the effect of the plan representation and compiler. |
| Same plans with weighted retrieval | Isolates the effect of early/recent/state weights. |
| Weighted retrieval with a larger UMG library | Measures additional coverage. |
| Weighted retrieval with multiple leaders | Measures cross-leader stitching. |

First validate held-out next-three-day output, establishment decisions, and terminal state, excluding the query episode and related duplicate trajectories. Group holdouts by early shop composition; do not train on another checkpoint from the same held-out run. Predicting our own imperfect behavior is not the primary objective: use leader imitation for representation checks and actual game outcomes for policy selection.

Tune a small fixed set of weights on development worlds, then freeze the candidate and evaluate on fresh random seeds, both seats, against V56 and additional opponents. The completed 128-world m1 survey is now exposed and is useful for regression analysis, not a fresh final test for settings chosen after inspecting it. Report first missing tape day and novel-composition strata, plus execution failures and runtime. Keep the original-UMG controls separate.

The first success criterion is a reproducible gain over current m1 with the same library. More downloads and better imitation error alone are not evidence of a stronger policy.
