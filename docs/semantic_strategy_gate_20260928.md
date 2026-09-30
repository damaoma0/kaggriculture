# Causal semantic strategy: local benchmark protocol

This is a full-season test of a semantic policy, the spatial tile planner, and KB115LT together. The candidate starts at step 0 and receives only the current official observation and configuration. It receives no target episode ID, recorded opening, future shop sequence, or future semantic tile counts. Static training data and opening policy are part of the frozen candidate dependency closure.

The outcome-blind panel is saved in `results/fresh/semantic_strategy_20260928/protocol.json`. It contains 8 development and 40 qualification live worlds, plus separate 8 development and 40 qualification historical worlds. Live qualification uses 40 distinct random seeds and 20 games in each seat. A preordered list of 135 unused recorded reserves is also frozen. The final numerical success threshold must be recorded before qualification is released. No strength or competition-readiness result follows from preparing this protocol.

## Opponents and inputs

The live opponent is the exact 185-file package at `submissions/2026-09-24-mgt_v9lite/pkg/`, copied to the study and checked against its source manifest. This is the bank-aware packaged V9lite, with warm-up thread disabled. The editable research agent is not used. Shops and weeds follow the natural engine RNG in live games.

Historical worlds come from `data/ladder_panel/p2750/`, whose dated source index identifies opponents rated 2750–3000 when selected. Each retains its original seed, seat, recorded shop sequence, and opponent action stream. No artificial starting-cash cushion or fresh-seed relabeling is used. The source corpus rating is historical provenance, not a current rating assertion. Source recordings and their hashes are frozen in the study.

Selection does not use recorded rewards. Qualification and reserve episode IDs are excluded from training; episode aliases and both seats of a shared source must be excluded together. The final candidate manifest records its training IDs. The extractor independently checked the 144 rich DSM training seats and 112 opening sources against all 183 recorded panel/reserve episodes: no overlap. Candidate-specific training IDs are checked again at freeze and at source-control selection.

## Validity and evidence

Every recorded world first gets an original-source control that replays both original action streams. It must finish 720 states with both agents `DONE`, reconcile both cash ledgers from starting cash plus revenue minus spending, and reproduce both original cash totals exactly. A source control that fails may be replaced by the next unused, training-disjoint reserve before candidate execution. Every attempt and control hash is logged. A candidate-induced rival failure never triggers replacement.

The candidate game must finish the same 720-state checks and produce 719 actions for each seat. Both full cumulative daily ledgers, action hashes and action streams, actual engine time banks/statuses, per-call timings, optional daily strategy diagnostics, and cash at days 0/6/11/12/18/24/30 are saved. Source modules imported from the editable repository make the game invalid. Frozen source and harness hashes are checked before dispatch and inside every worker.

The recorded-rival screen compares failed physical commands with its exact source control. More than 40 additional failed commands makes the candidate game ineligible. Missing-worker-command differences and failures by day are also retained. This screen is necessary rather than sufficient: a recorded action stream cannot respond to counterfactual prices. Historical results therefore remain distinct from responsive live-opponent results. Every timeout, source/ledger failure, or ineligible recorded rival makes the planned gate incomplete; no invalid win is counted, and its slot is not dropped from the denominator.

The harness uses engine 1.32.7, the normal 1-second action allowance and 60-second overage bank. Initialization time is reported separately. Diagnostics are captured inside the measured wrapper; no timeout bypass is enabled. The engine's completion and remaining-bank checks take precedence over the separately measured wall times; measured cumulative overage above 60 seconds also makes a case invalid. The current official farm (including own private state), market, and town are captured every morning alongside diagnostics.

The immutable `smoke_v1` snapshot omitted the separate `obs.private` field from its diagnostic copies. It retained public own-farm tiles/hands/cash, market/town, and plans; gameplay received the full official observation. The editable harness now records `private` explicitly for future snapshots. `scripts/audit_semantic_strategy_gate_20260928.py` independently checks saved source hashes, training/opening exclusions, action hashes, every daily cash equation, runtime totals, and report counts without importing the runner or executing games.

The editable harness also records compact packaged-V9lite health counters from `_V9_REPORT` and makes internal search-error/fallback cases ineligible. Earlier `smoke_v1`, both V2 candidates, `strategy_v3_modern4`, and the fixed `nearest_shops_v2` harness were frozen before this addition. Their engine/runtime checks remain available, but an unrecorded internal opponent error counter must not be described as zero.

## Running a frozen candidate

Use the repository virtual environment. `--files` must enumerate every local source/model dependency, including the executor and fixed recipe. Paths are copied with their repository-relative structure. The standard Kaggle loader does not provide `__file__` to the entry source; candidate root discovery must work with the official loader. The worker's working directory is its immutable project snapshot and its `scripts/` directory is on the import path.

```powershell
.venv/Scripts/python.exe scripts/semantic_strategy_gate_20260928.py freeze --id v1 --entry agents/semantic_strategy_20260928.py --files "scripts/dependency.py,data/model.json" --training-episodes data/training_episode_ids.json
.venv/Scripts/python.exe scripts/semantic_strategy_gate_20260928.py run --candidate v1 --split development --mode live --workers 2 --external-workers 0
.venv/Scripts/python.exe scripts/semantic_strategy_gate_20260928.py run --candidate v1 --split development --mode recorded --workers 2 --external-workers 0
```

The dependency names in this example are placeholders: use the candidate's actual closure. `run` re-enters the copied harness before starting its worker pool, so later edits to the development scripts cannot alter an in-flight run. Workers are capped by free memory and the shared four-game-worker limit; `--external-workers` reserves slots occupied by other runs. The current launcher reserves 1.8 GiB per worker plus 1.5 GiB headroom after the initial smoke reached 1.85 GiB per process. Its earlier immutable `smoke_v1` harness used 1.1 GiB per worker; use one worker for reruns of that frozen harness when free RAM is around 4 GiB. Existing successful and failed outputs are both preserved on resume.

Only after selecting and freezing the final candidate, setting the acceptance threshold, and receiving root coordination for qualification:

```powershell
.venv/Scripts/python.exe scripts/semantic_strategy_gate_20260928.py release --candidate v1
.venv/Scripts/python.exe scripts/semantic_strategy_gate_20260928.py run --candidate v1 --split qualification --mode live --workers 2
.venv/Scripts/python.exe scripts/semantic_strategy_gate_20260928.py run --candidate v1 --split qualification --mode recorded --workers 2
```

Release permanently identifies one candidate manifest for this qualification panel. `report` takes the same candidate/split/mode arguments and regenerates counts without executing games. Results are under `runs/<candidate>/<split>/<mode>/`; source-control decisions are under `selections/`, and concise reports under `reports/`.

## Separate fixed-shop development comparisons

`scripts/semantic_strategy_fixed_20260928.py` freezes the full per-day shop histories from a valid candidate's **eight natural development cases**. Only the harness receives these schedules; both candidate and responsive V9lite still receive current official observations. It refuses qualification worlds and binds natural result/action hashes, candidate manifests, copied harness files, and the shop arrays in a separate experiment manifest.

```powershell
.venv/Scripts/python.exe scripts/semantic_strategy_fixed_20260928.py prepare --id nearest_shops_v2 --reference strategy_v2_nearest --candidates strategy_v2_nearest,strategy_v2_unlock
.venv/Scripts/python.exe scripts/semantic_strategy_fixed_20260928.py run --id nearest_shops_v2 --candidate strategy_v2_unlock --workers 1
```

The prepared example already exists; choose a new ID for a new experiment. `run` first executes all eight forced-reference controls, then the other candidate in worlds with valid controls. Every pair uses the newly executed forced reference. Exact cash and both action-stream reproduction of its natural run are reported separately: timed searches may vary, so divergence alone does not invalidate a valid fixed-shop control. Exact reproduction would be required to reuse a natural outcome, which this runner does not do. Engine, both ledgers, source/input/shop hashes, and runtime checks remain mandatory. Invalid controls leave the planned denominator incomplete and are never replaced.

Results and reproduction diagnostics are under `fixed_experiments/<id>/`. These comparisons must be reported separately from natural-world policy performance. The earlier `nearest_shops_v1` is an unused preparation with a stricter reproduction requirement; no games ran under it. After-game strategy diagnostics are captured by this new harness, including final-day executor error counters.

## Frozen development results and later diagnostics

The completed natural live development runs below each have eight valid games. None is qualification. Same seeds can produce different natural shops after agent behavior changes, so differences across rows are whole-policy results rather than isolated mechanism effects.

| Frozen candidate | Wins / 8 | Mean margin |
|---|---:|---:|
| smoke_v1 | 1 | -6,592.75 |
| strategy_v2_nearest | 1 | -7,144.875 |
| strategy_v2_unlock | 2 | -5,201.625 |
| strategy_v3_modern4 | 1 | -9,671.75 |
| strategy_v4_modern4_finance | 1 | -6,623.0 |
| strategy_v5_blocks100_finance | 4 | +242.375 |
| strategy_v6_blocks100_recovery | 4 | +1,629.625 |
| strategy_v7_blocks100_readiness | 3 | -834.25 |
| strategy_v8_kb115lt2_readiness | 5 | +994.5 |

The separate `nearest_shops_v2` responsive fixed-shop comparison has eight valid newly executed references and eight valid unlock candidates. The mean paired margin change is +3,063.625, with six improvements and two regressions; both arms win1/8. Six forced reference controls reproduce natural actions/cash exactly. The other two remain valid paired references, with their natural divergences retained explicitly. These development results do not establish general policy strength.

The frozen V5 block policy changes both the policy and its training set, to100 modern training seats. Its runtime model contains fitted coefficients and anonymous examples instead of episode-tagged rows. The candidate manifest therefore explicitly binds the selected model hash, its training manifest hash, and its source dataset hash. The independent audit verifies the selected model rather than a default model file. The conservative243 source-episode union includes opening and pace sources and remains disjoint from all183 recorded panel/reserve IDs.

V6 uses the same V5 model, policy and tile modules, adding observed-stock-shortfall recovery and a retirement guard to the wrapper. `strategy_v6_vs_v5_freeze.json` records the exact two changed files: wrapper and configuration. Every other source and harness hash matches. Both V5 and V6 include120 own-only hourly inventory/worker snapshots over days6–10; the earlier V4 retains dawn snapshots only.

V7 is built by copying the exact frozen V5 project and harness, then overlaying only the tile adapter and anonymous-lifetime compiler. It preserves observed readiness identity among same-age initial crops. Wrapper, configuration, model, financing and every harness file remain identical to V5; V6 recovery is absent. `strategy_v7_vs_v5_freeze.json` records the two-file change. The extractor independently verified all192 saved V5 planning dawns: the fix has zero readiness mismatches and preserves every realized daily semantic count. Its completed live development panel passes the independent artifact audit, with zero V9 internal errors and maximum measured cumulative overage14.607 seconds. Relative to V5, mean paired margin is -1,076.625 (bootstrap95% -3,735.75 to +1,268), with four improvements and four regressions. Natural shops differ in all eight pairs; this is not an isolated same-shop effect.

The user subsequently selected KB115LT2 as the new baseline. `strategy_v8_kb115lt2_readiness` copies exact frozen V7, replacing only the executor source and its seven specified recipe settings: collect-at-floor, 3,000-iteration final hand-plan polish with exchange0.2/water-cost20, learned2 dawn trips, and deferred animal-harvest fraction0.3. The executor keeps the old runtime filename solely for compatibility with the unchanged wrapper; manifest provenance binds the actual `agents/mgt_lead_kb115lt2.py` bytes. The pooled causal pace table and day6–29 dispatch window remain unchanged. No V6 stock recovery or hand-bonus additions enter this comparison. `strategy_v8_vs_v7_freeze.json` records every difference. Its first full development game completed under normal engine budgets: cash95,342 against84,179, 17.746 seconds candidate overage, zero executor/V9 errors and zero planner warnings. The independent ledger/source/runtime audit passes. `reports/v8_full_game_smoke.json` binds the result and separate single-case driver hashes. That smoke result was retained as the first slot of the completed development panel; it is not a separate independent sample or qualification evidence.

V8 subsequently completed all eight live development games with five wins and mean margin+994.5. The independent source/engine/action/ledger/runtime audit and separate technical score report pass for all eight. Maximum measured overage is21.650 seconds, with zero cumulative executor errors and zero live-V9 internal errors. Its eight recorded development games also pass all technical checks, with four actual scripted wins and mean margin-495.5; maximum overage is20.492 seconds. The original strict screen retains five eligible games and three wins in the planned eight: cases112476470/112610631/112612822 exceed its command-failure threshold. Both scores are preserved under `docs/semantic_strategy_shipping_addendum_20260928.md`; no slots are replaced. Qualification remains untouched.

`strategy_v9_kb115lt2_reveal` is prepared from exact V8 for the next authorized development comparison. It changes the selected policy class, adds the reveal-feature model/subclass and training manifest, and logs compact own-public policy memory before each daily proposal. The entry is a minimal patch of frozen V8; it does not import the later stock-recovery, hand-bonus or market-admission changes. Base block/policy, tile modules and the full KB115LT2 recipe remain byte-identical. The new model changes fitted sheep/strawberry columns; shared constraints and later farm states can still change other realized decisions. On192 saved development dawns, disabling reveal features reproduces every full proposal, and enabled outputs match when using the exact frozen V8 base instead of the editable base. The harness update changes only freeze/provenance and qualification-release binding functions; its gameplay functions are AST-identical. These checks establish compatibility, not gameplay strength.

The D6 exact-layout/retile component diagnostic is a separate oracle experiment described in `docs/semantic_strategy_oracle_d6_20260928.md`. It receives future source tile-change intent and original action prefixes and must never be pooled with these causal strategy results. Its original missing-lock input defect was caught before any affected retile game; valid original source/exact controls are retained by hash.

V5 recorded development is complete but fails the integrity gate: all eight games finish with valid engine states, cash ledgers and runtime, while three exceed the frozen rival-failure limit. Cases112476470/112610631/112612822 have120/47/63 additional failed commands;112610631 includes22 missing-worker commands. Its apparent +2,652 win is ineligible. The denominator remains eight, with three eligible wins; raw all-eight mean margin is -617.875. No case is replaced, and the +177.2 mean among five valid games is not a complete-panel score.

For112612822, unchanged-action prefix replays prove the immediate economic cause: the native rival has859 before its day9 hour18 two-cow purchase, buys both at400, and ends at59. Against V5 it has720, buys one, then the second is refused at320. Both have11 shed units before the purchase, so capacity is not the cause. Both farms, markets, towns and cash ledgers reproduce at all ten preceding dawns. The missing cow causes the later recorded care/collection failures; this distinction does not change the frozen ineligible disposition. Detailed failure types/phases are in `reports/v5_recorded_integrity_breakdown.json`, and the exact purchase evidence in `diagnostics/cow_purchase_112612822.json`.
