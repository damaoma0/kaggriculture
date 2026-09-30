# v1 failure audit: w02 normalized vs funded

Mechanical comparison of saved completed game JSONs, using each game’s own seat. Exact locked-tile counts come from `assets`; crop and animal counts come from `tile_counts`. Revenue and spend are cumulative successful transaction ledgers. Daily outputs observe steps 0, 24, ..., 696, 719.

| Opponent | Own seat | Final normalized | Final funded | Gap (normalized - funded) | First observed divergence | Step 168: land locked N/F | Step 168: key assets N/F | Day 10 land locked N/F |
|---|---:|---:|---:|---:|---|---:|---|---:|
| mgt_m1 | 0 | 99580 | 60623 | +38957 | step 168 (day 7); land/counts/spending also first differ there | 50/75 | cow 7/2, strawberry 18/8 | 50/50 |
| v56 | 1 | 116358 | 59464 | +56894 | step 168 (day 7); land/counts/spending also first differ there | 50/75 | cow 7/2, strawberry 18/8 | 25/50 |

Both games match at step 144. The first observed difference is the day-7 snapshot at step 168, after the reported step-149 `BUY_LAND` cancellation. In mgt_m1, normalized uses 50 locked tiles (2 quadrants) while funded remains at 75 (1 quadrant); funded catches up to 50 locked tiles at step 240. Against v56, normalized reaches 50 locked tiles at step 168 and 25 at step 240 (3 quadrants), while funded stays at 75 through step 216 and then 50 (2 quadrants) from step 240 through the final snapshot.

At step 168, both revenue ledgers still match. Cumulative `BUY_LAND` spend is $1,000 normalized vs $0 funded in both games; other first spend differences are shown in the JSON. The land and asset divergence therefore appears before a revenue-ledger divergence. By final, normalized-minus-funded cumulative revenue and spend reconcile exactly to the cash gap:

- mgt_m1: revenue delta +37378; spend delta -1579; net cash delta +38957.
- v56: revenue delta +56528; spend delta -366; net cash delta +56894.

The JSON includes every daily locked-tile count, quadrant-equivalent area, crop/animal counts, and cumulative revenue/spend by category for both arms, plus first divergence steps by measure. Daily-only outputs identify the first divergent day boundary; they do not show the exact within-day transaction sequence.
