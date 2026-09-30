# Heavy-loss audit — 22 September 2026

“20k” is interpreted as a final losing margin of at least 20,000 coins. This audit reads cached results, not a fresh ladder download or newly simulated games. The cached ladder coverage ends on 20 September.

| Cohort | Games | Losses | Losses ≥20k | Worst margin |
|---|---:|---:|---:|---:|
| Submitted t10, recorded ladder | 141 | 24 | 1 | −22,371 |
| Submitted m1, recorded ladder | 86 | 22 | 0 | −12,585 |
| m1 vs live V50, 128 natural seeds × 2 seats | 256 | 69 | 0 | −15,071 |
| m1 vs live V56, four-seed smoke test × 2 seats | 8 | 6 | 0 | −14,072 |

These cohorts have different opponents and worlds and should not be treated as a paired improvement comparison. Seats can produce identical outcomes; game counts are not independent seed counts. The V56 smoke test is too small to establish strength. Historical artifacts also contain different m1 hashes; this report describes the saved runs, not a certification of today's source.

## The 22k loss: an execution failure with an existing repair

Episode 110950148, t10 vs Frost Cerberus: 96,732 vs 119,103, margin −22,371. The trace reproduces the recorded actions with zero mismatches. One hire failed on day 5 and three failed on day 9; missing workers shift later tape command indices. The trace counts 497 ineffective commands out of 6,606 (7.5%).

In the saved matched replay, m1 and the hire-guard build h2 both finish at 106,998 vs 108,393, margin −1,395, with no failed hires. The margin improvement is 20,976: our cash increases 10,266 and the opponent's decreases 10,710 through the shared market. It would be incorrect to call all 20,976 extra production. The opponent follows recorded actions and cannot adapt, so this is a diagnostic counterfactual, not a new live win.

Sources: `results/fresh/ladder_t10/trace_110950148.json` and `results/fresh/ladder_panel/{mgt_t10,mgt_h2,mgt_m1}/110950148.json`. The trace and panel use different ineffective-command instrumentation; their counts are not interchangeable.

## Remaining losses: production mismatched to demand

The six worst m1 recorded ladder games (111262874, 111269605, 111337545, 111324547, 111284610, 111261836) all have zero action mismatches and no hire shortfalls in the saved traces. Ineffective commands range from 0.16% to 1.76%. Five have additional or earlier late Yarn Store arrivals relative to the selected tape. The worst, against Raagav & Pieter (−12,585), instead has more Ice Cream Shops and fewer Yarn Stores than its tape: demand mismatch is broader than wool alone. This is diagnostic evidence, not a causal allocation of each loss.

In the worst saved natural V50 test (seed 176079, seat 1), the −15,071 margin reconciles exactly to the sales and spending ledgers. Wool contributes −36,587: we sell 230 units for 54,357 versus 381 for 90,944. Average realised prices are similar (236.33 vs 238.70 coins/unit), so a large quantity shortfall is visible. The symmetric arithmetic decomposition assigns −35,865 to quantity and −722 to realised price; this is an accounting decomposition, not a market counterfactual. Fertilizer contributes another −5,907, while other revenue and 9,631 lower spending offset much of the loss. The world has four Yarn Store arrivals, and the overlay buys four sheep, but still does not close the production gap.

Source: `results/fresh/selfplay/games/mgt_m1-176079-1-vs-v50_public.json`. Saved traces for the six ladder cases are under `results/fresh/ladder_t10/trace_<episode>.json` (the directory also contains m1 traces).

The next useful intervention is demand-conditioned production and animal servicing, tested against matched controls. More aggressive blanket expansion is not established as a fix. No agents or qualification panels were modified.

Reproduce cohort counts and the exact ledger reconciliation with `scripts/analyze_heavy_losses.py`; output is `results/fresh/heavy_loss_audit/audit.json`.
