# V14 net-fertilizer forecast: recorded development8

V14 versus the eight frozen 2750–3000 recorded opponents completed with **4/8 wins, mean margin −774.75**. The exact V13 baseline on these same worlds won **4/8, mean margin −13.5**. The paired change is **−761.25 margin per game**, with two improvements and six regressions. V14 stays out of the stack; no V14 live panel or qualification was dispatched.

| Episode | V13 margin | V14 margin | Paired change |
|---|---:|---:|---:|
| 112615422 | −2,793 | −2,882 | −89 |
| 112181121 | 3,991 | 4,443 | +452 |
| 111871547 | −10,154 | −10,431 | −277 |
| 112612822 | −694 | −424 | +270 |
| 111902048 | 3,848 | 2,685 | −1,163 |
| 111681195 | 6,216 | 4,168 | −2,048 |
| 112610631 | 4,311 | 2,652 | −1,659 |
| 112476470 | −4,833 | −6,409 | −1,576 |

The existing V13 results were reused with their result/action hashes bound before V14 ran. Each V14 game used the same native seed, seat, forced shop sequence and recorded rival commands as its V13 comparison, with independently verified original source controls. All eight pairs have identical shops. Prices can still change in response to our trades, while the recorded rival cannot change its requests; this measures the specified scripted-opponent comparison, not a live rival policy effect.

The only candidate changes from frozen V13 are the reviewed base/block policy and net-fertilizer helper with `policy.forecast_fertilizer_net=true`. Executor, tiler, wrapper, model and original harness remain identical. Candidate manifest SHA256 is `777116e0c9ac309d9481eac1e1da5621c926b380214e73a7c2aaac8b02024b5d`; the eight-case dispatch manifest is `1dcba12c0158838293862678d818dc6c641597a0a357103f3cad04a66b3bba64`.

## Actual fertilizer use and economics

These are totals across the eight games for our side, measured from successful engine operations and complete ledgers, not forecast quantities.

| Fertilizer measure | V13 | V14 | Change |
|---|---:|---:|---:|
| Collected | 2,842 | 2,846 | +4 |
| Consumed on crops | 1,627 | 1,672 | +45 |
| Sold | 1,214 | 1,172 | −42 |
| Sales revenue | 79,911 | 77,897 | −2,014 |
| Purchase spending | 0 | 0 | 0 |

The official engine consumes exactly one fertilizer item for each effective FERTILIZE command. Thus internal use is `op:FERTILIZE − no_effect:FERTILIZE`; missing-worker and malformed commands are excluded before these counters. Daily sums match the final ledger totals. Collections denote successful inventory gains, not biological production.

Other aggregate sold-unit/revenue changes were wheat +49/+1,994, tomato +58/+2,826, carrot −60/−2,312, wool +11/+497, milk −14/−402, egg −8/−408, strawberry −1/−23, and melon unchanged. These offset to only **+158 total revenue**. Total spending rose **2,151**, chiefly wheat purchases +2,241; tomato seeds +400, carrot seeds −380, strawberry seeds −100 and wheat seeds −10 account for the balance. Hires, land and animal spending are unchanged.

Our total cash fell 1,993 (mean −249.125). Rival cash rose 4,097 (mean +512.125), giving the mean margin loss −761.25. The worst case, 111681195, loses 3,256 own cash while reducing rival cash 1,208, for a margin loss 2,048. The best margin case, 112181121, still loses 367 own cash; the rival loses 819. These are observed quantities and accounting, without attributing every change to a particular forecast decision.

## First divergence in the worst regression

In episode **111681195**, saved proposals first differ on **D13**. Both action streams match exactly through step 312; our first different action is step 313 (D13 H1), while all 719 rival actions remain identical. The D13 public/economic/private observations match after excluding only `remainingOverageTime` (56.373843 versus 55.579256). This is an explicit economic-input equality check, not a claim that the entire observations or clocks are identical.

Both block policies request **13 wheat, 3 carrots and 3 tomatoes**, with the same remaining block totals and completed jobs. The capacity-admission rule orders crops by cohort value divided by the template's `last+1` duration: wheat divides by five, carrot by four. In V13, carrot's score **133.2/4 = 33.3** exceeds wheat's **159.5/5 = 31.9**. The net-fertilizer adjustment subtracts 58 from each value, flipping the order: wheat **101.5/5 = 20.3** now exceeds carrot **75.2/4 = 18.8**. This is a duration-normalized admission ranking, not a labour-normalized score.

With the same capacity, V13 admits **7 wheat + 3 carrots + 3 tomatoes**; V14 admits **10 wheat + 0 carrots + 3 tomatoes**. Both predict work 253.8, no free tiles, 11 hands and unchanged animal targets. The next observed dawn confirms the physical result: V13 has wheat 31/carrot 5, V14 wheat 34/carrot 2, while strawberry 29/tomato 16 are unchanged. D13 actual seed spending correspondingly changes wheat +30/carrot −60. Thus the helper really changes a constrained planting choice; it does not merely revise a displayed forecast.

The subsequent game is not a one-day ablation: that different crop mix changes layout, routing, maintenance and later replanning. From D13 onward V14 issues 26 fewer CARE and 11 fewer FEED commands. Its final collected/sold egg quantity is 26 lower (revenue −1,050), fertilizer collected/sold is 14 lower (revenue −415), while internal fertilizer use is **222 in both versions**. Strawberry collection is three lower, sales five lower, revenue −1,433; carrot sales fall by 18/revenue by 539, tomato sales fall by 4/revenue by 321. Offsets are wheat sales +23/revenue +747, milk +1/revenue +160 and wool +9/revenue +15. Own revenue is therefore −2,836. Extra wheat purchases 490 and wheat seeds 50, partly offset by carrot seeds 120 less, add 420 spending and reconcile the own cash loss −3,256.

The loss develops late: V14 is ahead 554 own cash at D24 dawn, then earns 3,608 less and spends 202 more over D24–29. The resulting 3,810 late cash loss turns the earlier gain into the final deficit. Strawberry average sale price also falls 175.79→173.49; an exact season-average accounting decomposition of its −1,433 revenue is −878.94 from five fewer units at the V13 average price and −554.06 from the remaining price/timing term. These terms do not independently identify price causality.

The rival's product quantities are unchanged for every product. Its revenue falls 1,071 through endogenous prices/timing under the fixed requests, and its fertilizer purchases cost 137 more, reconciling rival cash −1,208. That benefit is smaller than our own loss. The demonstrated pathway is **net-fertilizer valuation → flipped duration-normalized capacity ranking → three carrots replaced by wheat → different executed farm/labour/sales trajectory**. It does not prove that the initial three-crop substitution alone accounts for each later animal or berry loss; resolving those individual downstream effects would need a separate controlled diagnostic.

The saved-only audit `reports/v14_worst_recorded_case_mechanism.json` binds both result/action hashes, first decision and action, equal economic dawn inputs, realized next-dawn crops, daily ledgers and the complete quantity/price/spending decomposition. SHA256: `0c5e064f86d4821b8a38b815e954cc931482d3940bd59d3920725efbd3e03407`. No policy recomputation or new game was used.

## Technical and runtime checks

All eight V14 games finished DONE for both seats with 720 states, 719 calls per seat, exact source/script bindings, complete reconciled ledgers, zero reported executor errors and no runtime invalidity. Candidate input/source audit passed, including no overlap with reserved recorded worlds. No clocks, GC behavior or timeout limits changed.

Measured V14 own overage totals 262.430 seconds across eight games, versus 177.001 for V13. V14's maximum per-game overage is 40.575 seconds and minimum remaining engine bank 19.422 seconds; maximum individual callback is 8.099 seconds. V13's corresponding maximum overage is 50.114 seconds, minimum bank 9.883 seconds and maximum callback 6.630 seconds. V14 total own callback time is 539.671 seconds versus 435.577. These sequential runs establish that both passed their actual budgets; they are not a contemporaneous isolated policy-speed benchmark.

The prospective engine-valid scripted score is 4/8 for both candidates. The original stricter command-fragility screen is preserved separately: five eligible cases and three wins for each, with 112476470, 112610631 and 112612822 flagged and retained in the full denominator. No case was excluded, replaced or rerun to improve either result.

Artifacts live in main `results/fresh/semantic_strategy_20260928/`: raw V14 results/actions/logs in `runs/strategy_v14_kb115lt2_fertilizer_net/development/recorded/`, frozen dispatch under `recorded_dispatches/v14_net_fertilizer_development8/`, and reports `v14_recorded_incremental_comparison.json`, `v14_recorded_accounting_summary.json`, plus candidate independent/strict/shipping reports. Accounting summary SHA256: `5e556f4620b9d9d2c0d771204d90090da58180874a4eaeec8ab317f1c0ed0d9e`. The pre-run independent audit is preserved separately as `strategy_v14_kb115lt2_fertilizer_net-audit-before-recorded-refresh.json`.

The copied shipping report CLI initially looked for its documentation relative to the experiment folder and failed before producing a report. Running the byte-identical main-path script resolved this path issue; its SHA256 matches the dispatch-bound copy (`a6edab00dbbca38a60b3ce04da5a7f18e23a8b8d804becec597c433a32125614`). No game or frozen harness was modified or rerun.
