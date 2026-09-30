# Generalization and speed of tape value search — 23 September 2026

The selector now recovers substantial competitive margin across three live opponents. Reusing setup and observations preserves every forecast; the final early cutoff skips only already-rejected plans. It is still a research implementation; competition timing and broader demand coverage remain unresolved.

## Results in brief

- Corrected frozen panel: **18 paired games, 9 positive / 9 unchanged / 0 negative**, mean margin **+2,882**.
- These are **six shared shop worlds** crossed with three opponents: four new IID draws and two declared stress sequences. They are not eighteen independent demand samples.
- Mean own cash **+801**; mean rival cash **-2,081**. Wins remain **12/18 → 12/18**.
- Re-evaluated at D12, D15 and D18 from the actually reached state. All nine changed games made one switch; this does **not** yet test two executed switches within a game.
- V4 wool decision **104.1s**; V5 first run **9.6s**, then **7.5–7.8s**. Every candidate forecast and admission matches.
- V6 removes another copy. Paired warm medians: V5 **49.58 CPU seconds**, V6 **27.85 CPU seconds**; wall medians 50.15s / 28.12s. Later runs were substantially slower for both implementations; the cause was not isolated. Use contemporaneous paired comparisons, and do not multiply speed ratios from different runs.
- V6 reproduces **all 54 decisions and 1,636 full forecast results**, all actual game actions and both final cash values in the corrected V5 panel.

- V7 adds exact early rejection: **126 candidates** already violate cohort protection at the next reveal. It preserves all 54 recorded decisions/admission flags and reduces simulated turns **26.3%**, from 593,660 to 437,348. This work count comes from the saved full forecasts; official-engine checks separately pass on three historical cases.

## Generalization panel

| Live opponent | Games | Better / same / worse | Mean margin gain |
|---|---:|---:|---:|
| v56 | 6 | 3 / 3 / 0 | +3,094 |
| sixday | 6 | 3 / 3 / 0 | +2,452 |
| pasture | 6 | 3 / 3 / 0 | +3,100 |

The 115-trajectory rival library, candidate count, sampled futures, protection checks and thresholds were unchanged. The opponent identity, true future shops, evaluation seed and baseline outcome never reach the selector. All games complete under the official engine with reconciled ledgers and identical action prefixes within each pair. Shop draws are fixed within each pair; weed randomness cannot change their sequence.

The twelve IID matchup observations average **+3,670**, but represent only four independent shop draws. The six stress matchup observations average **+1,306**; five are unchanged. This is promising transfer evidence, not proof of a broad win-rate improvement or coverage of rare shop combinations.

### Every changed case

| World / opponent | Switch day | Donor | Margin gain | Own cash gain | Rival cash gain |
|---|---:|---:|---:|---:|---:|
| 0-v56 | 18 | 110059839 | +6,740 | +9,353 | +2,613 |
| 1-v56 | 12 | 109561161 | +5,143 | -7,693 | -12,836 |
| 3-v56 | 12 | 109569892 | +6,678 | +2,621 | -4,057 |
| 0-sixday | 18 | 110059839 | +4,355 | +9,243 | +4,888 |
| 1-sixday | 12 | 109561161 | +3,922 | -8,662 | -12,584 |
| 3-sixday | 12 | 109569892 | +6,437 | +3,045 | -3,392 |
| 1-pasture | 12 | 109561161 | +7,178 | -6,178 | -13,356 |
| 3-pasture | 12 | 109569892 | +3,581 | +3,974 | +393 |
| 5-pasture | 15 | 109547210 | +7,838 | +8,711 | +873 |

World 1 uses donor 109561161 against all three opponents. It improves margin by +3,922 to +7,178 while **reducing own cash by 6,178 to 8,662**. Admission requires positive expected own cash across eight modeled futures; it does not guarantee positive own cash in the realized future. These three observations share the same demand branch and are correlated.

### Late-yarn example

The stress sequence opens Pizza, Ice Cream, Smoothie, Bakery, then Yarn on D15 and another Yarn on D18. Against the pasture opponent, the selector reacts at **D15**, using donor 109547210. Margin improves **+7,838**, own cash **+8,711**, rival **+873**. It buys two additional sheep, sells **53 more wool and 41 more milk**, and spends **1,152 less on wages**. Wheat sales fall by 124, carrot by 36, strawberry by 5 and tomato by 3. The other two opponents produce no admitted switch in that world.

## What made it faster

The first profile put 57% of one rollout in rebuilding the 584-tape agent and garbage collection. Much of the remaining time was observation copying.

1. **Reuse the decoded tapes and static data.** Reset private player memory, overlay state, reports and router for every rollout. Pure suffix-sale tables remain cached.
2. **Build the public simulation template once per decision.** Copy the template while preserving official shared farm/market references.
3. **Copy JSON trees directly in V5.** Avoid rebuilding framework dictionary subclasses at every node.
4. **Borrow the simulated observation in V6.** The frozen native policy is read-only. It neither changes observations nor retains mutable observation aliases; rival scenario tiles and engine/private memory remain isolated copies.
5. **Use a portable semantic memory digest.** Remove only derived `(id(tape), day)` calendar caches and the unused inplace tape ID. Keep queues, clocks, plans, cohorts, inventories and all economic state.

6. **Stop irreversibly rejected candidates in V7.** At the next reveal, compare surviving starting cohorts against those the baseline retains in that same modeled world. A missing protected cohort is already a final rejection under V4. Return immediately, restore engine hooks through the existing `finally`, and skip the remaining worlds for that candidate. Partial cash and hire counts never trigger this cutoff.

Ownership checks exercised **1,438 policy calls**. Four reset/copy/isolation regression tests pass. Historical full-forecast equality includes the +18,449 strawberry recovery, +10,034 wool recovery and an unchanged control. The V6 optimization is guarded by the exact native-agent source hash; changing that source requires another ownership audit.

V5/V6 keep every forecast. V7 omits only work for candidates whose existing rejection is already proven. Profits for these discarded candidates are left uncomputed. The three historical official-engine checks preserve selection/admission and every unpruned forecast: wool 14,360→12,996 turns, strawberry 15,516→10,560, unchanged control 17,240→17,240. V7 has not independently replayed all 18 full live games; its broader selection/admission check uses their saved forecasts. Risk thresholds, survivor ranking and physics are unchanged.

## What to generalize next

Generalize the value model using each candidate’s dated production, cash and maintenance consequences:

- **State:** revealed demand, remaining reveal distribution, market stocks/prices, rival public cohorts, own cash/stock and cohort ages.
- **Plan:** dated planting/placement, harvest and sale curves, feed/care/fertilizer commitments, labor and delivery demand, and cohorts retired or preserved.
- **Value:** paired competitive margin, own cash and downside under common demand/rival futures.

The next speed step is an **offline-trained plan value model**: use the exact paired rollouts already produced as training labels; rank a wider semantic candidate set cheaply, then run exact transition/labor checks on the few finalists. Split evaluation by shop composition, opponent strategy and source-tape family. Keep the untouched engine rollouts as the teacher and reference. Test ranking recall for profitable feasible plans and actual paired margin; forecasting error alone is insufficient.

The model should explicitly retain productive alternatives with low initial cash but high later output, and separate volume from sale timing and shared-price effects. Expanding the training set with information about the realized future of the evaluated game would invalidate the test. Existing compact semantic profiles record requests; only verified executed jobs establish successful production.

For runtime, add a deadline-aware admission path that returns native behavior when it cannot finish the required candidate/base comparisons. Reduced candidate sets or fewer worlds change the policy and need a fresh frozen panel. **Correction from the cloud audit: the installed environment has 1s per action and 60s total overage, not the previously reported 12s.** Neither this manual live harness nor the new selector enforces that budget, and no competition-ready speed claim is made. See `docs/tape_cloud_speed_20260923.md`.

## Benchmark correction and provenance

The initial benchmark called `module.agent` on V56, which is an older entry inside that file. The correction invokes Kaggle’s last-new-callable `e410_agent`, reruns the same six prespecified V56 pairs, and retains the other twelve valid pairs by artifact hash. The original run remains in `generalization/`; only `generalization_corrected/` supplies the final policy figures. This is a harness correction on the same worlds, not six additional independent tests.

V5 was frozen before all new outcomes. V6 later replays the exact same panel solely for implementation equality. Results are correlated across opponents within a shop world. No new submission or baseline modification was made.

### Files

- `scripts/value_tape_search_v5.py`: isolated reusable rollout runtime.
- `scripts/value_tape_search_v6.py`: guarded borrowed-observation optimization.
- `scripts/value_tape_search_v7.py`: exact early rejection of cohort-destroying continuations; latest research selector.
- `scripts/benchmark_value_tape_generalization_v2.py`: corrected panel and provenance.
- `scripts/validate_value_tape_live_speed.py`: complete live/forecast equality.
- `scripts/compare_value_tape_runtime.py`: paired warm wall/CPU timing.
- `results/fresh/value_tape_speed_20260923/`: source snapshots, raw profiles, decisions, cash ledgers and checks.
