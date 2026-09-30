# Qualification v5 mechanical audit

All 256 records completed: 32 fixed worlds × 2 opponents × 4 arms. Records pair exactly on `(spec.id, opponent)`; every key has one record per arm. All records have `ledger_verified == [true, true]`.

| Arm | N | Mean own cash | Mean rival margin | Early failed hires total / games | Later failed hires total / games | D3 strawberry / melon | D6 strawberry / melon | Mean game max action (s) | Worst game max (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 64 | $108,959 | $+844 | 0 / 0 | 0 / 0 | 0.00 / 12.00 | 4.00 / 12.00 | 0.450 | 2.275 |
| latest | 64 | $90,033 | $-28,080 | 192 / 64 | 96 / 32 | 2.00 / 5.50 | 7.38 / 4.88 | 0.005 | 0.011 |
| semantic_inputs | 64 | $104,333 | $-1,203 | 0 / 0 | 0 / 0 | 4.00 / 10.00 | 9.88 / 10.00 | 0.138 | 1.172 |
| semantic_bank | 64 | $103,724 | $-1,396 | 0 / 0 | 3 / 2 | 4.00 / 10.00 | 10.00 / 10.00 | 0.060 | 1.210 |

## Worst paired cash and margin differences

Differences are within matching world and opponent; positive values favor the first arm.

### semantic_inputs_minus_baseline
- cash: minimum -49,901 at w08-mgt_m1 vs mgt_m1; maximum +16,938 at w11-v56 vs v56.
- margin: minimum -50,627 at w08-v56 vs v56; maximum +26,513 at w21-mgt_m1 vs mgt_m1.

### semantic_inputs_minus_latest
- cash: minimum -15,770 at w06-v56 vs v56; maximum +70,549 at w14-mgt_m1 vs mgt_m1.
- margin: minimum -15,569 at w06-v56 vs v56; maximum +95,955 at w14-mgt_m1 vs mgt_m1.

### semantic_bank_minus_baseline
- cash: minimum -49,690 at w08-mgt_m1 vs mgt_m1; maximum +16,691 at w11-v56 vs v56.
- margin: minimum -50,043 at w08-mgt_m1 vs mgt_m1; maximum +26,513 at w21-mgt_m1 vs mgt_m1.

### semantic_bank_minus_latest
- cash: minimum -25,678 at w26-v56 vs v56; maximum +70,549 at w14-mgt_m1 vs mgt_m1.
- margin: minimum -22,516 at w26-v56 vs v56; maximum +95,955 at w14-mgt_m1 vs mgt_m1.

### semantic_inputs_minus_semantic_bank
- cash: minimum -24,060 at w08-v56 vs v56; maximum +29,536 at w26-v56 vs v56.
- margin: minimum -26,653 at w08-v56 vs v56; maximum +28,843 at w26-v56 vs v56.

## Cohort details

Planted-day totals across 64 games per arm are in `cohort_planted_day_totals` in the JSON. Crop disappearance is not called a failure.

## Notes

- Action timing retains only per-game maximum by seat; no individual action samples exist. Means shown are means of game maxima, not mean action latency.
- Cohort snapshots classify currently live crops and planted_day only; they do not attribute crop disappearance to harvest, death, or other causes.
- No confidence intervals or significance tests are included.
