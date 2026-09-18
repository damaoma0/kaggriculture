# Router opening followed by continuous replanting

Four seed pairs (86301–86304 / 96301–96304), both seats: eight additional runs complete the opening/continuation comparison. The opponent always uses the public router throughout. Handoff is at step 216, the start of day 9. All means are full-season terminal cash.

Replanting is exactly the existing evaluator policy: maintain existing animals and crops, then replace cleared original crop slots with wheat through day 25. It buys no new land or animals and uses the common staffing rule capped at 10 hands. It is not repeated planting of the router's original premium crops.

| Our opening → continuation | Our cash | Opponent cash | Margin | Premature crop losses after handoff | Animal losses after handoff |
|---|---:|---:|---:|---:|---:|
| Our opening → replant | 61,085 | 125,809 | -64,724 | 5.1 | 0.0 |
| Router opening → replant | 62,430 | 110,984 | -48,554 | 11.0 | 0.0 |
| Our opening → router | 74,079 | 135,927 | -61,848 | 5.5 | 0.0 |
| Router throughout | 79,076 | 79,076 | +0 | 1.0 | 0.0 |

Under the same replanting rule, the router opening changes our cash by +1,345 and margin by +16,170 on average relative to our growth opening. Cash improves in 4/8 paired scenarios; margin improves in 7/8. Router opening → replant wins 0/8 against the complete router.

## Checks and interpretation

All eight additional runs completed with valid intermediate statuses and exact continuation cash accounting. Their day-9 features match the complete-router reference in all scenarios. Both saved opening replays match that reference exactly, excluding unique episode IDs. The generic controller takes over the actual farm state without changing assets or inventories.

Using the same continuation rule is a better controlled comparison of openings, but remains policy-conditioned: different layouts interact with routing, staffing, and shared prices. It does not estimate the optimal value of either opening, and the four seeds are a small sample. The generic scheduler's premature crop losses also matter when interpreting the router board's value.

| Seed | Seat | Router opening → replant cash | Opponent cash |
|---:|---:|---:|---:|
| 86301 | 0 | 85,721 | 149,968 |
| 86301 | 1 | 85,721 | 149,968 |
| 86302 | 0 | 44,830 | 100,624 |
| 86302 | 1 | 44,830 | 100,624 |
| 86303 | 0 | 46,564 | 71,874 |
| 86303 | 1 | 46,564 | 71,874 |
| 86304 | 0 | 72,604 | 121,470 |
| 86304 | 1 | 72,604 | 121,470 |

[Full replay](../results/fresh/router_replant/seed86301-seat0/full_replay.json) · [Raw results](../results/fresh/router_replant/panel.json)

Run `.venv/Scripts/python.exe scripts/test_router_replant.py` to reproduce. Saved replay folders are not overwritten; use a fresh output directory in the script for reruns.
