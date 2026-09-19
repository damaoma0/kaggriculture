# Sale timing: the shed as a price cache, rushing, and tick alignment (2026-09-20)

Data: Mother-Goose's 72 raw replays, hourly (`scripts/mg_cache_extract.py` -> `results/fresh/mg_watch/hourly.json`;
`scripts/mg_cache_study.py` -> `cache_study.json`), and our own leave-one-out games against live V50 with hourly wool
and milk quotes and both sides' sell orders logged (`scripts/mgt_loo.py` now stores `trace`).

## Mechanics (engine source)
- Nothing spoils in the shed; only plants on tiles decay. A cache costs no units.
- The bound is capacity: 100 non-seed items. At midnight every unit's cargo is auto-dropped in unit order and the
  overflow is DISCARDED; BUY_PRODUCT / BUY_ANIMAL fail at the cap. Her shed peaks at 77 on an average day, is over 90
  on 27% of days, and shed + cargo at hour 23 exceeds 100 on 11% of nights (she loses overflow herself).
- Step order: unit actions -> market -> shop consumption (steps with step % 4 == 0; the town centre once a day) ->
  plant decay -> day end. Consumption is spread evenly through the day; there is no extra overnight consumption.
- A new shop is appended at the end of day 3k-1 and first consumes AFTER the market phase of hour 0 of day 3k. Its
  type is unknown to everyone until then.

## The price cycle is a 4-hour sawtooth with one big tooth
Quote over that day's mean, days 10-28: wool peaks at hours 1, 5, 9, 13, 17, 21 (1.28, 1.10, 1.06, 1.05, 1.04, 1.03)
with troughs of 0.90-0.96; milk 1.15 at hour 1, 1.00-1.08 at the other post-tick hours; strawberry +-4%; eggs,
tomato, carrot, wheat, melon flat. The step after a consumption tick is the local peak (wool +10.6%, milk +7.8%,
strawberry +3.9% over the tick hour) and hour 1 is the peak of the day because the midnight production has not been
sold yet. Everyone at her level sells there: her wool 46% / milk 62% of units on steps with hour % 4 == 1, her
opponents 62% / 59%. Her sale price over the hourly day mean is 1.30 for wool and 1.12 for milk - her OPPONENTS get
1.25 and 1.13. (The 1.41 quoted earlier came from quotes sampled every two hours, which miss the odd-hour peaks.)
**She has no timing edge over her peers; this is how the top of the ladder sells.**

## What waiting costs (unit-weighted by her sales of the day; quote relative to hour 1 of the day)
| | h1 | h2-6 | h9-21 | h23 | next day h1 | day+2 h1 |
|---|---|---|---|---|---|---|
| Wool | 1.00 | 0.83-0.91 | 0.88-0.89 | 0.76 | 0.87 | 0.96 |
| Milk | 1.00 | 0.85-0.89 | 0.89-0.91 | 0.82 | 0.86 | 0.85 |
| Strawberry | 1.00 | 0.97-1.01 | 0.99-1.01 | 0.94 | 0.90 | 0.88 |

- **Rushing pays at exactly one moment**: hour 1 is worth 10-15% more than anything later that day or the next
  morning for wool and milk. After hour 1 the day is flat (+-3%), so hurrying a harvest from hour 9 to hour 5 earns
  nothing; labour efficiency wins there. Only the farmer stands on the farm at hour 0 (hands hired at hour 0 act
  from hour 1), so the hour-1 lot is one or two animals' worth; her 24% of milk sold at hour 1 is that.
- **Do not slip to the next day**: -3 to -5% for wool and milk, -10% for strawberries.
- **She does not cache.** First-in-first-out from shed arrival to sale: 48% of her wool and 40% of her milk is sold in
  the step it reaches the shed, median hold 1 hour, 23% / 19% held over 6 hours. Her realised gain over the quote
  at arrival is +2.8 per wool (+367 a game, +251..+494), +1.5 per milk (+307), +0.9 per strawberry (+203). Holding
  her arrivals to the next morning instead would have LOST 8-15% on wool and 4-9% on milk (the quote next morning is
  below the arrival quote for 75% / 77% of units): prices fall through the season as the glut builds.

## Tests on our agent (leave-one-out, 40 worlds, live V50, paired against `mgt_h0` = `mgt_t10` behaviour)
| Variant | What | Result |
|---|---|---|
| `mgt_h1` | hold dead-stock surplus of wool/milk, release in hours 0-6 | **identical games in 40/40**: the surplus rule sells 0.1 wool a game - the tape's own scheduled SELLs absorb the top-up units, at her hours |
| `mgt_h3` | defer the tape's wool/milk/strawberry SELLs (35 / 10 / 71 units a game) to the next post-tick step | **-658 (-790..-529), worse in 38 of 40**; own cash -205, V50 **+453**; wool 152.2 -> 150.7 |

Our agent already sells 53% of its wool and 86% of its milk on post-tick steps and realises 1.19x / 1.13x the day
mean against V50's 1.14x / 1.12x. Moving the rest onto the peak step made it worse: V50 sells heavily on exactly
those steps, orders fill in per-unit lockstep, and the quote before the step is not what a lot sold INTO the crowd
realises. Her off-tick sells (hour 0, before the hour-1 crowd) were front-running it. The peak is a race, and joining
the crowd later hands the rival the clean units.

## Banking before a shop opens? (`scripts/mg_shop_open_study.py`, 576 openings, sonnet subagent; numbers re-read by me)
"Relevant" = the new shop buys the product. Bootstrap 95% intervals over events.

- **She does not bank and does not dump.** Units sold on the opening day, relevant minus irrelevant: wool +0.24
  (-0.06..+0.55), milk -0.03, strawberry +0.06, all n.s.; hours 0-1 of the opening day: wool **-0.69 (-1.24..-0.08)**,
  i.e. less, not more. Stock on the night before an opening against the neighbouring nights: wool -0.9, milk -0.5,
  strawberry -1.0 (all significantly LOWER); wheat +3.6 (her season-long wheat position, not opening-specific). The
  three-day rhythm in her wool sales is sheep biology (3-day production from the day-0 flock lands on days 6, 9, ...),
  identical for relevant and irrelevant openings and present in her opponents too.
- **No jump at the opening** (hour 23 -> hour 0: wool -0.1): the new shop first consumes after hour 0's market.
- **The lift afterwards is large and builds for days.** Quote against day D-1:

| | D | D+1 | D+2 | D+3 | D+5 |
|---|---|---|---|---|---|
| Wool, Yarn Store opened (68) | +7 | +26 | +49 | +53 | +71 |
| Wool, any other shop (508) | -17 | -26 | -25 | -43 | -48 |
| Milk, relevant (227) / not (349) | +2 / -5 | +7 / -9 | +3 / -22 | +4 / -27 | +1 / -43 |
| Strawberry, relevant (307) / not (269) | +1 / -2 | +5 / -5 | +5 / -11 | +9 / -14 | +12 / -22 |

  Carrot and wheat move by 1-4 (flat price curves). Difference-in-differences for wool: +52 (D+1), +96 (D+3), +115 (D+6).
- **Consequence.** Banking AHEAD loses in expectation because the type is unknown: wool is relevant 1 time in 8, so
  the expected D+3 move is 1/8 x 53 + 7/8 x (-43) = -31. Holding AFTER a relevant reveal is the play: a wool unit
  sold at D+2 instead of D is worth ~+42. Dumping at hour 00 of the opening day is the worst moment of the window.
- Tests: `mgt_r1` (hold wool 2 days after a Yarn Store is revealed, release 8 a step) and `mgt_r2` (wool, milk and
  strawberry, 2 days), capacity- and cash-guarded (`_shp_reveal_hold`).
