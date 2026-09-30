# Corrected mission: production-plan continuation beyond UMG tape coverage

## User's objective

When our observed shop history and current board no longer have a suitable continuation in the Mother-Goose action-tape library, choose a credible **remaining-season production plan** and execute it from our actual state.

The intended transferable artifact is a whole-farm trajectory: how much of each crop/animal to maintain, plant, produce, retire, and sell over the remaining days. Exact leader movements and tile coordinates are not the policy to copy. Isolated crop substitutions do not answer this objective.

The production-module integration experiment remains a narrow execution experiment. Its negative carrot result provides no test of whether following a leader's complete production trajectory can close the tape-coverage gap. Continuing with another isolated crop swap is not the next milestone for this mission.

## What running out of tapes means

The recorded tapes still contain actions through the end of the game. What runs out is a continuation that suits both the revealed market and our accumulated board. Existing coverage measurements show a median of 10 compatible tapes at day 15, two at day 18, and one at day 21. A fallback should respond to coverage and mismatch, rather than assume day 18 is universally the right handover.

## Representation

Extract complete daily trajectories from UMG and other leaders, retaining:

- Revealed shops and market information available at each planning checkpoint.
- Crop counts by crop **and age cohort**, productive animals, and remaining productive life.
- Planting/retirement targets and expected harvest/animal-output quantities by day.
- Seed, fertilizer, feed, land, cash, inventory and daily labor requirements.
- Provenance: leader, submission, episode, observed versus inferred quantity.

“Maintain x units of y on day z” needs cohort ages and harvest targets: ten newly planted tomatoes cannot replace ten tomatoes already producing. The plan must include care and funding obligations through the end of the season.

## Decision and execution layers

1. **Choose the remaining-season production trajectory.** Match revealed demand and our existing cohorts to complete leader plans. Initially select one coherent continuation. Later combine compatible crop/herd portions only under a shared land, cash and labor budget; averaging two plans can produce an infeasible third plan.
2. **Adapt it to our starting board.** Preserve valuable existing crops/animals, account for their future output, and schedule the additions/retirements needed to approach the target. Do not force an unreachable target or destroy working assets merely to match a snapshot.
3. **Compile feasible actions.** Plan workers, inputs, care, harvesting and delivery from actual positions and inventories. This planner must be able to generate new routes; restricting it to the old tape's visits defeats the fallback's purpose.
4. **Replan when new information arrives.** New shops, unexpected prices or execution failures can change targets. Protect already-funded care commitments while revising the remaining horizon.

The recent tile reservation and inventory checks may be reusable implementation details. They are not the research objective or the plan-selection mechanism.

## Evaluation order

### 0. Identify the uncovered shop branch and find its production plans

First enumerate the new shop reveals that remove the last exact-history match in the UMG library. Separate literal shop-order gaps from gaps in current aggregate demand and from incompatibility with our accumulated board. For each gap, retrieve whole-farm production trajectories from UMG examples with comparable revealed demand, then other leaders if needed, and record the starting-state differences that must be bridged.

`scripts/map_umg_shop_coverage.py` now builds this index from all 584 frozen UMG tapes. The library contains all 64 first-two-shop histories, 351 of 512 first-three histories, and 544 of 4,096 first-four histories. Its output, `results/fresh/production_continuation/shop_coverage.json`, includes missing branches and initial whole-farm standing-count continuations. These are candidate targets, not executable validated plans: compact board labels omit crop ages, and source trajectories after their next shop reveal are conditional on their own future draws.

The first research deliverable is a table of **covered history → newly revealed shop → current farm → candidate whole-farm production plans → feasibility gaps**. Complete this plan-discovery step before building the execution machinery. Production policy must be chosen using revealed information only; a donor's later shop-conditioned actions are not an unconditional commitment for our world.

### Shop-history count is not production-plan count

The day-6 audit (`scripts/check_umg_day6_equivalence.py`, `results/fresh/production_continuation/day6_equivalence.json`) finds that all 64 ordered shop-pair groups have the same unique modal standing-count profile at the start of day 6: 3 wheat, 4 strawberries, 12 melons, 4 cows and 2 sheep. This profile appears in 516 of 584 recordings; there are 18 observed count profiles in total. Day 6 is the point before commands responding to the second shop. Subsequent days 6–9 production trajectories diverge, and multiple shop histories can also share a trajectory. Counts omit crop ages and cannot establish complete state equivalence.

Consequently, absence of an exact shop-history match alone is not a sufficient fallback trigger. The useful next coverage measure is how many distinct production continuations remain feasible for the current board and visible market. Exact-history coverage measures recorded worlds; it does not measure coverage of usable production plans.

### A. Can we execute a known full production plan?

Start from recorded leader states at several handover days. Supply the corresponding remaining-season production targets to the new planner, without supplying its recorded movement commands. Compare daily cohort counts, output, missed care, labor/input costs and final cash with the source run. This is an execution diagnostic, with explicit hindsight targets; it is not an online-policy performance claim.

### B. Can we select a useful plan when a suitable tape is unavailable?

Hold out complete episodes and shop histories. At handover, select or adapt a production trajectory using only information revealed so far. Hide the test world's matching action tape and any future shop information. Compare against the current best available UMG tape router, with active opponents and varied initial shops.

Separate the cost of selecting the wrong production plan from the cost of executing a good plan imperfectly. Recorded-opponent tests remain supporting diagnostics.

### C. Does combining leaders add value?

Compare UMG-only target plans, other-leader target plans, and resource-feasible combinations. A mixture must improve complete remaining-season outcomes on held-out worlds, rather than merely reproduce selected local crop cycles.

## Next concrete deliverable

A library and visualization of **whole remaining-season production trajectories**, indexed by handover state and visible demand, plus an explicit distance/feasibility measure for reaching each trajectory from our board. Use this to identify which complete continuation is missing when the router becomes stuck, then implement and validate the trajectory-following executor.

References: `docs/gap_ceilings.md`, `docs/leader_segments.md`, the existing UMG production visualization, and `docs/labour_search.md`. The labor optimizer is currently an offline model and must not be described as a validated in-game executor.
