# Leader reveal-response rules (600 games, 6 teams)

Corpus: `data/leader_semantics/<team>/<episode>.json.gz`. See `scripts/leader_reveal_response.py` module docstring for the day-shift correction and the 'co' (cow vs empty coop) label ambiguity.

## Q1: units per shop revealed (excess holdings change vs. a non-demanding shop revealed on the same day)

### STRAWBERRY

| reveal day | n demand / n not | +units @3d | +units @6d |
|---:|---:|---:|---:|
| 3 | 295/305 | +0.33 | +6.53 |
| 6 | 298/302 | +6.38 | +8.24 |
| 9 | 333/267 | +6.44 | +7.30 |
| 12 | 296/304 | +5.80 | +6.30 |
| 15 | 296/304 | +3.87 | +4.03 |
| 18 | 287/313 | +0.54 | +0.40 |
| 21 | 313/287 | +0.26 | +0.21 |
| 24 | 299/301 | +0.80 | +0.92 |

Pooled cluster-robust OLS (delta ~ demanded + day + current holdings), n=4800 events / 600 games: demanded coef @3d = +3.12 (se 0.14), @6d = +4.46 (se 0.21).

Per-team pooled excess @3d: Boey=+0.8, DECEM=+3.6, DSM=+3.8, M & M & P & Q=+3.5, Unknown Mother-Goose=+3.5, Vadim Vasilenko=+3.6

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

Pooled cluster-robust OLS (delta ~ demanded + day + current holdings), n=4800 events / 600 games: demanded coef @3d = +0.00 (se 0.00), @6d = +0.00 (se 0.00).

### TOMATO

| reveal day | n demand / n not | +units @3d | +units @6d |
|---:|---:|---:|---:|
| 3 | 150/450 | +0.00 | +0.07 |
| 6 | 136/464 | +0.03 | +1.53 |
| 9 | 169/431 | +2.17 | +4.29 |
| 12 | 136/464 | +1.84 | +2.83 |
| 15 | 140/460 | +1.68 | +2.17 |
| 18 | 184/416 | +0.89 | +0.13 |
| 21 | 155/445 | +0.50 | +0.87 |
| 24 | 153/447 | +0.36 | +0.24 |

Pooled cluster-robust OLS (delta ~ demanded + day + current holdings), n=4800 events / 600 games: demanded coef @3d = +0.99 (se 0.13), @6d = +1.41 (se 0.20).

Per-team pooled excess @3d: Boey=+0.1, DECEM=+1.8, DSM=+1.5, M & M & P & Q=+0.0, Unknown Mother-Goose=+1.0, Vadim Vasilenko=+1.3

### WHEAT

| reveal day | n demand / n not | +units @3d | +units @6d |
|---:|---:|---:|---:|
| 3 | 380/220 | +0.36 | +1.99 |
| 6 | 357/243 | -0.16 | +1.80 |
| 9 | 400/200 | +2.50 | +2.29 |
| 12 | 395/205 | +1.28 | +1.44 |
| 15 | 365/235 | +0.39 | +1.18 |
| 18 | 382/218 | +1.17 | +1.21 |
| 21 | 392/208 | +1.45 | +2.15 |
| 24 | 380/220 | +2.77 | +0.32 |

Pooled cluster-robust OLS (delta ~ demanded + day + current holdings), n=4800 events / 600 games: demanded coef @3d = +1.53 (se 0.26), @6d = +1.49 (se 0.31).

Per-team pooled excess @3d: Boey=+0.4, DECEM=+1.2, DSM=+2.5, M & M & P & Q=+1.5, Unknown Mother-Goose=+2.3, Vadim Vasilenko=+0.5

### CARROT

| reveal day | n demand / n not | +units @3d | +units @6d |
|---:|---:|---:|---:|
| 3 | 130/470 | +0.00 | +0.61 |
| 6 | 150/450 | +0.53 | +5.02 |
| 9 | 160/440 | +3.48 | +4.30 |
| 12 | 138/462 | +3.52 | +4.10 |
| 15 | 169/431 | +3.93 | +5.91 |
| 18 | 152/448 | +3.77 | +5.09 |
| 21 | 144/456 | +5.58 | +6.74 |
| 24 | 135/465 | +4.13 | +1.26 |

Pooled cluster-robust OLS (delta ~ demanded + day + current holdings), n=4800 events / 600 games: demanded coef @3d = +3.02 (se 0.20), @6d = +4.15 (se 0.30).

Per-team pooled excess @3d: Boey=+1.2, DECEM=+4.0, DSM=+2.8, M & M & P & Q=+5.4, Unknown Mother-Goose=+2.0, Vadim Vasilenko=+3.3

### WOOL

| reveal day | n demand / n not | +units @3d | +units @6d |
|---:|---:|---:|---:|
| 3 | 82/518 | +0.69 | +6.70 |
| 6 | 86/514 | +5.63 | +6.32 |
| 9 | 61/539 | +5.60 | +6.46 |
| 12 | 70/530 | +3.87 | +4.50 |
| 15 | 72/528 | +2.34 | +3.03 |
| 18 | 74/526 | +1.46 | +2.32 |
| 21 | 62/538 | +0.99 | +2.06 |
| 24 | 75/525 | +0.75 | +0.66 |

Pooled cluster-robust OLS (delta ~ demanded + day + current holdings), n=4800 events / 600 games: demanded coef @3d = +2.67 (se 0.13), @6d = +4.06 (se 0.15).

Per-team pooled excess @3d: Boey=+1.4, DECEM=+3.2, DSM=+2.5, M & M & P & Q=+3.0, Unknown Mother-Goose=+2.7, Vadim Vasilenko=+3.4

### EGG

| reveal day | n demand / n not | +units @3d | +units @6d |
|---:|---:|---:|---:|
| 3 | 154/446 | +0.04 | +1.27 |
| 6 | 143/457 | +1.11 | +1.93 |
| 9 | 139/461 | +1.13 | +1.13 |
| 12 | 183/417 | -0.01 | +0.00 |
| 15 | 151/449 | -0.01 | -0.02 |
| 18 | 138/462 | +0.04 | +0.08 |
| 21 | 153/447 | +0.10 | +0.12 |
| 24 | 158/442 | +0.04 | +0.12 |

Pooled cluster-robust OLS (delta ~ demanded + day + current holdings), n=4800 events / 600 games: demanded coef @3d = +0.24 (se 0.06), @6d = +0.49 (se 0.08).

Per-team pooled excess @3d: Boey=+0.2, DECEM=+0.1, DSM=+0.4, M & M & P & Q=+0.0, Unknown Mother-Goose=+0.3, Vadim Vasilenko=+0.4

### MILK

| reveal day | n demand / n not | +units @3d | +units @6d |
|---:|---:|---:|---:|
| 3 | 234/366 | +0.26 | +3.35 |
| 6 | 221/379 | +2.83 | +3.50 |
| 9 | 240/360 | +1.81 | +2.03 |
| 12 | 209/391 | +0.48 | +0.72 |
| 15 | 208/392 | +0.24 | +0.67 |
| 18 | 236/364 | +0.40 | +0.90 |
| 21 | 241/359 | +0.52 | +0.90 |
| 24 | 232/368 | +0.58 | +1.31 |

Pooled cluster-robust OLS (delta ~ demanded + day + current holdings), n=4800 events / 600 games: demanded coef @3d = +0.88 (se 0.06), @6d = +1.67 (se 0.08).

Per-team pooled excess @3d: Boey=+0.6, DECEM=+1.1, DSM=+1.0, M & M & P & Q=+0.9, Unknown Mother-Goose=+0.8, Vadim Vasilenko=+0.9


## Q2: timing of first commitment relative to reveal (window r-3..r+9)

| product | n obs | n censored | mean delay | median | p25 | p75 | anticip. | same-day | lag |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| STRAWBERRY | 1694 | 723 | -2.22 | -3.0 | -3 | -1 | 90% | 8% | 2% |
| MELON | 0 | 0 | - | - | - | - | - | - | - |
| TOMATO | 831 | 392 | 0.01 | -1 | -3 | 3 | 52% | 17% | 31% |
| WHEAT | 3051 | 0 | -2.64 | -3 | -3 | -3 | 91% | 9% | 0% |
| CARROT | 1070 | 108 | 0.93 | 0.0 | -3 | 4 | 43% | 8% | 49% |
| WOOL | 431 | 151 | -1.0 | 0 | -2 | 0 | 44% | 54% | 2% |
| EGG | 519 | 700 | 0.16 | 0 | -3 | 3 | 42% | 26% | 32% |
| MILK | 949 | 872 | -1.96 | -2 | -3 | -1 | 78% | 21% | 2% |

## Q3: saturation (mean +units@3d among demanded events, by count of already-revealed shops also demanding the product)

- **STRAWBERRY**: prior=0 -> +7.00 (n=596), prior=1 -> +7.05 (n=581), prior=2 -> +1.49 (n=517), prior=3 -> -3.78 (n=387), prior=4 -> -6.82 (n=223), prior=5 -> -8.18 (n=88), prior=6 -> -6.83 (n=24), prior=7 -> -8.00 (n=1)
- **TOMATO**: prior=0 -> +1.20 (n=547), prior=1 -> +2.23 (n=399), prior=2 -> +1.41 (n=184), prior=3 -> -1.99 (n=70), prior=4 -> -5.79 (n=19), prior=5 -> -3.25 (n=4)
- **WHEAT**: prior=0 -> +0.36 (n=600), prior=1 -> +9.45 (n=597), prior=2 -> +4.36 (n=574), prior=3 -> -0.30 (n=520), prior=4 -> +3.06 (n=404), prior=5 -> +4.04 (n=238), prior=6 -> +2.45 (n=93), prior=7 -> -0.44 (n=25)
- **CARROT**: prior=0 -> +2.01 (n=542), prior=1 -> +6.23 (n=376), prior=2 -> +8.28 (n=195), prior=3 -> +8.17 (n=52), prior=4 -> +7.46 (n=11), prior=5 -> +17.00 (n=2)
- **WOOL**: prior=0 -> +2.94 (n=381), prior=1 -> +2.69 (n=156), prior=2 -> +1.28 (n=36), prior=3 -> +0.88 (n=8), prior=4 -> +0.00 (n=1)
- **EGG**: prior=0 -> +0.80 (n=549), prior=1 -> +1.02 (n=390), prior=2 -> +0.17 (n=202), prior=3 -> -0.05 (n=60), prior=4 -> -0.07 (n=14), prior=5 -> +0.00 (n=4)
- **MILK**: prior=0 -> +1.50 (n=584), prior=1 -> +1.98 (n=524), prior=2 -> +0.49 (n=387), prior=3 -> -0.06 (n=208), prior=4 -> -0.13 (n=86), prior=5 -> -0.21 (n=24), prior=6 -> +0.00 (n=8)

## Q4: late game

| crop | last planted mean/median/max | never (n) | if day-24 shop demands it | if not |
|---|---:|---:|---:|---:|
| STRAWBERRY | 14.31/15.0/21 | 0 | 14.28 (n=299) | 14.34 (n=301) |
| MELON | 3.42/1.0/19 | 0 | - (n=0) | 3.42 (n=600) |
| TOMATO | 19.17/19/27 | 143 | 18.95 (n=113) | 19.24 (n=344) |
| WHEAT | 26.95/27.0/29 | 0 | 26.94 (n=380) | 26.95 (n=220) |
| CARROT | 26.38/27/29 | 5 | 26.51 (n=134) | 26.35 (n=461) |

| animal | last purchase mean/median/max | never (n) | if day-24 shop demands it | if not |
|---|---:|---:|---:|---:|
| WOOL/SHEEP | 8.82/8.0/23 | 0 | 9.77 (n=75) | 8.68 (n=525) |
| EGG/GOOSE | 10.85/11.0/12 | 104 | 10.76 (n=132) | 10.88 (n=364) |
| MILK/COW (ambiguous, see caveat) | 9.67/9.0/21 | 0 | 9.65 (n=232) | 9.69 (n=368) |

## Q5: land (quadrant unlock day; fixed engine order NE(1000) -> SW(2000) -> SE(4000))

| quadrant | n purchased / never | mean/median day | min-max | on a reveal day | day after reveal |
|---|---:|---:|---:|---:|---:|
| NE | 600/0 | 6.88/7.0 | 6-7 | 0.125 | 0.875 |
| SW | 552/48 | 9.81/10.0 | 9-10 | 0.192 | 0.808 |
| SE | 355/245 | 11.01/11 | 11-12 | 0.011 | 0.0 |