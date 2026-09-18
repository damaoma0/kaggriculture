# Router work-order scheduler

## Result

The prototype reproduces the public router’s terminal cash and complete sales/spending ledger in all 16 normal seed-seat pairs. It makes zero late task attempts in those games. This establishes production preservation on router farms, not a stronger economic policy.

Seed 93100 was used for debugging. The frozen implementation was then tested on seven fresh seeds (93101–93107), both player seats, with natural shop RNG and a public-router opponent. Each pair has normal and displaced-worker conditions and both controllers: 56 held-out games plus eight development games.

| Held-out condition | Public router mean cash | Scheduler mean cash | Paired difference |
|---|---:|---:|---:|
| Normal | 109,879.9 | 109,879.9 | +0.0 |
| Workers displaced | 110,986.1 | 109,590.4 | -1,395.7 |

Under displacement, scheduler cash was higher in 8/14 pairs, equal in 0, and lower in 6. Paired differences ranged from -22,001 to +9,557. Seats share seeds and should not be treated as independent samples.

## Intervention and scope

Both controllers start from the same native-router prefix at turn 224 (day 9, hour 8). The intervention moves the farmer and first two hired workers to another unlocked tile exactly two Manhattan steps away, using row-major tie-breaking. Assets, cash and inventories are unchanged at the checkpoint. This is an artificial execution-recovery test, not normal-game win-rate evidence. Natural later randomness can diverge after changed farm actions.

The scheduler preserves crop calendars, task ownership, original branch rules and market plans. Each task has a tile, preferred turn and predecessor. It paths from actual positions, attempts overdue tasks in order, and reuses the router’s weed repair and projected-shed sales logic. Hiring adds position constraints because worker spawn locations depend on occupancy. It does not reassign work between workers, check every resource dependency, repair arbitrary layouts, or choose new investments. Daily unfinished jobs are abandoned at the day boundary.

## What the routines teach us

- Trace 1 establishes strawberry cohorts on days 5, 6, 7, 8 and 11, alongside rolling wheat cycles.
- A representative day-5 strawberry receives fertilizer on days 14 and 18 and yields two units at each harvest on days 15, 17, 19 and 21. Fertilizer timing around production nights matters more than a generic “fertilize available crops” rule.
- The router continues expanding after the opening: trace 1 purchases land on days 6 and 11. A maintenance-only continuation misses part of its production system.
- Apparently redundant movements can determine where the next worker spawns. Removing them without modeling hiring changes downstream routes.

## Validation

- 14,495 compiled task/waypoint targets checked against actual positions in four full source trajectories; all agree.
- Every evaluated game reached 720 states without an invalid/error status; terminal cash reconciles exactly with recorded revenue and spending.
- All 16 normal paired games match complete accounting ledgers, including product quantities sold.
- Held-out final route coverage: {'main': 8, 'yarn': 4, 'yarn_carrot': 2}. This does not establish runtime coverage of all four compiled branches.
- Earlier incorrect spawn reconstruction and missing hiring-constraint smoke tests are retained in separate directories and excluded from these results.

## Next research step

Keep the conditional public router as the selected competitive baseline. Use this executor as a controlled foundation: replace fixed task ownership with daily allocation using crop deadlines, travel, available inventory and delivery capacity; first require unchanged production on the router farm, then evaluate alternative crop cohorts and investments. The new representation makes those changes measurable without rediscovering the production calendar through a broad parameter search.

[Detailed crop routines](router_routines.md) · [Results](../results/fresh/router_scheduler/results.json) · [Source hashes](../results/fresh/router_scheduler/manifest.json)

## Production versus cash in the largest reversal

On seed 93106, seat 0, both controllers retain the YARN branch. The displaced replay earns 112,435 versus 90,434 for the scheduler, despite selling 194 versus 249 milk units and 252 versus 262 strawberries. Thus branch selection alone does not explain the reversal. Changed production/sales timing and subsequent market/randomness paths are confounded in this natural-game test; no single causal explanation has been isolated.

This is why recovery should be judged using both task execution and realized economic outcomes. Preserving the original production schedule is an engineering milestone, not evidence that the schedule is economically optimal.
