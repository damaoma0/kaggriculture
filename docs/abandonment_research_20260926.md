# When to stop feeding an animal: abandonment research (2026-09-26)

Report only: nothing under `agents/` or `scripts/fragments/` was changed and nothing was tested inside the agent.
Panel: the 40 DSM worlds of `results/fresh/threads_20260928/panel_dsm40b.txt`. Sides: LEADER = DSM's recorded tape,
and the arms KS1, KC8, KE7, KB1 (streams in `results/fresh/day12_viz/<arm>_streams/`). The objective is MARGIN (our
cash minus the rival's cash). The rival replays its recorded actions.

## Answer in brief

1. **The module's economics are wrong, but its abandonments are not where most of the money goes.** Each animal
   is judged on its own at the hour-0 quote, and that quote is assumed to hold for the rest of the season. The model
   ignores the market impact of our units, both on our own later sales and on the rival's revenue. It rarely drops an
   animal before its final production cycle, so the direct cost of its drops is small: +50 to +144 margin a world
   would be recovered by keeping the animals it dropped that had 2 or more productions left.
2. **The costly errors sit around the rule:**
   - (a) After a pen empties, the agent re-buys animals that cannot produce any more: 690 / 800 / 475 / 2,420 coins a
     world in KS1 / KC8 / KE7 / KB1, exact. DSM never does this.
   - (b) At low quotes, animals are fed only to keep them alive, and the CARE that would bank extra units is skipped.
     Caring on every fed day would add about +1.0 to 1.2k margin a world. It costs only labor, about 80 steps a world.
   - (c) Whole herds are dropped as a block, 3.1 to 3.3 cows per stop event, when keeping a few would be better.
3. **DSM abandons more than we do, not less:** 3.1 cows, 1.9 sheep and 1.4 geese a world mid-season, in the
   oversupplied worlds. It drops 1 or 2 animals at a time and serves the rest fully. Its drops are own-cash optimal:
   keeping them would cost DSM 1,287 a world. They are margin-neutral: keeping them changes DSM's margin by +29.
   **Copying DSM's cuts would cost our arms 1.5 to 1.8k margin a world** (worse in 39 or 40 of 40 worlds), because
   every unit we withhold raises the rival's prices.
4. **Correct rule for margin:** never abandon an animal that still has 2 or more productions before night 28. Decide
   only the final cycle, at the quote. Value units at no less than a floor (milk 60, wool 100, egg 45) in the
   maintenance DP. Never buy or place an animal that cannot pay back before the season ends. Estimated effect: at
   least +0.74k (KS1) and +0.94k (KC8) a world from the guard plus the stop rule. Service at the floor value (item 2b)
   could add up to about +1.1k more, but that needs a labor test.

## 1. How the module decides

Sources:

- `scripts/fragments/sem_maintenance.py`: `maintenance_jobs`, `sm_tile_plan`, `_SMSolver`.
- The call site in `agents/mgt_lead_sector_animal.py` near line 1258.

Settings in all four arms, from K5b plus the spec cfg:

| Setting | Value |
|---|---|
| `sched_maint` | True |
| `mj_collect` | True (fertilizer is valued) |
| `fert_shadow` | 0, so `mj_prices = None` and every price, fertilizer included, is the current quote |
| `retire_visit` | 0 |
| `maint_goal` | "value" |
| `sd_wheat_frac` | None |
| `mj_every` | 3 |

- **When:** the module is called at the first step of each day, hour 0 (`S["mj_day"] != day`). It is re-solved only
  when the set of assets changes, at most every 3 hours.
- **Inputs:** the tile state (placed day, consecutive_unfed, bank, held yield, fed / cared flags,
  fertilizer_available), and the product, wheat and fertilizer quotes of that step.
- **Model:** a per-animal DP from today to day 29, with an exact copy of the engine's day rule. The objective is in
  1/20 product units: `20*units - feeds*round(20*wheat/price) + collects*round(20*fert/price)`. Ties go to more
  units, fewer visits, then fewer turns. **All prices are held constant to the season end.**
- **Abandonment:** the optimal plan stops feeding. `end_of_life` means no production can be reached, which is
  correct. `error` means "remaining value does not cover upkeep" (`future_full > 0` and `future_econ <= 0`). The
  plan can also feed only every other day, which is keep-alive mode.
- **Consequence:** a job the module does not return is not in the day plan, so the animal gets no FEED and escapes
  after two unfed days. A CARE job is valued at 1 unit x quote. At a low quote the executor drops it (section 4c).
- **What it ignores:**
  - that the quote is the post-sale trough, and prices move;
  - that every unit sold lowers the price of every later unit, ours and the rival's;
  - that all animals of a kind get the same verdict, so herds go as a block;
  - that the purchase layer will refill the emptied pen.

**Worked example: KC8 in world 112592389, the cow at (3,5), placed on day 9.**

Dawn quotes, days 18 to 26:

| Day | 18 | 19 | 20 | 21 | 22 | 23 | 24 | 25 | 26 |
|---|---|---|---|---|---|---|---|---|---|
| Milk | 87 | 68 | 3 | 1 | 19 | 11 | 17 | 7 | 5 |
| Fertilizer | 39 | 36 | 32 | 29 | 25 | 22 | 17 | 14 | 11 |

Wheat stayed at 41 to 43.

- On days 18 and 19 the module plans full service. From day 20 it is in keep-alive mode: feed and care only on the
  day the cow would otherwise escape (days 20, 22, 24).
- On day 25 the inputs are milk 7, wheat 42 and fertilizer 14. So one feed costs `round(20*42/7) = 120`, which is 6
  milk units, and one fertilizer collection is worth 40, which is 2 milk units. A 2-day keep-alive cycle nets
  about -6 + 2x2 + 1 = -1 milk unit. The plan is `(0,0,0)` (units 6, which is only the held yield, against 11 at full
  service), with verdict `error`. The cow escaped on night 26.
- All 13 cows stopped on days 24 to 26 (10 on night 25), and the herd went from 13 to 3.
- What a milk unit was actually worth in that game (`marginal.json`, exact): 91 for own cash and 106 for margin, sold
  at the best time, on every day from 18 to 28. The dawn quotes were 1 to 19.
- Exact value of keeping the cows (`keep.json`, `summary_log.txt` section 5):
  - each cow alone: +243 to +269 margin at full care;
  - the best is keeping 4 of the 13: +393;
  - keeping all 13: -541 (full care) or +18 (fed only), because their 75 extra milk units depress the price.
  The herd was too large for this market, and a partial keep was right.
- Then the agent bought **12 cows on days 26 to 29 (4,800 coins). None of them could produce.**
- In the same world, DSM cut 7 of its 13 cows on days 16 to 19, 1 or 2 at a time, as its quote fell from 66 to 22.
  It fed and cared for the other 6 to the end. Keeping its cut cows would have cost DSM 4,986 own cash and 2,501
  margin.

## 2. How DSM decides (replays of its 40 tapes)

Sources: `animals.json`, `dsm_mid_list.txt`, `summary_log.txt`.

- **How often.** Mid-season abandonments a world:
  - DSM: 3.12 cows in 26 worlds, 1.90 sheep in 24, 1.43 geese in 23.
  - KS1: 1.73 cows in 16 worlds, 0.12 sheep, 0.20 geese.
  - KC8: 1.70 cows, 0.28 sheep, 0.17 geese.

  Sheep escaping after their last production (end of life, about 5 a world) are correct in every side.
- **Where.** DSM's herd shrinks only where supply exceeds demand:

  | World | Milk demand a day | DSM cows | Our arms |
  |---|---|---|---|
  | 112581436 | 7, and the rival alone sells 10 to 13 | 11 to 3 | KS1 keeps 11 |
  | 112577829 | 1 to 7 | 8 to 2 | |
  | 112592389 | 13 | 13 to 6 | |

  Where milk demand is 19 or more a day, its herd stays constant.
- **How.** The decisions are gradual:

  | Side | Cows per stop event | Quote / wheat at the stop (median) | Stop day (median) | Productions lost (median) |
  |---|---|---|---|---|
  | DSM | 1.6 | 0.88 | 24 | 2 |
  | Ours | 3.1 to 3.3 | 0.40 to 0.47 | 24 to 26 | 1 to 2 |

  DSM's own realised milk price over the 2 days before a stop has a median of 53.
- **Service is binary.** When DSM feeds, it cares: 97 to 100% of fed cow-days at milk quotes of 15 or more, and 84%
  below 15. Our arms care on 33 to 44% of fed cow-days when the quote is below 40. Both use the cheap cow cycle
  (feed and care on production days only). For DSM, 34% of cow feeds follow an unfed day; for ours, 23 to 25%.
- **Purchases are never late.** DSM buys cows by day 15 (almost all by day 10), sheep by day 19 and geese by day 11.
- **Economics of DSM's drops** (exact keep counterfactual, `keep.json`, `individual_log.txt`):
  - Keeping all of them: own -1,287 a world, rival -1,315, margin +29 (full care); fed only gives margin +225.
  - Per animal, keeping costs DSM 84 to 964 own cash for cows and sheep.
  - So DSM's rule is own-cash optimal and roughly margin-neutral.
  - Its goose drops are last-cycle drops, and slightly wrong (keeping each is worth +62 to +588).

## 3. The correct economics

**Market mechanics** (engine 1.32.7):

- The price is a pure function of the inventory. Shops and the town centre consume a fixed number of units whatever
  the price.
- A sale at a price above 1 raises the inventory for the rest of the season. So every extra unit lowers the price of
  every later unit, ours and the rival's, by the local slope `s`:
  - milk glut: 2.1 a unit;
  - wool glut: 0.116 x the excess, for example 5.8 at +50;
  - eggs: about 1.7/(1+excess), negligible.
- The marginal value of one more unit sold at step t is:

  ```
  own    = p(t) - s * O_after(t)
  margin = p(t) - s * (O_after(t) - R_after(t))
  ```

  O and R are our later units and the rival's later units.
- I checked the exact repricer (`abandon_market.reprice`) against the engine by injecting sales: 4 of 6 cases match
  exactly, and the other 2 are within 1% (`validate_log.txt`).

**Measured values of one extra unit** (means over 40 worlds, days 20 to 28, `marginal.json`):

| Product | Dawn quote | Own, best sale time | Own, sold at the end | Own, sold same day | Margin, best time |
|---|---|---|---|---|---|
| Milk | 34 to 68 | 58 to 67 | 47 to 53 | negative until about day 26 (-150 to -6) | 84 to 192 |
| Wool | 63 to 103 | 92 to 110 | | | 122 to 220 |
| Egg | 46 to 51 | 46 to 51 | | | 46 to 51 |

- An early extra milk unit costs our own later sales more than it earns. That is why "sold same day" is negative.
- The distribution is bimodal: for milk, the own-cash value is below 40 in 16 to 23 of 40 worlds.
- The dawn quote is the least bad simple online estimator, but it is biased low:
  - milk: mean absolute error 45 to 53, bias -14 to -28;
  - wool: mean absolute error 71 to 95, bias -51 to -93.

**Feeding one more day.** There are three service levels:

- **full:** feed and care every day, 1 + interval units a production;
- **keep-alive:** cows fed and cared on production days only; sheep fed every other day;
- **stop:** escape after 2 unfed days; a production on the first unfed day pays 1 and loses the bank.

Break-even unit values, with wheat at about 40 and fertilizer f:

| Animal | Full vs keep-alive | Keep-alive vs stop |
|---|---|---|
| Cow | 1 extra wheat gives 1 extra milk, so v > 40 | 1 wheat per 2 days gives 2 milk + 2 fertilizer, so v > (40 - 2f)/2, about 5 to 20 |
| Sheep | v > 40 | about 10 to 25 |
| Goose | 1 wheat gives 2 eggs, so v > 20 | always feed daily (eggs are about 47) |

CARE costs labor only. On a fed day it adds 1 unit at the next fed production.

The final cycle is different: the cost is the feed since the previous production, and the value is units x the
end-of-season value, where few rival units are left to depress.

**Per-animal ground truth** (`abandon_drop.py`, 17,951 decisions: every animal alive at dawn of days 14, 17, 20, 23
and 26; its later units removed from our sales; exact repricing):

- For margin, dropping is worse in 84 to 90% of cow decisions, 88 to 95% of sheep decisions and 100% of goose
  decisions. The average cost of dropping is 300 to 1,800 margin per animal.
- Only 5% of the cow and sheep decisions robustly favour dropping, and no simple glut signature isolates them. With
  quote < 30 and our sale rate above the rival's, keeping is still better on average by 202.
- For own cash, the answer depends on which units disappear: removing our earliest units (FIFO) gains 444 to 684
  own per cow; removing our last units (LIFO) loses 450 to 602. So own cash here is a sale-timing question; the
  margin answer holds under both.

**Herd level.** The value is concave in the number kept (`summary_log.txt` section 5):

| Side, world | Cows dropped | Best keep | Keep all |
|---|---|---|---|
| KC8 112592389 | 13 | 4, +393 | -541 |
| KC8 112591190 | 11, all on day 22 | 4, +1,705 | +161 |
| KS1 112591190 | 14 | 3, +346 | -982 |
| DSM 112592389 | 7 | keeping even one is -423 | |

**DSM-style trimming applied to our arms** (`dsmcut_log.txt`): 6.3 animals a world give own +0.49 to +0.67k, rival
+2.1 to +2.3k, **margin -1.5 to -1.8k**, worse in 39 or 40 of 40 worlds.

## 4. Where the current model goes wrong, quantified

a. **Wrong unit value (the dawn quote, held constant).** The direct cost through premature drops is small.

- Regret on the 18k per-animal decisions, per world (`rules_log.txt`, margin FIFO / LIFO):

  | Side | Quote rule | Oracle, never-drop, floor, last-cycle |
  |---|---|---|
  | KS1 | 1,651 / 591 | 1,584 / 462 |
  | KC8 | 565 / 445 | 450 / 283 |
  | KE7 | 1,502 / 788 | 1,288 / 530 |
  | DSM | 463 / 203 | 318 / 28 |

  The quote rule's excess regret is 67 to 258 a world.
- On the arms' actual drops, keeping those that had 2 or more productions left adds +50 / +144 / +141 margin a world
  (KS1 / KC8 / KE7). Their final-cycle drops were right: keeping them would give -48 / -5 / -94.

b. **All-or-nothing herd drops.** On average 3.3 (KS1) and 3.1 (KC8) cows stop on the same day. The best partial
keep would add +128 / +272 / +170 a world (upper bound). Keeping half of the animals that had 2 or more productions
left, most productions first, gets +74 / +206 / +143 (`partial_keep_log.txt`).

c. **Service throttled at low quotes (partial abandonment).** At milk quotes below 40:

- on 46 to 48% of fed cow-days, the module plans CARE and the executor skips it (its value is 1 unit x quote);
- on 55% of fed sheep-days, the module itself plans no care.

Caring on every day we already feed would add 17 milk, 4 wool and 10 eggs a world. Margin +1,112 / +1,188 / +1,013
(KS1 / KC8 / KE7); own cash -26 to -199, because the units are sold the next morning. That takes 77 to 81 extra
CARE steps a world, on tiles the hand already visits to FEED (`care_log.txt`).

Goose care is skipped 38 to 40% of the time at normal egg prices, so that part is not caused by the quote. It is
probably a priority threshold such as `sd_tier_anim_c_minv 150` (a goose care is worth about 47 + 20); I did not
verify this.

d. **Re-buying after abandonment.**

- Mechanism: `_plan` issues a PLACE job for any pen that holds an animal on the leader's board but not on ours
  (`agents/mgt_lead_sector_animal.py` line 742). The market layer then buys the animal (line ~2800), with no check
  that it can still produce.
- Animals bought too late to ever produce (cow on day 22 or later, sheep 24 or later, goose 26 or later):

  | Arm | Coins a world | Worlds | Worst single world |
  |---|---|---|---|
  | KS1 | 690 | 19 | 4,600 |
  | KC8 | 800 | 20 | 7,200 |
  | KE7 | 475 | 19 | |
  | KB1 | 2,420 | 26 | 11,400 |

  This is exact, and own cash equals margin. DSM: 0.

e. **KB1** abandons 8.5 animals a world, and keeping them would add +4.4k margin. Most of its sheep losses are
execution misses (the plan fed them). Its cows are mostly module verdicts in collapsing herds. This is not a rule
question. In KS1, KC8 and KE7, cow escapes are almost all module verdicts, and sheep and goose escapes are mostly
execution misses (`animals.json`, field `mod_feed`).

## 5. Proposed corrected rule (not implemented)

**R1. Purchase and placement guard.** Buy or place an animal only if its production before night 28 pays for the
animal plus its feed at the unit value v. With full care, the first production is capped at max_held.

Units produced if placed on day p:

- cow: U(p) = 6 + 3 x floor((21 - p)/2)
- sheep: U(p) = 6 + 4 x floor((23 - p)/3)
- goose: U(p) = 4 + 2 x (25 - p)

Break-even unit value, with wheat at 40:

| Animal | Placement day: break-even v |
|---|---|
| Cow | day 21: 120, day 19: 89, day 17: 73, day 15: 64, day 13: 58 |
| Sheep | day 23: 123, day 20: 86, day 17: 70, day 14: 61 |
| Goose | day 25: 115, day 22: 58, day 20: 47, day 18: 41, day 15: 36 |

- Hard rule: never buy or place a cow after day 21, a sheep after day 23 or a goose after day 25. A pen emptied
  after its animal's last production is not refilled.
- Economic cutoffs, between the own-cash and margin break-evens: cow by day 17, sheep by day 21, goose by day 19.
  DSM uses 15, 19 and 11.
- Effect (hard rule, exact): +690 / +800 / +475 / +2,420 a world (KS1 / KC8 / KE7 / KB1).

**R2. Stop rule.**

- For an animal with 2 or more production nights left (on nights up to 28), never abandon. In the DP, value its
  product at `v = max(quote, FLOOR)`, with FLOOR = milk 60, wool 100, egg 45. That is the panel's own-cash value of a
  unit held to the end; margin values are higher.
- In the final cycle (1 production left), use the quote as now: keep only if the last production's units x quote
  cover the feed days x wheat.
- Implementation hint: an `sm_tile_plan` wrapper like the existing `retire_visit` one, which already receives the
  state and the day.
- Optional herd safety: if 2 or more animals of one kind would still be dropped on the same day with 2 or more
  productions left, keep at least half of them.
- Effect (exact keep counterfactual): +50 / +144 / +141 a world, or +74 / +206 / +143 with the herd safety. The upper
  bound is +128 / +272 / +170. For KB1, +4.4k.
- In the regret test, FLOOR and "decide only in the last cycle" both reach the oracle's regret.

**R3. Service at the same value.** Value FEED and CARE jobs at v, not at the quote, so that a fed animal is also
cared. Measured gross: +1.0 to 1.2k margin a world for about 80 CARE steps. This needs a labor test in the agent
before anyone believes it.

**Not recommended** (tested here):

- DSM-style trimming: -1.5 to -1.8k margin a world.
- A forward-price estimator built from inventory, shops and the last 3 days' sale rates of both players: it drops
  more animals, and its regret is higher than the quote rule's (`rules_log.txt`, FWD_MARGIN).
- A closed-form herd rule (`abandon_herd.py`): on the abandonment groups it gains only +47 to +158. On herds the arms
  kept, it would trim about 22 animals a world, a false alarm worth -13 to -15k margin a world (`herd_log.txt`).

**Total estimated effect:** R1 + R2 is about +0.74k (KS1) and +0.94k (KC8) margin a world, robust on this panel.
R3 could add up to about +1.1k, subject to labor.

## 6. Caveats

- **Frozen rival.** Every margin number assumes the rival's recorded quantities and timing. Our units change its
  prices, not its sales. A live rival that holds stock in a glut would weaken the margin channel. The panel and the
  ladder recordings share this assumption.
- **Our other actions are held fixed.** Labor for extra feeding or care is counted but not charged. Extra units are
  sold at hour 8 of the morning after production. Own-cash results depend on sale timing (the FIFO/LIFO bracket);
  the margin results do not.
- **One animal at a time.** The per-animal drop analysis is one-at-a-time; herd effects are concave (section 3).
  Different figures for the same question (for example the rules regret against the keep counterfactual) differ in
  how decisions are grouped, but they agree on the sign.
- **Other people's counts.** The coordinator's per-world cow death counts (KS1 1.5, KC8 2.6, KB1 7.3) differ from
  the current `multi/<ARM>` files (1.95 / 2.17 / 6.85). This report uses its own replays, which stop after step 718.
  A replay through step 719 adds a night-29 refresh that the real game never runs; I found and removed that
  artifact.

## 7. Method and files

**Replays.** `scripts/abandon_replay.py` replays the official engine through `scripts/upkeep_engine.py` and records
every animal-night, every effective FEED / CARE / HARVEST / COLLECT, every trade unit of both players (with the quote
inventory) and the inventory at every step. All 200 replays reproduce the recorded cash (`replay_log.txt`).

**Scripts** (all under `scripts/`):

| Script | What it does |
|---|---|
| `abandon_animals.py` | per-animal table, and the module's hour-0 verdict reconstructed from dawn states |
| `abandon_market.py` | exact repricer, single-unit value tables, keep counterfactuals |
| `abandon_validate.py` | checks the repricer against the engine |
| `abandon_drop.py` | per-animal drop counterfactuals |
| `abandon_individual.py` | keep value of each abandoned animal |
| `abandon_rules.py` | scores price inputs for the DP |
| `abandon_care.py` | care on every fed day |
| `abandon_dsmcut.py` | DSM's cuts applied to our arms |
| `abandon_herd.py` | closed-form herd rule (rejected) |
| `abandon_summary.py` | purchases, service level, plan versus done, stop medians, herd curves, DSM buy days |

**Outputs** (all under `results/fresh/abandon_20260926/`):

- Replays: `replay/<side>/<ep>.json`
- Tables: `animals.json`, `marginal.json`, `keep.json`, `drop.json`, `individual.json`, `rules.json`
- Logs: `replay_log.txt`, `validate_log.txt`, `market_log.txt`, `animals_log.txt`, `individual_log.txt`,
  `rules_log.txt`, `care_log.txt`, `dsmcut_log.txt`, `herd_log.txt`, `partial_keep_log.txt`, `summary_log.txt`
- DSM's stops listed one by one: `dsm_mid_list.txt`
