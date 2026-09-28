# V12 live01: retry mechanism and natural-world accounting

The completed V12 run improves competitive margin from +3,165 to +6,591 (+3,426), while own cash falls 80,218 to 79,125 (-1,093) and rival cash falls 77,053 to 72,534 (-4,519). This is a natural-world result, not an isolated estimate of retry profit: the shared-RNG shops diverge at D15 (SMOOTHIE_SHOP becomes PET_CAFE) and D21 (BAKERY becomes ICE_CREAM_SHOP). Both runs are technically valid; the complete V12 development panel finishes 5/8 wins and does not pass its 6/8 gate.

## What the actual retry does

The first changed action is D8 H3, step 195, farmer/unit 0 at shed tile 44. Both streams previously picked up four WHEAT at H2. V12 picks up one more at H3 instead of feeding immediately; observed carried wheat changes 4 to 5 while one wheat was available in the shed. This is the only additional consecutive wheat pickup found in the D6–10 saved hourly observations. Internal retry-audit records were not retained by this harness, so admission reasons or unseen retries are not invented from action requests.

The farmer completes the same route, adding the previously skipped feed on sheep tile 26, born D6, at H18. His final water moves from H19 to H21; two trailing PASS commands pay for the extra pickup and restored feed. D8 physical totals differ only by +1 PICKUP, +1 FEED and -2 PASS. There is no change in harvest or collection that day. Cash at D9 dawn is identical: wheat sales revenue and wheat purchase spending each fall by 132, and four fewer wheat are sold.

At D9 dawn both farms retain exactly the same animal cohorts. Sheep 26 changes consecutive-unfed 1 to 0 and pending care bonus 2 to 3. This restores service and one care bonus; it does **not** save an animal from an observed D8 escape. The V8 sheep is fed again on D9 and also survives. By D10 dawn, V12 additionally has two sheep and one goose placed on D9; these are earlier successful placements rather than recovered dead cohorts. Later differences include new daily routing and semantic choices, so the complete season cannot be attributed to the one feed.

Before trading under the new D15 shop, own cash is +45 and rival cash -182 versus V8, a margin difference of +227. This already includes downstream routing, delivery and shared-price effects under the same revealed shop prefix. It is not a one-feed valuation.

## Final successful quantities and revenue

“Collected” means successful HARVEST/COLLECT_FERTILIZER inventory gains measured by the engine instrumentation. It is not an estimate of biological production or a count of requests. All changes below are V12 minus V8.

| Own product | Collected V8 → V12 | Sold V8 → V12 | Revenue change |
|---|---:|---:|---:|
| Carrot | 422 → 489 | 409 → 489 | +6,532 |
| Egg | 169 → 149 | 169 → 149 | -941 |
| Fertilizer | 402 → 368 | 208 → 190 | -273 |
| Melon | 60 → 60 | 60 → 60 | -31 |
| Milk | 135 → 110 | 135 → 110 | -4,056 |
| Strawberry | 111 → 88 | 111 → 88 | -2,618 |
| Tomato | 126 → 129 | 123 → 129 | +259 |
| Wheat | 604 → 557 | 368 → 381 | +248 |
| Wool | 198 → 197 | 198 → 197 | +365 |

Own total revenue falls 515 and spending rises 578, exactly reconciling the -1,093 cash difference. Spending changes are wheat purchases +498, carrot seeds +480, strawberry seeds -300 and wheat seeds -100. Animal purchases, land and wages are unchanged. In particular, the final wool gain is a revenue change at one fewer unit sold, not a wool production gain.

| Rival product | Sold V8 → V12 | Revenue change |
|---|---:|---:|
| Carrot | 284 → 284 | +1,788 |
| Egg | 64 → 64 | -38 |
| Fertilizer | 245 → 245 | +13 |
| Melon | 83 → 83 | +21 |
| Milk | 113 → 108 | -1,950 |
| Strawberry | 104 → 104 | -1,661 |
| Tomato | 90 → 90 | -81 |
| Wheat | 358 → 357 | -138 |
| Wool | 285 → 285 | -2,974 |

Rival total revenue falls 5,020 and spending falls 501 (wages -288, wheat purchases -203, fertilizer purchases -10), reconciling -4,519 cash. Its largest revenue loss is wool at exactly the same 285 units sold, followed by milk and strawberry. The first changed rival action is D19 H2, step 458; prices can change earlier despite identical rival actions. The altered shops and changed joint sales prevent attributing these revenue differences solely to our feed repair.

| Dawn | Own cash change | Rival cash change | Margin change |
|---|---:|---:|---:|
| D9 | 0 | 0 | 0 |
| D10 | -185 | -34 | -151 |
| D12 | -332 | -90 | -242 |
| D15 | +45 | -182 | +227 |
| D18 | +1,879 | -2,636 | +4,515 |
| D21 | -1,359 | -4,559 | +3,200 |
| D24 | -1,513 | -5,553 | +4,040 |
| D30 | -1,093 | -4,519 | +3,426 |

This read-only analysis uses the completed `strategy_v8_kb115lt2_readiness` and `strategy_v12_kb115lt2_runtime_fast` live01 recordings. No new game or qualification outcome was used. The reproducible script is `scripts/audit_kb115lt2_v12_live01_20260928.py`. The detailed artifact, source/action SHA256 values, animal-state differences, day-by-day physical changes and committed retirements are in `results/fresh/semantic_kb115lt2_recovery/v12_live01_natural_trace.json`, SHA256 `d239ea707167d6ebdec3c48f9848078c0ea56f4fe1fb5ca561ad471ffcad9881`.
