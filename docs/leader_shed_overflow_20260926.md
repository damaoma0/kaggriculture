# How the leaders avoid midnight deletions, and when they turn around to sell midday (2026-09-26)

Branch `leader-shed-overflow`. Data: every fetched leader tape (635 episodes, six teams: DSM 100, Mother-Goose 142,
Vadim 140, M&M&P&Q 113, DECEM 100, Boey 40), replayed through the official engine with hooks on the leader's seat
(all 635 reproduce the recorded final cash exactly), plus K5b's season streams on its 53 panel worlds (panel13 + the
40-world DSM confirmation panel). Window: days 11-28, K5b's season window. No games were run: this is replay analysis only.

- Extractor: `scripts/leader_shed_flow.py leaders|arm ...`. It records nights (the shed before the dump, what is carried
  in by product and by unit, what is deleted, and animal product still on the tiles), every DROP/PLACE at the shed
  (whether it came from a harvest or a pickup, the route before and after, the shed-visit pickups), and the fate of
  every harvested unit: delivered at hour h, carried to midnight, or consumed.
- Report: `scripts/leader_shed_report.py` -> `results/fresh/leader_shed_20260926/report.txt` (all tables below).
  `k5b.jsonl.gz` is committed. `leaders.jsonl.gz` (15 MB) is not, but regenerates in about a minute:
  `leader_shed_flow.py leaders results/fresh/leader_shed_20260926/leaders.jsonl.gz --workers 3`.

Engine reminder (`_end_of_day`): after the hour-23 market, the engine refreshes crops and animals, spawns weeds, then
dumps every unit's inventory into the shed up to 100 (farmer first, then hands in index order). Anything over 100 is
deleted. A DROP/PLACE at a shed-access tile (4,4)/(5,4)/(4,5)/(5,5) puts goods into the shed at once, and a SELL order
in the same turn sells them, because the market runs after unit actions.

## 1. The midnight picture (per night, days 11-28)

| group | shed at 23 | carried in | total | deleted | nights >100 | delivered before h23 (units/day) | animal product left on tiles |
|---|---|---|---|---|---|---|---|
| DSM | 5.9 | 82.3 | 88.1 | 0.44 | 11% | 20.0 | 16.2 |
| Mother-Goose | 6.5 | 77.2 | 83.7 | 0.48 | 8% | 19.5 | 11.6 |
| Vadim | 5.8 | 80.3 | 86.1 | 0.38 | 8% | 18.6 | 15.7 |
| DECEM | 5.2 | 81.5 | 86.7 | 0.92 | 14% | 19.8 | 13.7 |
| M&M&P&Q | 17.1 | 67.4 | 84.5 | 0.38 | 8% | 18.4 | 11.2 |
| Boey | 13.1 | 70.2 | 83.2 | 0.33 | 7% | 26.5 | 8.6 |
| **K5b** | 8.7 | 86.6 | **95.3** | **3.09** | **30%** | **3.6** | **0.1** |

K5b does not harvest more than the leaders. It brings almost nothing back during the day.

**The leaders cap their midnight carry, K5b does not.** Nights sorted by the day's total output (delivered midday +
carried at midnight), in quintiles:

| quintile | DSM: midday / carried / deleted | MG: midday / carried / deleted | K5b: midday / carried / deleted |
|---|---|---|---|
| 1 (light) | 8.1 / 69.2 / 0.02 | 8.4 / 63.7 / 0.00 | 4.9 / 58.1 / 0.01 |
| 2 | 8.6 / 83.2 / 0.08 | 10.2 / 76.0 / 0.02 | 1.1 / 80.8 / 0.29 |
| 3 | 15.7 / 85.4 / 0.35 | 16.4 / 79.4 / 0.18 | 1.2 / 89.8 / 0.83 |
| 4 | 22.0 / 88.8 / 0.98 | 22.0 / 83.3 / 0.55 | 3.4 / 95.8 / 2.16 |
| 5 (heavy) | 45.7 / 84.7 / 0.77 | 40.5 / 83.7 / 1.64 | 7.5 / 107.8 / 11.95 |

The leaders' midnight carry levels off at about 85 whatever the volume. The excess goes to the shed during the day
(8 to 45 units). All six teams show the same shape. Without their midday deliveries, 54-70% of leader nights would go
over 100. K5b's carry rises with volume up to 108, and its top quintile loses 12 units a night.

The leaders' three tools, from largest to smallest:
1. **Same-day deliveries** of about 20 produce units a day (next sections).
2. **Animal product left on the tiles overnight** (9-16 units; K5b 0.1). The leaders harvest pens in the morning and
   sell the product the same day, so much of the animal output never enters a midnight carry. K5b harvests pens during
   the day and carries the product to midnight.
3. **A near-empty shed at 23** (about 6; K5b 8.7, of which 5 is its wheat feed reserve). M&M&P&Q and Boey keep 13-17
   in the shed but carry correspondingly less.

The hour-23 drop is **not** a leader tool: 1.1-1.5 units a day for the top four, 3-4 for Boey and M&M&P&Q. They deliver
earlier in the day.

## 2. When the leaders turn around (question 2)

Deliveries of harvested produce at the shed before hour 23, per day (DSM; the other teams are within about 15%):

| type | drops/day | units/day | units/drop | detour (median) | what | hours |
|---|---|---|---|---|---|---|
| A: harvest on a shed-access tile, drop at once | 1.1 | 4.2 | 3.7 | 0 | milk, eggs, wool | 0-3 |
| B: turnaround (out, harvest, back to the shed, out again) | 1.75 | 14.3 | 8.2 | **2 tiles** | milk, wheat, strawberries, wool, carrots, melons | 4-23, peak 16-20 |
| C: last stop of the day (h<23) | 0.14 | 1.6 | 11 | 0 | wheat | 20-22 |
| K5b, all types | 0.64 | 5.0 | - | - | turnarounds: melons only (the priority-harvest rule); end-of-day drops of milk, wheat and fertilizer | - |

What decides a turnaround (six teams pooled, 19,785 turnaround drops):
- **The shed is on the way.** The median detour is 2 tiles (previous job -> shed -> next job, compared with previous
  job -> next job directly). 84% of turnarounds stay in one quadrant: the hand harvests its patch, walks back past the
  shed, and continues to the animals (pens are near the centre). The next job is animal work in 68% of turnarounds
  (feed, collect fertilizer or harvest: cow 39%, sheep 19%, goose 9%) and watering in 12%. In 38% of turnarounds the hand also picks up wheat (feed) during the same visit, so
  the turnaround doubles as a restock between a harvest trip and an animal trip.
- **Harvest hour.** Share of each harvest-hour block's units delivered the same day:

| product | h0-3 | h4-7 | h8-11 | h12-15 | h16-19 | h20-23 | overall | K5b overall |
|---|---|---|---|---|---|---|---|---|
| milk | 85% | 56% | 30% | 31% | 41% | 10% | 59% | 8% |
| wool | 88% | 41% | 25% | 27% | 34% | 9% | 52% | 5% |
| melon | 88% | 99% | 36% | 5% | 0% | - | 62% | 74% |
| strawberry | 62% | 62% | 39% | 13% | 2% | 0% | 21% | 1% |
| egg | 57% | 13% | 7% | 10% | 19% | 5% | 18% | 2% |
| carrot | 36% | 25% | 22% | 16% | 3% | 0% | 13% | 2% |
| wheat | 22% | 18% | 19% | 12% | 2% | 0% | 10% | 2% |
| tomato | 24% | 19% | 13% | 6% | 1% | 0% | 5% | 1% |

  Anything harvested after hour 16 is almost always carried to midnight. Early harvests come back.
- **Distance of the harvested tile from the shed.** Milk same-day by distance from the access tiles, d0/d1/d2/d3/d4+:
  95/61/42/27/15% (leader on K5b's worlds). Wool 97/59/36/37/32%. Eggs 89/14/11/7/6%. Strawberries harvested at h0-7
  far out (d3+) still come back 63-73% of the time, because the hand works its outer patch first and walks back
  inward.
- **Load.** Turnaround hand-days are the hands with the bigger harvest (12.2 vs 8.5 units a hand-day, DSM). On the
  heaviest days, same-day volume reaches 40 units/day (wheat 10.9, milk 9.3, wool 6.5, carrot 3.9, strawberry 3.5,
  egg 3.1), against 9 on light days, which are mostly melons.
- **Size.** The hand carries a median 6-7 units at the turnaround (p90 13-14). A hand's own midnight carry has
  median 6, p90 12 for every leader team (K5b p90 14, max 35).

**What happens to the delivered goods.** The leaders sell midday-delivered produce within 0-3 hours: milk 65%, wool 66%,
strawberries 86%, carrots 85%, melons 99%. They also do not sell the overnight dump all at once. Of the night's carry,
36-68% (by product; melons 5%) is sold after hour 11 of the next day, and the shed holds 32 goods at noon on average
(K5b 23). K5b sells 80-98% of the night's carry at hours 1-2.

The leaders' realised prices by sale hour are in `report.txt` (section `prices`). They are confounded by day and world,
so I do not quote them as a price effect. The engine-counterfactual same-day credit is in the harvest-timing study
(`results/fresh/harvest_timing_20260925/`): melon +54/unit on days 6-11 mornings, wool +26/+9/+7/+6, milk +13/+7,
strawberry up to +5, everyday crops about 0.

## 3. What this means for K5b

- **The layout is not the difference.** K5b inherits the leader's day-11 board: milk harvested at distance 0/1/2 is
  26/28/31% of K5b's milk against 27/28/30% for the leader on the same worlds.
- **The zero-cost misses.** K5b harvests 45 units of milk per world *standing on a shed-access tile* and delivers only
  14% of them the same day (leader 95%). Wool on access tiles is 19% (leader 97%), eggs 8% (leader 89%). One DROP, with
  no walking, would put these in the shed. These come from outbound-only hands leaving the shed.
- **Harvest timing.** K5b harvests pens later: milk at h0-3 is 18% of its milk (leader 45%), wool 12% (31%). Most of
  its animal product is picked up at h4-11 on the way out, then carried all day.
- **A static estimate.** Replace K5b's deliveries by the leaders' same-day rates by product x distance x harvest-hour
  block on K5b's own harvests. That moves 17.3 units a night off the midnight carry. Deletions fall from 55.5 to about
  2 units per world (days 11-28), nights over 100 from 30% to 3%, and the deleted value (at next-morning quotes) from
  about 4.9k to 0.15k per world. This ignores the labour of the turnarounds (median 2 tiles, about 1.7 a day), the price
  impact of selling earlier, and any knock-on route changes. It is an upper bound on the deletion part, not a game result.

Candidate rules for the tiered plan, stated as the leaders' pattern and not yet tested:
1. Harvest pens on or next to the shed-access tiles first thing (h0-3) and DROP at once (type A).
2. The priority-harvest (round-trip) tier covers more than melons: a hand whose day is harvest-then-animal-work in one
   quadrant ends its harvest leg at the shed (drop, sell, pick up the feed wheat) when the detour is 2 tiles or less (type B).
3. Keep the projected midnight carry at or below about 85. Above that, the earliest-harvested loads come back the same day.
   Outbound-only hands stay outbound for work harvested after about h16.

The earlier KD thread (`results/fresh/threads_20260928/dump/`) worked on END-of-day deliveries and room estimates. The
leaders deliver early and on the way, so that thread's conclusion ("every hand's route is already packed to hour 23 with
no slack for a delivery detour") does not apply to a turnaround planned at the start of the day.
