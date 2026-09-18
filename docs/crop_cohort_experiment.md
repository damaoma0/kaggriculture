# Existing-land crop cohorts: results

**Decision: retain the corrected baseline; do not upload these variants.** Seven crop policies were tested in 328 distinct benchmark games. The best is a selective native-route carrot substitution: +60.2 average winning margin on the natural holdout, but -14.1 own cash and regressions against two of five opponents. This is a useful research candidate, not a sufficiently consistent improvement to promote.

## Question and control

Can we borrow the leaders' gradual crop changes and staggered cycles while reusing V45's existing workforce?

The control is `agents/v45_event_opening_fixed.py`, SHA-256 `e512d755d45fb3cee6602493a9af799131fb3b2dd3707f927e744e4b7a6cd7a3`. It includes the corrected safe wheat opening and forecast entry point. It is not the exact currently uploaded agent. Native fourth-quadrant eligibility remains available in both control and experimental policies.

Two explicitly requested GPT-5.6 tasks handle the benchmark script, native timeline audit, and run-log summaries. Strategy selection and review remain in the main task.

## First mechanism: strawberry replacement using worker return time

Four exploratory variants replace up to two strawberry plots with tomatoes from day 18, or up to four with carrots from day 20. Each crop has a batch and a one-new-plot-per-day version. Plot caps are maxima, not guaranteed commitments. Planting requires an already hired hand that can complete the detour after all remaining productive native tasks. Ordinary midnight cargo deposits are allowed; the last day requires explicit delivery. Existing native visits provide crop care where possible. There are no new HIRE or BUY_LAND orders from this overlay.

This is a deliberately simple feasibility experiment. It does not yet reserve a complete future service schedule before planting, optimize fertilizer, or solve joint worker routing. Crop failures and foregone strawberry production count against the policy, rather than being excluded from performance.

Smoke versions using only PASS suffixes, then explicit round-trip delivery, found no feasible commitments in their diagnostic world. Allowing midnight delivery produced commitments but exposed missing later care and harvest windows. Carrot harvest priority was corrected before the retained discovery panel: on its last lifespan day a one-action native visit harvests existing yield instead of watering and allowing the crop to expire.

The retained discovery panel freezes all four candidate sources and runs 80 games: baseline plus four candidates, four independent uniformly drawn hidden shop sequences (157010–157013), two seats, and two active public opponents (V45 and Two Coins). This is a diagnostic panel, not evidence of leaderboard superiority. Both seats are averaged within each seed/opponent; four seeds remain four worlds.

## Second mechanism: native wheat planting visits

The native timeline audit identifies existing wheat replant commands as potential insertion points. Changing crop at an existing planting visit avoids extra planting travel. Carrots have a shorter lifespan, so an early harvest visit must also be available; simply replacing the seed name is unsafe.

The second prototype changes two or four audited wheat cells to carrots when a Pet Cafe or Farmers Market has appeared. It harvests on an existing age-three visit, accepts the smaller yield if that visit has only one action, and waits for the next original planting command. Movement, direct hire/land requests, and inherited market orders are preserved. Extra carrot sales begin only after a confirmed swap, but can include baseline carrots as well as new output; this is a combined production-and-carrot-sale policy, not a perfectly isolated planting intervention. Seed reserves can leave surplus at the end. Contract fallbacks are counted and disqualify a result from promotion.

Two official-engine smoke games checked actual carrot planting, harvesting, sales, and midnight delivery, with zero contract errors or expired unharvested carrot yield. Their scores were unfavorable on the single smoke seed; these establish execution only.

The comparison panel has eight seeds chosen before observing results to cover all eight first-shop types: 158000, 158003, 158005, 158006, 158008, 158011, 158015, and 158024. Both seats and V45/Two Coins give 96 baseline-plus-candidate games. This is stratified shop coverage, not a naturally weighted ladder sample.

An additional economic variant uses the same four-cell routes but checks each replacement against the opportunity cost of wheat: two carrot units versus 3.5 displaced wheat units plus the extra 20-cost seed. It projects three days of currently visible carrot demand, allows four units of supply from every visible carrot plant that can mature by then, and includes an eight-unit own-sale price impact. Future unrevealed shops are not used. It stops seed replenishment on day 24 to limit final surplus. This conservative approximation is a separately tested hypothesis; it is not an optimal forecast or policy.

Independent GPT-5.6 review confirmed the demand/seed arithmetic and identified limitations: visible cohort carrots can be counted in both the four-unit supply allowance and the eight-unit sale impact; the carrot quote is projected while the wheat quote is current; two/3.5 units are route assumptions, not engine guarantees; unused reserve seeds are not explicitly charged in the gate. The fixed three-day horizon can also differ from the exact native harvest hour. These are heuristic choices, not a proven profitability bound. The candidate is frozen before holdout outcomes.

Natural-RNG holdout: six new seeds 159000–159005, both seats, and five active public opponents (V45, Two Coins, V44, Farming V5, Pasture 2700). Baseline and value-gated candidate give 120 games. Natural shop sequences may diverge after a policy changes farm-dependent weed RNG; those games assess full deployed behavior rather than a pure same-shop intervention.

## Promotion rule

A candidate must execute correctly and improve paired margin across independent shop sequences and both discovery opponents before promotion is considered. A discovery winner then needs new-seed comparisons against the broader public opponent panel and natural-RNG games. A small sample average, a favorable shop prefix, or beating an unchanged baseline in one seed is insufficient. No upload is justified by diagnostic results alone.

## Validation

The runner uses Kaggle's actual last-callable source loader for every participant. Each game requires 719 dictionary actions per player, 720 states, both terminal statuses DONE, and exact cash-ledger reconciliation. It records candidate and opponent hashes, actual shop sequence, crop counts, daily hire spending, runtime, and candidate telemetry. Exceptions are recorded as failures. Agent hashes are checked again when each worker loads a game.

The native audit has two additional games, 2,876 checked actions. Exhausted strawberry plots in those games had usable planting windows only on day 28, too late to yield; earlier replacement therefore necessarily sacrifices remaining strawberry value.

## Completed return-time experiment

All 80 games passed loader, action-count, terminal, and cash reconciliation checks. Every candidate reduced paired winning margin in every tested seed/opponent cluster. Average changes below combine both opponents and average seat replicates first.

| Variant | Own cash change | Winning-margin change |
|---|---:|---:|
| Carrots, batch | -558.25 | -726.88 |
| Carrots, staggered | -495.50 | -618.13 |
| Tomatoes, batch | -493.63 | -607.75 |
| Tomatoes, staggered | -696.88 | -799.13 |

These are incremental changes against the corrected baseline, not raw scores. All four candidates still beat Two Coins in all eight actual games each, but the unchanged baseline did better. Against V45 the candidates won 2/8, 4/8, 0/8, and 0/8 games respectively. Beating a weaker opponent alone would have selected a regression.

The implementation is rejected. Its harvest gains were too small and came with lost output elsewhere. No land-spending difference occurred; some native hire spending changed downstream even though the overlay never directly adds hires. The prototype also prebuys seeds before proving a feasible commitment, and does not reserve a complete future care schedule. Its direct-visit seed reservation can overcommit when combined with a new route; this is a static-review limitation, not an observed planting failure in this panel. `missing_plants` counts both natural expiry and missed-care loss and must not be described as a pure death count. Results reject this implementation, not the general concept of jointly planned crop cohorts and labor reuse.

Full result tables: `results/fresh/crop_cohorts/discovery/analysis.md` and `analysis.json`. Exact policy hashes and shop schedules are in the panel manifest and per-game records.

## Final native-route results

The fixed two-cell and four-cell substitutions both lose overall despite correct execution. Across the eight first-shop cases and both opponents, two cells change own cash by -338.2 and margin by -250.4; four cells change cash by -789.9 and margin by -688.6. There were zero contract errors or expired unharvested carrot units.

The economic gate improves on those fixed rules. In controlled shop coverage it triggers only in seed 158003: six confirmed planting cycles and 13 harvested units per game. It raises mean margin by +172.0 against V45 and +83.5 against Two Coins, averaging over all eight seeds, and matches the baseline in the other seven seeds. Its mean own-cash change across both opponents is -4.6. One favorable shop sequence is insufficient evidence for deployment.

### Natural-RNG holdout: best candidate versus corrected baseline

Six new seeds, both seats, five public agents; 120 games comprising 60 matched comparisons.

| Opponent | Own cash change | Winning-margin change |
|---|---:|---:|
| V45 | +48.5 | +130.8 |
| V44 | +48.5 | +130.8 |
| Farming V5 | +35.8 | +116.5 |
| Two Coins | -93.8 | -19.0 |
| Pasture 2700 | -109.7 | -58.2 |
| **Average** | **-14.1** | **+60.2** |

The candidate improves 20 paired margins, matches 30, and worsens 10. It wins 57/60 actual matches versus the baseline's 53/60; these wins are against the tested public agents, not leaderboard matches. Thirty candidate games trigger substitutions. All 60 pairs happened to retain identical realized shops, so observed shop-sequence divergence does not explain the regressions here. V44 and V45 behaved identically in this holdout; five public files are not five independent opponent families.

Pooling opponents and seats within each of the six seeds gives margin changes +313.4, 0, 0, 0, +17.0, +30.8. Exact bootstrap resampling of these six seed clusters yields an exploratory 95% percentile interval of approximately +2.8 to +162.4. This describes the small tested sample and fixed opponent mixture; it does not establish a reliable leaderboard gain or remove the opponent-specific regressions.

### What the remaining loss teaches us

In the worst paired-margin case (159000 versus Pasture 2700), own cash falls 337 and margin falls 160. The candidate sells seven additional carrots but total carrot revenue rises only 145; wheat revenue falls 502 and extra carrot seeds cost 140. Other ledger changes reconcile the remaining difference. The new output's quoted price is therefore an inadequate measure of its total value. Changes in sale timing and market prices also affect the existing crop portfolio. This ledger does not separately identify those two causes.

The next useful refinement is to value the **whole remaining farm's revenue**, including the effect of extra supply on our existing crops and the opponent's crops, while keeping baseline carrot sale timing isolated from the new lots. It is more promising than adding more unconditional crop swaps or treating currently idle commands as free seasonal labor.

## Final checks and artifacts

- 328 distinct benchmark games; the 360 panel records share 32 identical baseline cells between native and value panels. Smoke/debug runs are excluded from this count.
- Every retained game passes 719 dictionary actions per seat, terminal DONE, source-hash checks and exact cash-ledger reconciliation.
- Native and gated variants have zero observed contract errors and expired unharvested carrot yield in retained panels.
- The standalone value candidate matches its named-module entry point on all 719 actions in a live game with actual substitutions. Export SHA-256: `a08d4b396b4a190bf142a2e161f38c808e7f92d622911b3df6fc5103575c4f49`.
- Maximum measured candidate call in the natural holdout: 0.383 seconds.
- Main machine-readable artifact: `results/fresh/crop_cohorts/final_summary.json`. Per-panel `analysis.md`/`analysis.json`, manifests and game ledgers remain alongside it.
- Main research sources: `agents/crop_cohort_overlay.py`, `agents/native_crop_swap_overlay.py`, `agents/native_crop_value_gate.py`; builders and benchmark/audit/report scripts are in `scripts/`.
- The two requested GPT-5.6 tasks wrote the benchmark runner, native-route prototype and audit, and independent summaries/reviews. The main task reviewed integration, authored the first overlay and economic gate, ran comparisons, and made the promotion decision.

No selected baseline, archived submission, or Kaggle submission was changed.
