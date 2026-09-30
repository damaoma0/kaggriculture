# Shop prefixes, UMG coverage, and the 3000 target

Research date: 22 September 2026. This analysis uses existing replays. No new candidate qualification games or Kaggle submission were run.

**Subsequent update:** the [128-world current-m1 versus V56 survey](C:/Users/xyygl/Documents/kaggriculture/docs/v56_random_world_benchmark.md) has now completed: 177 wins / 79 losses in 256 games, with a 69.1% win rate (95% seed-clustered CI 61.3–77.0%). The eight-game coverage discussion below records the earlier state of evidence. The new production-plan continuation remains unqualified.

## 1. Required score against a 2750 opponent

Under the standard 400-point Elo model:

`expected score = 1 / (1 + 10 ** ((2750 - 3000) / 400)) = 0.8083176725`.

Score means win = 1, draw = 0.5, loss = 0. Thus a 3000-rated player would be expected to score **80.8% against a 2750-rated V56**. With no draws this is the win rate.

| Score against 2750 | Implied standard Elo |
|---:|---:|
| 60% | 2820 |
| 75% | 2941 |
| 80% | 2991 |
| 80.8% | 3000 |
| 85% | 3051 |
| 90% | 3132 |

The previous 60% promotion threshold demonstrated improvement over this opponent; it was insufficient for the stated 3000 goal. The separate [3000-target addendum](C:/Users/xyygl/Documents/kaggriculture/docs/continuation_3000_target_addendum.md) and `promotion_protocol_3000_v2.json` now require a mean score of at least 80.8% and a **clustered 95% lower confidence bound strictly above 80.8%**, while preserving the frozen original protocol and its other requirements. The practical planning target is roughly 90% observed over 128 independent worlds. Both seats are tested but clustered together.

For intuition only, with independent binary outcomes the two-sided Wilson 95% lower bound first exceeds 80.8% at 113 wins out of 128 (88.3%). This is not the benchmark's actual decision rule: the actual checker uses world-cluster bootstrap intervals and handles draws and seat differences.

The 2750 opponent rating is an assumption supplied in the question. Kaggle describes a final Bradley–Terry tournament and rating changes based on wins/losses/ties, without giving the exact 400-point Elo conversion on its evaluation text. Coin margin does not directly change rating updates. Therefore, this is a useful matchup target, not a guarantee of a 3000 leaderboard rating. Wider opponent coverage is still necessary. [Official Kaggriculture evaluation information](https://www.kaggle.com/competitions/kaggriculture/overview/citation)

## 2. Are we testing enough untaped worlds?

**No: we have substantial diagnostic replay data, but too few candidate-versus-V56 games.**

| Evidence | Independent worlds | What it establishes |
|---|---:|---|
| Existing unchanged-m1 V56 smoke run | 4, each played in both seats | 2 wins / 6 losses; all worlds lose an exact UMG prefix by day 12. Too small for qualification. |
| Historical m1 replay audit | 86 | Coverage and production analysis against the recorded ladder opponents; not a test of the new continuation against V56. |
| Planned natural qualification | 128 | Not run. Measures candidate and current baseline against frozen V56. |
| Planned original-UMG controls | 64 | Not run. These are known historical paths, not evidence of unseen-path performance. |

The four V56 world outcomes were identical between seats: **1 winning world and 3 losing worlds**. Mean cash margin was nevertheless +1,341, because the one winning world had a large margin. This illustrates why win score must be primary. These are results for unchanged m1, not the proposed continuation.

### Coverage against all 584 downloaded UMG tapes

These are empirical percentages in our 86 historical worlds, not estimates from an exhaustive uniform-world census. An exact shop prefix is only a necessary condition for replaying an exact tape; farm state, cash, crops, care, and other conditions can still differ.

| First shops | Reveal day | Exact ordered prefix available | Same composition, allowing different order |
|---:|---:|---:|---:|
| 1 | 3 | 86/86 (100%) | 86/86 (100%) |
| 2 | 6 | 86/86 (100%) | 86/86 (100%) |
| 3 | 9 | 57/86 (66.3%) | 85/86 (98.8%) |
| 4 | 12 | 7/86 (8.1%) | 73/86 (84.9%) |
| 5 | 15 | 1/86 (1.2%) | 53/86 (61.6%) |
| 6 | 18 | 0/86 | 35/86 (40.7%) |
| 7 | 21 | 0/86 | 26/86 (30.2%) |
| 8 | 24 | 0/86 | 12/86 (14.0%) |

By day 12, 79/86 worlds have no exact tape. Of those, **66 have a familiar shop composition in a different order**, and 13 have no matching composition either. This distinction matters: an order mismatch can still leave a useful production-plan donor, while a new composition requires more generalization.

First ordered-prefix break was day 9 in 29 games, day 12 in 50, day 15 in 6, and day 18 in 1. Historical final results by break bucket were:

| First missing prefix | Games | W / D / L | Mean cash margin |
|---|---:|---:|---:|
| Day 9 or earlier | 29 | 21 / 0 / 8 | +6,249 |
| Day 12 | 50 | 39 / 0 / 11 | +9,263 |
| Day 15 or later | 7 | 4 / 0 / 3 | +2,626 |

These are descriptive results against different historical opponents. They cannot establish that later tape loss causes better or worse performance, or tell us a V56 win rate. The five checkpoint observations per game also do not turn 86 games into 430 independent game outcomes.

### Evaluation coverage needed next

Retain the 128 natural-world panel for a representative win-rate estimate. Add a separately reported **128-world untaped stress panel**, selected without viewing outcomes:

- 64 worlds whose day-12 ordered prefix is absent but its shop composition is present in the frozen UMG corpus.
- 64 worlds whose day-12 composition is also absent.
- Balance the first shop across all eight types; run both seats and keep each world as one statistical cluster.
- Freeze the corpus hash and world list before tuning. Force the selected shop sequence only in the evaluation harness, revealing shops to agents at the normal times.
- Log actual fallback activation, donor/target selection, production error, invalid actions, runtime, final win score, and cash margin. Prefix absence alone does not prove that the intended new module ran.
- Run the candidate and current m1 on the same stress worlds. Report both strata and paired improvement separately from the natural-world score; deliberately oversampled rare worlds must not inflate the claimed natural win rate.

This extra panel is a concrete recommended quota. Its manifest and results are **not yet created**, and the integrated continuation has not qualified. The existing known-path UMG controls remain necessary for the separate requirement to improve over the original tapes.

## 3. How much of final production can the first shops predict?

![Shop-prefix prediction and tape coverage](C:/Users/xyygl/Documents/kaggriculture/results/fresh/shop_prefix_predictability/shop_prefix_predictability.png)

I interpret "first x shops determine y% of cumulative output" as **how much variation in whole-season production can be predicted using those shops**. The target is always the same final day-30 total, summing physical production over all ten three-day segments. It is not output already harvested by the reveal day, sales revenue, or units bought for resale.

The plotted percentage is `100 * (1 - model_squared_error / training_mean_squared_error)` on held-out episodes. A 77% score means 77% less squared prediction error than predicting the training-set average. It does **not** mean that 77% of output units are causally fixed or that we copy UMG with 77% accuracy.

| Shops known | Day | UMG: 105 games | Our m1: 86 games |
|---:|---:|---:|---:|
| 1 | 3 | 16.3% | 20.6% |
| 2 | 6 | 42.8% | 52.5% |
| 3 | 9 | 63.9% | 57.3% |
| 4 | 12 | **77.2%** | **58.8%** |
| 5 | 15 | 79.7% | 56.7% |
| 6 | 18 | **81.3%** | 54.0% |
| 7 | 21 | 78.8% | 51.3% |
| 8 | 24 | 76.3% | 43.4% |

At four shops, the conditional bootstrap intervals are UMG **73.0–80.7%** and m1 **53.2–63.9%**. At six shops, UMG is **78.2–84.3%**. These intervals condition on the fitted models and fixed split; they do not include all model-selection and training-data uncertainty.

### Product detail

![Prediction skill by product](C:/Users/xyygl/Documents/kaggriculture/results/fresh/shop_prefix_predictability/shop_prefix_products.png)

At four shops, UMG's product scores are wheat 65.6%, carrot 75.7%, tomato 69.3%, strawberry 86.3%, melon 13.7%, egg 91.5%, milk 83.9%, wool 82.0%, and fertilizer 23.5%. By five shops, wool reaches 94.0% and fertilizer 57.3%.

The main curve pools raw-unit squared errors, so products with more variable total quantities carry more weight. For UMG the largest weights are wheat 24.8%, carrot 22.5%, wool 15.6%, and egg 14.4%; melon has almost no weight. Giving every product equal weight yields **65.7% at four shops and 70.1% at six**, versus 77.2% and 81.3% on the main curve. We should not infer precise melon plans from the strong aggregate score.

### Method and limitations

- UMG uses 105 verified rich replays of submission 56266758. Our m1 uses 86 verified replays of submission 56395605. These are separate populations with different worlds and opponents; differences between the curves are not a controlled head-to-head or a direct measure of UMG proximity.
- At prefix x, input is a separate eight-category shop identity for every position 1 through x. Extending the prefix retains all earlier inputs. No farm state, opponent information, future shop, or match outcome enters prediction.
- Five outer folds hold out entire first-four-shop unordered compositions: 87 groups for UMG and 66 for m1. Ridge penalties are chosen using only grouped inner training folds, separately per product; predictions are clipped at zero. The alpha grid is 1, 10, 100, 1000, or a constant predictor.
- First-four composition defines the split even when only one to three shops are supplied as features. Later shops affect grouping, not input features. This evaluates generalization across withheld early compositions rather than random episode interpolation.
- Confidence bands use 2,000 paired episode-bootstrap samples of fixed out-of-fold residuals. This is exploratory analysis of our existing research corpus, not a new sealed gameplay qualification set.
- More observed shops cannot reduce the information available to an ideal predictor. The declines after the peak show finite-data/model-estimation limits. They do not show that later shops hurt the policy or do not matter.
- The initial counts-plus-weighted-exposure model is retained as `compressed_summary_metrics.json` for transparency. Its summaries are not nested across prefix length, so it is unsuitable as the primary marginal-information curve. The ordered-position method was declared in `ordered_method_addendum.json` before its run, and is used throughout this report.

## 4. Implication for continuation plans

The useful conjunction is at day 12: **exact tape coverage is only 8%, yet familiar composition coverage is 85%, and UMG's final production is already substantially predictable from the revealed shops.** This supports learning production targets that generalize across shop order, with an explicit correction for the farm we actually own.

Use an early-prefix prediction as a provisional production budget, then update it using newly revealed shops and remaining feasible harvests. Keep dated planting/animal investments and terminal crop/care state alongside cumulative targets; identical final totals do not specify when to produce or make an action schedule feasible.

The chart does not prove that our lower predictability causes losses, that copying those totals will beat UMG, or that a learned target can be scheduled profitably. Those claims require the full-season untaped-world comparisons above. It does, however, support the existing production-plan continuation direction without requiring millions of exact deterministic tapes.

## Reproduction

- Prediction: `scripts/research_shop_prefix_predictability.py`
- Coverage audit: `scripts/audit_untaped_world_coverage.py`
- Chart rendering: `scripts/plot_shop_prefix_predictability.py`
- Metrics, out-of-fold predictions, method declaration, chart summaries, and images: `results/fresh/shop_prefix_predictability/`
- Rating gate: `scripts/check_continuation_promotion.py --protocol results/fresh/tape_gap_plans/promotion_protocol_3000_v2.json`

The rating-gate regression tests use explicitly synthetic data. The chart and coverage analysis use real historical replays. Neither is a new candidate qualification result.
