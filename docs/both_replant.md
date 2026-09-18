# Direct match: both openings followed by replanting

This is the requested head-to-head comparison in the same game. One farm uses our selected growth opening, the other the public router opening. At step 216 (start of day 9), BOTH switch to independent instances of the same replanting controller. Neither uses router decisions after that point.

Four seed pairs (86301–86304 / 96301–96304), both seats, eight games. The controller cares for existing assets and replaces cleared original crop plots with wheat through day 25. It buys no new animals or land. Each farm uses the same workload-based staffing rule, capped at 10 hands; actual staff counts can differ with workload.

| Strategy | Mean terminal cash |
|---|---:|
| Our opening → replant | 71,387 |
| Router opening → replant | 96,316 |

Our mean margin: -24,929. Our wins: 0/8; draws: 0/8. Router-opening cash is 34.9% higher on average.

| Seed | Our seat | Our opening → replant | Router opening → replant | Our margin |
|---:|---:|---:|---:|---:|
| 86301 | 0 | 58,272 | 83,758 | -25,486 |
| 86301 | 1 | 66,014 | 102,602 | -36,588 |
| 86302 | 0 | 78,323 | 116,161 | -37,838 |
| 86302 | 1 | 77,242 | 113,772 | -36,530 |
| 86303 | 0 | 78,764 | 107,867 | -29,103 |
| 86303 | 1 | 78,572 | 104,432 | -25,860 |
| 86304 | 0 | 66,955 | 70,969 | -4,014 |
| 86304 | 1 | 66,955 | 70,969 | -4,014 |

All games completed with valid intermediate statuses and exactly reconciled continuation cash accounts. The growth-side day-9 features match previous runs in all eight scenarios, and the saved opening replays match exactly excluding episode IDs. Both farms use the same continuation implementation with their own actual state.

This measures opening performance under this specific replanting policy and shared market. It is not optimal board value: the scheduler can service different layouts with different efficiency, and four seeds are a small sample. Unlike previous comparisons against a full router, neither side retains the router's stronger continuation here.

[Full head-to-head replay](../results/fresh/both_replant/seed86301-seat0/full_replay.json) · [Raw results](../results/fresh/both_replant/panel.json)

Run `.venv/Scripts/python.exe scripts/test_both_replant.py` to reproduce. Use a fresh output directory in the script for reruns; saved replay folders are not overwritten.
