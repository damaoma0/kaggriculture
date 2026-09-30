# Tape transition repair — 24 September 2026

Research implementation, development failures, and frozen qualification results. The submitted agent and frozen V9 source are unchanged.

## What changed

`scripts/value_tape_repair_r1.py` adds a small execution adapter around a private copy of original m1. When a donor tape would destroy a cohort that the baseline retains at the next shop reveal, the search can propose a repaired version of that tape. A cohort is identified by coordinates, species, and birth day. Repairs last only until the next reveal.

The adapter adds emergency feed/water jobs to the existing funded labor scheduler, preserves necessary harvest jobs, and intercepts destructive digging or idle commands on protected assets. The simulator charges the actual labor, feed, purchases, and displaced work. A large scheduler priority is a service ordering device, not an invented profit credit.

The search retains V9's ordinary candidates and adds at most two repaired alternatives, each protecting at most six cohorts. Up to three attempts close secondary cohort failures. These alternatives are scouted, screened over four futures, and at most one is evaluated over eight. Incomplete candidates cannot be selected.

This is a bounded service repair and donor-plan transition. It does not yet compile arbitrary semantic production targets, remap every donor tile, or create new herd and planting plans from scratch.

## The development failure and its cause

The initial six-case screen included the two exact m1 recordings for Snorlax and EvilMango and four large unchanged V56 losses. Five results matched V9. One regressed:

| Development world | V9 margin | Initial repair margin | Difference |
|---|---:|---:|---:|
| `random-06-v56` | −8,897 | −10,467 | −1,570 |

A day-15 transition onto route 408 preserved a young tomato at `(9,1)`, born on day 13. Execution used two watering attempts and suppressed one dig. The forecast passed all eight futures, predicting mean margin gain 1,023 and minimum gain 163.

Actual own cash rose **7,227**, but rival cash rose **8,797**. The execution repair worked; the competitive forecast was wrong. Our changed supply improved the rival's milk and strawberry receipts enough to outweigh our own gain.

Adding 24 ordinary shop futures (`value_tape_repair_r2.py`, 32 total) still approved this bad transition. More shop samples did not resolve the rival sale-timing error.

Hindsight attribution is isolated in `forecast_attribution.json`. Supplying actual future shops and recorded rival flows made the forecast less optimistic, but did not exactly reproduce the live result: the public rival model is approximate, and forecast rollouts omit future own weeds. None of these actual future inputs enter the candidate policy.

## R3: check sale-timing sensitivity separately

`scripts/value_tape_repair_r3.py` validates a proposed repair against the best admissible ordinary V9 fallback at the same current state:

1. Complete 16 balanced shop futures and require the existing cash, margin, cohort, and hire rules.
2. Run 16 additional stress scenarios: the original eight worlds with modeled rival sales delayed by six and twelve hours. Purchases stay at their original times; total net product quantities are conserved.
3. Require every stress scenario to respect the ordinary downside bound. Stress scenarios are not assigned probabilities or blended into the expected gain.
4. On veto or incomplete validation, use the ordinary V9 fallback. A cooperative 18-second decision deadline checks between simulations and every eight simulated turns.

On the known regression, the first two stresses gave margin changes of −375 and −573. The latter breached the 500 downside limit, so R3 retained V9's −8,897 result.

These stress tests are useful sensitivity checks, not a complete responsive opponent policy or a guarantee against market-model errors.

## Wider development screen

R1 ran on all 32 earlier V56 worlds plus the two original-m1 recordings: one better, one worse, 32 unchanged versus V9. Six completed games were reused only after verifying identical frozen source and harness bytes.

The improvement was `random-11-v56`, with shops Farmers, Bakery, Ice Cream, Bakery, Farmers, Farmers, Ice Cream, Farmers. A day-12 route-582 transition needed one sheep at `(6,2)`, born on day 8, preserved through day 15.

| Policy | Final margin |
|---|---:|
| Original m1 | −1,667 |
| V9 | +763 |
| R1 / rechecked R3 | +3,468 |

R3 completed all 16 ordinary futures and 16 sale-delay stresses for this repair. The worst stress margin change was +2,469. The full live recheck gained **2,705 in margin versus V9**, consisting of own cash **−291** and rival cash **−2,996**. This is a competitive gain, not an own-cash increase relative to V9's later adaptive decisions.

Against original m1 in that world, own cash rose 1,777 and rival cash fell 3,358, producing the 5,135 margin improvement. The validation predicted mean own-cash gain 1,721 against its native continuation comparator. V9 subsequently makes a separate day-18 decision in the live comparison; the forecast does not recursively simulate future calls to the value selector.

R3 was rerun on these two intervention cases. The other 32 development games were R1 runs, and are not presented as 32 additional R3 executions.

Across 102 R1 development decisions, 261 of 587 ordinary alternatives failed cohort preservation. The bounded repair search attempted 160 alternatives and 156 survived their initial cohort check. Of the 160, 152 ultimately had nonpositive risk-adjusted forecast value, four failed cohort/hire protection, one failed the final admission gate, and three were admitted (two selected). This is high physical success among the deliberately small attempted repairs, with sparse economic gains; it is not 97.5% coverage of arbitrary tape mismatches.

The exact Snorlax loss of 25,467 remains unrecovered. Repairing its missing sheep or tomato cohorts made candidate transitions feasible, but their forecast economics were negative. EvilMango's existing V9 recovery of 6,421 was retained in the R1 screen.

## Fresh qualification protocol

Before outcomes were observed, the R3 policy, harness, dependencies, and random design were frozen at:

`results/fresh/tape_repair_20260924_01a0/r3holdout24/`

- 24 independently generated uniform eight-shop worlds, excluding the earlier development seeds and another agent's reserved seed range.
- Every world crossed with live V56 and live original m1, alternating own seat by world.
- Original m1, V9, and R3 each run from day zero: 48 matched comparisons, 144 full games, **24 independent worlds**.
- No outcome-based exclusions or policy tuning on this sample.
- Decisions only on shop reveals at days 12, 15, and 18; only current public observations and own memory are provided to the planner.
- Separate accounting for own cash, rival cash, and score margin.
- Whole-world bootstrap uncertainty retains both opponents together.

The earlier 2,750–3,000-score recording panel initially qualified V9. R3's new runs on those same recordings are reported separately below.

### Two fresh cases that change the interpretation

**Incremental repair benefit — `fresh-11-original_m1`, seed 3685372307.** At day 18, route 422 needed a sheep at `(7,4)`, born on day 8, and a strawberry at `(8,2)`, planted on day 6, preserved until day 21. R3 scheduled two service tasks and one watering attempt. Native and V9 both tied; R3 won by 1,016. Own cash changed −1,260 and rival cash −2,276. Our sales included 73 more carrots and 17 more strawberries, but 93 fewer wheat units. Rival sold quantities were unchanged: its lost receipts were mainly strawberry (−2,448) and carrot (−860), partly offset elsewhere. The 16-future mean margin forecast was +1,543 and the worst delivery stress +149. Actual own-cash change was worse than the +111 forecast, despite the favorable score margin.

**Shared selector regression — `fresh-12-v56`, seed 1895503985.** Both V9 and R3 selected ordinary route 47 on day 12. A native win of 1,692 became a loss of 838, a margin regression of 2,530. This was not a newly repaired transition. Our cash rose 1,768, but V56's rose 4,298. We sold 44 fewer wool units; its wool revenue rose 6,674, partially offset by losses on other products. The original eight-future mean margin forecast was +4,842, with minimum +1,140. This fresh failure shows that optimistic rival-price effects also affect ordinary V9 switches, outside R3's extra repair-only stress gate.

The reconciled product, purchase, wage, and cash differences are saved in `fresh_case_economics.json`. Neither case was used to change the frozen qualification policy.

### Completed fresh results

All **144 games / 48 matched comparisons / 24 independent worlds** completed and passed the audit.

| Opponent | Comparisons | R3 vs original m1: better / same / worse | Mean margin gain | Original wins → R3 wins | R3 incremental gain over V9 |
|---|---:|---:|---:|---:|---:|
| Live V56 | 24 | 3 / 20 / 1 | +294.6 | 17 → 17 | 0 |
| Live original m1 | 24 | 4 / 20 / 0 | +768.3 | 2 → 5 | +42.3 |
| Both | 48 | 7 / 40 / 1 | +531.4 | 19 → 22 | +21.2 |

Versus V9, R3 was **one better, 47 identical in final margin, zero worse**. The extra win came from a tied baseline, so it recovered no additional deficit in already losing games. The complete R3 package reduced original m1's summed loss deficit by only **1.25%** on this sample. The large individual development recovery has therefore not generalized into broad loss recovery.

Whole-world percentile bootstrap intervals for mean margin improvement were **[+22.8, +1,165.6] versus original m1** and **[0, +63.5] versus V9**. The latter is driven by one intervention in one world; it does not establish a reliable general upgrade. These are descriptive paired estimates, not Elo estimates. Across both opponents, mean own cash changed +263.1 versus original m1 but −26.3 versus V9.

Coverage across R3's 144 fresh decisions:

- 823 ordinary alternatives; 298 failed cohort preservation.
- 200 bounded repair alternatives attempted; 194 survived the initial cohort check.
- Final repair outcomes: 185 nonpositive risk-adjusted forecasts, seven cohort/hire failures, six final-gate failures, two admitted by the initial eight-future gate.
- Ten repairs reached eight complete futures. Only one won selection and entered the additional validation stage; it passed and was executed.
- Eight total selected commitments, including seven ordinary V9 commitments and that one repair. No decision timeouts.

Fresh local timing, including the current action with the search:

| Metric | V9 | R3 |
|---|---:|---:|
| Mean reveal decision | 2.81 s | 3.40 s |
| Median reveal decision | 1.56 s | 2.33 s |
| 95th percentile reveal decision | 6.39 s | 6.97 s |
| Maximum reveal decision | 7.23 s | 7.89 s |
| Minimum measured overage bank remaining | 50.91 s | 48.45 s |
| Mean full-game wall time | 13.22 s | 14.99 s |

R3 is approximately 21% slower per reveal in this panel. Its extra cost is bounded locally, but the small incremental benefit does not yet justify replacing V9 generally.

### Post-evaluation ordinary-switch diagnosis

`scripts/probe_ordinary_tape_timing_risk.py` reconstructs the exact native prefix for `fresh-12-v56`, then applies the same 16-future/16-stress validation to ordinary route 47, using only the day-12 observation and own memory. It **still approves the losing switch**: forecast mean +5,023, ordinary minimum −265, worst delivery stress +301. The policy was not changed. This is evidence against the simple proposed fix of applying the repair-only timing guard to every switch. Results and the diagnostic-function hash are in `ordinary_timing_diagnostic.json`.

## Completed recording extension

R3 ran 42 additional complete games with the same frozen policy and harness: 32 fetched rated-opponent recordings and 10 original-m1 recordings. The earlier source reconstructions and baseline/V9 controls were reused after checking 168 reference-file hashes. This is a rerun on previously inspected episodes, not an independent holdout.

| Recording group | Cases | R3 vs original: better / same / worse | Mean margin gain vs original | Additional gain vs V9 |
|---|---:|---:|---:|---:|
| Exact original-m1 controls | 10 | 2 / 8 / 0 | +664.6 | 0 |
| Rated opponents without material command failure | 21 | 2 / 19 / 0 | +503.8 | 0 |
| All rated recordings, diagnostic only | 32 | 7 / 25 / 0 | +1,507.3 | +77.3 |

Eleven rated recordings fail the existing screen of more than 40 additional ineffective/missing/malformed opponent commands in at least one comparison arm. They remain in the raw results but are excluded from competitive claims. Passing this screen is still weaker than running a responsive live opponent.

The sole additional replay gain is **+2,473 against TheEggman in episode 112562107**, from a day-18 route-79 repair preserving a strawberry. Own cash rose 1,432 and rival cash fell 1,041. However, its baseline, V9, and R3 arms all have material recorded-command failure, so this does **not** count as evidence of stronger play against TheEggman's live policy.

All ten original-m1 controls still reconstruct exactly. EvilMango's previously established recovery remains +6,421; Snorlax's −25,467 loss remains unchanged. Across the 42 R3 replays, there were zero timeouts; the lowest measured overage balance was 45.30 seconds.

## Decision

Keep this as a research adapter, with V9 and the submitted m1 unchanged. The repair layer demonstrably makes selected transitions feasible and has one new positive live result, but its fresh incremental mean is small and it adds simulation cost. It has not broadened recovery of large losing cases. The stronger next work is economically informed candidate generation and better rival production/market forecasts, reusing the existing semantic and public-flow components. The discovered ordinary-switch regression is a required future regression case; its observed future must not become an input to the playing policy.

## Functional verification

`scripts/check_tape_repair_r3.py` passed:

- An immediate deadline abort followed by a successful full decision in the same process.
- Engine-hook restoration and unchanged input observation/memory.
- Correct known repair selection and all required validation scenarios.
- Balanced public futures with the revealed prefix preserved.
- Sale-delay conservation, purchase timing, and no mutation of the input world.
- Cohort birth identity and repair expiration.

`scripts/audit_tape_repair_panel.py` checks frozen file hashes, three-arm pre-intervention equality, full action hashes, complete game lengths, cash ledgers, unchanged native actions when there is no intervention, selected-candidate admission, complete repair validation, runtime-bank arithmetic, and native error telemetry.

Local timing is measured synchronously and includes initialization. It is not a competition-container timing certificate.

The fresh panel started serially. A second memory-gated worker later handled worlds 18–23 while the original worker continued through the earlier worlds. After those six worlds finished, the second slot was used for the recording extension. At most two game workers ran concurrently. Results use measured shared-laptop wall time; this concurrency is part of the timing context.

## Components to reuse for the next iteration

The current repair shortlist inherits V9's shop-distance and tile-Hamming retrieval. Making those few plans feasible often leaves their economics unattractive. Broader semantic retrieval should rank the dated investment, service, harvest, delivery, and terminal-cohort plan before spending exact simulation time. The project already has `tape_semantic_features.py` and verified three-day segment extraction; their requested jobs must still be distinguished from successful production.

For rival deliveries, `agents/adaptive_market_order.py::FlowModel` already infers recent rival net flow from public market changes minus our own realized flow, with price-floor and midnight-overflow ambiguity flags. The earlier `docs/adaptive_market_order.md` records zero mismatches among observations marked usable in its own corpus. This component is not integrated into R3 yet. A useful next comparison is donor-only forecasts versus donors reweighted by recent observed sale timing and quantities, with ambiguity retained rather than imputed as zero.

For speed, retain the existing exact runtime reuse and early physical vetoes. Profile any new retrieval or history feature separately from full-season simulation, and report whether saved simulation work changes selected actions. A faster forecast with worse repair decisions is not an improvement.
