# Ladder win analysis with at-game-time ratings

Direction: redo the 2026-09-23 win/seat/opponent analysis using ratings taken as of each game's creation time instead of the CURRENT leaderboard score for the opponent.

## 1. At-game rating availability

The Kaggle API does **not** expose a per-episode rating. `competition_list_episodes` returns `ApiEpisode`/`ApiEpisodeAgent` objects with only id/create_time/end_time/state/agents and submission_id/index/reward/state/team_name/team_id — no score or rating field on either class (checked against the SDK source, `kagglesdk/competitions/types/competition_api_service.py`). The replay JSON `info` block similarly carries only Agents/EpisodeId/TeamNames/seed. The only place a true per-episode Initial/UpdatedScore exists is the meta-kaggle dataset (`EpisodeAgents.csv`, 26.9 GB; `Episodes.csv`, 8.0 GB, per `dataset_list_files`), which covers every Kaggle simulation competition ever run and is impractical to fetch for this scope. **Exact at-game ratings are unavailable within these constraints.**

Fallback used: four already-fetched full leaderboard snapshots (2026-09-18T19:25, 2026-09-20T03:15, 2026-09-20T19:39, 2026-09-23T15:09, 9463, 9599, 9674, 9909 teams respectively). Each game is joined to whichever snapshot is closest in time to its `created` timestamp, separately for our team and the opponent (falls through to the next-closest snapshot if the team is missing from the closest one).

- Games: 1093 total in ladder_games.json; 856 on the two live submissions (t10, m1) used below; 237 on the older submission 56341683 excluded.
- Missing opponent at-game rating: 1 games (opponent team not present in any snapshot).
- Staleness (hours between game time and snapshot used) — ours: mean 13.4h, median 10.5h, p90 28.9h, max 33.7h; opponent: mean 13.6h, median 10.4h, p90 29.1h, max 53.0h.
- Ghost Rule at-game rating from the 4 snapshots: 2261.4 (09-18 19:25) -> 2309.7 (09-20 03:15) -> 2471.6 (09-20 19:39) -> current ~2800 (09-23).

This is real recorded history, not reconstruction, but it is coarse (4 checkpoints over ~5 days) — treat every number below as approximate, and the staleness figures above as the honest error bar on "at-game-time".

## 2. Win rate vs at-game rating difference, vs Elo

### pooled (n=855)

| diff bucket | n | wins | win rate | 95% CI | mean diff | mean Elo pred |
|---|---|---|---|---|---|---|
| <-300 | 41 | 26 | 63.4% | [48.1%, 76.4%] | -368 | 11.1% |
| -300..-200 | 84 | 56 | 66.7% | [56.1%, 75.8%] | -248 | 19.5% |
| -200..-100 | 80 | 52 | 65.0% | [54.1%, 74.5%] | -150 | 29.8% |
| -100..-50 | 68 | 49 | 72.1% | [60.4%, 81.3%] | -74 | 39.5% |
| -50..0 | 68 | 41 | 60.3% | [48.4%, 71.1%] | -25 | 46.3% |
| 0..50 | 73 | 46 | 63.0% | [51.5%, 73.2%] | +25 | 53.6% |
| 50..100 | 77 | 54 | 70.1% | [59.2%, 79.2%] | +76 | 60.7% |
| 100..200 | 141 | 99 | 70.2% | [62.2%, 77.1%] | +145 | 69.6% |
| 200..300 | 81 | 55 | 67.9% | [57.1%, 77.1%] | +248 | 80.6% |
| >300 | 142 | 111 | 78.2% | [70.7%, 84.2%] | +763 | 95.0% |

Logistic fit win ~ a + b*diff: a=+0.744 (se 0.077, p=2.8e-22), b=0.00048 (se 0.00022, p=0.0248); Elo's implied slope is 0.00576.
Overall actual win rate 68.9% vs mean Elo-predicted 57.0% (actual-Elo = +11.9%, 95% CI [+8.4%, +15.3%]).
Fitted 50%-win rating gap: -1537 (95% CI [-2989, -85]) — i.e. our fitted curve predicts a 50% expected score against opponents rated -1537 relative to us, not 0 as Elo assumes. Given the mean opponent rating actually faced in this sample (2428), that implies an equilibrium/saturation rating of roughly **891** (95% CI [-561, 2343]) — the rating at which we'd expect to score 50% against a similarly-composed future pool. This assumes the future opponent pool resembles the one observed here; it is not a forecast.

### t10 (n=476)

| diff bucket | n | wins | win rate | 95% CI | mean diff | mean Elo pred |
|---|---|---|---|---|---|---|
| <-300 | 31 | 20 | 64.5% | [46.9%, 78.9%] | -366 | 11.1% |
| -300..-200 | 54 | 36 | 66.7% | [53.4%, 77.8%] | -250 | 19.3% |
| -200..-100 | 53 | 34 | 64.2% | [50.7%, 75.7%] | -149 | 29.8% |
| -100..-50 | 41 | 31 | 75.6% | [60.7%, 86.2%] | -73 | 39.7% |
| -50..0 | 44 | 25 | 56.8% | [42.2%, 70.3%] | -25 | 46.4% |
| 0..50 | 47 | 31 | 66.0% | [51.7%, 77.8%] | +25 | 53.6% |
| 50..100 | 44 | 37 | 84.1% | [70.6%, 92.1%] | +75 | 60.6% |
| 100..200 | 67 | 45 | 67.2% | [55.3%, 77.2%] | +141 | 69.1% |
| 200..300 | 27 | 20 | 74.1% | [55.3%, 86.8%] | +244 | 80.2% |
| >300 | 68 | 54 | 79.4% | [68.4%, 87.3%] | +844 | 96.3% |

Logistic fit win ~ a + b*diff: a=+0.806 (se 0.101, p=1.89e-15), b=0.00057 (se 0.00029, p=0.0529); Elo's implied slope is 0.00576.
Overall actual win rate 70.0% vs mean Elo-predicted 52.9% (actual-Elo = +17.1%, 95% CI [+12.6%, +21.5%]).
Fitted 50%-win rating gap: -1415 (95% CI [-2937, +108]) — i.e. our fitted curve predicts a 50% expected score against opponents rated -1415 relative to us, not 0 as Elo assumes. Given the mean opponent rating actually faced in this sample (2430), that implies an equilibrium/saturation rating of roughly **1015** (95% CI [-507, 2538]) — the rating at which we'd expect to score 50% against a similarly-composed future pool. This assumes the future opponent pool resembles the one observed here; it is not a forecast.

### m1 (n=379)

| diff bucket | n | wins | win rate | 95% CI | mean diff | mean Elo pred |
|---|---|---|---|---|---|---|
| <-300 | 10 | 6 | 60.0% | [31.3%, 83.2%] | -372 | 11.0% |
| -300..-200 | 30 | 20 | 66.7% | [48.8%, 80.8%] | -243 | 19.9% |
| -200..-100 | 27 | 18 | 66.7% | [47.8%, 81.4%] | -151 | 29.7% |
| -100..-50 | 27 | 18 | 66.7% | [47.8%, 81.4%] | -76 | 39.2% |
| -50..0 | 24 | 16 | 66.7% | [46.7%, 82.0%] | -26 | 46.2% |
| 0..50 | 26 | 15 | 57.7% | [38.9%, 74.5%] | +25 | 53.6% |
| 50..100 | 33 | 17 | 51.5% | [35.2%, 67.5%] | +76 | 60.8% |
| 100..200 | 74 | 54 | 73.0% | [61.9%, 81.8%] | +148 | 70.0% |
| 200..300 | 54 | 35 | 64.8% | [51.5%, 76.2%] | +250 | 80.7% |
| >300 | 74 | 57 | 77.0% | [66.3%, 85.1%] | +689 | 93.9% |

Logistic fit win ~ a + b*diff: a=+0.668 (se 0.119, p=1.92e-08), b=0.00043 (se 0.00033, p=0.187); Elo's implied slope is 0.00576.
Overall actual win rate 67.5% vs mean Elo-predicted 62.2% (actual-Elo = +5.4%, 95% CI [+0.2%, +10.5%]).
Fitted 50%-win rating gap: -1548 (95% CI [-4102, +1006]) — i.e. our fitted curve predicts a 50% expected score against opponents rated -1548 relative to us, not 0 as Elo assumes. Given the mean opponent rating actually faced in this sample (2426), that implies an equilibrium/saturation rating of roughly **877** (95% CI [-1676, 3431]) — the rating at which we'd expect to score 50% against a similarly-composed future pool. This assumes the future opponent pool resembles the one observed here; it is not a forecast.

### By world type (pooled t10+m1)

| world type | n | actual win rate | mean Elo pred | actual-Elo | 95% CI |
|---|---|---|---|---|---|
| no_yarn | 272 | 84.2% | 55.8% | +28.4% | [+23.1%, +33.6%] |
| early_yarn_only | 208 | 69.7% | 57.8% | +11.9% | [+5.2%, +18.6%] |
| late_yarn | 375 | 57.3% | 57.5% | -0.1% | [-5.5%, +4.9%] |

late_yarn minus no_yarn (actual-Elo residual): -28.5%, 95% CI [-36.0%, -21.1%], permutation p=0.0002.

## 3. Seat asymmetry (rating-controlled)

| scope | seat0 n/win% | seat1 n/win% | raw diff (s1-s0) | 95% CI | Fisher p | rating-controlled OR (seat1) | OR 95% CI | p |
|---|---|---|---|---|---|---|---|---|
| pooled | 440/69.8% | 416/68.0% | -1.7% | [-4.5%, +7.8%] | 0.605 | 0.946 | [0.707, 1.267] | 0.711 |
| t10 | 252/71.4% | 224/68.3% | -3.1% | [-5.4%, +11.0%] | 0.484 | 0.905 | [0.609, 1.345] | 0.622 |
| m1 | 188/67.6% | 192/67.7% | +0.2% | [-9.1%, +9.3%] | 1 | 1.013 | [0.658, 1.560] | 0.952 |

## 4. Opponent identity

653 unique opponent teams across 856 games (t10+m1); 266 total losses.
Top-15 opponents by loss count account for 12.4% of all losses. Opponents we've played >=3 times (37 teams) account for 16.2% of losses. Losses to teams currently ranked in the top 100: 47 (17.7% of losses). Of losses with a valid at-game rating for both sides, 44.0% were to an opponent rated above us at game time (117/266).

| team | current rank | games | W-L | mean margin | mean opp rating (at game) |
|---|---|---|---|---|---|
| LagrangianLocomotive | 252 | 5 | 1-4 | -1,633 | 2283 |
| Omar Althobaiti | 110 | 6 | 3-3 | +1,023 | 2737 |
| Inzilbêth | 819 | 4 | 2-2 | +2,254 | 2422 |
| kowalskii | 2173 | 3 | 1-2 | +1,691 | 2019 |
| AcidicBlaster | 366 | 3 | 1-2 | -98 | 2706 |
| 摆烂小分队 🏆 | 27 | 3 | 1-2 | -1,460 | 2652 |
| Yaroslav | 162 | 3 | 1-2 | -1,772 | 2591 |
| curiosity | 115 | 3 | 1-2 | -1,152 | 2770 |
| ZHIRUI ZHAO | 347 | 3 | 1-2 | +1,009 | 2581 |
| QQ农场 | 40 | 3 | 1-2 | -2,100 | 2818 |
| kwa | 32 | 3 | 1-2 | -3,065 | 2839 |
| offhand | 76 | 3 | 1-2 | +2,160 | 2756 |
| CHEN Xiang | 155 | 3 | 1-2 | -427 | 2693 |
| DL Julius | 272 | 2 | 0-2 | -5,196 | 2551 |
| Satuker | 256 | 2 | 0-2 | -4,094 | 2468 |

## 5. Own vs opponent cash: win/loss margin decomposition by rating band

Overall (n=856): mean own cash in wins 108,507 vs losses 106,361 (contributes +2,145 to the margin gap); mean opponent cash in losses 112,076 vs wins 99,876 (contributes +12,200). Share of the win/loss margin gap from our own cash: 15.0%; from the opponent's cash: 85.0%.

Bands below are the exact at-game rating value used (only 3 distinct values occur among these 856 games, one per snapshot era -- see section 1), not a quantile split, so each band is a clean time slice rather than an arbitrary cut through one snapshot's block of games.

| our at-game rating (games created) | n (W/L) | ours: win vs loss | theirs: win vs loss | share ours | share theirs |
|---|---|---|---|---|---|
| 2310 (2026-09-19..2026-09-20) | 141 (117/24) | 111,511 vs 108,762 | 98,170 vs 114,500 | 14.4% | 85.6% |
| 2472 (2026-09-20..2026-09-22) | 448 (317/131) | 108,742 vs 105,782 | 100,567 vs 111,095 | 21.9% | 78.1% |
| 2801 (2026-09-22..2026-09-23) | 267 (156/111) | 105,774 vs 106,526 | 99,753 vs 112,709 | -6.2% | 106.2% |

