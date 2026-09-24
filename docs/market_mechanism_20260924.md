# Why the rival earns more against y3 than against the leader (market mechanism, 2026-09-24)

Status: FINAL (2026-09-24, ~22:30). 54 leader worlds replayed (all 54 LEADER replays reproduce both recorded final
cash totals); 35 intact after dropping 19 where the rival's final cash in the y3 run fell below 0.8x its recorded final.

## Question
y3 placed in a 3000+ leader's recorded world (same seed, forced shops, the rival replaying its recorded actions) earns
about the leader's own cash, yet the same rival earns ~+9k more against y3. Per product the rival's PRICE is higher
(strawberry +27.8/unit, milk +24.1, wool +33.5) at about the same own volumes. Mechanism, and can we reproduce it?

## Tools (new files only)
- `scripts/extract_market_events.py <agent.py|LEADER>[,...] <out_dir> <tape>...` — replays a leader world (LEADER) or
  puts our agent in the leader's seat and logs every successful market unit of BOTH players with (step, order index,
  lockstep iteration, player, op, item, price, market inventory before), per-step market inventory before the market
  phase and after town consumption, both sheds, public on-board yield per product, and HARVEST gains.
  `_process_market` is replaced by a logging copy of the engine function (installed engine byte-identical to
  `data/kaggriculture.py`). Every LEADER replay reproduces both recorded final cash totals. The in-process memory
  gate waits while (free + own RSS) < 3 GB.
- `scripts/analyze_market_events.py [agent_dir] [leader_dir] [collapse]` — exact re-pricing of every unit from
  (units sold, units bought, town consumption, lockstep positions); validated against the logged prices for all 9
  products in every log (0 mismatches). Town consumption per step is identical in the leader world and the y3 world
  (forced shops), so a rival unit's price differs between the worlds ONLY through the market inventory it is quoted
  from. Cross-world swaps, an exact decomposition, sale-timing rule replays, calendar transplants, reaction tests.
- `agents/mgt_y3_selltime.py` — copy of mgt_y3 plus a last-defined entry point that sells STRAWBERRY/MILK/WOOL as
  soon as they reach the shed (SELLTIME_MODE=asap). Research only.
- Logs: `results/fresh/market_events_20260924/{LEADER,mgt_y3,mgt_y3_selltime}/<episode>.json.gz`,
  summary `results/fresh/market_events_20260924/summary_mgt_y3.json`.

## Engine facts that decide the mechanism (data/kaggriculture.py)
- A product's price is a pure function of one number, its market inventory: `price = f(inventory)`.
  inventory = 10000 + every unit sold at a price > 1 (both players) - units bought - town consumption.
  Consumption is a fixed schedule (town centre 1/day; each shop 1 per 4 steps, single-product shops 2), applied
  after the market phase, independent of anyone's sales. Prices "recover" only through that consumption.
- Therefore a unit's price depends only on the CUMULATIVE units sold before it (by anyone) minus consumption so far.
  A unit we sold three days before a rival unit depresses it exactly as much as one sold in the same step.
- Sales at the $1 floor do NOT add to inventory: they earn $1 and leave everybody's later prices untouched.
- Within a step: order index i of both players is processed together, units interleaved one at a time; both
  players' k-th units at the same index are quoted from the SAME inventory. A lower index sells completely first.
- Shape: below I0 (scarcity) strawberry/milk are sqrt (flat far from I0: ~0.3-1 $/unit), above I0 (glut) linear
  (strawberry 1.92 $/unit, milk 2.10), wool/melon quadratic. The scarcity premium built up while nobody sells is
  collected cheaply by the FIRST seller; whoever starts later sells into a stock already pushed toward/above I0.

## Method
For each world: L = leader world (logged), Y = y3 world (logged), S = swap (rival's L schedule, y3's Y schedule),
all re-priced exactly. Rival revenue(Y) - rival revenue(L) = [S - L] "our schedule" + [Y - S] "rival's own schedule"
(the rival's replay differs only via weeds/cash). For each rival unit u the inventory difference S - L splits
exactly into: dA production calendar (our units that had ARRIVED in our shed before u), -dH holding (arrived but
unsold), -dF our $1-floor sales before u, and the rival's own floor units. The price change of u is allocated to
those parts in proportion (one secant per unit; 0 unexplained). Windows: same step / 1-3 steps / 4-23 steps /
1-2 days / >=3 days before u, over our inventory-moving units.

## Results (35 intact worlds; per world, y3 world minus leader world)
The finding replicates: y3 earns 1.08x the leader's cash, the rival +12.5k; rival price per unit strawberry
141.9 -> 173.1 (+31.3), milk 89.2 -> 117.9 (+28.7), wool 117.8 -> 157.0 (+39.2), melon 192.3 -> 169.1 (-23.2), at
rival volumes -7/-8/-11/-4 units. Exact decomposition (`results/fresh/market_events_20260924/analysis_mgt_y3.txt`):

| | strawberry | milk | wool | melon |
|---|---|---|---|---|
| rival revenue | +5017 | +3943 | +4284 | -2474 |
| = our schedule (rival fixed) | +5650 | +3648 | +5838 | -2068 |
| + rival's own schedule | -633 | +296 | -1554 | -406 |
| our schedule: production calendar (not yet arrived) | +6146 | +3036 | +5388 | -2142 |
| our schedule: holding (arrived, unsold) | -717 | -141 | -466 | +67 |
| our schedule: our $1-floor sales | +171 | +427 | +1248 | 0 |
| our schedule: rival's own floor units | +50 | +327 | -332 | +7 |
| window: same step | -22 | +84 | +122 | -21 |
| window: 1-3 steps before | -32 | -17 | +26 | -201 |
| window: 4-23 steps before | -252 | +327 | -312 | -340 |
| window: 1-2 days before | +284 | +1001 | -167 | -634 |
| window: >=3 days before | +5623 | +1927 | +6501 | -878 |
| our-schedule effect > 0 in (bootstrap 95% CI) | 32/35 (+4.2k..+7.1k) | 19/35 (+1.6k..+6.0k) | 34/35 (+3.5k..+8.5k) | |
| market stock - I0 at the rival's sales, L / Y | -20 / -51 | +35 / +24 | +30 / +12 | +62 / +74 |
| local slope $/unit at the rival's sales, L / Y | 1.32 / 0.94 | 1.89 / 1.72 | 3.01 / 1.98 | 1.44 / 1.70 |

Strawberry by leader team (our-schedule effect): MMPQ +3952 (6), MG +7849 (8), DECEM +3877 (6), Vadim +4186 (7),
DSM +8524 (7), Boey -981 (1). Dropped (collapsed rival) by team: DSM 4, Vadim 4, MMPQ 3, MG 3, DECEM 3, Boey 2.

Timing descriptors (leader / y3 / rival): strawberry first arrival day (median) 13 / 16 / 13, mean sale day 21.3 /
22.4 / 21.7, FIFO holding 10.0 / 3.7 / 13.5 steps, lot per selling step 3.0 / 5.5 / 5.4; share of units sold in a
step where the other side also sells 28% / 22% (rival 37%); within those steps ahead / interleaved / behind the
rival 20 / 71 / 9% (leader) vs 25 / 69 / 6% (y3). Milk and wool: same first-arrival day (8, 6) but the leader's
herd produces more early (wool sold before day 12: 28 vs 20); the leader holds LONGER (milk 9.2 vs 5.1 steps, wool
10.4 vs 5.4). Hours: both favour post-tick steps (t%4==1; shops consume at t%4==0 after the market phase).

Daily path, strawberry (mean of 35): units sold before the day, leader / y3 / rival, and the rival's mean price in
the leader world / y3 world: d14 5 / 0 / 2 (183 / 191); d16 24 / 0 / 14 (180 / 196); d18 55 / 24 / 42 (159 / 182);
d20 90 / 57 / 75 (126 / 164); d22 121 / 88 / 105 (113 / 145); d24 150 / 130 / 133 (109 / 143); d26 172 / 152 / 155
(114 / 150); d29 207 / 193 / 188 (110 / 141). Market stock minus I0 at day start, leader world -77 (d16), -3 (d21),
+10 (d24); y3 world -101, -39, -17. Same season volume, sold ~3 days earlier; the leader world's market sits 25-35
units fuller from day 16 on and every later rival unit pays for it. Wool: stock +47 vs +30 from day 21 (rival price
60 vs 106 at d24). Milk: +57 vs +32 at d29 (43 vs 96).

### Mechanism
The price is a function of the cumulative net stock and consumption is identical in both worlds, so the rival's
price falls by (slope) x (our inventory-moving units sold before its unit). 109% of the strawberry, 92% of the wool
and 83% of the milk effect is the PRODUCTION CALENDAR: the leader's units exist earlier. Same-step collisions,
within-step order and holding are ~0 or negative (the leader holds LONGER than y3). y3's $1-floor sales (7 / 14 / 20
units per world for strawberry / milk / wool vs the leader's 1 / 3 / 7) add 3% / 12% / 21%: a floor sale does not
move the stock. Melon runs the other way: everyone harvests on day 10 and y3 sells 21 more.
The early seller pays little for it: below I0 the strawberry/milk curve is sqrt (flat, ~1 $/unit), so the leader's
early units sell near the scarcity peak while pushing the stock toward I0, where the rival's later units meet the
steeper part (1.32 vs 0.94 $/unit at the rival's sales). The leader's own revenue ~= y3's (y3 minus leader:
strawberry -278, milk +2254, wool +2879); the rival's is much lower. y3's later calendar is the "cooperative" one
(combined revenue +4.7k strawberry, +6.2k milk, +7.2k wool higher in the y3 world).

### Deliberate or incidental
- The calendar is a FIXED opening: in the 600-game corpus (`data/leader_semantics`) DECEM, MMPQ, MG, DSM and Vadim
  plant their first strawberries on day 2 (MMPQ day 1) in 100/100 games each, exactly 3-4 plants by day 2 (IQR 0),
  and buy their first cow and sheep on day 0-1 in 100/100 games, before the first shop reveal and identical against
  every rival. In the 12 original worlds the leader plants on day 2, 10 plants by day 5, 3 sheep on day 3; y3 plants
  on day 5, 4 by day 5, 2 sheep. Incidental with respect to the rival.
- Sale steps: Mantel-Haenszel odds ratio of selling (given stock), stratified by hour x fresh/old stock, when the
  rival harvested in the last 2 steps: leader 2.26 / 1.76 / 2.25 (strawberry / milk / wool) vs y3 1.49 / 1.07 / 1.22
  (y3 cannot react: its OR is the synchrony baseline); rival sells in the next 3 steps (front-running check): 1.31 /
  1.32 / 1.35 vs 1.16 / 1.09 / 1.03. A weak excess association, either reaction or calendar synchrony (the leader and
  strong rivals share the day-2 opening; y3 is 3 days off). Its dollar value is <= 0 either way: holding and
  same-step components are -717 / -141 / -466 and -22 / +84 / +122.

### Rules for our agent (exact market replay; y3 production and the rival's schedule fixed; margin per world, 35 worlds)
| rule | strawberry | milk | wool |
|---|---|---|---|
| sell on arrival, order first | -280 | -172 | -149 |
| sell on arrival, after the rival in the step | -718 | -532 | -378 |
| post-tick aligned | -267 | -208 | -40 |
| oracle: hold up to 24 steps to sell in the rival's next selling step, first | +90 | +34 | +117 |
| hold 1 day | -975 | -906 | -744 |
| never sell at <= $1 / <= $10 (hold and retry) | -71 / -57 | +24 / +57 | +113 / +165 |
| leader's calendar at y3's volume (quantile transplant) | +2194 (own -715, rival -2909) | +391 | +3160 (own -773, rival -3934) |
| same units 1 / 2 / 3 days earlier | +605 / +1589 / +2814 | +554 / +896 / +1447 | +877 / +1088 / +1452 |

The leader's calendar for strawberry + milk + wool: +5745 margin per world (market-only), flips 8 of y3's 20 losses in
these 35 worlds (strawberry alone +2194, 3 flips). The floor guard holds up to 67-86 units (shed-cap risk). Melon
calendar shifts are infeasible (all melons mature on day 10).

## Live check: pure sale-timing rule (agents/mgt_y3_selltime.py, SELLTIME_MODE=asap)
Strawberry/milk/wool sold the step they reach the shed (SELL 99 merged or put first); 54 worlds, 35 intact in both
runs. Versus y3: margin mean -5294 (median -1478, bootstrap 95% CI -10367..-1218), 32 of 35 worse, wins 15 -> 11.
Per product live own / rival: strawberry -671 / +399 (replay -565 / -284), milk -1301 / -215 (-639 / -467), wool
-989 / +1157 (-415 / -266). The mean includes chaotic divergences (112661570 -68.5k: the rival's replay drifted to
148k; 112714050 +9.9k: y3's routing changed); knock-on effects (budget guard, routing) make it worse than the
market-only replay, same direction. Selling earlier than y3 already does cannot reproduce the effect: y3 sells within
~4 steps of arrival; its goods arrive days later.

## What it would take to test the real lever on the 2750-3000 panel
The lever is the opening calendar (strawberries planted day 2 with ~10 by day 5; 3 sheep and the first cow on day
0-1), not a SELL rule. y3's library is the older MG opening and the grafted new opening failed (hidden state), so:
(1) an overlay that plants the day-2 strawberries and buys the extra early sheep on tiles the tape does not use
(hidden hands after the tape's last hire, hire_guard-safe cash); (2) a market-only pre-screen: run
`extract_market_events.py agents/mgt_y3.py` on the p2750 worlds and apply `shift_calendar` / a synthetic day-12
strawberry start to estimate margin and win flips per world; (3) the live 185-game p2750 panel, y3 vs y3+overlay
(ladder_panel.py / remote_panel.py `p2750`). That panel measures exactly this channel (opponent units and timing
frozen, prices live), but the overlay must not break the tape and results must be read with the frozen-replay
collapse rate in mind (19/54 worlds here).
