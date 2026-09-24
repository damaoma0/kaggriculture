# A semantic architecture for Kaggriculture: proposal for discussion (2026-09-24)

Status: discussion document, no code. Benchmark: the 2750-3000 exact panel (`data/ladder_panel/p2750/`). Study
material: the six teams rated 3000+ on 2026-09-23 (Boey 3080, M & M & P & Q 3060, Unknown Mother-Goose 3052, DECEM
3043, Vadim Vasilenko 3033, DSM 3001). Harvest and extraction are running (`data/leader_semantics/`, stream S1); the
value of layout freedom is being measured (`results/fresh/layout_value/`, stream S2). Sections marked PENDING wait for them.

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
- That layout freedom is worth something (PENDING: S2; prior routing results suggest it is modest).

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
outside. Pastures and coops are structures, so animal placement is decided when they are built. PENDING (S2): how
much this is worth. The prior results (routes within 4% of optimal, idle time fragmented at day end) suggest the
direct walking saving is modest; its real value may be that freed hours absorb maintenance that is skipped today.

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
| layout | no | care cost vs distance |
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
