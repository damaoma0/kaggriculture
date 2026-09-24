# Ladder tracking (from 2026-09-24)

Live: `mgt_v9lite_y3_iofix` 56525017 (uploaded 2026-09-24 15:26 by the other agent system; its description gives
SHA 37223758, a rebuild of our validated archive 49a56e4c) and `mgt_m1` 56395605. `mgt_t10` 56368334 retired by that
upload. The next upload retires m1. Tools: `scripts/track_submission.py <sub> [ref...]` (first-N-games comparison
by opponent band), `scripts/rating_trend.py <sub>... --window N` (appends current ratings to
`results/fresh/rating_log.jsonl`; win rate / margin by consecutive windows of games). The API has no per-game rating;
opponent bands use the 2026-09-23 full leaderboard.

## 2026-09-24 21:15
- V9-lite 2645.4, 76 games, 60-16 (79%, margin +8,258); first-76 comparison: t10 65-11 (86%), m1 58-18 (76%).
  V9-lite met more 2500-2750 opponents early (15-6 in 21 games; t10 9-0, m1 4-3). Placing; too early to judge.
- m1 2740.0 (2700 on 09-23), 488 games; by 60-game windows 77% -> 65% -> 57% -> 65% -> 48% (09-24, 29-31 vs >=2500)
  -> last 8 3-5. Same shape as t10 before its decline (last four windows 57/55/48/46%; rating 2805 -> 2752.6).
  Reading: m1's 2740 is at or past its peak; retiring it costs less than the number says.
- **The 2750-3000 panel led the ladder:** it measured t10 −352 vs m1 (CI −648..−76) while t10 still held the higher
  rating; the ladder has since converged toward it (t10 falling). A validation of the panel as an instrument.
