# Random-world m1 versus v56 benchmark

Completed 22 September 2026. Current deployed m1 versus frozen V56; the new production-plan continuation is not integrated in this build.

128 fresh random seeds, both seats, natural shops and weeds. Source files and the complete seed list were frozen before play; no outcome-based selection or stopping. Both agents played live through the official Kaggle engine.

Completed rows: **256** / **256**; failures: **0**.

Overall W/T/L: **177/0/79**; mean margin **+2,744**; median **+3,028**.
Mean-margin 95% CI: **+1,519 to +3,974**. Win score: **69.1%**; seed-clustered 95% CI: **61.3%–77.0%**.

## First ordered-prefix break

| Bucket | n | W/T/L | Mean margin | Cluster 95% CI |
|---|---:|---:|---:|---:|
| <=D9 | 76 | 57/0/19 | +3,347 | +940 to +5,762 |
| D12 | 146 | 98/0/48 | +2,423 | +830 to +4,006 |
| D15+ | 34 | 22/0/12 | +2,775 | -671 to +5,995 |
| never | 0 | 0/0/0 | — | — |

## First shop

| Group | Games | Seed clusters | W / D / L | Win score | 95% score CI | Mean margin |
|---|---:|---:|---:|---:|---:|---:|
| BAKERY | 36 | 18 | 32 / 0 / 4 | 88.9% | 72.2%–100.0% | +3,986 |
| BRUNCH_SPOT | 38 | 19 | 23 / 0 / 15 | 60.5% | 39.5%–81.6% | +1,432 |
| FARMERS_MARKET | 32 | 16 | 22 / 0 / 10 | 68.8% | 43.8%–87.5% | +3,279 |
| ICE_CREAM_SHOP | 36 | 18 | 26 / 0 / 10 | 72.2% | 50.0%–88.9% | +2,523 |
| PET_CAFE | 22 | 11 | 18 / 0 / 4 | 81.8% | 54.5%–100.0% | +5,259 |
| PIZZA_SHOP | 20 | 10 | 10 / 0 / 10 | 50.0% | 20.0%–80.0% | +27 |
| SMOOTHIE_SHOP | 36 | 18 | 22 / 0 / 14 | 61.1% | 38.9%–83.3% | +1,820 |
| YARN_STORE | 36 | 18 | 24 / 0 / 12 | 66.7% | 44.4%–86.1% | +3,531 |

## UMG tape availability at day 12

| Group | Games | Seed clusters | W / D / L | Win score | 95% score CI | Mean margin |
|---|---:|---:|---:|---:|---:|---:|
| order_only | 183 | 92 | 125 / 0 / 58 | 68.3% | 58.7%–77.6% | +2,212 |
| novel_composition | 39 | 20 | 30 / 0 / 9 | 76.9% | 56.4%–94.7% | +5,216 |
| ordered_match | 34 | 17 | 22 / 0 / 12 | 64.7% | 44.1%–85.3% | +2,775 |

Combining both missing-prefix groups: **155 wins / 67 losses in 222 games** (111 seed clusters), **69.8%** win score, 95% CI **61.3%–77.9%**.

## Seat

| Group | Games | Seed clusters | W / D / L | Win score | 95% score CI | Mean margin |
|---|---:|---:|---:|---:|---:|---:|
| 0 | 128 | 128 | 90 / 0 / 38 | 70.3% | 62.5%–78.1% | +2,855 |
| 1 | 128 | 128 | 87 / 0 / 41 | 68.0% | 60.2%–75.8% | +2,633 |

## Tape coverage

| Shops revealed | Day | Exact order: games covered | Same composition: games covered |
|---:|---:|---:|---:|
| 1 | 3 | 256 / 256 | 256 / 256 |
| 2 | 6 | 256 / 256 | 256 / 256 |
| 3 | 9 | 180 / 256 | 254 / 256 |
| 4 | 12 | 34 / 256 | 217 / 256 |
| 5 | 15 | 5 / 256 | 159 / 256 |
| 6 | 18 | 3 / 256 | 103 / 256 |
| 7 | 21 | 1 / 256 | 74 / 256 |
| 8 | 24 | 0 / 256 | 46 / 256 |

## Interpretation and validation

Win-score uncertainty uses 128 seed clusters, not 256 independent observations. Exactly 104 seed pairs had identical final margins; 112 had identical shop sequences. Normal farm-dependent weed RNG can change later shops between seats.

Average final cash: m1 109,005.0; V56 106,260.6. All recorded ledgers were checked for both seats. Validation errors: 0. Agent calls above one second: 0; maximum measured call 0.3362s. Captured SHP internal errors: 0.

The main 95% intervals use 20,000 bootstrap resamples of whole seeds. Subgroup intervals are descriptive, unadjusted for multiple comparisons, and can be wide with few worlds. A matching shop prefix does not ensure matching farm state; missing a prefix does not isolate the causal effect of fallback. Exact ordered match, order-only mismatch, and novel composition are classified against the 584 tapes actually embedded in m1; all episode IDs and shop paths were verified against the compact corpus.

This tests current m1 against a single frozen live opponent. It does not test the unfinished continuation, compare with original UMG tapes, or complete the full promotion protocol. Against the assumed 2750-rated opponent, the previously derived standard-Elo planning target is 80.8%; this run is reported without claiming a Kaggle rating.

The frozen manifest, per-game ledgers, timing, source hashes, embedded-tape audit, complete subgroup statistics, and retained failure records are in `results/fresh/v56_random_20260922/`. Top-level exceptions and SHP error counters are captured; other internally caught router errors were not instrumented.
