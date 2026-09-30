# Optional fertilizer net-flow prototype

`forecast_fertilizer_net` is **off by default**. Only the recovery worktree is edited; frozen V8/V12 candidates are unchanged. No engine, training, export or game ran. Enablement for a future separately frozen policy is `policy.forecast_fertilizer_net = true`; the new helper must be included in its source closure.

Files: `scripts/semantic_strategy_fertilizer_net_20260928.py`, optional hooks in `scripts/semantic_strategy_policy_20260928.py` and `scripts/semantic_strategy_blocks_20260928.py`, `tests/test_semantic_fertilizer_net_20260928.py`, and `scripts/audit_semantic_fertilizer_net_20260928.py`.

## Accounting and timing

The engine consumes one fertilizer per FERTILIZE and sets the effect through application day+2. Annual watering gains one extra unit under that effect. Ongoing output available at dawn D uses watering/fertilization during D−1. The new calendar follows these rules while retaining the existing policy output dates and amounts:

| New crop, ordinary release | Existing modeled output | Expected fertilizer input |
|---|---|---|
| Wheat, age3 | 5 | 1 at age2 |
| Carrot, age3 | 4 | 1 at age2 |
| Melon, age10 | 6 | 0; normal watering suffices |
| Tomato, outputs ages8–11 | 1.65 per event | 0.65 at ages7 and10 |
| Strawberry, outputs ages10/12/14/16 | 1.65 per event | 0.65 at ages9 and13 |

The ongoing calendar represents a model-derived mixture:65% of cohorts receive full fertilizer service and35% none. Each application covers as many successive service dates as the three-day effect permits. It is an expectation, not fractional game actions, and was not fitted to the eight development cases. Fresh public yield/watering and an observed active-effect expiry credit already-covered annual output. Known active effects also credit ongoing service. Expired/released annual output has no new input charge; observed deferred annual harvest uses the inherited next-day target. Public details are matched by crop/birth and count. Stale yields and details dated in the future are ignored; a replacement with a new birth receives no predecessor credit.

Both farms' internal use is removed from expected fertilizer market supply. Own fertilizer in shed/hands is credited once, analogously to the existing wheat feed accounting; rival private inventory is not invented. The history producer explicitly distinguishes gross observed harvest from genuine signed market net flow. A gross harvest blend is debited once in full. For a genuine net-flow blend with weight w, only the remaining model fraction (1−w) receives an input debit, and negative fertilizer net purchases are retained. Unknown flow semantics raise an error only when the option is enabled. The returned rival fertilizer calendar and the existing-own calendar in price-impact terms use the same signed net meaning.

Marginal crop cost uses the same calendar when enabled. The legacy tomato loop charged0.4 at service ages7–11 (including a fifth service with no modeled production), totaling2.0; the shared calendar uses1.3. Strawberry changes1.6→1.3; wheat/carrot0→1; melon stays0. Thus a changed crop ranking is an intended accounting consequence, not a new quantity target rule. Animal counts, retirement intentions and hiring policy are unchanged by the implementation.

## Verification and static effects

All14 pure tests pass. They cover annual input requirements, D−1 service timing, shared effect windows, fresh yield/active-effect credit, delayed annual readiness, no future/stale replacement credit, own/rival/private-stock identities, gross versus signed net history, ambiguity rejection, and scalar marginal/calendar consistency. A dedicated replacement regression carries an observed wheat effect through day5, replaces that cohort with wheat born day3, and confirms the replacement still requires its own day5 application. A surviving tomato cohort retains its valid observed effect; stale yield/watering values are ignored. `_advance` can retain the original allowlisted details because matching requires both crop and birth; its newly created cohorts have a new birth and cannot inherit those credits.

Across192 saved V8 dawns, the disabled code returns **exactly the same public states and full proposals (including every forecast day and diagnostics) as frozen V8**. The reconstructed disabled current quantities also match all192 recorded proposals. Hourly observer memory was not saved; earlier successful public harvest totals approximate it, and previously issued retirement identities are checked against the current farm. Matching choices does not claim exact reconstruction of every original forecast value.

Enabled:15 current crop-allocation changes and13 additional forecast-only changes. There are no current changes to animals, retirement counts, land or hands in this static sample. Most current changes substitute tomato for a marginal wheat/carrot slot; late cases substitute wheat for carrot. Every forecast day was compared, since suffix quantities can influence spatial compilation. Fourteen selected paired compilations confirm five changed-current-quantity cases also change current tiles. Nine forecast-only cases retain current tiles but change later plans. Those compiles share an empty historical prefix plus actual current retirement intent; they are not exact replays of the original internal tile memory.

| Case | Current crop-allocation days changed | Additional forecast-only days | Fertilizer quote MAE: off→on |
|---|---:|---:|---:|
| 00 | 3 | 1 | 26.88→18.06 |
| 01 | 0 | 1 | 15.94→8.71 |
| 02 | 1 | 2 | 24.24→15.00 |
| 03 | 3 | 4 | 24.59→14.35 |
| 04 | 6 | 0 | 23.00→11.35 |
| 05 | 0 | 4 | 25.94→15.12 |
| 06 | 1 | 0 | 24.82→16.29 |
| 07 | 1 | 1 | 20.76→11.65 |

D12 forecasts across136 subsequent dawn quotes improve fertilizer MAE23.27→13.82. This is development calibration, not profit evidence. The model still predicts D29 fertilizer price1 in every case, versus actual16–39: future rotations and acquisitions are not represented by today's crop cohorts, while current animals continue producing in the model. This correction cannot fix that asymmetry alone.

Static proposal timing on this machine: off mean0.0211s, maximum0.1021s; on mean0.0457s, maximum0.1588s. The complete three-arm192-state audit took18.0s. These are local pure-policy measurements, not an engine timing qualification or a competition overage guarantee.

## Limits and next decision

The calendar assumes required watering, collection, delivery and financing occur. Conditional observed active fertilizer does not revise the inherited1.65 ongoing output expectation. Stale annual details revert to modeled history, which can assume ideal past applications that were not observed. It does not introduce future recorded cohorts, predicted replacement cycles, an exact sale model, or a new absolute-value admission rule.

Existing own/rival fertilizer flow terms are now net, but marginal additions still perturb market paths through their positive output only. Their new fertilizer consumption is charged at the baseline quote without accumulating a negative fertilizer input into the competitive price externality. This applies to both `cohort_value` and `bundle_value`; the active block policy uses unit bids, so the bundle limitation is currently dormant there. The existing feed approximation has a similar limit. This is not complete net-flow treatment of added-cohort market impacts.

The existing `_advance` suffix-cash model still values gross output at the unchanged current-dawn prices and does not debit fertilizer consumption. That separate approximation is explicitly retained. Current-day admission starts from observed cash and benefits from the corrected unit bids; future admission still uses the approximate inherited cash balance. The13 forecast-only differences therefore arise from bids and subsequently changed cohorts, not a correction to suffix cash pricing. The option corrects market inventory forecasts and marginal crop input valuation; it is not a full cash-flow rewrite.

Independent focused review by the extraction agent found no blocker in D−1 timing, inclusive effect expiry, own private-stock credit or signed net-versus-gross history treatment. Its identified forecast limitations are recorded above. Runtime/model sources remain unchanged by the review; the extra replacement regression and this report clarification are the only follow-up changes.

The change is measurably active, so a prospective paired development experiment can test crop mix, feed purchases, product delivery, prices and runtime. Better forecast error does not establish better game performance. No game enablement or freeze occurred in this subtask.
