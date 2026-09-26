# Matching DSM's sale pattern (2026-09-26)

Data: KM1 (current candidate) vs DSM on the 40 DSM confirmation worlds, days 11-28. Scripts: `scripts/season_timing.py`
(sales / harvests by hour), `scripts/sale_pattern_stats.py` (patterns), `scripts/timing_counterfactual.py` and
`scripts/sale_pattern_cf.py` (exact market counterfactuals), `scripts/season_returns.py` (deliveries by hour).

## The price gap is about order against the rival

Price per unit, ours minus the rival's: DSM's games wool +28.2, milk +14.6, strawberry +15.7 (x units: +11.7k a world);
KM1's games wool -4.9, milk -5.1, strawberry -1.4 (-1.4k). Swing ~13.1k, two thirds of the remaining margin gap.

Shop consumption is a fixed schedule (engine `_town_consume`), so the market stock of a product at any moment = start
stock + everything sold so far by both players - bought - the fixed consumption; the price is a fixed function of it. The
rival sells the same units in every game, so its prices depend only on how many units we (or DSM) put in before it.

## DSM's pattern vs ours (share of each product's sales by hour block; sold the day it was harvested)

| product | DSM | KM1 | same day DSM / KM1 |
|---|---|---|---|
| wool | 31% h0-3, 9-18% in every later block | 58% h0-3, 20% h4-7, ~5% midday, 17% h20-23 | 45% / 28% |
| milk | 13-25% in every block | 54% h0-3, 21% h4-7, 14% h20-23 | 55% / 36% |
| strawberry | 37% h0-3, 32% h12-19, 13% h20-23 (32% sold 2+ days after harvest) | 87% h0-3, 13% h20-23 | 20% / 1% |
| egg | 76% h20-23 | 86% h0-3 | 27% / 13% |
| wheat | 37% h0-3, 27% h20-23 (harvest->sale median 114 h) | 57% h0-3 (140 h) | |

Cumulative hour-of-day profiles: `results/fresh/threads_20260928/dsm_hourly_profile.json`.

WHY OURS DIFFERS: the market's quota is `T.cum_sold[d] - sold so far`, DSM's cumulative sales to the END of the day
(the semantic plan records only daily sales), so at hour 1 we may sell everything DSM sells all day, and the night's dump
is in the shed: we sell it all at dawn. Deliveries (dsell) are sold at once; wheat is held as a two-day feed reserve.

## How much is reachable (exact market counterfactual, our same units, frozen rival)

A: our k-th unit at DSM's k-th sale time: margin +13.8k a world (rival -7.3k, ours +6.4k); our average prices then land
on DSM's (milk 95 -> ~107 vs DSM 108, wool 146 -> ~153 vs 155, strawberry 139 -> ~148 vs 146).
B: the same, but never before the unit is in our shed (dump units from hour 1): margin +6.7k (ours +7.0k, rival +0.4k):
wheat +3.0k, strawberry +1.5k, milk +1.1k, wool +0.9k, fertilizer ~0. B = a market policy alone.
A - B ~7.1k needs earlier deliveries (almost all of the rival-side effect).

Deliveries to the shed during the day, cumulative per farm-day, by hour 6 / 8 / 12 / 16 / whole day:
milk DSM 3.2/3.7/4.2/4.6/5.9, KS1 1.5/1.9/2.5/2.6/3.7, KM1 1.5/2.7/3.6/3.8/4.6; wool DSM 1.7/2.1/2.5/2.7/3.7, KS1
0.4/0.5/0.7/0.8/1.5, KM1 0.2/1.5/1.8/1.8/2.4; strawberry DSM 0/0/0.2/1.2/2.8, KS1 and KM1 ~0.2 all day.

## Proposed changes (not built)

1. Hourly quota: quota(d, h) = cum_sold[d-1] + F_p(h) x sold[d], F_p = DSM's cumulative hour-of-day profile (constants
   from data; deployable, the semantic plan gives daily totals); keep the catch-up when behind. Target: B's
   strawberry / milk / wool part (~3.5k).
2. Wheat on DSM's pace: sell wheat by the same hourly quota instead of holding a two-day feed reserve; buy feed wheat just
   in time (sd_wheat_jit exists). Target: B's wheat part (~3.0k, rival -2.9k); buy-backs not in the counterfactual.
3. Earlier deliveries (the A - B part, mostly rival-side): milk / wool before hour 6 (DSM harvests pens on or next to the
   shed tiles in hours 1-3), strawberries in the afternoon.
Caveats: frozen rival; our counterfactual prices use the stock at the start of each step (within-step order approximate).
