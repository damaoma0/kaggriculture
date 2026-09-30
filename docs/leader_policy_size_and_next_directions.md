# Beyond mgt_t10: policy reconstruction and size reasoning

## Correction: the existing submission already retrieves compatible leader tapes

The user referred to v10; the archived submission is `submissions/2026-09-19-mgt_t10/main.py`, Kaggle submission 56368334. It is 4,752,454 bytes and contains 584 UMG recordings. Its router re-ranks at day starts by revealed demand at historical checkpoints and tile-label compatibility, with a board-distance term. Feed guard, care top-up, orphan adoption and a market-gated sheep expansion program supplement replay.

The previous recommendation to choose a UMG continuation by current demand and farm similarity largely repeats that design. The recent 120-period diagnostic tested output-vector prediction against simple baselines, not v10, and cannot be cited as an improvement over it. Crop-age-aware matching is a real omitted feature, but would still be a tape-selector refinement, not a new production strategy.

The remaining structural limitation is the inability to generate an arbitrary new, feasible whole-farm plan for the actual board. Recorded commands depend on the donor's tile layout and timing. The prior frozen m1 study found compatible candidates collapsing around days 15–18; forcibly switching to the correct recording after the boards diverged was harmful. That motivates a production policy that can issue new commitments and a scheduler that can execute them on the current farm.

## What can be inferred from branching and the file limit?

Kaggle's published competition overview specifies a 100 MiB submission limit: https://www.kaggle.com/competitions/kaggriculture/overview/citation (checked September 21).

After k reveals, ordered shop histories number 8^k. Counts of eight shop types, ignoring their reveal order, have C(k+7,7) possibilities. Direct enumeration of the game's demand vectors agrees with those composition counts through eight reveals.

| Day | Ordered histories | Shop-count compositions |
|---|---:|---:|
| 12 | 4,096 | 330 |
| 15 | 32,768 | 792 |
| 18 | 262,144 | 1,716 |
| 21 | 2,097,152 | 3,432 |
| 24 | 16,777,216 | 6,435 |

This is a count of input histories, not a count of different plans or code branches. Counts alone do not encode crop ages, earlier price paths or previously committed investments, so they are not a proven sufficient state for the policy.

Three illustrative encodings:

1. One independent full recording per final shop history, at our observed average of roughly 8,138 bytes per recording including shared code/data: naive linear extrapolation gives about 127 GiB. This is not a lower bound: sharing and compression can change marginal storage radically.
2. A four-byte plan identifier for each of the 16,777,216 final histories occupies 64 MiB. An entire eight-level tree including all intermediate prefixes and the root has 19,173,961 nodes: four bytes per node requires about 73.14 MiB, leaving roughly 26.86 MiB for shared plans and code. Child indexes can be implicit in a complete eight-way tree. The online lookup uses only the revealed prefix, so it need not read future shops. This illustrates that millions of indexed histories are not themselves impossible; whether adequate shared plans fit is a separate question. The example is a storage calculation, not an implemented policy.
3. A small rule program can branch on shop counts, calendar and live farm state, and calculate actions as needed. Such a program may represent millions of outcomes without enumerating them. Runtime computation and archive compression also separate submitted file size from expanded state size.

The limit provides an upper bound on submitted bytes, not an identifiable estimate of UMG's actual bytes, effective branching factor, or architecture. Deterministic actions do not establish lookup-table implementation. Finite recordings are compatible with many program structures.

## Research directions that go beyond selecting a recording

### 1. Learn a compact conditional production policy

Use demonstrated whole-farm commitments as labels: plants established by crop and day, herd additions, retirements, productive crop ages and the remaining harvest schedule. Inputs must be restricted to information already observed: stage, revealed demand, existing commitments and available resources. Represent the outputs jointly under land and labor constraints.

Fit compact phase-based rules or small decision trees and penalize unnecessary branches. The objective is to explain many recordings with the same rule and predict held-out shop-history families. Infer a default seasonal schedule plus conditional changes to the remaining plan. Earlier 30-game hand-fitted rules are hypotheses, not a completed general policy; scale and validate them against the wider 584-recording corpus, keeping submissions distinguishable.

If similar farm states and aggregate demand reliably share the same next commitments despite different shop order, merge those cases. If prediction fails, find the missing state variable rather than adding a tape ID. A rule/parameter program can then produce targets for a combination never recorded. This is the preferred next research milestone. The full-plan executor remains a separate necessary step.

### 2. Infer the tradeoffs behind leaders' choices

Construct feasible alternative whole-farm plans at recorded decision points. Fit a small objective model so the demonstrated choice scores well: product value, available demand, worker time, land occupancy, input cost, maturity delay and penalty for flooding a market. This is inverse planning: learning what tradeoffs explain behavior.

Solve for a new plan on our board with those learned tradeoffs. It can generalize beyond observed quantities. Leader decisions need not be optimal, and inferred objectives are not unique; judge this on held-out choices and then game outcomes. This is substantially more work than rule fitting and requires a credible feasibility model.

### 3. Optimize a small family of flexible whole-season schedules

Define a low-dimensional plan family: early herd mix; day-12 allocation of freed land; the size and timing of the next strawberry/tomato cohorts; the late wheat/carrot transition; and reserve land/worker capacity before the next reveal. Optimize these commitments jointly across many possible future shop sequences and multiple live opponent styles.

Recompute the remaining plan after each reveal, preserving valuable existing cohorts and accounting for the opportunity cost of reserved capacity. Copying a leader's style supplies a starting family; simulation evaluates the choice, including its price impact and execution cost. This differs from tuning a tape router or inserting isolated crop modules. Approximate dynamic programming or scenario-based optimization is appropriate once the state and executor are dependable.

## Recommended first experiment

Compare compact policy models using (a) full revealed shop order, (b) aggregate counts, and (c) counts plus actual crop/herd commitments and phase. Predict joint planting/retirement/production targets on held-out shop-history groups. Track predictive error, feasibility violations and model description size together. Do not use future revealed shops in model inputs or treat a recorded remainder as an unconditional future plan.

The useful question is how many distinct decision rules or plan families are needed to explain and generalize the observed behavior. This is estimable by held-out compression/prediction tests; the hidden submission's exact byte size is not.
