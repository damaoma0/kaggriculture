# Cumulative production-plan compiler

`scripts/cumulative_plan_solver.py` converts a current farm snapshot and several **timed cumulative-output targets** into an integer, whole-farm production schedule. It is the inversion step between an output forecaster and a future routing controller; it does not retrieve a donor tape.

## Input

```json
{
  "snapshot": {
    "day": 12, "season_days": 30, "land_capacity": 25,
    "tiles": [[{"kind":"PLANT","crop":"MELON","planted_day":4,"yield_units":3}]],
    "seeds": {"MELON": 12}, "seed_purchase_budget": {"MELON": 0},
    "fertilizer": 4, "fertilizer_budget": 0,
    "daily_action_capacity": 168, "travel_allowance": 30,
    "already_produced": {"MELON": 18}
  },
  "target_mode": "remaining",
  "targets": [{"day":15,"product":"MELON","units":36}, {"day":21,"product":"MELON","units":72}]
}
```

Targets are output actually harvested/collected, never sales. A target endpoint is exclusive: a three-day horizon at day 12 counts actions/output on days 12–14. With `target_mode: cumulative`, `already_produced[product]` is subtracted before solving. A snapshot can instead provide normalised `cohorts`, one object per existing crop/animal with `kind`, `type`, and `planted_day` or `placed_day`.

### Replay-corpus bridge

The fixed dataset checkpoint schema is accepted through a wrapper input:

```json
{"checkpoint": {"day":12,"observation":{"day":12,"player":0,"farms":[...],"private":{...}}},
 "snapshot_overrides":{"travel_allowance":30,"seed_purchase_budget":{"MELON":6}},
 "targets":[{"horizon":3,"product":"MELON","units":36}]}
```

`compile_checkpoint()` selects `farms[observation.player]`, uses private seed and shed holdings, and counts owned non-locked tiles after reserving weeds and empty structures. It never reads a later segment. The forecaster should pass its 3-, 6-, and end-horizon estimates as `horizon`; an evaluation may substitute held-out realised outputs only after targets and compiler settings have been frozen.

Hands disappear at daily refresh, so a checkpoint's `hands` list is deliberately **not** used as a next-day capacity forecast. Pass `hire_schedule: {"12": 11, "13": 11}`, `travel_allowance`, and `farm_hand_cost_mult`. Eleven early hires give 276 farm-action slots on normal days and 264 on day 29: ten market hires at step 0 act from step 1; the eleventh placed at step 1 acts from step 2. Crop/animal service shares that capacity.

New herd expansion is opt-in through `animal_purchase_budget`, for example `{"SHEEP": 3}`. It reserves a tile from purchase day, schedules build/place plus daily feed/care/fertilizer collection, and respects the animal count cap. The caller must have separately funded the animal, structure, feed and market orders; this aggregate compiler records the physical commitment and does not invent the cash flow.

## Model

Every existing productive crop/animal selects exactly one service profile. Existing crops may vary harvest age and fertilizer use; animals may vary care and fertilizer collection. The asset cannot disappear without its legal harvest/cleanup. Future crop cohorts include early and late harvests plus fertilized alternatives. Profiles call the checked-in engine's unit action, per-step decay and daily refresh functions on a copy of each native tile, retaining held yield, water/unfed streak, care bank, fertilizer duration, and lifespan. The MILP enforces:

- target output at **each target day** (under/over variables carry a large penalty);
- tile occupancy on every remaining day;
- per-crop seed budgets and daily prefix feed/fertilizer stock flow, including collected fertilizer output;
- daily aggregate action capacity after the declared travel allowance.

This timing is essential: two schedules with identical season totals can differ at day 15 because their cohorts have different ages. The objective reports the smallest timed deviation rather than claiming an impossible cumulative path.

Run:

```powershell
.venv\Scripts\python.exe scripts\cumulative_plan_solver.py input.json --out results/fresh/cumulative_planning/plans/plan.json
.venv\Scripts\python.exe scripts\validate_cumulative_plans.py
```

## Certificate and limits

`aggregate_feasible` is true only when every target has zero timed slack under the stated aggregate land/input/work budget. The output includes daily actions/resources and three-day output allocations. It always sets `routing_feasible` to `null`: daily counts cannot prove a crew can travel to all tile coordinates in the needed order. A later route compiler must consume the daily plan, concrete tile placement, hand positions, orders and actual inventories, then independently certify or reject it.

## Frozen procurement parameters

Use `procurement_cash_budget` (otherwise checkpoint cash), `seed_purchase_budget`, `feed_purchase_budget`, `fertilizer_budget`, `resource_prices`, `hire_schedule`, `farm_hand_cost_mult`, `travel_allowance`, `animal_purchase_budget`, `solver_time_limit`, and `mip_rel_gap`. Feed and fertilizer purchases are integer decision variables bounded by their supplied caps; the solver charges the purchased quantity at `resource_prices` or the engine base price. Seed and animal costs use the engine constants. Fixed daily hires use the engine Fibonacci cost. Future sales, future prices, and any market revenue are never credited. The result reports procurement counts, solver status, dual bound, and MIP gap.

`travel_fraction` optionally reserves a fraction of daily raw worker actions. The final guard `require_primary_animal_output` defaults to true: animals that cannot produce their main good before the horizon ends are not added solely to match fertilizer output. `horizon: "end"` maps to the season endpoint. Existing seed stock is conservatively charged again in the cash constraint; this can reject a feasible plan but cannot fund an unaffordable one. Price quotes, delivery and storage remain conditional aggregate assumptions.

For the full experiment and its limitations, see `docs/cumulative_prediction_and_planning_research.md`. Initial and guarded planner results are retained separately; the guarded rerun follows an observed economic degeneracy and is a diagnostic refinement.
