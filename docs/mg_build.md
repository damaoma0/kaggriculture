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

## Built but not evaluated when paused

`mg6_herd_mg`, `mg6_herd_noyarn`, `mg6_herd_v48` (herd, decided per purchase), `mg6_flip5`, and `mg_live`
(her reimplemented policy as an opponent: her fitted tables in both directions, R6, R8, one melon, the
equilibrium opening). The three-opponent panel (her reimplementation, V48, frozen benchmark) was not run.
