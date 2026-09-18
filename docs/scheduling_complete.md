# Completed scheduling research

## Final recommendation

Keep the full conditional public router as the competitive baseline. The work-order executor, worker allocator and individual-task repair are implemented and evaluated, but none establishes an improvement in normal play. They are experimental tools for controlled changes to execution.

## Completed plan

1. Extracted crop cohorts and all four public route streams into work orders; checked 2,876 recorded source actions and 14,495 task/waypoint positions against real trajectories.
2. Built a deadline-aware executor with hiring-position constraints; verified normal cash and accounting preservation and tested worker displacement.
3. Added inventory-constrained exchanges of complete daily job sequences; restored normal accounting after permutations of interchangeable workers in all 14 held-out comparisons in that study.
4. Implemented single-task watering and harvest repair, including travel, task prerequisites, helper commitments, harvest delivery, crop maturity and hiring constraints.
5. Completed focused constraints/official-engine checks, a 30-game smoke panel and a frozen 264-game final evaluation. Reconciled cash, audited successful production and recorded the final selection.

## Final evaluation design

Four unseen seeds (95200–95203), both seats, eleven scenarios and three controllers: public router, chain allocator and task repair. The 264 games use normal engine randomness and a public-router opponent. The smoke seed 95100 is excluded. Controllers and scenario rules were frozen before running the final panel.

The panel includes normal and equal-inventory position permutations at turn 224; two-tile displacement of the first three workers on days 9, 16 and 26, at hours 8, 16 and 20. Full native-router prefixes preserve the conditional branch state at each checkpoint. All continuations reach the season end. Disruptions are synthetic; four seeds and correlated seats do not establish broad generalization.

## Terminal cash by scenario

| Day / hour | Condition | Public router | Chain allocator | Task repair | Repair minus allocator |
|---|---|---:|---:|---:|---:|
| 9 / 8 | normal | 78,087.0 | 78,087.0 | 78,087.0 | +0.0 |
| 9 / 8 | permuted | 75,921.0 | 78,087.0 | 78,087.0 | +0.0 |
| 9 / 8 | displaced | 77,179.5 | 77,986.5 | 77,986.5 | +0.0 |
| 9 / 16 | displaced | 80,807.0 | 80,871.8 | 80,871.8 | +0.0 |
| 9 / 20 | displaced | 80,872.8 | 80,848.5 | 80,848.5 | +0.0 |
| 16 / 8 | displaced | 78,472.2 | 77,566.0 | 77,566.0 | +0.0 |
| 16 / 16 | displaced | 80,125.8 | 78,238.0 | 78,238.0 | +0.0 |
| 16 / 20 | displaced | 80,689.0 | 78,622.8 | 78,622.8 | +0.0 |
| 26 / 8 | displaced | 77,049.2 | 78,045.8 | 78,045.8 | +0.0 |
| 26 / 16 | displaced | 77,525.2 | 78,045.8 | 78,045.8 | +0.0 |
| 26 / 20 | displaced | 77,885.0 | 78,016.8 | 78,016.8 | +0.0 |

## Execution and production

- Repair issued 0 transferred WATER operations and 0 transferred HARVEST operations, with 0 approach steps, across 88 repair continuations.
- Realized successful watering counts and harvested quantities match the allocator in 88/88 paired continuations.
- All eight normal seed-seat pairs match the router in terminal cash, complete sales/spending ledger and successful-production counters, with zero late task attempts.
- Final route coverage across repair continuations: {'main': 66, 'milk_glut': 22}. This panel does not establish coverage beyond those observed branches.
- Production counters wrap the official engine’s unit-action function: water counts only false-to-true watering transitions; harvest quantities count actual inventory gains before market processing. These counters cover only the continuation after its checkpoint.
- Every game finished with valid states and exact cash reconciliation for both players. Focused tests also verify helper travel does not prematurely complete a task, deadlines are protected, wheat feeding stock is not diverted, harvest delivery is required, and transferred watering/harvesting succeeds in the engine.

The first audit wrapper raised an IndexError on source commands for nonexistent hands, which the engine normally ignores. It was corrected without changing either policy; the 65 already completed valid games were retained and the remaining jobs resumed. Both observer manifests are preserved. Failed/incomplete games are excluded.

## What the repair policy does

Consider only the next uncompleted job in a worker’s sequence, once due. A helper must arrive sooner than its owner and return to its own next job by that job’s original deadline. Preserve future hiring positions. Validate the crop and operation. Mark a transferred job complete only when issuing its operation at the target, not while approaching it. Retain normal observed-state route branch selection and market repairs.
Harvest transfers exclude wheat, because the original worker may need it for feeding. They require a scheduled helper DROP before midnight/season end, and reject harvests promised to an explicit owner PLACE order. These are conservative rules, not a complete model of shared shed capacity or future prices. Watering takes priority near midnight.

## Interpretation and limits

The router’s dense daily schedules leave limited slack. A policy that forbids delaying any helper commitment may therefore have little opportunity to intervene. This is a measured limit of this repair approach, not proof that the router is optimal. Large cash differences under artificial disruption can also arise from downstream market and randomness paths; production and cash must be read together.
No investment optimizer, imitation-learning model, general farm-layout planner, global assignment solver or inventory-transfer system was implemented. Those were possible later research directions, not requirements of this scheduling plan. The completed policy still follows the router’s economic program.

## Reproduce

```powershell
.venv/Scripts/python.exe scripts/verify_task_repair.py
.venv/Scripts/python.exe scripts/test_router_task_repair.py --seeds 4 --workers 4
.venv/Scripts/python.exe scripts/report_task_repair.py
```

[Results](../results/fresh/router_task_repair_final/results.json) · [Frozen hashes](../results/fresh/router_task_repair_final/manifest.json) · [Earlier allocation study](router_allocator.md) · [Production routines](router_routines.md)
