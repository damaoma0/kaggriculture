# Mother-Goose's plan as the base (2026-09-19)

Direction set by the user: **her plan is the base; adaptations come from public V50 and from our
first-principles results.** This replaces the V45-benchmark-plus-layers line (`docs/mg_build.md`), whose
candidates sit at ~2200 on the ladder while V48-class agents are at 2600-2800.

## What changed on the ladder

- Public frontier: V49 and V50 (`agents/v49_public.py`, `agents/v50_public.py`), pure appends on V48 with
  identical route tapes. V49 adds carrot-for-wheat swaps by price, species choice by expected value,
  fertilizing young wheat, a same-day courier, shed guards and rival-stock-aware sale ordering. V50 adds a
  weed-repair fix and a day-earlier sheep expansion in double-Yarn worlds. **V50 beats V48 63-1 (+2,720)**, our
  old benchmark 64-0 (−3,943) and our best old candidate 57-7 (−2,678).
- Mother-Goose retired 56266758 (3185) for two new submissions, 56331731 (~3110) and 56331777 (~3065).
  Against the 2700-2900 band they are 52-0 (+14.3k), against 2900-3050 84%, against 3050+ only 29%
  (old: 88% / 73% / 60%); 2-18 against Majkel's newest. She never meets the V45-V50 family in 94 sampled
  replays (her opponents are all 2900+ with their own architectures).

## Her new submissions are closed-loop; the old one is a replayable plan

| | Old (56266758 and its twin 56266899) | New |
|---|---|---|
| Determinism | same shops → byte-identical actions for 8-12 days | diverge within a day between shop-matched games |
| Orders | exact | over-requested (hires, land, tomato sales at 11% fill) and capped by the engine |
| Opening | BUY 13, BUY 5, SELL 13 wheat round trip; $29 left | cow + BUY 5 wheat, keep; $5 left; day-1 hires short in 42/42 |
| Strawberries | from day 5, deferred batch days 11-13 (18/game) | from day 2, continuous; deferred batch −75% |
| Third quadrant | day 12 | day 9-10 |
| Tomato / carrot / wheat plants | 9.5 / 30 / 139 | 7.0 / 40 / 169 |
| Yields, fertilize ages | 7.5 strawberry, 7.4 tomato | unchanged |

Her new tapes do not replay even in their own world (21-21, −12k vs V50: recorded budget-exact buys miss when
prices differ and cascade). Her old tapes do: **30-0, +11.5k vs live V50** with natural weeds, no cushion, once
the opening is replaced by the equilibrium feed purchase (`scripts/mg_tape_offworld.py`).

## The base: a router over her recorded games

- Library: 584 rated games of the old policy as compact tapes (`data/mg_tapes/`, `scripts/fetch_mg_tapes.py`;
  the twin plays the identical pre-shop stream and stays byte-identical to 56266758 games for 4-8 days).
- Agent: public chassis core (hand alignment, weed repair, budget guard, sell clamping, dead stock, terminal
  liquidation) + tape library + shop router + equilibrium opening (`scripts/build_mg_tape_agent.py`). The
  router picks, at day starts, the tape whose shop history is closest in demand terms among tapes whose recorded
  board is compatible with ours. 4.7 MB file, 3 ms per step after the rewrite.
- Natural seeds 174000-174031 vs V50: 33-31, **+31** (−2,610 to +2,685); **+5.1k over our old benchmark** on the
  same games. About level with V50.

## Where the rest goes: leave-one-out in her own worlds (`scripts/mgt_loo.py`, 40 worlds vs live V50)

| Arm | W-L | Mean margin |
|---|---|---|
| Her native tape, raw | 36-4 | +8,437 |
| Native tape through the chassis layers | 37-3 | +8,507 |
| Router with that tape removed | 18-22 | −1,300 |

The chassis layers are free; **routing costs ~9.8k** (median 6.7k). Exact shop-prefix matches carry to day 9-12;
after that the chosen tape's later shops are wrong (4-6 of 8) and boards have diverged too far to switch. By
product the loss is wool −4.1k, then strawberry, tomato, wheat, milk, egg at ~0.5k each.

**The wool loss is one behaviour.** When the true world has more Yarn Stores than the chosen tape (12 of 40
worlds) wool is −13.5k and the total loss −19.7k; when Yarn positions match the loss is −4.8k with wool +0.1k.
Her own plan adds sheep as Yarn Stores appear at shops 3-5 (8→15, 14→20 sheep); a borrowed tape does not. This
is also V50's headline feature. First adaptation: a Yarn-responsive sheep programme on top of the tape.

## Router: board similarity in the choice (hamming_weight 1.0)

Adding the board Hamming distance to the ranking key (`--cfg hamming_weight=1.0`, agent `mgt_v2e`) is worth
**+2,402** in leave-one-out (+362..+4,435; 23-17; dead commands 91 -> 57). Weight 0.5 is +1.4k, 2.0 and a looser
compatibility limit are worse, a heavier wool weight does not help.

## Adaptation 1: servicing repairs on top of the tape (`scripts/fragments/mgt_sheep.py`)

All numbers: 40 leave-one-out worlds vs live V50, paired against the router alone (`mgt_v2e`, 23-17, +1,101).
`scripts/mgt_loo_compare.py <candidate> <reference>` prints the paired table.

| Build | What it adds | W-L | Paired margin |
|---|---|---|---|
| `mgt_g1` | feed guard only | 25-15 | **+2,331** (+201..+6,106), better 12-3 |
| `mgt_t7` | feed guard + care top-up + sheep expansion gate | **28-12** | **+3,032** (+603..+7,199), better 22-11 |
| top-up over guard | | | +701 (+182..+1,328) |

Natural seeds 174000-174031, both seats, vs live V50 (`scripts/selfplay_gate.py`, loaded with Kaggle's loader):

| Build | W-L | Mean margin | Note |
|---|---|---|---|
| `mgt_v1` router, no board term | 33-31 | +31 (-2,610..+2,685) | |
| `mgt_v2e` router, board term 1.0 | 40-24 | +1,758 (-577..+4,065) | |
| `mgt_t7` + feed guard, care top-up | **54-10 (84%)** | **+3,199 (+1,062..+5,292)** | paired over `mgt_v2e` +1,441 (+755..+2,256), 21 seeds better / 6 worse; max call 0.04 s |
| `mgt_t10` + orphan adoption | **54-10 (84%)** | **+3,340 (+1,345..+5,361)** | paired over `mgt_t7` +142 (0..+335): 3 seeds better (174026 +2.1k, 174008 +2.1k), 0 worse, 29 identical |

`mgt_t7` against the other two panel opponents on the same seeds: **V48 54-10, +4,735** (+2,287..+7,089); **frozen
benchmark 56-8, +5,487** (+2,919..+8,043).

**Feed guard.** Her crew feeds animals from the shed's wheat stock, which her own wheat fields refill; her feed
purchases are sized to the unit. On a borrowed tape the stock runs a few wheat short, a hand's `PICKUP WHEAT n`
comes up empty, its FEEDs do nothing, and after two unfed days the animal is gone. In the five-Yarn world
(109532024) eight of her fourteen sheep starved: margin -51k. The guard looks one step ahead at the tape's wheat
PICKUPs and buys the shortfall: 11 wheat in that game, margin **+16k** (wool 31k -> 94k). It buys something in 15
of 40 worlds, 1-13 wheat a game.

**Care top-up.** Her servicing is demand-conditioned (`scripts/mg_care_rule.py`, all 584 tapes): sheep are cared
for on 46% of animal-days (fed 68%) with no Yarn Store, 75-90% with one or more; cows 65% -> 86% as milk shops
appear; geese always ~92%. A tape from a lower-demand world under-services our animals. Every day the tape's own
FEED/CARE visits are read from the tape calendar; an animal it skips gets CARE (or FEED + CARE) from a hand of
ours when the banked unit is worth it at the price the engine curve is heading for, and a hand is hired only when
its run is worth 1.5x its marginal Fibonacci wage. Best worlds: four Pizza shops +8.5k (milk +13k), Yarn worlds
+4k each. Engine detail that matters: the bank is paid only if the animal is FED on the production day, and her
low-demand tapes skip exactly those feeds, so a top-up is only counted when the tape feeds the next production
day (or a second feed is charged).

**Sheep expansion (her Yarn rule) is gated off by the market model.** Her additive rule (4 + 10/9/4/2/2 per Yarn
Store by reveal day) says 14 sheep in a one-Yarn world, but against V50 - which runs sheep too - the wool market
is already saturated: 4 more sheep sold +51 wool for +143 revenue (price is `200 - 0.058 x^2` in the glut x and
hits the floor at x = 59). The gate now simulates the glut day by day from the engine curve, the shops'
consumption and BOTH farms' flocks; it declined in all 40 worlds once the feed guard keeps the tape's own flock
alive.

**Orphaned animals after a tape switch.** The two worst natural seeds (174026 -13k, 174015 -5k;
`scripts/mgt_dead.py mgt_t7 seed:174026:0`) are tape switches onto a tape whose animals sit on other tiles: four
cows / four sheep are never fed again and leave two days later. True dead commands are otherwise rare (WATER on
an empty tile 6-17 a game). Two fixes, leave-one-out paired against `mgt_t7`:
- adoption, first version (`mgt_t8`: an animal the tape will not FEED for three days is serviced by us): +36
  (-169..+279) but 8 better / 30 worse - it also fired on her end-of-season wind-down (she stops feeding on days
  27-29 but still comes to harvest), hiring ~3 pointless hand-days a game (-500) against +2k in the four worlds
  with real orphans. Corrected definition (`mgt_t10`): the tape's crew does not TOUCH the tile for three days:
  **+175 (+47..+334), 7 worlds better, 0 worse.** Kept.
- animal tiles weighted x3 in the router's board distance (`mgt_t9`): -228 (-874..+350). Not kept.

Lessons that cost games before they were understood (also in CLAUDE.md):
- Hire overlay hands only after the tape's last hire of the day (hour 1 on 96% of her days) and hide them from
  the tape layer. An extra unit on a shed tile moves the engine's next spawn, and a displaced tape hand replays
  its whole day one tile off (-5k to -9k a game).
- The shed holds 100 items. Overlay cargo dumped at midnight pushes her products out; bring it home and sell it
  the same day, carry feed leftovers forward, never take wheat or animals her own crew still picks up today.
- Overlay pastures must be left out of the router's board distance or it starts switching tapes.

## Adaptation sources

- First principles: equilibrium opening (in; she moved to the same thing herself), market model for crop
  allocation, owned-hands executor (`scripts/fragments/mg_hands.py`) for work the tape does not contain.
- V50 (audit of `agents/v50_public.py`): tape-agnostic as written - terminal 7-turn planner (one gate fix),
  same-day courier, three shed-overflow guards, sale ordering and rival-exposure reordering, day-0 seed budget.
  ~19 layers share one V45-specific idiom (`routes[2 if t>=648 else native['route']]`) that one substitution
  fixes. Risky on foreign tapes: the sheep-to-cow cap, feed suppression, the literal-gated opening. The
  double-Yarn sheep expansion needs its day and tile gates generalised.
- Her new version: earlier commitment (strawberries from day 2, third quadrant day 9-10).
