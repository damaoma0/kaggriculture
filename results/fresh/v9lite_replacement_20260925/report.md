# V9-lite replacement / wool-upturn experiment — 2026-09-25

Four frozen arms differ only in packaged agents/mgt_y3.py: baseline, explicit crop-replacement guard, wool-price upturn, and both. Current submissions and the original V9-lite package are unchanged.

| Arm | Historical mean margin change (2 diagnostic worlds) | Fresh pilot mean margin change | Pilot better / worse / same |
|---|---:|---:|---|
| guard | -3178.0 | 709.0 | 2 / 0 / 2 |
| upturn | -10.0 | 625.5 | 2 / 0 / 2 |
| combined | -2914.5 | 829.5 | 2 / 0 / 2 |

Historical results use fixed recorded shops and opponent actions. Pilot uses two newly generated seeds, both seats, a responsive V56, natural RNG and the official engine time bank. These are two independent pilot worlds, not four independent worlds. Confirmation seeds remain separate.

Completed full games: 24. Recorded failures: 0. Verified live ledgers: 16. Minimum own live time bank: 41.752883. Internal search errors: 0.

## Mechanism and rejection evidence

The guard scans the selected route for DIG then PLANT on the same tile over today and the next two days, abstains when native FEED precedes the conversion, removes optional FEED/CARE and retains an already-requested HARVEST when product is present. It changes no shops or external opponent behavior. Contract checks cover conversion recognition, native-feed veto, final-stock harvesting and removal of obsolete rescue commitments.

In episode 111261836 it restores the D26 wheat planting at (3,4), which later yields five wheat. But total wool sold falls 80 to 58, wage spending falls 953, and final competitive margin falls 2,034. The second diagnostic loses 4,322. Thus treating the donor conversion as mandatory is not a validated fix for current y3: keeping an animal can be the profitable demand response. The old m1 failure does not transfer directly to V9-lite.

The isolated wool-upturn patch changes the current diagnostics by -20 and 0. Its older m1 validation cannot be reused as current-package evidence.

No promotion is justified by restoring a planting or increasing a forecast alone. Any successor needs a comparison of feasible remaining animal income and crop replacement income, including labor and rival price effects, rather than an unconditional retirement priority.

Reproduce: experiment_v9lite_replacement.py freeze / historical / pilot; report_v9lite_replacement.py; test_mgt_replacement_guard.py. Exact source hashes, predeclared seeds, raw results, work traces and ledgers are stored beside this report.
