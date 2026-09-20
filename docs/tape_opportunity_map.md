# What is left to gain by modifying her tape (2026-09-20)

Base: `mgt_b1` = router over 584 of her recorded games + feed guard + care top-up + orphan adoption + sell one step
early. All numbers paired, leave-one-out (her worlds, that world's tape removed, live opponent) unless noted.

## The ceiling
| Same 40 worlds | vs V50 | vs frozen benchmark |
|---|---|---|
| her NATIVE tape (her plan made for that world) through our chassis | +8,507 (37-3) | +11,014 (39-1) |
| ours, borrowed tapes + repairs | +4,345 (28-12) | +6,735 (31-9) |
| gap | -4,163 | -4,279 |

We hold about 60% of her edge (51% against V50). Natural seeds, 256 games: 71.5% vs V50, 77.0% vs V48.
Her native tape IS the ceiling of tape modification: anything beyond it means out-planning her, not editing her.

## Production is already hers: the yields carry over
| per plant / animal | ours on a borrowed tape | her native tape |
|---|---|---|
| tomato | 7.00 (10.2 plants) | 7.06 (10.9) |
| strawberry | 7.22 (27.5) | 7.24 (27.1) |
| melon / carrot / wheat | 5.95 / 3.26 / 2.64 | 5.94 / 3.27 / 2.70 |
| wool per sheep / milk per cow / eggs per goose | 19.7 / 25.5 / 34.0 | 19.3 / 24.9 / 34.7 |

The 7.2-vs-4 tomato gap belonged to the V45 chassis. On her tape there is no yield gap and no plant-count gap, so
the executor's original justification (her fertilize / harvest schedule) is gone.

## What the remaining -4.2k is made of (ours minus native, vs V50)
own cash -3,673, rival +490: **price effect -2,785** (milk -1,714, wool -845, strawberry -348), unit effect -213
(tomato -544, wheat -493, wool -371, egg -342, carrot -298, offset by milk +1,550 from the care top-up), our overlay's
spending +675 (hires +368, wheat +346). Concentrated: four worlds lose 13-16k each (multi-Yarn, four-Pizza), the
median world loses 2.7k, 17 of 40 are within 2k of native.
The price effect is not sale timing (every sale-side change is measured null or negative). It is mostly production
not sized to THIS world's demand: a tape from a Yarn-heavier world over-supplies wool where ours has less demand, and
the care top-up adds milk everywhere, including where it only lowers the price.

## Inventory, ranked by value x chance of landing
| # | Modification | Value | How estimated | Build | Tape permits? | Lands in 10 days? |
|---|---|---|---|---|---|---|
| 1 | Care top-up priced with its OWN price impact (stop adding milk / wool where it only moves the quote) | +0.3 to +0.8k | inferred: milk price effect -1.7k against +1.55k of units; the valuation uses the outlook price, not the marginal one | hours | yes (overlay) | yes |
| 2 | Crop mix by shop draw (port the crop-swap layer + market model) | +0.5 to +1.3k | inferred: the crop unit effects vs native sum to -1.3k (tomato, wheat, carrot, egg); the V45 version measured +0.5k paired | 1-2 days | partly: wheat<->carrot swaps ride her visits; strawberry<->tomato need her fertilize calendar checked tile by tile | probably |
| 3 | Animal counts sized to demand, in BOTH directions (fewer sheep / cows where the shops do not buy) | +0.5 to +1.5k | inferred from the price effect; the upward half is MEASURED: +139 n.s. (80 worlds; +11.1k, +7.6k, -7.6k) | 1-2 days for the downward half (skip her BUY_ANIMAL + service visits) | yes for skipping purchases; extra animals need the SE quadrant (built) | maybe |
| 4 | Melon day re-plan (one step ahead on every lot) | ~+2k us, ~-2k rival | modelled on the engine curve and the traced lots (identical on both sides) | large: re-routing day 10 | NO - executor | no |
| 5 | Hour-1 farmer sale (farmer milks / shears the animal next to the shed at hour 0, sells at hour 1) | +0.1 to +0.3k | modelled: hour 1 is +10-15% on wool and milk, one or two animals a day | 1 day (farmer override + route repair) | executor-lite | unlikely to pay for itself |
| 6 | V48 / V50 sale-timing layers | +0.0 to +0.2k | measured on other bases: +137 (V44/V45); our own sell-early +22..+37 | 0.5-1 day each | yes | yes, but small |
| - | Tape selection | exhausted | measured: no day-12 feature beats the ranking; future-demand term -2.4k to -4.3k | - | - | - |
| - | Sale timing: hold, tick-align, post-reveal hold, sell-all at her sale points | 0 / -658 / +25, -405 / -194 | measured | - | - | - |
| - | Fertilizer guard | 0 (never fires) | measured | - | - | - |
| - | Feed economy / spending | nothing to take | measured: she feeds what her peers feed; the purchase gap is round-trip wheat | - | - | - |
| - | Late sheep expansion, wheat-field pastures | negative | measured: -2k to -13k a world | - | - | - |

## Overlaps
- 1, 2 and 3 are the same money seen three ways (production matched to this world's demand); together they are bounded
  by the price effect plus the crop unit effects, about 3k, not 3k each. 1 is the cheap slice of 3.
- 2 and 4 do not collide: the melon field is cleared on day 10-11 and her strawberries / tomatoes go in afterwards.
  2 and 3 share labour only through our own overlay hands (each is the 12th-14th hire, 144-377 a day).
- 4 and 5 both need command rewriting of her units, i.e. the same executor machinery; 5 is a small first piece of 4.

## Provenance and ladder check (2026-09-20 03:15 UTC)
- `submissions/2026-09-19-mgt_t10/main.py` (sha 14f4def1..., submission 56368334) IS her tape base: 941 lines of
  route-replay chassis machinery with no routes of its own, then 584 embedded tapes - 310 from her submission 56266758
  and 274 from 56266899, every one an episode in `data/mg_tapes/` - the shop router, and the overlay. The description
  "benchmark + demand-keyed strawberry rule + melons + geese + buy-5 opening" is the OTHER submission, `cand_v1_nash5`
  (56341683), a V45 benchmark with her rules bolted on.
- Ladder: 56368334 is at **2309.7 after 101 games, 85-16**, still rising (2032 -> 2265 -> 2310); last 25 games 20-5.
  By opponent's current score: <1800 21-1, 1800-2200 30-6 (+6.5k), 2200-2500 **25-5 (+6.3k)**, 2500-2800 **9-4
  (+2.0k)**. `cand_v1` on the same ladder: 2239.4 after 203 games, 115-88; 2200-2500 31-27 (+0.1k), 2500-2800 21-28
  (-1.2k). The rating lags the record because a new submission starts near 600 and the update shrinks with every game.

## Microstructure map (engine `_process_market`, and 40 traced games against V50)
- Orders are cut at 10 and filled by list position: position i of BOTH players is processed together, unit by unit,
  both quoted at the same pre-commit inventory, so two SELLs of one product at the same position split every price step
  equally; a SELL at a lower position finishes before the other side's starts. HIRE and BUY_LAND are atomic, in seat
  order. A buy quotes the post-buy inventory, so a same-step round trip nets zero. There is no seat advantage.
- So priority = (step, list position). Against V50, measured: only 19-21% of our wool, milk and strawberry units are sold
  in a step where V50 sells the same product (melon 87%), and in those steps both sides already sit at position 0
  (same position for 72-98% of the co-sold units; we are behind on 4-15% of them, i.e. 1-3% of all units). Position is
  already taken by both sides; re-ranking our list is worth tens, not hundreds.
- What is left is the STEP. Selling a lot one step before the rival's sale of that product is the only lever that has
  measured positive (+22..+37, never negative, all three opponents), and it only reaches lots already in the shed; 48%
  of her wool is delivered and sold in the same step. Every lever that moves our sales LATER pays the rival ~+400.
- Untried, on-thesis: V45-family opponents are tapes too - deterministic given the shops we also see, identifiable from
  their public farm by step 25, their tapes public. Their sale steps can be predicted and front-run by exactly one
  step (the chassis has the `front_run` / `opponent_plan` hook for this). Bound: 20% of ~68k wool + milk + strawberry
  revenue is co-sold; taking those lots first instead of sharing them is worth an inferred +0.4 to +0.7k to us and
  about as much off the rival. It does nothing against opponents that are not tapes.

## Majkel (rank 1): what we have and what we never did
- Measured: 38 of his games in the 52-replay segment study (`docs/leader_segments.md`): per-segment behaviour, reaction to
  shop reveals (same demand conditioning as hers), 58 PASS commands a game against her 882 (he works every hour, she
  leaves labour idle), fertilizer made and used rather than bought, and the record comparison on the board.
- Never done: replaying his tape against our benchmark, a product decomposition, or rule inference. His recorded actions
  are one sample of a closed-loop hourly planner; replayed open-loop they would desynchronise the way her NEW
  submissions' tapes do (21-21, -12k in their own world). Not worth doing as a tape.
- Nondeterminism: 15 of 210 same-seat pairs diverge on identical observation histories, median first divergence at
  step 3, action agreement 0.28 in the first segment and 0.00 from day 18. His overage clock drops 60 -> 40.8 s in the
  opening and is flat afterwards (hers 60 -> 46.3): a heavy start-up computation, then sub-second steps. Divergence at
  step 3, before any opponent or price information differs, reads as a wall-clock-bounded search (incidental), not a
  mixed strategy - inference, not proof.
- His wider ranges: shop-controlled correlations with the opponent's visible board were weak and inconsistent in the
  segment study, so there is no evidence he conditions on something she does not; the variance is consistent with
  re-planning every hour from noisy search. Learning from him means learning a planner, which is the executor route.

## Labour slack and the fourth quadrant (2026-09-20, offline over her tapes)
Scripts: `scripts/mg_slack.py` (584 tapes), `scripts/mg_slack_geo.py`, `scripts/mg_slack_absorb.py` (146 tapes).

**Slack.** 7,046 paid unit-steps a game: work 48%, travel 40%, idle 12% (855 steps). The idle is not a spare hand:
- by hour: <=3% idle for hours 0-15, then 6 / 7 / 14 / 21 / 30 / 41 / 56 / 72% for hours 16-23. It is the tail of
  each route. Trailing idle block per unit-day (days 6-28): 0 steps 34%, 1-2 steps 33%, 3-5 steps 27%, 6+ steps 5%.
- by phase: days 6-11 26 idle steps/day over 10.3 units; 12-17 41 over 11.6; 18-29 23-24 over 12.0.
- wages 4,720 a game; the last hire of each day costs 1,814 (38%) - so a dropped hand is worth ~73 a day.

**Can a hand be dropped?** Generous bound: drop the lightest hand (7.8 work + 8.5 travel steps), let every other
unit use its trailing block one-way (midnight auto-drop means no return trip), greedy nearest tile, inventory and
spawn shifts ignored. The others reach 38% of its work commands; ALL of it on 15% of days -> **232 a game at most**,
91 if the dropped hand had any seed / feed / fertilizer / shed job excluded. Twenty idle steps a day exist, but as
ten blocks of two, and a block of two reaches nothing. Not worth building.

**Can idle hands fetch harvest early?** No paid hand is idle in the morning: on day 10 (melon day) idle is 0% for
hours 0-15 in every sampled tape. Early runs need either an extra hire or re-ordering a hand's own route (a replan).
`docs/sale_timing.md` already prices the prize: only hour 1 is worth more (10-15% on wool/milk), the rest of the day
is flat +-3%, and only the farmer exists at hour 1.

**Fourth quadrant for travel.** She owns three quadrants in 581 of 584 tapes (NE day 6, SW day 11; never SE). Work
commands by ring: d0 16%, d1 12, d2 14, d3 15, d4 14, d5 11, d6 8, d7 6, d8 3 (mean 3.15). Day-20 boards: the 18
tiles within distance 2 hold the animals (6.5 cows, 4.2 sheep, 2.6 geese); the 30 tiles beyond distance 4 hold 13
strawberries, 9.6 wheat, 6 tomatoes - the low-touch crops are already the far ones. 77% of hand-days reach beyond
distance 4. Upper bound if every such hand-day stopped at 4: 1,060 steps a game = 48 hand-days = the last hand
(1,814) plus most of the next (~1,100) over a full season, ~2,900; SE cannot be bought before ~day 12, which leaves
~17 days: **<= ~2,000 of wages against 4,000 of land**. The realistic relocation (SE's 15 near tiles replace the 15
farthest) saves 300-400 steps, ~1,000-1,300. Negative on travel alone at any bound, and it needs a full replan: the
tape addresses tiles by dead-reckoned moves, so moving one crop rewrites every route through it. SE only pays if it
carries ADDED production (our sheep overlay: +139 n.s. on LOO), which is a different sum.

**Priority.** Neither idea clears a few hundred a game at its upper bound. Front-running the V45-family tapes
(inferred +0.4-0.7k, overlay-sized, no replan) stays ahead of both.

## Head to head against her ORIGINAL tape (2026-09-20, 128 fresh worlds)
`scripts/mgt_loo.py <agent> <agent> 128 mg_vs,mg_vs_only 80`, report `scripts/mgt_h2h_report.py`. A recorded tape
belongs to its world, so the panel is 128 of HER recorded worlds (seed, her shops forced, natural weeds) that were
never used for tuning (worlds 80-207 of the fixed shuffle; the 0-79 block is the development set). Her recorded
moves play her seat raw (equilibrium opening only); our agent plays the other seat live (we sit in seat 0 in 76
worlds, seat 1 in 52). Margins are ours minus hers. "Net" subtracts the 2,468 frozen-tape handicap of
`docs/tape_vs_bench.md` from us.

| `mgt_t10` | W-T-L raw | mean raw (95% CI) | W-T-L net | mean net |
|---|---|---|---|---|
| **A. ladder case**: her tape for this world removed from our library | **19-0-109** | **-4,485** (-5,346 to -3,610) | 8-0-120 | -6,953 |
| **B. same plan**: we are restricted to her tape for this world | **98-0-30** | **+546** (+380 to +738) | 5-0-123 | -1,922 |
| A minus B, paired by world (= routing to a neighbour's tape) | 15-0-113 | **-5,031** (-5,873 to -4,185) | | |

- **Our layers do not degrade her policy.** On her own plan the repairs + overlay are worth +546 (wool +461, milk
  +270 of revenue; +204 wages, +257 wheat of spending). Both seats agree (+518 / +585).
- **The whole deficit is the plan we replay.** Without her tape for the world we lose 4.5k to it: tomato -1,023,
  wool -829, wheat -694, milk -614 of revenue, and +1,171 of spending (wheat +571, wages +483). That is a
  WHAT-to-produce error (a neighbour's plan, made for other shops), not an execution error: the same chassis and
  overlay run her own plan at +546.
- **On the handicap.** 2,468 was calibrated on our old benchmark, a price-reactive policy, frozen against itself.
  Her tape here stays valid (3.6-4.6 commands without effect a game out of ~6,200; 5.4 against V50; no failed hire
  chain), and she does not condition on prices, so the real handicap in this matchup is probably much smaller than
  2,468. It cannot be measured without her code. The raw numbers are the better estimate; the net ones are the
  pessimistic bound.

| `mgt_b1` (= t10 + sell one step early) | W-T-L raw | mean raw (95% CI) | W-T-L net | mean net |
|---|---|---|---|---|
| A. ladder case | 19-0-109 | -4,455 (-5,317 to -3,586) | 8-0-120 | -6,923 |
| B. same plan | **111-0-17** | **+779** (+578 to +989) | 7-0-121 | -1,689 |
| A minus B | 13-0-115 | -5,235 (-6,078 to -4,384) | | |

Selling one step ahead of her adds +233 on her own plan (98-30 -> 111-17): the microstructure lever works against
her, it is just small next to the plan gap.

**What the 5.0k routing loss is made of (`mgt_t10`, A minus B, per game):** our revenue -2,982, our spending +668
(wheat +310, wages +279), HER revenue +1,372 (she no longer shares every quote with a twin selling the same lots
on the same steps: wool +2.7, milk +1.5, tomato +3.6 a unit). Our revenue loss is PRICE, not units:

| ours | units B -> A | realised price B -> A | revenue |
|---|---|---|---|
| wool | 134.3 -> 139.3 | 155.1 -> **142.5** | -972 |
| milk | 179.7 -> 181.1 | 129.4 -> **125.1** | -612 |
| strawberry | 212.4 -> 217.3 | 168.4 -> **163.6** | -221 |
| tomato | 77.6 -> **66.5** | 81.2 -> 83.1 | -776 |
| wheat | 405.3 -> **387.5** | 36.4 -> 37.0 | -431 |

A neighbour's tape reproduces her VOLUMES within 4% (tomato -14%); what it does not reproduce is the fit between
when / how much is sold and this world's shops. By phase the wool quote at our sale steps is equal to day 17 and
then falls away (days 18-23: 150 -> 134, days 24-29: 145 -> 113): the mismatch is in the late game, where the
shops that matter (days 9-27) were unknown when the tape was chosen.

## Plan versus execution: what the split looks like (2026-09-20, `scripts/mg_plan_split.py`)
**Interface today.** `Chassis.act` takes `routes[route_id][step]` - one flat Kaggle action dict
`{farmer, hands[], market[]}` - and mutates it. There is no task object anywhere on the crew side: a hand's command
is addressed by hand index and is only right if that hand stands where her hand stood (dead reckoning);
`hand_align` pads the list and `weed_repair` inserts a DIG and replays the displaced command. The MARKET half is
already split from execution: orders do not depend on routes, and `budget_guard`, `room_guard`, `clamp_sells`,
`dead_stock`, `terminal_liquidation`, `sell_lead` re-write them against the real cash and shed every step. The
only place a crew PLAN exists is the overlay: `_tc_simulate` / `_tc_visits` (tape calendar) recover
(step, unit, tile, command) from the tape, `_shp_cal` turns that into per-day feed / care / touch sets, and
`_shp_runs` + `_shp_work` are a working small executor (assign tiles to up to 4 hidden hands, walk, PICKUP wheat,
FEED / CARE / HARVEST, deliver and sell in the same step). So the extractor exists and a narrow executor exists.

**How much of a tape is plan.** Per game 7,046 unit-steps + 756 market orders:
- decisions, ~10%: PLANT 233, FERTILIZE 187, BUILD 21, BUY_ANIMAL 14, BUY_LAND 2 on the crew side; SELL 269,
  BUY_SEED 146, BUY_PRODUCT 47 on the market side (HIRE 278 is a consequence of the workload).
- upkeep that follows from those decisions by rule, ~36%: WATER 1,020, HARVEST 499, COLLECT_FERTILIZER 389,
  FEED 317, CARE 299 (her servicing is demand-conditioned, so FEED / CARE carry some decision too).
- execution, 57%: moves 2,837 (40%), shed logistics 349 (5%: PICKUP 212, PLACE 94, DROP 44), idle 857 (12%).
- The crew plan is 1,393 tile-visits a game (46 tiles a day, 2.2 commands a visit).

**How good her execution is.** Re-ordering the same tiles optimally inside each leg (exact DP, order constraints
ignored, so generous) saves 107 of 2,666 moves a game (4.0%); 87% of hand-days are already optimal. Re-packing
across hands is bounded by the slack study: <= ~1.0k of wages with a perfect packer, ~0.35k realistically. An
executor that routes 10% worse than she does costs ~280 steps = a hand a day = -1.8k.

**Read.** Splitting crew plan from crew execution is feasible (the extractor and a narrow executor exist) but
re-executing the SAME plan buys at most ~0.3-1.0k and risks ~2k: her crew half is near-optimal and we already run
it faithfully (+546 on her own plan). The 5k sits in the half that is ALREADY separable - the market plan (what is
sold when, wheat round trip) against the actual world's shops - plus a late-game production fit. The executor only
earns its cost if it is used to CHANGE the plan (late-shop re-plants, melon-day re-route), and that needs a model
of her plan as a function of shops first.

## Why the ladder case loses 4.5k: late shops, through PRODUCTION (2026-09-20, `mgt_b1`, 128 worlds)
Scripts: `scripts/mgt_h2h_lateshops.py`, `scripts/mgt_h2h_service.py`, `scripts/mg_service_dynamics.py`,
`scripts/mg_crop_dynamics.py`. The harness now records our router history, daily revenue of both sides, the
overlay telemetry and an hour-23 servicing snapshot of both farms.

**Correction.** "Price, not units" (above) was an average over two groups that cancel. Per world it is units:
- The router's last switch is on day 12 (median); after day 12 in 23 of 128 worlds, after day 18 in 9. The final
  tape has the same first four shops as the world in 33 worlds and the same last four in **0**.
- With the SAME wool demand in the tape's world and this world (59 worlds) our late wool is 52.1 units at 112.7
  against 52.7 at 112.1 on her own plan: **a neighbour's sell schedule costs nothing.** Same for milk (92.6 vs
  93.3) and tomato (82.3 vs 81.4).
- Where this world has MORE late Yarn demand than the tape's world (27 worlds) we sell 81.9 late units against her
  112.7 at ~195: **-4,161** there. Where it has LESS (38 worlds) we sell 133 against 96 at 90 instead of 124:
  revenue +33. Under-production at high prices is not paid back by over-production into a glut.
- OLS of the per-world loss on demand-capacity mismatch of the final tape (R2 0.20): intercept -639, early
  mismatch -1.0k, **late mismatch -3.6k**; the top quartile of late mismatch loses 8.3k.
- The deficit is a tail: the worst 32 worlds carry 61% of it, the worst 64 carry 93%. They are worlds where one
  product has many buyers and she scales it (her revenue minus ours: tomato +22k in a Farm-Farm-Piz-Farm world,
  wool +19k with late Yarn Stores, strawberry +16k, milk +10k). By buyers among the 8 shops, contribution to the
  mean gap: wool with 2+ Yarn +658, tomato with 2+ buyers +935, milk with 4+ +495, carrot with 3+ +524 (we
  out-earn her by 427 with 0-2), egg +170; our extra spending 1,254 (hidden hands 515, wheat 598, sheep 121).

**Her late game is a live policy.** Per animal-day, by the shop capacity for the product OPEN that day
(584 tapes): sheep fed/cared 57%/26% with no Yarn Store, 95%/95% with one (days 12-17), and care goes 3% -> 94%
ON THE DAY the first Yarn Store opens; herd on day 24 is 3.6 / 6.5 / 10.3 for 0 / 1 / 2+ Yarn Stores. Cows 47%/36%
-> 95%/95% across capacity 0 -> 24+. Crops the same: strawberry plantings on days 12-17 go 0.2 -> 21.9 a game and
their fertilizer on days 18-23 0 -> 34 with open capacity; tomato plantings 6 -> 17; carrots 0.5 -> 31 on days
18-23. In the head-to-head worlds our servicing matches hers where demand matches (sheep 80%/75% vs 78%/74%) and
is off where it does not (world has more: ours 6.5 sheep 80%/69% vs hers 7.9 at 89%/80%; world has less: ours 8.5
at 86%/75% vs hers 6.5 at 63%/48%).

**Consequence.** Re-deriving the SELL schedule late recovers ~0: sale timing is not where the loss is. What is
missing is her late demand response in production (herd, servicing, plantings, fertilizer), which no tape fixed
before the late shops are known can contain, and which the router cannot switch into (boards diverge).
