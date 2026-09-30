# Semantic tile planner on KB115LT

Stage: **full40**. Input contract: **strict**. Baseline: `ST28EXACT`. Bootstrap: 20,000 world-paired draws, seed 20260928.

Exact-tiling baseline: **27/40 wins**, mean competitive margin 1,947 (bootstrap 95% -451 to 4,372). Own cash reconciled 40/40; explicit complete-engine audits 40/40; engine status unverified in 0 earlier artifacts.

| Candidate | Paired worlds | Wins | Mean margin delta | Bootstrap 95% CI | Regression p (one-sided) | Requested gate |
|---|---:|---:|---:|---|---:|---|
| ST28REUSESTRICT | 40 | 26/40 | 152 | -554 to 799 | 0.6670 | pass |

The requested full40 gate is at least 20 wins and no statistically significant paired regression at one-sided α=0.05. Passing this test does **not** prove equivalence or noninferiority: no acceptable loss margin was declared. These are fixed-shop worlds against recorded opponent actions; prices still respond to our changed supply.

## ST28REUSESTRICT

Margin improved / unchanged / worse: 20 / 0 / 20. Paired t 95% CI: -553 to 856. Win flips gained / lost: 1 / 2.

Complete games 40/40; own cash reconciled 40/40; both final cash figures agree with ledgers 40/40. Executor errors 0; games with interface leaks 0. Maximum measured overage bank 13.22 s; 0 games exceed 60 s.

Frozen executor and policy configuration match: True. Confirmed runtime-regime conflict: False; runtime pairing unverified for 0 worlds. Explicit complete-engine audits 40/40; engine status unverified 0.

Failed market requests and no-effect commands are retained in the JSON report. Intentional animal retirement is included in death counters. Offline execution does not certify Kaggle action-time compliance.

Disjoint non-development remainder: 32 worlds, 20 wins, mean paired margin 181 (bootstrap 95% -594 to 895).
