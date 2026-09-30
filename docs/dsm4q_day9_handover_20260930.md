# Us vs the new DSM on days 9-10: the day-11 board after an exact day-8 handover (2026-09-30)

User: "investigate discrepancy between us and new DSM during days 9-11, assuming an exact handover from day 8" /
"You hand off at day 11 and what we only care is your board then" / "plan your productions based on DSM conditioned on
shop reveal" / "buy Q4 with same or almost same timing vs DSM, then deliver as close a board as possible. Lead on cash
is failure to replant."

Setup (`scripts/dsm4q_d9_gap_20260930.py`, `scripts/dsm4q_d11_board_20260930.py`): 43 recorded games of the new DSM
(56692773, four quadrants). Our seat replays DSM's own commands through day 8 (`--prefix-steps 216`), the candidate
plays from the day-9 dawn, the opponent replays its recorded commands (exact market credit, recorded weeds). The
reference is DSM continuing its own game (43 / 43 controls reproduce both recorded cash totals). Compared: the board at
the day-11 dawn (step 264). 40 / 43 handovers are exact (3 differ by a 1-2 tile midnight weed: the forced opponent weeds
shift our farm's weed draws; excluded). Arms are det-clock (`n18rc223d` = the live n18rc223s).

## Baseline: live n18rc223d (40 games)

Day-11 board: 37.6 tiles differ from DSM's (25 of them DSM's 4th quadrant, which we never buy), 12.6 on shared land;
wheat 21.4 vs 28.3, tomatoes 0.9 vs 5.6, strawberries 23.1 vs 25.4; cash $9.6k vs $2.7k, shed wheat 15 vs 27. DSM buys
Q4 on day 10 in 43 / 43 games (unlock seen at hours 10-13).

## Arms (9 paired games, exact handover; cassette learned on the other half of the games)

| arm | what | composition distance | tiles differ | empty | Q4 bought |
|---|---|---:|---:|---:|---|
| n18rc223d | live | 28.7 | 43.0 | 4.6 (+25 locked) | never |
| d9c4a/b | DSM-new cassette (days 6-11 targets by revealed shop types, wheat scale 1.0) | 18.0 | 33.7 | 24.7 | d10 h11-12 |
| d9c4c/d | + keep the tier plan through the day-10 unlock, virtual Q4 land, land reserve day 10 | 18.2 | 37.7 | 23.1 | d10 h10 (9/9) |
| d9c4e/f | + same on day 9 | 17.1 | 34.7 | 24.0 | d10 h10 |
| d9c4i/j | + executor `sd_tier_defer_locked` (stops on a still-locked quadrant go to the route's end) | **16.1** | 35.0 | 21.8 | d10 h10 |
| d9c4k/l | + collected fertilizer sold the same day, seeds before feed wheat | 17.9 | 38.4 | 22.1 | d10 h10 |
| d9c4o/p | i/j + `sd_tier_idle_steal` (a finished hand takes other routes' unstarted plantings) | **15.8** | 35.0 | 21.3 | d10 h10 |
| DSM | | 0 | 0 | 11.8 | d10 h10-12 |

Composition distance = tiles that would have to change kind to match DSM's counts (positions ignored). The tile-exact
distance stays ~35 for every cassette arm: DSM puts its crops on other coordinates than our tiler.

## Where the remaining difference comes from (planting funnel, per game)

| | cassette asks | plan keeps | planted | alive next dawn | DSM planted |
|---|---:|---:|---:|---:|---:|
| day 9 | 12.5 | 9.0 | 4.5-6.3 | 4.4-6.0 | 11.9 |
| day 10 | 22-23 | 22-23 | 15.5-17.3 | 14.9-16.5 | 22.0 |

The cassette asks for DSM's amounts; execution drops them:
1. **Mid-day unlocks.** The executor switches to the old hourly dispatcher at a land unlock (live build). Keeping the
   tier plan (`unlock_keep_tier_days`) with `sd_land_virtual` planned Q4 at hour 0, but the routes reached Q4 before the
   hour-10 unlock and `_tier_check` returned "skip" on a LOCKED tile (log: `skip PLANT WHEAT` on tiles 66 / 67 / 77 / 78
   at hours 3-6). `sd_tier_defer_locked` (results/fresh/dsm4q_d9_20260930/exec_defer_locked.py) fixes it: world
   115518441 plants 13 Q4 tiles by hour 23 (DSM 14; before 8). DSM's own Q4 pace is slow too: first plantings at hours
   12-13, 12 by hour 22, about 4.5 hands on Q4 from hour 15.
2. **Day 9 in worlds where Q3 comes that day (5 of the 10 test worlds, 7 of 40 overall): cash.** After the $2,000
   land at hour 4-5 our cash is $3 from hour 8; strawberry seeds wait (`wait_noseed` 26) and are skipped (world
   115515236: 0 of 13 planned). DSM spends on seeds (strawberries / tomatoes / wheat), the cassette spends ours on cows
   and geese first. The day-9 revenue gap is FERTILIZER (40 games, live build): both sides collect ~16.7 on day 9, DSM
   sells 11.7 of them the same day, we sell 5.5 (only yesterday's, from the shed; today's collection rides in hand to
   the midnight dump: recipe sd_fert_sell 1 / fert_hold 1): -$458 of the -$412 day revenue gap. Wool is equal (12.1
   vs 11.9 sold; one world -6). Arm k/l (sd_fert_sell 0, fert_hold 0, seeds first) did NOT sell fertilizer the same
   day (3.0 sold vs DSM 10.9: the hands kept it for fertilizing); its day-9 lift 4.5 -> 6.3 plantings came from seeds
   first. The same-day recipe also needs fertilizing off (sd_fert_frac high) and a low deliver_value: not yet tested.
   **Day 9 fertilizer = cash (user rule, arm d9c4q/r, executor `sd_fert_cash_days [9]`, exec_fert_cash.py: no
   FERTILIZE; a hand at the shed places its fertilizer, sold at once; a finished hand walks home with it).** Day 9:
   fertilizer sold 4.8 -> 9.2 (DSM 10.9), revenue $2,686 -> $2,970 (DSM $3,237), seeds bought ~$163 -> $262 (DSM $579),
   plantings 4.5 -> 6.2 (DSM 11.9). The day-11 board does not improve (composition 16.9, weeds 4.7 vs DSM 0.3): per game
   2.4 older plants (wheat / strawberries) die on day 10 after two dry days and 1.2 seedlings are planted at hour 22
   without their water. Day-9 spend (10 games): seeds $163 vs $579, animals $1,430 vs $1,220 (cassette cows), hires
   $205 vs $161; DSM keeps cash positive all day (world 115515236: fertilizer placed in the shed at hours 2 / 6 / 14,
   seeds bought one at a time to hour 21, no cows that day).
3. **Day-9 capacity clip.** The tile compiler places the cassette's animals before its crops: new coops take the few
   free dawn tiles (world 115521612: 5 free tiles -> 5 coops, 0 crops; DSM 3 geese + 2 crops).
4. **Crop placement.** Our plan replants harvested melon tiles with tomatoes (2.0 a game), DSM with wheat (4.5 a game);
   DSM's tomatoes go to Q4.

Wheat is the largest count gap (20.7 vs 28.7), then empty tiles (+9.5) and weeds (+2.8).

## E68 (the other thread's days 6-8 executor) as context, and on days 9-10

- **r2 (other thread, `n18e68r2p<world>`)**: DSM (3Q, 56619023) exact state at the day-6 dawn, DSM's own tile plan of
  the world (`tile_exact`), E68 on days 6-8 (money runs first, land at the first tick the money covers it, hourly
  re-plan), stop after day 8. 9 worlds: day-9 dawn board 6.7 tiles off DSM's (4-11), cash $229 vs $226, Q3 bought at
  hour 2 in 6 worlds (DSM hour 7-8). Remaining gap = the new quadrant's wheat on its unlock day (3.3 a world): DSM
  plants 1.5-2.3 tiles an hour from hour 9, r2 0.6-1.3.
- **The same test on days 9-10** (`d9e68p<world>`: DSM-new exact state at the day-9 dawn, DSM-new's own tile plan of
  the world, `scripts/export_tile_plans.py` on data/leader_semantics_dsm4q, E68 days 9-10, stop after day 10):
  - money runs on (days 6-8 settings; fertilizer / wool / milk / eggs brought home at once): collapses on a mature farm.
    Day 9: 19 money jobs, only 10 WATER (DSM ~37), 16 feed / water jobs left "late"; day 10: 40 jobs "late", 5 of 27
    plantings. Day-11 board: weeds 20, strawberries 7.8 vs 26.3 (composition distance 44).
  - money runs off (`d9e68m<world>`): the old land matches DSM's board almost exactly (2.8 tiles off on shared land,
    weeds 0.3 = DSM) but Q4 is bought in 1 of 9 worlds: day-10 melons harvested 26 (DSM 36) but sold 3 that day (DSM
    33; 23 sit in the shed at the day-11 dawn). DSM's day-10 revenue $9,766 = melons $8,281 -> Q4 at hour 10. Day 9:
    wool sold $458 vs DSM $2,386.
- Implication for a days 9-10 executor: E68's upkeep without generic money runs, plus a targeted cash plan - the ripe
  melons harvested early on day 10 and sold at once (Q4 by hour ~10), day-9 wool and fertilizer placed in the shed as
  hands pass it - then Q4 planted from the unlock.

## Learning DSM's own days 9-10 (user: "E68 is learning from what is actually done by DSM")

`scripts/dsm4q_day_profile_20260930.py` (hour-by-hour means over the 43 DSM-new games; any arm for comparison):
- Day 9: fertilizer 5.6 sold at dawn, 11 hires at hours 0-1, ~14 feed wheat bought; wool harvested hours 1-4 and 12
  sold at hours 3-7; ~17 fertilizer collected, 4 placed in the shed, ~6 more sold during the day; ~6 plantings (old
  land) hours 9-22 with seeds bought one an hour; 38 waterings, 17 feeds, 17 cares, 7 idle unit-hours; cash $350-1,170.
- Day 10: 11 fertilizer sold at dawn, 15 hires, 53 feed wheat bought; melons harvested hours 3-7 and 33 sold at hours
  8-11; Q4 at ~hour 10; 12 plantings on Q4 from hour 12 (~1.2 an hour) + 7.5 on old land; 53 waterings; ~0 idle.

E68 with DSM's own money runs (exec_e68_moneycrop.py: crop money jobs; money goods day 9 wool + fertilizer within 2 of
the shed, day 10 melons), DSM-new's tile plan, 9 paired worlds (`d9e68c<world>`):

| | tiles off (Q4 + old land) | composition | Q4 | wheat | strawberries | weeds | cash at day-11 dawn |
|---|---:|---:|---|---:|---:|---:|---:|
| best tier arm d9c4o/p | 35.0 (13.3 + 21.7) | 15.8 | d10 h10 | 20.7 | 23.2 | 3.1 | $4,197 |
| E68 money runs off d9e68m | 26.4 (23.7 + 2.8) | 25.2 | 1 of 9 | 20.3 | 22.7 | 0.3 | $1,127 |
| **E68 + DSM's money runs d9e68c** | **10.9 (4.0 + 6.9)** | **10.1** | d10 h9-10, 9/9 | 26.1 | 22.1 | 4.0 | $3,988 |
| + day-9 waters of ongoing crops d9e68w | 10.9 (4.4 + 6.4) | 10.2 | d10 h7-10 | 25.0 | 23.0 | 3.0 | $3,891 |
| DSM | 0 | 0 | d10 h10-12 | 28.7 | 26.3 | 0.3 | $3,463 |

**One extra hand (d9e68h, tile_exact extra_hands 1): neutral** - composition 9.8, weeds 4.0 -> 3.0 but Q4 plantings
fewer; the extra hand idles (day-9 PASS +11 unit-hours), wages +$490 over the two days. The crew already has 13 hands
on day 10 (14 units, = DSM).

**Hand trace -> seed livelock (fixed).** World 115518441, day 10: unit 9 stood on an open, empty Q4 tile (8,5) from
hour 10 to 14 with $2-5k cash and 2-5 wheat seeds in stock. Its route every hour: PASS now (wait one tick for its own
seed purchase, market orders run after unit actions), PLANT next hour. Each hourly re-plan gave the stock to routes
evaluated first for plantings hours later (`avail_without` subtracts every other route's use regardless of when), so
the ready unit bought again and waited again. Fix in exec_e68_moneycrop.py: `seed_prebuy` (buy now the seeds the routes
plant in the next K hours beyond the stock, money allowing) + `plant_now` (a unit standing on its open planting tile
whose route only waits for a seed plants from stock not used this hour). d9e68s (seed_prebuy 2, plant_now 1):
composition 10.1 -> 8.2, tiles off 10.9 -> 8.7 (Q4 3.8, shared 4.9), day-10 plantings 20.3 (old 10.5 + Q4 9.8; DSM
7.5 + 12.2), day-10 idle 27.9 -> 18.9 unit-hours (17 of them at hours 20-23), tomatoes 4.8 (DSM 5.3), weeds 3.6.

**Dead strawberries were young (user: "did the strawberries reach maturity?").** d9e68s: 28 strawberries (2.8 a game)
died into weeds on days 9-10, ages 2-8 (17 of them the day-6 block at age 4), none had produced, all four harvests
(ages 10/12/14/16) ahead; DSM kept 27 of the 28 tiles alive. Mechanism (world 115508914, tiles 9 / 18 / 19): no water
on day 9 (not at risk, E68 waters ongoing crops only at risk), day-10 survival waters planned at the end of three
routes (done at hour 20), dropped as "late" by the hour-6/7 re-plans and never re-inserted - E68's eviction only
removed tier-3 production jobs, never plantings. Fix: `evict_plan_for_keep` (a keep-alive job may evict plantings,
cheapest seed first) + `keep_by` 16. d9e68k: strawberry deaths 2.8 -> 0.4 a game, weeds 3.6 -> 1.3, strawberries at the
day-11 dawn 22.9 -> 24.0 (DSM 26.3), for 2.1 fewer plantings (mostly wheat: 26.2 -> 25.6). Composition distance
unchanged at 8.2 (a tile is a tile), but in value ~2.4 strawberries x 4 harvests (~$1.4k of future sales) against ~2
wheat plantings (~$0.4k).

**Q4 crew (user: "direct a few hands toward the Q4 border ... delegate less work and have their paths end at the Q4
border").** Staging idle hands toward Q4 (`stage_q`, d9e68g) changed nothing: no hand is idle between hours 8 and 19
(the moves fired only at hours 21-23). Day 10 unit-hours: DSM walks 142 moves, we 172-182; DSM has ~4.5 hands on Q4
from hour 15, we 1.5-2.2 until hour 17. `crew_q` (exec_e68_moneycrop.py): at hour 0 the hands without a bring-back
nearest the new quadrant form a crew; each gets a contiguous snake chunk of the quadrant's plantings (route walks to
the border and waits for the land); other work enters a crew route only where it does not delay its quadrant jobs;
the quadrant's plantings go only to the crew.
- crew 4, strict (d9e68r): Q4 plantings 11.9 (DSM 12.2), Q4 tiles off 1.0 - but old-land deaths 1.9 strawberries +
  3.2 wheat a game (composition 9.1).
- crew 4, keep-alive jobs may cross into crew routes / evict their plantings (d9e68t4p): deaths 0.4 / 0.2 but Q4 back
  to 8.6 (composition 7.8); crew 3 (d9e68t3p): Q4 6.5 (composition 9.1).
- **crew 4 survival-first + day-9 waters of ongoing crops (`water_ongoing {"9": 150}`, d9e68u): composition 7.0, tiles
  off 7.4 (Q4 4.0 + shared 3.4), wheat 27.3 (DSM 28.7), deaths 0.2 strawberry / 0.1 wheat, Q4 plantings 9.8, day-9
  waters 30.7 (DSM 38.3)** - DSM's day-9 watering removes most of the day-10 survival wave that pulled the crew off Q4.
  Remaining: ~1.3 fewer hands on Q4 in the afternoon, Q4 plantings -2.4, empty +5.9 (Q4 +4), the walking surplus.

**Walking and end-of-path watering (user: "could it be a pathing issue?").** Not step-level: per game on day 10 DSM
142 moves / 80 detour steps / 9 reversals, we (d9e68u) 164 / 70 / 12. Our extra moves come from route geometry (field
-> shed hops 9.0 vs 5.8, shed -> field 2.6 vs 1.9 steps a hop, fewer ops chained on one site: field -> field hops 84 vs
119) and the larger loss is idle: 21 PASS on day 10 (16 at hours 21-23) vs DSM 1, work ops 135 vs 169, waters 39 vs 53.
Wheat at age 2 is watered (paired 10 worlds, day 10: ours 7.7 of 7.7, DSM 7.2 of 7.7); the gap is strawberries /
tomatoes on day 10 (5.2 watered vs DSM 12.0). `idle_water` (days 9-10; a hand whose route is finished waters the nearest
unwatered plant nobody plans to water - window wheat / carrots first, then ongoing crops; d9e68v): waters day 10 39.2 ->
42.2, idle 21.2 -> 14.0, plants going into day 11 unwatered 23.1 -> 20.2 (DSM 20.2; strawberries / tomatoes 14.8 vs DSM
13.2) - day 11's keep-alive load now equals DSM's. The day-11 board is unchanged (composition 7.2 vs 7.0).

**Handoff gap in cash and potential goods** (`scripts/dsm4q_handoff_value_20260930.py`; day-11 dawn, DSM's own day-11
quotes for both sides, unfertilized base yields: standing crops' remaining harvests, animals' products to day 29, shed
goods; land not valued), 9 paired worlds:

| | cash | shed stock | standing crops | animals | total vs DSM |
|---|---:|---:|---:|---:|---:|
| live n18rc223d (no Q4: +$4,000 not spent) | +6,064 | -1,039 | -5,497 | -382 | -854 (-4,854 with Q4 at cost) |
| tier cassette arm d9c4o/p | +734 | -1,383 | -3,635 | +271 | -4,013 |
| E68 best d9e68v | +285 | -2,190 | -2,171 | -1,938 | -6,014 |

d9e68v potential units vs DSM: wheat 79 / 104, strawberries 98 / 105, tomatoes 15 / 21, melons 33 / 36, milk 70 / 78,
eggs 109 / 129. Animals: same cow purchases as DSM, but 0.8 cows, 0.2 sheep and 0.2 geese a world are lost on days
9-10 (gone by the next dawn after two unfed days; DSM loses none), and fewer geese bought in 3 of 10 worlds. Shed at the
day-11 dawn: DSM 20.5 feed wheat, 3 melons, 8.1 milk; ours 3.4, 0, 4.3.

Hour profile of d9e68c vs DSM: wool 12.5 sold at hours 3-7 (DSM 12), melons 30 sold at hours 5-10 (DSM 33 at 6-11), Q4
at hour 9 (DSM 10), day-10 plantings 19.2 (DSM 19.7). Remaining: old strawberries dying on day 10 (2.7 a game: E68
waters an ongoing crop only at risk, so the day-9-watered cohort is one survival wave on day 10; 22 jobs "late" in one
traced world), ~4 fewer Q4 plantings, $1.4k unspent. NOTE: these runs use DSM's own per-world tile plan (hindsight,
as r2); the realistic version is E68 on the cassette (shop-reveal) plan.

**Stockpile and pen fixes (user: "a huge gap you underreported ... all are fixable")** - `scripts/dsm4q_stock_flow_20260930.py`
(pens fed / cared / harvested / escaped per day, goods produced / sold / in the shed, feed wheat, day-10 melon harvests),
9 paired worlds, d9e68v vs DSM: day-10 pens fed 14.3 of 20.1 (DSM 19.0 of 21.0), cared 14.9 (19.0), pens harvested 2.7
(4.1); 0.7 cows, 0.2 sheep, 0.1 geese escape a world on day 10 (DSM none); milk produced 4.7 (11.6), eggs 2.2 (3.4),
fertilizer 28.8 (36.2); melons 29.9 (36.0); feed wheat in the shed at the day-11 dawn 3.3 (21.3).
- **Melons: the harvest came before the window watering.** The executor takes ripe melons first (money job, class 0)
  and harvests at once, at 5 units. The engine's WATER on a one-time crop inside its yield window adds +1 unit on the
  spot (+2 if fertilized; `kaggriculture.py` WATER handler), and DSM waters in the same visit and harvests the next hour
  at 6 (6.00 units a harvested tile vs our 4.91). `money_water_first` (money crop visit = WATER, HARVEST when the tile
  was not watered today and is below its maximum inside the window): 35.9 melons (DSM 36.0), 5.98 a tile. Same
  priority, one extra hour a tile.
- **Evening feed wheat** (`eve_feed`, day 10 at hour 18: one wheat per animal for tomorrow minus the shed and hands,
  keeping $300): wheat into day 11 3.3 -> 16.3 (DSM 21.3).
- **Pens at keep-alive priority** (`feed_tier_days {"9": 1, "10": 1}`: feed / care jobs class 1, may evict plantings like
  keep-alive jobs): pens fed day 10 18.9 (DSM 19.0), cared 19.8 (19.0), escapes 0.2 a world; milk 10.4 (11.6), eggs 3.7
  (3.4), fertilizer 34.8 (36.2). **But it costs plantings**: day-9 plantings 8.9 -> 3.0 (DSM 12.7), composition distance
  7.2 -> 16.2, empty tiles 17 -> 27 (DSM 12).

| arm (9 paired worlds), day-11 dawn value vs DSM | cash | stock | crops | animals | total | composition |
|---|---:|---:|---:|---:|---:|---:|
| d9e68v (before) | +285 | -2,190 | -2,171 | -1,938 | -6,014 | 7.2 |
| d9e68x = v + melon water-first + evening wheat | +1,141 | -1,350 | -2,463 | -2,303 | -4,974 | 8.3 |
| d9e68f = x + pens class 1 days 9-10 | +1,435 | -463 | -4,839 | -1,402 | -5,269 | 16.2 |

**Day-9 leak** (the day-10 dawn state valued the same way at DSM's day-10 quotes; x = v on day 9): **-$2,568 a world**
of the -$6,014 (crops -1,861, animals -1,097, stock -659, cash +1,049 unspent). Same crew (10.1 hands, 254 unit-hours);
DSM 130 work ops, we 118: PASS 9.8 vs 4.3 (6.4 at hours 22-23, 2.9 at hours 2-7 waiting at the shed for a purchase),
moves 126 vs 117, shed deliveries ~13 vs ~8 (DSM batches its fertilizer drops, partly with PLACE FERTILIZER n). DSM
plants 12.7 (strawberries 3.3, tomatoes 2.4, wheat 6.9), we 8.9 (1.4 / 1.3 / 6.1); DSM buys ~14 feed wheat at hours 0-1,
picks it up at hour 1 and feeds from hour 3, waters from hour 4; we buy feed wheat at hours 4-6, feed from hour 7, water
from hour 8, and hold $1.5-1.9k all day (DSM spends down to ~$400). Day 10: PASS 13 vs 0.8 (hours 1-2 waiting for the
hour-1 wheat, 21-23 idle), work ops 136 vs 170; DSM buys ~27 wheat at hours 0-2 and feeds ~10 pens by hour 8 with the
new hires (they spawn at the shed).

**Smoke on the worst offenders** (user: "smoke on worst offenders ... don't waste time on full runs on multiple boards";
`scripts/dsm4q_smoke_20260930.py EPS ARMS`: per world, the day-11 dawn gap to DSM by component, the care bank now valued
beside it - pending_care_bonus x product price, what feed + care visits buy - board composition distance, plantings and
pens fed by day, escapes). Worlds = the three largest v gaps. Arms on top of x:
- y: feed wheat also bought at hour 1 (feeds still due today) and at hour 18 on day 9 (tomorrow's). **Broke world
  115507316** (day-10 plantings 25 -> 12): the day-9 evening wheat plus day 10's hires left $17 at day-10 hours 2-6, the
  hour-0 / hour-1 plans placed 10-12 plantings, and once the melon money came (hours 7-12) 13-15 plant jobs stayed "late"
  all day - the hourly re-plan keeps the sequences, and a planting may evict only class-3 jobs (traced with log_hours).
- z: y + pens class 1 on day 10 only; n: y + pens class 1 on days 9-10 without eviction power (`feed_evict 0`, class
  order only); a: y + class 1 only for animals producing today (`feed_prod_tier`; their bank is paid or wiped that night);
  **b: n + the evening wheat buy reserves tomorrow's hire wages (`eve_feed.keep_hires`)**.

| day-11 gap vs DSM | 115513676 | 115507316 | 115511982 | mean |
|---|---:|---:|---:|---:|
| v (before) | -11,569 | -8,361 | -5,387 | -8,439 |
| x | -10,779 | -6,032 | -3,965 | -6,925 |
| y | -6,442 | -7,033 | -6,050 | -6,508 |
| z | -9,497 | -4,790 | -7,488 | -7,258 |
| n | -5,407 | -3,757 | -3,073 | -4,079 |
| a | -4,967 | -2,962 | -4,490 | -4,140 |
| **b** | **-5,407** | **-825** | **-3,073** | **-3,102** |

b: no escapes in the three, composition 8 / 7 / 10 (v 15 / 5 / 7), day-10 plantings 23 / 28 / 21 (DSM 22 / 24 / 22); the
pens-first day 9 still costs day-9 plantings (2 / 5 / 10, DSM 10 / 15 / 19). Hand time on these worlds is the root cause:
day 9 DSM 134 work ops vs ours 114-117 (moves 111 vs 125, PASS 2 vs 11-12), day 10 170 vs 134-141 (moves 145 vs 167-172,
PASS 1 vs 12-14), so every fix that adds work to the routes takes it from something else.

**b on all 9 exact worlds** (the one arm run beyond the smoke): day-11 dawn gap **-6,014 (v) -> -2,825** (x -4,974): cash
+686, stock -953, crops -1,889, animals -670; care bank -1,259 -> -969; composition 7.2 -> 6.8; escapes a world 1.0 ->
0.3; better than v in 8 of 9 worlds, one world ahead of DSM (+764). Melons 36.0 (DSM 36.0), feed wheat into day 11 27.2
(21.3), day-9 pens fed 14.4 (16.0) / cared 17.4 (16.1). Still short: **day-10 pens fed 13.4 of 20 (DSM 19.0)**, milk 6.4
(11.6), eggs 1.9 (3.4), fertilizer 29.1 (36.2); day-9 plantings 6.1 (12.7).

Day-10 pens traced (world 115515236, b: 9 of 20 fed, DSM 20; `log_hours`): 24 wheat in the shed at hour 0 and 19 feed jobs
at class 1, but only 10 fit into the hour-0 routes (18 keep-alive waters, 20 plantings and 6 melon runs already there);
the placed feeds sat late in their routes, nothing was fed before hour 6, and the hourly re-plans pushed them out (12
placed at hour 6, 2 at hour 16). **Pen crew** (`pen_crew {"days": [10], "size": 3}`: at hour 0, 3 hands outside the
quadrant crew, earliest free near the shed, each get a snake-ordered chunk of the pens, wheat picked up in batches of
feed_batch; everything else inserted around them): 18 of 19 feeds placed at hour 0, 16 of 20 pens fed by midnight.

## How far DSM's boards are a function of the shops (replicating them; user: "very limited scope")

43 DSM-new games, boards at each dawn grouped by the shop prefix revealed so far (day d knows d // 3 shops):
- days 1-2: one board for all 43 games (0.4-0.5 tiles off the mode); day 6: 97 of 100 tiles identical in every game -
  the opening is fixed and the tape router already reproduces it;
- days 3-5 (first shop): 0.7-1.5 tiles off within a group; days 6-8 (first two shops): 0.4-2.0 (pairs) - near-exact;
- same-(s1, s2) pairs differ on day 8 by 1-7 tiles (the day-6 quadrant), on day 9 by 4-12 in the 3rd quadrant (bought
  day 8 h7) and on day 11 by 4-12 in each new quadrant (4th bought day 10 h10-13); seat and land hours are identical.
  The new land is mostly filler: 3rd quadrant at day 9 ~11 wheat (0-17), 2 geese; 4th at day 11 7 wheat, 3 strawberries
  (0-8), 1.6 tomatoes (0-11), 12 empty; fill order near the shed first, 84% / 72% of tile pairs in the same order.
- Treating wheat / carrot / empty / weed as filler (user: "cut things like wheat to have minimal knock-on"), the nearest
  DSM game by shop prefix (leave-one-out) predicts the non-filler board: day 8 with two shops matched 3.3 of 46 tiles
  off, composition 1.3 (one shop matched 10.8 / 5.4); day 11 with three matched 12.5 of 58 / 1.8, two matched 18.0 / 5.8.
- Our arms at the day-11 dawn (exact day-9 handover): live 35.5 non-filler tiles off (composition 6.3); cassette 22.9
  (5.2); E68 on DSM's own tile plan 4.2 (2.2). Execution is not the gap - the plan's placement of core items is.
- Coverage: 34 distinct (s1, s2) in 43 games; 18 of 43 have a two-shop match in the rest of the corpus.

## Retrieval smoke, other leaders' boards and count figures

- Retrieved tile plan (the nearest DSM game's plan by shop prefix, no digging of our live crops) in two worlds, day-11
  dawn: world 115524856 (3 shops matched) non-filler tiles off 18 / composition 5.0 / value -6.7k (wheat-last 17 / 3.0
  / -5.2k); world 115518441 (2 matched, 3rd Yarn vs Brunch: sheep 8 vs 3) 17 / 9.5 / -8.1k; the cassette 11-14 / 1.5-3.0
  / -1.1 to -1.7k; DSM's own plan 3-6 / 1.5-3.0 / -2.8 to -3.9k. Retrieval loses: the neighbour's new-quadrant tiles are
  occupied in our world and the 3rd shop sets the counts.
- Other leaders (`scripts/leader_boards_compare_20260930.py`, 2,325 games): ~12 teams play DSM's day-6 opening (1.2-1.8
  tiles off) but stay on 3 quadrants (4th by day 10 in 0-5%); the 4Q teams (Victor, DECEM, M&M&P&Q, Majkel1337,
  atsushi11o7, My second life) play other openings (9-12 tiles off) and layouts (day-8 non-filler 19-26 off, day 11 39-52;
  DSM's own leave-one-out 3.0 / 16). No team reproduces DSM's tiles.
- Count figures (`scripts/leader_counts_20260930.py run|report`; every leader game replayed to day 29, counts at each
  dawn): the median counts per revealed shop-type mix of the 4Q teams (incl. DSM) predict DSM's counts with core errors
  3.8 / 6.6 / 7.8 / 8.6 / 9.2 tiles at days 8 / 11 / 14 / 17 / 20 covering 42-44 of 44 worlds; DSM-only tables 3.3 / 6.9 /
  10.4 / 11.2 / 11.7 covering 42 / 40 / 38 / 32 / 29. Per kind, Victor / DECEM / M&M&P&Q match DSM's animals within +-1 and
  strawberries within +-1-3; tomatoes are the systematic difference (+2.5 at day 11, -3 to -6 from day 20); wheat noisy.
- Pooled cassette (DSM fold + the three 4Q leaders with semantic records, evaluation episodes excluded; 240 games, 18
  mixes at day 11 vs 9): worse in both smoke worlds - composition 3.0 -> 6.0 and 1.5 -> 5.0, value -1.7k -> -4.0k and
  -1.1k -> -5.3k (fewer strawberries, more tomatoes). Keep DSM-only targets for days 6-11; other leaders' figures only as a
  fallback for uncovered mixes and per kind (animals) - their tomato / wheat numbers are not DSM's.

## DSM's dropped optional jobs after day 11 (for the post-day-11 solver)

`scripts/dsm4q_dropped_jobs_20260930.py` (user: "what are the optional jobs DSM is dropping in each turn"): DSM's 43
games replayed from both seats' recorded actions (final cash reproduces 43/43); each day's dawn state (after the
midnight refresh) vs the state after the day's last unit actions; per game per day, days 11-24 (25-29 in brackets):
- kept almost always: waters of plants not watered yesterday (21-24 a day, 1-2% dropped; [4%]), seedlings (0%),
  harvests of one-time crops at max yield / last window day (0-1%), fertilizer collection on every pen (0-3%), feeds of
  animals unfed yesterday (1-7%; [56%]: animals left to escape on days 28-29), full pens producing tonight (0-19%);
- bonus jobs mostly kept: window waters of one-time crops (7-19% dropped), waters of fertilized ongoing crops producing
  tonight (1-6%), feeds of animals producing tonight with a banked bonus (3-14%; [26%]);
- dropped or deferred: waters of plants watered yesterday with no bonus (71-77%, ~24 a day: an every-other-day cycle),
  other feeds (24-59%; [74%]), cares (10-31%; [52%]; care done ~= fed and cared), ripe one-time crops still growing
  (67-74% left standing: harvested at max), strawberry / tomato units (21-39% left), products of pens not full (26-54%;
  33-53 units held on the farm), empty owned land (34-65% left; [96%]: no replanting from ~day 25), weeds (17-58%; [96%]).
Per game and day: results/fresh/dsm4q_d9_20260930/dsm_dropped_jobs.json.

## Files
- cases / recordings: results/fresh/dsm4q_d9_20260930/cases.json, study/recordings_d4q9/, leader_commits/d4q9-*.json
- games (every step): results/fresh/dsm4q_d9_20260930/games/; viewers viz/b2b_d4q9-115561922_n18rc223d_p216.html,
  viz/b2b_d4q9-115518441_d9c4i_p216.html
- DSM-new cassettes (2 folds): results/fresh/dsm4q_d9_20260930/dsm4q_cassette_{a,b}.json
- executor variants: exec_defer_locked.py, exec_defer_steal.py (same folder); arms d9c4a..p in the study's candidates

## Full games on all 43 worlds: d9c4o / d9c4p vs the live build (2026-09-30)

User: "Can you try d9c4o on a larger panel?" / "Focus on running against higher rating opponents". Every world out of
sample: d9c4o (cassette learned on fold a) on the 21 fold-b worlds, its twin d9c4p (cassette from fold b) on the 22
fold-a worlds; live n18rc223d on all 43; all from step 0 (`--prefix 0`), DSM's shops, recorded frozen opponent, DSM's
own game as reference. Runner (strongest opponent first) in the session scratchpad (run_rated.py, calls the harness
job() unchanged); report `scripts/d9c4_panel_report_20260930.py` -> results/fresh/dsm4q_d9_20260930/d9c4_panel_report.txt.
Opponent strength = the opponent team's ladder score on 2026-09-30 (opponent_ratings.json). No errors, no bank stops.

| opponents | worlds | candidate margin | live margin | DSM margin | cand - live margin (SE) | wins cand / live / DSM |
|---|---:|---:|---:|---:|---:|---|
| rated 2650+ | 10 | -9.9k | -8.4k | +9.4k | -1.5k (2.2k) | 1 / 2 / 10 |
| 2450-2650 | 9 | -5.4k | -1.5k | +16.4k | -3.9k (1.3k) | 4 / 5 / 9 |
| below 2450 | 24 | +23.0k | +28.1k | +43.3k | -5.2k (1.3k) | 22 / 23 / 24 |
| all | 43 | +9.4k | +13.4k | +29.8k | **-4.1k (1.0k), better 9/43** | 27 / 30 / 43 |

- **The candidate is worse than live in full games**: cash -3.5k (SE 0.7k), better in 11/43. It buys Q4 on day 10 in
  43/43 (live never does) and earns +6.7k more revenue (tomato +2.7k, wheat +2.0k, strawberry +1.5k, milk +0.9k; eggs /
  fertilizer -0.9k each) but spends +9.1k more (land 4.0k, hires 1.8k, seeds 1.6k, animals 1.1k, feed wheat 0.6k): the
  4th quadrant does not pay back within the season as we farm it. Day-11 cash: cand 4.6k / live 10.2k / DSM 2.7k.
- **Against strong opponents both lose** (2650+: 1 and 2 wins of 10); the difference between them is not significant.
- **The gap to DSM is mostly the opponent earning more against us**: live vs DSM margin -16.4k = our cash -3.6k and
  the opponent +12.8k (candidate: -7.1k and +13.4k). The recorded opponent sells the same units; the difference is the
  prices it gets. DSM sells much more wheat (revenue 18.8k vs 11.7k live) and carrots (9.2k vs 6.3k).
- Mechanism diagnosis of the strong-opponent losses (6 worlds rated 2665+, 3 at 2494-2519; 4 lenses with independent
  skeptic re-computation): docs/d9c4o_strong_opponents_diagnosis_20260930.md, raw findings
  results/fresh/dsm4q_d9_20260930/strong_opponent_findings.json.

## Executor arms on the 10 strongest-opponent worlds (2026-09-30, wrap-up)

User: "do option 1" (animal service for live), then "Yes you can try" (option 2, 4Q wheat service). Arms built with
`scripts/sem_arms_20260929.py make` (config only, executor unchanged); X = Xo on fold b / Xp on fold a; compared with
`scripts/d4q9_arm_compare_20260930.py ARMS --min-rating 2650` (results/fresh/dsm4q_d9_20260930/wheat_arms_strong10.txt).

- Option 1 dropped before building: live's animal service is already at DSM's level (days 11-28, all 43 worlds: eggs 236
  vs 229, milk 170 vs 159, wool 98 vs 105, bank wipes ~0; animal revenue within $0.5k). The only animal gap is the late
  sheep flock in Yarn + 2650+ worlds (7.4 vs 9.6 sheep on day 25, -$2.3k in 5 worlds); larger flocks already tested
  negative (n18rc229d x1.5 -2.0k, n18rc243d -0.5k). The diagnosis's animal faults are d9c4o's, not live's.
- Margin vs d9c4 (10 worlds, SE): d9w1 `sd_tier_water_exact` +1.3k (1.3k, 7/10); d9w2 + `sd_onetime_gain_fix` = d9w1
  exactly (no effect in the tier executor); d9w3 + `sd_wheat_fert_mand` -2.2k (0.7k, 2/10: +54 wheat but 44 fewer
  fertilizer sold, opponent +1.8k); d9i1 `sd_tier_idle_work` (minv 20) +1.7k (1.3k, 5/10; 54 fewer PASS but +4
  collects; the gain is the opponent's -2.4k, our cash -0.7k); live +1.5k (2.2k). All 4Q arms level with live on these
  worlds (-8.2k to -8.6k margin, 2 wins of 10). None changes wheat or fertilizer.
- **Wheat mechanism (corrects the diagnosis's watering claim)**: per harvested wheat planting (days 11-27), yield is set
  by (window waters, fertilized): 2 waters unfertilized = 3 units, 2 waters fertilized ~5, 3 fertilized = 6. Every planting
  already gets its window waters; d9c4 has 33.8 unfertilized plantings a world (live 5.3, DSM 9.9) because its Q4 wheat
  gets no extra fertilizer: fertilizes 185 (live 191, DSM 252), collects 376 (live 424, DSM 486) with the same crew (12.7
  vs 13.0 hands) and herd; DSM idles ~250 fewer unit-hours. The lever is fertilizer COLLECTION during the day (DSM's
  multi-job pen visits), not water valuation, forced fertilizing or the end-of-day filler (idle hands at h22-23 are far
  from the pens). Script: session scratchpad wheat_life.py.
- Stopped unfinished at the user's wrap-up: live + water_exact (n18rc223w1d) and + idle filler (n18rc223w1id), 4 / 10
  worlds each (inconclusive); d9w1i (4Q + both) not run.
