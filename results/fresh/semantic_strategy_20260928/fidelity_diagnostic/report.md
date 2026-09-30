# Causal strategy quantity fidelity diagnostic

Twenty whole training episodes were held out before fitting. No gate games were evaluated. This measures quantity imitation, not competitive strength. Market and rival snapshots are absent in the archives: policy predictions below use base prices, market inventory 10,000, and an empty rival farm. Raw nearest-neighbor quantity retrieval does not require those substituted fields.

| Variant | MAE per species/day | D6 strawberry bias | D6 cow bias | D9 strawberry bias | Late wheat bias | Hands mean |
|---|---:|---:|---:|---:|---:|---:|
| calendar_median | 0.639 | 0.700 | -0.100 | 0.850 | 0.261 | 10.583 |
| cash_unconstrained_neutral_market | 1.125 | 1.550 | 0.200 | 1.850 | -4.617 | 10.940 |
| no_economics_neutral_market | 1.016 | -0.850 | 0.250 | 0.750 | -5.167 | 10.840 |
| policy_neutral_market | 1.127 | 1.300 | 0.150 | 1.850 | -4.617 | 10.940 |
| raw_nearest_joint_counts | 0.562 | -0.450 | 0.250 | 0.200 | 0.167 | 10.775 |

Cash-sensitive decisions: 9/480. Economics chose a different neighbor from pure distance in 182/480 decisions.

Model SHA256: `f548f1fa3d68668fb837538f1741df4b6317a0f82dc16cb54a44052c41b1f382`. Policy SHA256: `d3d678eaaab6bcc7f91755250edf15e0fa696bd83a714b1a73b987846b2e456f`.

The full JSON contains species/window totals, land accuracy, hand-count errors, and each prediction. All figures are development diagnostics under the stated missing-feature assumptions.
