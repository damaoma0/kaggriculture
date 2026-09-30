# Tape research: findings from the other project discussions

This note integrates the user's suggestions in **Review kaggriculture project context**, the fresh evidence in **Refetch game records and diagnose**, the tape-picker comparison, and the saved production-plan research. It adds a read-only audit of the completed V9 panel. No new games, policy changes, or submissions were made for this note. The completed 106-pair panel remains frozen.

## User suggestions carried into the next experiment

- Use coherent **three-day production segments**, including planting, herd investment, service obligations, and the farm state left for the next segment.
- Treat shop composition as context. Select using the current farm, timing of revealed demand, resource commitments, transition cost, and expected economic value.
- Transfer a donor's production decisions onto our own available tiles and workers through the labor scheduler.
- Adapt after a shop reveal provides new evidence. Earlier intervention means an earlier **observed reveal**, without supplying future shops to the policy.
- Judge progress against original m1 and live V56 on fresh worlds, including wins, large losses, and runtime. Leader recordings can suggest plans even when their exact commands cannot be replayed.

V9 implements economic comparison and a three-day commitment to an existing tape. It does not yet implement a general compiler for a donor's semantic production plan. Its candidate set still depends on nearby tile arrangements, and its fixed continuation cannot repair a missing feed, delivery, or crop-replacement job automatically.

The earlier segment prototypes identify execution requirements: the first reproduced 4/12 native windows, the later compiler 8/12. The maintenance continuation still lost because replacement crop cycles disappeared. A segment must carry its next planting and investment obligations forward as well as protect today's assets. See [execution and recovery](continuation_execution_and_recovery.md) and [production-plan recommendations](m1_plan_fix_recommendation_20260923.md).

## What the fresh diagnosis adds

The other thread reconstructed 54 new games exactly, including 25 m1 games. For **m1 alone**, successful whole-season sales were:

| Product | m1 | Matched opponent | Shortfall |
|---|---:|---:|---:|
| Strawberry | 226.28 | 244.28 | 7.4% |
| Wool | 131.16 | 167.56 | 21.7% |
| Milk | 201.92 | 231.28 | 12.7% |

At day 12, m1 had 21.8 strawberry plots versus 32.2, 5.84 sheep versus 7.24, and 7.72 cows versus 8.12. Effective feeding and care covered 70.6% versus 82.2% of observed sheep-days and 72.0% versus 82.3% of cow-days. The rates include planned wind-down, so every skipped service is not necessarily an error.

The archived DSM comparison suggests earlier strawberry establishment matters: in the combined fresh cohort we are behind DSM at day 7 but ahead in standing plots by day 18. DSM's different shop draws make this descriptive evidence. Across the new losses, strawberry harvest per planting was already close to the eight-unit ceiling. These observations support testing **timely, serviced cohorts**; they do not establish the return from adding plants, animals, or fertilizer indiscriminately.

Sources: [fresh-game diagnosis](records_refresh_20260923.md), [farm comparisons](fresh_farm_gaps_20260923.md), and their JSON artifacts.

The other thread's eight-game V9 sample improved two cases (+2,233 and +5,853), with no regressions. Two unchanged games, **112483478 and 112502033**, also appear in our ten-game panel of exactly reproduced m1 recordings. Six of its 25 fresh m1 records overlap our recordings. These panels should retain their separate sampling designs and headline estimates; counting every appearance as an independent new game would overstate the evidence.

## New audit: where V9 runs out of candidates

The following counts are from the **64 completed live matchups on 32 fresh worlds**, evaluated at days 12, 15, and 18. Alternatives include retaining the incumbent tape through the next reveal. They are candidate evaluations, not unique tapes or independent games.

| Reveal | Alternatives evaluated | Rejected for losing a cohort preserved by the baseline | Share |
|---|---:|---:|---:|
| Day 12 | 384 | 59 | 15.4% |
| Day 15 | 375 | 200 | 53.3% |
| Day 18 | 356 | 218 | 61.2% |
| Total | 1,115 | 477 | 42.8% |

The other outcomes were 293 alternatives not expanded after their first scenario, 298 stopped after a nonpositive four-scenario risk score, 38 failing the final eight-scenario gate, and nine admissible alternatives across seven selected decisions. All categories reconcile to 1,115. An unexpanded alternative is untested under the remaining futures; it is not a demonstrated bad plan.

The ten exact native-recording controls had 80/173 alternatives rejected for cohort loss. The other 21 recordings without major command failures had 171/368. Their opponents still replay fixed actions, so these counts are kept separate from the responsive panel.

**Interpretation:** later adaptation is increasingly constrained by the executable transition. This supports generating a repair to the candidate's missing jobs. It does not establish that removing the preservation rule would improve results. Intentional retirement needs an explicit economic comparison, while accidental loss needs a repaired schedule.

## Untouched loss: Snorlax, episode 112109339

This is the exact-native-control game with margin **−25,467**. Baseline and V9 are action-identical, and both final balances, hourly farm states, and private states reproduce the recording. The first three reveals are Yarn Stores, already known by day 9. The later sequence is Bakery, Bakery, Farmers Market, Farmers Market, Pet Cafe.

| Metric | m1 | Snorlax |
|---|---:|---:|
| Sheep at day 9 | 9 | 10 |
| Sheep at day 12 | 21 | 29 |
| Sheep at day 18 | 25 | 31 |
| Sheep at day 24 | 25 | 25 |
| Wool harvested | 541 | 558 |
| Wool sold | 516 | 558 |
| Average realized wool sale price | 154.10 | 171.70 |
| Wool revenue | 79,514 | 95,811 |
| Hire expense | 16,668 | 4,305 |

The cash ledger decomposes exactly:

| Contribution to our margin | Amount |
|---|---:|
| Wool revenue gap | −16,297 |
| Extra hire expense | −12,363 |
| All other revenue and spending differences, net | +3,193 |
| Final margin | **−25,467** |

This game has a midseason herd gap, but the final harvest gap is only 17 wool. A further 25 of our harvested units were not sold; 11 remain in worker inventory at game end. The remaining 14 require tracing the delivery/storage history before attributing their loss. Different average sale prices reflect sale timing and market conditions; the ledger is not an estimate of profit recoverable from a particular intervention. Similarly, the hire gap cannot simply be removed while assuming unchanged output.

At day 12, route 2 is best in the first simulated future (+1,761 margin), but its four-scenario mean becomes −41.25, with risk score −1,607.83. It is screened out. Other routes left at one scenario have no complete value estimate.

At day 15, all four tested changes of tape lose at least one protected cohort. Three lose the sheep at (3,8); the fourth loses that sheep plus others. At day 18, all four changes fail preservation again. One loses only a tomato cohort; others lose a cow, sheep, tomato, or strawberry cohorts. Retaining the incumbent adds no value here because the native router already retains it.

This gives concrete repair targets: preserve the missing sheep service, classify a proposed tomato retirement by its remaining value, keep wool deliveries and sales feasible, and price the labor used by both the old and additional jobs. A smaller crop-output target alone would miss the dominant wage and wool-revenue differences.

## Next experiment implied by the combined evidence

1. **Repair transitions in a separate research policy.** Start from the known failed cohort/job in a candidate rollout; add feasible feed, care, water, harvest, or delivery jobs on our actual farm. Retest the full remaining season and the state at the next reveal. Planned retirement must be explicitly valued. Preserve the current V9 results as the comparison.
2. **Add reveal-conditioned production deltas.** Test bounded earlier strawberry cohorts at day 9/day 12 and sheep/cow service or investment changes where observed demand supports them. Include feed reservations, future service, replacements, and displaced work in the same plan. The Snorlax world also justifies studying the day-9 Yarn response.
3. **Expand search using verified transition features.** The first-scenario shortlist leaves many alternatives unresolved. Rank by actual three-day output, delivery, expense, and resulting cohorts, then reserve exact multi-future evaluation for finalists. The existing requested-plan-only ranker missed major recoveries, so it is not a proven replacement.
4. **Keep economic and execution effects visible.** Report realized own and rival cash, sale quantities and dates, expense by category, surviving cohorts, and the reason each candidate is rejected. Evaluate on new worlds after developing on these inspected cases; these cases are now development data.

Reproduction: `scripts/audit_cross_thread_tape_findings_20260923.py` reads the existing completed artifacts and checks the panel sizes and the Snorlax ledger. Its output and hashes of every input read are in `results/fresh/tape_cross_thread_20260923_01a0/audit.json`. Running it creates no games and does not modify either source panel.
