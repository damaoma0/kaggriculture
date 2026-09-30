# Filling UMG tape gaps from the nearest production plan

Research run: 22 September 2026. Primary policy: m1, submission **56395605**.

## Conclusion

Start with a **nearby whole-farm plan adjusted for our actual crop and animal cohorts**. A missing shop sequence is not, by itself, evidence that the production plan needs changing. Preserve useful commitments, estimate the remaining harvest from the actual board, and change the future planting calendar only where a concrete difference calls for it.

The first experiment supports this representation. It does **not** establish a stronger playing policy or a leaderboard improvement.

## What was measured

- Replayed all **86 m1 recorded games**, both players' actions, with their recorded shop paths. All 86 matched recorded final cash and every daily shop prefix. These compact records do not contain full original observations, so this is not an independent every-state comparison.
- Retained **430 native checkpoints** at days 12, 15, 18, 21 and 24, with physical production, current crop ages/yields, animal state, inventories, cash and public market state.
- Used all **584 compact UMG tapes** to check shop-prefix availability. Used **105 full-state UMG games from submission 56266758** for the age/yield-aware comparisons. The latter is a smaller donor pool, not all 584 tapes.
- Kept older t10 (**56368334**, 141 games) separate. It was inventoried but not pooled into the m1 results.
- Delegated corpus reconstruction, independent audits and pilot compilation to the existing GPT-5.6 agents.

Donor selection uses only the current revealed shops and current farm. Its fixed ordering is shop-count replacements, productive asset-count difference, modeled near-term production difference, tile-label difference, then revealed-shop order. Episode IDs break ties; rewards and later shops do not enter the selection. An exact ordered prefix is missing in **422/430 checkpoints**; this is a history-coverage definition, not proof that every available continuation is unusable.

Native age, held yield and care enter through the modeled production signature. This is not an exact match of every cohort field: two young crops that produce nothing in the next three days can still have different later calendars. Cash and inventory are checked during compilation, not used as a hard filter in this first retrieval experiment.

## The smallest differences are useful controls

### Day 12: a missing sequence can require zero production change

Our episode **111317319**, compared with UMG episode **110059839**:

- Same revealed shop multiset, different order; our full ordered prefix is absent from the 584-tape library.
- Same productive asset counts, same tile-label layout, same modeled next-three-day production from existing assets.
- Both actually plant **15 wheat and 12 strawberries** during days 12–14.
- Both harvest/collect exactly **72 wheat, 12 eggs, 21 milk, 19 wool and 53 fertilizer**, with zero output of the other four products.

This is a control case where an imitation system should preserve the production plan. Replanning merely because an exact branch is missing could make it worse.

### Day 15: adjust for missing cohorts without reconstructing the past

Our episode **111296485**, compared with UMG **110372518**, has one fewer cow and one fewer strawberry plant. Both still plant **13 wheat, 7 carrots and 3 tomatoes** over days 15–17. The cohort-adjusted target differs from our observed output by only **2 wheat, 1 strawberry and 1 milk** across all nine products.

This suggests retaining the common investment calendar and adjusting its expected output for the actual cohorts. Buying an animal now cannot recreate output from a mature animal that was established earlier.

### Similar current output can hide a different future plan

At day 21, our episode **111324137** plants **36 wheat and no carrots** over the next three days; its selected UMG donor plants **22 wheat and 17 carrots**. Much of the immediate output still comes from inherited animals and mature crops.

Therefore a continuation needs two linked descriptions:

1. Harvest/collection quantities by deadline.
2. Planting and herd establishment dates, with the resulting cohort state at the next reveal.

Matching only the first description can miss the decision responsible for later divergence. These differences alone do not tell us which calendar earns more.

## A tested way to transfer production targets

For the next three days, use:

**Target = our maintained-cohort output + (UMG observed output − UMG maintained-cohort output)**

Clip each product at zero. The maintained-cohort calculation uses actual native tile state through the checked-in engine mechanics, with routine watering/feed/care, no new cohorts and no additional fertilizer. It simulates six days and sums the first three, so the artificial forecast horizon does not stop care prematurely.

The donor residual includes its harvesting schedule, fertilizer decisions, short crop cycles and other behavior omitted by the simple maintained-cohort calculation. It is a statistical adjustment, not a guarantee that the requested units are reachable. The whole-farm compiler must project the target onto available resources and existing cohorts.

Historical donor output is used only for **[day, day + 3)**, before the next shop reveal. Longer targets use the previously frozen cumulative forecaster on our current checkpoint; later donor shop outcomes are not transferred. The forecast is policy-conditional and remains uncertain when applied to our different farm.

### Agreement with our observed next-three-day production

Mean absolute error in units **per product**, equally weighting all nine products, among checkpoints without an exact ordered UMG prefix:

| Day | Cases | Copy donor output | Adjust for our cohorts | Previous frozen forecast |
|---|---:|---:|---:|---:|
| 12 | 79 | 2.16 | **1.14** | 1.51 |
| 15 | 85 | 5.37 | **1.75** | 2.01 |
| 18 | 86 | 8.46 | **2.37** | 2.62 |
| 21 | 86 | 11.45 | **3.25** | 3.33 |
| 24 | 86 | 13.20 | **4.36** | 4.49 |

This measures how well a representation describes our recorded behavior. Our existing behavior is not an optimality label. Smaller error does not establish higher profit, and zero-heavy products and wheat/fertilizer have the same unit weight as sale products here.

An independent paired bootstrap resampling whole episodes estimates an overall reduction of **0.213 units/product** versus the frozen forecast, with a 95% interval of **0.056–0.370**. The separate day-18, day-21 and day-24 intervals include zero; the evidence for improvement over that forecast is strongest early. The improvement over direct copying is much larger: **5.632 units/product**, interval **5.184–6.097**.

The same residual rule was also checked on the previously used 30 UMG test games, using only the 75 development donors and excluding the query's first-four-shop composition. Per-day next-three-day errors were **1.09, 1.70, 2.22, 2.79 and 3.59**, versus **1.80, 5.08, 8.30, 9.97 and 11.97** for direct nearest-donor copying. This is a diagnostic on an already exposed test set, not a fresh blind validation.

![Production differences](/C:/Users/xyygl/Documents/kaggriculture/results/fresh/tape_gap_plans/production_differences.png)

The chart reports signed differences, which can cancel across games; use the absolute-error table to assess prediction agreement.

## Ten whole-farm planning cases

Selected two missing-prefix cases per day using the frozen current-state matching rule, with distinct own episodes. Compiled two variants per case: the frozen forecast alone and its next-three-day component replaced by the residual-transfer target. Longer cumulative targets are raised only if necessary to remain monotone.

All **20 solver runs reached optimal status** and passed independent aggregate checks for land, work, cash, seed/feed/fertilizer flow, existing-cohort preservation and target arithmetic. Tile interval assignments were materialized. Funding uses current cash only, 11 hands per day, a 30% travel reserve, current resource quotes and at most two added animals of each species.

All 20 retain some target slack. They are resource-consistent projections within a restricted calendar model; they are not exact reproductions of every requested unit. The two variants optimize different target vectors, so their respective target errors are not a common performance benchmark. These plans have not been routed or tested as complete playing policies.

## Direct continuation test in the engine

As a separate control, replaced our own action stream with the selected donor's entire three-day window in each of the ten cases. Our checkpoint history, recorded opponent actions and shop path stayed fixed. All ten baseline production vectors matched the recorded ledgers, and every donor window matched its independently stored compact tape action-for-action.

| Start day | Own episodes | Change in cash at window end |
|---|---|---:|
| 12 | 111317319 / 111271925 | +282 / +63 |
| 15 | 111296485 / 111253835 | −53 / +77 |
| 18 | 111259496 / 111240681 | −1,095 / −3,582 |
| 21 | 111324137 / 111294229 | +196 / −1,787 |
| 24 | 111263986 / 111324547 | −4,595 / −913 |

These are cash-at-checkpoint differences, **not full-season profit or win-rate results**. Terminal inventory, investments, market timing and surviving assets can differ; the opponent is a fixed recorded stream.

The closest day-12 control reproduced our production exactly across all nine products and had no terminal asset-count deficit. Its +282 cash breaks down as **89 fewer wages + 200 fewer wheat purchases − 7 wheat sale revenue**. However, it ended with one less wheat in the shed and **one less stored care bonus on each of two cows**. Those bonuses affect later production. It is not a state-equivalent saving, despite identical immediate harvests. This is a concrete reason to preserve terminal cohort/care state as well as output.

At day 18, direct reuse reduced wheat output by **33 and 38 units** in the two cases. At day 21, one borrowed continuation ended with **three fewer cows, three fewer sheep and one fewer goose** than our baseline. Counts alone do not distinguish deaths from changed acquisition/retirement choices, but they establish that this was no longer the same physical continuation.

**Interpretation:** close production plans can be reusable when exact shop histories are missing. The later action paths are not reliably reusable. A target/calendar-to-job bridge must service our real cohorts and coordinates; a better nearest-tape selector by itself is insufficient.

## What this says about the scheduler interface

The new labor module has strong evidence for **rearranging an already executable supplied plan**. Its current public API takes 48 concrete actions. It extracts successful jobs and keeps establishment routes containing planting/building/placing fixed. It does not yet accept arbitrary production targets and synthesize all prerequisite purchases, placements and routes.

See [the scheduler contract](/C:/Users/xyygl/Documents/kaggriculture/docs/tape_gap_scheduler_contract.md). For a new continuation, the remaining bridge must supply dated jobs and verify their execution from our actual state. The successful fixed-plan scheduler results cannot certify a changed production calendar.

## Recommended continuation design

1. **Use a zero-change control first.** Where revealed demand, cohorts and planned investments match, retain the existing calendar and allow the scheduler to improve its execution.
2. **Preserve current cohorts explicitly.** Predict remaining production from age, held yield, care and fertilizer state; do not attempt to make up missing historical cumulative output.
3. **Borrow a complete nearby investment calendar.** Use the donor's next-reveal planting/herd calendar as a reference, with timed output targets and a next-reveal cohort-state target. Penalize changes to this reference instead of freely replacing it with a different calendar that happens to match output totals.
4. **Expose the smallest necessary change.** Report the changed planting dates/counts, added animals, input budget and expected harvest delta. Recompile required whole-farm work together so preserved jobs are not displaced by an isolated overlay.
5. **Reconsider at each new reveal.** Execute only the near-term commitment; use later forecasts to guide investments, not as a fixed suffix that assumes donor future shops.
6. **Compare policies only after the bridge is executable.** First validate jobs and protected assets in the engine, then compare against unchanged m1 across both seats, diverse shops and reacting opponents. Recorded-opponent continuations remain diagnostic.

Prioritize the day-12 and day-15 neighborhood first. Under this matching rule the median productive asset-count L1 difference is **4, 11, 18, 20.5 and 24.5** across the five checkpoint days. Later donors are materially farther away even when the revealed shop multiset matches; calling those cases a small tape repair would be misleading.

## Reproducible artifacts

- `scripts/analyze_own_umg_tape_gaps.py`: reconstruct own checkpoints and compact donor candidates.
- `scripts/research_nearest_continuation.py`: frozen matching, residual targets, evaluation and chart.
- `scripts/compile_nearest_continuation_plans.py`: paired whole-farm calendar compilation.
- `scripts/audit_tape_gap_pilot.py`: independent aggregate certificates.
- `scripts/test_nearest_donor_windows.py`: ten exact-engine, three-day action-transfer controls.
- `results/fresh/tape_gap_plans/local_transfer_protocol.json`: fixed selection and evaluation rules.
- `results/fresh/tape_gap_plans/dataset_primary.json`: reconstructed m1 corpus.
- `results/fresh/tape_gap_plans/local_transfer_analysis.json`: every checkpoint and comparison.
- `results/fresh/tape_gap_plans/local_transfer.json`: ten concrete checkpoint/target inputs for the compiler.
- `results/fresh/tape_gap_plans/pilot/`: complete calendar plans, tile allocations, costs and audits.
- `results/fresh/tape_gap_plans/nearest_donor_windows.json`: complete engine control results, including action-alignment assertions and the corrected dictionary-based cash reads.
- `results/fresh/tape_gap_plans/zero_difference_economics.json`: the production-identical control's exact terminal farm/private states and economic decomposition.

No competition agent or submission was changed by this research.
