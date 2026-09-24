# Which build is which (2026-09-24)

| build | what it is | source / built by | status |
|---|---|---|---|
| `mgt_t10` | Mother-Goose tape router over 584 of her old recorded games + feed guard, care top-up, orphan adoption | this project (09-19); `agents/mgt_t10.py` | **live, submission 56368334, 2805** |
| `mgt_m1` | `mgt_t10` + sell one step early + hire guard + strand rule | this project (09-20); `agents/mgt_m1.py` | **live, submission 56395605, 2700**; the reference for every paired number |
| `mgt_lib584` | `mgt_m1` code with the full library passed through a subset filter; plays identical games to m1 | this project (09-23) | research control only |
| `mgt_y2` | `mgt_m1` + late-Yarn service layer (`yarn_service=1, yarn_gate=1`) | this project (09-23) | parked (traced defect) |
| `mgt_y3` | `mgt_y2` + two fixes: rescue tasks pinned first, harvest only full batches (`rescue_pin=1, yarn_harvest_min=4`) | this project (09-23/24) | **candidate**, packaged in `submissions/2026-09-24-mgt_y3/`, NOT submitted |
| `mgt_o1` / `mgt_o1r` | `mgt_m1` + DSM's recorded days 0-5 opening, handoff to our tapes on the day-6 morning (o1r: opening passed through raw) | this project (09-23/24) | failed (−66k / −87k) |
| `mgt_dsm_a` / `mgt_dsm_b` | router over 109 of DSM's recorded games, hires trimmed to what arrived (a: with m1's guards, b: without) | this project (09-24) | failed (−7.1k / −13.1k) |
| **V9** (`mgt_v9`) | value selector: at the reveals of days 12/15/18 it forecasts candidate tape switches over 8 simulated futures, rejects switches that destroy live crops/animals, switches only on a predicted margin gain; base = `mgt_m1` | the user's other agent system: `scripts/value_tape_search_v9.py` (docs/records_refresh_20260923.md). `agents/mgt_v9.py` is OUR research wrapper so our harnesses can run it | under measurement |
| `mgt_v9y3` | V9 on top of `mgt_y3` (the forecast clones are also y3) | our wrapper | under measurement |
| **R3** (`mgt_r3`) | V9 + bounded transition repair: up to two repaired alternatives that keep named crops/animals alive via extra feed/water jobs and blocked digs; admitted only after 16 shop futures + 16 delayed-sale stresses; 18 s decision deadline | the user's other agent system: `scripts/value_tape_repair_r3.py` (docs/tape_transition_repair_20260924.md). `agents/mgt_r3.py` is OUR research wrapper | under measurement |
| `mgt_r3y3` | R3 on top of `mgt_y3` | our wrapper | under measurement |

Notes:
- R3 contains V9 (it falls back to V9's choice), so "V9 + R3" is not a separate combination. The combination set is
  m1, y3, V9, V9+y3, R3, R3+y3.
- V9 and R3 are not single-file submissions. They import from `scripts/` and need `data/kaggriculture.py` plus
  `results/fresh/value_tape_followup_20260923/{rival_library,modern_rival_library}`. Without the libraries V9 does not
  fail loudly; it corrupted the game in a test (−113k).
- `mgt_r1` / `mgt_r2` in `agents/` are unrelated older router variants from 09-19, not R1/R2 of the repair work.
