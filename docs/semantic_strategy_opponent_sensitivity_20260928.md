# Does the semantic policy respond to the opponent and market?

Yes, but mostly when admitting a crowded or underfunded plan. The three-day production budget itself depends on visible shops and our own cohorts, not the opponent or market. On **290 of 384 saved V5/V7 dawns (75.5%)**, every age-eligible requested addition is admitted, so even adversarial value rankings leave today's decisions unchanged. On the remaining 94 dawns, at least one ranking changes the admitted counts. There is no positive-value requirement: ranking a proposed investment last does not reject it if money and space remain.

This is a read-only sensitivity audit of eight V5 and eight V7 development traces, days 6–29. The same cases recur across arms, so 384 dawns are not 384 independent worlds. No game, qualification observation or policy edit was used.

## What was reproduced exactly

All **384/384 full proposals** reproduce from the saved actual observation, recorded requested target, recorded cohort values, and reconstructed still-present retirement commitments. Recorded values are rounded to three decimals; despite that, the complete proposal dictionaries match, including hands and estimated costs. The three-day requested targets also reconstruct **384/384** by carrying block schedules and observed successful births forward from earlier own-farm dawns.

The original hourly `public_history` was not saved. It cannot be reconstructed exactly from dawns or daily output totals: the observer only detects consecutive hourly transitions and omits the H23→H0 harvest transition. Therefore this audit does **not** claim full original `propose()` or policy-memory parity. Recomputing with an explicitly empty history produces the original complete proposal on 379/384 dawns; five differ. The root wrapper now records the relevant input memory for future candidates, without changing frozen V8.

## Synthetic changes to today's decisions

The following probes keep our actual farm, cash, private stocks and visible shops fixed. Forecast-based rows compare against their own empty-history baseline. Inventory stress sets each product's inventory to `10000 ± 2T`, where `T` is its engine price-curve scale. These are deliberately large mechanism probes, not feasible game continuations or profit estimates.

| Synthetic probe | Dawns with changed forecast values | Dawns with changed actual proposal |
| --- | ---: | ---: |
| Remove rival crop/animal cohorts | 368 | 10 |
| Double rival cohort counts | 368 | 30 |
| Add 20 mature rival sheep | 368 | 27 |
| Add 20 mature rival strawberry plants | 219 | 8 |
| Set rival animal held yield/care bonus to zero or full | 0 | 0 |
| Market inventory glut; keep current quotes fixed | 368 | 79 |
| Market inventory scarcity; keep current quotes fixed | 368 | 34 |
| Observed rival harvest history explicitly zero | 368 | 6 |
| Observed rival harvest history 50 units/product/day | 368 | 35 |
| Inventory glut and consistent current quotes | 368 | 141 |
| Inventory scarcity and consistent current quotes | 368 | 34 |

The 16 D29 rows have no future productive establishment and generally no value response. Among the rows above, plant counts and sometimes animal additions change. **No probe changes retirement intentions or land targets.** Only consistent glut prices change hands, on eight dawns. Rival-only probes change no hands in this sample.

A separate exact admission probe keeps the recorded cohort values fixed while changing only current quoted prices. Halving quotes changes 40/384 proposals; setting all quotes to the floor changes 80; doubling them changes none. Current quotes enter the same-day sale-income credit, which changes available capital. These quote-only scenarios intentionally do not maintain the normal price/inventory identity; they isolate that admission dependency.

For example, V5 live-00 D7 under the synthetic extra-sheep rival changes today's accepted plan from three wheat, three cows and one goose to four wheat and three cows. V5 live-00 D16 changes four carrot/three tomato/seven wheat to four carrot/one tomato/nine wheat. The three-day requested budget remains unchanged: the admission ranking decides which requested work gets space today. This does not establish that either changed plan is better.

| Arm | Saved dawns | All eligible additions admitted | Ranking-sensitive dawns | Empty-history differences |
| --- | ---: | ---: | ---: | ---: |
| V5 | 192 | 147 | 45 | 2 |
| V7 | 192 | 143 | 49 | 3 |

## Where the information reaches decisions

- `_make_block` uses cumulative visible-shop demand and our own species counts. D6 retrieves an opening example using shops, our counts/ages and land. Neither path uses rival cohorts, current prices, inventory or public action history. The block fixes day shares, nominal hands and land.
- `_choice` forecasts market inventory using rival crop/animal births and counts. Its observed-history blend consumes inferred rival **harvests** from the prior three days. Logged feed, care, establishments and combined market flow do not directly enter this block decision.
- Rival current animal held yield and pending care bonus are collected by `public_state`, but `forecast_market` uses the anonymous birth/count output calendar instead. The two animal-detail probes therefore change nothing.
- `_proposal` sorts requested additions by cohort value per modeled duration and admits them while capital and capacity remain. There is no value floor, no new alternative species outside the block budget, and no opponent-sensitive retirement rule. `economics_weight=0` does not disable this admission ranking; that setting belongs to the daily-nearest selector, not block-budget generation.
- Current prices affect financing through expected same-day receipts. In particular, price changes can suppress more additions than rival-value changes when the farm depends on selling today's output.

Twelve recorded dawns admit additions with nonpositive logged cohort value: 11 cows and one strawberry. Five cows were already held as unplaced stock, so continuing their placement preserves a purchased commitment. Six cows and the strawberry were not yet held. This illustrates the absence of a value floor; it does not validate the value estimate or prove a realized loss.

## Useful interface for a further admission policy

The narrow insertion point is after `_choice` forms today's outstanding semantic target and computes forecast values, but before `_proposal` ranks admissions. A separate optional gate could cap **unbought** additions using marginal joint supply, rival delivery timing and uncertainty while preserving prepaid animals/seeds and committed retirements. It must return both an admitted count and an explicit deferral/cancellation reason. The block completion ledger otherwise retries a rejected request every day, so same-block deferral and budget cancellation need distinct semantics.

Changing only `cohort_values` cannot make a fully funded plan respond: a value-aware gate or an opponent-conditioned block budget is required. A gate should not turn a weak cow-buy estimate into automatic retirement of existing cows. Its forecast and eventual gameplay checks must remain separate, since the present output calendar omits current held animal yield and exact delivery timing.

The new optional reveal model has an independent 31-check static/pure-feature PASS. Its baseline matches the frozen V8 model by hash and dictionary; only SHEEP/STRAWBERRY coefficient columns are refitted, while schedules, caps, hands, land and opening examples remain unchanged. The feature indexes the shop revealed in the current block; appended future entries cannot change that index, modeled unknown reveals use a uniform expectation, and D27 has no new-reveal feature. This adds current reveal identity, **not opponent or market sensitivity**. Selection is exploratory development evidence, not a fresh performance test.

Artifacts:

- `scripts/audit_semantic_strategy_sensitivity_20260928.py`
- `results/fresh/semantic_strategy_20260928/policy_sensitivity_v5_v7_saved_dawns.json` — every source hash, exact replay result, per-day count change, and limitation.
- `scripts/audit_semantic_reveal_features_20260928.py`
- `results/fresh/semantic_strategy_20260928/reveal_feature_independent_audit.json` — model/source hashes and all 31 independent checks.
