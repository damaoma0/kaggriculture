# Strawberry, sheep and cow gaps — fresh September 23 cohort

Exact official-engine replay of the same 54 newly fetched games (25 m1, 29 t10), with both final balances verified. Opponent comparisons are within the same game. DSM is the archived leader sample: 108 games, 109 farm observations including one self-play; its different shop draws make the leader comparison descriptive, not matched or causal. Counts are day-start live plants/animals, not purchase requests.

| Asset | Day | Ours | Actual opponents | DSM archive |
|---|---:|---:|---:|---:|
| STRAWBERRY | 7 | 11.7 | 12.6 | 17.6 |
| STRAWBERRY | 9 | 17.1 | 19.4 | 19.0 |
| STRAWBERRY | 12 | 21.2 | 29.8 | 24.5 |
| STRAWBERRY | 18 | 28.7 | 31.3 | 27.3 |
| STRAWBERRY | 24 | 14.8 | 17.2 | 8.7 |
| SHEEP | 7 | 2.4 | 3.0 | 4.6 |
| SHEEP | 9 | 5.3 | 4.9 | 5.8 |
| SHEEP | 12 | 6.3 | 7.4 | 6.6 |
| SHEEP | 18 | 6.8 | 8.0 | 7.5 |
| SHEEP | 24 | 6.7 | 8.1 | 7.2 |
| COW | 7 | 4.4 | 5.2 | 5.9 |
| COW | 9 | 6.3 | 6.8 | 6.8 |
| COW | 12 | 7.5 | 7.8 | 8.9 |
| COW | 18 | 7.9 | 8.0 | 8.8 |
| COW | 24 | 7.6 | 7.9 | 7.5 |

## Full-season sales, matched fresh games

| Product | Ours | Opponents | Deficit |
|---|---:|---:|---:|
| STRAWBERRY | 213.0 | 234.9 | 21.9 (9.3%) |
| WOOL | 142.3 | 177.0 | 34.6 (19.6%) |
| MILK | 193.0 | 213.8 | 20.8 (9.7%) |

Sales are successful market units, not harvested units or revenue. No comparable fresh leader sales panel was rerun here.

## Animal service

Rates are weighted by observed animal-days immediately before all 29 executed overnight refreshes. Effective care means both fed and cared that day. Not every skipped day is a mistake: planned retirement, output caps, and low prices can justify wind-down.

| Animal | Fed: us / rival | Fed and cared: us / rival |
|---|---:|---:|
| SHEEP | 80.6% / 84.4% | 72.2% / 82.3% |
| COW | 75.8% / 81.6% | 70.0% / 79.4% |

## Interpretation

Strawberries: the leader gap is early. We have 5.8 fewer plots than DSM at day 7, 3.2 fewer at day 12, but 1.4 more at day 18 and 6.2 more at day 24. More late standing plants are not automatically better: planting dates, cohort age and earlier sales matter. Actual fresh opponents lead us by 8.6 plots at day 12 and 2.6 at day 18.

Sheep: an early DSM gap (2.4 versus 4.6 at day 7), a continuing deficit against actual opponents (1.2 animals at day 12 and 1.4 at day 24), and weaker feeding/care all contribute to lower wool sales.

Cows: only 0.3 fewer than actual opponents at day 12, but 1.4 fewer than DSM; the earlier day-7 gaps are 0.9 and 1.5 respectively. The roughly 10% milk-sales deficit is larger than the midgame herd-count deficit and coincides with weaker animal service. Buying more cows alone is not established as a profitable fix.

## m1 alone (25 fresh games)

At day 12, m1 has strawberries 21.8 vs 32.2, sheep 5.84 vs 7.24, and cows 7.72 vs 8.12. Whole-season sales are strawberries 226.3 vs 244.3 (7.4% fewer), wool 131.2 vs 167.6 (21.7% fewer), and milk 201.9 vs 231.3 (12.7% fewer).

Source data: `results/fresh/records_refresh_20260923/farm_comparison/summary.json`; replay extractor: `scripts/compare_fresh_farms_20260923.py`; leader cache: `results/fresh/newphase_20260923/leader_response/dsm_cache.json`.
