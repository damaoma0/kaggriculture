# Audit of the tier planner (flow and weights) - 2026-09-27

Companion to `docs/tier_planner_reference.md` (how it works). This page asks whether it is a sound foundation. Evidence is
KB78 vs DSM on the 40-world panel (days 11-28) unless noted; scripts named inline.

## 1. Verdict

The planner is geometrically adequate but economically unsound. Its routes are as path-like as DSM's, yet each visit
does less, the day is packed by required work before any value is weighed, and the values it does weigh are on
different, partly arbitrary scales. Patching single passes (the 40+ flags tested this session) keeps hitting the same
walls. A rebuild should change the unit of planning (the tile's full service), the objective (value of work done per
hour, with required work as constraints) and the weights (one currency), and keep what works (the path shape, the
engine-exact time model, melon / dawn / delivery logic).

## 2. Path shape is not the problem (panel_path_metrics.py)

Path = consecutive worked tiles adjacent in the grid (graph path); a gap = tiles walked without work between two
worked tiles.

| Radial (outbound) hand-day | DSM | KB78 |
|---|---:|---:|
| hand-days a world | 177 | 172 |
| transitions that are path steps | 82% | 85% |
| pure path / near path (max gap 1) / gap 2-3 / jump 4+ | 31 / 50 / 18 / 1% | 35 / 45 / 18 / 2% |
| tiles walked without work | 2.1 | 2.4 |
| worked tiles / ops / steps | 6.6 / 13.6 / 8.4 | 7.2 / 12.6 / 9.0 |
| ops per worked tile | **2.06** | **1.75** |

| Returning hand-day (back within 1 of the shed mid-day) | DSM | KB78 |
|---|---:|---:|
| hand-days a world | 32 | 36 |
| path steps / jump 4+ | 68% / 12% | 79% / 5% |
| ops | 10.1 | 11.2 |

The user's principle (radial hands: missions on a path or almost a path, few walk-only tiles, is near-optimal) already
holds for 80% of our radial hand-days. The difference is what happens on the path: DSM visits fewer tiles and does more
at each (2.06 vs 1.75 ops a tile, 1 op more a hand-day on 0.6 fewer steps). DSM's returning hands are the less
path-like ones (they walk home). The long jumps (hand 8, day 17) are real but rare (2% of radial hand-days).

## 3. Structural findings

### 3.1 Required work is routed first, value second (the decomposition)
The mandatory search places every required op, minimising route hours; optional work is inserted afterwards by a greedy
fill into whatever time is left.
- A route's composition is fixed before anyone asks what else is worth doing on the tiles it visits. 84 of 89 routes at
  pens with an unplaced collect worth 80 already end at 24 with required work (`panel_fert_path.py`, plans).
- The search cannot trade a longer route for more valuable work, or prefer the tile with more work on the same path.
- Freed time (every lever this session that saved hours: farmer hour 0, wheat pickups, spawn slack) re-entered the
  greedy fill and became walking, not work (KB91 / KB92 / KB97 / KB101: work unchanged, moves up).

### 3.2 The unit of planning is an op piece, not a tile's service
A pen's day is split into up to four independent pieces: the required part (search), the collect (pool D/E, also a
fertilizer source for pairing), feed+care (pool C if worth >= 150 else D/E), a deferred harvest (D/E). Each is placed
by itself. Result: 10.5 tiles a day served by 2+ hands (DSM 7.6); pen visits 1.6-1.8 ops (DSM 2.2-2.8); strawberry
harvests without the watering on the same visit 6.3 a day (DSM 2.5) (`panel_tile_coverage.py`).

### 3.3 The search objective counts hours only
`cost = 1000 x (lateness + supply failures) + wu x route hours + 1.0 x extra steps between stops - 2.0 x pens on the
way out (capped)`.
- No value of work (all its ops are required), so it is indifferent to how much optional work a route could pick up.
- The hop term double-counts walking already in the route hours; the pen credit is an ad-hoc coupling to fertilize
  pairing.
- Nothing about where a route ends or how full it is; packing every route to 24 with required work is its optimum.

### 3.4 Search mechanics
- Start: angular arcs of equal work (ops + 1.5 a stop), matched to hands by an angle proxy. Arcs ignore where the work
  sits along a path and which spawn tile suits them (first stop 1.47 steps from the hand's spawn tile vs 1.20 from the
  nearest one, `panel_spawn_first.py`).
- Annealing: 2,500 iterations, moves limited to one stop, to routes within 3-4 tiles. No move takes a cluster to the
  neighbour whose area it sits in (hand 8) or re-matches whole routes to spawn tiles; tried after the fact, whole-route
  swaps could not move first stops (KB102 / KB103) because the fills reshape routes afterwards and finished routes are full.

### 3.5 Phase order overrides value order in the fills
Phase C (outbound hands) sees waterings / fertilizes / big feed+care bundles only; stand-alone collects (80) and
deferred harvests are offered only in D/E, after C has used the time. A watering scored at 5 coins/h can take the hour
a collect at 80 needed. Offering collects in C (KB93 / KB94) only stole fertilize-pairing collects because routes were
already full of required work - the problem is 3.1, not the phase list alone.

### 3.6 Plan once, never revisit
The plan is made at hour 0 and executed open-loop (only the hour-2 spawn remap and op-level skips). Deviations
(a skipped water, a missing wheat, a spawn off by a tile) are never re-planned; the day's last hours strand (115 idle
hours a world, 46 of 68 idle hand-days planned short, `panel_end_idle.py`).

### 3.7 Midnight and deliveries after the fact
Turnarounds, DSM's return count and go-home drops are inserted into routes already packed, so each costs production.
The dump order (farmer, then hands by hire order) makes the hour-1 hires' goods the ones deleted (7.8 of 9.0 units,
`panel_dump_units.py`) - the plan does not know the order.

## 4. Weights

One currency is missing: the planner mixes model values, floors and bonuses. Each should be the op's marginal coins
(output gained or loss avoided, net of inputs), and a single labour shadow price should decide what is worth an hour.

| Weight | Current [KB78] | Role | Problem |
|---|---|---|---|
| maintenance-module value | per job | op value | the only modelled value; everything below overrides or replaces it |
| default op value | 50 | op with no module job | arbitrary; unrelated to the op's effect |
| `sd_water_tomorrow` | floor 10 | WATER on a dry plant | a guess at tomorrow's labour; a watering that saves a fertilized production night is worth far more, a redundant one nothing |
| `sd_feed_bonus` | +20 | FEED / CARE | flat bonus regardless of the bank, the animal's remaining nights, the product's price |
| `sd_collect_floor` | floor 80 | COLLECT | above the sale value (~41) and above a wheat fertilize's worth (~1 unit x 36 - 0.6 x 41 = 11), below a strawberry fertilize's (~140 - 25); the real value is the best use of that unit |
| fertilize (`sd_tier_fert_exact`) | gain x price - 0.6 x fert price | FERTILIZE | the only exact value; the 0.6 charge is a tuned constant |
| `opt_harvest_frac` / `hp_frac` / `sd_tier_anim_harv_frac` | 0.15 / 0.5 / 0.1 | early / window / deferred harvests | three fractions of held x price for the same kind of decision |
| `sd_hard` | +5000 | survival op | fine as a constraint marker |
| `plan_value` | 400 | plant / build / place | irrelevant (mandatory) |
| `sd_tier_anim_c_minv` | 150 | which feed+care joins phase C | a pool gate, not a value |
| `sd_tier_rate_c` / `sd_tier_rate` | 5 / 1 coins an hour | fill thresholds | far below any labour shadow price (~40-70); with phase ordering they decide which hours go to low-value work first |
| `sd_tier_hop_w` | 1.0 | cost per extra step | double counts walking |
| `sd_tier_coll_w` | 2.0 | pen credit on the way out | ad-hoc coupling |
| `sd_tier_iters` / `sd_tier_offsets` | 2,500 / 4 | search effort | small for ~100 stops and 12 routes, but more effort on this objective would only pack required work tighter |

## 5. What a sound foundation looks like

### 5.1 Unit: the tile's service
For every tile, the day's service = all ops worth doing there today (required and optional) with their order, hours and
marginal values; a visit performs the service (or a prefix of it when time runs out). Pens get feed + care + collect +
harvest together, a producing strawberry harvest + water (+ fertilize on its fertilize days) together.

### 5.2 Objective: value per hour, required work as constraints
Maximise the total value of services done, subject to: every required op done by its deadline, each hand's hours
(steps + ops <= 24 - start), supply (fertilizer / wheat carried), the midnight load. A labour shadow price lambda
(coins an hour) prices time: a service or a detour is worth including when its value exceeds lambda x its hours.

### 5.3 Routes as paths (the user's principle)
- Radial (outbound) hand: a graph path from its spawn tile outward through tiles with service, few walk-only tiles,
  prize-collecting: pick the path that collects the most service value within the hand's hours. Generate candidate paths
  from each access tile (beam search that prefers high value density and allows at most one connector tile), then choose
  one path per hand covering every required tile (set packing: greedy by value, then local exchange of path segments).
  The hand is chosen by spawn tile, exactly (the hour-0 spawn tiles are known).
- Returning hand: its harvest targets form a path whose end is near the shed at the drop hour (strawberries on harvest
  days, pens with produce), then a second path out; the drop hour set by the sale plan.
- Stragglers (hand 8): a required tile off every path is attached to the path it is nearest to, paying its connector
  steps at lambda.

### 5.4 Keep
The engine-exact route time model (`_tier_eval`), the spawn rules, melon hands, dawn legs, deliveries, the executor and
the market code.

### 5.5 Build and test
A separate planner mode behind a flag (`sd_path_planner`), replacing the mandatory search and the fills for outbound
segments. First on the labour viewer world (112602061) with the viewer, then 40 worlds. Report path metrics, ops per
tile, idle hours and shared tiles next to margin.
