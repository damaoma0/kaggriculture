# Animal harvest intervals and service (2026-09-26)

## Engine rules (kaggriculture.py 1.32.7, `_daily_refresh_animals`, `HARVEST`)

At each midnight, per animal: if today is a production night (`(day + 1 - placed_day - first_yield_day) % interval == 0`),
`yield += 1 + bank` when fed today, else `yield += 1` and the bank is wiped. Then a fed AND cared day banks +1. The tile
holds at most `max_held`; anything above is lost. Two unfed days in a row = escape. HARVEST moves all held units into
the unit's inventory (one action), whatever the amount.

| animal | interval | max_held | full service (fed + cared daily) | best harvest interval | units a harvest |
|---|---|---|---|---|---|
| goose | 1 day | 4 | 2 eggs a day | every 2 days | 4 |
| cow | 2 days | 6 | 3 milk a production (1.5 a day) | every 4 days (before the 3rd production) | 6 |
| sheep | 3 days | 6 | 4 wool a production (1.33 a day) | every production (two would make 8 > 6) | 4 |

A harvest is needed today only when tonight is a production night and `held + 1 + bank > max_held` (the animal
thread's `_tier_anim_harv_needed`), and at the season end (everything held must reach the market). A harvest earlier
than that produces nothing extra and costs a unit-hour.

Value of service (engine rules): a CARE on a fed day adds +1 unit at the next production (if that production is fed
and still inside the season): about 110 for a cow, 160 for a sheep, 48 for a goose. A FEED on a production night
realises the bank (bank x price); a missed one wipes it. A FEED costs one wheat (~36), so goose service barely pays.

## Measured (scripts/season_animals.py, 40 DSM worlds, days 11-29, per world; results/fresh/threads_20260928/animals_k5b_40.json)

| | DSM goose | K5b goose | DSM cow | K5b cow | DSM sheep | K5b sheep |
|---|---|---|---|---|---|---|
| fed / cared (of animal-days) | 79% / 77% | 61% / 42% | 67% / 67% | 65% / 52% | 77% / 74% | 64% / 51% |
| production nights fed | 79% | 61% | 89% | 72% | 91% | 76% |
| units made a production | 1.72 | 1.27 | 2.62 | 2.19 | 3.69 | 2.79 |
| bank wiped (units) | 14.8 | 23.2 | 8.4 | 19.2 | 3.3 | 13.2 |
| lost to the cap (units) | 0.3 | 0.0 | 1.9 | 0.0 | 2.9 | 0.0 |
| harvests | 66 | 101 | 53 | 76 | 32 | 41 |
| units a harvest | 2.59 | 1.30 | 3.48 | 2.28 | 4.19 | 2.85 |

Why we harvest so often: the task list emits an animal HARVEST whenever `yield_units > 0`, and the tiered plan makes
every HARVEST mandatory (tier 2), while FEED (except keep-alive) and CARE are tier-4 leftovers at a flat value
(50 + sd_feed_bonus 20). So every animal holding 1+ units gets a forced visit daily and service loses the competition
for time. Keep-alive feeding (only when unfed yesterday) feeds every other day, so production nights are often unfed
and the banked care is wiped: we care (spend the labour) and then throw the bonus away.

DSM does not harvest at the cap either (cow 3.5, sheep 4.2 a harvest) but loses little to it (1.9 / 2.9 units a world).
