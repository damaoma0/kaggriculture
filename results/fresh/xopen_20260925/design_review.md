**Verdict: not ready to build as written.** Section 0's cash data is sound: D≈11 is well supported as a description of the leaders. The failures are elsewhere. Five mechanisms would silently break games in the engine, the failsafe's ranking is degenerate, and E1/E2 cannot test either of the two things the user asked for: the handoff date and the EV cuts. I ran static checks only (listed at the end). No games were run, nothing was pushed to Kaggle and no files were edited.

## Blocking flaws: engine or game-breaking

**B1. Seed planting fails for the whole step.** `data/kaggriculture.py` lines 920-933: if a step's PLANT requests for a crop exceed the seeds held at the start of the step, every PLANT for that crop that step becomes PASS.
- A.4 checks feasibility one unit at a time. With deferred seed purchases, one missing seed on a multi-unit planting step kills all of that step's plantings of the crop.
- Catch-up PLANTs from released units count toward the same total.
- Change: check feasibility per crop per step across all units, using the pre-market seed count (seeds bought at step t can be planted from t+1). Choose which s of the k recorded PLANTs go ahead by value and substitute the rest.

**B2. Role mapping by spawn tile breaks on the known shed-occupancy effect.** `_spawn_hand` (lines 533-541) picks the least-occupied shed-access tile at the market phase, after unit actions. A.3's rule "same step and same shed tile as recorded hand k = role k" fails whenever a lagged, released, detouring or rendezvousing unit stands on a different shed tile than recorded at a hire step. That is exactly the CLAUDE.md lesson (-5 to -9k a game).
- Change: role k = the k-th successful hire of the day, capped at H(t). Treat a spawn-tile mismatch as a position offset to rendezvous away (1-2 steps).
- Also bar released and detouring units from shed-access tiles at the recording's hire steps, or accept and log the offset.

**B3. Ops that succeed can still destroy assets.** The engine executes DIG on any plant, weed or empty structure (lines 484-491). HARVEST on a one-time crop clears the tile at whatever yield it has (lines 464-468).
- A.4 emits a recorded op verbatim whenever it is feasible. After a catch-up planting (one day late) or a day-6 switch, a recorded DIG or early HARVEST can wipe a live crop of ours or take a partial yield. The exemplar has no DIGs on days 0-10, but pool recordings after day 6 are not checked.
- Change: run destructive recorded ops only when our tile's (crop, planted_day) equals the recording's. Otherwise substitute. Allow DIG as a substitute only on WEED tiles.

**B4. Substitute ops and released units starve the recorded roles.**
- A.4's substitute ("maintenance op when its inputs are in hand") can spend wheat or fertilizer the role needs for its later recorded FEED or FERTILIZE.
- The shadow executor (D.1) plans released units as if it controlled every unit. It will PICKUP shed stock that in-sync roles' recorded PICKUPs need later, and take tile ops in-sync roles will do.
- Change: substitutes may use only the inventory surplus against the compiled inventory path. Run the executor copy on released units only, with claimed tiles masked and the shed budget net of in-sync roles' remaining recorded pickups today. `xopen_build.py` owns the copy, so this is allowed.

**B5. Order fills are not observable.** The engine reports no per-order fills. The cumulative caps E_i(t) − ours_i(t−1), S_i(t) − oursold and H(t) need exact own fills, and the leader itself does SELL WHEAT and BUY WHEAT in the same step (tape step 1).
- Change: specify fill inference from observation deltas:
  - seeds = Δseeds + our PLANTs
  - animals = Δshed + our PICKUPs
  - wheat and fertilizer from Δshed, deposits, pickups and sells in list order
  - hires = Δhands; land = Δunlocked
- Add a static unit test against the compiled leader ledger, where fills are known.

**B6. An early abort leaves the deploy without retrieval.** D.1 sets `_DEP["switched"] = {3,6,9}`. On an abort handoff before day 9 (B.3), the deploy's own day-6/9 retrieval never fires. Change: on abort, remove the future reveal days from `switched`.

**B7. The EV ranking is degenerate for the known loss mechanism.** `sm_tile_plan` uses one constant price, and the season ends at refresh day 28.
- A strawberry planted on day 13 or earlier still gets all 4 productions, so Delta1 = 0 until the cutoff. Cows and sheep flip between 0 and one production depending on parity.
- C.4 therefore defers strawberry seeds (900 on day 6, 500 on day 10) and parity-lucky cows first, even ahead of wheat buy-ahead (0.03). It keeps deferring them until the day-13 cutoff.
- That turns every cash shortfall into later goods and later animals: exactly the measured T-gap (+5.9k later goods, +7.5k animals later). The v1 "known limitation" is the main effect, not a detail.
- C.4's "old deferrals lose priority on their own" contradicts Delta1 rising near deadlines, so starvation behaviour is unspecified.
- Change: value delay with a price path (the deploy's count and reveal forecast, or a falling late-price curve) plus a cash-timing term for revenue pushed past the next bound day (`xo_cash_rate` in the first build, not later). Price over the expected deferral length k, not one day. Specify ties when Delta1 = 0 (FIFO by dependent-op step).

## Blocking flaws: the tests would not answer the question

**T1. The date is never tested where it matters.**
- E1 runs each recording in its own world, where shops always match, so the cost of ignoring our day-9 shop is invisible there.
- E2 has no date arm. Day 10 is the largest, most shop-reactive spending day (66% of cumulative reinvestment by then; Yarn Store sheep 11.3 vs 3.2).
- Add E2 arms with fixed D = 9 (hand off at the third shop reveal) and fixed D = 11, alongside the dynamic rule.

**T2. The EV failsafe is never isolated.**
- E1 is a pure replay, so there are no breakages and neither the repairs nor the failsafe run. E2 bundles everything.
- Add an **E1-stress** cell: leader world, own recording, with an agent-side cash reserve that withholds h = 5/10/15% of each sale's proceeds from spending until D. The h = 0 control reproduces the leader exactly, so B/C are exercised with everything else equal.
- Add a naive-failsafe arm in E1-stress and E2: tier-0 wages and feed, then the engine's natural list-order partial fills. This is the only way to show the user's EV cuts help.

**T3. The date evidence for "our side" comes from policies that do not follow the plan.**
- The dynamic-rule replays use deploy cash paths (`xopen_cash_safe.py dynamic()`). The deploy never buys the $4,000 quadrant and holds 3.8-6.1k on day 11.
- An exact follower with SE land has 219-1,312 on day 11 at a 5-10% cut (open_stats (f)). The rule at t = 11 needs at least 1.25 × 1,226 = 1,533, so it fails, and xo3 will mostly hand off at 12-13.
- xo3 is then confounded: land and the date change together. Run xo3 at fixed D = 11, or report it by handoff day.

**T4. The failsafe load estimate is too coarse.** Section (f) is daily, uses a uniform haircut, and assumes deferrals cost no later revenue.
- Funding on the bound days is lumpy single-product sales exposed to the rival: day 6 is 86% wool (3,438 of 3,892), day 10 is 95% melons (8,753). The rival's day-10 revenue median in new worlds is 16.8k.
- Intraday, the leader funds buys to the last coin, so partial fills fire on steps even when daily totals cover.
- Change: in E0, replay the recorded market lists step by step with per-product price ratios (wool on day 6, melon on days 10-11) from the 185 worlds. Model deferral carrying into later revenue. Re-derive the day-10 deferral and D for xo1 and xo3.

**T5. There is no go/no-go gate after E1.** The build is large (roles, lag, rendezvous, detours, releases, survival net, shadow executor, re-retrieval, failsafe).
- E1 needs an X10 cell that hands off to the deploy's executor and count model (the new-world successor), not only T.
- Add X10-noSE (verbatim replay with the third BUY_LAND removed; ops on locked tiles do nothing) to separate the land effect behind E2d's −0.039.
- Build B/C only if X10 (deploy successor) beats T or the deploy by a pre-set margin with CI > 0. Report the opponent's failed orders per cell: the X cells keep the frozen opponent in its recorded world until D, which T does not.

**T6. E3 leaks.** p2750 worlds 112613630 and 112614774 are Vadim (16770421) corpus games. Vadim makes up 84 of the 165-game day-6 pool, so retrieval by shops could pick the world's own recording. The 12 smoke worlds are clean (110937191..111941962). Exclude the world's own episode from pools, or drop those two worlds.

## Required but not blocking
1. Catch-up seed and animal orders go in at the next affordable step, before the dependent op's step, not after a 3-step wait. The PLANT at t+1 has already failed by then.
2. Day-6 tie-break: within a shop-distance tier, prefer candidates whose day-6 cash is at or below ours. Pool median is 843 vs the exemplar's 743, and day-6 reinvestment is 4.7k.
3. Implement fixed D = 11 first and log the dynamic rule in shadow. The rule's R_plan must exclude items cancelled by land_max; today R[10] still contains the $4,000 in xo1.
4. The rule's check covers the plan's reinvestment through day 14, but that plan is dropped at D. Also check that the successor's committed spend (`_T` days D..11, then the count model) is covered.
5. Keep the per-tile hidden-state comparison at compile: watering parity, fertilized_until, care bank, unfed, one-time yield. See check 2 below.
6. Truncate compiled plans to days ≤ 13 to keep the bundle small.
7. The SELL stock prediction must also subtract same-step PICKUPs.

## Checks I ran (static, one process)
1. **Order-list length.** No step in the exemplar tape has more than 10 market orders. Its hour-0 pattern is SELL, then 8 HIREs (cash-limited: day 1 gets 3 at hour 0 and 1 at hour 2), then BUY WHEAT. H(t) and the fill inference are therefore essential.
2. **Day-6 pool.** All 239 compared DSM/Vadim tapes diverge from the exemplar's unit commands on day 0-1, so "state-identical" means board only. Even so, among the 165 strict-pool games no plant tile left unwatered by the exemplar on day 5 goes unwatered on the candidate's day 6. FEED and CARE on day 5 match. The day-6 switch is safe on watering.
3. **Weeds.** The exemplar keeps 0-5 empty tiles most days, so the 0.16 weeds a game estimate is credible.
4. **Episode overlap.** Checked episode ids of the p2750 panel against the leader corpus (result in T6).

**Sound:** the offset-corrected cash identity (540/540), the day-11 sharpness, the X29 and xo0 reproduce-to-the-dollar harness checks, tier-0 wages before purchases (lesson 4), and the cumulative-cap handling of the leader's failed over-asks.

**Files:**
- `C:\Users\xyygl\Documents\kaggriculture\results\fresh\xopen_20260925\design.md`
- `C:\Users\xyygl\Documents\kaggriculture\scripts\xopen_cash_safe.py`
- `C:\Users\xyygl\Documents\kaggriculture\scripts\xopen_open_stats.py`
- `C:\Users\xyygl\Documents\kaggriculture\data\kaggriculture.py`