# Fixing recurring mgt_m1 production-plan mismatches

The worst tape's strawberry failure is real, but a blanket strawberry increase is not supported. I replayed all **198** available mgt_m1 ladder games with the exact official engine and recorded actions: **89 losses and 109 wins**. The [cross-game artifact](../results/fresh/m1_cross_game_symptoms/summary.json) and [script](../scripts/audit_m1_cross_game_symptoms.py) record planting, actual harvest, fertilizer use by crop, sales, cash, and early farm capacity for both seats. No agent action was changed.

| Symptom | Losses (89) | Wins (109) | Meaning |
|---|---:|---:|---|
| Fewer strawberry plots than opponent | 59 | 78 | Common even in wins; rival count alone is not a buying instruction. |
| Less fertilizer on strawberries | 54 | 71 | Broad allocation difference, but not necessarily profitable to reverse. |
| Both fewer plots and less berry fertilizer | 52 | 69 | The worst episode is a severe member of a widespread pattern. |
| Strawberry revenue gap worse than −5,000 | 34 | 18 | Large *cash* shortfalls concentrate in losses. |
| Our berry yield below 7/plot while rival reaches at least 7.4 | 19 | 21 | The extreme 5.75-vs-7.52 yield gap is not present everywhere. |

Across all 198 games, mgt_m1 used **35,845** fertilizer on crops versus opponents' **20,062**, yet only **10,303** of its applications went to strawberries versus opponents' **11,851**. Its aggregate strawberry yield was **7.38 per planted plot**, almost the opponents' **7.46**; many crops already approach the eight-unit ceiling. Episode 111345443 was much worse at **5.75 vs 7.52**. Thus fertilizer redirection requires checking each cohort's remaining unboosted production, not just globally preferring strawberries.

The route mismatch is systemic. In the **89 losses**, the selected tape disagreed with the newly revealed store in **383 slots**; **71** games made no donor switch after day 12. At day 12, **16** losses had more *known* strawberry-shop demand than the selected donor's first four shops; their median observed final berry revenue gap was **−11,205**. This is an association within losses, not the gain from a patch. The existing 584-tape coverage audit found median compatible-donor counts of **10 at day 15, 2 at day 18, and 1 at day 21**. Retuning the donor score cannot repair a later state when no suitable executable donor remains.

## Recommended architecture

Keep the current tape as a reliable base schedule, but make the **production plan** a separate decision. At each shop reveal, compare the tape's remaining crop and animal **cohort trajectory** with plans retrieved from leader tapes by visible product demand and current farm assets. A donor may supply target counts and timing even when its coordinates cannot be replayed. Preserve existing productive cohorts and compile only the incremental jobs needed to approach a feasible target. Replan on later shop reveals while protecting already-funded care and feed obligations.

The plan selector should evaluate a **complete remaining-season marginal competitive margin** for each small change: our extra sales, the price effect on all our existing sales, the effect on opponent prices, seed/animal/land/hire/feed/fertilizer expense, crop maturation, and the capacity of actual workers and tiles to maintain and deliver the output. Use known shops, current market state, current cohorts and visible rival assets. Unknown future shops get a conservative distribution rather than one donor tape's future sequence. A current quote or a deficit against the opponent is not a sufficient signal; the rejected extra-sheep and strawberry-hold experiments demonstrate why.

## Smallest useful implementation and evaluation

Start with one **bounded strawberry cohort delta** at the day-9/day-12 branch: propose zero, two or four additional plots, plus scheduled fertilizer on berry cohorts that can still use it. A fourth land block is a separate candidate only when its extra productive capacity pays for the 4,000 cost and associated workers. Use a small fixed route for the extra jobs, reserve seeds/fertilizer and future water/harvest visits, and leave existing animal feed and protected tape jobs intact. Abort the delta when real purchases, tiles or visits fail; never count planned fruit as produced fruit. This is a proof of the plan/execution interface, not a global strawberry rule.

Evaluate the change first on episode 111345443 and other **day-12 berry-demand-positive** cases, then on paired losses **and wins**, and finally on untouched seeds and active opponents. Require exact action/ledger replay, sustained crop care, no displaced feed failures, and improvement in **both-seat final margin**, not just our fruit units. Report per-product sales and the opponent's price loss. If the bounded delta fails, improve the price/service forecast or target choice before broadening to milk, wool, carrots, and tomatoes. The same interface then handles all 56 observed directed store-mismatch pairs without hand-writing 56 rules.

The 107 no-effect commands in the worst game deserve a separate state guard, but they mostly target empty or already-cleared tiles; only a few occur on live berry plots. Replacing those commands alone cannot create the missing orchard. The first economic test should change a serviced production cohort, not simply remove no-ops.

Related evidence: [deep episode audit](deep_tape_audit_111345443.md), [store mismatch screen](store_mismatch_production_shift.md), [production-plan fit audit](production_plan_best_fit.md), [continuation design](production_plan_continuation.md), [scheduler contract](tape_gap_scheduler_contract.md), and [rejected larger-shift tests](larger_production_shift_20260923.md).
