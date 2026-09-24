# Leader reveal-response rules (540 games, 6 teams)

Corpus: `data/leader_semantics/<team>/<episode>.json.gz`. See `scripts/leader_reveal_response.py` module docstring for the day-shift correction and the 'co' (cow vs empty coop) label ambiguity.

## Q1: units per shop revealed (excess holdings change vs. a non-demanding shop revealed on the same day)

### STRAWBERRY

| reveal day | n demand / n not | +units @3d | +units @6d |
|---:|---:|---:|---:|
| 3 | 262/278 | +0.36 | +7.13 |
| 6 | 264/276 | +7.07 | +9.19 |
| 9 | 299/241 | +7.16 | +8.16 |
| 12 | 263/277 | +6.63 | +7.37 |
| 15 | 269/271 | +4.13 | +4.38 |
| 18 | 261/279 | +0.68 | +0.58 |
| 21 | 280/260 | +0.25 | +0.17 |
| 24 | 269/271 | +0.88 | +1.01 |

Pooled cluster-robust OLS (delta ~ demanded + day + current holdings), n=4320 events / 540 games: demanded coef @3d = +3.45 (se 0.14), @6d = +4.93 (se 0.22).

Per-team pooled excess @3d: Boey=+1.0, DECEM=+3.6, DSM=+3.8, M & M & P & Q=+3.5, Unknown Mother-Goose=+3.5, Vadim Vasilenko=+3.6

### MELON

| reveal day | n demand / n not | +units @3d | +units @6d |
|---:|---:|---:|---:|
| 3 | - | - | - |
| 6 | - | - | - |
| 9 | - | - | - |
| 12 | - | - | - |
| 15 | - | - | - |
| 18 | - | - | - |
| 21 | - | - | - |
| 24 | - | - | - |

Pooled cluster-robust OLS (delta ~ demanded + day + current holdings), n=4320 events / 540 games: demanded coef @3d = +0.00 (se 0.00), @6d = +0.00 (se 0.00).

### TOMATO

| reveal day | n demand / n not | +units @3d | +units @6d |
|---:|---:|---:|---:|
| 3 | 140/400 | +0.00 | +0.08 |
| 6 | 122/418 | +0.03 | +1.73 |
| 9 | 153/387 | +2.38 | +4.72 |
| 12 | 123/417 | +2.04 | +3.13 |
| 15 | 125/415 | +1.91 | +2.47 |
| 18 | 162/378 | +0.98 | +0.09 |
| 21 | 140/400 | +0.53 | +0.95 |
| 24 | 137/403 | +0.38 | +0.24 |

Pooled cluster-robust OLS (delta ~ demanded + day + current holdings), n=4320 events / 540 games: demanded coef @3d = +1.06 (se 0.14), @6d = +1.54 (se 0.22).

Per-team pooled excess @3d: Boey=+0.0, DECEM=+1.8, DSM=+1.5, M & M & P & Q=+0.0, Unknown Mother-Goose=+1.0, Vadim Vasilenko=+1.3

### WHEAT

| reveal day | n demand / n not | +units @3d | +units @6d |
|---:|---:|---:|---:|
| 3 | 347/193 | +0.32 | +1.86 |
| 6 | 322/218 | -0.23 | +2.08 |
| 9 | 364/176 | +2.58 | +2.42 |
| 12 | 355/185 | +1.37 | +1.52 |
| 15 | 328/212 | +0.41 | +1.35 |
| 18 | 340/200 | +1.38 | +1.45 |
| 21 | 347/193 | +1.73 | +2.25 |
| 24 | 344/196 | +3.18 | +0.78 |

Pooled cluster-robust OLS (delta ~ demanded + day + current holdings), n=4320 events / 540 games: demanded coef @3d = +1.75 (se 0.27), @6d = +1.65 (se 0.32).

Per-team pooled excess @3d: Boey=+0.9, DECEM=+1.2, DSM=+2.5, M & M & P & Q=+1.5, Unknown Mother-Goose=+2.3, Vadim Vasilenko=+0.5

### CARROT

| reveal day | n demand / n not | +units @3d | +units @6d |
|---:|---:|---:|---:|
| 3 | 116/424 | +0.00 | +0.68 |
| 6 | 135/405 | +0.59 | +5.64 |
| 9 | 141/399 | +3.94 | +4.87 |
| 12 | 127/413 | +3.87 | +4.45 |
| 15 | 150/390 | +4.43 | +6.70 |
| 18 | 137/403 | +4.17 | +5.63 |
| 21 | 131/409 | +6.09 | +7.24 |
| 24 | 122/418 | +4.53 | +1.44 |

Pooled cluster-robust OLS (delta ~ demanded + day + current holdings), n=4320 events / 540 games: demanded coef @3d = +3.33 (se 0.21), @6d = +4.56 (se 0.32).

Per-team pooled excess @3d: Boey=+3.1, DECEM=+4.0, DSM=+2.8, M & M & P & Q=+5.4, Unknown Mother-Goose=+2.0, Vadim Vasilenko=+3.3

### WOOL

| reveal day | n demand / n not | +units @3d | +units @6d |
|---:|---:|---:|---:|
| 3 | 74/466 | +0.77 | +7.33 |
| 6 | 76/464 | +6.29 | +6.93 |
| 9 | 56/484 | +6.14 | +7.07 |
| 12 | 64/476 | +4.23 | +4.98 |
| 15 | 66/474 | +2.62 | +3.37 |
| 18 | 65/475 | +1.65 | +2.60 |
| 21 | 59/481 | +1.13 | +2.20 |
| 24 | 65/475 | +0.91 | +0.76 |

Pooled cluster-robust OLS (delta ~ demanded + day + current holdings), n=4320 events / 540 games: demanded coef @3d = +2.97 (se 0.13), @6d = +4.49 (se 0.15).

Per-team pooled excess @3d: Boey=+3.5, DECEM=+3.2, DSM=+2.5, M & M & P & Q=+3.0, Unknown Mother-Goose=+2.7, Vadim Vasilenko=+3.4

### EGG

| reveal day | n demand / n not | +units @3d | +units @6d |
|---:|---:|---:|---:|
| 3 | 139/401 | +0.05 | +1.41 |
| 6 | 128/412 | +1.25 | +2.19 |
| 9 | 126/414 | +1.21 | +1.24 |
| 12 | 169/371 | +0.02 | +0.04 |
| 15 | 140/400 | -0.01 | -0.02 |
| 18 | 126/414 | +0.04 | +0.09 |
| 21 | 133/407 | +0.10 | +0.12 |
| 24 | 143/397 | +0.05 | +0.14 |

Pooled cluster-robust OLS (delta ~ demanded + day + current holdings), n=4320 events / 540 games: demanded coef @3d = +0.26 (se 0.06), @6d = +0.53 (se 0.09).

Per-team pooled excess @3d: Boey=+0.5, DECEM=+0.1, DSM=+0.4, M & M & P & Q=+0.0, Unknown Mother-Goose=+0.3, Vadim Vasilenko=+0.4

### MILK

| reveal day | n demand / n not | +units @3d | +units @6d |
|---:|---:|---:|---:|
| 3 | 211/329 | +0.29 | +3.72 |
| 6 | 201/339 | +3.09 | +3.86 |
| 9 | 217/323 | +1.97 | +2.19 |
| 12 | 180/360 | +0.54 | +0.79 |
| 15 | 184/356 | +0.27 | +0.74 |
| 18 | 212/328 | +0.45 | +1.00 |
| 21 | 217/323 | +0.58 | +1.00 |
| 24 | 210/330 | +0.64 | +1.45 |

Pooled cluster-robust OLS (delta ~ demanded + day + current holdings), n=4320 events / 540 games: demanded coef @3d = +0.98 (se 0.06), @6d = +1.87 (se 0.08).

Per-team pooled excess @3d: Boey=+1.4, DECEM=+1.1, DSM=+1.0, M & M & P & Q=+0.9, Unknown Mother-Goose=+0.8, Vadim Vasilenko=+0.9


## Q2: timing of first commitment relative to reveal (window r-3..r+9)

| product | n obs | n censored | mean delay | median | p25 | p75 | anticip. | same-day | lag |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| STRAWBERRY | 1507 | 660 | -2.31 | -3 | -3 | -1 | 90% | 9% | 1% |
| MELON | 0 | 0 | - | - | - | - | - | - | - |
| TOMATO | 726 | 376 | -0.15 | -2.0 | -3 | 3 | 55% | 15% | 30% |
| WHEAT | 2747 | 0 | -2.67 | -3 | -3 | -3 | 91% | 9% | 0% |
| CARROT | 951 | 108 | 0.97 | 1 | -3 | 4 | 41% | 9% | 50% |
| WOOL | 374 | 151 | -0.98 | 0.0 | -2 | 0 | 40% | 59% | 0% |
| EGG | 451 | 653 | -0.33 | 0 | -3 | 3 | 46% | 26% | 27% |
| MILK | 830 | 802 | -1.99 | -2.0 | -3 | -2 | 77% | 22% | 2% |

## Q3: saturation (mean +units@3d among demanded events, by count of already-revealed shops also demanding the product)

- **STRAWBERRY**: prior=0 -> +6.87 (n=536), prior=1 -> +7.52 (n=521), prior=2 -> +1.99 (n=467), prior=3 -> -3.68 (n=346), prior=4 -> -7.11 (n=197), prior=5 -> -8.81 (n=78), prior=6 -> -7.52 (n=21), prior=7 -> -8.00 (n=1)
- **TOMATO**: prior=0 -> +1.30 (n=492), prior=1 -> +2.42 (n=358), prior=2 -> +1.50 (n=167), prior=3 -> -2.24 (n=63), prior=4 -> -6.06 (n=18), prior=5 -> -3.25 (n=4)
- **WHEAT**: prior=0 -> +0.67 (n=540), prior=1 -> +10.17 (n=537), prior=2 -> +4.67 (n=515), prior=3 -> -0.61 (n=470), prior=4 -> +3.04 (n=363), prior=5 -> +4.04 (n=213), prior=6 -> +2.29 (n=84), prior=7 -> -0.44 (n=25)
- **CARROT**: prior=0 -> +2.19 (n=484), prior=1 -> +6.90 (n=338), prior=2 -> +9.04 (n=179), prior=3 -> +9.33 (n=46), prior=4 -> +8.10 (n=10), prior=5 -> +17.00 (n=2)
- **WOOL**: prior=0 -> +3.17 (n=342), prior=1 -> +2.93 (n=141), prior=2 -> +1.30 (n=33), prior=3 -> +0.88 (n=8), prior=4 -> +0.00 (n=1)
- **EGG**: prior=0 -> +0.88 (n=494), prior=1 -> +1.11 (n=348), prior=2 -> +0.18 (n=187), prior=3 -> -0.05 (n=57), prior=4 -> -0.07 (n=14), prior=5 -> +0.00 (n=4)
- **MILK**: prior=0 -> +1.58 (n=525), prior=1 -> +2.16 (n=469), prior=2 -> +0.54 (n=347), prior=3 -> -0.05 (n=184), prior=4 -> -0.09 (n=77), prior=5 -> -0.18 (n=22), prior=6 -> +0.00 (n=8)

## Q4: late game

| crop | last planted mean/median/max | never (n) | if day-24 shop demands it | if not |
|---|---:|---:|---:|---:|
| STRAWBERRY | 14.01/15.0/21 | 0 | 13.98 (n=269) | 14.04 (n=271) |
| MELON | 1.69/1.0/15 | 0 | - (n=0) | 1.69 (n=540) |
| TOMATO | 19.04/19/27 | 143 | 18.77 (n=97) | 19.13 (n=300) |
| WHEAT | 26.94/27.0/29 | 0 | 26.94 (n=344) | 26.94 (n=196) |
| CARROT | 26.65/27/29 | 5 | 26.78 (n=121) | 26.62 (n=414) |

| animal | last purchase mean/median/max | never (n) | if day-24 shop demands it | if not |
|---|---:|---:|---:|---:|
| WOOL/SHEEP | 7.24/8.0/21 | 0 | 7.74 (n=65) | 7.18 (n=475) |
| EGG/GOOSE | 10.69/11.0/11 | 104 | 10.6 (n=117) | 10.72 (n=319) |
| MILK/COW (ambiguous, see caveat) | 9.19/9.0/21 | 0 | 9.19 (n=210) | 9.19 (n=330) |

## Q5: land (quadrant unlock day; fixed engine order NE(1000) -> SW(2000) -> SE(4000))

| quadrant | n purchased / never | mean/median day | min-max | on a reveal day | day after reveal |
|---|---:|---:|---:|---:|---:|
| NE | 540/0 | 6.86/7.0 | 6-7 | 0.139 | 0.861 |
| SW | 540/0 | 9.8/10.0 | 9-10 | 0.196 | 0.804 |
| SE | 355/185 | 11.01/11 | 11-12 | 0.011 | 0.0 |