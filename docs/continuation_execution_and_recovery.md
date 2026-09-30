# Continuation execution and recovery — 22 September 2026

**Keep mgt_m1. The execution components improved, but none of the three new policies improved competitive performance.** The current experimental build is `agents/mgt_continuation_dev.py`; it must not be treated as a replacement for m1.

## Implemented behavior

- A portable tile-job compiler packs work and delivery together, using cached route costs and bounded search. It generates worker routes from our actual positions and inventories.
- A complete three-day projection checks funding, purchases, planting, collection, delivery, shed overflow, and subsequent days before admitting a continuation. A later-day rejection leaves the live state untouched.
- The projector uses the checked-in engine's physical and market functions. Its scenario holds current shops, omits new weeds, and assumes no rival trades. It reads only public observations and our private inventory. It is a conditional feasibility check, not a guarantee about the future market.
- A calendar adapter transfers one donor's planting and animal-establishment dates/counts and fertilizer budgets. It services our actual cohorts and reports investment requests that cannot fit. Existing animals are not destroyed to match donor coordinates. The adapter is a new heuristic representation, **not a fitted general UMG policy**.
- After activation, the controller owns subsequent execution. It checks actual positions, inventories, tiles, input fills, and action preconditions. A discrepancy discards stale commands. It never resumes the old m1 action tape after changing the farm.
- The revised controller checks that a proposed window leaves an executable next day of maintenance. If a later donor proposal fails, it compiles maintenance from the current farm. An emergency controller is the final, best-effort fallback.
- Planning has a wall-clock budget, and expensive proposals abstain. This makes activation dependent on available execution time; it is not a deterministic policy solely of the observation.

## Native execution results

The same 12 previously exposed native donor fixtures are used: two each at days 12, 15, 18, 21, 24 and 27. The official interpreter reconstructs each source state. The rival passes and historical shops are conditioned by the diagnostic harness. No donor movements are given to the compiler.

| Compiler | Complete windows | Exact output | Exact ending tiles | Largest measured action |
|---|---:|---:|---:|---:|
| Previous v3 | 4/12 | 4/4 accepted | 4/4 accepted | See original segment report |
| Initial new, more search | 10/12 | 10/10 accepted | 10/10 accepted | 3.977 s |
| Final bounded compiler | 8/12 | 8/8 accepted | 8/8 accepted | 0.290 s |

The final compiler rejects four windows. This is improved execution coverage, not universal routing feasibility or evidence of higher profit. Ending tile equality does not imply equal cash, deliveries, worker positions or sale timing.

Artifacts: `results/fresh/continuation_executor/native_v1.json`, `native_v2.json`, and `native_final.json`. Each records source hashes and all worker-count attempts. The final gate has no errors and no measured actions above one second.

## Runtime integration and stress checks

`scripts/test_continuation_runtime.py` passes **10 tests**, including:

- A complete projected three-day fixture agrees with the independent official interpreter on every own-farm, own-private-state and market checkpoint, with weeds disabled in both for this deterministic diagnostic.
- A failure on the second day rejects the entire proposed window.
- A rejected, unfunded proposal leaves the live observation unchanged and does not activate the controller.
- Missing feed, displaced workers and missing seeds cannot advance stale production commands.
- An injected feed-stock removal triggers recovery and preserves the entire initial herd through three days in the official engine.
- Expired planning budgets abort search.

The fault-injection test initially assigned dictionary fields on Kaggle `Struct` objects without synchronizing their attribute fields. That invalid test fixture produced a spurious inventory-index exception. The fixture was corrected to use attribute assignment; the failure log is retained. This was not observed as an agent failure in the benchmark.

These fixtures are targeted tests, not proof that recovery always prevents loss from every reachable state. Raw log: `results/fresh/continuation_executor_runtime_tests_final.log`.

## Full-game development comparisons

Eight fresh development seeds, both seats, live V56, natural shops and weeds. All eight seeds were frozen before outcomes. Sixteen separate confirmation seeds were also reserved and remain unused. The existing qualification panel was not touched.

Three sequential experimental versions were evaluated on these development seeds. The first two panels each execute 16 candidate and 16 control games; the third executes 16 candidate games and reuses the 16 hash-verified control rows from the second. That is **80 full-game executions on eight development seeds**, not 80 independent worlds. Reused rows have explicit provenance.

| Policy | W / T / L vs V56 | Mean margin | Change vs m1 | Worst margin | Calls >1 s |
|---|---:|---:|---:|---:|---:|
| Unchanged m1 control | 10 / 0 / 6 | +2,943 | — | −10,095 | 0 |
| v1: three-day admission, emergency successor | 0 / 0 / 16 | −39,721 | −42,664 | −58,076 | 2 |
| v2: terminal upkeep check and daily maintenance | 8 / 0 / 8 | −4,216 | −7,159 | −31,494 | 0 |
| v3: add bounded productive fallback | 4 / 0 / 12 | −11,883 | −14,826 | −35,837 | 0 |

All completed games have 719 actions, 720 states, DONE statuses, and reconciled cash ledgers for both seats. The runner measures action durations but does not enforce online deadlines. Largest candidate calls were 1.236 s, 0.620 s, and 0.868 s respectively. These results are offline cash outcomes; they do not certify a submission under Kaggle time limits.

The paired mean-margin 95% seed-bootstrap interval is **−16,727 to 0** for v2 and **−26,239 to −4,196** for v3. Neither improves a single development seed. Exact shop paths match the control in 12/16 v2 games and 8/16 v3 games. Policy changes alter weed RNG consumption and can change later shops, so these are natural-world policy comparisons rather than fixed-shop causal decompositions.

The first version activates in 14 games and spends 3,160 turns in emergency behavior. Version 2 activates in four games, uses 48 planned maintenance days, and has zero emergency turns or detected execution discrepancies. Version 3 activates in eight games, schedules 98 maintenance days, and records two action-precondition recoveries with 12 emergency turns. Planned maintenance days are not a count of completed unique days: later proposals or recovery can supersede scheduled actions.

Version 3's productive fallback considers up to eight, then four, new short crops per day, charges seed costs, values its additional batch on the engine's current glut curve, and can renew fertilizer on productive existing crops. It falls back to existing-asset maintenance if the whole-farm work does not fit. Its extra activation and negative result reject this heuristic; they do not establish that sustaining crop replacement is intrinsically harmful.

## What the negative result identifies

The first prototype demonstrated a transition failure: a feasible three-day investment was followed by an infeasible new donor window and lengthy emergency behavior. Checking a next-day maintenance successor substantially improved that prototype's outcomes, but did not make it competitive.

In v2 the remaining losses occur despite completed maintenance, not detected command failures. Its two affected development seeds spend 12 days without normal replacement planting:

- Seed 1577629862, seat 0: own cash −20,448; rival cash +3,369; margin −23,817. Our production changes by −233 carrots, −219 wheat, −56 strawberries and −25 tomatoes. Additional spending is 2,026.
- Seed 572795381, seat 0: own cash −15,949; rival cash +17,490; margin −33,439. Our production changes by −422 wheat, −76 strawberries and −25 tomatoes. Additional spending is 6,024.

These are accounting comparisons with different realized market paths, not isolated treatment effects. Details are in `development_v2/active_case_audit.json`.

**A continuation needs economic continuity as well as executable care.** Keeping existing animals and crops alive while ceasing replacement cohorts can still produce a severe loss. A one-day maintenance successor is therefore an insufficient admission criterion for a competitive policy.

The next policy milestone is a remaining-season production/value comparison that preserves profitable replacement cycles and accounts for cohort timing, labor, conversion costs and shared-market response. The current nearest donor, full-care heuristic and short-crop valuation do not meet that standard. Tuning donor similarity or merely accepting more windows is not supported by these results.

## Code and reproduction

- `scripts/fragments/continuation_executor.py`: route compiler and bounded search.
- `scripts/fragments/continuation_projection.py`: physical projection, same-turn availability and complete-window checks.
- `scripts/fragments/continuation_calendar.py`: cohort-aware calendar adaptation and experimental productive fallback.
- `scripts/fragments/continuation_control.py`: admission, observation verification, maintenance and emergency recovery.
- `scripts/build_continuation_agent.py`: standalone assembly and actual Kaggle last-callable check.
- `scripts/validate_continuation_executor.py`: versioned native execution gate.
- `scripts/test_continuation_runtime.py`: integration and fault-injection tests.
- `scripts/report_continuation_experiment.py`: complete-panel, source-hash, ledger, paired and lower-tail reporting.
- `results/fresh/continuation_executor/development_v{1,2,3}/`: frozen sources, manifests, per-game data and summaries.

The project venv launcher could not start its configured interpreter in this session. Runs used the bundled Python 3.12 executable with the existing `.venv/Lib/site-packages` and `scripts` on `PYTHONPATH`; Kaggle environments remained version 1.32.7. No environment files were changed.

Example from the project directory in PowerShell:

```powershell
$env:PYTHONPATH = "$PWD/.venv/Lib/site-packages;$PWD/scripts"
& 'C:/Users/xyygl/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' scripts/test_continuation_runtime.py
```

Use a new output directory when evaluating a changed build. Frozen benchmark artifacts preserve the exact previous sources even if the experimental builder is run again.

No competition submission was made. m1 remains selected; confirmation and qualification did not run because all candidate policies failed development.
