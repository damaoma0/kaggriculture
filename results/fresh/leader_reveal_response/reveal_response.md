# Leader reveal-response rules (263 games, 6 teams)

Corpus: `data/leader_semantics/<team>/<episode>.json.gz`. See `scripts/leader_reveal_response.py` module docstring for the day-shift correction and the 'co' (cow vs empty coop) label ambiguity.

## Q1: units per shop revealed (excess holdings change vs. a non-demanding shop revealed on the same day)

### STRAWBERRY

| reveal day | n demand / n not | +units @3d | +units @6d |
|---:|---:|---:|---:|
| 3 | 126/137 | +0.35 | +7.33 |
| 6 | 115/148 | +7.56 | +8.72 |
| 9 | 151/112 | +6.33 | +7.61 |
| 12 | 124/139 | +5.44 | +5.53 |
| 15 | 127/136 | +3.36 | +3.82 |
| 18 | 127/136 | +0.61 | +0.36 |
| 21 | 135/128 | +0.36 | -0.24 |
| 24 | 141/122 | +0.24 | +0.29 |

Pooled cluster-robust OLS (delta ~ demanded + day + current holdings), n=2104 events / 263 games: demanded coef @3d = +3.04 (se 0.21), @6d = +4.36 (se 0.32).

Per-team pooled excess @3d: Boey=+1.0, DECEM=+3.4, DSM=+3.5, M & M & P & Q=+3.0, Unknown Mother-Goose=+3.2, Vadim Vasilenko=+3.5

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

Pooled cluster-robust OLS (delta ~ demanded + day + current holdings), n=2104 events / 263 games: demanded coef @3d = -0.00 (se 0.00), @6d = -0.00 (se 0.00).

### TOMATO

| reveal day | n demand / n not | +units @3d | +units @6d |
|---:|---:|---:|---:|
| 3 | 61/202 | +0.00 | +0.03 |
| 6 | 65/198 | +0.01 | +0.77 |
| 9 | 70/193 | +1.59 | +3.29 |
| 12 | 63/200 | +1.69 | +2.66 |
| 15 | 68/195 | +1.68 | +2.10 |
| 18 | 79/184 | +1.23 | +0.24 |
| 21 | 70/193 | +1.03 | +1.75 |
| 24 | 67/196 | +0.05 | -0.25 |

Pooled cluster-robust OLS (delta ~ demanded + day + current holdings), n=2104 events / 263 games: demanded coef @3d = +0.99 (se 0.18), @6d = +1.34 (se 0.28).

Per-team pooled excess @3d: Boey=+0.0, DECEM=+1.6, DSM=+1.9, M & M & P & Q=+0.0, Unknown Mother-Goose=+1.3, Vadim Vasilenko=+1.0

### WHEAT

| reveal day | n demand / n not | +units @3d | +units @6d |
|---:|---:|---:|---:|
| 3 | 160/103 | +0.47 | +2.12 |
| 6 | 154/109 | +0.72 | +2.08 |
| 9 | 188/75 | +1.16 | +2.09 |
| 12 | 167/96 | +1.39 | +1.41 |
| 15 | 163/100 | +1.04 | +0.91 |
| 18 | 170/93 | +0.70 | +1.24 |
| 21 | 176/87 | +1.46 | +1.53 |
| 24 | 165/98 | +3.69 | +1.31 |

Pooled cluster-robust OLS (delta ~ demanded + day + current holdings), n=2104 events / 263 games: demanded coef @3d = +2.02 (se 0.37), @6d = +1.64 (se 0.45).

Per-team pooled excess @3d: Boey=+0.6, DECEM=+1.8, DSM=+4.2, M & M & P & Q=+1.3, Unknown Mother-Goose=+3.8, Vadim Vasilenko=+1.4

### CARROT

| reveal day | n demand / n not | +units @3d | +units @6d |
|---:|---:|---:|---:|
| 3 | 63/200 | +0.00 | +0.86 |
| 6 | 72/191 | +0.73 | +4.89 |
| 9 | 59/204 | +4.60 | +5.26 |
| 12 | 69/194 | +3.31 | +3.91 |
| 15 | 74/189 | +4.40 | +5.97 |
| 18 | 70/193 | +4.39 | +6.28 |
| 21 | 63/200 | +5.33 | +6.72 |
| 24 | 61/202 | +5.66 | +2.09 |

Pooled cluster-robust OLS (delta ~ demanded + day + current holdings), n=2104 events / 263 games: demanded coef @3d = +3.37 (se 0.31), @6d = +4.45 (se 0.45).

Per-team pooled excess @3d: Boey=+2.1, DECEM=+4.7, DSM=+3.3, M & M & P & Q=+5.0, Unknown Mother-Goose=+2.5, Vadim Vasilenko=+3.5

### WOOL

| reveal day | n demand / n not | +units @3d | +units @6d |
|---:|---:|---:|---:|
| 3 | 33/230 | +0.91 | +7.32 |
| 6 | 40/223 | +6.25 | +6.55 |
| 9 | 27/236 | +5.82 | +6.75 |
| 12 | 30/233 | +4.03 | +4.25 |
| 15 | 28/235 | +2.23 | +2.65 |
| 18 | 31/232 | +1.06 | +2.01 |
| 21 | 32/231 | +1.22 | +2.22 |
| 24 | 29/234 | +0.78 | +0.66 |

Pooled cluster-robust OLS (delta ~ demanded + day + current holdings), n=2104 events / 263 games: demanded coef @3d = +2.88 (se 0.18), @6d = +4.15 (se 0.22).

Per-team pooled excess @3d: Boey=+2.4, DECEM=+3.0, DSM=+2.1, M & M & P & Q=+4.0, Unknown Mother-Goose=+2.9, Vadim Vasilenko=+3.4

### EGG

| reveal day | n demand / n not | +units @3d | +units @6d |
|---:|---:|---:|---:|
| 3 | 69/194 | +0.10 | +1.49 |
| 6 | 66/197 | +1.32 | +2.58 |
| 9 | 80/183 | +1.28 | +1.25 |
| 12 | 75/188 | +0.02 | +0.05 |
| 15 | 66/197 | +0.01 | +0.04 |
| 18 | 72/191 | +0.07 | +0.02 |
| 21 | 71/192 | +0.20 | +0.32 |
| 24 | 64/199 | +0.06 | +0.31 |

Pooled cluster-robust OLS (delta ~ demanded + day + current holdings), n=2104 events / 263 games: demanded coef @3d = +0.43 (se 0.09), @6d = +0.72 (se 0.12).

Per-team pooled excess @3d: Boey=+0.3, DECEM=+0.3, DSM=+0.7, M & M & P & Q=+0.0, Unknown Mother-Goose=+0.8, Vadim Vasilenko=+0.8

### MILK

| reveal day | n demand / n not | +units @3d | +units @6d |
|---:|---:|---:|---:|
| 3 | 98/165 | +0.53 | +3.42 |
| 6 | 85/178 | +2.54 | +3.10 |
| 9 | 97/166 | +1.90 | +2.17 |
| 12 | 89/174 | +0.37 | +0.66 |
| 15 | 95/168 | +0.31 | +0.73 |
| 18 | 90/173 | +0.45 | +0.97 |
| 21 | 97/166 | +0.45 | +0.84 |
| 24 | 109/154 | +0.53 | +1.23 |

Pooled cluster-robust OLS (delta ~ demanded + day + current holdings), n=2104 events / 263 games: demanded coef @3d = +0.82 (se 0.08), @6d = +1.61 (se 0.11).

Per-team pooled excess @3d: Boey=+0.8, DECEM=+0.9, DSM=+0.8, M & M & P & Q=+1.2, Unknown Mother-Goose=+0.6, Vadim Vasilenko=+0.4


## Q2: timing of first commitment relative to reveal (window r-3..r+9)

| product | n obs | n censored | mean delay | median | p25 | p75 | anticip. | same-day | lag |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| STRAWBERRY | 711 | 335 | -2.16 | -3 | -3 | -1 | 87% | 10% | 3% |
| MELON | 0 | 0 | - | - | - | - | - | - | - |
| TOMATO | 333 | 210 | -0.17 | -2 | -3 | 3 | 55% | 15% | 30% |
| WHEAT | 1343 | 0 | -2.66 | -3 | -3 | -3 | 91% | 9% | 0% |
| CARROT | 487 | 44 | 0.85 | 0 | -3 | 4 | 44% | 9% | 47% |
| WOOL | 182 | 68 | -0.9 | 0.0 | -2 | 0 | 40% | 58% | 2% |
| EGG | 253 | 310 | -0.1 | 0 | -3 | 3 | 45% | 28% | 28% |
| MILK | 392 | 368 | -2.02 | -3.0 | -3 | -2 | 79% | 19% | 2% |

## Q3: saturation (mean +units@3d among demanded events, by count of already-revealed shops also demanding the product)

- **STRAWBERRY**: prior=0 -> +6.86 (n=261), prior=1 -> +6.71 (n=254), prior=2 -> +0.95 (n=224), prior=3 -> -4.31 (n=166), prior=4 -> -6.57 (n=92), prior=5 -> -8.35 (n=37), prior=6 -> -7.18 (n=11), prior=7 -> -8.00 (n=1)
- **TOMATO**: prior=0 -> +1.11 (n=244), prior=1 -> +2.06 (n=176), prior=2 -> +1.74 (n=80), prior=3 -> -2.12 (n=34), prior=4 -> -5.50 (n=8), prior=5 -> -6.00 (n=1)
- **WHEAT**: prior=0 -> +0.92 (n=263), prior=1 -> +9.05 (n=262), prior=2 -> +4.96 (n=253), prior=3 -> -0.06 (n=232), prior=4 -> +3.49 (n=178), prior=5 -> +3.29 (n=101), prior=6 -> +3.67 (n=40), prior=7 -> -0.21 (n=14)
- **CARROT**: prior=0 -> +1.93 (n=237), prior=1 -> +6.62 (n=169), prior=2 -> +8.06 (n=86), prior=3 -> +9.79 (n=28), prior=4 -> +8.11 (n=9), prior=5 -> +17.00 (n=2)
- **WOOL**: prior=0 -> +3.17 (n=170), prior=1 -> +2.67 (n=64), prior=2 -> +1.46 (n=13), prior=3 -> +1.00 (n=2), prior=4 -> +0.00 (n=1)
- **EGG**: prior=0 -> +0.98 (n=238), prior=1 -> +1.34 (n=182), prior=2 -> +0.38 (n=101), prior=3 -> +0.00 (n=31), prior=4 -> +0.00 (n=8), prior=5 -> +0.00 (n=3)
- **MILK**: prior=0 -> +1.43 (n=254), prior=1 -> +1.71 (n=221), prior=2 -> +0.39 (n=161), prior=3 -> +0.02 (n=86), prior=4 -> -0.10 (n=29), prior=5 -> +0.00 (n=7), prior=6 -> +0.00 (n=2)

## Q4: late game

| crop | last planted mean/median/max | never (n) | if day-24 shop demands it | if not |
|---|---:|---:|---:|---:|
| STRAWBERRY | 14.14/15/19 | 0 | 14.1 (n=141) | 14.18 (n=122) |
| MELON | 3.67/1/19 | 0 | - (n=0) | 3.67 (n=263) |
| TOMATO | 19.12/19/27 | 82 | 18.73 (n=48) | 19.26 (n=133) |
| WHEAT | 26.77/27/29 | 0 | 26.74 (n=165) | 26.82 (n=98) |
| CARROT | 26.35/27.0/28 | 1 | 26.53 (n=60) | 26.3 (n=202) |

| animal | last purchase mean/median/max | never (n) | if day-24 shop demands it | if not |
|---|---:|---:|---:|---:|
| WOOL/SHEEP | 8.47/8/23 | 0 | 9.21 (n=29) | 8.38 (n=234) |
| EGG/GOOSE | 10.51/11/12 | 40 | 10.15 (n=52) | 10.61 (n=171) |
| MILK/COW (ambiguous, see caveat) | 9.46/9/21 | 0 | 9.43 (n=109) | 9.47 (n=154) |

## Q5: land (quadrant unlock day; fixed engine order NE(1000) -> SW(2000) -> SE(4000))

| quadrant | n purchased / never | mean/median day | min-max | on a reveal day | day after reveal |
|---|---:|---:|---:|---:|---:|
| NE | 263/0 | 6.89/7 | 6-7 | 0.106 | 0.894 |
| SW | 246/17 | 9.76/10.0 | 9-10 | 0.236 | 0.764 |
| SE | 141/122 | 11.02/11 | 11-12 | 0.021 | 0.0 |