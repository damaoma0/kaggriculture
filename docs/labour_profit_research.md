# Labour arrangement for a fixed production plan

Research date: 21 September 2026. Engine: the project's installed Kaggriculture implementation.

Follow-up: [direct supplied-plan self-play](labour_selfplay.md) replaces the hindsight feasibility filter with an observation-based projection. Across 20 plans with both seats, labor plus forecast sale timing wins 40/40 matches against the identical unscheduled plan (+146.15 mean margin, +136.80 own cash versus the mirror control). Production and final farm/inventory states are preserved. This remains a research executor outside the live action-time limit.

## Recommendation

Use a **sale-deadline-aware routing search**, starting from the feasible recorded schedule. Give tile jobs a value relative to the additional travel, work, input collection, and delivery they require. Use that priority to propose assignments, then improve them with regret insertion and destroy/reinsert moves across workers. Compare several crew sizes by final profit.

Keep **delivery and selling as separate decisions**. A product arriving sooner can wait in the shed. Removing a worker is attractive when the remaining crew can still deliver the planned quantities before their intended sales. An earlier sale is an optional alternative, accepted only when its expected revenue gain exceeds its extra labour and other costs. Shortest routes, minimum headcount, and earliest sales are different objectives.

Your proposed distinction is correct: with enough storage and the same feasible purchase plan, an earlier delivery still permits the original later sale. It therefore cannot reduce the *best attainable* sale revenue. A policy that automatically sells upon arrival can lose money; that is a policy restriction, not a reason to avoid earlier availability. After reassignment, individual deliveries can move either earlier or later, so the useful constraint is meeting the chosen sale deadlines.

The implemented prototype is an offline research tool. Its exact feasibility filter sees the recorded continuation, and its production jobs are extracted from a supplied tape. The market-forecast selector does not read future opponent trades, but that does **not** make the complete experiment an online policy. No submission agent has been replaced, and no global optimum is claimed.

## What the plan must specify

A useful input is more precise than crop counts. It contains:

1. Initial tile states, worker positions, inventories, cash, and unlocked land.
2. Required tile operations with command arguments, allowed days, precedence, and required inputs. For example: harvest wheat, then plant, then water; collect wheat before using it to feed an animal.
3. Output quantities and earliest availability, plus intended delivery/sale quantities and deadlines.
4. Explicit purchase quantities and release times. Previously unsuccessful or oversized purchase requests in a tape are not additional production targets.
5. Opponent-supply scenarios and known shop consumption. Unrevealed shops and hidden rival inventories need uncertainty treatment during online play.

The fourth item proved essential. A literal action tape can request more animals or inputs than its cash actually buys. Saving wages gives those old requests new purchasing power, changing subsequent production. A schedule can preserve a 48-hour state contract and still break the original season later through that effect.

## Objective and heuristic

For a given production plan, maximize expected final cash:

`profit = sale revenue - successful purchases - land costs - cumulative hire costs`.

Revenue must use **per-unit marginal prices after our own market impact**, rather than multiplying a displayed price by an entire lot. Opponent orders, order-list positions, and shop consumption also affect execution prices.

For insertion of job `j` between route visits `a` and `b`, the relevant additional travel is:

`delta_travel = distance(a,j) + distance(j,b) - distance(a,b)`.

A suitable search priority is:

`priority(j,u) = (expected value lost by delaying j + deadline urgency) / (delta_travel + service + required pickup/drop work)`.

This should rank proposals, not authorize skipping required work. A survival operation with an imminent deadline remains mandatory even when its immediate revenue is zero. The value of optional CARE or an extra crop belongs in a separate production-plan decision.

The tested simple tile heuristic uses visible spot-valued harvested goods, a crop/product value for WATER/FEED/CARE, and a 10,000 priority bonus for preventing a second consecutive missed watering/feed. These are untuned ranking weights, not a calibrated economic valuation. All extracted jobs must still be assigned. A distance-only version provides a control.

The recommended acceptance test is stronger than that heuristic: compare feasible complete schedules by expected profit, including the option to retain the original sale times. For an extra worker, the break-even condition is:

`additional attainable revenue > next hire cost + additional input/handling costs`.

The current prototype tests removing workers and rearranging the existing crew. It does not search extra-worker hiring, every possible departure time, or every sale allocation.

## Why this search family

This is a routing problem with time windows, pickup/delivery dependencies, inventory constraints, and time-dependent revenue. A greedy nearest-tile rule ignores those dependencies. A value/distance rule is a useful initial ordering but still needs repair when individually attractive jobs leave an infeasible remainder.

Ropke and Pisinger's [adaptive large-neighborhood search research](https://pubsonline.informs.org/doi/abs/10.1287/trsc.1050.0135) supports using several competing removal and reinsertion operators for pickup/delivery problems with capacity and time-window constraints. Their results concern standard routing benchmarks, not Kaggriculture. Li, Chen and Prins also study [profit-oriented pickup/delivery routing with mandatory and optional requests](https://www.sciencedirect.com/science/article/pii/S0377221715011716). These provide a methodological basis for a richer profit-aware search; neither paper establishes the best algorithm for this project's game.

[OR-Tools time-window routing](https://developers.google.com/optimization/routing/vrptw) and [pickup/delivery constraints](https://developers.google.com/optimization/routing/pickup_delivery) are useful formulations. A [CP-SAT model](https://developers.google.com/optimization/cp/cp_solver) is a reasonable offline comparator for small instances, with an explicit distinction between a feasible solution and a proven optimum. The game's nonlinear, competing market fills would still require a suitable economic model or an outer simulation loop. No OR-Tools or CP-SAT solver was installed or benchmarked here.

The implemented search uses deterministic bounded 2-opt, relocation, regret insertion, randomized partial destruction/reinsertion, harvest-first ordering, distance/value construction, and removal of any of up to six suitable worker bundles. It is inspired by large-neighborhood search; it is not a full adaptive-operator implementation.

In this prototype, sale deadlines remain implicit in the recorded sale ledger and the engine acceptance test. A stronger next implementation should put input-release times, tile precedence and delivery deadlines directly into insertion feasibility. That should avoid generating many schedules which the engine later rejects.

## Engine constraints included

The experiment calls the installed official interpreter and actual transaction functions. It includes:

- Hired workers acting from the following turn, real spawn positions, and Fibonacci hiring costs.
- Physical commands before market actions; a seed bought this turn cannot fund this turn's planting.
- Per-worker wheat/fertilizer/animal inventories and harvest-to-feed dependencies.
- Atomic seed-demand validation across simultaneous planting commands.
- The ten-order limit and per-unit competing market fills. Removed hires leave an inert order slot so later sales do not gain a different order position accidentally.
- Shed capacity, discarded overflow, and the free midnight inventory return.
- Watering, feeding, care, harvest, weed generation, crop decay, and final-season timing.

The first two hours of surviving routes preserve their commands. When an arbitrary worker is removed, those two hours are simulated again to determine the surviving workers' actual spawn positions and inventories. Jobs after hour 2 are recompiled. Some purchase-dependent routes are also tested with their original commands retained.

## Experiment design

Four pilot episodes were used to develop the harness and candidate construction. The subsequent algorithm was frozen before selecting results from 12 additional ladder episodes and eight Mother-Goose episodes. The ladder sample includes three of our submissions. The Mother-Goose tapes use her original opponents, recovered from existing local replays; no new replay downloads were needed.

Each candidate changes one production day and is evaluated through the following day. The terminal contract requires both farms, both private inventories/seeds, market state, and successful trade quantities to match the unchanged continuation, except for cash and removed hire payments. This prevents a cheaper schedule from winning by leaving work unfinished or selling fewer units. The equality of opponent state/quantities also rejects counterfactuals that break its recorded physical plan.

Ladder experiments change zero-based days 3, 5, ..., 27: 13 candidate days per episode. Mother-Goose experiments change days 4, 6, ..., 26: 12 days, including day 10's melon harvest. Other days execute the supplied plan. These are deliberately non-overlapping 48-hour windows; **the results are not an optimization of every day of the season**.

Selectors are:

- **Preserve sale times:** choose the greatest wage saving among feasible candidates retaining the same successful sale times and quantities.
- **Distance / tile value:** restrict to that construction's candidates and rank with the public-state price model, including the unchanged baseline.
- **Market-aware portfolio:** rank the complete candidate pool using expected profit from three simple opponent-supply scenarios.
- **Robust portfolio:** use the minimum forecast gain across those scenarios.
- **Recorded-market hindsight:** choose the greatest actual profit among tested candidates. This is a best-tested hindsight comparator, not an upper bound on all achievable profit.
- **Immediate-sale control:** sell available non-input goods as soon as possible, without route changes. This is retained as a diagnostic and excluded from the portfolio selectors.

The public forecast uses current inventory and shops, visible rival output, and uncared animal production rates. Rival supply is scaled by 0, 1, or 2. It does not read recorded future opponent transactions or future shop reveals. Its successful own trade quantities and the feasibility gate nevertheless come from an offline continuation. Therefore even its positive results require a future online evaluation.

The initial raw-tape run exposed additional purchases funded by saved wages. The same algorithm was then rerun on explicit fixed plans: every buy, sale, hire and land order is capped to the original successful quantity at that exact order slot, for both players. Before this second experiment, every baseline farm, inventory, market state and successful transaction was checked against the raw recording. This is a correction to the plan representation after inspecting the first evaluation, so the corrected rerun should not be presented as a completely untouched blind test.

A final timestamp audit found that a snapshot's physical state was correct while its `step` metadata lagged by one turn. This did not change the executed engine transitions, but it could change forecast ranking. The bug was fixed, prefix-versus-full-replay forecast equality was added to verification, and both final panels were rerun. Only `fixed_ladder_v2` and `fixed_leaders_v2` support the final forecast comparison; earlier folders are retained as development diagnostics.

## Results

The final comparison covers **20 recorded worlds, 252 production-day scheduling instances, and 60 complete optimized seasons**: three chained selectors per world. The isolated instances contain 1,396 accepted alternative schedules, in addition to their unchanged baselines. Separate raw-tape runs and pilot experiments are development evidence, not additional independent test worlds.

These are actual changes in final cash after executing the selected schedules through the season, with the explicit fixed plans. All **60/60** optimized seasons preserve both players' terminal farm/inventory state, market state and successful trade quantities, and all reconcile to their transaction ledgers.

| Selector | Our ladder plans: 12 worlds | Mother-Goose plans: 8 worlds |
|---|---:|---:|
| Preserve sale times; save wages | **+133.17** | **+113.63** |
| Market-aware portfolio with public-state price heuristic | **+139.25** | **+153.13** |
| Best tested with recorded-market hindsight | **+144.50** | **+164.50** |

The market-aware selector improves all 20 complete seasons in this sample. Individual gains range from +2 to +361 on the ladder panel and +3 to +271 on the leader panel. Its episode-bootstrap 95% intervals for mean gain are approximately [+77, +207] and [+96, +205], respectively. These intervals describe this small conditional experiment, including its hindsight feasibility filter; they do not estimate live leaderboard improvement.

![Final cash comparison](../results/fresh/labour_profit/profit_comparison.png)

### Where the profit comes from

| Public-price portfolio, mean per season | Ladder plans | Mother-Goose plans |
|---|---:|---:|
| Wage savings | +136.00 | +142.75 |
| Sale-revenue change | +3.25 | +10.38 |
| Other spending change | 0.00 | 0.00 |
| Final-cash change | **+139.25** | **+153.13** |

Most of the measured benefit is labour saving. Allowing profitable changes to sale timing also admits some cheaper crew arrangements that cannot meet the *exact* original sale schedule. The extra gain over the sale-preserving selector is +6.08 on the ladder panel and +39.50 on the leader panel; not all of that difference is higher prices.

For context, baseline final cash averages 103,172 and 127,863, so these gains are about 0.1% of final cash. They establish feasible improvements in this bounded search, rather than a large competitive advance. The prototype only reschedules alternate production days.

### The tile-value heuristic

The following are means of summed **isolated-window** improvements, using each construction's candidates and the public-price selector. These two restricted selectors were not independently chained through full seasons.

| Candidate construction | Ladder plans | Mother-Goose plans |
|---|---:|---:|
| Distance-based greedy insertion | +29.50 | +6.50 |
| Tile value / incremental work | +20.83 | +3.25 |
| Complete search portfolio | +139.25 | +153.13 |

The simple value ranking does not beat distance-only insertion in this sample. Many greedy constructions cannot fit the complete mandatory job set; the value construction has an accepted candidate on only 16/156 ladder instances and 12/96 leader instances. Removing a worker and redistributing its jobs with regret insertion is a more productive source of candidates. These results support using value to guide a broader feasibility-aware search, not relying on the tested value ratio as the entire algorithm. They do not prove that a better marginal-value heuristic would fail.

The conservative scenario selector has isolated-window means of +138.67 and +139.38, with no losing selected windows. The mean-scenario selector loses 49 and 12 in two individual leader windows despite positive full-season totals. Thus “do not sell early when it loses money” is automatic with hindsight, but a forecast can still misjudge the trade. Preserving sale times remains a useful fallback.

### Two inspectable schedules

**Pure labour improvement:** episode **110838385**, zero-based day **27**. The search removes original worker 10, redistributes its jobs, and reduces 12 paid hands to 11. The marginal hire saving is **144**. Harvested quantities, input spending, sales quantities, sale times and sale revenue all match the source plan. Removing an arbitrary worker matters: the saved wage is the final marginal hire cost, irrespective of which worker's tasks are redistributed.

![Recorded and optimized worker schedules](../results/fresh/labour_profit/labour_arrangement_example.png)

The [executable schedule and tile jobs](../results/fresh/labour_profit/example_fixed_ladder_v2_wage.json) include the original and optimized actions, every worker's hourly location/command, and both sale ledgers.

**Labour plus revenue improvement:** episode **110003132**, zero-based day **14**. The selected schedule reduces 10 paid hands to 9, saving **55**, and changes wool deliveries/sales to gain **92** more revenue: **+147 net**. Both schedules sell 35 wool across the two-day window; wool revenue increases from **6,800 to 6,892**. The changed schedule delivers and sells six wool at day 14 hour 21, while also changing some other wool sale quantities and times. The +92 is the combined timing effect across all those sales, not the isolated value of that six-unit lot. Milk and other sold quantities stay unchanged.

The [complete profit-aware example](../results/fresh/labour_profit/example_fixed_leaders_v2_oracle.json) includes the actual successful sales and confirms equal harvested/collected quantities. Its forecasted gain is only +30.67 and its conservative scenario score is -34, illustrating real uncertainty around the otherwise positive hindsight result.

### Why literal tape replay was misleading

Before purchases were made explicit, the sale-preserving labour selector had a positive +41.25 mean local opportunity on the Mother-Goose panel but a **-235.25** mean when chained through raw action tapes. Four of eight resulting seasons failed the original production/trade contract. Additional cash could fund previously unsuccessful orders. The ladder panel also had one such full-season contract failure.

Those results are not fixed-production labour gains and are excluded from the main table. Capping each recorded order at its actual successful quantity restores an explicit plan and reproduces the complete original baseline before optimization. This is an actionable requirement for any executor that follows an existing tape.

The immediate-sale control, with unchanged routes, loses a mean 1,538 on the ladder panel and 2,089 on the leader panel in summed isolated windows. It was excluded from the portfolio choices. This supports separating delivery from selling; it does not show that making goods available earlier is intrinsically harmful.

### Implementation priority supported by these tests

First, formalize the plan's input quantities, task dependencies and delivery deadlines. Then expand the feasible routing neighborhood while preserving the source schedule as a fallback. Within the tested candidate pool, perfect market information adds only another +5.25 and +11.38 beyond the public-price portfolio. My inference is that improving feasible candidate generation is the more promising immediate step here than adding a much more elaborate price model. This is conditional on the narrow search tested: extra couriers, earlier opening actions and unrestricted daily scheduling remain unexplored.

To claim an online improvement, replace the recorded-future feasibility filter with own-state simulation and opponent scenarios, then test the resulting executable policy against reacting opponents with whole episodes and shop histories held out. The current results establish an offline research baseline for that work.

## Validation and practical limits

The fast simulation driver was independently compared with the normal Kaggle framework for all 719 transitions of two complete games, one in each seat. Farms, market states, private inventories and final rewards matched at every transition. Additional checks reject altered farm/inventory outcomes, check harvest-before-feed input handling, and confirm the forecast ignores future opponent trade records.

The fixed-plan conversion checks all 720 baseline states for each of the 20 evaluation recordings and checks equality of the entire successful transaction sequence. Each optimized season also reconciles final cash with actual successful revenue, purchases, land and wages. Full-season continuation-state checks are reported separately from isolated-block improvements.

Important limits:

- Opponents are recorded scenarios, not reacting live policies; both players' planned transaction quantities are explicit in the fixed-plan experiment.
- Only 20 evaluation worlds and alternate production days are tested. Episodes may share opponent strategy families, so episode-bootstrap intervals are descriptive rather than proof of broad generalization.
- Candidate enumeration is bounded and conservative; some original routes stay fixed, early input work is restricted, and many feasible schedules are never generated.
- There is no proof that the selected crew count is minimal or that the selected profit is globally maximal.
- This research tool is not packaged as a single-file competition agent or validated against the online action-time limit.

The older [labour-search benchmark](labour_search.md) estimates 1,363 saved wages per game from a relaxed offline model over 73 different tapes and 26 production days. The present experiment uses different instances, tighter continuation contracts, fewer rescheduled days, and a different bounded search. Its results cannot be used as a direct numerical refutation or confirmation of that estimate.

## Artifacts and reproduction

Use the project's `.venv/Scripts/python.exe`:

```powershell
.venv/Scripts/python.exe scripts/check_labour_profit.py
.venv/Scripts/python.exe scripts/build_labour_profit_panel.py
.venv/Scripts/python.exe scripts/build_labour_fixed_plans.py
.venv/Scripts/python.exe scripts/research_labour_profit.py --count 12 --panel results/fresh/labour_profit/fixed_ladder --chain --workers 4 --tag fixed_ladder_v2
.venv/Scripts/python.exe scripts/research_labour_profit.py --count 8 --panel results/fresh/labour_profit/fixed_leaders --days 4,6,8,10,12,14,16,18,20,22,24,26 --chain --workers 2 --tag fixed_leaders_v2
.venv/Scripts/python.exe scripts/report_labour_profit.py
```

`build_labour_fixed_plans.py` reads the saved `ladder_holdout/manifest.json` and `leaders_holdout/manifest.json` to recover the authoritative 20 source paths. Historical experiment tags retain earlier code hashes; use a new tag when rerunning those diagnostics with changed code.

Manifests freeze script and engine hashes, selected paths and experiment arguments. Per-episode records also retain source-file hashes, rejected-candidate counts, accepted choices, revenue/cost components, baseline results and complete-season results. Existing results resume only when the manifest matches. Sampling is deterministic for a fixed corpus; the saved manifest paths are the authoritative sample if the local corpus later changes.

Primary output directory: `results/fresh/labour_profit/`. The experiment deliberately leaves the live agent and existing research files unchanged.
