# xopen: follow the leader's plan exactly until the cash-safe date, repair breakages with an EV failsafe, then hand off (design, 2026-09-25)

Thread xopen. Design only: no games were run. Every number below comes from stored data and is reproduced by
`scripts/xopen_cash_safe.py` (-> `cash_safe.txt/.json`) and `scripts/xopen_open_stats.py` (-> `open_stats*.txt/.json`),
both in this directory.

**The user's rule (binding):** "follow the leaders' plans exactly up until a point of divergence", tightened to: follow
until a date D where cash growth has outpaced reinvestment and failed reinvestment is no longer a worry. Before D a
breakage does NOT trigger a handoff: it is repaired, with cuts ranked by expected value, and following continues.
The handoff to our executor happens at D.

Notation. **D** = the handoff day: our executor controls everything from hour 0 of day D. **X = D - 1** = the last day
replayed from the recording. "Plan" = the recording we follow. **R[t]** = reinvestment on day t: seeds + animals + wheat /
fertilizer bought + wages (fib per hire) + land. **V[t]** = revenue on day t. **C[t]** = cash at the start of day t.

## Summary

| question | answer (evidence in section 0 / A) |
|---|---|
| Is there a cash-safe date? | **Yes, and it is sharp.** In all 540 leader games the cash identity closes exactly (after correcting the corpus's one-day offset). Leaders are cash-bound on days 1-3 and 6-10: the morning cash is below that day's reinvestment in 97-100% of games. On day 11 that share is 13%, day 12 2%, day 13+ 0%. By day 10 they have spent 66% of the season's reinvestment. |
| D, leader corpus | First day of a safe suffix (morning cash >= 1.25 x that day's R for every later day, and cash never falls): **day 11 in 79% of games, <= 12 in 93%, <= 13 in 99%**. Still day 11 (p90 12) when every later coin of revenue is cut by 30% or 50%. The last bound day is day 10 in 84% of games. Five teams have a median of 11; Boey has 13. |
| D, our side | Our own cash paths give the same date. The current deploy in the 12 smoke worlds (7 builds, 84 paths, each world with its own 2750+ opponent): day 11 in 79/84 (5 at 14), and 84/84 under a 30-50% revenue stress. In leader worlds, the deploy is at 11 (10/12). T is at 11-12 (median 12): its lag pushes its own date back a day. |
| Our revenue vs the plan's | In the 185 p2750 worlds the current default earns 0.86 of the exemplar's recorded revenue on days 0-2 (the exemplar also sold 140 coins of wheat on day 0) and **0.93 on days 3-11 (p10 0.87)**. So the realistic cut is 7-13%, well inside the 30% stress. |
| Decision | **A dynamic rule, floor 10, cap 13.** Hand off at hour 0 of the first day t in 10..13 on which our own morning cash keeps the plan funded on every morning from t to 14. The test cuts the plan's revenue by h = max(0.3, our measured shortfall so far), with a 25% margin. Replayed on stored paths, the rule hands off on day 11 in 78% of leader games (10: 1%, 12: 15%, 13-14: 6%, capped at 13), T 11/12 (7/5), and the deploy smoke paths 11 in 36/36. A fixed D = 11 is the fallback. |
| Load on the failsafe | Carrying the exemplar's plan with 5% / 10% / 15% less revenue defers 0.1-0.5k / 0.5-1.1k / 0.9-1.7k coins on each of days 6, 7, 9 and 10. At 5-10% it is caught up by day 11 (cash on day 11 is 1,312 / 219). At 15% or more it is not (cash 0), which is when the dynamic rule moves D to 12-13. With land_max 2 (no $4,000 SE quadrant on day 10), day 10 needs no deferral for any cut up to 20%, and day-11 cash is 2.0-5.3k. |
| Which recording | Day 0: the deploy's exemplar, DSM's seat of 112655730. Plans cannot follow shops until day 6 because leaders don't: 165 corpus games (DSM 81, Vadim 84) are tile-for-tile identical to the exemplar at the start of days 4-6, including planting and placement days. **At day 6, hour 0, re-retrieve among these state-identical games by our two revealed shops.** Their day 6-10 plans depend strongly on the shops: sheep on day 11 are 11.3 vs 3.4 with or without a Yarn Store among the first two shops; strawberries 25 vs 14; cows 11 vs 6. At day 9, re-retrieve only if a state-identical game exists (4 against the exemplar). The day-9 shop is otherwise ignored until D. |
| Weeds | 0.16 expected weed spawns a game on the plan's empty tiles on nights 0-10 (0.13 on tiles the plan uses by day 12). The exemplar has 0 DIGs on days 0-10. Weed repair is rare but must exist. |
| Tests | E1: leader-world ablation, 12 G1 games x 7 cells: T, replay days 0..X then T for X = 5, 8, 10, 11 and the dynamic rule, plus the no-handoff control (it must reproduce the leader to the dollar). E2: 4 deploy arms x 12 smoke worlds. E3: the full 185-world panel only if E2 is clearly positive. |

## 0. The cash-safe date D

### 0.1 Accounting (checked)
- **Corpus** (`data/leader_semantics`, 540 games: DECEM, M&M&P&Q, Mother-Goose, DSM, Vadim 100 each; Boey 40).
  `market.*` at index i holds day i+1, and index 0 holds days 0 AND 1. So day t >= 2 uses index t-1, and days 0-1 form
  one block. Other inputs: wages = fib-sum over `hands_present` (correctly dated), land = 1000 / 2000 / 4000 read off
  the board's locked-tile count, structures are free (engine). With these, C[t+1] = C[t] + V[t] - R[t] holds to the
  coin for every day 0..28 in **540 / 540** games. Day 29's `hands_present` is 0 in the corpus (captured after the
  last step), so the day-29 residual is booked as wages. On the exemplar that residual equals the ledger's day-29
  wages, 143. The corpus figures match the correctly dated G1 ledger `results/fresh/lead_ledger/leader_112655730.json`
  exactly on days 2-28.
- **Ours, leader worlds:** G1 ledgers `lead_ledger/{leader,ours,deploy}_<ep>.json` (12 worlds, correctly dated; the
  identity error is 0 for all three sides). ours = T = mgt_lead.py at ledger time; deploy = the E2 cell.
- **Ours, new worlds:** `lead_world_trace` traces of 20 deploy builds in the 12 p2750 smoke worlds. They give cash at
  hour 0 and daily revenue; R is taken from the identity. The 185-world panel stores only cumulative revenue per day,
  so it is used for revenue ratios only.

### 0.2 Leader corpus (medians over 540; day 1 = days 0+1)
| day | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cash at day start C | 6 | 3 | 9 | 34 | 388 | 764 | 36 | 91 | 2,069 | 272 | 2,864 | 7,453 | 11,524 | 15,427 |
| reinvestment R | 3,635 | 510 | 620 | 154 | 80 | 4,722 | 978 | 1,324 | 4,288 | **7,122** | 1,082 | 1,474 | 546 | 426 |
| revenue V | 637 | 514 | 626 | 496 | 458 | 3,978 | 1,034 | 3,226 | 2,483 | 9,690 | 5,424 | 4,685 | 4,308 | 8,941 |
| C / R | 0.00 | 0.01 | 0.02 | 0.28 | 5.1 | 0.16 | 0.04 | 0.05 | 0.48 | 0.04 | **2.29** | 4.90 | 19.9 | 36.4 |
| share of games with C < R ("bound") | 100% | 100% | 100% | 82% | 26% | 100% | 100% | 100% | 100% | 97% | **13%** | 2% | 0% | 0% |
| share of the season's R spent so far | 10% | 12% | 13% | 14% | 14% | 28% | 30% | 34% | 46% | 66% | 69% | 74% | 76% | 77% |

Day 10 is the largest reinvestment day. On average it holds land 2,600, wheat 2,343, seeds 320, animals 490 and
wages 374.

Distribution of D, the first day of a safe suffix, checked through day 28:
| criterion (m = 0.25) | D histogram (day: games) | median / p90 |
|---|---|---|
| cov: C[t] >= 1.25 R[t] for every later t | 10:6 11:429 12:75 13:26 14:4 | 11 / 12 |
| cov + grow (C[t+1] >= C[t] too) | 10:6 11:422 12:74 13:33 14:4 19:1 | 11 / 12 |
| stress h = 0.3 (every later revenue coin x0.7) | 10:6 11:423 12:81 13:25 14:3 15:2 | 11 / 12 |
| stress h = 0.5 | 10:6 11:411 12:86 13:27 14:6 15:2 16:2 | 11 / 12 |
| stress h = 1 (no revenue at all: cash alone funds the rest) | 11:96 12:46 13:203 14:131 15+:64 | 13 / 15 |
| last bound day (C < R) | 9:15 10:456 11:55 12:13 13:1 | 10 / 11 |

Per team, median (p90) of cov+grow: DECEM 11 (12), M&M&P&Q 11 (11), Mother-Goose 11 (11), DSM 11 (12), Vadim 11 (12),
Boey 13 (13).

### 0.3 Our side
| path | D (cov+grow) | D (stress 0.3) | notes |
|---|---|---|---|
| G1 leader (12) | 11:11 12:1 | 11:11 12:1 | |
| G1 T (12) | 11:5 12:5 13:1 14:1 | 11:5 12:6 13:1 | T holds 1.2-67x the leader's cash on days 2-8 because it spends later, then earns 0.61-0.85 of the leader's revenue on 7 of the 10 days 7-16 |
| G1 deploy (12) | 11:10 12:1 13:1 | 11:11 12:1 | |
| smoke deploy, 7 builds x 12 worlds | 11:79 14:5 | 11:84 | cash on day 11 median 3.8-6.1k (the exemplar had 2.4k in its own world): the deploy never buys the $4,000 quadrant |

Revenue relative to the plan: our revenue per day in the 185 worlds (current default `mgt_lpv_tievalff`) is 0.86 of
the exemplar's on days 0-2, a very tight distribution. The deploy sells nothing on day 0, where the exemplar sold 140
coins of wheat; on days 1-2 the two are 986 vs 1,013. On days 3-11 it is **0.93 (p10 0.87, p90 1.01)**. The rival's
revenue on days 0-2 is 216 / 298 / 547: opponents also sell wheat and fertilizer early, and that is where our early
prices differ.

### 0.4 Decision: a dynamic rule
At hour 0 of day t, for t = 10, 11, 12, before any order of that step:
- h = max(0.30, 1 - our revenue on days 0..t-1 / the plan's revenue on days 0..t-1). The plan is the recording
  actually followed each day.
- B = our money. For s = t..14: require B >= 1.25 x R_plan[s], then B += (1 - h) x V_plan[s] - R_plan[s].
- Also require: the failsafe's deferral queue is empty, or B at s = t still covers it plus R_plan[t] with the 25% margin.
- If all hold, hand off: D = t. Otherwise follow another day. **At day 13, hour 0, hand off unconditionally (cap).**

Replayed on stored paths (Dmax 14, from day 6; same result with Dmax 12):
- leaders on their own plan: 10:6 11:423 12:81 13:25 14:5
- G1 T against the leader's plan: 11:7 12:5
- G1 deploy: 11:11 12:1
- smoke dep7 / dep8 / tw0 against the exemplar's plan: day 11 in all 36 paths

The rule never passes before day 10 on any stored path, so the floor of 10 is not binding. The cap of 13 is the day by
which 99% of leader games are safe; after it the recorded plan belongs to another world (next paragraph).

Why not earlier: days 6-10 are the cash-bound days (97-100% bound, C/R 0.04-0.48). The earlier notes say T loses
there ("the loss is made in the cash-bound days 6-12 and never recovered"), and that is where the leader's same-day
harvest, sell and buy chain matters.

Why not later: from day 11 the plan is no longer cash-limited (C/R 2.3, then 4.9, then 20+). It is also shop-specific
to its own world: same-team games are 19-26 tiles apart by day 11 and 22 from the exemplar. And in the deploy setting,
our executor plus the count model after day 12 beat continuing the leader's plan (E2d vs E2, progress log). A fixed
D = 11 is the fallback if the dynamic rule is not implemented.

### 0.5 What the failsafe has to absorb (exemplar's effective R fixed; deferred purchases retried next day)
| revenue cut h | deferred coins at end of day: 3 / 6 / 7 / 9 / 10 | cash on day 11 |
|---|---|---|
| 0.05 | 75 / 322 / 145 / 466 / 0 | 1,312 |
| 0.10 | 164 / 651 / 530 / 1,099 / 0 | 219 |
| 0.15 | 253 / 981 / 916 / 1,732 / 874 | 0 |
| 0.20 | 342 / 1,311 / 1,301 / 2,365 / 1,967 | 0 |

Proxy using the 185 worlds' own revenue ratios: the largest deferral in a world has median 861, p90 2,354, max 3,161.
The proxy overstates days 0-3 because the deploy does not replay the exemplar's day-0 wheat trades. With land_max 2
(A.6) the $4,000 day-10 land purchase is not made. The day-10 deferral is then 0 for h <= 0.2 (152 coins at 0.3), and
day-11 cash is 5,312 / 4,219 / 3,126 / 2,033 at h = 0.05 / 0.10 / 0.15 / 0.20. Days 6, 7 and 9 are unchanged.

## A. Exact following until D

### A.1 Which recording, and re-retrieval
- **Day 0-5: the deploy's day-0 exemplar**, DSM's seat of 112655730 (team 16732748,
  `data/leader_tapes/16732748_56498734/112655730.json.gz`). The deploy's day-3 retrieval is suspended. It adds
  nothing here: through day 6, leader boards do not depend on shops. The median Hamming to the team medoid on days 3
  and 6 is 0-2 (p90 <= 5) for every team except M&M&P&Q on day 6 (7, p90 29). 173 games are state-identical to the
  exemplar at day 3, and the plan in force on days 3-5 is the same as the exemplar's.
- **Day 6, hour 0: compatible re-retrieval.**
  - Candidates are games whose day-6 start state equals ours on every tile: the label, plus the planting day of every
    crop tile and the placement day of every animal tile. On the exemplar's own state that is 165 games (DSM 81,
    Vadim 84). Their day-6 cash has median 843 vs 743 for the exemplar.
  - Our state is the exemplar's if days 0-5 had no irreparable breakage. Otherwise match our live state with up to 2
    differing tiles, which are then handled as repairs.
  - Choose by the deploy's own shop distance: `leader_plan_retrieval.demand_vec` / `shop_distance` between our two
    revealed shops and each candidate's first two. Break ties by the smallest |candidate day-6 cash - our cash|, then
    DSM before Vadim, then the smaller episode id.
  - Why it matters: the candidates' day 6-10 plans depend on the shops (day-11 board, with / without a demand shop
    among the first two): sheep 11.3 / 3.4, geese 7.4 / 4.2, cows 11.0 / 6.0, strawberries 25.1 / 14.1, tomatoes
    5.7 / 2.7, carrots 3.3 / 0.6. Reinvestment on days 6-10 has median 18.4k (exemplar 17.5k).
  - Hidden state beyond the board (compile, A.2): a candidate is admitted only if its hour-0 shed wheat and fertilizer
    are within +-2 of ours, and its seed slots within +-1 per crop.
- **Day 9, hour 0:** switch only if a candidate state-identical to our day-9 state exists and it lowers the shop
  distance with all three shops counted. There are only 4 such games against the exemplar, all DSM. Otherwise keep the
  recording.
- **What is lost by ignoring our shops until D:** the shop revealed on day 9. Leaders' big day-10 reinvestment (land,
  wheat, animals) reacts to it, and in the corpus the day-11 counts differ strongly with the shops seen by day 9
  (sheep 11.3 vs 3.2, strawberries 23.9 vs 11.1). Following until D means the plan reacts to our day-9 shop only from
  D, through the executor and count model. The day-3 shop costs nothing because leaders ignore it until day 6. The
  day-6 shop is recovered by the day-6 re-retrieval.
- For comparison, the deploy's own retrieval: on day 3 it picks a game 5 tiles off the exemplar, never DSM. On day 6
  it lands within 2 tiles of the exemplar's day-6 board in 180/185 worlds, and 8 tiles off by day 9. On day 9 it is 9
  tiles off on the switch day and 28 by day 12. Its switches are board-plan switches for a closed-loop executor, not
  exact-replay handovers.

### A.2 Plan compilation (offline, once per recording): `scripts/xopen_compile.py`
Run on Kaggle (no local games). Replay the recording through the engine: same seed, forced shops, both seats'
recorded actions, the lead_ledger harness pattern. Hooks go on `_apply_unit_action`, `_commit_unit`, `_do_hire`,
`_do_buy_land` and `_end_of_day`. The replayed final cash must equal the recorded reward (assert).

Output: `results/fresh/xopen_20260925/plans/<team>_<ep>.json.gz`. Per game:
- **Roles.** Role 0 = farmer. Role k = the k-th hand hired that day (hands vanish at midnight; the hands list is in
  hire order). For every step and role:
  - pre-command position (the spawn rule of `scripts/lead_route_order.py::spawn`, checked against the engine)
  - the command, whether it took effect, and the tile it acted on
  - inventory after the step
- **Per step:** shed contents and seed slots before the market phase; the market list as recorded (at most 10); each
  order's effective units and prices; hires issued / effective; land.
- **Cumulative effective counts by step:** E_i(t) purchases per item, S_i(t) sales per item, H(t) hires today, Q(t)
  quadrants.
- **Dependency links:** resource -> consuming commands.
  - bought animal -> the PICKUP at the shed -> the PLACE on its tile
  - seed -> PLANT
  - bought wheat / fertilizer -> PICKUP -> FEED / FERTILIZE
  - quadrant -> every command on its tiles from the purchase step on
- **Per day (correctly dated):** V, R by kind, and the day-start state key for A.1: labels, planting / placement days,
  shed, seeds.
- **Per role and day:** the recorded tile-op list, used for claims (B.2) and role values (C.3).

Compile all 540 games once (3 shards, about 15 s a game). Only the exemplar and the day-6 pool are needed at run
time. To keep the bundle small, keep per ordered pair of first-two shops the pool game closest to the pool's day-11
board medoid for that pair: at most 64 plans.

### A.3 Mapping our units to recorded roles (by role, never by raw hand index)
- The farmer is role 0.
- A hand that arrives in the same step and on the same shed tile as recorded hand k is role k. That is the normal
  case: hires resolve in list order, the first k that cash allows succeed, and spawn tiles follow the same shed
  occupancy while the other units are in sync.
- **Late or missing hires.**
  - When our hand count is below the recording's, the missing roles are ranked by their remaining value today (C.3),
    and a late hand takes the highest-ranked role it can **rendezvous** with.
  - Rendezvous: the earliest recorded step s at which the hand can stand on the role's recorded position after first
    picking up at the shed whatever the role holds at s (from the compiled inventory). The test is: path length +
    pickup steps <= s - now.
  - Until s the hand walks there. Commands the role issued before s are orphaned and become catch-up jobs (B.2).
  - If no rendezvous exists before hour 20, the hand is released to the executor for the rest of the day.
- Hands never keep a role across midnight. Every day starts in sync: the farmer at (4,4), hands spawned by the spawn
  rule.
- **Lagged replay.** A role may run L >= 0 steps behind. At step t its unit executes the recorded command of step t-L
  if it stands on that command's pre-position. L grows by one when a repair uses an extra step (for example a DIG
  before a PLANT). L falls by one whenever the recorded command at t-L is a PASS, which is skipped.
- Slack available to absorb lag, in PASS unit-steps a day (exemplar): 9-79 on days 0-5, but 2 / 20 / 13 / 1 / 0 on
  days 6-10. At hour 23 any remaining lag is dropped, and the survival net (B.2) covers what it cost.

### A.4 Unit commands per step
For each unit mapped to role r with lag L, standing on the recorded pre-position of step t-L:
- The recorded command is a move: emit it verbatim. Moves never fail on an open board, and locked tiles can be crossed.
- The recorded command is a tile or shed op: check it against our live observation (tile kind, crop and animal, the
  unit's inventory, seed slots, shed stock).
  - If it is feasible, emit it verbatim.
  - If not, substitute a command on the same tile and in the same step: first a repair op on this tile (B.1), else a
    useful op the executor's maintenance list has for this tile (WATER / FEED / CARE / HARVEST / FERTILIZE /
    COLLECT, when its inputs are in hand), else PASS.
  - Either way the unit stays on the recorded trajectory, so the role's later commands stay valid. This is the main
    rule: **an infeasible op never desynchronises its unit; only late or missing hires do.**
- The recorded command is a PASS with L = 0: take a PASS-slot detour if one fits (B.2), else PASS.

A unit that is not on its role's pre-position (it is rendezvousing, or it is released) is controlled as in A.3 and B.2.

### A.5 Market orders: same step, same quantities, capped by the plan's effective totals
Each recorded order of step t is transformed in list order. The order of the list is kept: the engine resolves order
i for both players before order i+1, so an earlier SELL funds a later BUY in the same step.
- **HIRE:** kept while our hires today < H(t), the recording's effective hires through this step. The leader over-asks
  often (day 1: 9 asked, 4 arrived; day 10: 16 asked, 11 arrived), and the cap stops us hiring extra hands the plan
  never had.
- **BUY_SEED / BUY_ANIMAL / BUY_PRODUCT item i, quantity q:** q' = min(q, E_i(t) - ours_i(t-1)); dropped if q' <= 0.
  - The leader's failed over-asks (46 on days 0-10 in its own world) therefore buy nothing extra.
  - A deficit from our own earlier failures is automatically retried by the next recorded order for item i. If none
    comes within 3 steps, the failsafe queue (C.4) inserts a catch-up order.
- **SELL item i, quantity q:** q' = min(q, predicted shed stock of i at the market phase, S_i(t) - oursold_i(t-1)).
  Predicted stock = observed shed + this step's recorded deposits by in-sync units; unit actions resolve before the
  market. An unsold shortfall carries forward and sells when stock allows, up to the plan's cumulative S_i.
- **BUY_LAND:** kept while our quadrants < Q(t) and < land_max (A.6).
- **Hire guard:** buys in a step must leave the wages of the plan's hires in the next steps until the next recorded
  SELL (at most 3 steps). The exemplar's day 0 is the pattern: purchases at step 0, 4 hires at step 1.
- When the tier-0 hires of a step (C.2) are not affordable, pull that day's recorded SELLs of items already in the
  shed to the front of the list: the fewest sells needed, then the hires. This is the rule the executor gained in g5.
- Then run the failsafe affordability check (C.1). The list is truncated to 10; catch-up insertions are appended only
  if there is room.

### A.6 Land
- **E1 (leader worlds):** replay all land, since it is a pure replay.
- **E2 default (arm xo1): land_max = 2**, the deploy's measured setting (+5.6k margin on 12 worlds). The executor and
  count model after D were tuned on two quadrants, and E2d showed the count-model phase does worse from a leader-sized
  farm.
- The exemplar's SE purchase ($4,000 on day 10) becomes a cancelled bundle. Its tiles' commands (SE on day 10: 1
  strawberry, 7 wheat; day 11: 9 wheat, 1 strawberry) are released (B.2), and the planting value moves to free
  owned tiles only if the executor has one.
- Arm xo3 keeps land_max 3 (exact including SE).

## B. Breakages before D and their repair

### B.1 Detection and repair, per step
| breakage | detected when | immediate repair (same step) | re-synchronisation |
|---|---|---|---|
| weed on a tile the plan will PLANT / BUILD | day-start scan of the plan's tiles for today and tomorrow; or the op is infeasible | DIG as the substitute op; if seen at the day start, a DIG catch-up job due before the recorded op's step | the planting becomes a catch-up job (PLANT + WATER the same day); if the role itself does DIG + PLANT, L += 1 |
| planting failed or delayed (no seeds because the purchase was deferred; tile occupied) | PLANT infeasible | substitute (maintenance on the tile / PASS) | catch-up job (tile, PLANT, crop, deadline = the executor's catch-up window: strawberry 6, tomato 5, melon 3, wheat / carrot 1 days; never after plant_cutoff). PLANT and WATER must both fit before hour 23 |
| build failed (tile not empty) | BUILD infeasible | DIG as the substitute if the tile holds a weed or a finished crop | catch-up BUILD, then the PLACE chain |
| animal missing (BUY_ANIMAL deferred) | PICKUP of the animal infeasible | the chain PICKUP -> walk -> PLACE is marked infeasible by decision. The unit keeps walking the recorded path doing substitute ops; if the chain is a block of 3 or more steps away from other recorded ops, it is released (B.2) | when the animal is bought (catch-up order), a catch-up job places it (shed -> tile); target = the plan's placement tile |
| input missing (no wheat to FEED, no fertilizer; shed short, or a PICKUP picked fewer) | op infeasible | substitute; FEED gets a survival flag if the animal was unfed yesterday | tier-0 wheat (C.2) prevents most cases; the survival net feeds from free capacity |
| cash short for recorded orders | C.1 check fails | failsafe: tier 0 first, then cuts by EV (C.3-C.4) | deferred orders are retried by the cumulative caps (A.5) and the deferral queue |
| hire failed or late | fewer hands than the recording after the market phase | retry the HIRE next step (tier 0 if committed) | rendezvous or role re-ranking (A.3) |
| sale short (product not in stock) | SELL quantity clipped | none | sold when stock arrives (cumulative cap) |
| cross-role item not there (another role's deposit is lagged) | shed PICKUP infeasible | substitute | retried at the role's next recorded shed visit; otherwise treated as "input missing" |

### B.2 Scheduling repairs without breaking synchronisation
- **Claims.** The compile lists, per role and day, the tiles each in-sync role will act on later today. Repairs never
  target a claimed tile op; they only fill gaps.
- **PASS-slot detour.** An in-sync unit with a run of k consecutive recorded PASS steps at position p takes the
  highest-value catch-up job at tile q if 2*dist(p, q) + ops <= k. It walks, acts and walks back, and is on its
  pre-position again when the run ends. Days 0-5 have large PASS slack; days 6-10 almost none.
- **Release and rendezvous.** A unit whose recorded block has become infeasible by decision (a cut bundle, a skipped
  animal chain, a missing role) is released for that block. The executor controls it, working the pool of catch-up
  jobs, orphaned recorded ops and survival jobs on unclaimed tiles. The executor runs in shadow every step (D.1), so
  its commands for released units are always available. At the end of the block the unit rendezvouses back, or it
  stays released until midnight.
- **Survival net.** From hour 16, any live asset of ours that will die or escape tonight and has no remaining recorded
  or claimed op gets a job. That covers a plant due to be watered, a seedling planted today, and an animal unfed
  yesterday and not yet fed today. It is taken by free capacity first; if there is none, by the in-sync unit with the
  lowest-value remaining ops, which is then released. This is the B2 lesson: leader lists plus a survival net was
  +0.038 in G1.
- **Catch-up queue.** Ordered by C.3 value. A job leaves the queue when it is done, when its deadline passes
  (irreparable, B.3), or at handoff, where it becomes a target entry (D.1).

### B.3 Irreparable, and what happens then
- **Tile.** A tile is irreparable when its recorded state can no longer be reached before the plan's next dependent op:
  - a planting missed beyond its catch-up window;
  - a tile holding a live asset of ours the plan does not have;
  - an asset planted or placed 2 or more days late, whose recorded HARVEST / COLLECT timing no longer fits.

  The tile becomes **executor-owned**. Recorded commands on it are substituted (maintenance or PASS). The executor's
  closed loop gets the plan's board for that tile as its target, with catch-up allowed, and does its maintenance and
  harvests. Everything else keeps following the recording.
- **Role.** A role that cannot rendezvous before hour 20 is released until midnight and back in sync the next day.
- **Game (early handoff, logged as abort).** Any of:
  - Hamming between our labels and the recording's labels > 8 at a day start (exact following should keep it at
    0-2; T was at 1 on day 6 in G1);
  - more than 12 executor-owned tiles;
  - a tier-0 shortfall on two consecutive days.

  Then D = that day, and the handoff of D.1 applies as usual. Following recorded commands on a board a third of whose
  active tiles differ wastes more than it keeps. This is the only case of handoff before the rule of 0.4.

## C. Failsafe by expected value

### C.1 When it runs
At every market phase while following, compute:
- **need** = the step's transformed buys and hires (A.5) + catch-up orders + the hire-guard reserve;
- **available** = money + 0.9 x the quote of each earlier-listed SELL in this step x its units.

If need <= available, emit the list. Otherwise cut, in this order (C.2-C.4).

### C.2 Tier 0: never cut; bought first, ahead of the recorded order
1. **Wages of hands needed for committed work today.** Rank the day's roles by the survival and committed ops they
   carry: water that keeps a plant alive tonight, today's seedlings, feed for an animal unfed yesterday, harvests that
   decay, PLACE of animals already bought. Protect the hires of the smallest role set that covers all of them. Wages
   are tiny (fib: 12 hands = 376 a day) and funded before anything else, from the pulled-forward sells if needed. This
   is lesson 4 (the demand-hire death spiral).
2. **Feed wheat.** Shed + carried + bought today >= live animals today + animals placed today, and >= tomorrow's
   morning need when the plan has no wheat purchase before hour 6 tomorrow.

Watering costs labour, not cash: it is protected by 1 and by the survival net.

### C.3 Value of everything else: expected value per coin
All values use `scripts/fragments/sem_maintenance.py::sm_tile_plan`. The executor copy already loads it through
`_sm()`. It is run on a synthetic fresh asset, with price_fc = the current market quote of the product (the product
sells 2-10 days later; the quote is the only unbiased figure the agent has), fertilizer and wheat at their quotes, and
fert_ok = whether the plan fertilizes that tile later.
- **Crop planting** (crop c on day d): EV(d) = econ units x price_fc - seed - fertilizer inputs.
- **Animal** (species a placed on day d): EV(d) = econ value of the product over the remaining season, with wheat
  inputs netted and the daily fertilizer valued (`collect`), minus the animal's cost.
- **Delay cost:** Delta1 = EV(d) - EV(d+1). The ranking key is **Delta1 / cost**: coins of expected value lost per
  coin freed for one day.
- **Bundles** are ranked as one item:
  - land + the plan's assets on that quadrant for the next 3 days (Delta1 = the sum over the assets; cost = the land
    price);
  - an animal + its (free) structure;
  - seeds bought in one order for one day's plantings.
- **Wheat beyond tier 0.** Buy-ahead of feed for day+2 and later, and the leader's wheat trading: Delta1 = the expected
  price rise, about 1 coin a day (wheat climbs 25 -> 54 over a season). Delta1/cost is about 0.03, so it is the first
  thing cut.
- **Fertilizer buys:** Delta1 = the extra units lost if the FERTILIZE happens a day later, x price_fc.
- **Hires beyond tier 0:** the value of the role's remaining ops today (maintenance-job values + Delta1 of its plan ops)
  / the fib wage. In practice never cut.

Known limitation (v1): a coin available before D is worth more than its face value, because it funds the next
bound-day purchase. Delta1 ignores that timing effect. Arm option `xo_cash_rate` (0.05 a day on revenue shifted past a
bound day) is for a later test, not the first build.

### C.4 Cut order, defer vs cancel, retry
- Sort the step's non-tier-0 items by Delta1 / cost ascending. **Defer** the first ones until need <= available.
- An item is **cancelled** only when EV(d+k) <= 0 for every feasible k before D_cap + its catch-up window: past
  `plant_cutoff` (strawberry 13, tomato 18, melon 19, wheat 25, carrot 26) or `last_animal` (sheep 17, cow 18, goose
  20), or a bundle whose quadrant is excluded by land_max.
- Deferred items join the **deferral queue**, and it is re-ranked every step with the new recorded items. Queue items
  are retried before any new item with a lower Delta1/cost, through the cumulative caps (A.5): a recorded order for the
  same item carries the deficit, and otherwise an inserted catch-up order does.
- A deferred item's EV decays with the delay, so old deferrals lose priority on their own and are cancelled at their
  deadline.

### C.5 Adapting the step's remaining recorded commands, by role
For every cut or deferred item, look up its dependent commands (compile links) and mark them infeasible by decision:
the PICKUP / PLACE of an animal, the PLANT of deferred seeds, the ops on the tiles of a deferred quadrant, the FEED
that needed deferred wheat.
- Single steps are substituted in place (A.4).
- Blocks of 3 or more consecutive steps are released (B.2).
- When the item is bought later, the dependent work comes back as catch-up jobs; the original recorded steps are not
  replayed.
- Roles whose remaining ops become worthless (for example, every op on a cancelled bundle) are the first released to
  the survival net and the catch-up queue.

## D. Handoff at D

### D.1 Deploy variant (new worlds)
- **The shadow executor.** The deploy's executor (`agent()` of the executor section) runs every step from day 0. Its
  commands are used only for released units, and its market output is discarded while following. At init, set
  `_DEP["switched"] = {3, 6, 9}` so the deploy's own retrieval never fires. Keep `_T` equal to the followed recording
  through `_dep_switch(T, Target(followed sem), day, tiles)`, at day 0 and at every re-retrieval, so the shadow
  executor's jobs for released units match the plan.
- **State passed at hour 0 of day D:**
  1. **Target.** The followed recording stays `_T` for days D..11. From day 12 (or from D if D >= 12) the deploy's
     count-model composition runs unchanged (`compose_from` 12). `hands_add_early`, land_max, the sell rule and the
     wheat keep apply as in the deploy.
  2. **Executor `_S`.** `assign` is cleared. `pmap` / `smap` receive every relocation made by repairs: a planting or
     structure put on a tile other than the recording's. Without them the planner would plant the event again.
     `done` recomputes itself (a planted tile marks its event done). `sold` = the recording's `cum_sold[D-1]` (only
     used with sell_source "cum"; the deploy sells as items reach the shed). The maintenance-job cache is kept.
  3. **Deferral and catch-up queues.** Nothing is transferred explicitly. Each item is already a diff between our live
     board and `_T`: a missing planting is a `_T` event still inside its catch-up window; a missing animal is an
     `animals_by_day` entry; missing land is `land_day`. Log what was pending at handoff.
  4. **Executor-owned tiles** simply stay under the executor, which from D owns every tile.
- **Timing budget:** a following step is a table lookup, feasibility checks and cached EV calls, plus the shadow
  executor (0.01-0.1 s a step now). The 60 s bank is not at risk.

### D.2 Leader-world variant (E1, `agents/mgt_lead_xopen.py`)
No shadow executor. At hour 0 of day D: `inner._S = inner._new_state()`, then `S["sold"] = inner._T.cum_sold[D-1]`.
`configure(sem)` already made the leader's game the target, and the board equals the leader's, so `pmap` / `smap` are
the identity. T hires the target's hands for day D at hour 0.

## E. Tests (Kaggle only; KGR_DATASET=yiyangxudmm/kaggriculture-panel-bundle-xopen, KGR_STAGE=results/fresh/kaggle_remote_xopen)

Before each push:
- count RUNNING kernels (`kaggle kernels list --mine --sort-by dateRun`, then `kaggle kernels status` for the recent
  ones);
- push only while fewer than 5 run, and at most 2 of them ours;
- poll in loops.

KGR_EXTRA = `data/leader_semantics,data/leader_tapes,results/fresh/lead_ledger,results/fresh/xopen_20260925/plans`.
No submissions.

### E0. Compile (1 kernel): `scripts/xopen_compile.py`
All 540 recordings (or at least the exemplar and the day-6 pool). Checks:
- replayed final cash = the recorded reward in every game;
- per-day V and R equal the offset-corrected corpus (section 0.1);
- the static spawn rule equals the engine's hand positions at every step.

### E1. Leader worlds: how much of T's gap is opening execution (`agents/mgt_lead_xopen.py`, runner `scripts/xopen_g1.py`)
Setup:
- `mgt_lead_xopen.py` loads `agents/mgt_lead.py` by path (no edit) and exposes `configure(sem, **cfg)` and
  `agent(obs)`. On days 0..X it returns the recording's action dict verbatim (deep copy); from day X+1 it calls T
  (D.2).
- It exposes `_S = {"log": ...}`, merging its counters with T's, so `lead_g1.play` stores them unchanged.
- `xopen_g1.py` sets `LEAD_AGENT_PATH` per worker and runs `lead_g1.play` over the 12 `lead_g1.GAMES` x cells.
  Results go to `results/fresh/xopen_20260925/g1/<cell>/<ep>.json`.

Cells (7 x 12 = 84 games; T's configuration everywhere = `p1_min_value=30;release_stale_d=true;fert_hold=1`):
| cell | replay days | handoff |
|---|---|---|
| T | none | T all game (baseline) |
| X5 / X8 | 0-5 / 0-8 | day 6 / 9 |
| **X10** | 0-10 | **day 11 = the fixed-D fallback** |
| X11 | 0-11 | day 12 |
| Xdyn | 0..D-1 | the 0.4 rule on our live cash; in a leader world our cash is the leader's, so D = that game's own date (11 in 11 of 12 G1 games, 12 in 1) |
| X29 (control) | all | none; **must reproduce the leader's final cash to the dollar, 12/12**, else the harness is wrong |

Report per cell:
- G1 ratio mean12 / mean11 / clean9 (the opponent-collapse convention of the progress log);
- paired vs T in coins (mean, 95% CI, better / worse);
- cash by day 0-15 / leader;
- mean placement day of geese / cows / sheep and animals placed by day. The T-gap split puts +7.5k here: geese on day
  12.1 vs 8.8, cows 5.9 vs 5.0, sheep 3.1 vs 1.9;
- units available by day for the "later goods" +5.9k line;
- revenue gap by product; Hamming on days 6 / 12 / 20;
- T's first-day behaviour after the handoff: failed buys, idle passes, catch-up plantings.

Reading: X10 - T = the part of the 13.45k gap that is opening execution given T's later game. X11 - X10 and X8 - X10
show whether the date matters. The predicted order is X10 around X11 > X8 > X5 > T.

### E2. New worlds: the deploy following exactly until D with repairs (12 smoke worlds, 1 kernel)
Builds from `scripts/xopen_build.py`, which copies the current `agents/mgt_lead_deploy.py` (sha recorded) and inserts an
XOPEN section before a new last-callable entry point:
| arm | content |
|---|---|
| xo0 | unmodified copy. **Harness check:** reproduces the current default (`mgt_lpv_dep8` / `mgt_lpv_tievalff`) to the dollar in 12/12 smoke worlds |
| **xo1** | exemplar exactly to the dynamic D + day-6 strict re-retrieval (+ day 9 if a state-identical game exists) + B repairs + C failsafe + land_max 2 |
| xo2 | xo1 without re-retrieval (the exemplar to D) |
| xo3 | xo1 with land_max 3 (exact including the day-10 SE purchase) |

- Runner: `scripts/xopen_trace.py`. It calls `lead_world_trace.run_one` after wrapping the loaded entry point, so it
  also records hour-0 money, board label counts and hands per day, and at the end `_XO_REPORT` from the agent's
  globals.
- Per-step log `_XO_LOG`: {step, kind: breakage / repair / defer / cancel / cut / rendezvous / release / abort /
  handoff, cause, role, tile, item, qty, EV, Delta1/cost}.
- Report:
  - margin vs xo0 (paired, 95% CI, better / worse) and vs y3; own / rival split;
  - **breakages per game by cause and day**, repairs attempted / succeeded;
  - failsafe cuts: item, day, EV, Delta1/cost; deferred vs cancelled; coins deferred by day;
  - handoff day distribution; re-retrieval pick (shop distance);
  - cash by day 0-15 against the recording's cash;
  - animals placed by day (geese / cows / sheep);
  - Hamming to the recording at each day start until D;
  - timing (max s / step, bank).
- Secondary, optional: xo1 in the 12 G1 worlds through a `lead_ablation.py`-style E2 cell, with the episode held out
  of retrieval (exemplar 112661570 in world 112655730).

### E3. Full 185-world p2750 panel
Only if E2's xo1 (or the best arm) is clearly positive vs xo0: paired 95% CI above 0 and >= 8/12 better. One arm, 2
shards.

### Static checks (local, one process, no games)
- parse and Kaggle-loader entry (last callable);
- cumulative-cap transformer on the exemplar's recorded market lists (the leader's own failed over-asks must map to
  q' = 0 when our history equals the leader's);
- failsafe ranking on synthetic purchase lists (tier 0 first; wheat buy-ahead cut first; land bundle ranked by the sum
  of its assets' Delta1);
- rendezvous planner on the compiled positions;
- the state-key matcher reproducing the 165-game day-6 pool;
- handoff state builder: after D, `_plan` issues no plant job for an already planted event.

## F. Files and order of work
- Done (this design): `scripts/xopen_cash_safe.py`, `scripts/xopen_open_stats.py`, and their outputs here.
- To build, all new files:
  - `scripts/xopen_compile.py` (E0)
  - `agents/mgt_lead_xopen.py` and `scripts/xopen_g1.py` (E1)
  - `scripts/xopen_build.py` -> `agents/mgt_lpv_xopen0..3.py`, and `scripts/xopen_trace.py` (E2)
  - `scripts/xopen_report.py`
- Order: E0 -> E1 (84 games, about 35 min in one kernel) -> build + static checks -> E2 (48 games) -> E3 if positive.

## Risks and open points
1. **Shop fit after day 6.** The day-9 shop is ignored until D. The corpus shows it matters for the day-10
   reinvestment. The day-9 strict re-retrieval pool is tiny (4 against the exemplar).
2. **The count-model phase from a leader-shaped farm.** E2d (leader plan to day 11, then the count model) was -0.039
   vs E2 in G1. land_max 2 (xo1) and xo3 separate the land part of that.
3. **Revenue cuts of 15% or more** leave deferrals uncaught at day 11. The dynamic rule then extends to 12-13, but the
   plan's day 11-12 commands belong to a different world.
4. **Hire fragility on days 1-5.** Day-start cash is 1-14 coins for the exemplar, and our hour-0 hires depend on
   hour-0 sells of midnight-dumped fertilizer. Rendezvous and pulled-forward sells handle it. How often it fires is
   unknown until E2.
5. **Frozen opponents** in G1: 112708229's opponent collapses; report mean11 / clean9. In the smoke worlds the
   opponents are recorded, so our changed market behaviour can break their open-loop orders. Report opponent failed
   orders.
6. **The new-world upside may be small.** The progress log puts the deploy's new-world loss mostly in plan scale after
   day 12, not in the opening (item 6 of the deployment gap decomposition). E1 measures the opening-execution share
   in leader worlds; E2 says whether it transfers.
