# Harvest-timing economics (540 leader games, 216749 harvest events)

Coins per harvest event for shifting the HARVEST 1 day earlier / later. earlier = -loss1*price - trend + tile_rate; later = +gain1*price + trend - tile_rate (trend, tile_rate in coins/day; tile_rate = 0 for ongoing crops, which keep the tile regardless of harvest timing). loss1/decay from the corpus; gain1 modeled (one-time crops) or observed (ongoing crops, see module docstring).

Reading notes:
- For crops harvested right at the earliest legal age (melon age 10 = first_yield_day; strawberry/tomato's first production), the "1 day earlier" column is a counterfactual (HARVEST is illegal one day sooner) -- it measures the value of that last pre-harvest watering, not an available action. The "1 day later" column is the real, available lever for those crops.
- A negative "units gained by 1d later" is the growth-window rule turning into the decay rule: once the observed harvest is already at the window's last day (wheat age 4, carrot age 3), the model's next day is past the window, so decay ticks (-1 unit/2h) apply instead of a growth bonus -- this is why late-game wheat / carrot show large negative "1 day later" values even at "0% past window" (they are AT the edge, not past it; one_more_day_gain is forward-looking).
- tile $/day is pooled revenue / pooled tile-days for one-time-crop plantings that were harvested at least once, bucketed by PLANTING period, applied to the same-numbered HARVEST period (leaders replant the same tile the same day 39-96% of the time depending on crop/period -- see harvest_timing_report.py's "replanted same day" column; this is a same-bucket proxy, not a lagged one).


## WHEAT (harvest-allowed age 2, window end 4, held cap 6, one-time (frees the tile))
| period | n | mean age | price/unit | trend $/day | tile $/day | units lost, 1d earlier | units gained, 1d later | past window | decay units so far | **1 day earlier** | **1 day later** |
|---|---|---|---|---|---|---|---|---|---|---|---|
| d0-5 | 5517 | 2.58 | 29.3 | +0.33 | +29.9 | 1.00 | +0.48 | 0% | 0.00 | +0.3 | -15.4 |
| d6-11 | 8538 | 2.51 | 37.7 | +1.89 | +48.3 | 1.10 | +0.51 | 0% | 0.00 | +5.1 | -27.3 |
| d12-17 | 26464 | 3.29 | 38.9 | -0.53 | +51.0 | 1.43 | -1.15 | 0% | 0.00 | -4.4 | -96.2 |
| d18-23 | 20694 | 3.34 | 36.4 | -0.28 | +49.3 | 1.60 | -1.22 | 0% | 0.00 | -8.7 | -93.8 |
| d24-29 | 32813 | 3.26 | 30.1 | -2.00 | +37.4 | 1.47 | -1.20 | 0% | 0.00 | -4.7 | -75.4 |
  tile $/day sample (plantings with >=1 harvest, by PLANTING period): d0-5 n=6224, d6-11 n=24124, d12-17 n=20948, d18-23 n=26513, d24-29 n=16217

## CARROT (harvest-allowed age 2, window end 3, held cap 4, one-time (frees the tile))
| period | n | mean age | price/unit | trend $/day | tile $/day | units lost, 1d earlier | units gained, 1d later | past window | decay units so far | **1 day earlier** | **1 day later** |
|---|---|---|---|---|---|---|---|---|---|---|---|
| d6-11 | 152 | 2.49 | 45.8 | +0.93 | +44.8 | 1.00 | -0.95 | 0% | 0.00 | -2.0 | -87.2 |
| d12-17 | 4558 | 2.77 | 44.2 | -0.24 | +45.4 | 1.01 | -2.02 | 0% | 0.00 | +1.2 | -135.1 |
| d18-23 | 8019 | 2.79 | 43.9 | +0.15 | +48.8 | 1.09 | -2.27 | 0% | 0.00 | +0.6 | -148.2 |
| d24-29 | 19891 | 2.76 | 39.9 | -1.64 | +44.3 | 1.07 | -2.16 | 0% | 0.00 | +3.3 | -132.2 |
  tile $/day sample (plantings with >=1 harvest, by PLANTING period): d6-11 n=1944, d12-17 n=5785, d18-23 n=12092, d24-29 n=12799

## MELON (harvest-allowed age 10, window end 12, held cap 6, one-time (frees the tile))
| period | n | mean age | price/unit | trend $/day | tile $/day | units lost, 1d earlier | units gained, 1d later | past window | decay units so far | **1 day earlier** | **1 day later** |
|---|---|---|---|---|---|---|---|---|---|---|---|
| d6-11 | 5169 | 10.00 | 226.3 | -50.31 | +74.1 | 1.00 | +0.00 | 0% | 0.00 | -101.9 | -124.0 |
| d12-17 | 292 | 10.03 | 155.4 | -4.02 | +62.8 | 0.90 | +0.01 | 0% | 0.00 | -73.2 | -65.2 |
| d18-23 | 45 | 10.02 | 102.6 | -13.27 | - | 0.44 | +0.00 | 0% | 0.00 | -32.3 | -13.3 |
| d24-29 | 1 | 10.00 | 108.7 | -1.12 | - | 0.00 | +0.00 | 0% | 0.00 | +1.1 | -1.1 |
  tile $/day sample (plantings with >=1 harvest, by PLANTING period): d0-5 n=5415, d6-11 n=89, d12-17 n=3

## TOMATO (harvest-allowed age 8, decay starts the day after the 4th production, held cap 4, ongoing (tile stays occupied))
| period | n | mean age | price/unit | trend $/day | tile $/day | units lost, 1d earlier | units gained, 1d later | 4th+ prod. banked | decay units so far | **1 day earlier** | **1 day later** |
|---|---|---|---|---|---|---|---|---|---|---|---|
| d12-17 | 668 | 8.06 | 77.8 | +3.27 | - | 0.00 | +0.22 | 2% | 0.00 | -3.3 | +20.7 |
| d18-23 | 11826 | 9.43 | 72.8 | -0.82 | - | 0.00 | -0.07 | 46% | 0.00 | +0.8 | -6.1 |
| d24-29 | 10820 | 9.74 | 68.6 | -0.48 | - | 0.00 | -0.68 | 59% | 0.00 | +0.5 | -47.2 |

## STRAWBERRY (harvest-allowed age 10, decay starts the day after the 4th production, held cap 4, ongoing (tile stays occupied))
| period | n | mean age | price/unit | trend $/day | tile $/day | units lost, 1d earlier | units gained, 1d later | 4th+ prod. banked | decay units so far | **1 day earlier** | **1 day later** |
|---|---|---|---|---|---|---|---|---|---|---|---|
| d6-11 | 157 | 10.00 | 141.7* | - | - | 0.00 | +0.08 | 0% | 0.00 | +0.0 | +11.7 |
| d12-17 | 18622 | 11.52 | 188.0 | -2.91 | - | 0.00 | -0.10 | 23% | 0.00 | +2.9 | -22.4 |
| d18-23 | 27883 | 13.40 | 138.2 | -11.75 | - | 0.00 | -0.10 | 54% | 0.00 | +11.8 | -25.5 |
| d24-29 | 14620 | 14.06 | 109.9 | +2.44 | - | -0.00 | -0.44 | 68% | 0.00 | -2.4 | -45.7 |
  * = no sales of this crop recorded in this period's days (pooled); price/unit falls back to the crop's whole-corpus average, and the period's own trend ('-') is genuinely unavailable.

## A few hours earlier / later (not a smooth per-hour rate; reported as discrete effects)

One-time crops (wheat/carrot/melon) have a real within-day lever: harvesting before vs after the day's WATER changes the units in THIS harvest (the growth-window bonus is credited the moment you water). Ongoing crops (tomato/strawberry) do not: their daily +1/+2 is decided by yesterday's watering and paid out at the automatic end-of-day refresh regardless of when during the day you press HARVEST, so the harvest hour only affects which SALE price you catch (see the intraday price pointer below), never the unit count.

| crop | harvesting before today's WATER costs (coins, when in growth window & unwatered) | share of harvests unwatered-before, in window | decay tick (coins / 2h, once decay has started) |
|---|---|---|---|
| WHEAT | +54.1 | 2% | +34.2 |
| CARROT | +54.7 | 4% | +41.3 |
| MELON | +217.9 | 1% | +215.7 |
| TOMATO | n/a (production fixed by yesterday's watering) | n/a | +70.4 |
| STRAWBERRY | n/a (production fixed by yesterday's watering) | n/a | +141.7 |

decay tick eligibility: one-time crops once age > the window end (wheat 4, carrot 3, melon 12); ongoing crops once 4 productions have banked (decay starts the day after the 4th, independent of age).

Intraday price trend (continuous, by hour of the ready hour): see harvest_timing_market.py's "By hour bin" tables (results/fresh/harvest_timing_20260925/market/credit_report.md) -- built from the same replays, already broken out by hour bin per product.
