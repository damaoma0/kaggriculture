# Hand-off to the meta-openings thread (from the sale-rules / semantic-stack thread, 2026-09-30 ~04:45 UTC)

The user fired up a separate thread to copy the leaders' meta openings. Messaging between sessions is unavailable
from this session, so this file is the hand-off. Please read it before starting; append replies at the bottom.

## Findings

- **Fresh leader fetch:** `data/leader_tapes/<team_id>_<submission>/`, from `scripts/harvest_leader_tapes.py`.
  - Each tape now also stores `quadrants_by_day`: both seats' owned quadrants at each dawn, read from the replay.
  - Team names come from `results/fresh/ladder_live_20260930/leaderboard_20260930.json`.
  - The latest 30 games of each top-10 team's best submission are in.
  - A bigger fetch (top-20, up to 80 games each) was started at ~04:35 and keeps **adding files to these folders**.
- **Quadrants** (current best submissions, 30 games each):

  | rank | team | submission | quadrants | 3rd quadrant | 4th quadrant | wins / 30 |
  |---|---|---|---|---|---|---|
  | 1 | M & M & P & Q | 56679033 | 4Q 30/30 | day 8 (22) / 9 (8) | day 10 | 30 |
  | 2 | DECEM | 56688636 | 4Q 30/30 | day 8 / 9 | day 10 | 23 |
  | 3 | Victor @ Tufa Labs | 56686384 | 4Q 30/30 | day 8 / 9 | day 10 | 20 |
  | 4 | DSM (new) | 56692773 | 4Q 30/30 | day 8 | day 10 | 30 |
  | 5 | Vadim Vasilenko | 56678397 | 3Q 29/30 | day 8 | - | 13 |
  | 6 | Unknown Mother-Goose | 56689315 | 3Q 28/30 | day 8 | - | 21 |
  | 7 | Yizhou | 56676365 | 3Q 30/30 | day 8 | - | 14 |
  | 8 | Boey | 56686734 | 3Q 30/30 | day 8 / 9 | - | 18 |
  | 9 | My second life | 56688520 | 4Q 30/30 | day 8 | day 10 | 10 |
  | 10 | Majkel1337 | 56663513 | 4Q 30/30 | day 8 | day 10 | 11 |

  Script: sale-rules scratchpad `leader_quadrants.py`. DSM's OLD submission 56619023 was 3Q; our stack's day 6-11
  cassette and block model copy that old plan (`data/leader_semantics_dsmc/16732748`).
- **matu997 (2,793) beat our live n18rc99s by 10.9k with a day-10 4th quadrant** (game 115287820).
  - Strawberries −10.0k: 297 vs 250 units at the same price. matu had 10 strawberry tiles by day 4 and 20 by day 7.
  - Wheat −6.0k and tomatoes −4.6k.
  - matu spent 12.3k more: land +4k, hires +2.6k, wheat +2.4k.
- **A naive 4th quadrant on our stack failed.** Arm n18rc244d = n18rc216d + `--land-gate` + `policy.land_by_day {"4": 10}`.
  - It bought the land only on day 12.
  - It left 17-20 tiles empty on days 12-13 and put the new land into tomatoes and carrots.
  - It made 43 fewer animal cares, and lost 3.5k vs n18rc216d on the matu997 game.

## Running in the sale-rules thread (read the outputs instead of redoing them)

- **Agent "leaders' openings + 4Q survey":**
  - Clusters the top-20 openings from the tapes.
  - Writes exact boards for M&M&P&Q / DSM new / DECEM / Victor / Boey / Vadim into
    `data/leader_semantics_0930/<team>_<sub>/`.
  - Report: `meta_report.md` in the sale-rules scratchpad.
- **Agent "planner retrain + 4Q prototype":**
  - Extracts DSM 56692773 into `data/leader_semantics_dsm4q/16732748_56692773`.
  - Builds a 4Q cassette and block model, plus arms on n18rc223d.
  - Traces why the 4th quadrant slipped to day 12.
  - Report: `retrain4q_report.md`.
- Sale-rules scratchpad:
  `C:\Users\xyygl\AppData\Local\Temp\claude\C--Users-xyygl-Documents-kaggriculture\6d41efd9-2702-44ee-9a16-7709427fd202\scratchpad`

## Submitted tonight (user's request)

n18rc223s = **Kaggle 56696209**: n18rc216 + milk / wool margin hold rules + 3-step bank guard. It was +974 vs n18rc216 on
Kaggle MGT (32/8). Live now: 56696209 + n18rc99s 56676484 (n18rc8s 56655029 retired). Record:
`submissions/2026-09-30-n18rc223s/`.

## Collision rules (please follow)

1. **Arm ids.** The sale-rules thread creates arms with `scripts/sem_arms_20260929.py` in
   `results/fresh/semantic_h2h_20260929/study/candidates` as **n18rc2NN**. It is up to n18rc245d, and its agents take
   the next numbers. Please use a **different prefix** (e.g. `n18mo01`…) so neither thread overwrites the other's
   candidates.
2. **Laptop.** The limit is 4 game workers on this shared laptop, and the sale-rules panels use 4 until ~10:00 (plus a
   few smoke games).
   - Please run games on Kaggle: `scripts/kaggle_remote/remote_panel.py pushcmd`. The sale-rules rounds use 2 private
     sessions.
   - Kaggle served a **STALE** dataset version after "ready" twice tonight. Wait ~10 min after "ready", and check
     `run_info.json` for "STALE BUNDLE".
3. **Data folders.** Treat `data/leader_semantics_dsmc`, `data/leader_semantics`, and the frozen candidates as
   read-only. The two agents above write only to `data/leader_semantics_0930/` and `data/leader_semantics_dsm4q/`.

## Replies

(append here)
- 2026-09-30 ~05:00 (sale-rules thread): the user halted the meta-openings thread; the 4Q opening work now runs from the
  sale-rules session as background agents - 4Q tape-router opening copying the leaders through the END of day 10 (user
  ruling), arms n18rc270-289; 4Q planner for day 11+ (cassette row / block model), arms n18rc250-269; leader opening survey
  (data/leader_semantics_0930/); opponent-style study. Reports land in the sale-rules scratchpad (router4q_report.md,
  retrain4q_report.md, meta_report.md, oppstyle_report.md).
