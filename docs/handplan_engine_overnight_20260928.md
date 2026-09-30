# Hand-plan engine, overnight log (2026-09-28/29)

## Morning summary

Best clean version (no DSM information beyond the tile plan interface + days 0-10): **KB115LTD2H3**, frozen as
**KB115LT2** (`agents/mgt_lead_kb115lt2.py`, spec arm KB115LT2; KB115LT itself is untouched). On the 40-world panel
(Kaggle): **31/40 wins (78%, Wilson 62-88%)**, mean margin +4,517, vs the clean base KB115LTk (27/40, +2,016): +2,501 a
world (95% +1,463..+3,867), 32 better / 8 worse, 4 losses turned into wins and no win lost. On the 30 worlds not used to
choose settings: 23/30 wins (base 20/30), +1,978 a world (95% +1,211..+2,788). KB115 (with DSM's sales books, harvest
days, dawn file and copy returns) is 33/40, +5,938.

KB115LT2 = KB115LT + four lower-layer changes, all default-off flags in `agents/mgt_lead_sector_search.py`:
1. `sd_collect_at_floor 1` - a pen with fertilizer always gets its collect op (the maintenance module dropped all of
   them once the fertilizer quote hit $1: whole days without fertilizing; +8.6k / +6.7k in the two worlds it hit).
2. `sd_polish 3000` + `sd_polish_final 1` + `sd_polish_xch 0.2` + `sd_polish_water_c 20` - the hand-plan local search
   on engine-true values after the planner, with the EXCHANGE move (a job into a stop the route already makes, a cheaper
   job out): per world +36 cares, +10 net collects, -26 low-value waters.
3. `sd_tier_dawn_shape "learned2"` - DSM's dawn trips conditioned on the morning: on synchronized sheep mornings (>= 6
   pens within 2 tiles holding >= 4 wool) it clears the pens one tile off the shed (and pairs the two-off ones), up to 8
   trips - wool reaches the market before the rival's sales.
4. `sd_tier_anim_harv_frac 0.3` (was 0.1) - a deferred pen harvest is worth more, so wool / milk leave the pens sooner.

Tried and parked: front seller (-937 a world, 33 worlds), compulsory goose care (-1k, a win lost), collect cap 3 / off
and the end-of-day idle filler on top of the polish (not additive), pen-harvest value 0.6 / 1.0 (labour cost).
Largest item left: when our wool / milk / strawberries reach the market vs the rival (~5.5k a world through the
rival's prices, the frozen-opponent caveat applies) - a price-path forecast for the seller is the next lever.
Caveat: the learned2 thresholds come from DSM's dawn trips in the 40 recordings (coarse constants, not outcome-tuned).

Base: KB115LT (the clean lower layer, `docs/kb115lt_tile_planner_interface.md`), run from the working file
`agents/mgt_lead_sector_search.py` as arm KB115LTk (KB115LT itself stays frozen in `agents/mgt_lead_kb115lt.py`).
Tests: Kaggle private kernels (bundle `yiyangxudmm/kaggriculture-lt-bundle`, `scripts/kgr_check_run.py` refuses a stale
bundle), 8-world panel `panel_dsm8.txt` + the two worlds where the fertilizer bug fired (112577829, 112591190).
Success = wins (our final cash > the rival's) and mean margin.

## 1. Bug: no fertilizer collects once the quote hits $1 (`sd_collect_at_floor`)

KB160's end-of-season loss (-2,087 after +199 the morning after its polished day) traced to day 27: the fertilizer
quote reached $1 on day 26 (KB158: 4.8), the maintenance module emits COLLECT_FERTILIZER only while the quote is > 1
(`scripts/fragments/sem_maintenance.py`), so that day had no collect op at all, 16 fertilizes (~81 each) had no supply
and the hands idled 74 actions. KB115L: 2/40 worlds hit it (days 24-27, 140 unplanned fertilizes). Fix: the tier plan
gets a collect op on every pen with fertilizer available, worth max(quote, sd_collect_floor).

## 2. Polish = the hand-plan local search in the agent (`sd_polish`, `sd_polish_final`)

Offline (two worlds, days 12-27, planner drops kept): +87 / +83 a day on the scorer. Ported as a post-pass on the
finished routes: relocate / swap / reverse stops, add / drop optional WATER / FERTILIZE / CARE / FEED / COLLECT, on
engine-true values, lateness and supply from the planner's own `_tier_eval`, midnight load within the delivery pass's
headroom. Corrections found on the way (engine rules the offline scorer had wrong):
- a FERTILIZED ongoing crop's production-day water is worth a unit (engine: the fertilizer bonus needs that day's water);
- an unfed animal still produces 1; a skipped feed makes tomorrow's feed a must (charged like a skipped water);
- care banks only on a fed day (the value follows the current feeds, not the plan's original ones).
First local check (one world, before the corrections): -2,384, 622 s of planning; it dropped feeds (see above).
Speed: each route's first stop is fixed (keeps the hires' spawn prediction), insertion only next to the nearest stops,
`sd_polish_final` runs it once a day on the kept plan.

## 3. Parked: front seller (`sd_books_front`)

33 panel worlds, paired vs KB115L: -937 a world (95% -1,707..-147), 10 better / 23 worse, wins 27 -> 25.

## 4. Loss breakdowns vs DSM (KB115LT, the two losing panel worlds)

| world | margin vs DSM | sales timing | production |
|---|---|---|---|
| 112610623 | -12,574 | strawberry -2,653, milk -1,573 | wheat -3,182 (-72 units), fertilizer -2,755 (-53 sold at ~50), egg -1,124 (goose -28), carrot -981 |
| 112604454 | -15,948 | strawberry -5,470, wool -2,592, milk -1,506 | wheat -3,279 (-57), fertilizer -1,318, egg -919 (goose -16) |

Strawberries: the rival dumps at h23; both DSM and we sell before it within a day - the loss is the season pattern (DSM
sells more earlier, the mid-season price falls, the rival's late sales meet it; we sell a larger share late, when the
price has collapsed: our average 143 vs DSM's 153).

## Results

### Run ltp1 (Kaggle, 10 worlds: panel 8 + the two bug worlds)

KB115LTk reproduces the local KB115LT results to the dollar on all 8 panel worlds (Kaggle = laptop).

| arm | wins | mean margin | vs base | s/game |
|---|---|---|---|---|
| KB115LTk (base) | 7/10 | +2,312 | - | 118 |
| + collect fix, mode 1 (LTC) | 7/10 | +3,605 | +1,294 | 119 |
| + fix + polish 1500 (LTP) | 7/10 | +3,468 | +1,156 | 203 |
| + fix + polish, charge 20 (LTP2) | 7/10 | +3,753 | +1,441 | 198 |

- Collect fix: +8,640 (112577829, -12,998 -> -4,358) and +6,678 (112591190) where the bug starved days 24-27; 7 of 8
  panel worlds identical; 112592389 -2,383 - the quote hit $1 only on day 28 and mode 1 added 24 collects (worth the flat
  80) that day, taking the hours of harvests / deliveries (day-29 morning -2,893). Mode 2 limits floor collects to the
  day's fertilizes lacking supply.
- Polish vs LTC: -137 (LTP) / +148 (LTP2) a world, 5 better / 5 worse, +-2-3k swings, no flips: a wash. Its own log: ~25
  op changes and ~580 scorer coins a world over the season (offline +85 a day) - with first stops fixed and full
  routes it finds little: a lone add is late, a lone drop loses value.
- Where DSM's labour goes (per world, same hands, same plantings): fertilizer collected 395 vs 316 (-79; -56 sold),
  goose care 83 vs 50, wheat waters 489 vs 463, wheat fertilizes 117 vs 110 (wheat units a harvest 4.62 vs 4.16 = -71
  units a world). Hence the exchange move (a pool op into a stop the route already makes, a cheaper op out) and the
  planner-side sweeps below.

### Run ltx1 (same 10 worlds): the exchange move

| arm | wins | mean margin | vs LTC2 (95%) | better / worse | s/game |
|---|---|---|---|---|---|
| KB115LTC2 = base + collect fix mode 2 | 7/10 | +3,300 | - | - | 133 |
| + polish 3000, once a day, charge 20, exchange 0.1 (LTX) | 7/10 | +4,432 | +1,132 (-839..+2,597) | 8 / 2 | 180 |
| + the same, exchange 0.2 (LTX2) | 7/10 | +4,779 | +1,479 (+648..+2,301) | 9 / 1 | 165 |

- The polish now does what DSM does more of: per world +36 cares, +20 / -10 collects, -26 waters (low value), -8 net
  fertilizes; scorer gain ~2,300 a world. No win flips: the losing worlds are 4.5-9k down (sales timing dominates them).
- Collect fix mode 2 is worse than mode 1 here (-305 overall, all on 112577829; 112592389's day-28 collects stay - there
  was fertilize demand): the stack goes back to mode 1.
- Hand-day path shape (radial routes, DSM vs KB115LTk): visits 6.6 vs 7.1, ops 13.6 vs 12.5 - ops per visit 2.06 vs
  1.76, the planner audit's gap; the exchange move works on exactly that.

### Runs lcc1 / ltw1 (same 10 worlds): planner sweeps and the end-of-day filler

Hour budget per hand-day (hands, days 11-28, DSM vs KB115LTk): work 13.09 vs 12.24 h, idle after the last job 0.03 vs
0.78 h (~40 hand-hours a world), walking before the first job 1.01 vs 1.46 moves. New `sd_tier_idle_work`: a hand whose
plan is done walks to the best live job by value / (walk + 1) - care on an animal fed today, a fertilizer collect within
the midnight room, a water (window bonus / fertilized production / tomorrow's forced water) - skipping what other hands'
remaining plans do, with claims.

| arm (all on KB115LTC2) | wins | mean | vs LTC2 (95%) | better / worse |
|---|---|---|---|---|
| collect cap 3 | 7/10 | +4,142 | +842 (-182..+1,855) | 7 / 3 |
| no collect cap | 7/10 | +3,608 | +308 (-770..+1,444) | 6 / 4 |
| goose care mandatory, mode 1 / 2 | 6/10 | +2,327 / +2,239 | -973 / -1,061 | 6 / 4 |
| idle filler, min value 5 | 7/10 | +4,665 | +1,365 (-426..+2,794) | 8 / 2 |
| idle filler, min value 20 | 7/10 | +4,268 | +968 (+224..+1,727) | 8 / 2 |

Goose care stays parked (112575429 +6,927 -> -1,115 / -1,992: the forced cares take hours the plan needed). The
filler at min value 5 has one large drop (112570602 -5.2k; min value 20: +1.2k there) - traced: it did 1-4 waters a
day there, the margin split on day 14-15 and the run then lost 2 cows (day 19) and 2 strawberries the base kept: the
planner's sensitivity to a small state change, not a filler mechanism.

### Runs sta / stb (same 10 worlds): stacks on the collect fix (mode 1)

| stack | wins | mean | vs LTC (95%) | better / worse | s/game |
|---|---|---|---|---|---|
| S1 = LTC + polish (exchange 0.2) | 7/10 | +4,796 | +1,191 (+377..+2,015) | 8 / 2 | 153 |
| S2 = S1 + filler (min 20) | 7/10 | +4,811 | +1,206 (-52..+2,618) | 7 / 3 | 150 |
| S3 = S2 + collect cap 3 | 7/10 | +4,126 | +521 | 6 / 4 | 103 |
| S4 = S1 + filler (min 5) + collect cap 3 | 7/10 | +4,973 | +1,368 (+29..+2,779) | 7 / 3 | 102 |

Not additive: the polish and the filler use the same spare hours. S1 and S4 go to the 40-world panel (4 kernels).

### Runs c400-c403: the 40-world panel (Kaggle, 120 games, no failures)

| arm | wins | mean margin | vs KB115LTk (95%) | better / worse | s/game |
|---|---|---|---|---|---|
| KB115LTk (clean base) | 27/40 (68%) | +2,016 | - | - | 117 |
| S1 = collect fix + polish | 27/40 (68%) | +3,202 | +1,187 (+415..+1,970) | 26 / 14 | 159 |
| S4 = S1 + filler (min 5) + collect cap 3 | 27/40 (68%) | +3,273 | +1,257 (+520..+2,080) | 27 / 13 | 149 |
| reference: KB115L | 28/40 | +2,231 | | | |
| reference: KB115 (DSM extras) | 33/40 | +5,938 | | | |

A solid +1.2k a world, but the win count stays: each stack turns 2 losses into wins and 2 close wins into losses (all
within +-3k). Wins need a bigger lever than labour: the wool / milk timing item above (~5.5k a world).

### The largest item left: when wool / milk reach the market

Per world (10 worlds, KB115LTk vs DSM's own games): our wool / milk units match DSM's, our wool revenue -890, but the
RIVAL's wool revenue +3,852 and milk +1,664 - about -5.5k of margin a world, more than all the labour items. Lower-layer
cause: a deferred pen harvest is worth held x price x 0.1 (`sd_tier_anim_harv_frac`), so pens are harvested at overflow
or when a hand has time and our wool arrives after the rival's sales; DSM harvests at dawn after production.
Sweep queued: S1 with the fraction 0.3 / 0.6 / 1.0.

Case world wool flow (replay, harvested / sold per day): totals equal (DSM 166, ours 174); we are behind early in
cumulative sales (40 vs 48 by day 14; day-12 harvest 28 vs DSM's 36 - its dawn trips) and ahead late (143 vs 120 by day
22), selling in bursts (17 on day 22, 14 on day 27) where DSM sells a steady 5-7 a day. Every unit moves the price for
good, so the rival's early sales meet higher prices in our games: partly arrival (dawn trips), partly the season pattern
of our selling (a price-path forecast for the seller would be the deeper fix).

### Runs lth1 / ltd1 (same 10 worlds, on S1)

| arm | wins | mean | vs S1 (95%) | better / worse |
|---|---|---|---|---|
| deferred pen harvest worth 0.3 (H3) | 7/10 | +5,464 | +667 (-306..+1,644) | 6 / 4 |
| ... 0.6 / 1.0 | 7/10 | +4,213 / +4,565 | -584 / -232 | 5/5, 4/6 |
| learned2 dawn trips (D2) | 8/10 | +5,947 | +1,150 (-384..+3,462) | 4 / 2 |

learned2 (the synchronized-morning dawn rule: sheep pens 1 off when >= 6 pens within 2 tiles hold >= 4 wool, 2-off pens
paired into their trips when >= 8, up to 8 trips) acts only on such mornings (4 worlds identical); 112577829 -4,363 ->
+6,016 is the night's first win flip; 112604454 -1.6k. D2 and D2 + H3 go to the 40-world panel.

### Runs d400-d403: the 40-world panel with the dawn stacks

| arm | wins | mean margin | vs KB115LTk (95%) | better / worse | flips (won / lost) |
|---|---|---|---|---|---|
| KB115LTk (clean base) | 27/40 (68%) | +2,016 | - | - | - |
| S1 = collect fix + polish | 27/40 (68%) | +3,202 | +1,187 (+415..+1,970) | 26 / 14 | 2 / 2 |
| D2 = S1 + learned2 dawn | 29/40 (72%) | +3,965 | +1,949 (+1,014..+3,124) | 30 / 10 | 4 / 2 |
| D2H3 = D2 + pen harvest 0.3 | 31/40 (78%) | +4,517 | +2,501 (+1,463..+3,867) | 32 / 8 | 4 / 0 |

Held-out 30 worlds (not the 10 prototype worlds): S1 +754 (-94..+1,590), D2 +1,387 (+639..+2,113), D2H3 +1,978
(+1,211..+2,788), wins 20 -> 20 / 21 / 23 of 30. D2H3 frozen as KB115LT2.

### Runs e400-e403: two variants of D2H3 on the 40 worlds

| arm | wins | mean | vs D2H3 (95%) | better / worse | flips vs D2H3 |
|---|---|---|---|---|---|
| D2H3X = D2H3 + idle filler (min 5) + collect cap 3 | 29/40 | +4,307 | -210 (-677..+289) | 16 / 24 | 2 wins lost |
| D2H3T = D2H3 with learned2 thresholds 5 / 7 | 30/40 | +4,460 | -57 (-263..+130) | 6 / 6 | 1 close win lost (-135) |

KB115LT2 (D2H3) stays the best. Knob tuning stops here: further tweaks judged on the same 40 worlds would fit them.
