# UMG crop and animal lifecycles

22 September 2026. This describes the historical UMG policy used by our tape
library, not the team's latest submission. Exact lifecycle transitions come from
30 previously verified full replays of submission 56266758. Animal purchase
requests are also checked across all 584 compact tapes of 56266758/56266899.
All dates are zero-based game days; crop ages are days since planting.

## Long-term crops

| Crop | Establishment observed in 30 games | Retirement |
|---|---|---|
| Melon | Exactly 12 planted on day 0 in every game; 20 additional plants across the sample on day 8; exactly one per game on day 11 | All 410 plants harvested at age 10: calendar days 10, 18 and 21 respectively. Harvest removes the plant. No fertilizer applications observed. |
| Strawberry | First substantial batch on day 5, expansion on days 6–8, second major batch on days 11–13; scattered additions through day 17 | All 588 observed DIG removals occur at age 16, the fourth production day. Another 300 expire at age 17; six dry out, and 64 remain standing at game end. |
| Tomato | First planting on day 12; planting continues through day 21, mostly days 12–18 | All 172 observed DIG removals occur at age 11, the fourth production day. Another 56 expire at age 12; seven dry out, and 50 remain standing at game end. |

Strawberries total 958 plants (31.9/game) and tomatoes 285 (9.5/game). These are
successful plantings, checked against the independently verified engine ledgers.
Counts vary with the revealed shops; the temporal sequence is not a fixed count
target for every scenario.

The modal strawberry watering pattern, present in 426 cohorts, is ages
**0, 2, 4, 6, 8, 9, 11, 13, 15**. Fertilizer applications concentrate at ages
**9 and 13**, before the four production events at 10/12/14/16. Tomato watering
is usually ages **0, 2, 4, 6, 7, 8, 9, 10** (219 cohorts), with fertilizer at
**7 and 10**, covering production at ages 8/9/10/11. These are observed patterns,
not universal schedules or a proof of optimality.

Melons receive survival watering early and daily watering during yield growth;
the most frequent pattern is **0, 2, 3, 5, 6, 7, 8, 9, 10**. Watering at ages 6–10
raises their initial unit to six before the age-10 harvest.

The retirements follow cohort age. The early strawberry cohorts clear mostly
on calendar days 21–24; the main second batch finishes on days 27–29. The first
tomatoes clear from day 23. Subsequent plantings on these tiles are overwhelmingly
wheat or carrots. This is a staged investment and harvesting calendar, not
wholesale premature removal on a universal switch day. Late plantings can have
only a partial production cycle before the season ends.

## Animal maintenance and additions

The usual opening has three cows and two sheep by day 2, then four cows and two
sheep by day 6. Most expansion occurs on days 6–12; species and quantities vary
with shops. Animals are serviced with wheat FEED, CARE and fertilizer collection,
with harvests timed to stored output. Care boosts later production and is not
equivalent to keeping an animal alive.

The separate 584-tape care study finds stronger servicing in worlds with demand:
sheep CARE commands cover about 46% of animal-days without a Yarn Store versus
75–90% with Yarn demand; cow care also rises with milk-demand shops. Geese receive
care on roughly 92% of animal-days. These are descriptive tape-command ratios;
they do not establish that the schedule is optimal against another opponent.
See `docs/mg_tape_base.md` and `scripts/mg_care_rule.py`.

| Species | Latest purchase-request day in all 584 tapes | Games requesting purchases on days 18–20 | Latest observed placement in the 30 full replays |
|---|---:|---:|---:|
| Goose | 13 | 0 | 11 |
| Cow | 18 | 2 | 19 |
| Sheep | 20 | 22 | 23 |

**No animal purchase requests occur from day 21 onward in any of the 584 tapes.**
Purchase requests are not successful additions; placement dates above are
confirmed by native farm-state transitions.

The two day-23 sheep placements are real late herd increases. In episodes
110022417 and 109951976, a sheep bought on day 18 remains in the shed through the
start of day 23, then is placed. The respective live herds increase from 10 to 11
and from four to five. A cow bought on day 18 is placed on day 19 in episode
109978530, increasing the herd from seven to eight. These are rare exceptions,
not ongoing expansion across the final week.

End-of-season service winds down. In the 30 full replays there is no animal CARE
on days 28–29 and no FEED on day 29. Day-28 feeding still occurs, most often for
geese, to support final production. Many sheep disappear after feed withdrawal:
54 departures on day 25 and 43 on day 28 across the sample. Every observed animal
departure has a preceding consecutive-unfed count of one; the next missed feed
triggers escape. Earlier departures can include execution failures, so they
should not all be labeled deliberate retirement.

## Implication for production-plan transfer

Preserve age-specific commitments: strawberry servicing and harvests through age
16, tomato servicing and harvests through age 11, and melon harvest at age 10.
Match intended establishment dates and retirement/replacement dates, not just
standing crop counts. Treat late animal additions separately from maintenance
of the established herd, and distinguish purchase date from placement date.

## Reproduction and checks

- Run `node scripts/audit_umg_lifecycles.mjs`.
- Results: `results/fresh/umg_lifecycles/audit.json`.
- All 30 raw replay hashes match the previous exact-engine audit. Successful
  planting totals match the verified ledger for all three long-term crops in
  every game. Animal placements require a corresponding PLACE command and an
  observed new animal on the tile.
- One short-crop snapshot discrepancy is retained: episode 109940134 shows 119
  wheat establishments versus 120 successful engine PLANT events. A transition
  that begins and ends within one interpreter step need not remain in the next
  snapshot. No claim here depends on the short-crop lifecycle totals.
- Harvest-visit counts in the JSON can miss a midnight harvest masked by new
  production. The report uses crop establishment, retirement and servicing
  patterns, not those counts as an output ledger.
