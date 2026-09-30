# UMG animal purchase and departure dates

30 verified full replays of submission 56266758. Zero-based days. Percentages are pooled animal counts, not fractions of games.

## Successful purchases

| Days | Cows | Sheep | Geese |
|---|---:|---:|---:|
| 0–2 | 90 (39.5%) | 60 (31.3%) | 0 (0.0%) |
| 3–5 | 29 (12.7%) | 0 (0.0%) | 0 (0.0%) |
| 6–8 | 61 (26.8%) | 101 (52.6%) | 49 (42.2%) |
| 9–11 | 36 (15.8%) | 17 (8.9%) | 67 (57.8%) |
| 12–14 | 11 (4.8%) | 6 (3.1%) | 0 (0.0%) |
| 15–17 | 0 (0.0%) | 6 (3.1%) | 0 (0.0%) |
| 18–20 | 1 (0.4%) | 2 (1.0%) | 0 (0.0%) |
| 21–23 | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| 24–26 | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| 27–29 | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| Total purchased | 228 | 192 | 116 |

## Departures and survival

Percentages below use all successfully placed animals as the denominator, including those that survive the season. A departure happens at the end of the labeled day after two missed feeds; not every departure is necessarily deliberate retirement.

| Days | Cows | Sheep | Geese |
|---|---:|---:|---:|
| 0–2 | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| 3–5 | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| 6–8 | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| 9–11 | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| 12–14 | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| 15–17 | 1 (0.4%) | 1 (0.5%) | 0 (0.0%) |
| 18–20 | 2 (0.9%) | 10 (5.2%) | 0 (0.0%) |
| 21–23 | 2 (0.9%) | 5 (2.6%) | 0 (0.0%) |
| 24–26 | 3 (1.3%) | 60 (31.3%) | 2 (1.7%) |
| 27–29 | 4 (1.8%) | 47 (24.5%) | 1 (0.9%) |
| Still alive at game end | 216 (94.7%) | 69 (35.9%) | 113 (97.4%) |
| Total placed | 228 | 192 | 116 |

## Exact daily counts

| Day | Cows bought | Sheep bought | Geese bought | Cows departed | Sheep departed | Geese departed |
|---|---:|---:|---:|---:|---:|---:|
| 0 | 60 | 60 | 0 | 0 | 0 | 0 |
| 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2 | 30 | 0 | 0 | 0 | 0 | 0 |
| 3 | 29 | 0 | 0 | 0 | 0 | 0 |
| 4 | 0 | 0 | 0 | 0 | 0 | 0 |
| 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| 6 | 5 | 10 | 40 | 0 | 0 | 0 |
| 7 | 42 | 8 | 9 | 0 | 0 | 0 |
| 8 | 14 | 83 | 0 | 0 | 0 | 0 |
| 9 | 18 | 2 | 10 | 0 | 0 | 0 |
| 10 | 18 | 12 | 30 | 0 | 0 | 0 |
| 11 | 0 | 3 | 27 | 0 | 0 | 0 |
| 12 | 10 | 4 | 0 | 0 | 0 | 0 |
| 13 | 0 | 0 | 0 | 0 | 0 | 0 |
| 14 | 1 | 2 | 0 | 0 | 0 | 0 |
| 15 | 0 | 3 | 0 | 0 | 0 | 0 |
| 16 | 0 | 3 | 0 | 1 | 0 | 0 |
| 17 | 0 | 0 | 0 | 0 | 1 | 0 |
| 18 | 1 | 2 | 0 | 1 | 2 | 0 |
| 19 | 0 | 0 | 0 | 1 | 7 | 0 |
| 20 | 0 | 0 | 0 | 0 | 1 | 0 |
| 21 | 0 | 0 | 0 | 1 | 3 | 0 |
| 22 | 0 | 0 | 0 | 1 | 1 | 0 |
| 23 | 0 | 0 | 0 | 0 | 1 | 0 |
| 24 | 0 | 0 | 0 | 0 | 6 | 1 |
| 25 | 0 | 0 | 0 | 1 | 54 | 1 |
| 26 | 0 | 0 | 0 | 2 | 0 | 0 |
| 27 | 0 | 0 | 0 | 1 | 4 | 0 |
| 28 | 0 | 0 | 0 | 3 | 43 | 1 |
| 29 | 0 | 0 | 0 | 0 | 0 | 0 |

## Validation

All 900 game × three-day-period × species purchase counts reconcile to the previous exact-engine spending ledgers. Live animals, stored animals and carried animals are included to distinguish purchases from placements. Every species reconciles purchased = placed + unplaced, and placed = departed + surviving. Full daily counts, game incidence and successful purchase events are in `results/fresh/umg_lifecycles/animal_date_distributions.json`. Reproduce with `node scripts/report_umg_animal_dates.mjs`.
