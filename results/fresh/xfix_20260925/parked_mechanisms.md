# Parked fixes: failure mechanisms (2026-09-26)

Source: day-11 agent, `scripts/xfix_diag.py`, paired full-game ledger deltas per game (52 worlds; E1 cells on 12 G1 worlds).
Each fix: did it do its local job, where the money went, what undermines it. None is dropped; each has a re-test condition.

| # | fix | full-game delta | local job done? | where the money went | undermined by | re-test condition |
|---|---|---:|---|---|---|---|
| 1 | fert_follow | -693 | yes: wheat FERTILIZE +41, wheat harvested +32 (+785), carrots +277 | fertilizer sold -35 (-1,122); tomato/wool/strawberry -640 (harvests -6, waters -6 displaced) | fertilizer valued at its 60-70 sale price; +2 wheat units at ~40 do not repay it at our realized units (5 vs the leader's 6) | on top of the planner's labour |
| 2 | fert_shadow | +21 (flat) | partly: FERTILIZE +7, fertilizer sold -17 | none clear (+1.7k on 52 worlds is milk in collapse worlds) | module still refuses the day-2 (age-2) wheat fertilize at any price | extend the shadow price to the age-2 case |
| 3 | delivery credit | -1,587 | no: it removed the flat 10-unit / value trigger | PLACE -53, DROP -14; eggs -20 (-870), wool -566, fertilizer -556, strawberries -408; wheat +645 | credit table gives 0 to eggs / fertilizer / milk late, so they ride to midnight (cap, next-day price) | keep the flat trigger as a fallback |
| 4 | wheat/carrot tendency | -858 alone; -1,273 on replant | yes: harvests +35, carrots +14 | wheat harvested -66 (-1,717); waters -71 (age-3/4 window skipped); PASS +41 | early harvest takes 4-5 units instead of 6; the leader offsets with same-day replant + fertilizer (5 units at age 3) | as a package with replant + wheat fertilize |
| 5 | tomato/strawberry tendency | -213 on melons | yes: harvests +12 | wheat -5 units (-214) displaced | labour; the module's own harvest-when-needed already catches these productions | on top of the planner |
| 6 | fert_release + place_bonus + idle_deliver (Fday) | -1,770 vs Fhmrp | yes: fertilizer sold +29; closest day-11 layout | place_bonus_days 29 makes every animal PLACE win dispatch: +354 cows, +212 sheep, +581 wheat bought; eggs +1.8k but wheat -1.5k, strawberries -1.1k, tomatoes -0.5k; rival +1.9k | the dispatcher's labour budget: the animal bonus steals crop maintenance | fert_release alone (clean day-11 distance effect) |
| 7 | busy-day penalty + upkeep x0.65 | -6,321 on the harvest policy | yes: harvests +36, plantings +14, water +45 | COLLECT_FERTILIZER -161 (fertilizer sold -117, -4.1k), CARE -59, FEED -38, milk -87 (-2.4k), wool -30 (-2.3k); rival +11.5k | upkeep-only task definition includes COLLECT; x0.65 pushes care/feed below p1_min_value so they drop after 15h | COLLECT excluded, x0.65 at pair level only |
| 8 | leader maintenance lists (FdayL) | -6,697 vs Fday | yes: fertilized-until diffs 6.6 -> 2.0, units 7.8 -> 4.9 | strawberries -41 (-5.1k), milk -41, wool -23, eggs -12; CARE -44, FEED -22, HARVEST -15, PASS -75 | sched_maint off loses the module's harvest and production-day jobs; the lists assume the leader's labour and cohorts (we run 1-2 days off on remapped tiles) | lists as extra ops on top of sched_maint |
| 9 | exact removals (E1 Gex) | -1,493 (12 G1) | yes: DIG +6, plantings +4 | strawberries -16 (-1.4k), tomatoes -10 | we dig live cohorts on the leader's day, but our cohorts are later / smaller than the leader's | with cohort matching |
| 10 | cutoffs off (E1 Gpc0) | -67 | yes: plantings +20, water +37 | wheat -15, carrots -12, eggs -4 (displaced) vs strawberries +11 (+1.3k) | labour: late crew saturated | on top of the planner |
| 11 | early harvest (E1 Geo) | -2,321 | yes: harvests +25 | wheat -33, carrots -29 (-2.2k), water -66 | same as #4: forfeits window waters; no same-tile replant or fertilizer | as a package (see #4) |
| 12 | leader harvest days, no replant (E1 Ghl) | +36 | yes: harvests +13 | wheat -50 (-1.1k), water -31 | missing replant_leader; with it this is the confirmed Fhmrp | (confirmed as Fhmrp) |

Labour-bound, re-test on top of the planner: 1, 5, 6 (animal-bonus part), 7 (COLLECT excluded), 10.
Needing redesign rather than labour: 3 (flat fallback), 4 / 11 (fertilize + replant package), 8 (lists as additions), 9 (cohort matching).
