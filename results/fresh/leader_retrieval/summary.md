# Leader-plan retrieval (gate G2) - results summary

240 games (6 teams x 40), decision days (3, 6, 9, 12, 15, 18, 21), horizons +(3, 6).

Self-check (numpy batch vs pure-python `retrieve_games()`): 0/30 mismatches.


## Best retrieval setting per (decision day, horizon)

| day | horizon | protocol | k | lambda | n | tile-Hamming mean | composition MAE | frac <=8 tiles |
|---|---|---|---|---|---|---|---|---|
| 3 | +3 | logo | 1 | 1.00 | 240 | 1.03 | 0.077 | 0.992 |
| 3 | +6 | logo | 5 | 0.50 | 240 | 10.58 | 1.386 | 0.512 |
| 6 | +3 | logo | 5 | 1.00 | 240 | 6.73 | 0.583 | 0.771 |
| 6 | +6 | logo | 5 | 1.00 | 240 | 21.93 | 2.062 | 0.033 |
| 9 | +3 | logo | 5 | 1.00 | 240 | 19.36 | 1.701 | 0.067 |
| 9 | +6 | family_logo | 3 | 1.00 | 240 | 24.68 | 2.141 | 0.021 |
| 12 | +3 | logo | 3 | 1.00 | 240 | 21.17 | 1.627 | 0.029 |
| 12 | +6 | family_logo | 5 | 0.50 | 240 | 23.24 | 1.848 | 0.013 |
| 15 | +3 | logo | 5 | 1.00 | 240 | 22.07 | 1.814 | 0.021 |
| 15 | +6 | family_logo | 5 | 0.50 | 240 | 28.26 | 2.154 | 0.004 |
| 18 | +3 | logo | 5 | 1.00 | 240 | 26.67 | 2.103 | 0.000 |
| 18 | +6 | logo | 5 | 1.00 | 240 | 31.90 | 2.417 | 0.004 |
| 21 | +3 | logo | 5 | 1.00 | 240 | 31.91 | 2.361 | 0.008 |
| 21 | +6 | logo | 5 | 1.00 | 240 | 35.19 | 2.601 | 0.000 |

## Baselines

| day | horizon | baseline | tile-Hamming mean | composition MAE | frac <=8 tiles |
|---|---|---|---|---|---|
| 3 | +3 | persistence | 9.36 | 1.562 | 0.871 |
| 3 | +3 | corpus_mode | 7.45 | 0.855 | 0.667 |
| 3 | +6 | persistence | 37.51 | 5.886 | 0.000 |
| 3 | +6 | corpus_mode | 26.03 | 3.211 | 0.096 |
| 6 | +3 | persistence | 30.56 | 5.393 | 0.000 |
| 6 | +3 | corpus_mode | 26.03 | 3.211 | 0.096 |
| 6 | +6 | persistence | 73.67 | 13.184 | 0.000 |
| 6 | +6 | corpus_mode | 46.26 | 4.561 | 0.000 |
| 9 | +3 | persistence | 46.88 | 8.176 | 0.000 |
| 9 | +3 | corpus_mode | 46.26 | 4.561 | 0.000 |
| 9 | +6 | persistence | 49.81 | 8.368 | 0.000 |
| 9 | +6 | corpus_mode | 50.08 | 4.807 | 0.000 |
| 12 | +3 | persistence | 15.95 | 1.970 | 0.158 |
| 12 | +3 | corpus_mode | 50.08 | 4.807 | 0.000 |
| 12 | +6 | persistence | 22.39 | 2.994 | 0.054 |
| 12 | +6 | corpus_mode | 54.25 | 5.596 | 0.000 |
| 15 | +3 | persistence | 11.50 | 1.431 | 0.296 |
| 15 | +3 | corpus_mode | 54.25 | 5.596 | 0.000 |
| 15 | +6 | persistence | 24.18 | 2.474 | 0.037 |
| 15 | +6 | corpus_mode | 56.82 | 5.330 | 0.000 |
| 18 | +3 | persistence | 17.58 | 2.098 | 0.054 |
| 18 | +3 | corpus_mode | 56.82 | 5.330 | 0.000 |
| 18 | +6 | persistence | 32.98 | 4.182 | 0.000 |
| 18 | +6 | corpus_mode | 59.43 | 5.607 | 0.000 |
| 21 | +3 | persistence | 23.77 | 2.829 | 0.017 |
| 21 | +3 | corpus_mode | 59.43 | 5.607 | 0.000 |
| 21 | +6 | persistence | 36.60 | 4.455 | 0.000 |
| 21 | +6 | corpus_mode | 57.77 | 5.331 | 0.000 |

## Ridge regression (composition counts, LOGO, best alpha from {0.1,1,5,10,30})

| day | horizon | alpha | composition MAE |
|---|---|---|---|
| 3 | +3 | 1.0 | 0.670 |
| 3 | +6 | 5.0 | 1.740 |
| 6 | +3 | 5.0 | 1.191 |
| 6 | +6 | 5.0 | 2.186 |
| 9 | +3 | 5.0 | 2.001 |
| 9 | +6 | 0.1 | 2.309 |
| 12 | +3 | 1.0 | 1.044 |
| 12 | +6 | 10.0 | 1.435 |
| 15 | +3 | 10.0 | 1.002 |
| 15 | +6 | 10.0 | 1.425 |
| 18 | +3 | 30.0 | 1.229 |
| 18 | +6 | 30.0 | 1.867 |
| 21 | +3 | 30.0 | 1.709 |
| 21 | +6 | 5.0 | 1.895 |

## Protocol comparison at the best k/lambda-per-protocol (composition MAE, horizon +3)

| day | logo | loto | family_logo |
|---|---|---|---|
| 3 | 0.077 | 0.872 | 0.077 |
| 6 | 0.567 | 1.553 | 0.509 |
| 9 | 1.685 | 2.672 | 1.686 |
| 12 | 1.525 | 1.979 | 1.534 |
| 15 | 1.771 | 2.211 | 1.791 |
| 18 | 2.103 | 2.360 | 2.112 |
| 21 | 2.361 | 2.854 | 2.370 |
