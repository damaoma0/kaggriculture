# Mother-Goose's decision logic, reconstructed from her 30 games

Phase 1 of "infer her policy, reimplement it, then improve on it". Rules, not actions. Source: all 30
exactly replayed games of submission 56266758 (`scripts/extract_mg_events.py` →
`results/fresh/mg_policy/events-*.json`; analyses in `results/fresh/mg_policy/*.log`).

Each rule is marked **derived** (an exact or near-exact pattern with a clear structure, exceptions
explained) or **fitted** (a monotone relationship whose exact thresholds come from 30 games and may
be an artefact).

## Architecture: a V45-lineage shop router with a different executor and a mid-game controller

- **Same market plan family as ours.** 58 of 72 market-order lists on days 0-2 are identical to our
  benchmark's. Her step-1 orders are our tape's with different wheat quantities, and her step-0
  `[BUY 13, BUY 5, SELL 13]` is the public router's *original* step-0 tape, which V45 later replaced
  with the 70-unit round trip. Same opening board, same land days, same route switch keyed on the first
  two shops around step 144.
- **Her own executor.** Unit actions match ours on 66% of day-0 steps and almost none after, yet reach
  the same board: she routes workers differently.
- **A mid-game controller that defers crop allocation until more shops are known.** This is where she
  departs from V45. We commit all 33 strawberries by day 11, when 2-3 shops are visible. She commits
  17-23, holds the melon land, and allocates it on day 12 when four are visible.

## The rules

| # | Rule | Form | Status | Confidence |
|---|---|---|---|---|
| R1 | **Labour** | Fixed daily hire schedule 5,4,4,5,4,5,8,8,10,9,11,10,10-11,11,10,11,… then 11 flat; identical in all 30 games, ±1 on four days | derived | high |
| R2 | Opening, days 0-5 | Fixed V45-lineage build: 3 cows, 2 sheep, 12 melons, 7 wheat by day 2 | derived | high |
| R3 | Land | 2nd quadrant day 6, 3rd days 9-11, never the 4th (field standard) | derived | high |
| R4 | **Early strawberries** | Fixed per-day schedule (day 5: 4, day 6: 7-8, day 11: 4) plus increments keyed on how many of the **first two** shops demand strawberries: 0 → 17-18 plants, 1 → 20-23, 2 → 23 | derived (±1 is execution noise) | high |
| R5 | **Day-12 reallocation of the freed melon land** | On days 12-13 the ~14 tiles freed by the melon harvest get strawberries and tomatoes, split by demand among the **first four** shops: 4 strawberry shops → 18-19 strawberries, 0 tomatoes; 3 → 9-16 strawberries; 2 → 5-9; ≤1 → 0-2 strawberries, tomatoes fill the rest (up to 14; 7-11 when no tomato shop); the remainder goes to wheat | direction derived (ρ = +0.89 with strawberry shops, −0.56 with tomato shops); thresholds **fitted** | medium |
| R6 | **Tomato replant at wheat harvest** | Days 14-21: a share of harvested wheat tiles is replanted with tomato instead of wheat (125 of ~150 later tomato plantings are on tiles that held wheat). Share rises with tomato shops visible at day 15: 0 → 0-11%, 1 → 0-14%, 2 → 6-24%, 3 → 17-29%, 4 → 53-64% | direction derived; share function **fitted**, wide spread within levels | medium-low |
| R7 | **Carrots** | Every game: carrot filler at wheat harvests on days 25-27 (29% of those replants). High carrot demand (Pet Cafe counts double; demand ≥ 5) starts carrot replants from days 14-17 (58-98 plants) | filler derived; early-ramp trigger **fitted**, inconsistent at demand 3 (0-18%) | filler high; ramp low-medium |
| R8 | **Animals** | Route-keyed on the first two shops, V45-style. Yarn → sheep burst (12-16 sheep, 0-2 geese); two milk shops → cow burst (10-13 cows, 1-3 geese); **otherwise geese are the default animal** (6-7, bought days 6, 7/9, 10-11). Later cows/sheep added as further milk/Yarn shops appear | partition derived; per-route counts from small cells | high (partition), medium (counts) |
| R9 | Second melon wave | One melon on day 11 at a fixed tile ((3,6) or (1,6)) in every game; one on day 8 at (7,0)/(7,1) in ~60% of games | day 11 derived; day-8 trigger unidentified | high / low |
| R10 | Execution conditionals | Weed repair (DIG before building), affordability at the opening margin (plants 5 wheat instead of 7 when short), stock-driven worker routing | observed directly | high |

## What she conditions on, and what she does not

- **Shops**: yes — R4, R5, R6, R7, R8 all read the shop list; R4 and R8 read only the first two, R5 the
  first four, R6/R7 the shops visible at days 15/18.
- **Opponent**: no. Five game pairs with the same shops and different opponents are byte-identical for
  8-12 days (`docs/leader_segments.md`).
- **Prices**: no evidence. The one clean natural experiment — two games with identical shops, board,
  strawberry and tomato prices at day 12 — still split the freed land differently by 1-2 plants; the
  first divergence was a worker stepping west instead of east after a one-unit wheat-stock difference.
  Across all 30 games, once shop counts are controlled for, neither the strawberry/tomato price ratio
  (partial correlation −0.05, p = 0.79) nor her cash (+0.04, p = 0.83) explains the split.
- **Her own state**: only at the execution level (R10).

So the variation across her games is **shops feeding a fixed decision structure, plus execution noise
from her own state**. She is not price-aware and not opponent-aware.

## Where her +7.6k over us comes from, mechanistically

From the tape test (`docs/tape_vs_bench.md`): tomato +4.6k, egg +2.3k, melon +0.7k.

- **Tomatoes** come from R5 (a day-12 batch on the freed melon land) and R6 (swapping wheat replants
  to tomato, scaled by tomato demand). We grow tomatoes only through V45's gated day-18 program on the
  4th quadrant.
- **Eggs** come from R8: geese are her default animal wherever neither Yarn nor two milk shops lead the
  route, so she carries 6-7 geese in most games where our routes carry 2-3.
- **Melon** comes from R9: a second, small melon wave that sells after the first glut clears.

Underneath all three is one structural choice: **she keeps land uncommitted until more demand is
visible.** Our tape plants its full strawberry quota by day 11 on land she holds back for day 12.

## Limits

- Thresholds in R5, R6 and R7 are fitted to 30 games; several cells have 2-4 games (e.g. 4 tomato
  shops: n = 2). A reimplementation should treat them as a starting table, not as her code.
- Her worker routing is observed but not reconstructed. Tomatoes need servicing on days 8-11 after
  planting; our chassis's wheat-cycle visits do not provide that, which is the component whose absence
  sank our earlier crop-cohort attempts.
- Her sale schedule was not reconstructed here; the tape test showed her strawberry timing (164/unit
  vs our 148) contributes, but its rule is not yet extracted.
- Majkel1337 cannot be analysed this way (nondeterministic).
