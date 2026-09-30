# D6 exact-layout and retiled component controls

Current experiment: `results/fresh/semantic_strategy_20260928/oracle_diagnostics/d6_exact_vs_retile_locked_v4/`.
Preparation executes no games. This is an oracle component diagnostic on the previous DSM40 worlds, which are now stage2 development/training data. It cannot establish causal strategy strength or competition readiness.

The eight episodes are selected by hashing a fixed namespace and episode ID, without reading outcomes: 112575429, 112588791, 112626851, 112616236, 112587591, 112593664, 112596061, and 112573049. They are disjoint from all183 reserved causal recorded cases and reserves.

Both seats replay their original actions through step143. At step144, our side switches to the frozen KB115LT executor while the recorded rival continues. Both arms use the same original seed, recorded shop schedule, source prefix, hires, land calendar, reactive land-unlock hook, and enabled early financing from frozen `strategy_v4_modern4_finance`.

- `exact`: original allowed TilePlanView layout, retirement markers and daily hires.
- `retile`: strict tile-change counts compiled with anonymous lifetimes, `reuse` placement and zero polish rounds. Future source coordinates and ongoing first-harvest counts are absent from this compiler input.

The old exact interface was exported for a day11 handoff and contained cumulative sales through day10. Both diagnostic arms now contain only observed day0–5 cumulative sales. Versions1 and2 were prepared but never executed. Version3 produced eight valid source and exact-layout controls, retained at their original paths. Its retile input omitted75 observed locked cells, allowing33–45 placements before land purchase per selected world; none of those defective retile plans was executed. This was a real input defect, not a cosmetic board-label difference.

The corrected locked_v4 fixture preserves all75 locked flags in each initial semantic state, matches the complete observed day6 board, and rejects every plant/build/animal placement before its quadrant's purchase day. The public builder also rejects omitted observed locks. It reuses the valid source/exact controls through explicit hashes for all32 result/action artifacts, after verifying identical exact plans, executor files, gameplay harness, options and recordings. Original artifacts are not rewritten. The completed day11 tile-planner gate is unaffected because all four quadrants were already open at that handoff.

The runner first executes all eight original two-sided recordings and requires exact final cash reproduction. Candidate controls must reproduce both step0–143 action streams and the hash of both complete visible observations at step144, excluding only the wall-time-dependent remaining-overage value. A changed private inventory therefore invalidates the handoff. Each result also requires all720 engine states,719 actions per side, DONE/DONE statuses, every daily cash ledger, the official runtime limits, and the recorded-rival command-integrity screen. Failed cases remain in the planned denominator and are never silently replaced or rerun.

The frozen runtime is separate from the editable repository. Manifests bind the recording transformations, plans, compiler sources, executor recipe, hooks, harness, and original source hashes. Per-call own private inventories and worker positions are captured for day6–10. The exact-versus-retile contrast separates early placement costs from the shared lower executor's limitations; both sides still receive future oracle intent.

Preparation checks passed: all eight strict compiles have zero warnings; both arms share hires, observed prefix sales and land calendars; frozen hooks match the v4 implementation; the frozen oracle entry initializes with `sd_days=[6,29]` and zero interface leaks. Four contract tests pass without executing a game.

After explicit experiment authorization, run serially with:

```powershell
.venv/Scripts/python.exe scripts/semantic_strategy_oracle_gate_20260928.py report --id d6_exact_vs_retile_locked_v4 --arm exact
.venv/Scripts/python.exe scripts/semantic_strategy_oracle_gate_20260928.py run --id d6_exact_vs_retile_locked_v4 --arm retile
```

The exact command reports the reused controls. The retile command re-enters the frozen corrected harness; neither accesses qualification results. An independent audit is available through `scripts/audit_semantic_strategy_gate_20260928.py --oracle-experiment d6_exact_vs_retile_locked_v4`.

Completed results: all eight original-source controls reproduce both recorded cash totals, and all16 exact/retile candidate games pass the independent audit, including identical original prefixes and complete day6 private/public observations. Exact layout wins4/8 with mean margin -3,238.625; corrected retile wins3/8 with mean margin -3,616.5. The paired retile change is -377.875 margin, +102.875 own cash and +480.75 rival cash, with three improvements and five regressions. This small development sample does not establish noninferiority.

Compared with the original DSM source, exact-layout KB loses20,977.25 mean margin: own cash -3,549 and rival cash +17,428.25. Collected quantities remain close through day11, then diverge later. These measurements locate a remaining lower-executor/market gap; they do not implicate layout alone. Full paired artifacts are under the corrected fixture's `independent-audit.json` and `paired_summary.json`; source-versus-exact phase quantities and cash are in the original control directory's `exact_vs_source_phase_summary.json`.
