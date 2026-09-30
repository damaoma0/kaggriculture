# Tape opportunity audit — 24 September 2026

## Findings

The four large untouched losses all contain strong alternatives in the existing shortlist: +1,372, +9,839, +5,185 and +8,054 margin. Their gains persist with later R3 replanning. Additional donor retrieval did not improve the best cohort-preserving result in any of these eight cases. Prioritize admission and forecast quality on this evidence; it does not establish exhaustive tape coverage.

A concrete admission mismatch rejects a robust forecast margin gain because our own cash falls slightly. A post-hoc checkpoint ablation removes only that requirement for ordinary, fully evaluated alternatives while retaining cohort, downside and risk gates. It changes one of eight decisions, recovering +8,054; the other seven decisions remain identical, including the known bad +4,842-forecast/−2,530-realized switch. This is a small development ablation, not general qualification.

The largest missed recovery is conditional on later shops. Its original single scout predicted −6,949; completing all eight public futures still predicts −2,031. Supplying true future shops predicts +9,896 versus +9,839 realized. This establishes substantial hindsight headroom, not that switching was correct in expectation at D15. Fully evaluating the missed best branches did not admit any new one. More rollout samples alone did not fix these examples.

There is also residual model error: with true future shops, the known bad route 47 still predicts about +404 versus −2,530 realized, and is ranked above the profitable alternative (about +49 predicted versus +1,366 realized). Own simulation approximations and the nonresponsive rival model both remain possible causes.

## Recommended implementation order

1. Build a separate margin-based admission challenger with explicit cash-feasibility checks. Full simulation already charges spending; requiring higher final own cash can block a useful relative gain. Preserve the existing downside and execution gates initially.
2. Value contingent plans that can adjust at the next actual shop reveal. Preserve profitable options where their cost is justified. Use honest future-shop distributions; these results do not justify adding unrevealed shops to the playing selector or assuming every hindsight winner was an expected-value mistake.
3. Improve responsive opponent and own-continuation forecasts where fully evaluated candidates are still ranked incorrectly. The existing bad switch remains a required regression test.
4. Keep the unrecovered old random-06 world as a candidate-generation/earlier-reveal target: no tested alternative improved its native result. Add persistent production edits and explicit retirement operators as a separate action family.
5. Freeze the challenger and run genuinely new worlds against both live opponents. These eight selected development worlds cannot establish population gains or safety.

## What was tested

Completed: 133 full-game branches across 8 deliberately selected, previously exposed worlds. Seven worlds use live V56; one uses live original m1. These are development counterfactuals, not a random performance estimate or a qualified new policy.

Each branch reproduces the native prefix exactly, forces one candidate for three days at the specified reveal, then resumes native routing. The existing shortlist and repairs are supplemented by six additional donors, selected with known-shop distance under board mismatch caps 8/14/24, with bounded repairs where applicable. All candidate choices were frozen before new branch outcomes. No new planting or retirement operator is implemented in this stage.

“Cohort-preserving” means retaining all starting tomato, strawberry and melon crops and animals that native retains at the next reveal. It does not guarantee perfect execution, preservation forever, or profitable continuation. Wheat and carrot cohorts are not in this guard. All physical failures and economics are retained.

There are 25 later-replanning confirmation games in addition to the 133 initial full games.

## Realized opportunity with common native continuation

All gains below are changes in final own cash minus rival cash. Best alternatives are selected with hindsight from this bounded audit; they are not deployable decisions.

| World | Reveal | Native margin | Current selection gain | Best original shortlist gain | Best tested cohort-preserving gain | Best route |
|---|---:|---:|---:|---:|---:|---|
| random-24-v56 | D15 | -11,047 | +0 | +1,372 | +1,372 | 204 (original) |
| random-02-v56 | D15 | -9,979 | +0 | +9,839 | +9,839 | 93 (original) |
| random-00-v56 | D15 | -9,432 | +0 | +5,185 | +5,185 | 197 (original) |
| fresh-22-v56 | D15 | -8,908 | +0 | +8,054 | +8,054 | 496 (original) |
| random-06-v56 | D15 | -8,897 | +0 | +0 | +0 | None (original) |
| fresh-12-v56 | D12 | 1,692 | -2,530 | +1,366 | +1,366 | 377 (original) |
| random-11-v56 | D12 | -1,667 | +5,135 | +6,726 | +6,726 | 414 (original) |
| fresh-11-original_m1 | D18 | 0 | +1,016 | +0 | +1,016 | 422 (repair) |

There are 12 cohort-preserving branches with positive realized gains despite nonpositive forecast scores, including 12 gains of at least 500. These are correlated branches within eight selected worlds. A realized winner does not establish that its expected gain was positive using information available at the reveal.

38 branches lost at least one cohort that native retained at the next reveal. 6 of those still improved realized margin; this motivates explicit priced-retirement experiments, rather than treating accidental loss as a valid replacement plan.

## Check later replanning

The predeclared confirmation set is native, the current R3 choice, and the two highest-margin cohort-preserving branches in each world (deduplicated). R3 runs at remaining D12/D15/D18 checkpoints. Selection of these confirmation branches uses hindsight and supplies no independent qualification.

| World | Route | Final margin | Gain vs no forced switch with R3 later | Gain vs original native | Later choices |
|---|---|---:|---:|---:|---|
| random-24-v56 | `null` | -11,047 | +0 | +0 | `[null]` |
| random-24-v56 | `204` | -9,675 | +1,372 | +1,372 | `[null]` |
| random-24-v56 | `[337, [[4, 5, "SHEEP", 12]]]` | -10,375 | +672 | +672 | `[null]` |
| random-02-v56 | `null` | -9,979 | +0 | +0 | `[null]` |
| random-02-v56 | `93` | -140 | +9,839 | +9,839 | `[null]` |
| random-02-v56 | `11` | -2,926 | +7,053 | +7,053 | `[null]` |
| random-00-v56 | `null` | -9,432 | +0 | +0 | `[null]` |
| random-00-v56 | `197` | -4,247 | +5,185 | +5,185 | `[null]` |
| random-00-v56 | `104` | -7,331 | +2,101 | +2,101 | `[null]` |
| fresh-22-v56 | `null` | -8,908 | +0 | +0 | `[null]` |
| fresh-22-v56 | `496` | -854 | +8,054 | +8,054 | `[null]` |
| fresh-22-v56 | `213` | -1,095 | +7,813 | +7,813 | `[null]` |
| random-06-v56 | `null` | -8,897 | +0 | +0 | `[null]` |
| random-06-v56 | `256` | -8,897 | +0 | +0 | `[null]` |
| fresh-12-v56 | `null` | 1,692 | +0 | +0 | `[null, null]` |
| fresh-12-v56 | `181` | 1,692 | +0 | +0 | `[null, null]` |
| fresh-12-v56 | `47` | -838 | -2,530 | -2,530 | `[null, null]` |
| fresh-12-v56 | `377` | 3,058 | +1,366 | +1,366 | `[null, null]` |
| random-11-v56 | `null` | 763 | +0 | +2,430 | `[null, 289]` |
| random-11-v56 | `414` | 5,059 | +4,296 | +6,726 | `[null, null]` |
| random-11-v56 | `[582, [[6, 2, "SHEEP", 8]]]` | 3,468 | +2,705 | +5,135 | `[null, null]` |
| random-11-v56 | `413` | 4,956 | +4,193 | +6,623 | `[null, null]` |
| fresh-11-original_m1 | `null` | 0 | +0 | +0 | `[]` |
| fresh-11-original_m1 | `436` | 0 | +0 | +0 | `[]` |
| fresh-11-original_m1 | `[422, [[7, 4, "SHEEP", 8], [8, 2, "STRAWBERRY", 6]]]` | 1,016 | +1,016 | +1,016 | `[]` |

## Economics of the strongest alternatives

### random-02-v56: +9,839

Route `93`. Own cash changes +7,195; rival cash changes -2,644. Forecast margin change was -6949.0 over 1 scenario(s); risk score -6949.0.

| Product | Our sale receipts change | Rival sale receipts change | Our sold units change |
|---|---:|---:|---:|
| CARROT | +5,018 | -3,504 | +95 |
| EGG | -567 | +168 | -14 |
| FERTILIZER | -95 | -257 | +12 |
| MILK | -30 | +11 | -21 |
| STRAWBERRY | +884 | +1,541 | -39 |
| TOMATO | -2,797 | +0 | -38 |
| WHEAT | -1,219 | -125 | -45 |
| WOOL | +7,993 | -1,539 | +59 |

Our cost changes: `{"BUY_ANIMAL:SHEEP": 500, "BUY_PRODUCT:FERTILIZER": -315, "BUY_PRODUCT:WHEAT": 1448, "BUY_SEED:CARROT": 600, "BUY_SEED:TOMATO": -200, "BUY_SEED:WHEAT": -130, "HIRE": 89.0}`.
Rival cost changes: `{"BUY_PRODUCT:FERTILIZER": -524, "BUY_PRODUCT:WHEAT": -105, "BUY_SEED:CARROT": 20, "BUY_SEED:WHEAT": -20, "HIRE": -432.0}`.

### fresh-22-v56: +8,054

Route `496`. Own cash changes -571; rival cash changes -8,625. Forecast margin change was 6193.25 over 8 scenario(s); risk score 5231.502705033698.

| Product | Our sale receipts change | Rival sale receipts change | Our sold units change |
|---|---:|---:|---:|
| CARROT | -7,767 | +3,168 | -151 |
| EGG | -16 | +24 | +0 |
| FERTILIZER | -271 | +256 | -18 |
| MELON | +448 | +0 | +6 |
| MILK | -1,304 | -3,343 | +18 |
| STRAWBERRY | -1,401 | -6,841 | +38 |
| TOMATO | +2,637 | +0 | +41 |
| WHEAT | +6,328 | -1,610 | +168 |
| WOOL | -2 | -14 | -4 |

Our cost changes: `{"BUY_PRODUCT:FERTILIZER": 133, "BUY_PRODUCT:WHEAT": -479, "BUY_SEED:CARROT": -920, "BUY_SEED:TOMATO": 100, "BUY_SEED:WHEAT": 300, "HIRE": 89.0}`.
Rival cost changes: `{"BUY_PRODUCT:FERTILIZER": 145, "BUY_SEED:CARROT": 220, "BUY_SEED:WHEAT": -100}`.

### random-11-v56: +6,726

Route `414`. Own cash changes +4,449; rival cash changes -2,277. Forecast margin change was 3278.75 over 8 scenario(s); risk score 737.8689796893282.

| Product | Our sale receipts change | Rival sale receipts change | Our sold units change |
|---|---:|---:|---:|
| CARROT | -3,645 | +292 | -67 |
| EGG | -288 | +22 | -7 |
| FERTILIZER | +434 | -148 | +24 |
| MELON | +16 | +0 | +0 |
| MILK | +273 | -309 | +15 |
| STRAWBERRY | +8,590 | -4,182 | +69 |
| TOMATO | -1,006 | +1,794 | -24 |
| WHEAT | +8 | +184 | -1 |
| WOOL | +16 | +16 | +36 |

Our cost changes: `{"BUY_PRODUCT:FERTILIZER": -1, "BUY_SEED:CARROT": -340, "BUY_SEED:STRAWBERRY": 600, "BUY_SEED:TOMATO": -200, "BUY_SEED:WHEAT": -110}`.
Rival cost changes: `{"BUY_PRODUCT:FERTILIZER": -54}`.

### random-00-v56: +5,185

Route `197`. Own cash changes +4,581; rival cash changes -604. Forecast margin change was 847.625 over 8 scenario(s); risk score -609.4177013625065.

| Product | Our sale receipts change | Rival sale receipts change | Our sold units change |
|---|---:|---:|---:|
| CARROT | +54 | -6 | +2 |
| EGG | -1 | -7 | +0 |
| FERTILIZER | -97 | +108 | -7 |
| MILK | -217 | -52 | +0 |
| STRAWBERRY | -27 | +20 | +0 |
| TOMATO | +1,168 | +0 | +16 |
| WHEAT | +253 | -245 | +12 |
| WOOL | +3,224 | -393 | +18 |

Our cost changes: `{"BUY_PRODUCT:FERTILIZER": 1, "BUY_PRODUCT:WHEAT": -404, "BUY_SEED:STRAWBERRY": 100, "BUY_SEED:TOMATO": -50, "BUY_SEED:WHEAT": 40, "HIRE": 89.0}`.
Rival cost changes: `{"BUY_PRODUCT:FERTILIZER": 29}`.

## Future-shop attribution

A separate oracle diagnostic gives the forecasting model the actual future shops, keeps the modeled rival, and evaluates three donor trajectories. This cannot be used online. Residual errors can reflect rival behavior, own rollout approximations, and exogenous events; this test does not isolate the rival model alone.

| World | Candidate | Actual gain | Original forecast | Full 8 public scenarios | Forecast with true future shops |
|---|---|---:|---:|---:|---:|
| random-24-v56 | c04 | +1,372 | -3,718 | -5,976 | -420 |
| random-02-v56 | c03 | +9,839 | -6,949 | -2,031 | +9,896 |
| random-00-v56 | c03 | +5,185 | +848 | +848 | +4,671 |
| fresh-22-v56 | c01 | +8,054 | +6,193 | +6,193 | +7,584 |
| fresh-12-v56 | c04 | -2,530 | +4,842 | +4,842 | +404 |
| fresh-12-v56 | c06 | +1,366 | -3,321 | +663 | +49 |
| random-11-v56 | c01 | +6,726 | +3,279 | +3,279 | +8,696 |
| random-11-v56 | c07 | +5,135 | +3,431 | +3,431 | +3,361 |
| fresh-11-original_m1 | c07 | +1,016 | +1,792 | +1,792 | +1,505 |

## Verification and limits

- Every completed branch checks both cash ledgers and the exact two-seat action prefix. Native-control action hashes and final cash match the earlier full games.
- The official engine runs both policies live; no frozen-opponent continuation is counted here.
- Input and candidate hashes were saved before branch execution. Frozen policy payload files are rechecked in every worker.
- Local execution is diagnostic. The audit does not enforce the competition time bank; unlimited-budget later R3 confirmation is not a speed qualification.
- Native-continuation branch time averages 4.96 seconds including local setup; this is full-game labeling time, not playing-selector latency.
- Raw audit, candidates, traces, action streams, confirmations and attribution are under `results/fresh/tape_opportunity_20260924_01a0/`.
- Native m1, V9, and the frozen R3 policy were not changed. No submission was made.
