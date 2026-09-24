# Submission decision, 2026-09-24 (nothing submitted; the upload is the user's call)

Active now (only the latest 2 count, a new upload retires the OLDER active one): `mgt_t10` 56368334 (2805, older)
and `mgt_m1` 56395605 (2700). Candidates, all paired against y3 unless noted (frozen-opponent panels replay the
opponent's recorded moves; live V56 reacts):

| candidate | 2750-3000 (185) | 180 ladder worlds | live V56 | official runner on Kaggle CPU | form |
|---|---|---|---|---|---|
| `mgt_y3` (`submissions/2026-09-24-mgt_y3/`) | +306 vs m1 (+204..+416) | +183 vs m1 (+105..+266) | +295 vs m1 (+69..+554), 40 games | 8/8, bank >= 55.2 | one .py |
| `mgt_v9lite` (`submissions/2026-09-24-mgt_v9lite/`) | **+611 vs y3** (+342..+911); +314 excluding its 14 tuning worlds | **+671 vs y3** (+343..+1,052) | **+645** (+89..+1,327), 40 games; **+911** (+151..+1,793), 80 fresh games; pooled +822 | 8/8, bank >= 46.8, longest move 10.8 s | tar.gz, 185 files, 8.9 MB |

V9-lite = y3 + the other system's value selector V9, made about 3x cheaper (stream B, same decisions as V9 on 33/33
checkpoints) and packaged with a bank-aware budget (day 12 up to 30 s; an unfinished search keeps y3's route).
Wins: 2750-3000 87 -> 96, 180 worlds 130 -> 134, live V56 29 -> 27 and 54 -> 58. 1,650 searches, 0 errors, budget
never hit (day 12 median 11.6 s, max 18.2 s under 4 games per machine). Known risks: one live world (timing test
seed 0) where its switch lost both seats (-6.7k each vs y3); the real runtime's CPU share and whether it times module
loading are unknown (the budget reads the live bank, so slower hardware means more searches keep y3's route rather
than time-outs); a multi-file archive is a new submission path for us (the loader, gz fallback and root discovery
were tested from an empty directory, not on the real evaluator).

Options:
1. Upload V9-lite only -> active {V9-lite, m1}; t10 retires.
2. Upload y3, then V9-lite -> active {y3, V9-lite}; t10 and m1 retire. Recommended: the two strongest measured
   builds, with y3 a single-file fallback if the archive misbehaves on the real evaluator.
3. Upload V9-lite, then re-upload t10's file -> active {V9-lite, t10 copy}; m1 retires; the copy starts unrated.
