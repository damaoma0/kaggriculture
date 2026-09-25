# Fourth quadrant: where the loss comes from, the leaders' programme, and the third quadrant (2026-09-25)

Ordinals are used throughout: the FIRST quadrant is the free start quadrant (NW). The SECOND is the first purchase
($1,000; ours NE, bought day 6). The THIRD is the second purchase ($2,000; ours SW, bought day 9). The FOURTH is the
third purchase ($4,000; SE, bought day 10-11). "Bought day d" means the first day-start board with the quadrant unlocked
is d+1.

All games ran on Kaggle, private dataset `yiyangxudmm/kaggriculture-panel-bundle-q4`, stage
`results/fresh/kaggle_remote_q4`. Each remote baseline was checked against a stored run before any comparison:
- dep6: remote = stored, 12/12 smoke worlds.
- Traced dep6 runs = plain runs, 12/12.
- The tie-term-disabled control of the current deploy = the stored `mgt_lpv_ff1`, 3/3 worlds to the dollar.
- G1 of ff1: the remote run equals E1's stored E2ff1 exactly.

Paired numbers are per-game means with t 95% CIs, n = 12 smoke worlds unless stated.

## Summary
- **Why the fourth quadrant loses -8.5k, more than its $4,000 price.** Its own output is +11.8k at our prices, which
  covers its land, seeds and animals (5.4k). The loss is what it does to the rest of the farm:
  - the first three quadrants produce -7.1k: the fourth quadrant takes about 34 hand-days of work, we hire 13.7 more at
    the 13th-hire price, and the rest comes out of the old quadrants;
  - wages -2.9k;
  - the shed cap discards +66 items a game (wheat +43);
  - fertilizer is spent on the new crops and there are fewer geese (the cash trough on days 10-11): -2.6k;
  - the rival gains on the goods we now sell less of: -1.9k, against +2.7k better prices for us.
  The components sum to the measured delta; the residual is 0.
- **Do we follow the leaders' fourth-quadrant programme?**
  - Timing and crop class, yes: bought day 10, mostly wheat, few long-lived crops, almost no animals.
  - We depart on carrots (3.5 vs 17 plantings), on hands (we add a 13th hire; they add about 0.3 a day), and on service
    (7.5k of maintenance dropped on it, 22% of its wheat dies).
  - Even for the leaders it earns only 31.5-35 per held tile-day (15-17k gross), with a quarter of it empty all season.
- **Our third quadrant** earns 42.9 per held tile-day vs 54.1 for the leaders' third, while our first and second match
  theirs. Cause: the greedy dispatcher breaks equal-cost ties by tile index, so rows 0-4 (the first and second quadrants)
  win. Reversing the tie order moves the dropped work to the other quadrants and loses 11.3k.
- **Fix**: a value-aware tie-break (the tile whose jobs are worth most wins a tie), on the current deploy:
  - full panel +1,420 a game (+513 .. +2,328), better in 124/185;
  - G1 +0.021.

## 1. Sanity table: FOURTH-quadrant arm vs the current deploy (dep6)
`agents/mgt_lpv_q4.py` = `agents/mgt_lpv_dep6.py` (a copy of the deploy at pv30) + `DEP_CFG land_max 3`.
Script: `scripts/q4_sanity.py`. The ledger reconciles to 0.00 in every game (3,000 + income - spend = final).

| line | delta per game (95% CI) |
|---|---|
| **margin** | **-8,485 (-11,931 .. -5,038)**, better in 0/12 |
| own cash = income - spend | -6,727 (-9,432 .. -4,023) = +2,107 (-794 .. +5,007) - 8,834 (+8,356 .. +9,312) |
| rival cash | +1,757 (+601 .. +2,914) |
| spend: land | +4,000 |
| spend: wages | +2,929 (+2,486 .. +3,371), +13.7 hand-days |
| spend: seeds | +1,299 (+1,193 .. +1,405) |
| spend: animals | +442 (+167 .. +716) |
| spend: bought wheat | +164 (-77 .. +405) |
| sold units | wheat +71, tomato +20, carrot +14, strawberry +3; fertilizer -44, egg -34, milk -6, wool -5 |
| income by product | wheat +2,111, tomato +1,322, strawberry +1,320, carrot +535; egg -1,646, fertilizer -1,113, wool -341, milk -112 |

On the current defaults the loss is larger than the old land3 row (-5,314 vs an older baseline).

## 2. Decomposition of the -8,485 (sum of the lines = measured, residual 0.00)
Script: `scripts/q4_decompose.py`, run on lead_cycles records (the traced panel runs).
- SE output = harvested units on the fourth quadrant x our realised price.
- Other quadrants = the change in the first/second/third quadrants' harvested units x our price.
- Harvested-not-sold = the change in (harvested - sold): feed, stock, and shed-cap discards.
- Price lines = the price change on the baseline's units, ours and the rival's.

| line | per game (95% CI) |
|---|---|
| land | -4,000 |
| seeds for the fourth quadrant's plantings | -1,158 (-1,232 .. -1,083) |
| seeds, rest | -142 |
| animals placed on the fourth / rest | -100 / -342 |
| wages | -2,929 (-3,371 .. -2,486) |
| bought wheat / fertilizer | -164 |
| **FOURTH-quadrant output at our price** | **+11,761 (+10,762 .. +12,760)**: wheat 6,467, strawberry 1,944, tomato 1,475, melon 908, egg 592, carrot 374 |
| **first/second/third output change** | **-7,057 (-9,065 .. -5,049)**: wheat -3,192 (-91 units), egg -2,188 (-40 units), melon -665, milk -659, wool -526, strawberry -328 |
| harvested-not-sold change | -2,753 (-4,634 .. -871): strawberry -976, wheat -684, milk -352, egg -243 |
| fertilizer volume (collected - used - held) | -2,559 (-3,522 .. -1,595) |
| our price effect | +2,714 (+1,254 .. +4,173): fertilizer +1,446, milk +899, strawberry +680, wool +360; wheat -481, tomato -233 |
| rival price effect | -1,934 (-3,053 .. -814): strawberry -1,207, fertilizer -990, milk -420, wool -323; wheat +794 |
| rival spend | +176 |
| **sum = measured margin** | **-8,484**; residual 0.00 |

Reading:
- The fourth quadrant itself pays for its land and seeds. Its gross output (+11.8k) exceeds land + seeds + animals (5.4k).
- The loss comes from what the purchase does to the rest of the farm:
  - the first three quadrants produce 7.1k less;
  - the 13th hand costs 2.9k;
  - the shed cap discards far more goods;
  - fertilizer is used on the new crops instead of sold;
  - the rival gains on the goods we now sell less of.
- No single line exceeds the whole loss.

### 2a. Mechanisms, each measured (FOURTH arm vs baseline)
- **Labour.** The fourth quadrant absorbs 813 unit-steps a game (431 tile ops + 382 walking charged to them), about 34 hand-days.
  - We hire +13.7 hand-days, about 329 unit-steps.
  - The rest comes out of the first/second/third quadrants: -364 unit-steps (first -119, second -143, third -102), plus 132 fewer PASS.
  - Ops lost there: WATER -29, HARVEST -35, FEED -26, CARE -23, COLLECT -14, FERTILIZE -6.
  - Dropped maintenance at 23h (idle trace, module coins/game): first 0.8 -> 1.75k, second 7.7 -> 11.5k, third 6.2 -> 7.2k. That is +5.65k on the old three, plus 7.5k dropped on the fourth itself.
- **Hires** (`scripts/q4_quadrants.py hires`).
  - Identical through day 11, then +0.8..+1.1 hands/day on days 12-24.
  - 11.2 of the 13.7 extra hand-days are the 13th hire (233/day) and 2.0 the 12th (144).
  - Implied wage delta 2,929 = the panel's HIRE delta exactly.
  - The hire rule reacts to land only through the crop-tile count: hands = 6.19 + 0.040 x crop tiles + 0.123 x animal tiles + 1.
- **Wheat hole and the shed cap** (`scripts/q4_world_trace.py` drives E1's `lead_world_trace.run_one` serially; kernel q4w1).
  - Wheat: harvested +93.1, bought +4.0, sold +71.3, fed -19.0, discarded by the shed cap at midnight +42.7 (+20.5 .. +64.8), i.e. 55.4 vs 12.8 a game. Residual 5.5 / 3.4.
  - All discarded items: 87.5 vs 21.8 a game (+65.7), including strawberry +8.2, milk +3.1, carrot +2.8, egg +2.6. Worth about 3.5k at our prices.
  - The +56 "wheat plantings" in the deploy log are composition events. Actual net plantings are fourth +51 and old three -11.2.
- **Geese and the cash trough.**
  - The 4,000 goes out on day 10-11: cash at the day-11 start is 2,186 vs 5,061.
  - The plan's day-11 coop/goose is not bought, and the count model never restores it: its goose additions are 0.2 vs 0.6 a game, and its features include the locked-tile count.
  - Result: 4.0 vs 5.1 geese from day 12, hence -40 eggs and part of the fertilizer drop. Goose output per goose-day and the fed share are unchanged (1.63 vs 1.64; 89.8% vs 90.1%). It is fewer geese, not worse care.
- **Fertilizer.** FERTILIZE commands +30.5 (37 on the fourth quadrant), cap discards +2.1, eggs collected -30.6. Together these account for the 44 fewer fertilizer sold.
- **Representative world 111681195** (margin delta -7,528):
  - First divergence at day 10, hour 6: the farmer delivers fertilizer (PLACE FERTILIZER at the shed) instead of picking up wheat. The pending land order (land_day 10) sets the executor's cash-short flag, which triggers same-day delivery.
  - BUY_LAND succeeds on day 11, hour 1. Cash at the day-12 start is 5,489 vs 10,391. Day-11 purchases are wheat 441 vs 120 and seeds 440 vs 190.
  - From day 12 the crew is 13 vs 12.
  - The baseline builds a coop on day 11 and has 5-6 geese from day 12; the fourth arm stays at 4. Eggs over the game 138 vs 197, fertilizer 167 vs 232.
  - Shed-cap discards 97 vs 39 items (wheat 47 vs 14).

## 3. The leaders' fourth-quadrant programme vs ours
Leaders: `scripts/q4_leader_programme.py`, `scripts/q4_quadrants.py leaders`, `scripts/q4_third.py leaders --quad fourth`. 540-game corpus; the fourth-quadrant teams are DSM 100/100, DECEM 100/100, Vadim 96/100, MG 59/100. MMPQ and Boey never buy it.

Leaders' per-quadrant output uses an equal-share split of each day's harvested units of a product over that day's harvested tiles of that product. This is an assumption; it is exact when one quadrant did all of that product's harvests that day.

| | leaders (355 fourth-quadrant games) | ours (FOURTH arm, 12 worlds) |
|---|---|---|
| bought | day 10 (a few day 11) | day 10 in 8 worlds, 11 in 4 |
| first planting on it | the purchase day (99%) | the day after the unlock |
| crop tiles per day start, days 11 / 12 / 14 / 20 / 27 / 29 | 6.2 / 12.1 / 17.4 / 17.9 / 16.2 / 7.8 | 0.9 / 13.7 / 22.9 / 20.8 / 15.9 / 6.5 |
| empty or weed tiles, mid-season | about 6 of 25 all season | 2-7 rising (weeds = dead plants left undug: 50 tile-days) |
| plantings (days <= 11 / >= 12) | wheat 8.9 / 38.5, carrot 1.3 / 15.5, tomato 0.4 / 3.0, strawberry 1.4 / 2.4 | wheat 10.4 / 40.6, carrot 0.4 / 3.1, tomato 1.3 / 2.8, strawberry 1.5 / 1.4, melon 0 / 1.0 |
| animals on it (animal-days) | sheep 13, goose 5, cow <= 4 | goose 6 |
| hands | +0.3 a day (MG with vs without the fourth, days 12-28: 11.4 vs 11.1); both rise on day 10 regardless | +0.8..+1.1 a day (13th hire) |
| income per held tile-day | 35.2 (G1 worlds 31.5); gross about 15-17k | 25.2; gross 11.8k |
| units per planting | wheat 4.14, carrot 2.84, strawberry 6.4 | wheat 3.60 (11.2 of 51 died), carrot 2.37, strawberry 4.11 |

**Are we following the leaders' plan for the fourth quadrant?** In timing and class, yes:
- Same buy day in 8/12 worlds.
- A wheat-dominated quadrant with a few tomatoes/strawberries and almost no animals.
- About the same number of wheat plantings.

Where we depart:
1. Carrots: 3.5 vs 17 plantings. Our count model composes wheat before carrots, and the capped same-day wheat replant keeps wheat tiles wheat.
2. We add a 13th hand; the leaders work four quadrants with the same crew.
3. We plant it denser mid-season (21-23 crop tiles vs their 18) but serve it worse:
   - 7.5k of maintenance dropped on it: WATER/bonus 2.1k, HARVEST 1.8k, FERTILIZE 1.4k, WATER/survival 1.1k;
   - 22% of its wheat dies;
   - dead plants are left as weeds.

**Surprise:** even the leaders' fourth quadrant is not a 20k quadrant. At 31.5-35 per held tile-day it grosses about 15-17k, and they leave about a quarter of it empty all season. Their SE output minus land, seeds and animals, before wages, is +9.6k..+12.7k per game (`leader_programme.txt`).

## 4. Our first/second/third quadrants vs the leaders' (the third-quadrant question)
BASELINE arm (dep6, three quadrants) vs the leaders, income attributed per held tile-day. Leaders use the same method:
G1 = the 12 G1 worlds; 400 = all games of DSM, DECEM, Vadim and MG.

| | first | second | third | fourth |
|---|---|---|---|---|
| ours (dep6) | 72.2 | 76.6 | **42.9** | - |
| leaders, G1 | 72.4 | 65.5 | 54.1 | 31.5 |
| leaders, 400 | 74.9 | 65.2 | 54.2 | 35.2 |

Our first and second quadrants earn like the leaders'. Our THIRD earns 42.9 vs 54.1, about -5.6k a game (21.5k vs 27.0k attributed). The split:
- crops -4.8k: crop tile-days 335 vs 372 (-1.8k); value per crop tile-day 40.4 vs 49.3 (-3.0k);
- animals -0.8k.
Diagnosis (`scripts/q4_third.py`, stored q4c1 traces and the corpus):
1. **Idle land**: 81 empty+weed tile-days vs about 27.
   - Purchase ramp, days 10-12: 20 tile-days never used since unlock vs about 5. On day 10 the leaders already have 16.7 crop + 4.4 animal tiles, we have 9.0 + 1.7.
   - Mid-season: about 25 tile-days (dead end-of-life plants left undug + gaps after harvest) vs about 7.
   - Days 27-29, past every planting cutoff: 36 tile-days vs about 20.
2. **Crop mix**: in the retrieved-plan phase (days <= 11) our third matches the leaders' (wheat 12.0, tomato 3.8, strawberry 2.6, carrot 0.8 vs 15.2 / 4.0 / 3.2 / 1.0).
   - In the count-model phase we plant 34 wheat (23 of them same-day replants) and 3.3 carrots. The leaders plant 25 wheat and 22 carrots.
3. **Yield per planting** on our third (first quadrant in brackets): strawberry 4.41 (7.72), tomato 5.12 (7.71), wheat 4.27 (5.18).
   - Leaders' third: 6.8 / 7.1 / 4.2.
   - Strawberries at about 1.1 per production are mostly unfertilised.
   - Dropped maintenance on our third is 6.2k coins/game (FERTILIZE/bonus 1.5k, WATER bonus/production/survival 3.0k, HARVEST 1.4k), against 0.8k on the first.
4. **Animals** on the third: geese 50 / cows 27 / sheep 0 animal-days vs the leaders' 51 / <= 36 / 11.

### 4a. The cause of the third's under-service: tie order in the greedy dispatcher
- The greedy matching keeps the first (unit, tile) of equal cost: `for u in free: for idx in tasks: if c < best`.
- Tasks are built in tile-index order 0..99, row-major.
- Costs are integer Manhattan distances plus integer penalties, so ties are common, and ties go to rows 0-4 (the first and second quadrants).

Diagnostic copies (`scripts/q4_tie_variant.py`) add an epsilon under 0.001, so no non-tied choice changes. Kernel q4tie1, 12 smoke worlds:

| tie order | dropped maintenance first / second / third (coins) | total | income / held td first / second / third | margin vs dep6 |
|---|---|---|---|---|
| dep6 (north first) | 0.8k / 7.7k / 6.2k | 14.7k | 72.2 / 76.6 / 42.9 | - |
| reversed (south first) | 7.8k / 17.5k / 0.4k | 25.8k | 65.1 / 66.4 / 58.8 | **-11,343 (-14,603 .. -8,083)**, 0/12 |
| pseudo-random | 3.9k / 9.6k / 2.4k | 15.9k | 68.5 / 74.9 / 53.7 | -968 (-3,062 .. +1,127), 6/12 |

- The drop follows the tie order completely. With reversed ties the third reaches the leaders' service rates (WATER 0.88, FERTILIZE 0.190 per crop tile-day).
- But labour is short, so this is zero-sum or worse. Reversed ties starve the first and second quadrants, which hold the strawberries and melons: -31.6 strawberries sold, and the rival earns +4,595 more on strawberries at unchanged units.
- The default north-first order happens to protect the highest-value quadrants.

### 4b. Fix: value-aware tie-break
Among equal-cost tasks, prefer the tile whose jobs are worth most today: the executor's `S['tval']` (the maintenance module's coin values, or plan_value for plan jobs), x 1e-4, capped at 0.4 (the cost grid is 0.5). Distance still decides every non-tie.

- **tieval** (on dep6; kernels q4val1 smoke, q4g1a G1):
  - smoke margin +2,439 (t CI -409 .. +5,286; bootstrap +79 .. +4,926), better in 10/12; own +2,336 (+543 .. +4,129); rival -103.
  - World 111416249 (+13,012) has a broken opponent tape (+65 no-effect commands). Without it, n=11: margin +1,477 (-637 .. +3,591), own +2,101 (+198 .. +4,005).
  - G1 0.897 / 0.886 / 0.875 vs dep6 0.885 / 0.875 / 0.862.
  - Per quadrant, attributed income: first 52.0k (54.1k), second 45.2k (44.1k), third 26.2k (21.5k); third 52.4 per held tile-day. Dropped maintenance 12.1k vs 14.7k.
- **tievalff** = the CURRENT deploy (`agents/mgt_lead_deploy.py` working copy: fert_hold 1, cap_guard 0; sha256 2d9dc60b...) + the same patch.
  - Control check: the patch with the term multiplied by 0 (`mgt_lpv_tievalff0`) = the stored `mgt_lpv_ff1`, 3/3 worlds to the dollar.
  - G1: 0.902 / 0.892 / 0.885 vs ff1 0.881 / 0.873 / 0.865 (+0.021 / +0.019 / +0.020; ff1 rerun = E1's E2ff1 exactly).
  - **Full p2750 panel** (185 worlds, kernels q4pf0/q4pf1), paired vs the stored `mgt_lpv_ff1`:
    - all 185: margin **+1,420 (+513 .. +2,328)** (bootstrap +417 .. +2,221), better/worse 124/61; own +1,280 (+727 .. +1,833), rival -141 (-683 .. +402).
    - Excluding the 3 broken-opponent-tape worlds (ladder_panel rule; n=182): **+1,309 (+398 .. +2,221)**, better/worse 121/61; own +1,237 (+678 .. +1,796).
    - W-L 17-168 (ff1 16-169). The deploy vs y3 moves from -16,338 to -14,917.
    - Sold units delta: wheat +19.4, egg +11.1, tomato +6.7, wool +2.2, milk +2.0; strawberry -2.8, melon -0.9.
    - The smoke-12 subset: +1,359 (-1,104 .. +3,821).
  - The patch is one line: `c = c + (-min(4000.0, S['tval'].get(idx, (0.0, 23))[0]) * 1e-4)` after `c = cost2(u, idx)` in the greedy loop. The deploy itself is not edited here: E1 owns the executor.
    The exact diff against the current `agents/mgt_lead_deploy.py` (one line, after line 1031-1033 of the greedy loop) is in
    `results/fresh/q4_trace_20260925/tieval.diff`. It was measured on the earlier snapshot (sha256 2d9dc60b), before E1 added hand_stock / cap_deliver.

## 5. Surprises, and what was ruled out
- The loss grew with the executor upgrades: -8.5k now vs -5.3k on the older baseline.
- Our fourth quadrant's own output (+11.8k) is more than twice its land + seeds. The quadrant is not the loss; its knock-on effects are.
- The leaders' fourth quadrant earns little per tile-day (31.5-35, about a quarter of it empty all season), and they add almost no hands for it.
- The third quadrant's under-service is a tie-break artefact of the dispatcher, not distance: the quadrants are equidistant from the shed.
- Ruled out as the cause of the egg loss: goose care and feed. Per-goose output and fed share are unchanged; there are fewer geese.
- Ruled out as the cause of the missing wheat: deaths alone (the 91 fewer wheat units on the old quadrants are a real output loss). The extra wheat that was harvested but not sold went to the shed cap, not to feed: FEED -19.
- `lead_cycles.py`'s first ProcessPool version hung on Kaggle for over 50 minutes (the same pattern works in ladder_panel.py; cause not found). It was removed; serial runs take about 16 s a game. The hung kernel was replaced by pushing a new version.
- Process note: the q4tie1 diagnostic kernel was pushed a minute before the "stored data first" rule reached this thread.

## Files
- Scripts:
  - `scripts/lead_cycles.py` (extended: per-tile boards, animal harvest events, labour by quadrant, agent logs, optional idle trace; recorder refactored into `recorder()`)
  - `scripts/q4_sanity.py`, `scripts/q4_decompose.py`, `scripts/q4_quadrants.py`, `scripts/q4_third.py`
  - `scripts/q4_leader_programme.py`, `scripts/q4_world_trace.py`, `scripts/q4_tie_variant.py`, `scripts/q4_g1.py`
- Agents: `agents/mgt_lpv_q4.py`, `mgt_lpv_tierev.py`, `mgt_lpv_tiernd.py`, `mgt_lpv_tieval.py`, `mgt_lpv_tievalff.py`, `mgt_lpv_tievalff0.py`.
- Results:
  - `results/fresh/q4_trace_20260925/*.txt|json` (all tables above)
  - `results/fresh/lead_cycles/{mgt_lpv_dep6,mgt_lpv_q4,mgt_lpv_tierev,mgt_lpv_tiernd,mgt_lpv_tieval}/`
  - `results/fresh/ladder_panel/{mgt_lpv_q4,mgt_lpv_tievalff}/`
  - `results/fresh/lead_agent_20260924/abl_E2_{dep6,tieval,tievalff,ff1}/` (G1 via `scripts/q4_g1.py`)
  - `results/fresh/kaggle_remote_q4/`
