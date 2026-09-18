# Opening study: days 0-9

## Decision

Use the six-sheep/wheat opening as the provisional cash-first baseline. Keep the mixed-livestock/melon/strawberry opening as a second handoff state for midgame experiments. We have not established the best 30-day strategy or a globally optimal opening.

The implementation is agents/opening_v1.py: a new observation-driven controller, with no legacy planner or replay tape. Its agent entry point selects the cash-first configuration. Other configurations are instantiated by scripts/evaluate_openings.py.

## Mission chunks

1. **Opening (this study):** build a working farm, compare day-3/6/9 states, and save executable moves. The first baseline and comparison are complete.
2. **Midgame (next):** continue these exact states; compare reinvestment in land, crops, livestock, and fertilizer under revealed shop demand and opponent production. Choose the handoff time by results, rather than assuming day 9 is universally best.
3. **Late game:** optimize harvest deadlines, storage, sale timing, and final liquidation. Judge complete policies by 30-day outcomes across opponents and seeds.

## Provisional opening moves

Days and hours below are zero-based. Exact per-worker moves are in the linked move log.

| Stage | Actions | Purpose |
|---|---|---|
| Day 0, hour 0 | HIRE; buy 12 wheat products; buy 5 sheep; buy 8 wheat seeds. Farmer passes. | Fund feed and the initial flock; purchases become usable on the next turn. |
| Rest of day 0 | Grow toward 6 hired hands as cash permits. Pick up sheep, build nearby pastures, place/feed/care for sheep. Plant and water wheat. | Concentrate animal servicing near the shed. |
| Days 1-3 | Hire daily, feed/care, collect and sell fertilizer. Fill remaining wheat beds. Buy the sixth sheep once affordable. | Finance expansion from production; preserve feed liquidity. |
| Days 4-5 | Place the sixth sheep if not already placed. Harvest/replant mature wheat; retain a feed buffer. | Build working cash and keep the farm productive. |
| Days 6-8 | Harvest wool as it appears, return it to the shed, and sell. Continue feed/care/fertilizer and wheat cycles. | Convert the first livestock payouts into cash. |
| Day 9 | Save the farm, crop ages, private inventory, market, and opponent state. | Hand off to a separately evaluated midgame policy. |

This policy buys no extra land during the opening, sells fertilizer instead of applying it, and uses six hands as a target rather than assuming they are always affordable. Those are tested baseline choices, not universal rules.

The first five sheep occupy (4,4), (4,3), (3,4), (4,2), and (3,3). The sixth target is (2,4), using (x,y) coordinates on the NW 5x5 quadrant. Wheat occupies the other 19 target tiles.

[Full cash-first move log](../results/fresh/openings/sheep6-seed20261201-seat0/moves.md) · [Mixed-farm move log](../results/fresh/openings/mixed-strawberry-seed20261201-seat0/moves.md)

## Validation against the public-state router

Thirty configurations were screened on two seeds against starter (60 episodes). Eight candidates then faced agents/public/tschinkel_router_v31.py on six different seeds, both seats (96 episodes). The router is a strong local reference, not a verified current leaderboard leader. The two selected policies were subsequently recorded on three untouched seeds, both seats (12 episodes).

All episodes stop exactly at the beginning of day 9: 217 recorded states, 216 actions. These are opening-state comparisons, not win rates. Day-9 cash excludes unharvested output and inventory waiting to be sold.

| Policy | Mean cash at day 9 | Minimum cash | Crop / animal losses across 12 runs |
|---|---:|---:|---:|
| sheep6 | 9,300 | 8,657 | 0 / 0 |
| sheep4-melon0 | 8,720 | 8,543 | 0 / 0 |
| sheep4-melon8 | 7,472 | 7,347 | 0 / 0 |
| mixed4-melon8 | 6,725 | 6,568 | 0 / 0 |
| mixed-strawberry | 6,027 | 5,870 | 0 / 0 |
| carrot3-hands8 | 4,993 | 4,926 | 0 / 0 |
| wheat2-hands8 | 4,810 | 4,787 | 0 / 0 |
| wheat2-expand-hands10 | 4,569 | 4,548 | 36 / 0 |

## Untouched-seed results

| Policy | Day 3 mean cash | Day 6 | Day 9 | Day 9 range |
|---|---:|---:|---:|---:|
| sheep6 | 224 | 1,409 | 8,896 | 8,651-9,307 |
| mixed-strawberry | 370 | 1,787 | 5,869 | 5,699-6,007 |

Both selected policies had zero observed crop or animal losses in validation and untouched-seed runs. Each seat pair shares a seed; these are six validation and three untouched seed scenarios per policy, not 18 independent scenarios.

At the representative day-9 handoff, the cash-first farm has six sheep and wheat. The mixed farm has two cows, two sheep, eight melons, and eight strawberries. Melons and strawberries have not yet produced their main payouts within this study's horizon. A cash ranking therefore cannot establish which handoff is better for the whole season.

## Limits and findings to carry forward

- Sheep/fertilizer production beat the tested crop-only policies for opening cash. This does not establish a sheep-only 30-day strategy.
- Expanded crop farms missed some harvest/maintenance deadlines even with ten hands. Those losses confound economic conclusions about early land: improve scheduling before rejecting expansion.
- Cash-plus-installed-cost is retained in raw results as a bookkeeping diagnostic (cash plus original land, animal, and planted-seed costs). It is not liquidation value, expected future profit, or the selection objective.
- Shop draws share a daily random stream with weeds, so changing a farm can change the shop sequence even at the same seed. Use multiple seeds and show ranges.
- Fertilizer use, feed optimization, variable daily hiring, harvesting age, and alternate layouts remain unoptimized. The controller's movement and idle time also leave room for improvement.
- No leaderboard submission was made. The file can continue farming, but it has no tested midgame or endgame policy yet.

## Reproduce

From the project root:

```powershell
.venv/Scripts/python.exe scripts/evaluate_openings.py --stage screen --seeds 2
.venv/Scripts/python.exe scripts/evaluate_openings.py --stage validate --names sheep6 mixed-strawberry --seed-base 20261101 --seeds 6 --out results/fresh/openings/rerun
.venv/Scripts/python.exe scripts/verify_opening.py
```

Raw screening, refinement, validation, and untouched-seed results are stored under results/fresh/openings. Each recorded run includes moves.md, summary.json, and replay.json. Private opponent inventories are available only to offline analysis; the controller receives the normal player observation.
