# KB115LT: the lower layer for tile-planner training (2026-09-28)

KB115LT is the executor frozen as `agents/mgt_lead_kb115lt.py` (a byte copy of `agents/mgt_lead_sector_search.py` on
2026-09-28, so research edits to the working file never touch training runs; the KB115LT / KB115LTJ arms point to it) with the tile plan read **only** through an explicit
interface (`TilePlanView`) and a lower layer that uses nothing else of DSM's recorded game. A tile planner trained over
it supplies the interface; everything below it (maintenance, harvests, labour, routes, dawn trips, sales) is ours.

## KB115LT2 (2026-09-29): the same interface over an improved lower layer

`agents/mgt_lead_kb115lt2.py`, spec arm KB115LT2 = KB115LT + collect-at-floor fix, the hand-plan polish, learned2 dawn
trips and a higher deferred pen-harvest value (details: `docs/handplan_engine_overnight_20260928.md`). Same tile plan
interface and `sd_tp_file` input. 40 worlds (Kaggle): 31/40 wins, mean +4,517 (KB115LT's config there: 27/40, +2,016).

## Arm

`results/fresh/threads_20260928/animal/spec.json` -> `KB115LT` = KB115L + three settings:

| setting | meaning |
|---|---|
| `sd_tp_iface: 1` | the plan only through `TilePlanView`; any other read of the recorded game or of the per-world DSM files returns empty and is counted (`tp_leak` in each day's tier log) |
| `sd_clean: 1` | no DSM sales quotas (delivery values, dispatcher's open products, the regular sell path) and no DSM fertilize targets (fertilizer reserve) |
| `sd_books_pace_map` | the learned sell pace table for each world is fit on the 32 worlds outside its fold (`dsm_sell_pace_folds.json`; fold 0 = `panel_dsm8.txt`) |

No experimental add-ons (no front seller, no learned2 dawn, no evening wheat rule, no manual / polished plans).
Days 0-10 are DSM's recorded opening (the harness replays them). Generic learned constants remain: the dawn-rule
thresholds (fit on the 40 recordings) and the leaders' harvest-timing tendencies (540 tapes).

## The interface (tile planner -> lower layer)

Per day `d` of `n` (fields and formats as `TilePlanView.to_dict()` writes them; tiles are `y * 10 + x`):

| field | content |
|---|---|
| `n` | season length (days) |
| `plant[d]` | `{tile: crop}` plantings on day d |
| `events` | `[(planting day, tile, crop)]` the same plantings as a list (order kept) |
| `struct_by_day[d]` | `{tile: "COOP" or "PASTURE"}` structures standing at the end of day d |
| `animals_by_day[d]` | `{tile: species}` animals kept at the end of day d (placement = first day on the tile, exit / retirement = first day off it) |
| `board[d]` | 100 labels, the plan's board at the start of day d (`WH CA TO ST ME` crops, `sh co go` animals, `pa co` structures, ` .` empty, ` L` locked) |
| `harv_tiles[d]` | crop cohorts that end on day d (one-time crop harvest) or have their first harvest (ongoing crop); pens excluded |
| `removals[d]` | `[(tile, crop, planting day)]` live crop cohorts dug out on day d (read only with `exact_removals`, off) |
| `land_day` | `{quadrant: day}` land purchases |
| `hands[d]` | hands present on day d |
| `cum_sold[d]` | opening only (d <= 10): cumulative units sold, which seeds our sold counter at the day-11 handoff |

What the lower layer does with them: plants on the plan's tiles and days (tile-exact, catching up late plantings
within the late window), builds / places / lets animals go on the plan's days, keeps a late planting only when the
plan harvests that cohort, harvests-and-replants a one-time crop on the day the plan replants its tile, and hires the
plan's hands.

## Feeding a trained planner's plan

Write `{episode: plan}` in the `to_dict()` format and set `sd_tp_file` on top of KB115LT:

```
.venv/Scripts/python.exe scripts/export_tile_plans.py results/fresh/threads_20260928/panel_dsm40b.txt results/fresh/tile_plans/dsm40.json
```

writes DSM's 40 plans in that format (examples; the JSON round trip is checked lossless per field). Arm `KB115LTJ` =
KB115LT + `sd_tp_file: results/fresh/tile_plans/dsm40.json`. Run any arm with
`scripts/run_arms.py --spec <spec> --arms <ARM> --games <panel> --days 19` (results in
`results/fresh/sector_20260925/multi/<ARM>/<ep>.json`: `money[day] = [ours, rival]`; win = final ours > rival).

## Checks (2026-09-28)

- Interface completeness: KB115LTJ (JSON plan only) = KB115LT (recorded plan) to the dollar on 112575429 (+6,927)
  and 112604454 (-6,952), every day's plan identical, `tp_leak` empty (no read outside the interface), no errors.
- 8-world panel (`panel_dsm8.txt`): KB115LT wins 6/8, mean margin +4,029 (KB115L 6/8, +3,657; KB115 7/8, +7,647).
- KB115L on all 40 worlds: 28/40 wins (70%, Wilson 95% 55-82%), mean margin +2,231 (KB115 33/40, +5,938; DSM's
  own games 40/40, +17,657). KB115LT has not been run on the 40 worlds.
- Identity: the new switches are default off; KB115L re-run on the 8 worlds reproduces 7/8 to the dollar, one world
  differs by $1 on day 27 with identical day plans (the within-day re-planner's wall-clock budget).

## Subsequent strict semantic tiler validation (2026-09-28)

The completed local 40-world comparison is recorded in
[the semantic planner report](semantic_tile_planner_20260928.md). With the same
corrected D29 hires in both arms, exact tiling wins 27/40 and strict semantic
tiling wins 26/40; paired margin +151.575 (bootstrap95 -554..+799), no significant
regression. All80 games complete and reconcile. The compiler uses daily change
counts and the public D11 state, with explicit occupied-retirement metadata.
This supersedes the earlier "KB115LT has not been run on the 40 worlds" status;
the original opening, recorded-opponent and Kaggle-runtime limits still apply.
