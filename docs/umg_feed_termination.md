# UMG feed termination dates

30 verified full replays of submission 56266758. Zero-based days. Each animal contributes once, including animals still alive at season end. Percentages count animals, not games.

The last-feed date is its final successful wheat feeding. Maintenance termination begins the following day; isolated skipped days followed by more feeding do not count. These dates do not establish intent for individual early losses.

| Last successful feed day | Cows (228) | Sheep (192) | Geese (116) |
|---|---:|---:|---:|
| 14 | 1 (0.4%) | 0 (0.0%) | 0 (0.0%) |
| 15 | 0 (0.0%) | 1 (0.5%) | 0 (0.0%) |
| 16 | 1 (0.4%) | 2 (1.0%) | 0 (0.0%) |
| 17 | 1 (0.4%) | 7 (3.6%) | 0 (0.0%) |
| 18 | 0 (0.0%) | 1 (0.5%) | 0 (0.0%) |
| 19 | 1 (0.4%) | 3 (1.6%) | 0 (0.0%) |
| 20 | 1 (0.4%) | 1 (0.5%) | 0 (0.0%) |
| 21 | 0 (0.0%) | 1 (0.5%) | 0 (0.0%) |
| 22 | 0 (0.0%) | 6 (3.1%) | 1 (0.9%) |
| 23 | 1 (0.4%) | 54 (28.1%) | 1 (0.9%) |
| 24 | 2 (0.9%) | 0 (0.0%) | 0 (0.0%) |
| 25 | 1 (0.4%) | 4 (2.1%) | 0 (0.0%) |
| 26 | 3 (1.3%) | 43 (22.4%) | 1 (0.9%) |
| 27 | 152 (66.7%) | 20 (10.4%) | 17 (14.7%) |
| 28 | 64 (28.1%) | 49 (25.5%) | 96 (82.8%) |
| Never fed | 0 | 0 | 0 |

All 300 game × three-day-period feed totals reconcile to successful wheat consumption in the previous exact-engine audit. Midnight feed resets are handled through the post-refresh consecutive-unfed counter. Every animal departure with prior feeding occurs two days after its last feed.

Reproduce: `node scripts/report_umg_feed_termination.mjs`. Individual histories and daily distributions: `results/fresh/umg_lifecycles/feed_termination.json`.
