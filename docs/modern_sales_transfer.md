# Transferring our sale policies to V44 and V45

## Result

- **V44:** screened `order`; selected **`order`**. Confirmation mean margin change +137.4, own-cash change +60.7; 8/8 positive seed averages. File: `agents\v44_our_selected.py`.
- **V45:** screened `order`; selected **`order`**. Confirmation mean margin change +137.4, own-cash change +60.7; 8/8 positive seed averages. File: `agents\v45_our_selected.py`.

Each selected file is self-contained. `base` means the unchanged public source was retained because the transfer did not pass the predeclared gate. Existing `modern_router_selected.py`, the uploaded `market_impact_selected.py` and the Kaggle submission are unchanged.

## What was transferred

1. **Order:** our existing static price-impact sale-ranking formula from `adaptive_market_order.py`, using the physically available lot and an equally sized hypothetical rival lot. It replaces the native quote-priority score inside the existing distinct contiguous sale blocks. Purchase barriers and quantities stay intact. It uses the native ordering activation window (from turn 288), rather than broadening the opening or moving orders across purchases.
2. **Liquid:** sell additional physically available milk/wool during turns 216–695, with native ambiguity, pickup and order-cap guards. For stock sold ahead of a known future tape sale, add reservation debt so the corresponding future quantity is suppressed. This adapts our old liquidation policy to the newer scheduler; it is not a blind outer wrapper.
3. **Both:** combine the two transfers. Physical worker actions, planting, economic feeding and crop-input planning remain controlled by the public base.

The earlier joint-fertilizer candidate was already implemented on V45 and failed its independent confirmation. It is not included here. Several formerly researched ideas were also never selected; they are not treated as established improvements.

## Evaluation

Development: three seeds (140000–140002), both seats, Farming V5 and Two Coins, two bases and four modes: 96 games. Select the highest paired mean margin per base, then confirm without tuning on eight new seeds (141000–141007), both seats, Farming V5, Two Coins and the other public base: 192 games. Two initial smoke games give 290 full games before file-loading checks.

Future shops are uniform draws with replacement, common across comparisons and hidden until revealed. The independent confirmation sample is eight seeds; public rivals share some ancestry. The three-seed screen is deliberately provisional, not evidence of general superiority.

| Panel | Base | Transfer | Margin gain | Own-cash gain | Baseline W/T/L | Transfer W/T/L |
|---|---|---|---:|---:|---:|---:|
| development | v44 | order | +102.5 | +42.8 | 12/0/0 | 12/0/0 |
| development | v44 | liquid | -1,499.7 | -1,611.6 | 12/0/0 | 12/0/0 |
| development | v44 | both | -1,417.8 | -1,570.5 | 12/0/0 | 12/0/0 |
| development | v45 | order | +102.5 | +42.8 | 12/0/0 | 12/0/0 |
| development | v45 | liquid | -1,499.7 | -1,611.6 | 12/0/0 | 12/0/0 |
| development | v45 | both | -1,417.8 | -1,570.5 | 12/0/0 | 12/0/0 |
| confirmation | v44 | order | +137.4 | +60.7 | 32/0/16 | 32/0/16 |
| confirmation | v45 | order | +137.4 | +60.7 | 48/0/0 | 48/0/0 |

## Confirmation by opponent

| Base | Transfer | Opponent | Margin gain | Own-cash gain |
|---|---|---|---:|---:|
| v44 | order | farmingv5 | +132.6 | +49.9 |
| v44 | order | twocoins | +139.5 | +73.0 |
| v44 | order | v45 | +140.0 | +59.2 |
| v45 | order | farmingv5 | +132.6 | +49.9 |
| v45 | order | twocoins | +139.5 | +73.0 |
| v45 | order | v44 | +140.0 | +59.2 |

## Why the transfers differ

The liquidation adapter was useful on our older five-tape router, which left accessible animal products unsold. The newer bases already bring sales forward selectively. Our transfer sells additional stock sooner and reduces future scheduled quantities. Its development losses came mainly from milk/wool revenue, with relatively small changes in units sold; this points to timing and realized-price effects rather than a large production gain.

| Base | Development transfer | Milk revenue change | Milk units change | Wool revenue change | Wool units change |
|---|---|---:|---:|---:|---:|
| v44 | order | +1.5 | +0.00 | -14.5 | +0.00 |
| v44 | liquid | -917.7 | -3.00 | -644.0 | +0.17 |
| v44 | both | -915.2 | -3.00 | -651.8 | +0.17 |
| v45 | order | +1.5 | +0.00 | -14.5 | +0.00 |
| v45 | liquid | -917.7 | -3.00 | -644.0 | +0.17 |
| v45 | both | -915.2 | -3.00 | -651.8 | +0.17 |

Order-only changes ranking within the native sale blocks. It preserves quantities and fits the newer controller more naturally, but its confirmation results—not that compatibility argument—determine selection.

## Gate and checks

Both selected standalone files also passed full games through the official file-path agent loader, with native shop RNG, cash reconciliation and per-turn wheat conservation. Including these two packaging checks, the total is **292 full games**. These packaging games are not used for selection.

Per base, promote only with positive confirmation mean paired margin, nonnegative mean against each rival, >=6 of 8 positive seed averages, no fewer wins, no nonzero errors/fallbacks and max call <1s. Otherwise keep that unchanged base. Do not overwrite existing local selection or submit to Kaggle.

All 288 panel games completed 720 valid states, reconciled both cash ledgers and passed wheat conservation after every turn. Frozen source hashes match. Nonzero error/fallback counters: 0. The two smoke games also passed. Twenty-two focused contracts across both bases passed for stock limits, physical-action preservation, future-sale suppression, terminal abstention, pickups, order capacity and purchase barriers.

| Base | Gate | Passed |
|---|---|---|
| v44 | positive_mean | True |
| v44 | nonnegative_each_rival | True |
| v44 | six_positive_seeds | True |
| v44 | no_fewer_wins | True |
| v44 | no_errors | True |
| v44 | under_one_second | True |
| v45 | positive_mean | True |
| v45 | nonnegative_each_rival | True |
| v45 | six_positive_seeds | True |
| v45 | no_fewer_wins | True |
| v45 | no_errors | True |
| v45 | under_one_second | True |

## Reproduction and provenance

- Build: `scripts/build_modern_sales.py`; build fragment: `agents/modern_sales_overlay.py`.
- Contracts: `scripts/verify_modern_sales.py`.
- Evaluation: `scripts/evaluate_modern_sales.py --phase smoke`, `development`, `select`, then `confirmation`.
- Report and per-base selection: `scripts/report_modern_sales.py`.
- Frozen manifests, screen selection, all ledgers and telemetry: `results/fresh/modern_sales/`.
- Original V44/V45 source and attribution notices are retained. Our original ranking functions are extracted directly from `agents/adaptive_market_order.py` into each standalone build; no research module is imported at runtime.
