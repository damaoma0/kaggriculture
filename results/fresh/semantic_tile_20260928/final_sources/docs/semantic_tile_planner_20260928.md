# Semantic tile planner on KB115LT — 2026-09-28

**The strict semantic tiler passes the requested local 40-world gate.**
`ST28REUSESTRICT` wins **26/40**, compared with **27/40** for exact DSM tiling
on the same frozen KB115LT executor. Mean competitive-margin difference is
**+151.58**, bootstrap 95% CI **−554.13 to +799.22**. The predeclared one-sided
paired regression test gives **p=0.6670**: no significant deterioration.
This accepts the tile-planning component for the requested oracle-input stage;
it does not establish statistical equivalence or competition deployment readiness.

## Result and scope

| Measure | Exact DSM tiling + KB115LT | Semantic tiling + KB115LT | Paired change |
|---|---:|---:|---:|
| Opponents beaten | 27/40 | 26/40 | One fewer |
| Mean final own cash | 110,463.08 | 110,854.08 | +391.00 |
| Mean final rival cash | 108,515.68 | 108,755.10 | +239.43 |
| Mean competitive margin | +1,947.40 | +2,098.98 | +151.58 |

Margin improves in 20 worlds and worsens in 20. One loss becomes a win and two
wins become losses. Individual changes range from -6,620
(episode 112602061) to +5,038 (episode 112577829).
There is no evidence of a reliable improvement claim either; the confidence
interval includes zero.

The allocator was chosen using the existing eight-world development panel.
In the strict run those eight have 6/8 wins and
mean paired margin +35.00. The disjoint
remaining 32 have **20/32 wins**, paired margin **+180.72** (bootstrap 95%
−593.89 to +895.34). These 32 were not used to choose the allocator. The full
40 includes the development eight and is not a wholly untouched holdout.

The benchmark replays DSM's recorded opening on zero-based days **0–10**.
The tiler starts from the public **D11** farm and generates days **11–29**.
Both arms use the same forced shops, recorded opponent actions, daily hires,
frozen executor, configuration, and engine timeout regime. Market prices still
respond to our changed supply. This does not measure independently responsive
opponents or an independently generated opening.

Source semantics omitted the final midnight and incorrectly reported zero
hands on day 29. Actual successful hires are 10 in all 40 worlds; both arms
receive that correction. No executor policy changes are part of this comparison.

## What is implemented

The input is DSM's actual daily quantities of plantings, building changes,
one-time crop endings, crop removals/disappearances, animal additions,
retirements/exits, land additions, and hires. Future coordinates, source cohort
identities, maintenance, ongoing first-harvest dates, transactions, and opponent
results are excluded. The final artifact is `semantic_inputs_strict_clean.json`.
Full future change quantities remain oracle inputs, as requested for this stage.

1. **Anonymous crop lifetimes.** A small integer program links birth counts to
   feasible endings using the official crop maturity and lifespan rules. It
   chooses cohort links without DSM's future tile identities. Ongoing first
   harvest markers are derived from these crop clocks.
2. **Daily tile allocation.** A deterministic joint assignment favors reusing
   same-crop slots, compact cohorts, and modest travel/workload costs. Multiple
   greedy starts and improving swaps choose free sites. Future plants cannot
   occupy a live cohort's tile before its planned release.
3. **Retirement.** Explicit first-unfed markers coexist with physical occupancy.
   Same-species retirement choices consider remaining production phases and
   service distance. Retirement is a permitted plan decision, not inherently a
   failure or something the allocator must prevent. Escape occurs after the
   second unfed evening, leaving the structure behind.
4. **Executor interface.** The output contains all eleven `TilePlanView` fields
   plus daily 100-tile end-of-day states, retirement markers, exits, and hires.
   `board[d]` in the legacy executor interface is start-of-day; the explicit
   end-of-day plan is in `planner_metadata.daily`.

This is substantial retiling: **6,696 of 8,326 future crop plantings (80.4%)**
use a different tile from exact DSM tiling. Every world has changed placements.
All 40 compiled schedules conserve the requested daily counts without warnings.
The selected configuration is **strict / reuse / no suffix polish**.

## Validation and execution limits

All **80 paired local games** completed with both agents DONE and 720 states.
All daily own-cash ledgers reconcile; both final cash values match the ledgers.
There are **zero executor errors and zero interface leaks**. The candidate's
maximum measured overage bank is **13.22 seconds**; no candidate exceeds 60.
Normal 1-second action timeout settings were retained. A local pass does not
certify Kaggle machine performance.

The final code passes **46 tests** covering lifecycle feasibility, count
conservation, explicit occupied retirement, input isolation, output validation,
timeout rejection, and the 20-win/statistical gate. A poisoned-field audit
recompiles all 40 plans with **zero forbidden-data reads**. The default builder
using the final clean inputs reproduces the **entire tested plan JSON byte for
byte**, including retirement metadata.

Execution can deviate from the desired layout. The audit records 8,097 plantings
on the planned tile/day and 54 matched late, out of 8,326 planned; terminal
censoring and unmatched events are retained separately. Animal exits include
451 matches to planned tile/day, 3 timing drifts, and 28 outside the tile plan.
These are diagnostic categories, not automatic economic-loss labels. Relative
to exact tiling, mean harvested units are +1.65 and movement commands +31.95.
See `execution_audit_strict40.json` for the full unit and cash breakdown.

No final midnight is executed on D29. Terminal no-feed without an observed
escape is censored; it is not invented as a confirmed retirement/exit. Planned
D29 occupancy is a desired state rather than a verified source midnight.

The initial Kaggle jobs timed out, and an inherited exporter padded missing
cash observations. **All 56 initial cloud outcomes are excluded from policy
statistics.** The corrected local harness verifies endpoints explicitly. Local
compute replaced Kaggle at the user's request. No cloud jobs or local game
pools from this experiment remain running; no competition submission was made.

## Reuse and reproduction

[API/CLI and schema guide](semantic_tile_planner_usage_20260928.md) documents the
builder and an actual cow-retirement example. Primary entry point:
`scripts/build_semantic_tile_stack_20260928.py`, with pure `make_plan(semantic)`.
The executor is unchanged `agents/mgt_lead_kb115lt.py`, SHA256
`2ebe94ece8ef48bf0058e620b5803c11050de7e663a63f4f41522f0758186ee0`.

Artifacts are under `results/fresh/semantic_tile_20260928/`:

| Artifact | Purpose |
|---|---|
| `semantic_inputs_strict_clean.json` | Final strict counts and public opening |
| `plans/reuse_strict.json` | Tested full tile plans and retirement metadata |
| `spec_strict_v4.json`, `selection_strict_v4.json` | Frozen candidate and selection record |
| `reports/strict40/report.md`, `report.json`, paired CSV | All 40 results, uncertainty, per-world audits |
| `runs/life_local/shard0`, `runs/exact_remaining32/shard0` | Complete exact control |
| `runs/strict40/shard0`, `shard1` | Complete strict candidate |
| `local_runtime_v3/`, `local_runtime_v3_manifest.json` | Immutable local engine/runner/source snapshot |
| `execution_audit_strict40.json`, `layout_divergence.json` | Desired versus actual execution and retiling |
| `final_contract_audit.json`, `strict_scope_cleanup_audit.json` | Input boundary and identical-plan evidence |
| `final_raw_independent_audit.json` | Independent reaggregation of all 80 raw games and 2,400 daily cash balances |
| `build_verification/final_clean_plans.json`, `final_tests.log` | Final builder and test evidence |
| `final_manifest.json` | Final source/result hashes and gate decision |

Use the immutable snapshot for exact replay because this shared repository has
other ongoing experiments. The frozen plan SHA256 is
`5d372d0718722512ea3a780252f067f5ab3bbfdd78343ce373565d3c2b51f727`.

The initial compiler's copied ongoing-first-harvest counts exceeded the strict
contract. Its retained `COHORTLIFE`, `REUSELIFE`, and `REUSEPOLISH` results are
**timing-extended diagnostics**, not qualification evidence. See
[scope audit](semantic_tile_input_scope_audit_20260928.md) and
[cloud timeout audit](semantic_tile_cloud_timeout_20260928.md). The extended
reuse ablation scored 25/40, paired margin +162.60; its separate report explicitly
refuses the strict shipping gate. The strict candidate above independently
satisfies the requested input boundary and performance gate.
