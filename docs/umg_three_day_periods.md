# UMG: production ranges and pre-reveal farm configurations

Thirty full replays of submission **56266758**. Values are observed **minimum–maximum**, including zero; a single number means every game agrees. These are sample ranges, not guarantees or confidence intervals.

## Exact timing

Snapshots are ticks **71, 143, 215, 287, 359, 431, 503, 575, 647, 719**, immediately before the next three-day boundary. New shops reveal at ticks 72 through 576 in steps of 72; the eight-shop cap prevents further reveals at days 27 and 30. Tick 719 is the final recorded state.

Production is aligned to these exact snapshots: action outcomes 1–71, 72–143, …, 648–719. The first bin has 71 executed actions and the remaining bins have 72. The period labels below are calendar labels; strict conventional three-day totals are also retained in the JSON. This avoids mixing a post-reveal output total with a pre-reveal configuration.

**Output means successfully harvested/collected goods**, before subsequent use, sales or overflow loss. Purchased wheat is excluded. Product still held on plants/animals is recorded separately in each game file.

## Harvested/collected output per period

| Days | WHEAT | CARROT | TOMATO | STRAWBERRY | MELON | EGG | MILK | WOOL | FERTILIZER |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0–2 | 4–6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 8 |
| 3–5 | 24–26 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 15–17 |
| 6–8 | 13–15 | 0 | 0 | 0 | 0 | 0 | 12 | 12 | 19–23 |
| 9–11 | 8–19 | 0 | 0 | 0 | 70–72 | 0–12 | 12–18 | 8 | 37–41 |
| 12–14 | 53–96 | 0 | 0 | 0–1 | 0 | 0–30 | 16–33 | 19–46 | 48–55 |
| 15–17 | 53–121 | 0–12 | 0 | 28–38 | 0 | 0–42 | 10–45 | 4–48 | 48–57 |
| 18–20 | 25–98 | 0–40 | 0–17 | 33–62 | 0–6 | 0–42 | 12–77 | 3–40 | 45–60 |
| 21–23 | 5–91 | 0–48 | 0–84 | 19–98 | 6 | 0–42 | 6–40 | 3–51 | 45–60 |
| 24–26 | 34–156 | 0–110 | 0–66 | 5–98 | 0 | 0–41 | 8–55 | 1–47 | 42–60 |
| 27–29 | 84–214 | 4–141 | 0–59 | 8–83 | 0 | 0–42 | 4–41 | 0–47 | 30–55 |

## Standing crops and animals at the pre-reveal tick

Crop values count occupied crop tiles, including immature plants; animal values count living animals. Ranges are marginal: combining all maxima does **not** describe a feasible farm. Ages and actual tile grids are retained in the per-game records.

| Days | WHEAT | CARROT | TOMATO | STRAWBERRY | MELON | COW | SHEEP | GOOSE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0–2 | 7 | 0 | 0 | 0 | 12 | 3 | 2 | 0 |
| 3–5 | 3–4 | 0 | 0 | 2–4 | 12 | 3–4 | 2 | 0 |
| 6–8 | 6–11 | 0 | 0 | 13–19 | 12–13 | 4–9 | 4–9 | 0–3 |
| 9–11 | 18–25 | 0 | 0 | 17–23 | 1–2 | 4–12 | 4–11 | 0–7 |
| 12–14 | 13–25 | 0–3 | 0–15 | 18–43 | 1–2 | 4–13 | 4–11 | 0–7 |
| 15–17 | 5–25 | 0–12 | 0–21 | 18–49 | 1–2 | 4–13 | 4–13 | 0–7 |
| 18–20 | 1–23 | 0–14 | 0–25 | 18–49 | 1 | 4–13 | 3–13 | 0–7 |
| 21–23 | 11–39 | 0–30 | 0–23 | 6–35 | 0 | 2–13 | 3–13 | 0–7 |
| 24–26 | 16–43 | 0–31 | 0–15 | 4–31 | 0 | 2–13 | 0–13 | 0–7 |
| 27–29 | 0–4 | 0–2 | 0–10 | 0–13 | 0 | 2–13 | 0–9 | 0–7 |

## Remaining capacity and resources

| Days | EMPTY | WEED | LOCKED | EMPTY_PASTURE | EMPTY_COOP |
|---|---:|---:|---:|---:|---:|
| 0–2 | 0 | 0 | 75 | 1 | 0 |
| 3–5 | 0–1 | 0 | 75 | 0–1 | 0 |
| 6–8 | 0 | 0 | 50 | 0–1 | 0 |
| 9–11 | 12–15 | 0 | 25 | 0–2 | 0–1 |
| 12–14 | 0–5 | 0 | 25 | 0–1 | 0 |
| 15–17 | 0–2 | 0–1 | 25 | 0 | 0 |
| 18–20 | 0–2 | 0–1 | 25 | 0 | 0 |
| 21–23 | 0–3 | 0–1 | 25 | 0–1 | 0 |
| 24–26 | 0–5 | 0–1 | 25 | 0–1 | 0 |
| 27–29 | 28–53 | 2–19 | 25 | 0–5 | 0–1 |

| Days | cash | hands | quadrants |
|---|---:|---:|---:|
| 0–2 | 137.0–153.0 | 4 | 1 |
| 3–5 | 181.0–615.0 | 5 | 1 |
| 6–8 | 513.0–1059.0 | 10 | 2 |
| 9–11 | 14407.0–19104.0 | 10 | 3 |
| 12–14 | 20135.0–30050.0 | 10 | 3 |
| 15–17 | 30936.0–50185.0 | 11 | 3 |
| 18–20 | 44755.0–72840.0 | 11 | 3 |
| 21–23 | 52742.0–100662.0 | 11 | 3 |
| 24–26 | 60870.0–124833.0 | 11 | 3 |
| 27–29 | 73370.0–157574.0 | 11 | 3 |

## Variation in farm composition

| Days | Distinct crop/herd count configurations | Most frequent configuration: games |
|---|---:|---:|
| 0–2 | 1 | 30/30 |
| 3–5 | 2 | 29/30 |
| 6–8 | 16 | 5/30 |
| 9–11 | 25 | 3/30 |
| 12–14 | 27 | 3/30 |
| 15–17 | 29 | 2/30 |
| 18–20 | 30 | 1/30 |
| 21–23 | 30 | 1/30 |
| 24–26 | 30 | 1/30 |
| 27–29 | 30 | 1/30 |

## Validation and scope

Each game was rerun with its original recorded actions in the official engine. Final scores and all ten complete checkpoint observations reproduced; conventional production totals matched all saved segment-ledger product counts. Total production agrees under both boundary conventions. Harvest counting happens inside the engine before midnight inventory resets.

The 584 compact tapes retain day-start boards but lack these exact pre-reveal observations. Both tables therefore use the same 30 full replays rather than mixing sample populations or shifting the configuration by one tick.

Artifacts: `results/fresh/production_continuation/three_day_periods/summary.json` and `game-<episode>.json`. Script: `scripts/summarize_umg_three_day_periods.py`.
