# Semantic farm implementation — 24 September 2026

The proposed architecture is implemented as a separate research agent. It makes
daily production decisions, allocates tiles, generates maintenance, funds inputs,
and compiles worker routes from the actual state using the existing continuation
scheduler. There is no runtime donor action tape. The current version is a working
research implementation, not a replacement for mgt_v9lite: competitive validation
has shown a substantial regression.

## Modules and contracts

| Module | Implemented behavior | Validation |
|---|---|---|
| `build_semantic_strategy_study.py`, `extract_semantic_leader_families.py` | Exact-submission rating filter, benchmark exclusion, successful semantic job extraction, shop-prefix features, source hashes | Full-engine replay checks; additional 15 leader seats verified through 7,190 transitions |
| `train_semantic_farm.py`, `semantic_farm/model.py` | Daily joint quantity vectors from eligible leaders, shop/state/age matching, bounded economic alternatives | Whole-episode leave-out diagnostic; shop response and maturity tests |
| `semantic_farm/care.py` | Full useful care; explicit engine-derived omissions, input-cost comparisons, opening funding tradeoff | Counterfactual care tests and successful-job checks |
| `semantic_farm/layout.py` | High-service cohorts nearest the center; opening wheat includes its later strawberry use; existing productive assets stay fixed | Placement and live-asset protection tests |
| `semantic_farm/economics.py` | Visible-shop demand, uncertain future-shop prior, rival supply scenarios, marginal nonlinear receipts, input and wage reserves | Demand, late investment and cash-reserve tests |
| `semantic_farm/execution.py` | Collect/sell before financing, real cash, land acquisition, complete tile chains, existing route packing, physical checkpoints, final-day delivery | Independent interpreter parity for funding, replacement chains, land and terminal sales |
| `semantic_farm/policy.py` | Feasible incumbent first, quantity backoffs, full remaining-season service admission, daily replanning and state repair | Full 719-action integrations, displacement and overloaded-farm tests |
| Packaging and evaluation scripts | Dependency archive, source manifests, independent evaluation engine, paired live/recorded controls, cash ledger reconciliation | Isolated archive execution with the Kaggle callable loader |

Entry point: [`agents/semantic_farm.py`](../agents/semantic_farm.py).
Implementation directory: [`scripts/semantic_farm`](../scripts/semantic_farm).
The packaged entry point is the tested deployment artifact.

The default opening is the coherent DSM early-strawberry family from episode
112802103. It establishes two cows, three sheep, ten melons and ten strawberries.
The semantic scheduler sometimes delays three day-3 strawberries to day 4 because
the complete original six-plant investment does not have a feasible funding and
route path. This is an explicit quantity backoff, not an exact opening replay.
All five qualifying leader teams supply continuation proposals; automatic choice
among multiple pre-shop opening families is not yet fitted.

After day 5, proposals use the donor's **actual additions on that day**, bounded by
the remaining difference in farm composition. They do not purchase every missing
historical cohort. Only already revealed shops enter the policy. Future shop
scenarios are a uniform prior, never the evaluator's actual sequence.

Care defaults to every useful service. A skip must have an explicit reason:
zero output loss, fertilizer costing more than its estimated additional output,
or the initial-day animal feeding tradeoff needed to finance the opening. The
counterfactual uses the current tile state and full subsequent care. It does not
treat an expert's missed action as proof of an intentional or beneficial skip.
Recovery can omit fertilizer/care while preserving survival jobs, and is logged
separately from a full-care plan.

New investments must fit today's real routes and funding, a conservative service
envelope, and a replay of all remaining service days including final delivery.
A 40-asset guard limits growth until route/maintenance admission is better
calibrated. Failed or timed-out proposals spend no real money. This conservatism
is a likely performance constraint; passing the projection is not a proof against
all future rival trades or newly spawned weeds.

## Study provenance and model quality

The saved rating snapshot is 2026-09-24 09:16:42 UTC. The corpus contains **50
player-seasons from 45 distinct episodes**, 1,500 daily decisions, and 143,519
maintenance opportunities. It covers six submissions from five teams, rated
3000.6–3128.8 in that snapshot. Every episode in the 185-game target panel is
excluded from the study. Older traces without verified qualifying submission
ratings are excluded too.

The joint decision library is deliberately small and interpretable. It has not
demonstrated predictive superiority: leave-whole-episode-out quantity MAE is
**0.6907**, compared with **0.6528** for a same-day species median. Those metrics
measure imitation only, and abundant zero additions make this an imperfect
strategy metric. Unequal family sample sizes also remain a limitation.
The stronger family holdout also excludes every shared episode from training.
Nearest-neighbor quantity MAE is worse than the calendar median for each of the
five held-out families (see `family_holdout.json`). DSM contributes 37 of the 50
seasons; the other families contribute only three or four each. More examples and
better decision modeling are needed before treating this as a learned advantage.

## Validation and benchmark protocol

The two semantic test suites pass **34 tests**. A full-game package test loads the
actual archive through Kaggle's callable loader in a temporary directory under
isolated Python. Policy modules and model paths are asserted to come from that
archive. The game completes all 719 actions against live V56, with reconciled cash,
30 daily plans, and no emergency hours. This test exposed and fixed a packaging
assumption that Kaggle's loader would always define `__file__`.

The benchmark runner supplies recursive attribute-access observations, matching
Kaggle's observation contract. An initial run used plain nested dictionaries and
failed to load v9lite correctly; that run was discarded and rerun. The final
runner evaluates the checked-in engine in a separate module from the planner's
projection, and verifies both players' entire cash ledgers.

Frozen validation uses two panels, paired against m1, y3 and current mgt_v9lite:

- 16 recorded worlds from distinct teams in the existing 2750–3000 panel,
  selected by deterministic team interleave before outcomes. These are **team
  ratings**, not verified ratings of each recorded submission. The full inherited
  panel has 185 games, 61 represented teams, and observed ratings 2750–2985.6.
- Eight fresh live V56 worlds, each played from both seats. The first revealed
  shop is balanced across all eight shop types. Seeds are 924701, 924702, 924703,
  924705, 924706, 924709, 924711 and 924719. All arms in each world share the same
  shop sequence; agents only receive the prefix revealed so far.

Recorded action opponents cannot respond to changes caused by our policy. Their
scores are counterfactual diagnostics, not live Elo measurements. V56 supplies a
responsive control but is not asserted to have a current 2750–3000 rating. The
16-world screen is not exhaustive qualification on all 185 recorded games.

Runtime planning uses a cooperative two-second daily budget with a small emergency
allowance. The game permits one second per action plus an overage bank; measured
total policy time and maximum action time are reported. These local measurements
do not certify runtime on Kaggle hardware. Wall-clock search cutoffs can change
which feasible proposal is admitted under different machine load.
Long-lived control processes accumulated substantial memory. Remaining cases were
resumed in fresh processes, preserving completed results and identical source
hashes. `run_semantic_suite_isolated.py` now bounds this by starting a fresh process
for each matched world. Timings span different machine loads and should not be
read as a controlled speed comparison.

Two additional worlds (924729 and 924731, seat 0) test service-weighted versus
uniform layout, and optimized care versus full care. These change downstream
production decisions too; they are whole-policy ablations, not isolated estimates
of one module's causal effect. Uniform layout destabilizes the opening and causes
48 emergency hours in each game. These slow diagnostic runs do not establish
timeout-compliant competitive results. The default layout has no emergency hours
in these two cases.

The next strategic improvements should be validated against this frozen version:
calibrate quantity decisions and their effect on opponent receipts; estimate
incremental crew/route cost instead of applying a fixed per-service proxy; and
replace the conservative 40-asset cap with reliable staged service at larger
scale. Larger farms need richer route/procurement plans, rather than simply
removing the cap that prevented the observed care failures.
The opening supports same-visit wheat harvest followed by strawberry planting.
General same-day annual-crop rotation is not yet proposed: later new cohorts
normally use plots that were already vacant at planning time. Counting mature
plants as incumbents can therefore suppress a donor's replacement cohort. That
is another limitation of the current decision model, and a concrete next test
for improving production throughput.

## Results

All **128 paired benchmark games** completed (32 cases per arm), with both cash ledgers reconciled. The default semantic candidate had **zero failed purchases, ineffective physical jobs, and emergency hours** across its 32 benchmark games. These execution gates passed; competitive promotion failed.

| Panel | Agent | Wins / 16 | Mean cash | Mean margin |
|---|---|---:|---:|---:|
| Recorded 2750–3000 team band | semantic | 0 | 73,879 | -59,687 |
| Recorded 2750–3000 team band | m1 | 9 | 104,176 | 3,108 |
| Recorded 2750–3000 team band | y3 | 9 | 103,928 | 3,135 |
| Recorded 2750–3000 team band | v9lite | 9 | 103,979 | 3,216 |
| Live V56 | semantic | 0 | 65,115 | -77,320 |
| Live V56 | m1 | 8 | 114,435 | -165 |
| Live V56 | y3 | 9 | 114,775 | 336 |
| Live V56 | v9lite | 10 | 115,800 | 1,277 |

Scores count draws as half a win. No Elo rating is inferred.

On the recorded panel, the semantic policy earns 30,100 less cash than v9lite while its recorded opponents earn 32,802 more. The market feedback matters: valuing only our additional crop receipts does not capture the full competitive effect of changing supply.

Against v9lite's result in the same recorded worlds, the candidate's mean margin difference is **-62,903** (world-cluster bootstrap 95% interval -72,428 to -55,598). It used fallback service on 11 days; no animal-count decreases were observed. Maximum measured action time was 4.92s and maximum total policy time in a game was 51.80s.

Against v9lite's result in the same live worlds, the candidate's mean margin difference is **-78,597** (world-cluster bootstrap 95% interval -95,799 to -60,757). It used fallback service on 6 days; no animal-count decreases were observed. Maximum measured action time was 5.67s and maximum total policy time in a game was 53.14s.

The recorded-tape validity sensitivity (more than 40 changed opponent no-effect commands) leaves 14 unflagged worlds. Their mean margin difference versus v9lite is -65,447; the main table keeps all 16 worlds.

The package test and six additional ablation games also completed; they are separate from the 128-game table.

Artifacts:

- [Validation capsule](../results/fresh/semantic_architecture_20260924/validation.json)
- [Recorded-panel summary](../results/fresh/semantic_architecture_20260924/panel_verified/summary.json)
- [Live-panel summary](../results/fresh/semantic_architecture_20260924/live_verified/summary.json)
- [Care/layout ablations](../results/fresh/semantic_architecture_20260924/ablation_verified/summary.json)
- [Family holdouts](../results/fresh/semantic_architecture_20260924/family_holdout.json)
- [Verified archive](../results/fresh/semantic_architecture_20260924/package_v2/semantic_farm.tar.gz)

## Reproduction

From the repository root:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_semantic*.py
.venv\Scripts\python.exe scripts/train_semantic_farm.py
.venv\Scripts\python.exe scripts/run_semantic_farm.py --out results/fresh/semantic_new_panel --panel-limit 16 --arms semantic,m1,y3,v9lite
.venv\Scripts\python.exe scripts/run_semantic_farm.py --out results/fresh/semantic_new_live --seeds 924701,924702,924703,924705,924706,924709,924711,924719 --seats 0,1 --arms semantic,m1,y3,v9lite
.venv\Scripts\python.exe scripts/package_semantic_farm.py results/fresh/semantic_new_package
.venv\Scripts\python.exe scripts/validate_semantic_package.py results/fresh/semantic_new_package
```

Use a new output folder when sources change. Manifests reject mixed revisions.
For long suites, replace `run_semantic_farm.py` with
`run_semantic_suite_isolated.py` in the panel/live commands above.
The development failures and intermediate versions are preserved for diagnosis.
No existing playing agent was overwritten, promoted, or submitted.
