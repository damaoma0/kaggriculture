# Exact opening until the cash-safe date (xopen), 2026-09-25

Written by the coordinator from the builder's final report (the builder's own file tool refused .md output); the raw
tables are in `e1_report_g1.txt`, `e1_report_sem4.txt`, `e1_report_all.txt`. Code: commit e40f5db; results: 9d79fd7.

## Cash-safe date (design.md, cash_safe.txt)
Day 11, as a dynamic rule (hand off at hour 0 of days 10-12 once our cash funds the followed plan through day 14 under
a max(30%, measured) revenue shortfall with a 25% margin; day 13 regardless). Leaders start the day with less cash than
they spend that day on days 1-3 and 6-10 in 97-100% of 540 games; 13% on day 11, 2% on day 12, 0% from day 13.

## E0 control: passed
Replaying the whole game reproduces the leader's recorded cash 12/12 (lead_g1 worlds) and 52/52 (48-world set runs);
xopen_day=-1 equals the frozen mgt_lead.py copy (sha 8d578ef8) to the dollar on 2 games, every day-start cash equal.

## E1: gap to the leader and vs T (48 four-quadrant leader worlds; the 12 lead_g1 worlds agree)
T options: p1_min_value=30, release_stale_d, fert_hold=1 (+ the port's tie_value / hand_stock defaults).
| arm | gap to leader | vs T (paired, 95% t CI) | better/worse |
|---|---:|---|---|
| T | +14,320 (+10,794..+17,847) | - | - |
| replay to day 5, then T | +15,457 | -1,137 (-3,674..+1,401) | 22/26 |
| replay to day 8, then T | +18,050 | -3,730 (-6,155..-1,304) | 15/33 |
| replay to day 11, then T | +16,571 | -2,251 (-5,086..+585) | 25/23 |
| dynamic rule (day 11 in 38 worlds, day 12 in 10) | +16,613 | -2,292 (-5,181..+596; boot -5,281..+285) | 26/22 |
12 lead_g1 worlds: dynamic -964 vs T (-6,176..+4,248), +2,137 on the 9 clean worlds (7/9 better).

Cumulative revenue gap to the leader at the end of each day window (48-world means):
| window | 0-5 | 6-8 | 9-11 | 12-14 | 15-17 | 18-20 | 21-23 | 24-26 | 27-29 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| T | 42 | 588 | 4,564 | 7,801 | 12,707 | 15,313 | 15,158 | 15,731 | 17,239 |
| dynamic | 0 | 0 | 780 | 3,528 | 7,002 | 10,369 | 12,186 | 14,590 | 17,692 |

**Answer to the user's question: the production failure persists after an exact opening.** Harvested units behind the
leader on days 12-29: dynamic 271 (249..294) vs T 320. Three-reason split (deep_decomp), dynamic vs T: less production
+15.5k vs +13.2k (production at the leader's prices 15.5k vs 21.8k: animals fewer/later +1.9k vs +6.9k, missed plantings
4.2k vs 6.1k, crop care 8.9k vs 9.8k, plantings after T's cutoff 4.2k in every arm, later availability 5.1k vs 6.4k,
shed-cap discards 1.6k vs 1.1k, market depth -6.6k vs -14.6k); labour +0.1k; sale timing +1.0k vs +1.1k. The exact
opening removes the animal lag, but the extra early production sells lower, so cash does not rise.

Why a day-5 / day-8 handoff is worse than no replay: T inherits the leader's cash-bound state (same cash, e.g. 14 and 248
coins, same 9 hands, no failed buys) but does not carry on the leader's in-flight plan: on the handoff day it plants 0.6
vs 4.3 (48-world means) with ~30 extra PASS unit-steps; on day 9 it plants 11 vs 19; on day 10 it buys 6 wheat vs 53 and
earns 5.5k vs 9.4k. T from scratch avoids this with its own cash-richer path.

## Not run
E2 (new worlds, agents/mgt_lpv_xopen.py, static checks passed; review fixes B1-B7 have synthetic tests) and E3 (full
panel): skipped when the work was redirected to tile-exact parity. The follow mode has never run in a real game; a first
E2 must include the follow-mode control in the leader's own world (must equal the replay arm to the dollar). Own order
fills inferred from observations were exact in 115/170 compiled games (misses at midnight, where cap discards look like
sales).
