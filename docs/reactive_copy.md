# Reactive public-board copying

## Definition

The copier sees the opponent's currently occupied crop/animal tiles, land ownership and worker count. It targets the same coordinates on its own farm and uses the observation-driven worker scheduler from opening_v2. It does not read opponent actions, private inventories, recorded routes or future state. Copying therefore starts after the opponent's investment becomes visible.

It protects and finishes existing own crops even after the opponent changes the matching tile. Empty plots adopt the opponent's current crop or animal. It matches visible crew up to 12 hands, buys NE only after the opponent owns it and cash permits, and keeps a 300 cash land buffer. It does not apply fertilizer or synchronize harvest timing; its own scheduler sells produce. New animals stop at day 20, new crops must have time to mature by day 29, and the last seven turns return and sell stock. This version supports the two quadrants used by the reference router. It is one specific copying baseline, not the best achievable copying strategy.

## Matched comparison

Four seed pairs (86301–86304 / 96301–96304), both seats; same scenarios as the handoff experiment. The copier continues its own state across the day-9 checkpoint. The opponent runs the full public router throughout. All scores are terminal cash. Opening-dependent market and random-draw differences remain part of each strategy's outcome.

| Strategy | Our mean cash | Opponent mean cash | Mean margin |
|---|---:|---:|---:|
| Reactive copy throughout | 49,987 | 102,350 | -52,363 |
| Growth → replant | 61,085 | 125,809 | -64,724 |
| Growth → router | 74,079 | 135,927 | -61,848 |
| Router throughout (self-play) | 79,076 | 79,076 | +0 |

Relative to growth → router, copying improved margin in 5/8 matched scenarios, with mean margin change +9,484. Copying won 0/8 matches against the router.

## Checks and limits

All eight games completed with valid intermediate statuses and exact continuation cash accounting. Verified 1,438 full-game actions through the copier's file entry point with no observation mutation. Seed allocation was checked on every decision. Opening losses: 0; later premature crop losses: 30; later animal losses: 3.

In the saved seed-86301 games, 46 matching day-9 crop tiles across both seats had median planting delay 0.0 days. This is a diagnostic on matching surviving crops, not a population-wide estimate of copying delay.

The two newly supported scheduler cases are TOMATO seed purchases and harvesting at age 8; previous opening layouts contain no tomatoes. Existing opening and router-handoff entry-point checks passed unchanged. The copier is a local multi-file agent and is not a standalone submission bundle.

## Per-scenario results

| Seed | Seat | Copier cash | Router cash | Margin change vs growth → router |
|---:|---:|---:|---:|---:|
| 86301 | 0 | 65,201 | 121,806 | -4,844 |
| 86301 | 1 | 55,549 | 102,642 | +14,642 |
| 86302 | 0 | 31,226 | 80,448 | +27,919 |
| 86302 | 1 | 32,414 | 95,395 | +14,160 |
| 86303 | 0 | 52,552 | 88,170 | +16,734 |
| 86303 | 1 | 52,552 | 88,170 | +16,734 |
| 86304 | 0 | 55,200 | 121,085 | -4,735 |
| 86304 | 1 | 55,200 | 121,085 | -4,735 |

[Full replay](../results/fresh/reactive_copy/seed86301-seat0/full_replay.json) · [Raw results](../results/fresh/reactive_copy/panel.json)

```powershell
.venv/Scripts/python.exe scripts/test_reactive_copy.py
.venv/Scripts/python.exe scripts/report_reactive_copy.py
```

The test runner refuses to overwrite saved replay folders; use a fresh output directory in the script for reruns.
