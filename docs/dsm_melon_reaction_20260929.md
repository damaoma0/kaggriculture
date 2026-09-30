# How DSM reacts to an early melon dump (2026-09-29)

Source: exact replay of 206 recorded DSM games (both action streams, recorded shops; all 206 reproduce the recorded
cash). Script `scripts/dsm_melon_reaction_20260929.py`, rows `results/fresh/dsm_melon_reaction_20260929/games.json`.
Two DSM submissions: 56498734 (100 games, episodes 112.56M-112.95M) and the current 56619023 (106 games, 114.35M-114.61M,
rated 3027).

## 1. Within a game: no reaction

DSM's melon schedule is fixed per version. Day-10 melons sold, by how many units the opponent had sold by hour 9:

| DSM version | opp units by h9 | n | DSM wins | margin | DSM d10 units | DSM d10 price | melon rev DSM-opp |
|---|---|---|---|---|---|---|---|
| old (h9) | <=5 | 13 | 13 | +17,061 | 35.5 | 248 | -2,690 |
| old (h9) | 6-15 | 62 | 62 | +11,616 | 35.6 | 240 | -2,065 |
| old (h9) | >=16 | 25 | 19 | +14,101 | 35.5 | 236 | -2,008 |
| new (h6) | <=5 | 13 | 12 | +41,888 | 36.0 | 253 | +503 |
| new (h6) | 6-15 | 68 | 61 | +17,338 | 36.0 | 247 | -718 |
| new (h6) | >=16 | 25 | 21 | +5,778 | 35.8 | 243 | +230 |

Same units at the same hours whatever the opponent does. It neither rushes nor holds back; it takes about 10 less a
unit (about -400 a game) when undercut. Only 3 of 206 games have the opponent 10+ units ahead of DSM's first sale.

## 2. Between versions: the reaction is a rebuilt melon plan

| | old 56498734 | new 56619023 |
|---|---|---|
| first melon sale | day 10 hour 9 (100/100) | day 10 hour 6 (105/106) |
| day-10 sales by hour | h9 12, h11 6, h12 6, h13 4.6 | **h6 5.9**, h9 17.9, h10 6.0, h12 5.9 |
| melon plantings | 6 on day 0 + 4 on day 1 | 6 on day 0 + 2 on day 1 + **4 on day 6** |
| days 9-14 melons | 59.7 units at 215 | 48.0 at 232 |
| day 15+ melons | 0 | 24.2 at 135 (the day-6 cohort) |
| season melon revenue DSM - opp | -2,132 | -345 |

The hour-6 tile is the farmer (episode 114348368): h0 W, h1 N (on the tile, 2 steps from spawn), h2 WATER (5 -> 6
units, the window bonus), h3 HARVEST, h4 S, h5 E, h6 DROP with `SELL MELON 6` in the same turn. Only one tile goes
early; the bulk still goes at hour 9. Nobody fertilizes melons, so the water hour is spent on the harvest day.

## 3. The whole top field moved to hour 6 in the same window

| opponent | vs old DSM: opp first sale / units by h9 | vs new DSM | melon rev DSM-opp (old -> new) |
|---|---|---|---|
| M & M & P & Q (3039) | h6 (16/16), 18.4; opp price 246 vs DSM 239 | h8 10, h6 3; 11.5 | -1,329 -> -561 |
| DECEM | h9 14, h7 3; 12.0 | h6 (7/7); 24.0 | -681 -> -5 |
| Vadim Vasilenko | h9 (12/12); 12.0 | h6 (8/8); 24.0 | +14 -> +82 |
| Unknown Mother-Goose | h9 (2/2); 12.0 | h6 (2/2); 24.0 | -352 -> +728 |

Opponent versions changed too, so these pairs compare both sides' versions. Among the top teams melon timing is now a
draw at hour 6 (day-10 prices about 243 on both sides).

## Consequences for us

- V9-lite (older UMG tapes, first sale at hour 9) is one step behind the current field. Its "windfall" is large
  against our KB/V8 stack because we sell at hours 8-10.
- Hour 6 is table stakes. Beating the field needs an earlier first tile: a melon already at its cap at dawn (fertilized
  in the window, as `sd_melon_fert` does) needs no water hour, and a tile 1 step from a shed access tile gives
  move / HARVEST / move / PLACE + SELL, about hour 3. The `sd_melon_fert` + `sd_melon_rush` arm still sold at hours
  8-10, so it has not reached hour 6 yet.
- DSM's day-6 cohort sells 24 units at about 135 after the dump. That is late use of melon land, not a timing play.
