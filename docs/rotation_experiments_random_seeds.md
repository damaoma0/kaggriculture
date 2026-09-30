# DSM / UMG tape experiments on fresh random seeds

**No reliable improvement established. Keep mgt_m1.**

The experiment tested three changes and a routing control. The baseline file was not edited, and no submission was made.

## Design

- Two random diagnostic seeds (both seats), followed by 12 development seeds (both seats). Five agents against the frozen V56 opponent: 20 diagnostic games and 120 development games.
- A separate 32-seed validation set was sampled before any game outcomes. The highest positive development mean margin improvement selects one candidate; that candidate is evaluated unchanged against V56 with a same-seed m1 control, and directly against m1, both seats.
- Complete 30-day games: 719 actions and 720 states. Natural engine RNG, active opponents, no forced shops, no extra starting cash, and reconciled cash ledgers.
- Bootstrap intervals resample entire seeds, retaining both seats together (12,000 resamples). Seats are not treated as independent worlds.
- New seeds were checked against 514 saved seed/experiment manifests: no overlap. The reserved qualification block was not used.
- Same initial seed does not guarantee the same eventual shops: policy-dependent weed draws consume the shared RNG. The results estimate competitive performance under natural RNG, not a fixed-shop causal crop effect.

## Approaches

1. **DSM library:** replace the 584-tape UMG library with 108 complete DSM calendars, retaining the m1 execution and repair layers. Begin with a DSM opening and route within DSM; no late UMG-to-DSM coordinate splice.
2. **Age-aware UMG selection:** retain all 584 tapes and add 0.35 per day of same-type cohort age mismatch, capped at four days per tile, to the routing score. Historical donor ages come from establishment actions; runtime queries use only the current farm.
3. **Tomato rotations:** replace at most two native wheat plantings during days 12–18. Reserve native visits for watering, age-11 harvest, cleanup, and retain the route through the commitments. No added moves or hires. Seed purchases and lost native production are charged by the engine; supplemental sales require tracked delivery.
4. **Hold control:** make the same commitment selection and retain the route, leaving native crops and market actions unchanged. This separates the routing restriction from crop substitution. It is adaptive, so later eligibility can differ once farms diverge.

These are bounded prototypes, not a general whole-farm continuation planner.

## Development results

| Approach | Games | W / T / L vs V56 | Mean margin | Change vs mgt_m1 | Own cash change |
|---|---:|---:|---:|---:|---:|
| Unchanged mgt_m1 | 24 | 16 / 0 / 8 | +3,782.7 | +0.0 | +0.0 |
| DSM tape library | 24 | 10 / 0 / 14 | -6,138.2 | -9,920.9 | -15,701.7 |
| Age-aware UMG routing | 24 | 16 / 0 / 8 | +3,820.8 | +38.2 | +82.2 |
| Two tomato rotations | 24 | 16 / 0 / 8 | +3,726.2 | -56.5 | -1,765.5 |
| Hold the selected tape (control) | 24 | 18 / 0 / 6 | +4,346.7 | +564.0 | +269.2 |

Positive changes mean a larger final cash margin against V56 than m1 obtained on the same initial seed and seat.

The age-aware selector changed actions in 2/24 games. Its +38.2 gain came from 1/12 improved seeds; 11 were unchanged.

The rotations established and harvested 48 crops, yielding 192 confirmed tomato units. Tracked delivery confirmed 182 units; not every harvested unit became separately credited delivery. Mean own cash fell 1,765.5.

Relative to the hold control, rotations changed mean margin by -620.5 (seed-bootstrap 95% interval -1,071.2 to -244.4).

## Independent validation

Selected before inspecting validation outcomes: **Hold the selected tape (control)**.

| Approach | Games | W / T / L vs V56 | Mean margin | Change vs mgt_m1 | Own cash change |
|---|---:|---:|---:|---:|---:|
| Unchanged mgt_m1 | 64 | 41 / 0 / 23 | +3,024.9 | +0.0 | +0.0 |
| Hold the selected tape (control) | 64 | 43 / 0 / 21 | +3,109.2 | +84.3 | +390.1 |

Held-out paired margin improvement: **+84.3**, 95% seed-bootstrap interval **-735.0 to +877.2**. Better / unchanged / worse seeds: 5 / 25 / 2.

Directly against mgt_m1: **21 wins / 32 ties / 11 losses**, mean margin **+731.0**, 95% seed-bootstrap interval -73.5 to +1,830.1.

Only 54/64 candidate-versus-V56 games retained the control's full shop sequence. 50/64 action streams were identical to the control.

## Checks and limitations

All **332 benchmark games** completed. Across the evaluated own-agent calls, the largest measured decision was **4.6136 seconds**, with **32 calls over one second**. This offline harness measures decision time but does not enforce online timeouts. The V56 validation panel had no calls over one second for either m1 or the candidate; the spikes occurred in direct games hosting two large m1-family agents in one process.

Each direct game had one slow seat-0 call: 32 charged to the candidate and 32 to unchanged m1. Two additional serial timing diagnostics preserve the exact recorded action hashes and rewards. Garbage-collection callbacks identify a generation-2 collection during the first player’s day-1 action (step 24), lasting 2.064 seconds with the candidate in seat 0 and 1.089 seconds with m1 there. The raw timing failures are retained, and the direct results are offline cash outcomes rather than certification under online time limits. No GC settings or agent code were changed to make the result pass.

The donor-age audit covered 105 hourly UMG replays: 170,517 of 170,542 inferred productive tile/day ages matched (99.985%); 3,697 productive observations had no inferred age and receive no age penalty. The other 479 tapes have inferred, unaudited ages. This is a limitation of the compact tape data.

The calendar audit examined 19,479 native wheat opportunities: the original frozen overlay accepted 10,956, including two late opportunities missing planting-day water. The editable template now explicitly rejects those; all 10,954 accepted schedules in the corrected audit have planting-day water. Frozen benchmark sources remain preserved. All 48 development rotations actually produced four tomatoes, so this edge case did not explain their measured result. Rebuilding the rotation/control from the corrected template produces new hashes; those rebuilds are not the versions in the benchmark tables.

DSM replay produced about 396 additional no-effect commands per game, 66 fewer strawberries, and 23 fewer melons than m1. This rejects this direct library transplant, not the value of DSM production data or the strength of the original live DSM agent.

## Reproduction and artifacts

- `results/fresh/rotation_experiments/design.json`: random seeds, selection rule, initial hashes.
- `results/fresh/rotation_experiments/selection.json`: candidate selection before held-out results.
- Each panel has `manifest.json`, immutable-for-this-run `frozen/` sources, all game rows, logs, and `summary.json`.
- `scripts/rotation_experiment_panel.py`: frozen-source, resumable panel dispatch.
- `scripts/summarize_rotation_experiments.py`: paired comparisons, cash ledgers, activation, timing, seed-cluster intervals.
- `scripts/build_rotation_experiments.py`: rebuild variants from m1 and the local donor libraries (the rotation template includes the later day-zero guard).
- `scripts/audit_rotation_births.py`, `scripts/audit_rotation_calendars.py`, `scripts/check_rotation_seed_overlap.py`: data and schedule audits.

Baseline SHA-256: `1152ef2e12c4535dbc381b9c54ac7d7a0b1a9ad3d0a8018a7567dcf5c4a52470`.
