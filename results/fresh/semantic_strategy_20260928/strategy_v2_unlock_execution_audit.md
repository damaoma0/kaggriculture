# Semantic strategy execution audit

8 completed games; 2 wins; mean margin -5,202. These are development outcomes.

## Daily execution

Counts show matched actual additions / compiled requested additions. Matching is by type and day; extra additions cannot compensate for a different missing type.

| Day | Crops | Animals | Structures | PASS | No-effect / work | New land: actual / planned asset tiles |
|---|---:|---:|---:|---:|---:|---:|
| 6 | 73/93 | 22/59 | 22/59 | 528 | 0/560 | 95/152 |
| 7 | 44/45 | 22/27 | 27/27 | 860 | 0/548 | 0/0 |
| 8 | 10/10 | 13/29 | 20/20 | 740 | 0/597 | 0/0 |
| 9 | 44/147 | 13/49 | 5/31 | 731 | 0/748 | 41/85 |
| 10 | 106/123 | 28/41 | 28/30 | 165 | 1/1051 | 34/52 |
| 11 | 114/114 | 26/29 | 17/17 | 214 | 0/1062 | 0/0 |
| 12 | 42/42 | 13/13 | 10/10 | 173 | 0/1155 | 0/0 |
| 13 | 60/61 | 9/10 | 9/9 | 147 | 0/1193 | 0/0 |
| 14 | 84/84 | 4/4 | 3/3 | 105 | 0/1210 | 0/0 |
| 15 | 55/55 | 3/3 | 3/3 | 123 | 0/1200 | 0/0 |
| 16 | 35/35 | 1/1 | 1/1 | 125 | 0/1194 | 0/0 |
| 17 | 55/55 | 1/1 | 1/1 | 92 | 0/1202 | 0/0 |
| 18 | 54/54 | 2/2 | 2/2 | 226 | 0/1199 | 0/0 |
| 19 | 60/61 | 2/3 | 2/2 | 84 | 0/1228 | 0/0 |
| 20 | 65/65 | 3/3 | 2/2 | 105 | 0/1251 | 0/0 |
| 21 | 64/65 | 1/1 | 1/1 | 137 | 0/1230 | 0/0 |
| 22 | 78/78 | 2/2 | 2/2 | 97 | 0/1235 | 0/0 |
| 23 | 95/95 | 1/2 | 1/1 | 85 | 0/1261 | 0/0 |
| 24 | 89/91 | 0/1 | 0/0 | 101 | 1/1250 | 0/0 |
| 25 | 98/99 | 0/0 | 0/0 | 68 | 0/1258 | 0/0 |
| 26 | 112/114 | 0/0 | 0/0 | 89 | 0/1256 | 0/0 |
| 27 | 90/90 | 0/0 | 0/0 | 164 | 0/1154 | 0/0 |
| 28 | 0/0 | 0/0 | 0/0 | 345 | 0/861 | 0/0 |

## Addition coverage by type (D6–28)

| Asset | Matched | Requested | Fraction |
|---|---:|---:|---:|
| animal:COW | 61 | 100 | 61.0% |
| animal:GOOSE | 52 | 89 | 58.4% |
| animal:SHEEP | 53 | 91 | 58.2% |
| crop:CARROT | 438 | 444 | 98.6% |
| crop:MELON | 3 | 3 | 100.0% |
| crop:STRAWBERRY | 124 | 158 | 78.5% |
| crop:TOMATO | 93 | 105 | 88.6% |
| crop:WHEAT | 869 | 966 | 90.0% |
| structure:COOP | 51 | 79 | 64.6% |
| structure:PASTURE | 105 | 142 | 73.9% |

## Retirement and errors

Observed animal exit classifications: {"no_matching_recorded_retirement": 20, "planned_early": 9, "planned_on_time": 77}.

Recorded retirement outcomes: {"exit_observed": 86}.

Unambiguous new crop site outcomes: {"later_matching_plant": 78, "no_matching_plant_in_followup": 67, "on_time": 950}.

No-effect commands by operation: {"no_effect:PLACE": 2}.

Lower-layer exception counters were logged for 192/192 daily plans. Empty top-level error lists do not establish that caught dispatcher exceptions were absent.

## Limits

- No following morning is saved for D29; boundary additions/exits are censored, while its action/financial ledger is still included.
- Boundary changes omit construction or placement that was undone within the same day.
- Counts match by type/day; same-crop rotations cannot be located from end labels alone.
- Later matching plants are not proof of a delayed original command: daily replanning can replace the old intention.
- An exit without a recorded retirement is described neutrally; these observations do not prove whether a death was economically harmful.
- No-effect commands measure unsuccessful physical work, not caught lower-layer software exceptions.
