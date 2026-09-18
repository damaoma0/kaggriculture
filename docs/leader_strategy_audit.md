# Current leader: whole-season strategy audit

## Conclusion

The strongest research direction is **production allocation and the worker schedule that supports it**, rather than another small opening or sale-order adjustment. The leader changes its crop mix much more throughout the season than our V45 baseline. However, the challenger beating it in these matches uses a different, larger farm successfully. We should learn the decision principles, not copy the leader's board or impose its land limit.

We have not established that V45 is a local optimum. The evidence identifies a structural restriction worth relaxing: many of its crop counts and transitions remain tied to fixed routes and dates, even when later market conditions differ.

## Current standing and sample

Kaggle snapshot retrieved September 16, 2026:

- Rank 1 **Majkel1337**, team 16718819, leaderboard score **3187.0**; active submission **56156662** also showed 3187.0. Its newer active submission 56216119 showed 3180.4.
- Rank 2 **M & M & P & Q**, leaderboard score **3114.5**.
- Rank 3 **DSM**, leaderboard score **3089.0**.

Rankings move. Source: [Kaggriculture leaderboard](https://www.kaggle.com/competitions/kaggriculture/leaderboard). Raw CLI snapshots are `results/fresh/current_leader_board.csv`, `current_leader_submissions.csv` and `current_leader_episodes.json`.

Inspected **11 recent public episodes** of the leader's higher-rated submission: five new downloads plus six previously used for opening analysis. Both seats, six distinct first-shop types and ten distinct first-two-shop pairs are represented. Every downloaded match is retained, including defeats. The sample contains only two opponents, so it is not representative of the whole ladder.

The leader won **6/11**, with mean actual margin **-3,417.8**. Against DSM it won 4/5; against M & M & P & Q it won **2/6**, with mean margin **-7,850.5**. The leader's ranking does not make every recent decision optimal.

These are observed action/state logs, not source code or internal reasoning. We cannot identify its exact objective, search algorithm or forecast model from them.

## Validation and comparisons

Reproduced all **720 states** of each of the eleven actual matches, checking farms, market, town and private state for both seats. Successful-transaction ledgers reconcile exactly with terminal cash. Worker and production metrics count actual engine execution, excluding agent-internal projections.

Ran two additional controls per episode, for **33 completed full-game runs**:

1. Replace the leader with our corrected V45-based candidate, leaving the original opponent's recorded actions fixed.
2. Keep the leader's recorded actions and replace its opponent with our candidate.

Both controls retain the recorded shop sequence. Prices, affordability, weeds and farm outcomes may change. Baseline: `agents/v45_event_opening_fixed.py`, including the safe feed purchase and corrected forecast entry point. This is our V45-based candidate, not the unmodified public file.

**These controls are diagnostics, not live matches.** The second control makes the frozen leader lose 11/11, but it also causes 23–2,317 commands per game to target workers who were not hired. Recorded market decisions cannot adapt to new cash and prices. This invalidates interpreting that apparent sweep as evidence that V45 beats the actual leader. The same caution applies when replacing the leader: the original opponent also cannot react.

## 1. The main difference is continual crop reallocation

Elapsed-day checkpoints, averages across eleven games. Leader columns are actual observations; V45 columns are replacement controls against the same recorded opponents and shops, with changed market interactions.

| Elapsed days | Leader strawberries | V45 strawberries | Leader tomatoes | V45 tomatoes | Leader carrots | V45 carrots |
|---:|---:|---:|---:|---:|---:|---:|
| 12 | 26.5 | 32.9 | 0.8 | 0.0 | 0.5 | 0.0 |
| 18 | 29.4 | 32.9 | 3.8 | 0.0 | 1.9 | 0.0 |
| 21 | 22.2 | 32.9 | 7.3 | 1.8 | 6.4 | 0.0 |
| 24 | 10.1 | 19.9 | 6.8 | 1.8 | 10.3 | 0.0 |
| 27 | 5.6 | 13.0 | 6.3 | 1.8 | 18.2 | 29.0 |

V45 keeps approximately 33 strawberries through day 21 in this panel. Its wheat counts are exactly 20 at day 12, 24 at day 15, 25 at days 18/21, 38 at day 24 and 16 at day 27 across all eleven controls. The leader's mix varies much more by match and changes across more checkpoints. It starts carrots well before V45's large terminal conversion, and grows tomatoes on existing land.

This supports investigating an adaptive planting/replacement policy. It does **not** prove each leader replacement was price-optimal: we would need a counterfactual crop plan with feasible watering, harvest, transport and staffing to establish that.

## 2. Fertilizer is allocated differently

Eleven-game average, actual leader versus V45 replacement:

| Quantity | Leader | Our V45 |
|---|---:|---:|
| Fertilizer collected | 334.0 | 367.4 |
| Fertilizer applied | **150.6** | **101.2** |
| Fertilizer sold | 181.5 | 342.1 |
| Fertilizer purchase spending | **0** | **2,998.7** |
| Wheat harvested | 603.8 | 575.8 |
| Tomatoes harvested | 54.8 | 14.5 |
| Carrots harvested | 107.8 | 89.2 |

The leader uses more of its own fertilizer instead of selling most of it and later purchasing inputs. V45's selling and repurchasing is not automatically a mistake; timing and price differences can justify it. The opportunity to study is the joint choice **apply, retain, sell, or buy**, with crop outputs and service time valued together. Our current forecast layer mainly values selected native fertilizer-worker plans; it does not freely redesign the crop mix and all fertilizer uses.

## 3. A hard three-quadrant rule would be the wrong conclusion

The leader never buys the fourth quadrant in these eleven matches. Our V45 controls buy it in 2/11. But M & M & P & Q buys it in **5/6 actual matches against the leader** and wins four.

The following comparison uses only those **same six actual head-to-head matches**, with no replacement agents:

| Metric, mean per match | Majkel1337 | M & M & P & Q |
|---|---:|---:|
| Final cash | 107,935.8 | **115,786.3** |
| Land spending | 3,000.0 | 6,333.3 |
| Worker spending | 4,878.8 | **4,771.2** |
| Worker movement commands | 3,443.2 | **2,650.0** |
| Fertilizer applied | 147.3 | **225.2** |
| Tomatoes harvested | 42.5 | **177.3** |
| Carrots harvested | 119.2 | **236.5** |
| Tomato sale revenue | 3,745.2 | **16,228.3** |
| Carrot sale revenue | 5,423.7 | **10,339.7** |
| Egg sale revenue | 2,278.7 | **11,028.7** |

The challenger has a broader production portfolio, particularly tomatoes, carrots and geese/eggs. It makes about **23% fewer movement commands** with a similar worker bill, despite generally owning more land. This points toward studying spatial organization and service schedules alongside production choice. Movement counts are descriptive, not an isolated proof of better routing: the two farms perform different jobs and have different layouts.

### Concrete match

In [episode 109701719](https://www.kaggle.com/competitions/kaggriculture/leaderboard?submissionId=56156662&episodeId=109701719), the challenger finishes at **125,467** against the leader's **109,543**.

It earns 9,522 from tomatoes versus 1,444; 11,502 from carrots versus 7,453; and 11,539 from eggs versus 3,802. Its worker bill is **4,730 versus 4,929**, despite land spending of **7,000 versus 3,000**. It also earns more strawberry revenue in that game. This is a full portfolio and execution difference, not a single magic crop or a pure sales-timing advantage.

## 4. Cheap-looking activity is not automatically useful

Across all eleven leader matches, it averages only 59 PASS commands, versus 489 for our V45 controls. However, it also has more movements and more no-effect watering commands: 88 versus 11.5. Mean seasonal worker spending is essentially equal: **4,885 versus 4,852**.

Therefore "eliminate every PASS" is not a sound objective. A replacement job must generate more value than its travel, inputs and disruption cost. Idle time can be deliberate slack. The appropriate measure is marginal net return from a feasible job schedule, not activity count.

Similarly, the leader's wheat product purchases cost 7,079 versus 17,442 for V45 controls, but V45 also resells substantially more wheat. Gross purchase spending is not waste by itself. Net wheat sales minus wheat-product and wheat-seed purchases are **9,704 for the leader versus 9,151 for V45** in this panel: a much smaller difference than the gross purchase gap suggests.

## Recommended research sequence

### A. Build a crop-plan evaluator beyond fixed V45 routes

At a harvest or planned crop-removal decision, compare concrete alternatives:

- Keep the existing recurring crop.
- Replant wheat, carrots or tomatoes where season length permits.
- Leave the tile temporarily unused if no serviceable plan pays.

Each candidate must include planting, watering, fertilizer, harvest and transport times through the remaining season. Value expected *delivery* prices, including our added supply and observed opponent production, then subtract seeds, fertilizer opportunity cost and added worker cost. Reuse the forecasting work, but apply it to production selection rather than only native input tours.

Start with **three quadrants and the safe existing opening** to isolate production choice. This is an experimental control, not a permanent land cap. A crop substitution is not safe merely because it fits on the same tile: maturity dates and service jobs must remain executable.

### B. Jointly schedule workers and allocate fertilizer

Take the proposed jobs and build feasible routes, including pickup quantities and shed returns. Re-evaluate the plan when it needs another hire. Decide fertilizer retention/application/sale in the same calculation. The challenger comparison makes this more promising than imposing a smaller crew or selling less fertilizer unconditionally.

### C. Add expansion as a complete investment plan

Evaluate the fourth quadrant together with its crop portfolio and worker tours. Require expected incremental proceeds to cover the 4,000 land purchase, seeds, inputs and additional service cost. Compare against the best reuse of existing plots. Neither "always expand" nor "never expand" follows from these logs.

### Evaluation requirements

- Use active source-code opponents wherever available, including a fresh strong public policy outside the V45 family. Do not substitute recorded action streams for adaptive opponents when claiming wins.
- Preserve a fixed V45 control; separate crop selection, scheduling, fertilizer allocation and expansion ablations.
- Cover all first-shop types and multiple later shop sequences, both seats, and fresh held-out seeds. Keep forecast fitting and policy selection away from final evaluation seeds.
- Track paired final margin and cash, actual successful production/delivery, input spending, missed planting/feeding, and marginal hire costs. Include natural engine RNG confirmation as well as fixed-shop diagnostic panels.
- Judge success on full-season games; earlier income, more harvests or lower spending individually do not establish a better policy.

This audit prepares that research direction. It does not implement or submit a replacement farming planner.

## Artifacts

- `scripts/audit_leader_strategy.py`: exact replay, successful transaction and worker-action audit, two diagnostic controls.
- `scripts/report_leader_strategy.py`: aggregate and matched-opponent comparisons.
- `results/fresh/leader_strategy/manifest.json`: baseline hash and sample provenance.
- `results/fresh/leader_strategy/summary.json`: numerical summary.
- `results/fresh/leader_strategy/audit-<episode>.json`: ledgers, daily boards, physical outputs, layouts, market requests and controls.
- `results/fresh/leader_strategy/replays/`: eleven original replay downloads.

Episodes: 109655909, 109662252, 109668602, 109675071, 109681490, 109687905, 109694306, 109701719, 109701761, 109709271, 109717736.
