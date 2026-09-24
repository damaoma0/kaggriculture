# Maintenance past the last reachable harvest

Corpus: 323 leader games across 6 teams (`data/leader_semantics/`).

Unmatched maintenance actions (no planted/placed anchor found): 0. Unresolved animal-placement species lookups: 0.

## Overall wasted actions by type (mean per game / total)

| Type | Total | Per game | Share of all such actions |
|---|---:|---:|---:|
| WATER | 13068 | 40.46 | 3.5% |
| FEED | 923 | 2.86 | 0.8% |
| CARE | 1261 | 3.90 | 1.1% |
| FERTILIZE | 1860 | 5.76 | 3.1% |

## Overall wasted actions by asset kind (mean per game / total)

| Kind | Total | Per game |
|---|---:|---:|
| WHEAT | 9956 | 30.824 |
| CARROT | 3204 | 9.920 |
| SHEEP | 1014 | 3.139 |
| STRAWBERRY | 993 | 3.074 |
| COW | 929 | 2.876 |
| MELON | 660 | 2.043 |
| GOOSE | 243 | 0.752 |
| TOMATO | 113 | 0.350 |

## Wasted actions by day of season (total across corpus)

| Day | Wasted actions | Per game |
|---:|---:|---:|
| 19 | 124 | 0.384 |
| 20 | 1 | 0.003 |
| 21 | 72 | 0.223 |
| 22 | 6 | 0.019 |
| 23 | 215 | 0.666 |
| 24 | 153 | 0.474 |
| 25 | 91 | 0.282 |
| 26 | 262 | 0.811 |
| 27 | 5934 | 18.372 |
| 28 | 3386 | 10.483 |
| 29 | 6868 | 21.263 |

## Cost estimates

- Wheat wasted on FEED past last reachable harvest: 923 total, 2.86 per game (1 wheat per wasted FEED).
- Estimated unit-hours wasted (1 step/action + corpus per-day MOVE:working ratio for walking): 35246.3 total, 109.122 per game.
- Share of ALL maintenance actions (WATER+FEED+CARE+FERTILIZE) in days 20-29 that are past the last reachable harvest: 6.7% (16988 of 252651).
- FEED actions on animals on days 27-29 whose next production falls after day 28: 686 of 4561 FEED actions (624 of 3740 distinct animal instances).
- Per-game wasted-action count: mean 52.98, median 49.0, stdev 22.33, range 17-126.

## IMPORTANT CAVEAT: most wasted WATER is survival watering on an unharvested crop

Because `maintenance` only records actions that actually took effect, every 'wasted' WATER action in this report is on a tile that is still a *live, unharvested* plant (a harvested/weeded tile cannot flip a WATER flag). Splitting WATER's waste by kind: 12166 of 13068 (93.1%) are on one-time crops (WHEAT/CARROT/MELON) past their yield-bonus window but still standing with accumulated, unharvested yield on the tile; another 900 (6.9%) are on ongoing crops (STRAWBERRY/TOMATO) past their last scheduled production but already in the post-schedule decay phase, still holding un-harvested units. For both cases, a plant tile still turns to weed after 2 consecutive unwatered days regardless of production status (docs/environment.md), which would destroy the standing, unharvested yield outright. A literal 'stop maintaining once next production is beyond day 28' rule is therefore only a clean, no-downside saving when the tile has ALSO already been harvested (in which case it wouldn't need watering anyway and wouldn't appear here); applied to a still-standing crop it would need to be paired with either an immediate harvest or acceptance of that crop's loss. The same logic applies more weakly to FEED: an animal 2 consecutive days unfed escapes, which would also drop any of its own unharvested product bank. FERTILIZE and CARE have no survival role (only WATER/FEED do), so their wasted counts (1860 and 1261 total) are the cleanest, closest-to-unambiguous savings in this report.

## By team (per game)

| Team folder | Team name(s) | Games | Wasted/game | WATER | FEED | CARE | FERTILIZE | Wheat/game | Unit-hrs/game | Share days20-29 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 16915014 | Boey | 100 | 66.07 | 42.83 | 5.16 | 4.56 | 13.52 | 5.16 | 137.258 | 10.4% |
| 16623559 | DECEM | 42 | 55.19 | 48.24 | 1.64 | 3.07 | 2.24 | 1.64 | 113.729 | 6.2% |
| 16732748 | DSM | 61 | 50.46 | 42.80 | 1.48 | 3.69 | 2.49 | 1.48 | 105.764 | 5.6% |
| 16730612 | Unknown Mother-Goose | 40 | 49.77 | 42.70 | 1.60 | 4.05 | 1.43 | 1.60 | 103.486 | 5.9% |
| 16681125 | M & M & P & Q | 40 | 42.95 | 34.23 | 3.23 | 3.40 | 2.10 | 3.23 | 89.253 | 5.8% |
| 16770421 | Vadim Vasilenko | 40 | 35.00 | 26.77 | 1.38 | 3.83 | 3.02 | 1.38 | 64.569 | 4.0% |
