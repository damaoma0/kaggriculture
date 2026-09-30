# Semantic strategy execution audit

8 completed games; 1 wins; mean margin -6,593. These are development outcomes.

## Daily execution

Counts show matched actual additions / compiled requested additions. Matching is by type and day; extra additions cannot compensate for a different missing type.

| Day | Crops | Animals | Structures | PASS | No-effect / work | New land: actual / planned asset tiles |
|---|---:|---:|---:|---:|---:|---:|
| 6 | 0/96 | 0/59 | 0/59 | 1045 | 0/325 | 0/155 |
| 7 | 80/80 | 27/34 | 34/34 | 903 | 0/537 | 0/0 |
| 8 | 30/30 | 22/39 | 31/32 | 828 | 0/567 | 0/0 |
| 9 | 2/148 | 8/53 | 1/36 | 1080 | 0/595 | 0/160 |
| 10 | 92/178 | 16/44 | 17/32 | 518 | 0/873 | 0/92 |
| 11 | 140/140 | 38/39 | 26/26 | 221 | 0/1101 | 0/0 |
| 12 | 105/123 | 10/15 | 9/12 | 308 | 0/1138 | 0/21 |
| 13 | 56/56 | 11/11 | 9/9 | 159 | 0/1158 | 0/0 |
| 14 | 61/61 | 4/5 | 4/4 | 94 | 0/1217 | 0/0 |
| 15 | 78/78 | 7/7 | 6/6 | 60 | 0/1246 | 0/0 |
| 16 | 55/55 | 3/3 | 3/3 | 97 | 0/1233 | 0/0 |
| 17 | 51/51 | 3/3 | 3/3 | 111 | 0/1201 | 0/0 |
| 18 | 44/44 | 1/1 | 1/1 | 96 | 0/1227 | 0/0 |
| 19 | 70/70 | 2/2 | 2/2 | 101 | 0/1250 | 0/0 |
| 20 | 78/78 | 0/1 | 0/0 | 100 | 0/1256 | 0/0 |
| 21 | 34/34 | 1/1 | 0/0 | 93 | 0/1249 | 0/0 |
| 22 | 71/71 | 0/1 | 1/1 | 69 | 0/1259 | 0/0 |
| 23 | 94/94 | 0/0 | 0/0 | 103 | 0/1262 | 0/0 |
| 24 | 92/93 | 0/0 | 0/0 | 97 | 1/1243 | 0/0 |
| 25 | 78/78 | 0/0 | 0/0 | 84 | 0/1252 | 0/0 |
| 26 | 104/105 | 0/0 | 0/0 | 102 | 0/1264 | 0/0 |
| 27 | 74/74 | 0/0 | 0/0 | 154 | 0/1141 | 0/0 |
| 28 | 0/0 | 0/0 | 0/0 | 344 | 0/869 | 0/0 |

## Addition coverage by type (D6–28)

| Asset | Matched | Requested | Fraction |
|---|---:|---:|---:|
| animal:COW | 60 | 131 | 45.8% |
| animal:GOOSE | 55 | 104 | 52.9% |
| animal:SHEEP | 38 | 83 | 45.8% |
| crop:CARROT | 371 | 388 | 95.6% |
| crop:MELON | 2 | 2 | 100.0% |
| crop:STRAWBERRY | 180 | 282 | 63.8% |
| crop:TOMATO | 141 | 173 | 81.5% |
| crop:WHEAT | 795 | 992 | 80.1% |
| structure:COOP | 54 | 93 | 58.1% |
| structure:PASTURE | 93 | 167 | 55.7% |

## Retirement and errors

Observed animal exit classifications: {"no_matching_recorded_retirement": 13, "planned_early": 6, "planned_on_time": 73}.

Recorded retirement outcomes: {"exit_observed": 79}.

Unambiguous new crop site outcomes: {"later_matching_plant": 134, "no_matching_plant_in_followup": 213, "on_time": 1081}.

No-effect commands by operation: {"no_effect:PLACE": 1}.

Lower-layer exception counters were logged for 0/192 daily plans. Empty top-level error lists do not establish that caught dispatcher exceptions were absent.

## Limits

- No following morning is saved for D29; boundary additions/exits are censored, while its action/financial ledger is still included.
- Boundary changes omit construction or placement that was undone within the same day.
- Counts match by type/day; same-crop rotations cannot be located from end labels alone.
- Later matching plants are not proof of a delayed original command: daily replanning can replace the old intention.
- An exit without a recorded retirement is described neutrally; these observations do not prove whether a death was economically harmful.
- No-effect commands measure unsuccessful physical work, not caught lower-layer software exceptions.
