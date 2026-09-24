# A semantic architecture for Kaggriculture: proposal for discussion (2026-09-24)

Status: discussion document, no code. Benchmark: the 2750-3000 exact panel (`data/ladder_panel/p2750/`). Study
material: the six teams rated 3000+ on 2026-09-23 (Boey 3080, M & M & P & Q 3060, Unknown Mother-Goose 3052, DECEM
3043, Vadim Vasilenko 3033, DSM 3001). Harvest and extraction are running (`data/leader_semantics/`, stream S1); the
value of layout freedom was measured (`results/fresh/layout_value/`, stream S2: none for a simple rule).

## 1. The idea in one paragraph
Stop replaying what the leaders DID; learn what they DECIDE and generate our own play from it. A leader's game is
compressed into a small set of semantic decisions conditioned on the shops visible at the time: how many tiles of
which crop, which animals and how many, when to expand land, when to retire and replant a cohort, and how much to
maintain. Our agent retrieves or predicts those decisions for its own world, turns them into a farm plan laid out on
OUR board, and executes the plan with our own scheduler, closed-loop, hour by hour. The recording never touches the
action stream, so the two failure modes that killed every graft (budget-exact actions, hidden state at a handoff)
cannot occur by construction. What remains hard is execution quality and cohort economics, and those are exactly
where the earlier executors lost.

## 2. What is measured, and what is assumed
Measured (this project):
- Plans are shop-driven. Visible shops explain leaders' boards: DSM sheep R² 0.98 -> 0.80, cows 0.94 -> 0.78,
  strawberries 0.95 -> 0.67 from day 9 to day 24; 70-100% of count variance by day 9 across leaders.
- Prices, cash and the opponent add ~0 to the plan once shops and DSM's own board 3 days earlier are known (median
  −0.001 R²). Cash moves timing (which hour a purchase goes through), not quantities. A price-aware planner is worth
  at most 1-2k a game.
- The top leaders share one fixed opening (day-6 boards identical across DSM, DECEM, Mother-Goose, Vadim;
  2 cows, 3 sheep, melons 6 -> 10, strawberries from day 2), whatever the shops.
- Replaying a leader's actions fails for mechanical reasons: budget-exact streams (DSM starts days 1-3 on a median
  4/3/8 coins; the engine clips 34% of its opening hires), and hidden state at a handoff (O1r −51k even where the
  day-6 board matched). Protecting hires by holding cash starves purchases (hire reserve −34k).
- Execution quality is worth a lot: DSM's own plan replayed in our worlds gives 95.5k against DSM's 109.2k.
- Labour: the leaders' routes are within 4% of optimal for their layout; our scheduler (`scripts/labour_search.py`,
  regret insertion + ruin-and-recreate, 0.14 s a day) does the same jobs with ~1 hand a day fewer (1,363 of ~4,720
  wages a game) because it re-assigns jobs across hands.
- Maintenance is demand-conditioned in the leaders' play (Mother-Goose cares sheep 46% of animal-days without a Yarn
  Store, 75-90% with one; 3% -> 94% the day a Yarn Store opens), and much of it is provably worthless by the engine
  rules (unfertilised strawberries yield 1 whether watered or not; watering matters only for survival, a one-time
  crop's bonus window, and a fertilised ongoing crop's production day; care on the last production day is wasted).
- Previous executors failed on ECONOMICS, not on commands: the continuation executor reproduced 8/12 native 3-day
  windows exactly, yet lost 4k-12k because it kept existing cohorts alive and stopped planting replacements ("a
  continuation needs economic continuity as well as executable care", `docs/continuation_execution_and_recovery.md`).
- Where our current agents lose: late shops (5-8) the tape library cannot cover (~4.5k of the gap is generated, not
  recorded, by the leaders), and strawberries at 2750-3000 (−20.8 units, −2.9k a game, almost all days 12-17: the
  leaders commit about one reveal earlier).
Assumed (to be tested):
- That leaders' decisions transfer across opponents (they barely condition on the opponent, which supports it).
- That a composition plan plus computed maintenance recovers most of a leader's value when executed by us.
- (Tested and refuted: a simple care-cost layout is worth nothing; see [F].)

## 2b. First look at the 3000+ material (240 games, 40 per team, 2026-09-24)
`data/leader_semantics/` (stream S1): both seats' recorded actions replayed through the engine with the recorded
seed and shop order; recorded cash reproduced in 240/240 games; per-day boards, plantings, harvests, animals,
maintenance per tile, labour and market for the leader's seat. Scripts `scripts/extract_leader_semantics.py`,
`scripts/leader_semantics_openings.py`, `scripts/leader_semantics_maintenance.py`.
- **Two opening families, not one.** DSM and Vadim play one identical day-6 board in 100% of games, Mother-Goose 85%,
  DECEM 70% (117 of the 240 games share it exactly: 10 melons, 10 strawberries, 2 cows, 3 sheep). The #1 team, Boey
  (3080), plays a different one: 10 melons, 4.4 strawberries, 4.8 cows, 2.5 geese, 2.9 sheep, 17 distinct boards in
  40 games. M & M & P & Q (3060): 9 melons, 8 strawberries, 6.5 wheat, 4.8 cows, 2.5 sheep, 35 distinct boards.
  [A] therefore needs a choice between families (or a learned rule for it), not one schedule.
- **Maintenance really is "maximum by default, exceptions where the engine says it is worthless".** Animals are fed
  and cared 83-98% of animal-days on days 7-17, falling to ~50-70% (sheep, cows) on days 18-29 as their last
  productions pass; geese stay at 72-89%. Crops follow the engine's value rules, not "always": melons are watered on
  about half the days while young (survival only) and 98-100% in their bonus window (days 7-17); strawberries on
  54-74% of days (every other day plus); wheat, tomatoes and carrots 56-77%. This is what [E] would compute.
- **Current leaders barely condition sheep service on demand.** Sheep care with vs without a visible Yarn Store:
  DSM 0.80 vs 0.65, Vadim 0.78 vs 0.67, Mother-Goose 0.81 vs 0.73, DECEM 0.80 vs 0.70, M&M&P&Q 0.78 vs 0.77, Boey
  0.81 vs 0.90 (reversed). The old Mother-Goose tapes' 46% -> 75-90% switch is largely gone: they keep sheep serviced
  regardless, which again points to "service everything that can pay" rather than a demand-keyed rule.

## 3. Components and how they compose
```
 visible shops, day, our farm (full observation), cash, rival farm (observable)
        |
 [A] Opening program (days 0-5): leaders' fixed opening as TARGETS, executed closed-loop
        |
 [B] Plan model (learned): shop-conditioned composition + cohort calendar  --->  [C] Plan evaluator (optional,
        |          "what to own, when to add / retire"                          engine rollouts, V9-lite style)
        v
 [D] Daily compiler: today's deltas (plant / buy / place / build / dig / retire) + maintenance jobs [E] + harvests
        |                                              [E] Maintenance value rules (computed from the engine)
        v
 [F] Layout: where each new cohort goes (care cost vs distance)       [G] Market: sells, wheat stock, cash projection
        |                                                                    |
        v                                                                    v
 [H] Labour scheduler: jobs -> farmer + k hands, k chosen by marginal value vs fib cost, routes
        |
 [I] Hourly executor: route -> this hour's command per unit; market orders; verify effects on the observation;
     repair (retry purchases when cash allows, re-schedule the rest of the day in 0.14 s when anything deviates)
```

**[A] Opening program.** The leaders' opening is fixed, so it is one target schedule: by the end of day d, these
tiles planted with these crops, these structures built, these animals placed, this land bought. Our executor pursues
the schedule with whatever cash the world gives it: purchases retried the hour cash allows, hires sized to the jobs
of the day, never a recorded order stream. Success criterion: our day-6 board within a few tiles of the leaders' and
our day-6 cash in their 740-810 band (ours today: 213) across the panel's worlds.

**[B] Plan model: the heart of the "semantics".** Represent each leader game as a plan grammar: cohort events
(`plant 8 ST on day 2`, `build 2 pastures + buy 3 sheep on day 5`, `retire the day-2 ST on day 18, replant WH`,
`buy land NE on day 6`) plus a service policy. Two ways to produce a plan for our world, both conditioned on the
visible-shop demand vector the router already uses:
- Retrieval: k nearest leader games by visible-shop demand (the router's distance, but over 3000+ plans rather than
  Mother-Goose's actions), blend their composition trajectories, re-plan at every reveal. It inherits the router's
  robustness and none of its execution fragility, because plans are layout-free and budget-adaptive.
- Regression: per decision type, a count model on the shop demand vector plus our own lagged composition (the flow
  form in which prices added nothing). This generalises to shop sequences no leader played, which is where the tape
  library runs out (shops 5-8).
The model must carry cohort LIFECYCLES explicitly (planting cadence, the day a strawberry or tomato cohort is
retired, replanting, pasture-to-wheat conversions late in the season). That is the lesson of the continuation
executor, and it is also where the strawberry deficit lives (the leaders commit a reveal earlier).

**[C] Plan evaluator (optional).** When retrieval yields several plausible plans (or at a reveal), simulate the
remaining season with the engine clone and a rival model and pick on margin: V9-lite's machinery, pointed at plans
instead of tapes. Its known blind spot (switches that raise our cash but the rival's more) stays; its cost is now
affordable (V9-lite: day-12 search median 6-12 s).

**[D] Daily compiler.** At hour 0, diff plan against farm: new cohorts to establish, cohorts to retire, structures,
land. Emit jobs with dependencies (buy seed -> plant -> water the same day; buy animal -> pickup -> place -> feed).

**[E] Maintenance: maximum by default, exceptions computed.** The user's framing (maximum maintenance by default,
explicit rules for when to skip) fits the engine closely, with one refinement: most skip rules can be DERIVED rather
than learned. Every maintenance job gets a value from the engine's rules (the yield it protects or adds, times the
product's forecast price, minus the labour it takes), e.g.:
- water a young seedling: survival (plant dies after 2 unwatered days) -> high;
- water an unfertilised strawberry: only every other day for survival -> half the watering of "max";
- feed an animal on its production day: protects the whole care bank -> high; on other days only +1 bank;
- care on the last production day, anything that cannot pay before day 29: zero.
Default = do every job with positive value; exceptions = when labour binds, the scheduler drops the lowest-value
jobs. The leaders' observed skip patterns (sheep care without a Yarn Store, etc.) then become a VALIDATION target for
this calculus, not its source. Where they disagree, we learn something (either our valuation or their play is off).

**[F] Layout.** Assign each new cohort to a tile by care cost: daily-visited items (animals: feed + care; tomatoes in
their production window) nearest the shed, every-other-day items (strawberries) next, short crops (wheat, carrots)
outside. Pastures and coops are structures, so animal placement is decided when they are built.
MEASURED (S2, `scripts/layout_value.py`, DSM's 109 games, the scheduler's time model): walking is ~40% of unit-hours
(farmer 39.5%, hands 42.4%), but a "most-cared-for nearest the shed" greedy re-layout is WORSE in 109/109 games
(−1,975 unit-hours, −124 wages a game; 517 days need more hands, 8 fewer), and DSM's layout is already as close to
the shed, visit-weighted, as the greedy (3.63 vs 3.71). The greedy scatters tiles that are worked together on the
same day. So layout is not a lever by itself: keep the leaders' spatial pattern (co-located same-day cohorts), and
only a joint layout-and-schedule optimiser could still find something. Layout drops from the critical path.

**[G] Market.** Reuse what exists: sell timing (`sell_lead`), the wheat stock trade (buy ~700 early, sell ~800
late), the flow model of rival sales (`agents/adaptive_market_order.py::FlowModel`). New: a 24-48 h cash projection
(scheduled sells at forecast prices minus scheduled buys and hires), so purchases can spend "to the last coin" the
way the leaders do without the budget-drift failure: the hire-reserve experiment showed a blind reserve starves the
plan, a projection does not.

**[H] Labour scheduler.** Exists (`scripts/labour_search.py`); needs the executor's job format and a choice of k
(hands) by marginal value against the fib cost instead of "as few as possible".

**[I] Hourly executor.** The observation is complete for our own farm, so no dead reckoning of state is needed; only
plans are dead-reckoned. The bounded continuation compiler (`docs/continuation_execution_and_recovery.md`,
max 0.29 s an action) is the nearest prototype.

## 4. Learned versus computed
| decision | learned from 3000+ games | computed |
|---|---|---|
| opening | the fixed target schedule | how to reach it with our cash |
| what to own (crops, herd, land) and when | yes: shop-conditioned plan model | scaling to our cash and land |
| cohort retirement / replanting | yes (cadence, day) | whether a retirement pays (engine value) |
| maintenance | only as validation | value of every job from engine rules |
| layout | the leaders' spatial pattern (same-day cohorts together) | only jointly with the schedule, if at all |
| hands per day, routes | no | scheduler |
| selling, wheat stock | partly (existing heuristics) | cash projection, price forecast |
| rival response | no (leaders ignore it) | optional: V9-lite plan evaluator |

## 5. The hard parts, in order of risk
1. **Execution quality.** Every executor in this project has lost to replay so far (−4k to −12k). The new design
   removes the two mechanical failure modes, but a closed-loop executor has to be as good as the leaders' own
   (the 95.5k vs 109.2k gap is the prize and the risk).
2. **Cohort economics.** Replacement cycles, late conversions, the endgame (stop investing in what cannot pay by
   day 29, liquidate). This is where the last executor lost.
3. **Generalisation of the plan model.** Six teams, perhaps 300-400 games; shop sequences are combinatorial. Retrieval
   is safe inside the data, regression is needed outside it; both need held-out checks by team and by shop pattern.
4. **Cash flow.** Leaders spend to the last coin; our plan must stay feasible at our prices.
5. **Market interaction.** The plan changes the rival's prices; V9's lesson (own +7.2k, rival +8.8k) applies to any
   plan chosen for our own cash.
6. **Validation cost and time.** Every stage needs panels; the Kaggle pipeline exists and is fast (185 games in
   ~20 min per session), and the official-runner test must be run on the final package (a background thread that
   passed every panel crashed the official runner this week).

## 6. What prior work already gives us
- Study data and tools: 109 DSM tapes with boards (`data/dsm_tapes/`), ~200 leader tapes (`data/leader_tapes/`),
  harvest (`scripts/harvest_leader_tapes.py`), exact re-resolution of replays with the engine
  (`scripts/extract_dsm_price_panel.py`, 0 mismatches), shop-conditioned count models (`scripts/shop_target_predictability.py`,
  price-awareness panel).
- Execution: the labour scheduler, the bounded continuation compiler, the overlay's hidden-hand machinery and repair
  jobs (`scripts/fragments/mgt_sheep.py`), the hire guard.
- Simulation: the isolated engine clone and rival trajectory model (V9 chain), V9-lite's affordable search.
- Market: sell_lead, wheat trading, FlowModel.
- Evaluation: the 2750-3000 panel, the 180-world ladder panel, live V56 plus five public opponents, Kaggle remote
  panels, the package builder and the isolated official-runner test.

## 7. Gates (each one measured before the next is built)
- G1 Executor fidelity ("semantic replay"): give the executor DSM's OWN plan, extracted semantically, in DSM's own
  worlds (seed, forced shops, the opponent's recorded actions). Pass: our cash >= 95% of DSM's recorded cash on
  average (replaying DSM's actions gives 87%). This isolates execution from planning.
- G2 Plan model: predict held-out leader plans (by game and by team) from visible shops; report per decision type.
- G3 Opening: [A] reaches the leaders' day-6 board and cash band in the panel's worlds.
- G4 Whole agent against y3 / V9-lite on a 60-world slice of the 2750-3000 panel and live V56.
- G5 Acceptance: full 2750-3000 panel, 180 ladder worlds, live V56 plus the public opponents, official-runner test.

## 8. Realistic scope
The competition closes on 2026-09-30 and submissions are frozen for the final evaluation. G1 alone is several days
of work (the executor must handle planting, animals, structures, land, market and repair), and G1-G5 are two to three
weeks. So the full architecture does not ship in this competition; saying otherwise would repeat the opening story.
What could plausibly be tested inside the window, as increments on the current chassis:
- a semantic router: choose tapes by distance to the retrieved 3000+ composition trajectory instead of to the tape's
  shop sequence (cheap, uses the existing library);
- a semantic overlay: extend y3's mechanism (service the assets the world demands but the tape neglects) from sheep
  to all products, driven by the plan model's composition deltas, with the hidden hands and the scheduler.
Both reuse validated machinery and would be judged by the same panels. Neither is the new architecture; both are
steps it would need anyway.

## 9. Questions for the user
1. Is the goal a better final submission by the 30th (then only the increments above are realistic), or the new
   architecture as research beyond the deadline?
2. Retrieval or regression first for the plan model? (Recommendation: retrieval, because it is safe inside the data
   and reuses the router's distance.)
3. Should the plan evaluator ([C], rival-aware) be part of the design from the start, given its known blind spot?

## 10. Decision (user, 2026-09-24 evening) and the plan to a feasible submission
The user: the goal is a feasible submission; open more threads; focus on the leader games; rival-awareness designed
but of lower importance. The MVP that can plausibly land by the 30th:

**Leader-following agent (`agents/mgt_lead.py`).** The plan is a leader game's own per-day BOARD (the layout
measurement says their layout is already as good as anything we would compute, and the grid is the same), chosen by
retrieval from the 240-game corpus and re-chosen at reveals. Each day our planner diffs the target's upcoming boards
against our real board and emits jobs (land, builds, animals, plantings, digs, fertilizer), adds maintenance
(maximum by default, engine-derived skips) and harvests, and the existing job compiler
(`scripts/fragments/continuation_executor.py`) packs them into routes and hourly actions. Purchases retry when cash
allows; selling follows the target's per-day sold units. No recorded action is ever replayed.

Threads (started 2026-09-24 ~19:00):
- T1 (strongest model): the agent + gate G1 (follow a leader game in its OWN world; cash ratio >= 0.90 on 12 games of
  the common opening family). Progress log `docs/lead_agent_progress.md`.
- T2: plan selection, retrieval vs regression (gate G2), `scripts/leader_plan_retrieval.py`.
- T3: opening families, per-day targets and outcomes, `data/leader_semantics/openings.json`.
Timeline: G1 by 09-26; retrieval wired in and G4 (60 worlds of the 2750-3000 panel + live V56) by 09-27; full
acceptance, packaging and the official-runner test 09-28; hand-over 09-29. At every gate the comparison is the
validated V9-lite + y3 (`docs/v9lite_validation_record_20260924.md`), which stays the fallback. If G1 fails by 09-26,
the MVP does not ship and the remaining days go to hardening the fallback.

## 11. Rival awareness (designed, not on the critical path)
What is observable: the rival's whole farm every step (tiles, animals), the market prices and the shops. What it is
for: the plan's value is margin, and our supply moves the rival's prices (V9's failure mode: own +7.2k, rival +8.8k).
Design, cheapest first:
1. Residual demand: when retrieving a plan, discount products the rival already supplies heavily (its board counts
   per product against the visible shops' demand). One extra term in the retrieval distance; testable on G2's data
   as "does it predict leaders' plans better" (the leaders ignore the rival, so expect ~0 there) and on panels.
2. Sell timing against the rival's harvest calendar (its crops' ages are visible): avoid selling into the day its
   strawberries or wool come in. Extends the existing FlowModel.
3. Plan evaluation with a rival model (V9-lite machinery on plans): only if 1-2 show value; the known blind spot stays.

## 12. Plan selection measured (T2, gate G2 offline; `results/fresh/leader_retrieval/summary.md`)
Leave-one-game-out over the 240 games, decisions at the reveals: retrieving the nearest leader game (shop-demand
distance + own-board Hamming, lambda 1.0, k 1-5) predicts the board 3 days ahead almost exactly at day 3 (98-99%
within 8 tiles) and well at day 6 (77%), but from day 9 on under 7% of predictions land within 8 tiles: after the
shared opening no single recording is a tile-level analogue of a new world. From day 12 a ridge regression on
composition COUNTS (visible shops + own counts) beats retrieval (count MAE day 15 +3: 1.00 vs 1.81). Same-family
restriction changes nothing (cross-family distances are already large). Leave-one-TEAM-out is much worse, but that
measures imitating an unseen team; we follow these same teams in new worlds, so leave-one-game-out is the relevant
test. Design consequence: two target modes in the planner, tile-level target boards through ~day 9 (opening and
early game, retrieval), composition targets from ~day 12 (regression), laid onto our own board by the planner.
