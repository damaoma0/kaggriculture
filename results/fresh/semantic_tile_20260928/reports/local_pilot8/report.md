# Semantic tile planner on KB115LT

Stage: **exploratory8**. Input contract: **timing_extended**. Baseline: `ST28EXACT`. Bootstrap: 20,000 world-paired draws, seed 20260928.

Exact-tiling baseline: **6/8 wins**, mean competitive margin 3,924 (bootstrap 95% -2,611 to 10,924). Own cash reconciled 8/8; explicit complete-engine audits 8/8; engine status unverified in 0 earlier artifacts.

| Candidate | Paired worlds | Wins | Mean margin delta | Bootstrap 95% CI | Regression p (one-sided) | Requested gate |
|---|---:|---:|---:|---|---:|---|
| ST28COHORTLIFE | 8 | 6/8 | -1,920 | -4,117 to 124 | 0.0727 | not eligible |
| ST28REUSELIFE | 8 | 6/8 | -184 | -2,060 to 1,565 | 0.4295 | not eligible |
| ST28REUSEPOLISH | 8 | 6/8 | -213 | -1,581 to 1,245 | 0.3952 | not eligible |

The requested full40 gate is at least 20 wins and no statistically significant paired regression at one-sided α=0.05. Passing this test does **not** prove equivalence or noninferiority: no acceptable loss margin was declared. These are fixed-shop worlds against recorded opponent actions; prices still respond to our changed supply.

The strict tile-change-only input contract is not declared for these candidates; numerical results cannot qualify them for the requested strict shipping gate.

## ST28COHORTLIFE

Margin improved / unchanged / worse: 3 / 0 / 5. Paired t 95% CI: -4,690 to 851. Win flips gained / lost: 0 / 0.

Complete games 8/8; own cash reconciled 8/8; both final cash figures agree with ledgers 8/8. Executor errors 0; games with interface leaks 0. Maximum measured overage bank 17.17 s; 0 games exceed 60 s.

Frozen executor and policy configuration match: True. Confirmed runtime-regime conflict: False; runtime pairing unverified for 0 worlds. Explicit complete-engine audits 8/8; engine status unverified 0.

Failed market requests and no-effect commands are retained in the JSON report. Intentional animal retirement is included in death counters. Offline execution does not certify Kaggle action-time compliance.

## ST28REUSELIFE

Margin improved / unchanged / worse: 4 / 0 / 4. Paired t 95% CI: -2,541 to 2,173. Win flips gained / lost: 0 / 0.

Complete games 8/8; own cash reconciled 8/8; both final cash figures agree with ledgers 8/8. Executor errors 0; games with interface leaks 0. Maximum measured overage bank 13.73 s; 0 games exceed 60 s.

Frozen executor and policy configuration match: True. Confirmed runtime-regime conflict: False; runtime pairing unverified for 0 worlds. Explicit complete-engine audits 8/8; engine status unverified 0.

Failed market requests and no-effect commands are retained in the JSON report. Intentional animal retirement is included in death counters. Offline execution does not certify Kaggle action-time compliance.

## ST28REUSEPOLISH

Margin improved / unchanged / worse: 3 / 0 / 5. Paired t 95% CI: -2,041 to 1,614. Win flips gained / lost: 0 / 0.

Complete games 8/8; own cash reconciled 8/8; both final cash figures agree with ledgers 8/8. Executor errors 0; games with interface leaks 0. Maximum measured overage bank 14.18 s; 0 games exceed 60 s.

Frozen executor and policy configuration match: True. Confirmed runtime-regime conflict: False; runtime pairing unverified for 0 worlds. Explicit complete-engine audits 8/8; engine status unverified 0.

Failed market requests and no-effect commands are retained in the JSON report. Intentional animal retirement is included in death counters. Offline execution does not certify Kaggle action-time compliance.
