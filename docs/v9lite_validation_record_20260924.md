# V9-lite + y3: validation record for the submitting system (2026-09-24; nothing uploaded by this thread)

## Build
- `submissions/2026-09-24-mgt_v9lite/submission.tar.gz`, 185 files, 8.88 MB, sha256 `49a56e4c1a0f86e5ac0ddbb4a9d44fdf936f3e199ef4a838589c5619f25db539`
  (= `MANIFEST.json`, committed f0c923c). Entry `main.py` = `scripts/package_v9lite_main.py`, sha256 `b4c273bd...`,
  entry function `v9lite_agent` (defined last; Kaggle calls the last callable). Build: `scripts/package_v9lite.py`.
- Contents: y3 (`agents/mgt_y3.py` inside = `submissions/2026-09-24-mgt_y3/main.py`, sha256 `416ab697...`, byte for
  byte) + V9-lite at the reveals of days 12/15/18 (`scripts/value_tape_search_lite.py` over the other system's
  unchanged V9 chain) with a bank-aware budget (day 12 up to 30 s, then 20 s; 8 s reserve; an unfinished search
  keeps y3's route). No background thread. **y3's late-Yarn layer (both defect fixes) IS in this build.**

## What it is worth (paired, 95% CI)
| panel | vs m1 | vs y3 | wins |
|---|---|---|---|
| 2750-3000 exact, 185 (frozen opponents) | +917 (+622..+1,241) | +611 (+342..+911); +314 (+120..+524) without its 14 tuning worlds | m1 84, y3 87, this 96 |
| live V56, 120 games (60 seeds x 2 seats, seed-clustered CI) | +1,000 (+137..+1,922) | +822 (+82..+1,682) | m1 81, y3 83, this 85 |
| 180 ladder worlds (frozen) | - | +671 (+343..+1,052) | y3 130, this 134 |
| live pasture2700 / sixday_latest / v45, 40 each | - | +864 (+12..+1,925) / +1,423 (+385..+2,712) / -302 (-1,060..+457) | |

Combination versus V9-lite alone (`agents/mgt_v9litem1pkg.py`, same package on m1): 2750-3000 V9-lite alone +627 vs m1
(+328..+950), y3's layer adds +290 on top (+132..+457); live V56 V9-lite alone +847 vs m1 (+120..+1,682), y3's
layer adds +153 (-226..+460; wins 87 alone vs 85 combined). The layers add; the combination is chosen.

## Interaction: does a V9 switch strand sheep y3's layer services?
`scripts/v9_strand_interaction.py` on all 72 worlds (40 p2750 + 32 of the 180 ladder worlds) where the build
differs from y3 (diagnostic copy `agents/mgt_v9lite_diag.py`, identical play in 72/72): sheep lost 0 in every world.
After a late Yarn reveal (20 worlds) V9 switches TO tapes that service sheep themselves: y3's yarn tasks -19.9,
orphan days -1.7, wool +25.6, margin +3,865 vs y3 (p2750 alone: 14 worlds, +4,320). Other switches (52): +2,799,
orphan days +0.0, yarn tasks +1.5. The residue is switches made BEFORE a late Yarn Store (the new tape plans less wool; y3's layer
then carries up to 28 more service tasks, up to 4 orphan days): four of the six worst worlds, -1.3k to -2.2k. A tail,
not a general property (the other 26 switches average +2,022).

## Checklist
| check | result |
|---|---|
| base reproduces with the new code off | PASS: searches disabled (`agents/mgt_v9lite_off.py`) = y3 to the dollar in 185/185 |
| carries every dependency, imports nothing from the repo | PASS: official runner from an empty dir, 16 games, 0 modules loaded from the repo's scripts/agents/data/results |
| tested the way Kaggle loads it | PASS: `kaggle_environments` file loader + official time accounting, empty dir, Kaggle CPU: 8/8 (bank >= 46.8); `.gz` libraries decompressed also works |
| time bank at pessimistic concurrency | PASS: 4 packages at once per machine 16/16 (bank >= 35.2); one core 8/8 (>= 46.4); half a core 8/8 (>= 30.8, longest move 21.3 s); panels at 4 games per machine: 1,650 searches, 0 errors, budget never hit |
| hash matches notes and committed version | PASS (above) |
| replaces m1, not t10 | **NOT POSSIBLE BY A PLAIN UPLOAD**: only the latest 2 submissions are active, so any new upload retires the OLDER active one, t10 (56368334, 2805). Keeping t10 means re-uploading its file afterwards (the copy starts unrated) |

Known risks: one live V56 world where its switch lost both seats (-6.7k each); the real evaluator's CPU share and
whether it times module loading are unknown (the budget reads the live bank, so slower hardware turns searches into
y3's route, not time-outs); first multi-file upload for this project. Fallback: `submissions/2026-09-24-mgt_y3/`.
The fixed opening is not involved.
