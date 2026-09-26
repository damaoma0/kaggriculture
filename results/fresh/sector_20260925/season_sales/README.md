# Season sales and fertilizer, leader vs C1 (tile exact from the day-11 morning, days 11-29), 2026-09-28

Produced by scripts/season_sales_replay.py (replays the leader tape and our season streams in the same world, logging both
players' SELL / BUY_PRODUCT commits). Replay finals reproduce the season runs exactly.

Sales revenue days 11-29, ours (C1) minus the leader's own, and the recorded opponent in our run minus in the leader game:
| world | ours | opponent | margin effect |
|---|---:|---:|---:|
| 112444381 | -12,865 | +4,780 | -17,645 |
| 112673479 | -21,718 | +9,540 | -31,258 |
| 112661570 | +644 | +34,472 | -33,828 |
- Our realized prices are not worse (usually higher, fewer units); the own gap is VOLUME (wheat 152 vs 401, 263 vs 518, 129 vs 477).
- The opponent sells the same units in both runs; its prices are higher in ours because we supply less to the shared market.
- 112661570 wool: the leader sells heavily (42 on day 15, 62 on day 18); wool crashes 240 -> 114 (day 21) -> ~50; in our run it
  stays 210-230 to day 24. Our wool revenue +16.5k, the opponent's +26.8k -> -10.3k margin.

Fertilizer days 11-29 (collected / available animal-days, applied, sold):
| world | leader | C1 |
|---|---|---|
| 112444381 | 401/411 (98%), 233, 186 | 324/397 (82%), 114, 225 |
| 112673479 | 380/388 (98%), 216, 177 | 306/397 (77%), 116, 205 |
| 112661570 | 424/441 (96%), 226, 215 | 242/488 (50%), 72, 188 |
The leader collects 93-99% in every period even at a sale price of 1-25; our collection falls with the price
(112661570: 63% -> 56% -> 28%): the collect job is valued at the sale price, so late collections are dropped.
