# Cumulative production forecasts and whole-farm plan reconstruction

## Conclusion

**The forecasting step now works substantially better on unseen UMG shop combinations. The inversion step can generate new whole-farm schedules, but it is not yet a validated in-game executor.**

The strongest result is near-term prediction. Against a shop-count-and-reveal-timing model, the frozen system reduces mean absolute error by **53.9% for the next three days**, **34.7% for the next six days**, and **11.7% for the rest of the season**. It generates quantities from the current observation; it does not choose a recording and return that recording's output.

The production compiler uses actual engine mechanics to turn those quantities into crop cohorts, harvest dates, animal commitments, input requirements and tile assignments. Timed targets substantially improve the reconstructed production schedule. The remaining gaps are economically sensible target selection, richer service schedules, and actual worker/order execution.

Nothing was submitted to Kaggle. `agents/mgt_m1.py` remains unchanged.

## 1. Evidence and experimental separation

The expanded corpus contains **151 verified leader trajectories**:

- UMG submission `56266758`: **75 development games and 30 held-out games**.
- Majkel1337 `56216119`: 30 reference games.
- Earlier Majkel `56156662`: eight reference games.
- MMPQ `56254996`: eight reference games.

A separate random sample contains **16 of our archived v10 ladder games**, from a population of 141. It is used only to check transfer from UMG to our policy.

Every included replay was replayed with the official installed engine. Both seats' farms, private state, market and town matched the recording at **all 720 states**, and the cash ledger reconciled. Production labels count positive inventory changes inside successful `HARVEST` and `COLLECT_FERTILIZER` actions. They exclude purchases and sales. Harvested wheat subsequently fed to animals still counts as gross wheat production; fertilizer subsequently applied still counts as collected production.

The UMG test contains 30 distinct first-four **unordered shop-count combinations**, all absent from development. Development has 57 such combinations. There is no train/test overlap in match, seed, or first-four composition. Selection used identities and shop prefixes, without filtering on score or output. This is a deliberate test of generalization to missing branches, although it does not cover every possible world or current leader version.

Model families, regularization and residual widths were selected from development only. Episode-grouped nested cross-validation keeps each game together. A second grouped diagnostic excludes complete first-four compositions. The final model choices were frozen before the reported test results were inspected.

Protocol bookkeeping: an earlier delayed default-path development command wrote a mixed report into the working output directory. Only its record counts/model identifiers were inspected. It was replaced by the verified train-only freeze before test metrics were examined. The final freeze hashes `dataset_train.json`; its timestamp precedes the final test report. The later correction to normalized test scores changed their denominator to saved training dispersion, not predictions or model selection.

The planning experiments are **diagnostics**, not another sealed forecasting test. Their 10 episodes, three checkpoint days and target ablations were selected before the forecast results. Mechanical corrections and a later economic guard are reported separately below.

## 2. The prediction system

At days 12, 15, 18, 21 and 24, predict all nine products at three horizons:

1. Next three days.
2. Next six days.
3. All remaining days through day 29.

Endpoints are exclusive. A day-12 three-day prediction counts actions on days **12–14**, before the next shop reveal. Add already observed production to obtain a cumulative season total.

Six candidate models were compared: shop counts; counts plus reveal timing; each product's own revealed demand; state-aware ridge regression; state regression with capacity interactions; and nearest-state donor output. Features available at the checkpoint include:

- Revealed shops and their arrival times.
- Own and opponent crop counts, crop-age buckets, held yield, watering/fertilizer condition.
- Animal ages, held output, care banks and feeding condition.
- Seeds, inventory, shed, cash and visible market quantities.
- Cumulative production so far and production in the previous three days.

All feature scaling is fitted within training folds. Product-normalized error prevents high-volume wheat from dominating model selection. For deployment, negative increments are clipped and an elementwise cumulative maximum enforces `next3 ≤ next6 ≤ end`. This is a simple coherence rule, not least-squares isotonic regression. Baselines receive the same rule in the independent comparison.

The selected model depends on the horizon: **capacity interactions win 12 of 15 cells**, shop counts plus timing win the day-12 and day-15 season-end forecasts, and state regression wins one cell. This is useful evidence for a two-part interpretation: existing commitments strongly determine the immediate harvest, while visible demand remains informative about longer-term choices.

### Held-out improvement

Mean absolute error is measured in **units per product**, averaging the five checkpoint days. Percentages refer to prediction error, not cash or win rate.

| Horizon | New system MAE | Error reduction vs counts + timing | Vs own-product demand | Vs nearest-state donor |
|---|---:|---:|---:|---:|
| Next 3 days | 2.27 | **53.9%** | 69.2% | 63.0% |
| Next 6 days | 5.90 | **34.7%** | 58.4% | 57.9% |
| Remaining season | 15.93 | **11.7%** | 43.2% | 56.3% |

The episode-bootstrap 95% intervals for improvement over counts + timing are approximately **49.0–57.9%**, **29.0–39.9%**, and **7.5–15.6%**, respectively. Complete episodes are resampled, preserving dependence across their products and checkpoints. These are sampling intervals for this held-out panel, not guarantees about all future opponents.

![Held-out forecast comparison](C:/Users/xyygl/Documents/kaggriculture/results/fresh/cumulative_planning/forecast/forecast_comparison.png)

Season-end MAE by checkpoint is **24.83, 20.40, 15.07, 12.15 and 7.15**. At day 24 the errors are wheat 17.37, carrot 14.82, tomato 4.06, strawberry 7.21, melon approximately zero, egg 3.89, milk 5.44, wool 6.40 and fertilizer 5.13. Low overall error does not mean every product is equally predictable.

This does **not** establish superiority to the actual v10 router's chosen tape. The donor comparator here is a nearest-state predictor on the labelled training corpus. Our archived router uses a larger tape library and a different selection rule.

A separate **post-analysis mechanics baseline** services the assets already on the board using exact engine profiles, establishes no new cohorts and applies no additional fertilizer. Its MAE is **4.10, 20.50 and 68.92** at the three horizons, versus **2.27, 5.90 and 15.93** for the frozen model. This baseline was not used to select or tune the model. It confirms that current commitments explain much of the near-term harvest, while continued planting and service choices matter; its long-horizon deterioration is expected because it never replants.

### Uncertainty and transfer

The empirical per-product residual bands attain roughly **86–94% marginal coverage**, depending on checkpoint and horizon. However, **all nine products simultaneously** fall inside their respective bands in only **37–70%** of cases. A collection of marginal bands is not a joint safe production plan. These widths also reuse out-of-fold residuals after model selection; they are descriptive, not exact conformal intervals.

On our random 16-game v10 panel, the same UMG model has season-end MAE **29.26, 30.42, 20.06, 16.91 and 11.08**. Transfer is materially worse. This test measures prediction of v10's recorded behavior, not what UMG would counterfactually produce from a v10 farm. Neither interpretation permits treating a learned UMG target as automatically reachable or profitable on our board.

![Transfer to v10](C:/Users/xyygl/Documents/kaggriculture/results/fresh/cumulative_planning/forecast/domain_transfer.png)

The other leaders remain separate. Majkel's 30-game, train-only diagnostic gives season-end out-of-fold MAE 34.17 down to 11.42 over days 12–24. The two eight-game versions are too small for reliable comparisons. Those error levels do not rank the quality of their game policies: sample sizes and production distributions differ.

## 3. Why cumulative totals do not uniquely identify a plan

Let `x[j]` be the integer number of cohorts following schedule `j`. A schedule specifies asset type, establishment day, care/fertilizer policy, harvest dates and tile release. Let `A[p,h,j]` be the output of product `p` produced before deadline `h` by that schedule.

Reconstruction solves approximately:

`sum_j A[p,h,j] × x[j] = target[p,h]`

subject to daily land, labor, inputs and cash constraints. Existing assets must select exactly one legal service schedule. Under/over variables record target discrepancies.

With only one deadline, many different cohort schedules have identical output totals. For example, wheat can be harvested early at lower yield and replanted, or kept longer for more yield per seed. Tomato and strawberry totals can come from differently dated cohorts, producing different gaps during the season. Multiple deadlines remove some ambiguity; they cannot recover unique coordinates, worker paths or the leader's private objective.

The implementation minimizes total absolute target error, then uses small tie-breaks favouring fewer new cohorts and less procurement. This is **quantity reconstruction**, not profit maximization.

## 4. What the production compiler actually implements

Production columns call the checked-in engine's unit actions, decay and nightly refresh on native tile snapshots. Six relevant mechanics functions were compared structurally against the installed engine and match. Tests cover all five crops and three animals, fertilized/unfertilized output, current held yield, dry streaks, care banks, early harvesting and exclusive endpoints.

Useful verified details:

- Unfertilized wheat and carrot yield at most **4 and 3** under the tested complete growth schedules; fertilized versions reach **6 and 4**.
- Tomato and strawberry can yield **4 unfertilized or 8 fertilized units** over their productive lives if harvested in time to avoid the held-output cap.
- Melon can reach **six units at age 10**; age 12 is its final growth day, not a mandatory waiting period.
- Animal output includes accumulated care from earlier days. Today's care is banked after tonight's production; it cannot boost that same refresh.
- Existing productive assets are preserved. The compiler may choose different harvest ages, fertilizer use, care, and fertilizer collection. It cannot silently delete an animal to free land.
- One-time harvest and ongoing-crop cleanup release land for reuse the following day. This deliberately excludes same-day harvest/replant.

Shared constraints include:

- Owned usable tiles and each cohort's occupied interval; existing weeds/empty structures are reserved.
- Daily service actions with **30% of raw action capacity reserved** for travel and handling in the experiment.
- Eleven hires per day: **276 raw actions normally, 264 on day 29**. Hires reset nightly and incur Fibonacci costs.
- Seed stock/purchase caps, integer feed/fertilizer purchases, and daily cumulative feed/fertilizer balance.
- Starting cash funding all counted purchases and hires; **no future sales are credited**. Seed/animal prices use engine constants; feed/fertilizer purchases are conditional on the checkpoint price quotes.
- At most two added animals of each type in this diagnostic. No land expansion.

Every solved plan has daily input/output/work tables and a concrete allocation of its cohorts to non-overlapping farm coordinates. This proves interval allocation, **not worker routing**. Intra-day delivery, the 100-unit shed limit, market order sequencing, future weeds and paths remain unresolved. The 30% reserve is an assumption, not an empirical routing guarantee.

## 5. Reconstruction experiments

Ten preselected UMG test episodes were evaluated at days **12, 18 and 24**, yielding 30 starting states. Each was solved three ways:

1. Forecast season-end quantities only.
2. Forecast next-three, next-six and season-end quantities.
3. Actual future quantities at those deadlines, supplied as an explicitly labelled hindsight oracle.

All initial **90 solves reached optimum within this schedule family**. Arithmetic checks passed for land, actions, seed/feed/fertilizer balances, cash, exact-one preservation and target accounting. Coordinate allocation succeeded for every plan.

Adding timed targets reduced error against the full timed forecast vector by **42.5%** compared with end totals alone. The episode-bootstrap interval was **36.9–47.7%**. This measures the value of timing constraints, not the accuracy of either forecast or actual executed production.

### An important failure found and resolved

The first example bought a sheep on day 28 solely to match one extra fertilizer unit, despite having no time to produce wool. That was legal within the quantity objective and economically unconvincing. It exposes a real limitation of literal imitation: a small target error can justify a bad purchase when money has no sufficient penalty.

The final compiler therefore excludes new animals that cannot produce their **primary good** before season end. This guard was added after inspecting the diagnostic. Both the initial results and the guarded rerun are retained; the rerun is not presented as a new sealed validation.

The guarded 90 solves also all reached optimum and passed the independent checks. Their results are:

| Starting day | End-only plan error against all timed forecasts | Timed plan error against same forecasts | Oracle-plan error against actual timed production |
|---:|---:|---:|---:|
| 12 | 5.06 | **2.16** | 1.92 |
| 18 | 4.99 | **2.73** | 2.60 |
| 24 | 3.23 | **2.22** | 1.66 |

Units are mean absolute product error per included deadline. The guarded timed-vs-end-only reduction is **46.5%** (diagnostic episode-bootstrap interval **42.6–50.8%**). At day 24, next-six and season-end are the same deadline and are counted once.

**No plan matched every target exactly.** This must not be interpreted as proving the targets impossible in the game. The hindsight targets came from real successful replays, so their residual error demonstrates restrictions in our schedule family, such as daily care patterns, collection timing, same-day replanting and a fixed workforce. The compiler certifies its own aggregate constraints; it does not enumerate all legal play.

### Concrete generated continuation

The first preselected example is episode **109780145 at day 12**. Its farm holds 19 wheat, 21 strawberries, two melons, ten cows, four sheep and three geese; available model land is 73 tiles, with **$16,073** cash.

The guarded plan preserves those assets, adds 11 wheat and three strawberries on day 12, seven strawberries on day 13, and three wheat, two tomatoes and one goose on day 14. It schedules subsequent wheat/carrot cycles and small fruit additions through day 27. The forecast target is generated from the checkpoint; no future shops or recorded movements are supplied to this planner.

Counted procurement plus all remaining hires costs **$6,866**, including **$4,176** in hires. It needs no purchased wheat or fertilizer under the aggregate flow assumptions. Peak reserved land is 73; peak service workload uses about 77% of the already travel-reduced capacity. The full timed target MAE is **1.89 units per product/deadline**. This is a candidate allocation to execute and replan, not a command tape or a recommendation to commit today to every late-season choice.

![Generated production plan](C:/Users/xyygl/Documents/kaggriculture/results/fresh/cumulative_planning/plans/example_production_plan.png)

## 6. What this changes about the strategy

The evidence supports **a compact conditional forecast plus constrained replanning**, rather than requiring a separate complete recording for every future shop history.

The practical policy should preserve current commitments, use the relatively accurate next-three-day prediction as its immediate target, use longer horizons as softer guidance for slow crops, and recompute after each shop reveal. It should not average independent product targets and assume the result fits the farm.

The major unresolved layer is now concrete: compile the selected daily commitments into worker visits, input distribution, harvest delivery and orders, then measure their output/cash in the engine. The oracle residual also suggests adding more service/collection schedules before interpreting all prediction-to-plan deviation as forecast failure.

After execution is reliable, target selection should be judged by the consequences of decisions—cash, production shortfalls and repair cost—not prediction accuracy alone. This follows the distinction developed in [Smart “Predict, then Optimize”](https://arxiv.org/abs/1710.08005). That paper motivates the direction; its SPO training method was **not implemented here**. The uncertainty limits under changing policies/shop distributions are also consistent with the need for explicit assumptions in [Conformal Prediction Under Covariate Shift](https://arxiv.org/abs/1904.06019); this study does **not** claim its coverage guarantees.

### Resolved versus still unproven

| Question | Result |
|---|---|
| Can state improve cumulative forecasts beyond shops alone? | Yes, especially over the next 3–6 days, on this held-out UMG panel. |
| Can a compact model predict previously unseen early shop combinations? | Yes; the exported fitted artifact is about **0.60 MiB**, with no test labels or future shops. |
| Can cumulative targets generate new whole-farm commitments? | Yes; integer cohort plans, resource schedules and tile allocations were constructed. |
| Do end totals uniquely recover UMG's strategy? | No; timed targets help substantially, and residual ambiguity remains. |
| Can the current compiler exactly replicate UMG? | No; even hindsight targets retain small errors in the restricted schedule family. |
| Does it beat v10 or UMG in games? | Untested. Forecast gains and aggregate target tracking are not game performance. |
| Is this ready to upload? | No; routing, order/storage execution and live-opponent evaluation remain. |

## 7. Reusable artifacts and reproducibility

Main code:

- `scripts/research_cumulative_forecast.py`: grouped fitting, frozen evaluation and reference studies.
- `scripts/cumulative_trajectory_model.py`: compact model export and coherent `predict_trajectory(model, checkpoint)` API.
- `scripts/cumulative_engine_profiles.py`: exact per-tile production schedules.
- `scripts/cumulative_plan_solver.py`: integer production-plan compiler.
- `scripts/evaluate_cumulative_planning.py`: initial and guarded diagnostics.
- `scripts/check_cumulative_plan_certificates.py`: independent arithmetic and mechanics-identity audit.

Results under `results/fresh/cumulative_planning/` include the frozen data manifest, corpus audit, `forecast/trained_model.json`, all per-game forecast predictions, initial/guarded plan cases, paired summaries, coordinate assignments and figures. The exported API was checked against **450 forecast vectors / 4,050 product values**, with maximum numerical difference approximately `1.14e-13`.

The planner can be called through `compile_checkpoint(checkpoint, targets, **resource_policy)`, where each target has a product, units and either an absolute exclusive `day` or `horizon` (`3`, `6`, or `"end"`). Supply explicit workforce and procurement limits. A nonzero target discrepancy is returned as a discrepancy; routing feasibility remains `null`.

The retained research files distinguish original and guarded results. Re-running a new model-selection experiment should use a new output directory and a fresh held-out sample; this test set has now been inspected.
