# Public-router handoff at day 9

## What the previous opening comparison measured

In `search_growth_openings.py`, our day-9 farm was handed to the generic maintenance or replanting controller. The opponent kept the same public-router instance it used during the opening. Thus the reported 47,918 versus 125,511 mixed opening and continuation quality; it was not an isolated estimate of opening weakness.

The earlier `evaluate_boards.py` panel separately included all pairs of maintenance, replanting, expansion and native policies. In a shared-controller pair the router's board received the same generic rule as ours; in native mode the router continued its own agent, while our side continued v1. These are different comparisons. Native router state was reconstructed by replaying its prior observations and checking its actions against the saved prefix.

## New experiment

Four new opening/future seed pairs (86301–86304 / 96301–96304), both seats, three arms: 24 full-season runs. At step 216 (start of day 9), keep the exact state and replace our controller. Each arm faces a public router playing from the start. The full-router arm uses two independent router instances. All arms use the same synthetic future seed within each scenario; it remains hidden from policies. Farms affect subsequent random draws and markets, so cross-opening futures need not be identical.

| Our opening → continuation | Our mean final cash | Opponent mean cash | Mean margin | Mean premature crop losses after handoff | Mean animal losses after handoff |
|---|---:|---:|---:|---:|---:|
| small-herd → replant | 61,085 | 125,809 | -64,724 | 5.1 | 0.0 |
| small-herd → router | 74,079 | 135,927 | -61,848 | 5.5 | 0.0 |
| public-router → router | 79,076 | 79,076 | +0 | 1.0 | 0.0 |

## Interpretation

The literal switch improved our mean cash from 61,085 to 74,079 (+21.3%) but reduced the competitive deficit by only 2,876 (+4.4%), because opponent income also increased. The complete-router self-play reference earned 79,077 per side. Our switched result is 6.3% below that cash reference, but this is not a clean 6.3% opening penalty: the opposing farm and shared market evolved differently. Every self-play game tied. The competitive results show a substantial remaining disadvantage even with the same router code controlling both sides after day 9.

This local router is primarily a recorded action stream, with switches at steps 226, 360 and 433. It does not reconstruct a route for an arbitrary farm. Its actions depend on the expected tile layout, crop ages, worker positions and inventories from its recorded opening. The source explicitly warns that unrelated prefixes can make it water and harvest empty tiles. A literal handoff therefore measures opening-plus-route compatibility, not just economic board quality.

A cold router at step 216 is sufficient here: its first branch is at 226, its route starts as MAIN, and its remaining persistent cache is derived from that route. No worker or farm state is hidden inside it. The experiment calls `Agent.act` directly so exceptions fail the run rather than becoming silent PASS actions. The standalone public entry point was then checked against the saved continuations.

All 24 games completed with valid intermediate statuses and exact continuation cash accounting. The growth arms have identical day-9 features in all eight scenarios and identical parsed opening replays (excluding unique episode IDs) in the two saved examples. Verified 2,012 continuation decisions against the unmodified public entry point, with no observation mutation. Crop-loss counts exclude normal expiry; animal counts include animals acquired after the handoff.

The local hybrid entry point is `agents/opening_v2_router.py`; it loads the two existing agents and switches at step 216. It matched all 1,438 actions in both saved full-game trajectories. It requires sibling files and is not a standalone submission bundle. The selected opening and public router remain unchanged. To isolate opening quality more cleanly, use a controller that actually adapts to arbitrary boards, or optimize openings that preserve the router's required handoff state. The current generic continuation also has limitations, so neither score is an optimal valuation.

## Paired results

| Seed | Seat | Growth → replant | Growth → router | Router → router |
|---:|---:|---:|---:|---:|
| 86301 | 0 | 45,985 | 51,590 | 103,801 |
| 86301 | 1 | 64,365 | 70,509 | 103,801 |
| 86302 | 0 | 67,424 | 70,984 | 69,511 |
| 86302 | 1 | 67,424 | 70,984 | 69,511 |
| 86303 | 0 | 61,599 | 77,407 | 47,089 |
| 86303 | 1 | 61,599 | 77,407 | 47,089 |
| 86304 | 0 | 60,142 | 86,877 | 95,905 |
| 86304 | 1 | 60,142 | 86,877 | 95,905 |

[Growth-to-router full replay](../results/fresh/router_handoff/small-herd-router-86301-seat0/full_replay.json) · [Raw panel](../results/fresh/router_handoff/panel.json)

```powershell
.venv/Scripts/python.exe scripts/test_router_handoff.py
.venv/Scripts/python.exe scripts/report_router_handoff.py
```

The runner refuses to overwrite saved replay directories. Use a fresh output directory in the runner for repeated experiments.
