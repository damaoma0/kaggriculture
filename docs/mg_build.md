# Mother-Goose-based build on our chassis (paused 2026-09-18)

Goal set by the user: run Mother-Goose's policy (deferred commitment, tomato and goose programmes, her
strawberry rule) on our chassis instead of patching V45/V48's plan. Paused when she left the top of the board.
She was not beaten: her old submission 56266758 was at 3185 and level with Majkel when she retired it herself
at 13:52 UTC on 2026-09-18. What is here is mostly opponent-agnostic and is kept.

## Architecture: crop swaps on the tape's own visits

The V45 chassis replays its route tape by dead reckoning: units have no pathfinding, and each unit's
position is its position now plus its tape moves. So every visit the crew will make to every tile is
known in advance.

- `scripts/fragments/tape_calendar.py`: forward simulation of the crew from the tape (hand spawns
  follow the engine's `_spawn_hand` rule). `scripts/check_tape_calendar.py`: it matches every tape
  unit's recorded position in 8 benchmark games through step 712. Layers change only 11-60 of about
  6,700 unit commands per game.
- `scripts/fragments/mg_slots.py`: the slot layer. It replaces the crop at a tape PLANT visit and
  rewrites only that tile's later commands, inside the new crop's life, using visits the tape
  already makes. No unit moves differently and no hire is added. A swap is committed only when the
  engine rules show it can be serviced:
  - a watering turn on the planting day;
  - never two dry days in a row;
  - harvest turns before decay;
  - no other tape planting on the tile while the new crop occupies it.
- Seeds for the new crop are bought one step ahead from the layer's own reserve. Purchases of the
  replaced crop are capped at what the remaining tape plantings need. The layer sells only the units
  its own programmes harvested.
- The benchmark's own day-18 tomato programme (V219) refuses to start if any tomato exists. Our
  tomatoes are masked from its step-432 check, so it decides as it would on the tape's farm.
- `scripts/build_mg_agent.py` builds `agents/<variant>.py` as the frozen benchmark plus this block
  (a single file, loaded by Kaggle's last-callable loader).

The crew is saturated after day 12 (about 3% idle turns, `scripts/labour_idle.py`). That is why
servicing reuses tape visits rather than borrowing idle hands.

## Milestones (her 30 recorded worlds with her shops forced, against the live frozen benchmark; `scripts/verify_mg_slots.py`)

| Step | Variant | Servicing | Margin vs benchmark (95% CI) | Own cash vs null (95% CI) |
|---|---|---|---|---|
| Gate | all 13 day-11 strawberries → tomatoes | 390/390 planted, 4/4 units each, 0 drought, 0 decay, 0 stranded seeds | −13,544 | −9,497 |
| 1 | same, V219 kept working | V219 still produces in 8/8 of its worlds (0/8 before) | −10,480 | −7,696 |
| 2 | bidirectional rule, calibrated market model | 145/145 | **+231 (−599 to +968), 11-14-5** | **+571 (+72 to +1,133)** |
| 2 | same rule, own-cash objective | 180/180 | −693 (−1,728 to +310) | +421 |
| 3 | rule may add 0-2 second-wave melons | 144/145 | **+309 (−512 to +1,052)** | **+679 (+175 to +1,264)** |
| 3 | her fixed one melon | 164/165 | −4 (−847 to +792) | +700 (+187 to +1,284) |

The null control (the layer active with no swaps) reproduces the benchmark: margin 0.

## Findings

1. **A strawberry slot's value depends entirely on strawberry demand.**
   - The benchmark's realised strawberry price is 18-73 when the first four shops include at most one
     strawberry-demanding instance, and 120-235 when they include three or four.
   - Replacing the day-11 batch with tomatoes gains +1.1k to +4.0k own cash in poor worlds and loses up
     to −20k in rich ones.
   - She moves in both directions: she plants 18-49 strawberries (mean 32, the tape plants 33).
2. **The strawberry rule is derived from engine economics, not fitted to her tables.**
   - A market model uses the engine price curves (the chassis's `_r37_market_price`) and the engine's
     consumption rates. Each demanding shop takes 6 units a day (12 for single-product shops), the town
     centre 1 a day, and undrawn shops count at their expected rate.
   - It reads both farms' standing plants from the board at day 10 and assumes the opponent's remaining
     plantings follow the tape (a clone).
   - It values each allocation of the day-11 batch (strawberry, tomato or melon) and each conversion of
     a day 11-13 wheat slot into a strawberry, and maximises margin.
   - Its only calibrated parameter: sales spread over 4 days. Selling on the harvest day overstated the
     benefit of cutting by about 8k. `scripts/calibrate_straw_model.py`: predicted own change −9.7k
     against −11.3k observed (correlation 0.85); benchmark change +4.1k against +4.2k.
   - In effect it swaps the batch to tomatoes when strawberries are forecast below about 60. The
     break-even from slot values is about 51.
3. **Her −2.6k fertilizer line is fertilizer she applies instead of selling.** She buys 16 units a
   game, and applies about 90 to wheat against our 38 and 15 to tomatoes against 5. Its return shows up
   in her crop lines.
4. **Her geese rule was a misreading.**
   - Her herd is within 1-3 animals of ours in every world.
   - Converting the tape's sheep to geese lost −12.3k in a world where a Yarn Store appeared on day 9
     (wool 27.6k → 11.5k, eggs +3.4k). The tape builds pastures on day 6, before shop 3 is visible.
   - V48's opposite direction, geese to sheep once a Yarn Store is visible (decided at purchase), gained
     +7.0k in that world. This is untested across worlds (`mg6_herd_v48`).
5. **Her exact opening orders break on our budget-exact chassis against a 70-flipper**, the same failure
   as her tape. The opponent build `mg_live` uses the equilibrium opening instead (buy 5, keep).

## Resumed 2026-09-18 evening: V48, fertilizer, geese, flip

**Her policy vs V48 (the premise for continuing).** Seeds 174000-174031, both seats, 64 games per row,
against live V48 (`scripts/selfplay_gate.py` with `GATE_RIVAL=v48_public`). Margin is paired with the
frozen benchmark on the same seeds.

| Our side | W-T-L vs V48 | Margin (95% CI) | Margin vs benchmark (95% CI) |
|---|---|---|---|
| Frozen benchmark | 1-0-63 | −2,525 (−3,088 to −2,028) | — |
| Her reimplemented policy (`mg_live`) | 18-0-46 | −3,669 (−6,165 to −1,416) | −1,144 (−2,930 to +588) |
| Same, without her herd rule (`mg_live_crops`) | 22-0-42 | −1,580 (−2,621 to −524) | +945 (+84 to +1,800) |
| Our build at step 3 (`mg5_econ_m`) | 13-0-51 | −2,180 (−3,245 to −1,213) | +345 (−327 to +983) |
| Flip 5 | 2-0-62 | −2,070 | +455 (+4 to +966) |
| Equilibrium opening (buy 5 on turn 0, keep) | 2-0-62 | −1,709 | +816 (+353 to +1,318) |

- **Our reimplementation of her policy loses to V48.** Her actual moves beat V48 30-0 by +12.2k in her
  own worlds (tape, 40-coin cushion), and her ladder record against the 2700-2900 band was 10-4. So the
  gap is fidelity: we capture her crop choices, not her yields.
- **Her edge is yield per plant, not choices.** Her tomatoes produce 7.2 units per plant against our 4.0,
  because she fertilizes them early and harvests daily. Her strawberries (7.6), wheat (4.2), carrots and
  melons yield what ours do. Her realised prices equal the benchmark's except wool (+25) and milk (+5).
- **V48 is a production clone.** It runs the same V45 route tapes. So the shared-price lift from our
  changes flows to it, as it does to the benchmark: margin/own-cash behaves the same as in self-play.
- **Caveat on natural-seed panels.** Any change alters weed spawning, which shares the random stream with
  the shop draws. Paired own-cash numbers partly reflect different worlds; margin is the clean measure.

**Ladder record check (Kaggle episode service).** Her retired submission 56266758 was at 3185 when she
replaced it on 2026-09-18.

| Opponents rated | Her win rate | Majkel 56216119 | Majkel 56156662 |
|---|---|---|---|
| 3050+ | 60% | 61% | 60% |
| 2900-3050 | 72% | 87% | 87% |

- She beat Majkel head to head (100-75 on his episode lists).
- Her losses to the 2900-3050 band are narrow: median 106k against 113k, and only 2 of 28 below 85k. Most
  are to ymg_aq, Sida Zuo and Excluding. So Majkel's edge is robustness against the mid-field, not
  beating her. Nothing in the record ties his lead to nondeterminism.

**Fertilized-tomato fix (`fertilize_swaps`).** Swapped tomatoes use the fertilizer the tape brings to the
slot on day 20. That gives 4.98 units per plant (360 of 390 fertilized, zero losses), but own cash is −84
(−365 to +178) against the unfertilized swap. On our calendar a fertilizer buys one extra tomato, worth
what the fertilizer sells for, so the fix is left off. Re-deriving the swap threshold with 4-, 5- and
6-unit tomatoes (`scripts/rederive_swap_threshold.py`) leaves the boundary unchanged: day-10 forecasts
are all at or below 80 or at or above 161, and the rule swaps the first group.

**Geese, decided at each purchase from the visible shops** (her 30 worlds, against the benchmark):

| Rule | Converted | Margin (95% CI) | Own cash (95% CI) |
|---|---|---|---|
| Her rule (first two shops) | 19 | +258 (−109 to +570) | +583 (+227 to +932) |
| Sheep → geese while no Yarn Store is visible | 21 | +362 (+46 to +645) | +812 (+553 to +1,086) |
| Geese → sheep once a Yarn Store is visible (V48 direction) | 6 | +456 (−8 to +1,148) | +356 (0 to +923) |

- The gain comes from worlds with no Yarn Store all season: +1.1k margin.
- The V48 direction pays only where a Yarn Store appears on day 9: +6.9k margin in each of those worlds.
- The two directions never fire in the same world, so the candidate uses both.

## Three-opponent panel (2026-09-18)

Candidate `cand_v1_nash5`: the calibrated strawberry rule with model-chosen melons, both herd directions,
and the equilibrium opening. Seeds 174000-174031, both seats, 64 games per opponent. Her recorded moves
are tested in her 30 worlds with the 40-coin cushion taken back out of her score.

| Opponent | Candidate W-T-L | Candidate margin (95% CI) | Candidate − benchmark, paired (95% CI) |
|---|---|---|---|
| Frozen benchmark | 42-0-22 (66%) | −24 (−854 to +776) | — |
| V48 | 20-0-44 (31%) | −1,242 (−2,170 to −351) | **+1,283 (+567 to +2,023)** |
| Her reimplemented policy (without R8) | 40-0-24 (62.5%) | +655 (−195 to +1,485) | +4 (−583 to +598) |
| Her recorded moves | 0-30 | −11,789 (−13,834 to −9,828) | +792 (−35 to +1,634) |

- **Against V48:** the candidate halves the benchmark's deficit. About +0.8k comes from the opening
  (immune to V48's turn-1 attack) and +0.5k from the crop and herd layers. It still loses.
- **Against her recorded moves:** it still loses every game. Her edge is yield from execution
  (fertilizer and daily harvests), which tape-visit swaps cannot produce.
- **Margin and own cash depend on the opponent's production plan.** Against her recorded moves (a
  non-clone with a fixed plan) the candidate's own-cash gain of +1,088 (+38 to +2,012) is mostly kept as
  margin (+792). Against production clones (the benchmark and V48) only about 15-20% is kept, because
  the shared-price lift flows to the clone.

## Executor stage (2026-09-18 night): owned hands, derived from her replays

Submitted `cand_v1_nash5` as 56341683 first. Then three extraction passes over her 30 replays
(`scripts/mg_servicing.py`, `mg_routing.py`, `mg_fertilizer.py`; outputs in `results/fresh/mg_executor/`).

**Her tomato schedule (285 plants).** Water at ages 0, 2, 4, 6 (survival), then fertilize+water at 7,
water+harvest at 8 and 9, fertilize+water+harvest at 10, harvest+dig at 11. 52% of plants carry exactly
this signature; the rest are one-element perturbations. Full-lived plants average 7.18 units, those with
both fertilizations 7.60 (81% take all 8). All 883 doubled productions had fertilizer active and water
that day; all 111 single ones lacked one. One unit services a tile per day, fertilize → water → harvest in
consecutive steps. The engine check (`scripts/tomato_schedule_test.py`) agrees: fertilize at 7 and 10 with
water on 7-10 gives 8 units, in 12 actions; daily harvest is her habit, not a requirement (two harvests at
9 and 11 avoid the cap). The tape's strawberry calendar gives a swapped tomato exactly 5.

**Her other crops yield what ours do** (strawberry 7.58 vs our ~7.5 with fertilizer at 9 and 13; wheat
4.22; carrot 3.36), so tomatoes are the whole yield gap.

**Routing and labour.** Same 11 hands a day as ours; she does fewer work actions (3,411 vs 3,492) and
idles 300 more unit-hours. She pays for tomatoes, carrots and geese with 140 fewer wheat waterings (3.08
per harvest vs our 3.45), ~90 fewer CARE actions and less strawberry work. Each unit walks a lane out of
the shed and finishes a tile before moving; animals early in the day, fields later. Her tomato bed is the SW
quadrant, rows 6-9, where our day-11 strawberry batch goes.

**Fertilizer.** Our placement equals hers (the earlier "she fertilizes earlier" was a board-inference
artefact). Gaps are volume: wheat 64% fertilized vs our 23% (+1.95 units per application, net +39 each,
~2k/game) and tomato plant count. Melons are never fertilized (6 units without). Her programme nets ~23.7k
of produce against 7.4k of forgone sales; ours ~20k.

**Our tape's slack** (`scripts/tape_slack.py`): ~132 redundant waterings and ~15 idle turns a day, scattered,
so an executor cannot run on freed tape labour; it needs its own hand (12th hire of the day: 89-144).

**Design: owned hands on owned tiles** (`scripts/fragments/mg_hands.py`). The tape keeps the farm; the slot
layer keeps its tomato tiles; on each tile's window days that the tape's calendar does not cover (ages 7,
8, 10 for a day-11 planting) one or two hands are hired after every other layer's hire window (tape by hour
2, V219/V233 by hour 6), buy fertilizer with the hire order, pick it up at the shed, walk the bed
nearest-first doing fertilize → water → harvest, and drop cargo before midnight. A failed hire leaves the
tape's 5 units. The market rule values tomatoes at 7.5 units and charges the hands.

Smoke test (her world 0, all 13 slots swapped): 94 tomato units (7.2 per plant) against 52 tape-only and 65
with fertilizer on the tape visit; 7 hand-days, 1,131 wages, 11 fertilizer bought, no failed commands.

### Owned hands, measured (her 30 worlds; seeds 174000-174031 vs V48)

| Test | Tomatoes per swapped plant | Own cash | Margin |
|---|---|---|---|
| Isolation, all 13 slots, tape visits only (`mg3_t11v`) | 4.0 | — | −10,480 |
| Isolation, fertilizer on the tape visit (`mg7_fert_t11`) | 5.0 | −112 vs hands | |
| **Isolation, owned hands v1** (`mg9_hands_t11`) | **6.97** (her 7.18) | −196 vs tape-only (−909 to +432) | +208 (−101 to +542) |
| Candidate v2 (`mg9_hands_econ`) vs null, 30 worlds | | **+1,527 (+382 to +2,802)** | **+1,203 (+191 to +2,247)**, 24-0-6 |
| Candidate v2 vs v1's crop rule (`mg5_econ_m`) | | +848 (+42 to +1,674) | +895 (+250 to +1,682) |
| Candidate v2 vs V48, paired with benchmark | | +6,996 | **+1,348 (+583 to +2,127)**; v1 was +1,283 |

- Hands hired 202/202 in the isolation and 72/72 in the candidate: no shortfalls, no failed commands, no
  drought or decay losses. Wages ~1,500 per swap world (6.7 hand-days), fertilizer bought ~14.
- Swapping all 13 slots everywhere breaks even: the extra 39 units per world sell into a glutted tomato
  market. Where the rule deploys them (10 of her 30 worlds) the hands add **+1,235 own cash and +912
  margin per swap world** over v1. On natural seeds against V48 the swap fires in half the games and the
  hands add only +65 margin.
- The tomato price is not the problem (ours 88 vs her 96). Volume is: 13 tiles at 8 units each into a
  market consuming 7-13 a day, plus the benchmark's own day-18 programme in some worlds; the marginal
  unit fetched ~29. She averages 9.6 tomato tiles, staggered over days 12-18.
- Per-world variance is large (−6.9k to +10.8k). The three losing swap worlds had no tomato-demanding
  shop visible at day 10; the model missed the opponent's gain from the withdrawn strawberries (+4.2k to
  +8.6k against a predicted +1.2k), a forecast error on the undrawn shops rather than a bug. Not fitted
  away at n=3.
- Candidate v2 vs the frozen benchmark on natural seeds: 42-0-22, −31 (−942 to +786); paired with v1 it is
  own cash −390 (−815 to −2), margin −7. The hands' tomatoes (+461) do not cover wages (+690) and
  fertilizer (+134). Marginal tomato ~24-33 against a hand cost of ~42 per unit.
- Model check on the swap worlds: in worlds with 0-1 tomato shops the model's tomato revenue is right
  (predicted 4.7-6.9k, realised 4.0-6.9k); in the four with 2-3 tomato shops it predicted +2.7-3.5k and
  the realised gain was −2.3k to +0.5k, because our early units erase the scarcity premium on our own
  late (V219) tomato sales, 80 units at ~163 in the null.
- Hands v2b (`mg10_*`: coverage subtraction, midnight dump, third hand): 7.55 units per plant in
  isolation, 7.02 in the candidate, but 219 hand-days against 202, so own cash −148 (−328 to +19) against
  hands v1. Candidate v2b on her worlds: 24-0-6, +1,045 (+20 to +2,078) vs null.
- Candidate v2b on natural seeds, paired with v1: vs V48 own −430, margin −85 (20-0-44, −1,326); vs the
  benchmark own −463, margin −160 (42-0-22, −184). Same conclusion at the old bed size.
- v1 hands lost 29% of second fertilizations to the turn budget (two hands, four turns reserved for the
  cargo drop, both ops planned even where the tape covered one). v2 subtracts the tape's coverage, lets
  cargo ride the midnight dump (the chassis's hour-23 guard counts carried stock; hands are never hired
  after day 28) and allows a third hand: world 0 went from 7.2 to 7.7 units per plant at the same wages.

### Scenario-weighted rule (econ2, candidate v3 `mg11_econ2`)

The tomato price below neutral inventory is a hinge that explodes with scarcity, so the value of the
late tomato sales depends steeply on how many of the five undrawn shops demand tomatoes, and valuing
at the expected demand misprices both tails (glut worlds and scarce worlds). econ2 values every option
across six demand scenarios (tomato-demanding undrawn shops: 0.4 with p 0.633 or 2.4 with p 0.367, from
Binomial(5, 2/8); strawberry-demanding: 1, 2.5 or 4.5 with p 0.19/0.62/0.19, from Binomial(5, 4/8)) and
maximises the expected margin. To fit the 1 s step budget the strawberry, tomato and melon markets are
simulated once per option per scenario and combined additively, and the option grid is coarse (keep
0/2/4/6/8/10/13, melons 0-2, adds 0/3/6/9/12). Decision step 0.35-0.40 s.

First smoke: her world 0 goes from "swap all 13" to 6 tomatoes + 1 melon + 6 strawberries, margin
+2.0k → +9.9k; the strawberry-rich world 5 keeps all 13 and adds 3, unchanged.

Her 30 worlds vs the benchmark: **24-0-6, +1,404 (+682 to +2,289)**, own +1,417 (+265 to +2,611),
benchmark cash +9 (v2: +320). Paired with v2: margin +201 (−165 to +714), own −110. Decisions: keep all in
19 worlds, 6 tomatoes in 4, 12 in 5, 13 in 1, 5 in 1; 61 hand-days (v2: 72). The two-strawberry-shop cell
went from −239 to +2,091 by planting 6 instead of 13. Planted 125/126, no errors.

Seeds 174000-174031 vs V48: **28-0-36, −767 (−1,618 to +25)**, median −528; paired with the benchmark
**+1,758 (+1,089 to +2,453)**; paired with the submitted v1 **+475 (+216 to +772)** margin, but own cash
−501 (−821 to −207) with V48's cash −976: the gain over v1 comes from depressing V48's strawberry and
tomato lines by more than our wages cost.

Seeds 174000-174031 vs the frozen benchmark: **48-0-16 (75%), +491 (−293 to +1,224)**, median +890; paired
with v1 **+515 (+230 to +851)** margin, own −477, benchmark −992. v3 is the first candidate significantly
better than the submitted v1 on natural seeds against both opponents; the gain is margin (the clone's
strawberry and tomato lines fall by ~1k) at a small own-cash cost (wages and fertilizer). Against her
recorded moves (30 worlds, cushion removed): 0-30, −11,434, but +1,147 over the benchmark (+263 to +2,076),
with our cash +904 and hers −243, so against a non-clone the gain is mostly our own. Peak call 0.48 s
against the 1 s limit. Not submitted at the time of writing.

## Built but not evaluated when paused

`mg6_herd_mg`, `mg6_herd_noyarn`, `mg6_herd_v48` (herd, decided per purchase), `mg6_flip5`, and `mg_live`
(her reimplemented policy as an opponent: her fitted tables in both directions, R6, R8, one melon, the
equilibrium opening). The three-opponent panel (her reimplementation, V48, frozen benchmark) was not run.
