# Sale timing and the rival's windfall (2026-09-26)

Data: `scripts/season_timing.py KE4` on the 40 DSM confirmation worlds (every successful SELL of both players by product,
day and hour; our harvests; every midnight dump), `scripts/season_timing_report.py`; results
`results/fresh/threads_20260928/timing_ke4_40.json`. KE4 = best margin branch (margin gap to DSM -22.1k a world, of which
the rival's extra revenue +11.1k; wool +4.0k, strawberry +3.5k, milk +1.8k).

## We sell at hour 1, DSM spreads its sales over the day

| product | units sold DSM / KE4 | KE4 units at hour 1 | DSM's top hours | our price DSM / KE4 | harvest -> sale DSM / KE4 |
|---|---|---|---|---|---|
| wool | 134 / 134 | 93 | h1 19, h21 15, h9 14, h13 12 | 155.1 / 150.0 | 29.6 / 31.4 h |
| milk | 189 / 199 | 112 | h21 29, h1 27, h17 27, h13 23 | 108.0 / 96.6 | 15.5 / 21.1 h |
| strawberry | 237 / 224 | 200 | h0 51, h1 28, h13 20, h17 20 | 146.2 / 143.4 | 18.6 / 16.7 h |

Units sold in hours 12-23, DSM / KE4: wool 49 / 28, strawberry 108 / 24, milk 90 / 41.

## The rival sells at hour 0, and its hour-0 price is set by the evening before

Rival units / price at hour 0 (DSM game -> KE4 game): wool 32 u 136 -> 177, strawberry 64 u 137 -> 157, milk 28 u
107 -> 126. The rival sells before our hour-1 dump; its price depends on the market stock left from the previous evening.
DSM's afternoon / evening sales (goods delivered during the day, sold within 0-3 hours) are not consumed by the shops
before dawn; our hour-1 dump is consumed during the day. Rival's extra revenue by our-hour block: wool h0-3 +1,771,
h20-23 +968; strawberry h0-3 +1,900, h20-23 +908; milk h0-3 +880, h20-23 +667: about 7.2k of the 9.4k on these three
products lands at dawn and late evening. Consistent with the leader shed-flow analysis (leaders sell 36-68% of the
night's carry after hour 11).

## Midnight dumps

KE4 deletes 69 units a world; 32.4 of them (47%) on the night of day 27, when `sd_tier_anim_harv_end = 27` makes every
animal harvest mandatory (carried 129 vs DSM 84). Arms KE6 / KE7 move that day to 28 / 29. Ordinary heavy night viewer:
`viz/dump_snapshot_112589990_d14.html` (`scripts/build_dump_snapshot.py`; KE4 carries 136, 36 deleted, midday drops 27;
DSM 84 carried, 55 delivered midday).

## Tests

- KT1 / KT2: KE4 + `sd_evening_sell` [WOOL, MILK, STRAWBERRY], half / all of the morning stock held and sold at hours 20-23.
- KT3 (always-on turnaround) not run: the turnaround's feasibility (no added lateness, detour <= 2, by hour 16) binds, not
  the overflow trigger (1 turnaround in 5 days either way).
