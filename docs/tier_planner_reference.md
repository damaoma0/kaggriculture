# The tier planner (mgt_lead_sector_search.py): flow and weights

Reference for the KB78 configuration (arm KB78 in `results/fresh/threads_20260928/animal/spec.json`, base `K5b` in
`scripts/sector_run.py`, agent defaults in `CFG` at the top of the agent). Written 2026-09-27 from the code; values in
brackets are the ones KB78 runs with. Line numbers drift - search the function names.

## 1. When it runs

| When | Function | What |
|---|---|---|
| Hour 0 of each day (days 11-28) | `_tier_pre` | Builds the day's job catalogue, predicts where the hires spawn, calls `_tier_core` (one or more passes) and stores the plan in `S["tier"]` |
| Every hour | `_tier_cmd` (per unit) | Walks each unit's item list (pickups, stops, ops) against the live board |
| Every hour | market block | Sells on DSM's recorded sell plan (books), buys wheat / seeds / animals, hires |

The plan is made once at hour 0 and not re-planned during the day (only the spawn remap of the hour-1 hires at hour 2
and executor-level skips change it).

## 2. The day's job catalogue (`_tier_pre` -> `rec`)

`_sd_build` (the older per-step planner's job builder) turns the live board plus DSM's plan for the day (plantings,
builds, animal placements from `_T`, tile-exact) into jobs: one op pipeline per tile (e.g. `WATER, HARVEST, PLANT,
WATER`), a release hour, deadlines and a "hard" index (the survival op). `_tier_pre` merges them into
`rec[tile] = {"ops": [...], "rel": release hour}`, each op `{"c": command, "m": mandatory, "v": value, "tier", "rank"}`.

### 2.1 Mandatory or optional (tiers)

| Op | Tier | Mandatory? |
|---|---|---|
| The job's hard (survival) op, PLANT, DIG, BUILD_*, PLACE, HARVEST | 2 | yes |
| WATER right after a PLANT or right before a HARVEST in the same pipeline | 2 | yes |
| other WATER, FERTILIZE | 3 | no (extras) |
| FEED (not keep-alive), CARE, COLLECT_FERTILIZER | 4 | no (extras) |

Overrides applied after that, in order (each only when its flag is on in KB78):

| Flag [KB78] | Effect |
|---|---|
| `sd_tier_anim_harv` [1] | an animal HARVEST not needed tonight (no overflow of max_held) becomes an optional tier-4 extra worth held x price x 0.1 |
| `sd_harvest_follow_dsm` [SHEEP, COW, GOOSE] + `sd_harvest_follow_keep` [1] | on DSM's harvest days the pen's harvest is mandatory (added if missing); on other days our harvest is dropped when it can wait |
| `sd_keep_alive_guard` [1, min 1] | an animal unfed yesterday with >= 1 production night left gets a mandatory FEED |
| `sd_tier_access_drop` [1] | a harvest on a shed-access tile is followed by PLACE_HARVEST (product straight into the shed) |
| `sd_tier_feed_bank` [1] | FEED on a production day with a care bank >= 1 is mandatory |
| plan jobs (DSM's plantings / builds of today not yet visible) | DIG / HARVEST pre-ops + PLANT (+ first WATER) or BUILD (+ PLACE), all mandatory, value `plan_value` 400 |
| `sd_tier_fert_skip_harv` [1] | no FERTILIZE on a one-time crop harvested today or a tile replanted / dug today |
| `sd_tier_fert_exact` [1] | every plant's FERTILIZE valued exactly (below); added where it pays, removed where it does not |

### 2.2 Values (`_sd_opvals`, then the overrides)

| Op | Value |
|---|---|
| any op with a maintenance-module job (`sched_maint`: `scripts/fragments/sem_maintenance.py`, per tile/asset) | the job's value x a market multiplier; its deadline; `kind == survival` marks it hard |
| optional (early) harvest from that module | held units x price x `opt_harvest_frac` 0.15 |
| an op with no module job | 50 |
| harvest inside the leader-tendency window (`sd_hp_parity`, crops MELON / WHEAT) | max(value, held x price x `hp_frac` 0.5) |
| WATER on an unwatered plant | at least `sd_water_tomorrow` [10] |
| FEED / CARE | + `sd_feed_bonus` [20] |
| COLLECT_FERTILIZER | at least `sd_collect_floor` [80] |
| survival op (plant dies / animal escapes tonight) | + `sd_hard` 5000 and mandatory |
| FERTILIZE (`sd_tier_fert_exact`) | extra units the fertilize adds (`_tier_fert_gain`: watered production nights in its 3-day cover) x crop price - 0.6 x fertilizer price (`sd_fert_frac` [0.6]) |
| plan job (plant / build / place) | `plan_value` 400 |
| every op | at least `sd_vmin` 2 |

Mandatory ops' values do not matter to the search (it has to place all of them); values steer only the extras.

## 3. Units and spawns (`_tier_pre`)

- Hands wanted = DSM's count for the day (`_sd_want_hands`). At hour 0 the market takes at most 10 orders, so k0 hires
  go at hour 0 (fewer when `sd_books_h0_slots` [2] keeps slots for DSM's hour-0 sells) and the rest at hour 1.
- The farmer starts every day on (4,4) and holds at hour 0 (`sd_tier_farmer_hold` [1]), so the hour-0 hires' spawn
  tiles are known: least-occupied access tile in the order NW (4,4), NE (5,4), SW (4,5), SE (5,5), one by one.
- Units passed to the core: `(0, (4,4), t0=1)`, hour-0 hires `(u, spawn, 1)`, hour-1 hires `(u, predicted spawn, 2)`.
- Passes: plan, derive the farmer's position after hour 0 -> hour-0 spawns (re-plan if they changed); then the
  hour-1 hires' spawn from the plan's own hour-1 positions (`sd_tier_spawn_h2` [1]: up to 2 re-plans); if still
  unsettled, `sd_tier_spawn_buffer` [1] plans the hour-1 hires from hour 3 (one hour of slack). At hour 2 the
  executor re-matches the hour-1 hires' routes to their real spawn tiles by first-stop distance (`sd_tier_spawn_remap` [1]).

## 4. One planning pass (`_tier_core`)

### 4.1 Melon hands (`_tier_melon`)
Ripe melons are partitioned among units starting by hour 1 into blocks each hand can harvest and drop at the shed
(PLACE MELON) by hour 8-12 (ranked by lateness, blocks, early bonus). A melon hand's later work is a `post` segment
starting at its drop hour, weight `wu = sd_tier_prio_w` 2.0 per hour. Melons nobody can drop by 12 stay normal harvests.

### 4.2 Dawn legs (`sd_tier_dawn` 3, file)
DSM's recorded early trips of the day (pen harvests at hours 0-3) are copied: each to one of our free units acting
from the same hour, same pens, same order. That unit's outbound segment then starts at the trip's end tile and hour.

### 4.3 Segments
`out`: a hand (or the farmer) from its spawn tile and start hour; `post`: a melon hand after its drop; outbound after
a dawn leg. Each has `wu` (hour weight) 1.0 (post 2.0).

### 4.4 Mandatory search (`_tier_search`)
Stops = one stop per tile holding mandatory ops (all its mandatory ops merged, its release hour).

**Route time (`_tier_eval`)**: start at `p0` at `t0`; pickups first at the shed (1 h for all the wheat its FEEDs need,
1 h for fertilizer to pick up, 1 h per animal type to place); Manhattan walking, one step an hour; wait until a stop's
release hour; every op 1 h. Lateness = hours a mandatory op runs after 23 + hours any op runs past 24. Supply failure =
a FERTILIZE with no fertilizer in hand (collected earlier on the route or picked up).

**Route cost (`_tier_cost`)** - what the search minimises, summed over segments:

    cost = 1000 x (lateness + supply failures)
         + wu x (end hour - start hour)                    # the route's length in hours
         + sd_tier_hop_w [1.0] x (extra steps between consecutive stops beyond 1)
         - sd_tier_coll_w [2.0] x min(pens on the straight way out, stops needing fertilizer)

There is no term for: the value of the ops (all mandatory), balance between hands, room left for extras, where the
route ends, or which spawn tile a route suits beyond the walk from `p0`.

**Start (sweep)**: stops sorted by angle around the shed centre, cut into K contiguous arcs of equal work
(ops + 1.5 per stop, K = outbound segments); arcs matched to segments sorted by their start angle, the rotation
chosen by a proxy (sum of each start's distance to its arc's nearest stop); each arc ordered by nearest neighbour from
the segment start plus or-opt. `sd_tier_offsets` [4] different arc start angles; the cheapest total kept.

**Simulated annealing**: `sd_tier_iters` [2500] iterations, temperature 2.0 -> 0.05 (hours) linearly. Moves:
55% relocate one stop to its best position in another route that has a stop within 3 tiles of it (or an empty
non-post route); 25% swap it with a stop of another route within 4 tiles (both at their best positions);
20% move it within its own route. Accept if cheaper or with probability exp(-delta / T). Best seen kept.
No move exchanges whole routes or moves a cluster of stops.

### 4.5 After the search
Dawn-leg pen service (`sd_tier_dawn_service`) merges into the same unit when it fits. (Day-return shape, pen round,
turn plan, pass drop: off in KB78.)

### 4.6 Extras catalogue
Optional ops with value > 0 become bundles:
- crop tile: one bundle of its tier-3 ops (WATER + FERTILIZE together), pool C;
- pen: the COLLECT alone (shared; also the fertilizer source for fertilize pairing), pool D/E;
- pen FEED + CARE together: pool C when worth >= `sd_tier_anim_c_minv` [150] (`sd_tier_anim_c` [1], x1.0), else pool D/E;
- deferred animal harvest (`sd_tier_anim_harv`): pool D/E.

### 4.7 Fills (`_tier_fill`, greedy)
Repeatedly the best feasible insertion over all bundles and candidate hands:

    score = bundle value / max(0.25, route cost after - route cost before)

inserted into the stop already on that tile if the route has one (no walking), else at the best position; kept only
when it adds no lateness or supply failure and score >= the phase's minimum rate. Candidate hands per bundle: the
`sd_tier_fill_near` [5] whose route passes nearest. A FERTILIZE without fertilizer in hand is paired with a COLLECT
before it (free collects nearest the tile or on the way out, best 3 positions (`sd_tier_pair_top` [3]); the pair is
scored on the fertilize alone (`sd_tier_pair_own` [1])). At most `sd_tier_coll_cap` [2] collects a hand unless the
next one is on its way.

| Phase | Hands | Pool | Minimum rate |
|---|---|---|---|
| C | outbound hands | crop WATER/FERTILIZE bundles, feed+care bundles worth >= 150 | `sd_tier_rate_c` [5] coins/h |
| relief (`sd_tier_relief` [1]) | a hand with spare time takes one stop from a busy route so that route can do an unplanned extra worth >= 20 | | |
| D | melon / animal hands (post segments) | collects, cheaper feed+care, deferred harvests | `sd_tier_rate` [1] |
| E | everyone | everything left | 1 |
| relief | again for what is left | | |

### 4.8 Midnight load and deliveries (`_tier_deliver`)
Projected load = what the routes carry at midnight (`_tier_load`); room = 100 - animals x 1 day of feed wheat - 5.
While over room: turnarounds (a shed stop between two stops, detour <= 2, by hour 16, loads >= 4 units:
`sd_tier_turnaround` [1]); copy DSM's number of daytime returns until day 22 (`sd_tier_copy_returns` [1]); end-of-day
DROPs for the most valuable loads per added hour (trimming low-value extras when the day is too short); harvest
deferral when still over (`sd_tier_dump_defer` [1]); go-home drops on heavy nights, skipping optional jobs and collects
(`sd_tier_deliver_skip` [1], >= 5 over).

### 4.9 Post passes and route build
Collects on pens a route already passes, within the shed's midnight room (`sd_tier_path_collect` [1], detour 1).
Each segment becomes an item list: dawn leg, pickups (wheat = number of FEEDs, fertilizer, animals), then the stops,
ops in rank order within a stop (DIG, COLLECT, FEED, CARE, FERTILIZE, WATER, HARVEST, PLACE_HARVEST, PLANT, second
WATER, BUILD, PLACE).

## 5. Executor (`_tier_cmd`, every hour)
Each unit walks its items: a pick item at the nearest shed tile (PICKUP, waiting up to 2 hours for wheat before hour 8);
a stop: walk there (x first, then y), then its ops one per hour, each checked against the live tile (`_tier_check`: do /
skip - already watered, nothing to harvest, no wheat in hand - / wait / dig first). DELIVER places one named product
from an access tile; a planned DROP is skipped when the shed will hold everything at midnight (`sd_tier_deliver_check`).
Units whose route is done PASS.

## 6. Where the observed waste comes from (viewer, world 112602061)
- Route cost = hours only, extras ignored: the mandatory search packs routes by walking time and leaves the extras to a
  greedy fill; 84 of 89 routes at pens with an unplaced collect already end at 24 with mandatory work.
- Sweep arcs are cut by angle and equal work: an arc can hold two far-apart clusters (hand 8, day 17: tomatoes at
  (1,7)/(0,6) and strawberries at (2,0)-(2,2), 16 of its hours walking), and annealing only moves single stops to
  routes within 3-4 tiles, so the clusters are not handed to the neighbours whose areas they sit in.
- Start tiles: arcs are matched to hands by angle proxy, never re-matched after the fills; first planned stop 1.47
  steps from the hand's spawn tile vs 1.20 from the nearest one (hands 4 / 6 / 9 on day 17).
- Pen work is split into separate bundles (mandatory part, collect, feed+care, deferred harvest) placed independently,
  so one pen is often served by 2-3 hands (10.5 shared tiles a day vs DSM 7.6).
- Fill scores divide value by added hours including walking, so the last free hours of a route rarely find a job worth
  the walk (stranded end hours; 39.8 of 50.8 route-days with spare time have no leftover job in reach).
