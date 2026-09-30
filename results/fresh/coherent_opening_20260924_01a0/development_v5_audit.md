# Development v5 mechanical audit

Compared semantic_inputs and semantic_bank on the fixed 16 specs, with v2 latest and v1 baseline controls. All 32 v5 candidate games were complete. No statistical significance claims are made.

| Arm | N | Ledger verified | Mean own final cash | Mean rival margin | Mean failed hires, first 3 days | D3 strawberry / melon | D6 strawberry / melon | Mean game max action (s) | Worst game max (s) |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| semantic_inputs | 16 | True | 109911.812 | 3366.438 | 0 | 4 / 9.875 | 9.875 / 9.875 | 0.005 | 0.011532500036992133 |
| semantic_bank | 16 | True | 111218.375 | 4801.25 | 0 | 4 / 9.875 | 10 / 9.875 | 0.075 | 1.135771100060083 |
| v2_latest | 16 | True | 90910.125 | -36288.812 | 3 | 2 / 5.5 | 7.375 / 4.875 | 0.489 | 1.4160498999990523 |
| v1_baseline | 16 | True | 116831.562 | 4609.5 | 0 | 0 / 12 | 4 / 12 | 0.151 | 1.1703035000246018 |

## Paired candidate cash differences

Positive values favor semantic_inputs.
- w00-mgt_m1: own cash -8,069; rival margin -6,335; D3 strawberry/melon +0/+0; D6 +0/+0.
- w00-v56: own cash -4,666; rival margin -6,459; D3 strawberry/melon +0/+0; D6 +0/+0.
- w01-mgt_m1: own cash +0; rival margin +0; D3 strawberry/melon +0/+0; D6 +0/+0.
- w01-v56: own cash +0; rival margin +0; D3 strawberry/melon +0/+0; D6 +0/+0.
- w02-mgt_m1: own cash -746; rival margin -1,595; D3 strawberry/melon +0/+0; D6 -1/+0.
- w02-v56: own cash -795; rival margin -1,146; D3 strawberry/melon +0/+0; D6 -1/+0.
- w03-mgt_m1: own cash -3,358; rival margin -3,851; D3 strawberry/melon +0/+0; D6 +0/+0.
- w03-v56: own cash -3,271; rival margin -3,571; D3 strawberry/melon +0/+0; D6 +0/+0.
- w04-mgt_m1: own cash +0; rival margin +0; D3 strawberry/melon +0/+0; D6 +0/+0.
- w04-v56: own cash +0; rival margin +0; D3 strawberry/melon +0/+0; D6 +0/+0.
- w05-mgt_m1: own cash +0; rival margin +0; D3 strawberry/melon +0/+0; D6 +0/+0.
- w05-v56: own cash +0; rival margin +0; D3 strawberry/melon +0/+0; D6 +0/+0.
- w06-mgt_m1: own cash +0; rival margin +0; D3 strawberry/melon +0/+0; D6 +0/+0.
- w06-v56: own cash +0; rival margin +0; D3 strawberry/melon +0/+0; D6 +0/+0.
- w07-mgt_m1: own cash +0; rival margin +0; D3 strawberry/melon +0/+0; D6 +0/+0.
- w07-v56: own cash +0; rival margin +0; D3 strawberry/melon +0/+0; D6 +0/+0.

## Lowest final cash cases

### semantic_inputs
- w04-mgt_m1: own 74,083, rival margin +1,743, failed hires first 3 days 0, later first failed hire step None.
- w04-v56: own 75,219, rival margin +20,595, failed hires first 3 days 0, later first failed hire step None.
- w00-v56: own 82,962, rival margin +13,238, failed hires first 3 days 0, later first failed hire step None.
- w00-mgt_m1: own 87,477, rival margin +13,599, failed hires first 3 days 0, later first failed hire step None.

### semantic_bank
- w04-mgt_m1: own 74,083, rival margin +1,743, failed hires first 3 days 0, later first failed hire step None.
- w04-v56: own 75,219, rival margin +20,595, failed hires first 3 days 0, later first failed hire step None.
- w00-v56: own 87,628, rival margin +19,697, failed hires first 3 days 0, later first failed hire step None.
- w01-v56: own 88,214, rival margin +3,582, failed hires first 3 days 0, later first failed hire step None.

## Notes

- Game files store only max_action_seconds per seat, not per-action timing samples; mean action time cannot be derived. Reported metric is mean of per-game maxima and worst per-game maximum.
- Failed hires are counted only from actual failed_hires event records, filtered to the policy seat.
- Crop disappearance is not classified as failure; D3/D6 counts and planted_day cohorts are snapshots.
- No statistical significance claim; this is a mechanical fixed-spec comparison.
