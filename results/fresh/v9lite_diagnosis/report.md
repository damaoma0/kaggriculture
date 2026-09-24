# V9-lite diagnosis (2026-09-24)

Framing: 56525017 is ONE live build (V9-lite search on top of y3 on top of m1). All "vs y3"/"vs m1"
numbers below are PANEL measurements of what one layer adds, not live head-to-heads.

## A. 2750-3000 exact panel (185 games) (n=184)

- y3 - m1 (Yarn layer alone): mean +308 (95% CI +206..+418), sum +56,684, better/worse/same 71/18/95
- v9litem1pkg - m1 (V9 search alone): mean +631 (95% CI +333..+956), sum +116,161, better/worse/same 32/7/145
- combined - m1 (total): mean +923 (95% CI +621..+1,247), sum +169,828, better/worse/same 82/21/81
- combined - y3 (what V9 search adds on top of y3): mean +615 (95% CI +339..+922), sum +113,144, better/worse/same 32/7/145
- own cash, combined - y3: mean +210 (95% CI -39..+495), sum +38,628, better/worse/same 23/16/145
- rival cash, combined - y3: mean -405 (95% CI -689..-161), sum -74,516, better/worse/same 14/25/145
- concentration of (combined - y3): top5 = 40% of net total gain, 36% of the sum of positive deltas; top10 = 58% of the sum of positive deltas
- own revenue delta (combined-y3), top products: [('CARROT', -47297), ('MILK', 30600), ('WOOL', 21530), ('STRAWBERRY', 13763), ('WHEAT', -12455), ('TOMATO', 10056)]
- note: m1/y3 (p2750eval schema) have no itemized rival_revenue, only a rival cash total; rival product deltas suppressed here
- by source: {'own_ladder': {'n': 81, 'mean': 625.5802469135803, 'sum': 50672.0}, 'team_vs_team': {'n': 103, 'mean': 606.5242718446602, 'sum': 62472.0}}
- worst5: [{'key': '112616230', 'comb_minus_y3': -1366.0}, {'key': '112093957', 'comb_minus_y3': -1413.0}, {'key': '112460119', 'comb_minus_y3': -2182.0}, {'key': '112612492', 'comb_minus_y3': -2230.0}, {'key': '112616240', 'comb_minus_y3': -4852.0}]
- best5: [{'key': '112617395', 'comb_minus_y3': 12033.0}, {'key': '112181121', 'comb_minus_y3': 9498.0}, {'key': '112583218', 'comb_minus_y3': 8814.0}, {'key': '112612772', 'comb_minus_y3': 7679.0}, {'key': '112200188', 'comb_minus_y3': 7663.0}]

## B. Live V56 paired (120 games/build) (n=120)

- y3 - m1 (Yarn layer alone): mean +178 (95% CI -57..+374), sum +21,360, better/worse/same 32/16/72
- v9litem1pkg - m1 (V9 search alone): mean +847 (95% CI +314..+1,443), sum +101,634, better/worse/same 26/8/86
- combined - m1 (total): mean +1,000 (95% CI +397..+1,649), sum +120,030, better/worse/same 43/16/61
- combined - y3 (what V9 search adds on top of y3): mean +822 (95% CI +266..+1,433), sum +98,670, better/worse/same 21/8/91
- own cash, combined - y3: mean +1,403 (95% CI +433..+2,407), sum +168,383, better/worse/same 24/5/91
- rival cash, combined - y3: mean +581 (95% CI -597..+1,635), sum +69,713, better/worse/same 21/8/91
- concentration of (combined - y3): top5 = 64% of net total gain, 50% of the sum of positive deltas; top10 = 76% of the sum of positive deltas
- own revenue delta (combined-y3), top products: [('WOOL', 62731), ('MILK', 44739), ('STRAWBERRY', 36563), ('CARROT', -10322), ('WHEAT', -7128), ('TOMATO', 3699)]
- rival revenue delta (combined-y3), top products: [('WOOL', 64058), ('MILK', 44089), ('STRAWBERRY', 34245), ('CARROT', -9914), ('WHEAT', -5316), ('TOMATO', 3811)]
- worst5: [{'key': '(1449981328, 1)', 'comb_minus_y3': -1524.0}, {'key': '(1921634684, 0)', 'comb_minus_y3': -5476.0}, {'key': '(1921634684, 1)', 'comb_minus_y3': -5476.0}, {'key': '(1455671948, 1)', 'comb_minus_y3': -5797.0}, {'key': '(1455671948, 0)', 'comb_minus_y3': -7430.0}]
- best5: [{'key': '(1779242936, 0)', 'comb_minus_y3': 16428.0}, {'key': '(1779242936, 1)', 'comb_minus_y3': 16428.0}, {'key': '(324432268, 0)', 'comb_minus_y3': 10931.0}, {'key': '(324432268, 1)', 'comb_minus_y3': 10560.0}, {'key': '(256822585, 0)', 'comb_minus_y3': 9038.0}]

## C. 180 ladder worlds (3-way) (n=180)

- y3 - m1 (Yarn layer alone): mean +183 (95% CI +105..+266), sum +33,016, better/worse/same 57/19/104
- combined - m1 (total): mean +854 (95% CI +492..+1,264), sum +153,803, better/worse/same 71/24/85
- combined - y3 (what V9 search adds on top of y3): mean +671 (95% CI +328..+1,062), sum +120,787, better/worse/same 26/11/143
- worst5: [{'key': 112282761, 'comb_minus_y3': -2564.0}, {'key': 111069352, 'comb_minus_y3': -2585.0}, {'key': 112187400, 'comb_minus_y3': -2791.0}, {'key': 110963585, 'comb_minus_y3': -2993.0}, {'key': 111159575, 'comb_minus_y3': -3093.0}]
- best5: [{'key': 111858516, 'comb_minus_y3': 15989.0}, {'key': 111362566, 'comb_minus_y3': 11344.0}, {'key': 111721810, 'comb_minus_y3': 10603.0}, {'key': 110963800, 'comb_minus_y3': 9904.0}, {'key': 112181121, 'comb_minus_y3': 9498.0}]

## D. Switch-day / product breakdown of the V9 layer's gain over y3 (72-world diag set)

n=72  mean margin delta +3,095

by switch day: {'12': {'n': 46, 'mean': 3484.586956521739, 'sum': 160291.0}, '12,15': {'n': 4, 'mean': 7985.0, 'sum': 31940.0}, '12,15,18': {'n': 1, 'mean': 2877.0, 'sum': 2877.0}, '12,18': {'n': 1, 'mean': 2614.0, 'sum': 2614.0}, '15': {'n': 16, 'mean': 1395.75, 'sum': 22332.0}, '18': {'n': 4, 'mean': 695.5, 'sum': 2782.0}}

top5 share of total gain: 27%; top10: 46%

own units delta: wool +567  milk +538  strawberry +176

worst5: [{'ep': 111069352, 'd_margin': -2585.0, 'switch_days': [12]}, {'ep': 112187400, 'd_margin': -2791.0, 'switch_days': [15]}, {'ep': 110963585, 'd_margin': -2993.0, 'switch_days': [12]}, {'ep': 111159575, 'd_margin': -3093.0, 'switch_days': [12]}, {'ep': 112616240, 'd_margin': -4852.0, 'switch_days': [12]}]

best5: [{'ep': 111858516, 'd_margin': 15989.0, 'switch_days': [12]}, {'ep': 112617395, 'd_margin': 12033.0, 'switch_days': [12]}, {'ep': 111362566, 'd_margin': 11344.0, 'switch_days': [12, 15]}, {'ep': 111721810, 'd_margin': 10603.0, 'switch_days': [15]}, {'ep': 110963800, 'd_margin': 9904.0, 'switch_days': [12]}]


## E. LIVE combined build (56525017) losing ladder games (17 of 79 completed)

replayed: 15/17; dollar-exact match to recorded result: 15/15

a V9 switch fired in 1/15 losses; no switch fired in 14/15

of the 1 losses where a switch fired, the no-switch counterfactual (native y3, same recorded world) would have scored better in 0


| ep | opp | recorded margin | diag margin | y3-noswitch margin | switch? | day(s) | y3 better w/o switch | sheep_lost d/y3 | orphan_days d/y3 | yarn_service d/y3 |
|---|---|---|---|---|---|---|---|---|---|---|
| 112977769 | in blue | -6344 | -6344 | -12316 | YES | [12] | no | 0/0 | 0/0 | 0/3 |
| 112977788 | Kyoungwon Jeong | -5492 | -5492 | -5492 | no | [] | no | 0/0 | 0/0 | 10/10 |
| 112967455 | Salem Ali | -5040 | -5040 | -5040 | no | [] | no | 0/0 | 0/0 | 0/0 |
| 112957860 | mogura2.0 | -2850 | -2850 | -2850 | no | [] | no | 0/0 | 5/5 | 33/33 |
| 112969589 | Ryo | -1845 | -1845 | -1845 | no | [] | no | 0/0 | 0/0 | 0/0 |
| 112981251 | track | -1510 | -1510 | -1510 | no | [] | no | 0/0 | 0/0 | 0/0 |
| 112983557 | beeyan | -1400 | -1400 | -1400 | no | [] | no | 0/0 | 0/0 | 8/8 |
| 112974276 | artem3605 | -1150 | -1150 | -1150 | no | [] | no | 0/0 | 0/0 | 0/0 |
| 112967296 | Maximo Uribarri | -1147 | -1147 | -1147 | no | [] | no | 0/0 | 0/0 | 0/0 |
| 112990676 | Aniket Sharma | -1128 | -1128 | -1128 | no | [] | no | 0/0 | 0/0 | 7/7 |
| 112952353 | itsuki-data | -948 | -948 | -948 | no | [] | no | 0/0 | 0/0 | 0/0 |
| 112962570 | Ishan Karnick | -932 | -932 | -932 | no | [] | no | 0/0 | 5/5 | 33/33 |
| 112936031 | 栗ご飯 | -465 | -465 | -465 | no | [] | no | 0/0 | 0/0 | 0/0 |
| 112979068 | datnt114 | -398 | -398 | -398 | no | [] | no | 0/0 | 1/1 | 11/11 |
| 112964929 | Raymond Parker | -19 | -19 | -19 | no | [] | no | 0/0 | 0/0 | 0/0 |
| 112996502 | -- | -1975 | NOT REPLAYED | | | | | | | |
| 112998531 | -- | -522 | NOT REPLAYED | | | | | | | |

## F. Ladder tracking (56525017 vs 56395605)

```
2026-09-24 21:51  submission 56525017: 84 games
  56525017: first 84 games 65-19 (77%), mean margin +7836 | 2500-2750 17-6  2750-3000 0-2  <2500 46-11  unrated 2-0
  56395605: first 84 games 63-21 (75%), mean margin +7849 | 2500-2750 5-5  <2500 58-16

```

```
56525017: rating 2652.2  games 84
   games    1-  40 (2026-09-24..2026-09-24): 37-3 (92%), margin  +13172; vs >=2500: 3-2
   games   41-  80 (2026-09-24..2026-09-24): 26-14 (65%), margin   +3309; vs >=2500: 13-5
   games   81-  84 (2026-09-24..2026-09-24): 2-2 (50%), margin    -263; vs >=2500: 1-1
56395605: rating 2739.9  games 490
   games    1-  40 (2026-09-20..2026-09-20): 32-8 (80%), margin  +12227; vs >=2500: 2-1
   games   41-  80 (2026-09-20..2026-09-20): 30-10 (75%), margin   +4641; vs >=2500: 3-2
   games   81- 120 (2026-09-20..2026-09-21): 31-9 (78%), margin   +5856; vs >=2500: 7-5
   games  121- 160 (2026-09-21..2026-09-21): 24-16 (60%), margin   +2297; vs >=2500: 8-2
   games  161- 200 (2026-09-21..2026-09-21): 24-16 (60%), margin   +1355; vs >=2500: 5-4
   games  201- 240 (2026-09-21..2026-09-22): 31-9 (78%), margin   +3992; vs >=2500: 8-3
   games  241- 280 (2026-09-22..2026-09-22): 25-15 (62%), margin   +1470; vs >=2500: 15-9
   games  281- 320 (2026-09-22..2026-09-22): 27-13 (68%), margin   +1521; vs >=2500: 10-8
   games  321- 360 (2026-09-22..2026-09-23): 21-19 (52%), margin   +2276; vs >=2500: 21-16
   games  361- 400 (2026-09-23..2026-09-23): 22-18 (55%), margin    -306; vs >=2500: 21-15
   games  401- 440 (2026-09-23..2026-09-24): 24-16 (60%), margin    +623; vs >=2500: 24-16
   games  441- 480 (2026-09-24..2026-09-24): 22-18 (55%), margin    -886; vs >=2500: 22-18
   games  481- 490 (2026-09-24..2026-09-24): 4-6 (40%), margin   -4882; vs >=2500: 4-6

```
