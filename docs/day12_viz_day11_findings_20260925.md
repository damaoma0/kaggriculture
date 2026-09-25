# Day 11: leader vs current-T from the exact hand-off (2026-09-25)

Source: the day12 side-by-side viewer's "Exact start — current T" arm (`results/fresh/day12_viz/fhmrp_streams/`,
produced by a separate thread: leader's own recorded actions through step 263, then `agents/mgt_lead_fix.py` with
`cfg={p1_min_value: 30, release_stale_d: True, fert_hold: 1, harvest_policy: 'leader_tendency', hp_crops: ['MELON'],
replant_leader: 1}` from the day-11 morning). Replayed through `scripts/upkeep_engine.py`
(`scripts/build_day12_side_by_side.py`), same seed/shops/opponent as the leader's own recorded game in all 12
`lead_g1` worlds. The day-11 morning board is byte-identical to the leader's own recorded state in all 12 worlds
(`handoff_ok`), and the replay reproduces the stream's own reported day-11/12/13 starting cash exactly in all 12
(`cash_checks`) — see `results/fresh/day12_viz/verify_table.md`. This isolates the day-11 *policy* difference from
the ~11 days of opening drift that dominate the plain "T from step 0" comparison; it is one day, 12 worlds — a
descriptive sample, not a controlled multi-seed test.

Interactive detail (per-hour boards, per-unit actions, running differences) is in `viz/day12_leader_vs_T.html`,
mode "Exact start — current T", Day 11.

## Headline: idling and walking concentrate in the last few hours of the day

Idle unit-steps on day 11, summed over all 12 worlds and 24 hours: **leader 5, current-T 87** — a 17x gap, and it
is not spread evenly. Hour-by-hour (unit-steps idle per hour, summed over the 12 worlds):

| hour | 0-14 | 15 | 16-17 | 18 | 19 | 20 | 21 | 22 | 23 |
|---|---|---|---|---|---|---|---|---|---|
| leader | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 3 |
| current-T | 0 | 0 | 0 | 1 | 3 | 8 | 11 | 15 | **49** |

Current-T is essentially never idle before hour 18, then idling climbs every hour to a peak at hour 23 (the last
hour of the day), which alone accounts for 56% of its day-11 idle total. The leader keeps working productively
through hour 23 in every world (only 4 of its 5 total idle unit-steps fall in hours 22-23, and even those are rare).
There is no game mechanic that makes hour 23 unproductive — a watered/fertilized/harvested action at hour 23 counts
the same as any other hour — so this looks like current-T running out of assigned work near day-end rather than a
deliberate stop. Concrete example, episode 112667461 (leader idle 0, current-T idle 19 that day): at hour 23, four
of our units (including the farmer) PASS while the leader's corresponding units WATER; at hours 19-21 one unit
PASSes while the leader's FERTILIZEs, WATERs, then PLANTs. Movement follows the same shape at a smaller scale:
current-T logs 1,692 move unit-steps on day 11 vs the leader's 1,392 (+22%), i.e. more repositioning as well as more
idling, for less output (below).

Every one of the 12 worlds shows current-T strictly at or above the leader's idle count; none show the reverse.

## Fertilizer flow: current-T collects, fertilizes and sells less, and carries a larger unsold surplus

Summed over 12 worlds, day 11 only (COLLECT_FERTILIZER produces 1 fertilizer/animal/day; FERTILIZE consumes exactly
1 from the acting unit's inventory and requires standing on a PLANT tile — confirmed in the engine source):

| | leader | current-T | ratio |
|---|---:|---:|---:|
| COLLECT_FERTILIZER (produced) | 247 | 198 | 80% |
| FERTILIZE (consumed) | 105 | 56 | 53% |
| FERTILIZER sold | 212 | 137 | 65% |
| FERTILIZER carried (unit inventories, mean of hour 0/12/23 samples) | 8.97 | 11.61 | +29% |

Current-T is behind the leader at every stage of the fertilizer chain except the one that matters least: it holds
*more* fertilizer in hand on average despite producing and using less of it. The leader turns fertilizer over
faster — collect, then promptly either spend it on FERTILIZE or sell it — while current-T's fertilizer backs up
un-spent and unsold. This is consistent with, and likely a downstream symptom of, the same day-end idling above:
units that are idling instead of working are also not converting carried fertilizer into either crop bonus or cash.

## The coop: current-T consistently ends day 11 with one fewer goose

Counting COOP tiles with a live goose at day-11 end (step 312, i.e. the day-12 morning board): **leader 101 geese
across the 12 worlds, current-T 89** — and every single world individually shows current-T exactly 1 goose behind
the leader (10 vs 9, 2 vs 1, 8 vs 7, 11 vs 10, 11 vs 10, 14 vs 13, 5 vs 4, 7 vs 6, 2 vs 1, 12 vs 11, 11 vs 10, 8 vs
7). That regularity — not "sometimes 0, sometimes 2" but *always exactly 1* — points at a specific, systematic gap
(a goose current-T doesn't buy/place that the leader does, or one it loses) rather than noise; it is flagged here as
a traced, surprising number, not diagnosed further. Correspondingly, EGG harvested on day 11 is lower for current-T
in 10 of 12 worlds (totals 34 vs the leader's 53); care quality where a coop exists looks comparable (`fed_today`/
`cared_today`/`consecutive_unfed` sampled at hour 0 and hour 24 show no systematic escalation on either side —
geese are not being starved, just fewer of them are on the board).

## Strawberry care: closely matched, day 11 is a quiet day for this crop by design

Strawberry plantings on day 11 are essentially identical: 24 (leader) vs 23 (current-T) summed over the 12 worlds,
matching per-world in 10 of 12 (off by at most 1 elsewhere). Neither side harvests any strawberries on day 11 in any
world (0 vs 0) — expected, since strawberries first yield day 10 and then every other day (10, 12, 14, 16 per
`docs/environment.md`), so day 11 falls between harvest days for a crop planted on schedule. Strawberry care is the
one area sampled here where current-T is not behind the leader; the day-11 gap is concentrated in wheat/fertilizer/
animal throughput and, above all, in used hours near day-end.

## Aggregate day-11 productivity (12 worlds, for context)

| | leader | current-T | ratio |
|---|---:|---:|---:|
| WATER | 658 | 514 | 78% |
| FERTILIZE | 105 | 56 | 53% |
| COLLECT_FERTILIZER | 247 | 198 | 80% |
| HARVEST (unit-steps) | 144 | 126 | 88% |
| idle unit-steps | 5 | 87 | 17x |
| move unit-steps | 1,392 | 1,692 | +22% |

## Caveats

Single day, 12 worlds, one exact hand-off point (step 264) per world — a descriptive sample of this specific
current-T build (`agents/mgt_lead_fix.py`, the melon-rule + replant-on-leader's-tile config), not a claim about
current-T generally or a multi-seed statistical test. The "exactly one fewer goose, every world" pattern is reported
as observed and traced to the coop tiles directly (not inferred from aggregate counters); its root cause (a missed
BUY_ANIMAL, a lost goose, or a placement difference inherited from the leader's own mid-game state) is not
diagnosed here. No policy change is proposed or made; `agents/mgt_lead_fix.py` and the day12 viewer's leader/T/x
arms are unchanged.
