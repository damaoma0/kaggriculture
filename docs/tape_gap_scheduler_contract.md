# Tape-gap scheduler contract

The labour scheduler is ready to **reschedule a supplied, feasible action plan**. It is not a general production-plan executor.

## Actual public boundary

`scripts/test_labour_selfplay.py` calls:

```python
selected_actions, decision = choose(observation, own_window, mode, rounds=80)
```

`observation` is the player's current day-boundary observation. `own_window` must be exactly 48 action dictionaries beginning at `observation.step`; `choose` asserts both requirements. It builds a fresh projected engine world with a PASS rival, empty rival private inventory, held shops, and no new weeds. It first runs the entire supplied window unchanged. Every requested buy, hire, and land order must fill in that projection; otherwise it returns the original window with `fallback: projected_input_shortfall`.

The returned value is a replacement for the first two calendar days only. It preserves the supplied market plan unless the separately tested sale-timing selector changes it. The self-play result establishes production/inventory equivalence only for its frozen recorded plans.

## What the implementation can and cannot schedule

`research_labour_profit.block()` obtains jobs by replaying the supplied actions, then `extract()` groups successful tile-local commands into `Job` objects. `arrange()` can reorder and reassign those extracted jobs, reduce an existing worker suffix, and alter delivery timing. It retains every job. It deliberately locks a worker route that contains `PLANT`, `PLACE`, `BUILD_COOP`, or `BUILD_PASTURE`, because its prerequisite purchases and tile order are tape-specific. `actions_for()` then compiles only those recorded/extracted jobs back into the original action slots.

Therefore, feeding a different crop count or herd plan into `choose()` is not sufficient. The scheduler has no API for a solver's day jobs, no construction of new seed/animal orders, no allocation of empty tiles, and no proof that a synthesized plan's carry-over after the 48-hour window is feasible. Its reported production equivalence would reject the intended change.

## Smallest safe adapter

Keep the current tape plan as the base and synthesize only a small, independently funded delta for the current two-day window:

1. Turn the production compiler's selected daily delta into concrete market orders and tile jobs: `PICKUP`, route, `DIG` only where explicitly authorized, `PLANT`/`BUILD_*`/`PLACE`, `WATER`, `FEED`, `CARE`, `FERTILIZE`, harvest/collection, and return/drop. Assign stable, vacant owned tiles and reserve them through the solver's release day.
2. Put the delta on one or more **fixed routes**. Keep their prerequisite orders and command order fixed. Present the remaining tape work to the existing extractor/scheduler; do not ask `arrange()` to relocate a route containing new establishment work.
3. Combine the fixed delta with the scheduler's returned commands only after engine projection. If either plan changes the other plan's input availability, worker count, tile, or market-order slot, reject the splice and keep the base plan.

This is intentionally narrow: it can support the smallest production difference such as a few late crop cohorts or an already-funded servicing increment, while preserving the majority of an own tape. It does not establish a full replacement executor.

## Required validation before a comparison

For every synthesized window, run the official-engine projection from the actual checkpoint with the same observation restrictions used by `choose`. Record successful market fills, per-action inventory deltas, planted/placed tiles, daily harvest/collection output, feed/fertilizer stock flow, worker availability, and the two-day terminal farm/private state.

Accept only when the projection meets the compiler's daily output/input quota and no protected tape obligation is lost. Then run the normal shared-market continuation without hindsight rollback, report both projected and realized deltas, and mark routing feasibility separately. The existing 40-game self-play result cannot be reused as validation of altered production because it explicitly tested zero production and terminal-state changes.
