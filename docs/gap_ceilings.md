# The 4.5k gap to her original tape: hindsight ceilings of every tape-level attack (2026-09-20)

Setting: her recorded tape in her seat, `mgt_m1` live in the other, 128 of her recorded worlds never used for tuning.
Ladder case (her tape for the world removed from our library): 20-108, -4,345. Same plan (we play her tape for the
world): 112-16, +898. **The gap between the two is 5,243 (+4,387 to +6,075)**; every ceiling below is a paired gain
over the ladder case on the same worlds. Scripts: `scripts/mgt_late_choice.py` (offline), `scripts/mgt_ceilings.py`,
research hooks `MGT_ORACLE_SHOPS`, `MGT_LATE_ONLY`, `MGT_SELL_FROM` in the router template (inert on Kaggle;
`mgt_m1o` = `mgt_m1` + hooks plays identical games without them), arms `mg_oracle`, `mg_late<D>`, `mg_sell<D>` of
`scripts/mgt_loo.py`.

## What there is to choose from late (offline, all 128 worlds)
| day | shops known | tapes compatible with the board we are on (median) | worlds with only the current tape | full-shop distance: tape we are on | best compatible tape in hindsight | best tape in the library |
|---|---|---|---|---|---|---|
| 6 | 2 | 583 | 0% | 55.1 | 20.0 | 20.0 |
| 9 | 3 | 474 | 0% | 41.7 | 20.3 | 20.0 |
| 12 | 4 | 288 | 0% | 33.3 | 21.4 | 20.0 |
| 15 | 5 | **10** | 16% | 31.9 | 27.3 | 20.0 |
| 18 | 6 | **2** | 45% | 31.6 | 30.9 | 20.0 |
| 21 | 7 | 1 | 59% | 31.3 | 30.9 | 20.0 |
| 24 | 8 | 1 | 80% | 31.2 | 30.9 | 20.0 |

The router is not fixed at day 12: it re-ranks every morning to day 28. It stops switching because nothing is left
to switch to - each tape reacts to its own fifth shop and the boards part between day 12 and day 15. The shops that
decide the late game appear on days 15-24, exactly when the choice is gone. And the best tape in the whole library
is still 20 away from the world (0 = same demand at every checkpoint): 584 recordings do not contain the world.

## Game-based ceilings
| attack | how the ceiling was measured | W-L vs her tape | gain over the ladder case (95% CI) | share of the gap |
|---|---|---|---|---|
| better tape SELECTION, any day | router ranks against the world's FULL shop list from day 3 (perfect foresight, same library, same compatibility) | 36-92 | **+1,311** (+87 to +2,499) | 25% |
| switch LATER, day 12 | her own tape for the world hidden until day 12, then forced | 11-18 (n=30) | **+2,455** (+1,084 to +3,895) | 50% |
| switch later, day 15 | same, day 15 | 0-30 | **-3,628** (-5,804 to -1,515) | negative |
| switch later, day 18 | same, day 18 | 0-30 | **-5,476** (-7,380 to -3,510) | negative |
| switch later, day 21 | same, day 21 | 0-29 | **-4,690** (-6,085 to -3,165) | negative |
| BLEND: our production, a late-shop-matched sell schedule | a neighbour's crew and purchases with HER sell orders from day 12 | 15-113 | **-1,150** (-1,854 to -524) | negative |
| SYNTHESISE / re-derive late sells | not run as a game: with equal demand in the tape's world and the real world a neighbour's schedule already realises her prices (wool 112.7 vs 112.1, milk 92.6 vs 93.3, tomato 82.3 vs 81.4); the four sale-timing layers built earlier measured 0, -658, +25 / -405, -194 | | ~0 | ~0% |

(the day-15/18/21 rows are from the first 30 of 64 worlds; the sign is 0 wins in 89 games.)

- **Late switching is not blocked by our rule, it is blocked by the tape format.** A tape addresses tiles by counted
  moves on ITS board. Forcing even the perfect tape onto our diverged board on day 15-21 costs 3.6-5.5k: its
  commands land on the wrong tiles and ours are orphaned. Day 12 is the last morning a switch pays.
- **Selection is worth 1.3k at most**, with information nobody has (the four shops still to come are random).
  Consistent with the earlier top-four oracle (+1.8k against V50). The library is the constraint.
- **Sell schedules are dead three times over**: the matched-demand diagnostic, four built layers, and now her own
  sell orders on our production, which LOSE 1.2k (a schedule fits the production stream it was written for).
- **Where the gap is**: a perfect plan adopted at day 12 is worth +2.5k even after paying the switch; the other
  ~2.7k is the first twelve days (the first four shops match in 33 of 128 worlds) plus that switch cost. What the
  late half consists of is known from `docs/tape_opportunity_map.md`: her servicing, herd, fertilizer and plantings
  follow the demand open THAT DAY. That is a policy; no recording chosen in advance contains it.

## Consequence
Both tape-level ceilings are low (selection 25%, late switching negative, sells negative), so the tape library is
the constraint and the answer has to be a different kind of thing: a live late-game demand response that acts
through our own hands and in-place insertions ON TOP of the running tape, never through a switch. Its ceiling is
the +2.5k of the day-12 row or better (it pays no switch cost). Pieces, with the sizes measured earlier: animal
servicing and herd to her open-demand targets ~1.3k; fertilizer on the strawberries and tomatoes that are already
planted, and late carrot / tomato plantings, ~1.5-2k together.
