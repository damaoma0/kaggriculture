# Causal strategy quantity fidelity diagnostic

Twenty whole training episodes were held out before fitting. No gate games were evaluated. This measures quantity imitation, not competitive strength. Market and rival snapshots are absent in the archives: policy predictions below use base prices, market inventory 10,000, and an empty rival farm. Raw nearest-neighbor quantity retrieval does not require those substituted fields.

| Variant | MAE per species/day | D6 strawberry bias | D6 cow bias | D9 strawberry bias | Late wheat bias | Hands mean |
|---|---:|---:|---:|---:|---:|---:|
| calendar_median | 0.639 | 0.700 | -0.100 | 0.850 | 0.261 | 10.583 |
| cash_unconstrained_neutral_market | 0.971 | 1.550 | 0.200 | 1.900 | -0.933 | 10.923 |
| no_economics_neutral_market | 0.842 | -0.850 | 0.250 | 0.850 | -1.433 | 10.831 |
| policy_neutral_market | 0.973 | 1.300 | 0.150 | 1.900 | -0.933 | 10.923 |
| raw_nearest_joint_counts | 0.565 | -0.450 | 0.250 | 0.150 | 0.078 | 10.783 |

Cash-sensitive decisions: 9/480. Economics chose a different neighbor from pure distance in 191/480 decisions.

Model SHA256: `f548f1fa3d68668fb837538f1741df4b6317a0f82dc16cb54a44052c41b1f382`. Policy SHA256: `c635568115affb27096db74634d122ce8cca9e7cd1ed1d880a564d81e127deff`.

The full JSON contains species/window totals, land accuracy, hand-count errors, and each prediction. All figures are development diagnostics under the stated missing-feature assumptions.
