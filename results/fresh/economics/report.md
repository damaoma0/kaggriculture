# Fresh crop economics: reproducible baseline

Source: installed kaggle-environments engine. Crop yields are probed through its unit-action and daily-refresh functions; sales use its rounded price function and $1 floor behavior.

## Assumptions

No fertilizer, opponent trades, or town demand. Each product begins at equilibrium inventory. Daily watering; ongoing crops harvested after each production. Sell output sequentially. Seed costs only. Storage, travel, hiring, cash-flow constraints, and the 30-day horizon are excluded. This is a reference curve, not an agent or an optimal allocation.

## Engine-checked harvests

| Crop | Harvests (age: units) | Total units |
|---|---|---:|
| WHEAT | 4: 4 | 4 |
| CARROT | 3: 3 | 3 |
| TOMATO | 8: 1, 9: 1, 10: 1, 11: 1 | 4 |
| STRAWBERRY | 10: 1, 12: 1, 14: 1, 16: 1 | 4 |
| MELON | 10: 6 | 6 |

## Seed return versus production scale

ROE = (sale revenue - seed cost) / seed cost. Even one plant moves prices; these are discrete sale calculations.

| Plants | Wheat | Carrot | Tomato | Strawberry | Melon |
|---:|---:|---:|---:|---:|---:|
| 1 | 870.0% | 410.0% | 358.0% | 368.0% | 1775.0% |
| 10 | 807.0% | 363.5% | 296.0% | 230.2% | 1687.6% |
| 25 | 777.2% | 326.0% | 245.4% | 53.9% | 1218.5% |
| 50 | 758.6% | 284.3% | 188.8% | -21.1% | 565.7% |
| 100 | 731.3% | 225.5% | 109.1% | -58.5% | 236.6% |

## Interpretation and next layer

Melon has max_yield_day=12, but its initial unit plus watering bonuses on ages 6-10 reach six units at age 10. Fertilizer cannot permit harvesting before first_yield_day=10.

Nominal tile-days use last harvest age, matching the earlier discussion; a real schedule also needs planting/harvesting time and daily action ordering. Daily watering here is not a minimum-labour schedule.

Next, optimize legal watering/fertilizer schedules, price fertilizer at its opportunity cost, and include movement, hiring, land, storage, and town/opponent supply. Greedy marginal allocation is not guaranteed optimal when these constraints and delayed revenues interact.
