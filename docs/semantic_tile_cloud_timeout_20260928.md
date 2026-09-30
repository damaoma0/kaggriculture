# Semantic tile mission: invalid cloud timing controls (2026-09-28)

The first cloud baseline is **not a valid 40-world policy comparison**. Preserve
these results as timeout diagnostics. The naive result, 2/40 wins and mean margin
-$27,824.85, must not be described as KB115LT's strategic performance.

## Frozen inputs and execution

- Private Kaggle dataset: `yiyangxudmm/kaggriculture-semantic-tile-20260928`, version 1.
- Kernels: `yiyangxudmm/kgr-sem28-exact-0-s0` and `yiyangxudmm/kgr-sem28-exact-1-s0`.
- Twenty of the existing forty DSM worlds per kernel, four game workers per
  kernel. Both ran engine `kaggle-environments==1.32.7` on Kaggle CPU.
- Arm `ST28EXACT`: frozen KB115LT, with `sd_tp_file` reading the exact DSM JSON
  plan. The sole plan correction was `hands[29]: 0 -> 10` in all forty worlds,
  restoring the source's successful final-day hires. All other plan fields match
  `results/fresh/tile_plans/dsm40.json`.
- Executor SHA256:
  `2ebe94ece8ef48bf0058e620b5803c11050de7e663a63f4f41522f0758186ee0`.
- Full immutable input copy:
  `results/fresh/kaggle_remote_semantic_tile_20260928/dataset_v1/repo/`.
  Source hashes: `results/fresh/semantic_tile_20260928/bundle_v1_manifest.json`.
- The notebooks did **not** set `KAGG_NO_TIMEOUT=1`. They used the engine's normal
  deadline while the existing KB115LT configuration set `sd_bank_stop=1e9`.

## What failed

Both notebook commands returned exit code 0, and the first wrapper reported all
forty jobs complete. Its final physical-money versus reward equality did not
prove that an episode reached the season end. The existing sector harness reads
`env.steps[min(day * 24, len(env.steps) - 1)]`; after an early termination, every
later requested day's money therefore repeats the last physical state.

The full ledgers expose the truncation: **34/40** have `days[d].cash == null`
before the end of the season. First missing-day counts are:

| First missing daily callback | Games |
|---|---:|
| D25 | 3 |
| D26 | 13 |
| D27 | 9 |
| D28 | 8 |
| D29 | 1 |
| No missing daily callback | 6 |

The six without a missing callback are not independently certified complete:
the old wrapper did not preserve final engine statuses or the number of states,
so an interruption during D29 remains possible. All forty are excluded from the
primary quality comparison rather than selecting apparently successful runs.

Recorded planner bank use spans **51.9401 to 64.4449 seconds**. Together with
truncation under the normal engine deadline, this identifies a cloud timing
failure. The engine also charges time outside the planner's own counter, so a
counter below 60 is not proof of avoiding a deadline. No executor exception or
tile-interface leak was required for this failure.

All complete adjacent daily cash transitions that remain readable reconcile as
`starting cash + revenue - purchases - wages - land = next cash`. This validates
those recorded transitions, not the missing suffixes.

The sector harness's action-stream exporter begins with the source DSM action
tape, then overwrites observed live actions. A truncated stream may consequently
retain unexecuted DSM actions after the interruption. **Do not treat those
suffixes as executed actions or use them for a season-end reconstruction.**

## Preserved artifacts and repair

- Raw notebook outputs and logs:
  `results/fresh/kaggle_remote_semantic_tile_20260928/sem28-exact-*/output/`.
- Merged results, full ledgers, input manifests, and completion records:
  `results/fresh/semantic_tile_20260928/runs/exact/shard0/` and `shard1/`.
- Per-world diagnostic audit:
  `results/fresh/semantic_tile_20260928/runs/exact/cloud_timeout_audit.json`.
- The cohort/reuse pilot also finished and was fetched. **All sixteen games are
  truncated**: all eight `ST28COHORT` games have a missing daily callback from
  D24–D29, and all eight `ST28REUSE` games from D25–D29. Recorded bank ranges are
  60.4953–67.6503 seconds and 60.2186–65.3986 seconds respectively. The naive
  0/8 result of each arm is a timeout artifact, not a policy result. Their frozen
  inputs are in `dataset_v2/repo/`; outputs and per-arm timeout audits are in
  `results/fresh/semantic_tile_20260928/runs/pilot/`; raw notebook output is under
  `results/fresh/kaggle_remote_semantic_tile_20260928/sem28-pilot-0/output/`.

The later immutable `local_runtime_v3` wrapper now saves final engine statuses,
state count, final step, configured action timeout, and remaining engine overage;
requires `DONE/DONE` and exactly 720 states; and reconciles every daily own-cash
ledger. A separate `--no-timeout` mode is explicit in the manifest and is never
silently mixed with normal-deadline controls. The user subsequently authorized
local compute; no additional cloud kernels were launched. Valid local exact and
candidate controls are the primary comparison.
