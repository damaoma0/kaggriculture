# Time-based path partition for the post-day-11 solver (2026-09-30)

## The design (user)

"We don't use a value based approach, but a time based." Every tile's work for the day is split into mandatory,
non-mandatory and slack hours (1 op = 1 hour, 1 tile walked = 1 hour). Each ordinary worker gets one path-like route of
adjacent tiles from the shed such that

- mandatory + walking <= the day (hard),
- mandatory + non-mandatory + walking <= the day (target),
- everything including slack >= the day + 1 hour (the worker never runs out of work).

Early-morning bring-backers plan their first leg before all other workers; their path budget loses only the return trip
and the walk from the shed to the second leg's start. Over time, cut by priority (slack, then non-mandatory) and then by
value (lowest first); mandatory is never cut. Objective under the constraints: fewest tiles walked. "Absolutely useless
jobs" are not jobs at all - they must not pollute the slack list.

## What DSM drops after day 11 (the evidence for the classes)

`scripts/dsm4q_dropped_jobs_20260930.py` (43 DSM-new games replayed from both seats' recorded actions, cash reproduces
43/43; dawn state vs the state after the day's last unit actions). Per game per day, days 11-24 (25-29): DSM keeps
~99% of deadline-tonight work (keep-alive and seedling waters, maxed harvests, fertilizer, at-risk feeds, full pens),
~81-99% of bonus-tonight work (window waters, fertilized production waters, bank feeds), and drops most slack
(alternate-day waters 71-77%, other feeds 24-59%, cares 10-31%, harvests of still-growing crops 67-74%, pen products
26-54%). Details in docs/dsm4q_day9_handover_20260930.md ("DSM's dropped optional jobs after day 11").

Time budget on DSM's farm (op-hours per day, days 11-24): mandatory 55-62, non-mandatory 60-64, slack 84-102 (DSM does
~40); DSM's crew ~12.3 workers = 284-297 unit-hours: ~4.6 h mandatory + ~5 h non-mandatory + ~9.5 h walking + ~0.8 h at
the shed per worker, the rest slack; idle 0.5 unit-hours a day for the whole farm. The three constraints hold for DSM.

## Job model (`scripts/path_partition_20260930.py`)

Engine facts (kaggriculture.py 1.32.7): units start the day on the shed-access tiles (4,4) (5,4) (4,5) (5,5) (farmer
from hour 0, hires from the hour after the hire); PICKUP only there, one item type per action, no inventory cap; any tile
is walkable; FEED needs wheat in hand; a harvested one-time crop leaves the tile empty (replant = HARVEST, PLANT, WATER on
one visit); a weed needs DIG before PLANT; a new plant starts one dry day down; fertilizer_available returns every night
for every animal (not cumulative); care banks only on a fed day and pays at the next production, not tonight's.

The day's plan (which one-time crops are harvested, which tiles planted) is DSM's own decision that day - this is a
routing check, not a plan check.

| class | jobs |
|---|---|
| mandatory | water a plant not watered yesterday (weed tonight otherwise); replant (DIG if a weed) + seedling water; harvest per the plan; feed an animal unfed yesterday (escape otherwise); empty a full pen / full strawberry-tomato producing tonight |
| non-mandatory | window water of a one-time crop (+1, +2 fertilized; also before its planned harvest); water of a fertilized ongoing crop producing tonight; feed of an animal producing tonight with a banked bonus; fertilizer collection; fertilize (gain > fertilizer price, at most as many as the day's collections) |
| slack | alternate-day water (only moves tomorrow's water), care of a fed animal and feed + care pairs (bank +1 for a later production), products of pens / plants not full |
| useless (not listed) | water / feed / care with no production left before day 29, harvesting still-growing crops, digging weeds nobody replants, fertilize worth less than the fertilizer or without supply |

## Partition

Work tiles sorted by angle around the shed (then distance); cut into K contiguous sectors with load (mandatory +
non-mandatory hours + ~1.2 h walk a tile) proportional to each worker's budget; each sector becomes an open path from its
nearest shed tile (nearest neighbour + 2-opt on tiles walked); `fit` keeps all mandatory work, cuts slack then
non-mandatory lowest value first while over budget, then puts back what still fits. Twelve sweep starts, local search on
the best three: boundary tiles shift between neighbouring sectors while the score improves, in the user's order - no
mandatory over the day, no non-mandatory cut, every path >= day + 1 h with slack, then fewest tiles walked. Budgets: DSM's
units that day (24 h farmer, 23 h a hand hired at hour 0), minus DSM's own early bring-back legs (a unit that harvests and
drops at the shed by hour 12; their jobs leave the pool).

## Offline result on DSM's farms

774 DSM game-days (43 games x days 11-28; results/fresh/path_partition_20260930/run_days11_28.txt), per game-day:

| days | jobs M / N / S (h) | DSM units, tiles walked | ours at DSM's crew: tiles walked, N cut, S cut, M over | fewest workers with no M over / N cut | paths short of day + 1 h (idle h) |
|---|---|---|---|---|---|
| 11-15 | 60.7 / 71.4 / 73.7 | 12.5, 111.5 | 97.6, 0.0, 39.7, 0.0 | 11.6 | 0.7 (0.3) |
| 16-20 | 55.6 / 69.1 / 90.2 | 13.0, 118.3 | 98.8, 0.0, 43.0, 0.0 | 11.2 | 0.6 (0.2) |
| 21-25 | 65.3 / 67.8 / 80.6 | 13.0, 109.3 | 96.6, 0.0, 36.1, 0.0 | 11.5 | 0.6 (0.2) |
| 26-28 | 53.0 / 70.4 / 52.4 | 12.5, 119.4 | 97.3, 0.0, 16.2, 0.0 | 10.7 | 4.4 (8.0) |

With DSM's crew and DSM's plan the partition does every mandatory and non-mandatory job and 34-47 h of slack (DSM ~40),
walking 12-19% fewer tiles than DSM (~10% after DSM's ~5 bring-back-leg moves); the same work fits 1-1.8 fewer workers
(hires by demand). Days 26-28 run out of work (4.4 paths short, 8 idle hours) - fewer hires at the end. Bring-back legs
(DSM's own, planned first): 1.7 units a day, 6.5 unit-hours, 2.2 jobs. Useless jobs filtered a game-day: fertilize
without supply 15.1 / worth less than the fertilizer 11.7, care with no production left 1.7, dig with no replant 1.3,
water with no production left 0.5, feed 0.2. Before the boundary search (sweep only): 1.7-2.8 paths a day short of
day + 1 h, 4.0 idle hours on day 15.

Viewer: `scripts/path_partition_viz_20260930.py EP DAY` -> viz/path_partition_EP_dDAY.html (left: our paths with their
jobs, mandatory solid / non-mandatory ring + dot / slack ring / cut crossed; right: DSM's unit tracks, bring-back legs
dashed); e.g. viz/path_partition_115518441_d15.html.

## Caveats and next steps

- Static plan on the dawn state with DSM's harvest / planting decisions and DSM's bring-back legs; no market timing
  (goods collected on a path reach the shed at the midnight dump and sell the next day), no seed / wheat cash limits, no
  breakage. Walking is Manhattan with free movement (engine: any tile is walkable).
- Next: wire the partition into an executor for one world (paths fixed at hour 0, cut on the fly by priority then value
  when a worker falls behind), show it in the step viewer, and compare the day's end state with DSM's.

## Full stack (2026-09-30): semantic planner + tiler + path-partition executor

`scripts/fullstack_smoke_20260930.py EP [--tag A] [--project d9c4o] [--cassette FILE --until-day N]`: days 0-10 are DSM's
recorded actions (exact handover at the day-11 dawn); the semantic strategy's planning layer (loaded from the candidate
project: policy observe / propose, plant extras and gates, cassette, free-fill, `build_plan` tiler) observes every step
and plans every hour 0 from day 6; from day 11 the day of its tile plan (plantings, one-time harvests, structures and
animals still missing from our board, digs, crew) is executed by the path-partition executor (`TPPAgent`,
scripts/tpp_smoke_20260930.py, arm-i settings: priority bring-backs, strawberry / wool / milk sold first, fertilizer
collection valued at use, animal collection as slack). Recorded opponent with its logged weeds and purchase credit.

| final cash (DSM's own continuation) | 115518441 (117,085) | 115524856 (95,168) |
|---|---:|---:|
| executor on DSM's hindsight plan | 100,132 (-16.9k) | 78,045 (-17.1k) |
| full stack A: planner as configured (cassette to day 12, then the policy) | 97,702 (-19.4k) | 73,457 (-21.7k) |
| full stack B: DSM-only cassette to day 29 | 93,430 (-23.7k) | 68,874 (-26.3k) |
| full stack C: merged cassette to day 29 (other leaders' animals / strawberries from day 12) | 92,032 (-25.1k) | 71,864 (-23.3k) |

No errors, planning 1.4-1.6 s a game. The planner costs 2.4-4.6k against DSM's hindsight plan; the executor is the larger
gap (~17k with DSM's own plan). Season cassettes lose to the existing policy after day 12. Full stack A vs DSM in
115518441, days 11-29: wheat -9.4k (677 made vs 812, 312 sold vs 586), eggs -2.6k, wool -2.4k (sold at $114 vs $135),
fertilizer sales -2.3k, carrots -1.3k, tomatoes -1.1k, strawberries -1.0k (235 vs 266 sold at $175 vs $158).

## Openings in the full stack, and our executor against the candidate's own (2026-09-30)

Openings tried in front of the path-partition executor (days 0-10, then the planner + our executor from day 11):
DSM's recorded prefix (A), the 4Q tape routers for all of days 0-10 (`--opening agents/router4q_dsm_lr.py` = RD,
`router4q_md_lrh.py` = RM; f2 = the executor also buys the plan's land and buys cash-first), and the candidate's own days
0-10 (`--opening candidate` = Cand: its tape router days 0-5, then its cassette + tier executor, Q4 on day 10). The
existing day 6-8 / 9-10 executors (E68, and our days 9-10 copy arm b) take a tile plan as input (DSM's hindsight plan in
their tests) and are not wired in yet.

| final cash (vs DSM) | 115518441 (DSM 117,085) | 115524856 (DSM 95,168) |
|---|---:|---:|
| A: DSM prefix + our executor | 97,702 (-19.4k) | 73,457 (-21.7k) |
| RD / RDf2: DSM-new tape router + our executor | 99,169 (-17.9k) | 72,366 (-22.8k) |
| RMf2: M&M tape router + our executor | 97,424 (-19.7k) | 42,097 (-53.1k; 3 quadrants at day 11) |
| Cand: candidate days 0-10 + our executor | 97,793 (-19.3k) | 75,337 (-19.8k) |
| candidate alone (its own executor all game, d9c4o.p0) | **115,966 (-1.1k)** | **86,281 (-8.9k)** |

"Candidate alone" = the d9c4o arm of the day-9 handover study (live n18rc223, det clock, + the DSM-new cassette for
days 6-11, Q4 on day 10, `sd_tier_defer_locked`, `sd_tier_idle_steal`) playing all 30 days itself (`--prefix 0` in
`scripts/dsm4q_d9_gap_20260930.py`): live tape router days 0-5, cassette + tier executor days 6-10, the live semantic
planner + tiler + tier executor after. Same world, shops and recorded opponent as every row.

**Caveat (stale executor config):** "our executor" here is this thread's arm-i configuration of
`scripts/tpp_smoke_20260930.py`. The other thread's TPP driver (its tpp_oneday.py; memory tpp-mends-0930) is further on:
the dig-before-harvest bug below is its `harvest_first` fix, goose feed + care pairing was measured there (neutral to
negative on margin), and its best configuration is -4.3k cash vs DSM over 43 worlds on DSM's plan (arm i: -17k on two).
The executor gap below must be re-measured with that configuration before it is quoted.

Cand and the candidate alone reach the identical day-11 state (4 quadrants; cash 4,959 / 4,325), so the whole
difference, **-18.2k / -10.9k, is our executor against the candidate's tier executor on days 11-29**. Traced with
`scripts/exec_loss_trace_20260930.py EPS fsCand.p264,d9c4o.p0` (ours | candidate's):

- **Strawberries dug with their last berries** (the plan's retirement removals): 15 / 26 plants dug holding 2 berries,
  30 / 52 berries lost (~$5.2k / ~$6.5k); the candidate loses none. Our tiles made as many or more berries (285 vs 282,
  306 vs 261) because our fertilizer reaches the production days (unfertilized productions 7 vs 28, 4 vs 41). Fix:
  HARVEST before the DIG.
- **Geese fed every other day** (".F.F.F" on most geese): a feed that cashes a banked care bonus is non-mandatory and gets
  cut, the care (slack) is still done, and the next day the feed is mandatory again (unfed yesterday). Banked eggs wiped
  29 / 39, cared-but-unfed goose-days 12 / 16; geese fed 67% / 71% of days vs 83% / 88%; eggs 201 vs 279, 240 vs 307
  (revenue -3.8k / -3.7k). Fix: feed and care as one pair (a pending bank makes today's feed as binding as a keep-alive
  feed; no care unless tomorrow's feed is planned).
- Wheat -4.1k / -2.5k (42 / 57 fewer harvested; 131 / 111 fewer waters overall, so fewer window bonuses; 101 / 63 fewer
  sold): not traced yet. Fertilizer sales -2.2k / -2.9k is mostly a trade for the extra berries and tomatoes above
  (tomatoes +1.1k in 115518441). Sheep escapes with wool on the tile: 10 / 10.
