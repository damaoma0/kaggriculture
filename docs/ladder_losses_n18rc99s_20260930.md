# Where n18rc99s loses on the ladder (2026-09-30)

Live submission **n18rc99s = Kaggle 56676484** (uploaded 2026-09-29 13:11, public score 2396.5 at 01:56 UTC 09-30).
All 133 of its ladder games up to 2026-09-30 00:53 UTC were fetched and replayed exactly through the frozen harness
(source control: both recorded command streams; both live cash totals reproduced in 133 / 133, every ledger
reconciles to the dollar). Per-game, per-day, per-product ledgers for both sides are compared, losses against wins.

Reproduce:

    .venv/Scripts/python.exe scripts/ladder_panel_fetch.py 56676484 "Ghost Rule"
    .venv/Scripts/python.exe scripts/ladder_live_losses_20260930.py run --sub 56676484 --workers 1
    .venv/Scripts/python.exe scripts/ladder_live_losses_20260930.py report --sub 56676484
    .venv/Scripts/python.exe scripts/ladder_bank_trace_20260930.py --sub 56676484      # Kaggle overage bank per step

Outputs: `results/fresh/ladder_live_20260930/56676484/` (cases.json, one source control per game, bank/, summary.json).
Recordings for candidate runs: `results/fresh/semantic_h2h_20260929/study/recordings_live_56676484/` (the shared
`ladder_cases.json` was not touched).

## Record

112 W / 21 L (84%). The first 90 games were 84-6; the latest 43 (opponents' median current score ~2,370) are 28-15.
By the opponent team's current score: below 2,200 65-2; 2,200-2,400 35-9; **2,400-2,600 11-8 (mean margin -102)**;
2,600+ 1-2. Every loss is to a team at our level or above (19 of 21 now score 2,230-2,790).

## Where the margin goes

Mean per game, us minus them. A product line is its revenue minus its own inputs (seeds, animals, bought-back
units), so a wheat trader's purchases and resales net out; the lines sum to the final margin.

| line | losses (21) | wins (112) | losses: volume / price |
|---|---:|---:|---:|
| strawberry | -4,228 | +156 | -1,696 / -2,799 |
| wheat | -4,190 | -2,008 | (traders: see below) |
| wool | -2,778 | +798 | -1,829 / -1,115 |
| melon | -1,375 | -1,471 | +49 / -1,424 |
| carrot | -1,123 | +695 | -1,484 / +32 |
| milk | +3 | +2,530 | +1,244 / -1,031 |
| egg | +2,151 | +6,231 | +1,833 / +575 |
| tomato | +1,915 | +4,950 | -104 / +2,183 |
| fertilizer | +561 | +1,019 | |
| hires + land | +1,436 | +931 | |
| **margin** | **-7,629** | **+13,832** | |

- Against weaker teams we win on eggs, tomatoes and milk (they barely run geese or tomatoes: 89 eggs and 18 tomatoes
  sold vs our 247 / 78). The teams that beat us run them too, so those advantages shrink to +4k, while we lose
  strawberries, wheat and wool.
- Cash margin is level to day 11 (-1.5k) and slides from day 12 to day 24 (-6.7k). In the wins we lead from day 12.
  (Day-by-day cash flatters whoever holds stock: in kuengo 115459605 we led +4.0k on day 24, then the opponent sold
  83 held wool at ~$230 on days 27-30 and won by 12.2k.)

## The clearest marker: the third quadrant a day late

| our 3rd quadrant bought | games | lost | mean margin |
|---|---:|---:|---:|
| day 8 | 108 | 5 (5%) | +13,173 |
| day 9 or 10 | 25 | 16 (64%) | -1,346 |

All 12 losses worse than -5k are late-quadrant games; the 5 day-8 losses are all within -4.1k. In the late games:

- The opponent bought its own third quadrant the same day or earlier in 20 / 25. These are the DSM-style
  three-quadrant openers, so the day 6-8 market is contested. Our income is lower: day 8 $2,656 vs $3,418 in the day-8
  games; days 6-8 milk -$662, wool -$316, fertilizer -$169. We end day 8 with $1,652 (median), short of the $2,000,
  because the executor buys land only from cash left after the hour's hires, feed and seeds.
- Strawberries come later: seed purchases $140 on day 6 and $640 on day 8 (day-8 games: $447 / $206). On day 7 we
  hold 9.9 strawberry plants vs the opponent's 18.1 (day-8 games 14.5 vs 13.9); empty tiles 12.0 vs 3.6 on day 7 and
  19.6 vs 8.4 on day 9.
- Caveat: this is an association, and it partly marks the strong opponent. The earlier land-reserve arm n18rc160
  (third quadrant on day 8 in 9 / 9 DSM worlds) was about neutral: +53 on 9 DSM worlds, ladder-83 +215, MGT -168,
  leaders +145 (docs/v16_progress_20260929.md). Those 25 late games are the place to test it again.

## Strawberries, wool, wheat, melons in the losses

- **Strawberries** (worst line in 11 / 21 losses): the opponents' fleet is larger early, so they sell 110 units on days
  14-21 at $174-197 against our 80. Ours arrive later and sell on days 22-30 at $109-119. Crash selling is about equal
  (we sell 18 a game on crash days, they sell 14), so the price gap comes from which days the berries exist, not from
  holding.
- **Wool**: fewer sheep (5.1-5.6 vs 5.7-6.1 on days 14-26), 20 units sold on days 14-17 at $114 vs their $143, and
  they sell 38 vs our 24 on days 26-30. The two biggest wool losses: Aacceeo -16.7k, kuengo -16.8k (112 vs 192 wool).
- **Wheat**: fewer wheat tiles from day 9 (13-21 vs 19-27 on days 10-26; our tomato lot takes 10 tiles from day 18-20
  where they keep 6). Many of these opponents also trade wheat (they buy $19k a game).
- **Melons** leak about 1.4k in wins and losses alike: the opponents sell a bigger first wave on days 10-13 (54 vs
  39) and few later. Our second wave (~24 units) sells on days 14-21 at $119-148 into the glut they created.
- End-game land: 3.6-7.2 weed tiles on days 26-30 vs 0.8-3.4 (strawberries rotting).

## Time bank: not the cause, but little headroom

No timeouts or errors in 133 games. The guard's lean mode (32 s used) fired on days 22-29 in 10 / 21 losses and
44 / 112 wins, about the same rate; lean2 and greedy never fired. Kaggle's ladder machines use a median ~30 s of the
60 s bank (1.8 s loading, then ~2-3 s each morning from day 11). The local official-runner check used ~3 s, so the
ladder runs roughly an order of magnitude hotter than that check. A heavier candidate would reach lean2 / greedy.

## Losses

| episode | opponent | margin | 3rd Q day | worst lines |
|---|---|---:|---:|---|
| 115430113 | darktetradgod | -23,947 | 10 | strawberry -6.6k, wheat -4.9k, milk -3.9k |
| 115485738 | ActiveMusyoku | -14,105 | 9 | strawberry -7.3k, wheat -7.1k, tomato -6.8k |
| 115386934 | kwa | -13,461 | 9 | strawberry -8.4k, wheat -8.0k, melon -1.7k |
| 115459605 | kuengo | -12,227 | 9 | wool -16.8k, strawberry -11.4k, tomato -1.9k |
| 115287820 | matu997 | -10,906 | 9 | strawberry -9.3k, tomato -3.6k, wheat -3.1k |
| 115295659 | ctree4113 | -10,309 | 9 | strawberry -8.8k, wool -3.2k, carrot -2.8k |
| 115498423 | James Holland | -10,170 | 9 | strawberry -7.1k, wool -6.2k, wheat -3.1k |
| 115402895 | HarshPandey-yt-auto | -10,087 | 9 | wheat -13.4k, melon -2.0k, milk -1.1k |
| 115421251 | aildar & slopernak & bobot | -9,503 | 9 | wheat -5.1k, strawberry -3.6k, wool -3.0k |
| 115434329 | Konstantin Zhar | -8,296 | 9 | wheat -13.1k, melon -2.1k, egg -1.2k |
| 115478587 | Shiji Zheng | -7,761 | 9 | wool -7.2k, wheat -4.4k, tomato -4.0k |
| 115438099 | Zyy7390 | -6,344 | 9 | wheat -5.9k, strawberry -3.8k, carrot -2.4k |
| 115474130 | t-enstar | -4,121 | 8 | strawberry -3.3k, wheat -3.1k, egg -2.9k |
| 115299182 | refine123 | -4,001 | 8 | milk -3.4k, carrot -3.4k, strawberry -3.2k |
| 115310544 | Michael Timbs | -3,932 | 9 | strawberry -7.1k, wheat -4.9k, carrot -3.2k |
| 115478849 | Fedor | -3,662 | 8 | wheat -4.7k, wool -3.8k, milk -3.3k |
| 115446645 | Junliang Ye | -2,644 | 9 | wheat -13.1k, melon -2.3k, wool -1.0k |
| 115442420 | Fritz Cremer | -1,940 | 9 | strawberry -15.8k, carrot -4.0k, tomato -2.1k |
| 115393844 | Alex Oranov | -1,212 | 8 | strawberry -6.3k, carrot -5.6k, milk -0.6k |
| 115294919 | RB25det | -931 | 9 | egg -3.3k, wheat -3.2k, melon -3.1k |
| 115259300 | Aacceeo | -645 | 8 | wool -16.7k, strawberry -4.4k, melon -2.0k |
