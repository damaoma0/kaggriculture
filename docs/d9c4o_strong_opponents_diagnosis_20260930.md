<!-- 2026-09-30: output of the multi-agent diagnosis workflow (4 lenses, each top claim re-computed by an independent skeptic, synthesis). Games: results/fresh/dsm4q_d9_20260930/games; helper scripts were written to the session scratchpad (diag/), not the repo. Panel context: docs/dsm4q_day9_handover_20260930.md, last section. -->

# Why d9c4o loses to strong opponents, compared with DSM

**Scope.** This covers the 6 strongest fold-b worlds, with opponents rated 2665 to 2793. The 3 second-tier worlds, rated 2494 to 2519, serve as a check. Every figure is a mean per world: candidate d9c4o.p0 minus DSM in the same world. I only read saved games and ran no new ones. The opponents are frozen replays, so only their sale prices react to us. Six worlds is a small sample, and one world (115551555) moves several of the means.

**Headline.** We end $19.7k behind DSM per world. Our cash is $7.1k lower and the opponent's cash is $12.6k higher.
- **Nothing is lost before day 11.** At dawn on day 11 we have $1.7k more cash than DSM, but DSM's shed holds $3.1k more goods. Counting those goods, we are about $1.4k behind at dawn 11, and days 11-29 lose about $18.3k.
- **Days 11-19 cost mostly our own cash.** Days 20-29 cost mostly the opponent's extra earnings, and half of the opponent's $12.6k gain arrives on days 25-29.
- **The exceptions lose mainly our own cash:** 115557062 and all three second-tier worlds. In the second tier our cash is $18.5k lower and the opponent gains $7.1k.

## 1. What costs us, ranked (checked figures, per world, strong 6)

"Opponent gain" means the higher prices it gets because we supply less, or supply it later. Its sold units are the same in both games.

| # | Mechanism | Margin | Our cash | Opponent gain |
|---|---|---|---|---|
| 1 | Too little wheat and carrot produced (wheat −139 made / −176 sold, carrot −71 / −77) | **−8.7k** | −6.7k | +2.0k (net of its dearer wheat buys) |
| 2 | Strawberries planted later (day 6: 6.3 plantings vs DSM's 13.0; days 8-11: 18.3 vs 4.7) | **−3.4k** | +0.7k | +4.1k |
| 3 | Wool, only in the 3 worlds with a Yarn Store | **−2.7k** | −1.3k | +1.5k |
| 4 | Milk, behind DSM in all 6 worlds | **−2.65k** | −0.04k | +2.6k |
| 5 | Fertilizer (not independently checked) | −1.4k | mostly ours | – |
| 6 | Tomato / egg | −0.5k / −0.2k | | |

These add up to about −19.6k. They share causes, though: the land shift ties rows 1 and 2, and the full shed ties rows 1 and 3. Read the ranking, not the sum.

**Row 1: wheat and carrot**
- **Wheat with minimum watering: about −95 units, −2.7k of our cash and −3.5k of margin.** d9c4o has 37 wheat plantings per world that get only the three waters needed to survive (ages 0, 2 and 4) and are never fertilized. Each yields 3 units after about 95 hours. DSM has 4.3 such plantings. They appear in all 9 worlds (22 to 65 per world). The rest of our wheat yields 1.51 units per tile-day, which is at or above DSM's rate.
- **Land moved from wheat and carrot to late strawberries:** −40 wheat and −42 carrot units. Net of what the extra strawberries earn, this costs about −1.2k.
- **Late plantings never harvested: −0.76k (wheat and carrot), −1.27k counting tomato.** On day 28 we have 16 idle hand-hours per world, against 0.3 for DSM.

**Row 2: strawberries**
- **The loss is production timing.** Our day-6 plantings make 49.5 fewer units by day 22. A counterfactual puts −3.3k on production timing and only −0.1k on holding stock in the shed.
- **The day-6 seed shortfall comes from day-6 revenue, not animal buys.** That revenue is $423-767 lower than DSM's, and 77-96% of the difference is fertilizer: we collect 8-9 units but sell only 2-4 and hold the rest overnight.

**Row 3: wool**
- **Missed care and a smaller herd: −2.05k.**
- **Full shed: −0.7k,** almost all of it in 115557062.

**Row 4: milk.** The loss is almost all the opponent's price gain.
- On day 10 only 6.3 of 8.8 cows are fed and cared for, against 9.2 of 9.2 for DSM.
- We have one cow fewer because the day-6 buy is 1 cow against DSM's 2.
- Milk left uncollected in the pens accounts for 36% of the opponent's milk gain.

**Where the opponent's $12.6k comes from.** Its extra money follows how far our cumulative sales of each good trail DSM's at the day level. 97% of its gain is a price gap that already exists at the start of the day. Order position within a tick is worth only $0.3k (2.5%).

**Claims that did not hold up:**
- **Selling at hours 0-1 (the head of the order queue)** is not the cause: about 2.5% of the opponent's gain.
- **Holding strawberries in the shed** costs only −0.1k net. The opponent gains +1.3k from it, but we gain +1.2k.
- **The late collapse in sheep care** is an artefact. DSM's care on days 26-28 is wasted because it only pays at the day-29 refresh. Our missed care is spread evenly between early and late.
- **The opponent's +3.5k on wheat** is gross revenue. Net of its wheat purchases it is +1.5k, because ShunkiKyoya buys and resells about 5,600 wheat.
- **"Each missing milk unit is worth $180-240 to the opponent"** is too high. Supplying those units recovers only $80-120 of margin each, because our later units also sell into an oversupplied market.
- **"Too few hands"** does not fit. Working hand-hours on days 20-29 are only 7% below DSM, and we have 61 idle hand-hours against DSM's 13. The problem is which tasks the executor generates.
- **"Day-6 cash went to animals"** does not fit. Our animal spend equals DSM's.

**Worlds that contradict the pattern:**
- **115551555 (ShunkiKyoya):** 63% of the strawberry loss (−12.8k). Without it the 6-world strawberry mean is −1.5k.
- **115553788 (kigasudayooo):** strawberries are +2.5k, because our late harvest drove prices to $1. Half of its wool gap is one fewer sheep bought on day 15.
- **115546186 and 115553788, plus second-tier 115544164 and 115540933:** the wheat loss is mainly less land, not the minimum-watering plantings.
- **115557062:** milk is only −0.3k (we have 8 cows to DSM's 7). Its wool loss is the full shed: 17 wool destroyed, about $4.0k.

## 2. Did we inherit this from the live build, or did d9c4o add it?

Final margin against DSM, per world:

| World | d9c4o | live build n18rc223d.p0 | d9c4o − live |
|---|---|---|---|
| 115561922 matu997 | −22,055 | −18,944 | −3,111 |
| 115546186 Christoffer Thimsen | −20,437 | −10,296 | −10,141 |
| 115560322 | −16,825 | −18,889 | +2,064 |
| 115553788 kigasudayooo | −11,364 | −10,200 | −1,164 |
| 115557062 THIRD FARM CLUB | −21,473 | −14,318 | −7,155 |
| 115551555 ShunkiKyoya | −26,026 | −36,389 | +10,363 |
| Mean, strong 6 | −19,697 | −18,173 | −1,524 (SD 7.3k, t −0.5) |
| Mean, second tier | −23,859 | −18,964 | −4,895 |

**Mostly inherited.** d9c4o is 2.6k per world worse than live over all 9 worlds (worse in 6 of 9, t −1.1). That difference is not significant.
- **The opponent's gain is about the same on average** (+12.6k against +12.8k). Per world, though, d9c4o moves it by anywhere from −6.3k to +4.6k, and those moves cancel out.
- **Live with DSM's exact days 0-8** (the p216 run) still ends at −14.1k, with the opponent at +8.3k. So about 35% of the opponent's gain depends on what happened before day 9.

**Inherited (live is as bad or worse):**
- Wheat volume: live is −251 units and −10.6k net, because it owns only 3 quadrants.
- Wool: −2.73k in both.
- Late milk care.
- Idle hands: on days 11-29 live issues 314 PASS commands, d9c4o 123, DSM 19.

**Added by d9c4o:**
- The minimum-watering wheat: 37 plantings against live's 9.2.
- Strawberry land moved to late plantings.
- Fertilizer collected on only 68-77% of animal-days, against 92-95% for live (−1.4k).
- About $520 of the $757 in unharvested end-of-season crops.
- The day-6 buy of one cow where DSM buys two (live buys none).

**Better in d9c4o:**
- Strawberry +3.1k and tomato +4.1k against live.
- The 4th quadrant pays on days 20-24: revenue there is +1.0k against DSM, where live is −5.8k.
- But d9c4o spends $5.7k more than live on days 6-10 and earns back only $4.2k on days 11-29. Without 115551555 it earns back just $1.9k of $5.8k.

## 3. Most promising fixes

1. **Service every wheat planting's watering window. This fixes a d9c4o regression (mechanism 1).**
   - The change: water at ages 2 and 3, harvest at age 3, and fertilize at age 2 when fertilizer is in hand. On days when a window water was skipped, 3.6-6.1 hands were idle.
   - Expected gain: +37 units and +1.35k margin for the age-3 water alone, or +112 units and +2.5k margin with fertilizer.
   - The fertilizer route needs 37 units; getting fertilizer collection back to live's 92-95% would supply them. The animals lens puts the collection shortfall at up to −1.4k, but that figure was not independently checked.
   - Also: no wheat or carrot plantings after day 26 unless a harvest slot exists, and use the idle hands on day 28 to harvest. Worth +0.5-0.8k, or up to +1.3k with tomato.
   - Realistic total: +2-3k per world. This is the most certain fix, since the minimum-watering plantings appear in all 9 worlds.
2. **Animal service in the tier executor. This is inherited, so it would help live too (mechanisms 3 and 4).**
   - Care for new sheep on the day they are bought. The whole herd was skipped on day 15 in 115553788 and 115551555.
   - Feed every sheep on its production day, since a missed feed then wipes the banked bonus.
   - Feed sheep bought on days 24-25, so they don't escape.
   - Fully service the cows on day 10 and collect the pens before the midnight refresh.
   - Keep shed room for wool late in the season.
   - Expected gain: wool care about +2.0k per world (about +4k in each Yarn-Store world), full shed +0.7k (mostly 115557062), milk about +1k. Realistic total: +2.5-3.5k.
3. **Day-6 cash and strawberry planting in the cassette (mechanism 2).**
   - Sell the day-6 fertilizer that same day instead of holding 6-7 units overnight. Memory notes that `sd_fert_sell=1` causes exactly this one-day lag, so check the cassette's setting.
   - Then buy about 13 strawberry seeds on day 6 instead of spreading the plantings over days 8-11, and buy 2 cows as DSM does.
   - Ceiling: the −3.3k production-timing loss, plus part of the −1.2k land loss to carrots. But without 115551555 the strawberry loss is only −1.5k, and 115553788 (+2.5k now) would probably lose.
   - Realistic: +1-2k. This is the least certain of the three.

## 4. Open questions

- **Planner versus starting state is not separated.** No saved game runs the live planner from DSM's exact dawn-11 state including the 4th quadrant; p216 has no 4th quadrant.
- **Why does the executor pass idle hands** while wheat windows and harvestable tiles go unserved? Trace task generation on day 28 and on the days a window water was skipped.
- **The fertilizer figures have no independent check:** the −1.4k and the 68-77% collection rate.
- **The opponents are frozen.** 115551555's gain rests on ShunkiKyoya's fixed wheat trading and late strawberry sales, and a live opponent would react. The median opponent gain is +11.9k against a mean of +12.6k.
- **The second tier has not been broken down by mechanism.** Its loss is mostly our own cash, and 115544164 alone is 12.8k worse than live.
- **Would fix 3 hurt worlds like 115553788,** where the late strawberry wave currently wins?

**Sources.** Scripts are in `C:/Users/xyygl/AppData/Local/Temp/claude/C--Users-xyygl-Documents-kaggriculture/d001f47c-f789-4e42-93cb-37e6712060a5/scratchpad/diag/`. Run them as `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe <script> ...` from the repo root.
- Timeline: `timeline_gap.py`, `timeline_windows.py`, `opp_tick_gain.py`.
- Wheat and carrot: `wc_volume.py`, `wc_class.py`, `skw_volume_skeptic.py`, `wvs_*.py`, `strand_check.py`, `skq_timeline/*.py`.
- Market rebuild: `mkt_replay.py`, `opp_ext.py`, `skx/*.py`, `pxk_price_ext/*.py`.
- Strawberry: `sk_cf.py`, `sk_rev6.py`.
- Wool: `care_cf.py`, `wool_conserve.py`.
- Milk: `milk_market_sim.py`.
- Also `scripts/exec_loss_trace_20260930.py EP d9c4o.p0,dsm`.

**Things to know about the data:**
- `frames[718].sh` is the shed before the last step's sale, not unsold stock.
- The hour labels in `opp_tick_gain.py` are off by one, because `m[t]` is money before step t.
- In the shared diag folder, `diag/mkt.py` was overwritten and restored only as `mkt.pyc`, so its source is lost. `diag/sk_wheat.py` was also overwritten.
