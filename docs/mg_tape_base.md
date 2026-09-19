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

## Adaptation sources

- First principles: equilibrium opening (in; she moved to the same thing herself), market model for crop
  allocation, owned-hands executor (`scripts/fragments/mg_hands.py`) for work the tape does not contain.
- V50 (audit of `agents/v50_public.py`): tape-agnostic as written - terminal 7-turn planner (one gate fix),
  same-day courier, three shed-overflow guards, sale ordering and rival-exposure reordering, day-0 seed budget.
  ~19 layers share one V45-specific idiom (`routes[2 if t>=648 else native['route']]`) that one substitution
  fixes. Risky on foreign tapes: the sheep-to-cow cap, feed suppression, the literal-gated opening. The
  double-Yarn sheep expansion needs its day and tile gates generalised.
- Her new version: earlier commitment (strawberries from day 2, third quadrant day 9-10).
