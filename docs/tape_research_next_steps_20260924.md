# Next steps for tape mismatch research

Proposal after the R3 qualification, 24 September 2026. No new playing policy or performance result is claimed in this document.

## What the evidence does and does not establish

- R3's bounded repairs preserved cohorts in 194 of 200 initial fresh scouts. This applies to selected small repairs, not arbitrary transitions.
- The evaluator assigned nonpositive risk-adjusted value to 185 repairs. Their actual counterfactual returns were not all measured. Some could be profitable alternatives that the evaluator rejects incorrectly.
- The fresh incremental improvement over V9 was one +1,016 result among 48 matchups, with no additional losing-game deficit recovery. Physical repair alone has not broadened recovery.
- V9 and R3 both approved a switch that actually lost 2,530 in margin. Additional shop futures and delivery-delay stresses also approved it.
- The current rollout uses exact own-farm mechanics but fixed modeled rival trades and donor farm snapshots. The rival does not change production, hiring, inventory decisions, or purchases in response to the changed prices. Paired comparison cancels rival costs only to the extent those costs would remain unchanged.
- Earlier semantic compilers lost heavily after replacement planting disappeared. A feasible next day of maintenance does not establish economic continuity.
- The earlier fast semantic ranker missed both reserved major recoveries in its top two. Cheap requested-plan features have not earned the right to discard good candidates.

Evidence: `tape_transition_repair_20260924.md`, `value_tape_scout_20260923.md`, `continuation_execution_and_recovery.md`, and `m1_plan_fix_recommendation_20260923.md`.

## 1. First measure where recoverable value is being lost

Build a controlled opportunity audit on already exposed development worlds. Begin with eight distinct live worlds: four large untouched losses, the two known forecast-regression worlds, and two successful controls. Use recorded-only opponents as separate diagnostic cases. Declare the exact cases and candidate budgets before inspecting new branch outcomes.

At a real reveal checkpoint, evaluate three nested candidate sets:

1. Existing V9 alternatives and the incumbent.
2. Repaired alternatives, including routes rejected before their full-season value was evaluated.
3. A bounded, diverse expansion: additional compatible donor plans and feasible local production/service/delivery edits.

First reproduce the checkpoint and baseline. Then replay each candidate through the live V56 or original-m1 opponent from the same prefix, shop world, and engine state. Keep the future continuation controller identical across alternatives, including any later scheduled replanning. Cache common prefixes where exact state and RNG restoration are verified.

For each checkpoint, record:

- Best realized margin among tested candidates, including staying with the incumbent.
- Best realized margin within the original shortlist.
- The current evaluator's selected candidate and predicted gains.
- Predicted-negative candidates that improve realized results; predicted-positive candidates that lose.
- Successful output, delivery, cost, cohort, and terminal-state differences.

The difference between best tested realized margin and selected realized margin measures missed opportunity within this experiment. It is a hindsight diagnostic on a bounded candidate set, not a true optimum or a deployable score.

Interpretation:

| Finding | Primary next work |
|---|---|
| A good candidate was already shortlisted but rejected | Repair value/rival forecasts and admission calibration |
| Good candidates appear only after expanding retrieval | Improve candidate generation and search diversity |
| Donor transitions fail but local edits work | Invest in the plan-to-jobs adapter |
| These feasible changes still do not recover losses | Change the action family or intervene at an earlier observed reveal |

Actual future shops and opponent private state may be used only by this diagnostic evaluator to produce labels. The playing selector receives current public information and own memory. Whole worlds used here become development data and cannot be called fresh qualification later.

## 2. Search over edits to a persistent production plan

Treat donor tapes as proposals for dated decisions. Candidate edits should include:

- Add zero, two, or four strawberry plots on available or deliberately released tiles.
- Adjust sheep investment in small increments when the revealed demand and remaining yield dates support it.
- Reallocate fertilizer using each cohort's remaining unboosted output.
- Change care or harvest visits for specified animal cohorts.
- Reschedule deliveries and remove a worker only when the remaining jobs fit.
- Retire an explicitly selected cohort and assign its tile/resources to a replacement plan.

Each proposal must include purchases, resource reservations, service, harvest, delivery, replacement cycles, and the state left after the next reveal. Choose coherent bundles under a common tile, labor, feed, fertilizer, cash, and storage budget. Independent best-per-product choices can spend the same resources twice.

Use bounded beam search: retain several distinct feasible plans after each edit, with native/no-change always present. Restrict the first implementation to a small fixed set of operators and one or two edits per candidate. More complex combinations come after this interface works.

Compile against our actual cohorts and worker positions. Use cohort species, maturity, held output, care state, location and expected remaining yield in matching. A cheap assignment of donor intentions to our assets can propose placements; full engine projection must verify that they can be executed together.

The existing scheduler reschedules supplied feasible actions. New establishment and resource-reservation jobs require an adapter. Earlier compiler failures also mean the candidate needs an executable productive continuation, including crop replacements, after the three-day window. Once a farm changes, blindly resuming an incompatible old tape is not a recovery strategy.

### Preserve useful cohorts; price deliberate retirement

The current hard guard preserves every starting cohort that native keeps to the next reveal. This conflates accidental destruction with an intentional replacement investment. Keep an explicit distinction:

- Unplanned loss is an execution failure.
- Planned retirement is a priced action, evaluated using remaining sale opportunities, service costs saved, replacement costs, and the replacement's output timing.

Audit retirement counterfactuals offline before relaxing any live protection rule. Increasing switch frequency is not itself the objective.

## 3. Model a rival that can respond

Reuse `agents/adaptive_market_order.py::FlowModel` to infer recent rival net sales from public market changes and our own trades. Preserve its ambiguity flags. Combine that history with visible animal/crop ages, held yield, service history, and worker positions.

Maintain several plausible rival inventories and behaviors, updating their weights as observations arrive. Candidate behaviors can represent frequent delivery, stock accumulation, reduced servicing when output is cheap, and demand-responsive investment. Respect physical output, storage, cash, and labor constraints; a modeled sales trajectory should be attainable under its assumed behavior.

The immediate staged implementation is:

1. Reweight existing donor trajectories by observed delivery timing and quantities.
2. Constrain projected supply using current cohorts and feasible future service.
3. Add a few responsive sale/service/investment behaviors in response to the candidate-induced market path.

Evaluate own receipts, rival receipts, own costs, rival costs, and candidate ranking separately. A reduction in average price error is insufficient if the model still selects harmful switches. Uncertainty should include volume, investment, timing, and behavior, rather than only delayed copies of one sales schedule.

Uncertainty-aware model ensembles and trajectory sampling are established model-based planning ideas; [PETS](https://proceedings.nips.cc/paper_files/paper/2018/hash/3de568f8597b94bda53149c7d7f5958c-Abstract.html) provides one relevant design precedent. Applying them here is a proposal, not a result established by that paper.

## 4. Move decisions to the useful reveal and preserve future options

Compare day-9 and day-12 decisions where known demand already supports a production change. This respects the user's requirement that a new shop reveal must supply the evidence. Also evaluate useful adjustments at later actual reveals, rather than restricting every experiment to days 12/15/18.

A three-day candidate should preserve a good next decision: usable cash, feed reserves, serviceable productive cohorts, productive replacement cycles, and enough worker/tile capacity. Candidate value must include the remaining farm and market position, not only revenue before the next reveal.

For bounded lookahead, enumerate the eight possibilities for the next shop, use the same branches for candidate and baseline, and allow replanning at that simulated reveal. Further futures remain uncertain. This addresses a current mismatch: forecasts resume native routing after the commitment, while the evaluated policy may call the value selector again.

Useful flexibility has an economic cost. Do not reserve land, idle workers, or cash solely because flexibility sounds desirable; evaluate whether it improves the conditional future choices.

## 5. Spend computation on decision quality

Use a hierarchy:

1. Millisecond semantic features generate and diversify candidates.
2. Exact three-day projections measure actual changes to output, costs, inventory, cohorts, and commitments.
3. A learned continuation-value model ranks those resulting states.
4. More expensive future and rival scenarios evaluate the best and most uncertain contenders.

Train the continuation model on realized branch outcomes from the opportunity audit, with labels kept separate from public observation features. Retain known large recoveries and hold out whole worlds, opponents and source families. Include exploration examples outside the old shortlist; otherwise the model only learns the existing search's biases.

Keep only a few finalists for full-season rollout. Allocate more compute when plausible candidates disagree or a large investment is irreversible, while preserving the existing deadline fallback. Investigate exact common-prefix reuse and batched numerical market calculations after profiling identifies worthwhile work.

The [value-equivalence principle](https://proceedings.neurips.cc/paper/2020/hash/3bb585ea00014b0e3ebe4c6dd165a358-Abstract.html) motivates modeling what matters to value-based planning. Here the practical criterion is whether the cheaper model retains good decisions and reduces realized selection regret. Reproducing the old evaluator's scores alone would preserve its errors.

Use language models offline for varied plan templates and failure analysis. Use code and the engine to label successful execution and measure returns.

## 6. Optimize and qualify for the actual competitive objective

Track win conversions and large-loss recovery alongside mean margin. Once outcome uncertainty is calibrated, test a state-dependent risk policy: protect likely wins and consider larger changes when the public-information forecast favors a loss. Do not condition playing behavior on a game's known eventual result, or make an inaccurate model more aggressive merely because the current cash balance is lower.

The next qualification should report:

- Candidate coverage: fraction of development opportunities found by the shortlist.
- Selection regret and false-positive/false-negative switch decisions.
- Fresh mean margin, wins gained/lost, sum of loss deficits, and worst-tail regressions.
- Executed production and deliveries, wages, feed, fertilizer, and own/rival cash effects.
- Decision time and remaining bank, with the actual competition runner before promotion.

Use live V56 and original m1 for responsive comparisons. Exact recordings supply reconstruction and diagnostic evidence; broken frozen-opponent continuations cannot establish competitive strength. Freeze a new policy and genuinely new worlds after development, preserve all outcomes, and report uncertainty by independent world.

## Recommended sequence

Start with the opportunity audit. Then prioritize the branch that its results identify, with production-plan edits and public-history rival forecasting as the two leading implementation tracks. Add earlier reveal decisions once those changes can be valued and executed. Distill the improved planner for speed after it demonstrates materially broader recovery.

The immediate deliverable should be a table of recoverable loss, missed profitable alternatives, and the reason each current decision failed. That would make the next implementation choice evidence-based and provide a useful common benchmark for the other agents working on this project.
