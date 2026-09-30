# DSM worker paths, 2026-09-27

Replayed the 40 saved DSM worlds listed in `results/fresh/threads_20260928/panel_dsm40b.txt` through the local official engine. Both players' final cash and terminal status match every recording. These recordings have 719 action transitions and 720 states.

The traces cover engine days 11–28, inclusive: 8,345 hired-worker days plus 720 farmer days. Days, hours and coordinates are zero-based. Unit 0 is the farmer; units 1 onward are hands in that day's hire order.

## Outputs

- `traces.json`: every recorded worker action for all 40 worlds, including position before and after, command, actual tile type, immediate inventory delta and whether the action changed state.
- `viewer_data.json`: the same trace format for worlds 112602061 and 112604454, used in the conversation's interactive view.
- `summary.json`: verification, aggregate measurements, source hashes and ineffective-action records.
- `examples.json`: independently replayed detailed examples, with inventories before and after each action.
- `shape_audit.json`: existing route-shape and path-metric analyses rerun over the 40 DSM worlds, with their classification limitations recorded.
- Reproduction script: `scripts/trace_dsm_worker_paths_20260927.py`.

The board backdrop is the day's morning state. Each action separately records its actual pre-action tile. Effects are measured inside the unit-action function, before subsequent units, market orders and midnight refresh.

## Worker utilization

Per hired-worker day: 13.0895 issued field-work actions (13.0265 effective), 8.8375 movement actions, 0.7177 shed exchanges and 0.0285 PASS actions. There were 547 ineffective non-PASS commands across all 40 worlds: chiefly repeated watering (280) and harvesting without yield (174). An effective command is a measured state change, not a claim that the command was economically optimal.

## Three exact paths to inspect

| World | Day | Hand | Work / walk / shed / idle | Observation |
|---|---:|---:|---|---|
| 112602061 | 21 | 12 | 16 / 5 / 1 / 0 | Compact outward route: pen collections at hours 10 and 14 supply crop fertilizing at hours 16 and 23. Ends at (6,9). |
| 112604454 | 16 | 5 | 8 / 13 / 2 / 0 | Harvests 6 milk and 4 strawberries, unloads at (5,4) at hour 13, loads wheat at 14, revisits a cow for feed/care at 17/18, then harvests/waters strawberries at 22/23. |
| 112602061 | 18 | 7 | 13 / 9 / 1 / 0 | Delivers wool at hour 4, later harvests wheat at 10 and uses it for feeding at 14/17; returns to fertilize its replanted wheat at 23. |

All commands in these three example paths had an immediate effect. The return-and-revisit example demonstrates that real DSM paths sometimes accept backtracking and split service for earlier delivery; it does not establish that every such choice is optimal.

The prior route classifier identifies roughly 87% of working hand-days as radial, but truncates geometry at the last field-work hour plus one. Its percentage is therefore a work-period classification, not a definitive count of full-day delivery returns. Its 82.45% adjacency figure concerns consecutive worked visits in its radial group, not the share of movement steps that perform work.
