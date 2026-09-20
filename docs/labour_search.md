# Labour arrangement as a search problem (2026-09-20, first milestone: offline benchmark)

`scripts/labour_search.py [every_nth_tape] [seconds_per_day]` - no games. Result file
`results/fresh/mg_tape/labour_search_73.json`.

## The problem
Each day: a set of jobs (one unit's commands on one tile in one stay: HARVEST, PLANT, WATER, FEED, CARE, ...), the
farmer (free, from hour 0, starts at (4,4)) and hired hands (n-th hire = fib(n); a hand acts from the hour after its
hire and spawns on a shed tile). Assign and order the jobs so that every route ends before midnight, with as few hands
as possible. The benchmark instances are HER OWN days, read off the tape calendar of her 584 recorded games.

## Time model (calibrated against her)
Route = PICKUP steps at the spawn tile (one per item type: wheat for FEED, fertilizer when the route applies more than
it has collected so far, an animal for PLACE) + Manhattan travel + one step per command. A job that needs a purchase
of the day (PLANT, PLACE, BUILD_*) may not start before the hour she started it; when two units work one tile the
order is kept; the same unit twice on a tile is one job. Produce she delivered the same day must be delivered the
same day (walk to the shed + one DROP after the last such job); the rest rides home free at midnight - she does that
on 86% of her produce-carrying hand-days. In this model her own routes cost **220.8 steps a day against 222.5 busy
steps she really used** (2.9 of those are waits, 7.7 PICKUPs, 4.0 shed drops); 0.87 units a day do not fit the model
and are left exactly as she routed them.

## Search
2-opt / or-opt on every route, then empty one hand after another by cheapest regret insertion into the others,
ruin-and-recreate in between. 0.14 s a day on average, 0.33 s worst case; a 1 s budget finds the same (the act limit
is 1 s plus a 60 s bank).

## Result (73 tapes, 1,898 tape-days, days 3-28)
**A. Same jobs, fewer hands.** At least one hand goes on 73% of days (one 45%, two 22%, three 6%): **9.74 -> 8.67
hands a day, 1,363 of her ~4,720 wages a game.**
| days | jobs a day | hands | wages saved a game |
|---|---|---|---|
| 3-11 | 38 | 7.78 -> 6.18 | 400 |
| 12-17 | 57 | 10.42 -> 9.10 | 516 |
| 18-23 | 64 | 11.00 -> 10.40 | 297 |
| 24-28 | 61 | 10.94 -> 10.56 | 150 |

**B. Room for the servicing she skips.** She leaves 106 FEED / CARE jobs a game undone (almost all from day 12 on).
91 of them fit at her hand count, 66 still fit after the hands of A are gone.

How this squares with the earlier slack study: each hand's own ORDER is within 4% of optimal and her idle time is
fragmented (two steps a hand at the end of the day), so nothing can be added hand by hand (that is why the in-place
CARE layer found 1.5 slots a game). Re-ASSIGNING jobs across hands consolidates those fragments: her 12% idle is
about 1.2 hands a day, and the search collects one of them.

## What it is not yet
A model, not the engine. Open risks: in-route inventory chains (wheat cut on the way and fed from the same hand),
shed stock for the PICKUPs, the shed cap, and that a day run by the search replaces the tape's crew commands
wholesale (dropping a hand changes every hand index) while the tape keeps the market orders. Next milestone: an
executor that turns the day's routes into commands, validated first on her own worlds (must tie her tape before it
may beat it), then on the ladder panel.
