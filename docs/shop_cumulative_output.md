# Can shop combinations predict cumulative production?

Historical September 17 leader versions, fitted separately. Output is actual harvested/collected units, excluding purchases and sales. Fertilizer means collected fertilizer.

`counts` uses the counts of all eight shop types. `counts_and_timing` also uses how many shop-days each type has been present. `own_product_demand` is a separately reported simpler check: each product uses only the total demand for that product from revealed shops (Pet Cafe/Yarn Store count double for carrot/wool). Models are not chosen using the outer test scores.

`remaining` predicts harvest from the checkpoint through day 29 using information then available. `already_produced` is descriptive only: it includes the newly revealed checkpoint-day shop as an input even though that target's harvest ended the previous day. It is not a forward forecast.

Each test holds out **every game with the same unordered shop combination**. A regularized linear model is trained on the other combinations. Its regularization (or a constant predictor) is chosen using inner validation, without the test games. The reference predicts each product using that leader version’s training mean at that date.

**Score = percentage reduction in held-out squared prediction error versus the reference.** 100% is perfect; 0% matches the reference; a negative value is worse. A dash means the target is constant. These are predictive diagnostics, not causal effects or profit.

## Season-total production from the eight shops known at day 24

| Leader/version | n / combinations | Wheat | Carrot | Tomato | Strawberry | Melon | Egg | Milk | Wool | Fertilizer |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| UMG 56266758 | 30 / 30 | 64% | 78% | 49% | 46% | -13% | 41% | 27% | 84% | 25% |
| Majkel1337 56216119 | 30 / 30 | 36% | 67% | 8% | 24% | -1% | -6% | 13% | 47% | 36% |
| Majkel1337 (earlier submission) 56156662 | 8 / 8 | 53% | 57% | 13% | -25% | -5% | -44% | -8% | -12% | -68% |
| M & M & P & Q 56254996 | 8 / 8 | 0% | -68% | -34% | -7% | 38% | 3% | -22% | -34% | -92% |

The final eight-shop combination includes reveals occurring after much of the production commitment. This measures an association with the whole-season total, not what an agent could forecast at day 12.

## UMG — 56266758

| Known by day | Target | Model | Wheat | Carrot | Tomato | Strawberry | Melon | Egg | Milk | Wool | Fertilizer |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 12 | season_total | counts | 52% | 85% | 74% | 92% | -12% | 55% | 71% | 77% | 30% |
| 12 | season_total | counts_and_timing | 54% | 81% | 72% | 92% | -22% | 73% | 79% | 84% | -6% |
| 12 | remaining | counts | 53% | 85% | 74% | 92% | -13% | 54% | 71% | 77% | 37% |
| 12 | remaining | counts_and_timing | 56% | 81% | 72% | 92% | -22% | 71% | 79% | 84% | 1% |
| 12 | remaining | own_product_demand | -3% | 66% | 75% | 94% | 0% | 0% | 82% | 80% | 0% |
| 12 | already_produced | counts | -27% | — | — | — | 0% | 46% | 0% | — | 8% |
| 12 | already_produced | counts_and_timing | -8% | — | — | — | 0% | 59% | 0% | — | 3% |
| 15 | season_total | counts | 72% | 89% | 83% | 81% | -1% | 41% | 63% | 84% | 40% |
| 15 | season_total | counts_and_timing | 67% | 88% | 81% | 88% | 3% | 79% | 81% | 95% | -12% |
| 15 | remaining | counts | 75% | 89% | 83% | 81% | -5% | 39% | 65% | 84% | 46% |
| 15 | remaining | counts_and_timing | 70% | 88% | 81% | 88% | 17% | 77% | 80% | 95% | 22% |
| 15 | already_produced | counts | 21% | — | — | 0% | 0% | 50% | -8% | 50% | -4% |
| 15 | already_produced | counts_and_timing | 6% | — | — | 0% | 0% | 71% | 4% | 55% | 1% |
| 18 | season_total | counts | 58% | 88% | 74% | 70% | -7% | 56% | 34% | 84% | 43% |
| 18 | season_total | counts_and_timing | 65% | 93% | 80% | 88% | 9% | 83% | 86% | 97% | 31% |
| 18 | remaining | counts | 60% | 89% | 74% | 71% | -2% | 54% | 35% | 88% | 55% |
| 18 | remaining | counts_and_timing | 70% | 93% | 80% | 88% | 8% | 81% | 67% | 95% | 42% |
| 18 | already_produced | counts | 11% | -12% | — | -13% | 0% | 57% | -7% | 62% | -8% |
| 18 | already_produced | counts_and_timing | 44% | -13% | — | 9% | 0% | 84% | 33% | 86% | -15% |
| 21 | season_total | counts | 70% | 89% | 55% | 62% | -9% | 60% | 32% | 83% | 36% |
| 21 | season_total | counts_and_timing | 67% | 93% | 78% | 87% | 1% | 77% | 77% | 97% | 19% |
| 21 | remaining | counts | 73% | 90% | 55% | 63% | — | 60% | 61% | 92% | 45% |
| 21 | remaining | counts_and_timing | 71% | 93% | 78% | 86% | — | 76% | 75% | 94% | 45% |
| 21 | already_produced | counts | 25% | 16% | 43% | 33% | -9% | 59% | -7% | 55% | -26% |
| 21 | already_produced | counts_and_timing | 31% | 17% | 75% | 40% | 1% | 77% | 68% | 87% | -9% |
| 24 | season_total | counts | 64% | 78% | 49% | 46% | -13% | 41% | 27% | 84% | 25% |
| 24 | season_total | counts_and_timing | 70% | 90% | 81% | 88% | 10% | 78% | 78% | 98% | 10% |
| 24 | season_total | own_product_demand | 7% | 66% | 41% | 58% | 0% | -5% | 44% | 82% | 0% |
| 24 | remaining | counts | 72% | 81% | 40% | 50% | — | 41% | 44% | 91% | 32% |
| 24 | remaining | counts_and_timing | 73% | 86% | 56% | 83% | — | 78% | 69% | 95% | 41% |
| 24 | already_produced | counts | 33% | 34% | 35% | 42% | -13% | 40% | -7% | 74% | 2% |
| 24 | already_produced | counts_and_timing | 34% | 46% | 77% | 84% | 10% | 78% | 74% | 92% | -8% |

## Majkel1337 — 56216119

| Known by day | Target | Model | Wheat | Carrot | Tomato | Strawberry | Melon | Egg | Milk | Wool | Fertilizer |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 12 | season_total | counts | 40% | 60% | 50% | 81% | -0% | 23% | 72% | 76% | 57% |
| 12 | season_total | counts_and_timing | 29% | 68% | 58% | 80% | -0% | 23% | 77% | 86% | 61% |
| 12 | remaining | counts | 43% | 59% | 50% | 81% | -3% | 23% | 72% | 76% | 61% |
| 12 | remaining | counts_and_timing | 32% | 66% | 58% | 80% | -3% | 22% | 77% | 86% | 61% |
| 12 | remaining | own_product_demand | 0% | 68% | 45% | 87% | 0% | 4% | 74% | 86% | 0% |
| 12 | already_produced | counts | -4% | -4% | — | — | -0% | 28% | 0% | 0% | 18% |
| 12 | already_produced | counts_and_timing | -26% | 14% | — | — | -0% | 24% | 0% | 0% | 40% |
| 15 | season_total | counts | 50% | 76% | 39% | 64% | -0% | -1% | 54% | 92% | 56% |
| 15 | season_total | counts_and_timing | 46% | 82% | 57% | 93% | -0% | 18% | 80% | 90% | 58% |
| 15 | remaining | counts | 51% | 77% | 43% | 65% | -3% | -2% | 69% | 92% | 58% |
| 15 | remaining | counts_and_timing | 48% | 79% | 54% | 94% | -1% | 17% | 81% | 88% | 57% |
| 15 | already_produced | counts | -4% | 27% | -1% | -6% | -3% | -1% | -9% | 54% | 40% |
| 15 | already_produced | counts_and_timing | 6% | 61% | -3% | -1% | -2% | 20% | 27% | 70% | 54% |
| 18 | season_total | counts | 52% | 63% | 23% | 44% | -2% | -4% | 12% | 90% | 47% |
| 18 | season_total | counts_and_timing | 50% | 77% | 54% | 90% | -1% | -15% | 69% | 92% | 55% |
| 18 | remaining | counts | 54% | 65% | 19% | 43% | -4% | -5% | 39% | 92% | 49% |
| 18 | remaining | counts_and_timing | 44% | 69% | 58% | 96% | -1% | -15% | 75% | 93% | 48% |
| 18 | already_produced | counts | -12% | 21% | -1% | -2% | -2% | -3% | -40% | 62% | 36% |
| 18 | already_produced | counts_and_timing | 27% | 82% | -34% | -8% | -2% | -15% | 32% | 81% | 54% |
| 21 | season_total | counts | 42% | 70% | 17% | 36% | -4% | -7% | 3% | 66% | 37% |
| 21 | season_total | counts_and_timing | 52% | 79% | 48% | 85% | -2% | 10% | 61% | 94% | 54% |
| 21 | remaining | counts | 44% | 71% | 6% | 31% | -5% | -8% | 51% | 78% | 43% |
| 21 | remaining | counts_and_timing | 38% | 73% | 48% | 86% | -1% | 9% | 73% | 95% | 51% |
| 21 | already_produced | counts | 2% | 29% | 4% | 1% | -3% | -6% | -4% | 50% | 18% |
| 21 | already_produced | counts_and_timing | 54% | 80% | 1% | 17% | -3% | 9% | 48% | 88% | 52% |
| 24 | season_total | counts | 36% | 67% | 8% | 24% | -1% | -6% | 13% | 47% | 36% |
| 24 | season_total | counts_and_timing | 46% | 85% | 39% | 80% | -1% | 19% | 62% | 94% | 55% |
| 24 | season_total | own_product_demand | 0% | 64% | 18% | 49% | 0% | -4% | 27% | 50% | 0% |
| 24 | remaining | counts | 31% | 53% | 18% | 25% | -5% | -7% | 40% | 61% | 51% |
| 24 | remaining | counts_and_timing | 15% | 56% | 36% | 69% | -5% | 23% | 71% | 92% | 48% |
| 24 | already_produced | counts | -0% | 55% | -3% | 23% | -1% | -7% | -14% | 42% | 18% |
| 24 | already_produced | counts_and_timing | 77% | 77% | 13% | 33% | -3% | 18% | 64% | 90% | 54% |

## Majkel1337 (earlier submission) — 56156662

| Known by day | Target | Model | Wheat | Carrot | Tomato | Strawberry | Melon | Egg | Milk | Wool | Fertilizer |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 12 | season_total | counts | 0% | -18% | 74% | 52% | -9% | -44% | -12% | 49% | -22% |
| 12 | season_total | counts_and_timing | -14% | -24% | 64% | 67% | 2% | -20% | -13% | 28% | -6% |
| 12 | remaining | counts | 0% | -18% | 74% | 52% | — | -43% | -12% | 49% | -27% |
| 12 | remaining | counts_and_timing | -14% | -24% | 64% | 67% | — | -13% | -13% | 28% | -3% |
| 12 | remaining | own_product_demand | 0% | -23% | 67% | 92% | — | -13% | 78% | 93% | 0% |
| 12 | already_produced | counts | -72% | — | — | — | -9% | -46% | — | — | 14% |
| 12 | already_produced | counts_and_timing | -47% | — | — | — | 2% | -42% | — | — | -34% |
| 15 | season_total | counts | -64% | -19% | 19% | 56% | -16% | -35% | 43% | -10% | 0% |
| 15 | season_total | counts_and_timing | -42% | -18% | 31% | 62% | -7% | -25% | 52% | -86% | -19% |
| 15 | remaining | counts | -104% | -19% | 19% | 58% | — | -36% | 52% | -9% | -2% |
| 15 | remaining | counts_and_timing | -39% | -18% | 31% | 63% | — | -26% | 46% | -92% | -1% |
| 15 | already_produced | counts | -45% | — | — | -16% | -16% | -33% | 33% | -17% | -35% |
| 15 | already_produced | counts_and_timing | -15% | — | — | -7% | -7% | -23% | 57% | -79% | -143% |
| 18 | season_total | counts | -110% | -11% | 5% | -41% | 1% | -20% | 49% | -5% | -2% |
| 18 | season_total | counts_and_timing | -80% | -25% | 13% | 5% | -0% | -20% | 54% | -71% | -12% |
| 18 | remaining | counts | -74% | -11% | 6% | -30% | — | -20% | 36% | -20% | -2% |
| 18 | remaining | counts_and_timing | -53% | -25% | 14% | -1% | — | -20% | 5% | -69% | -3% |
| 18 | already_produced | counts | -59% | — | 1% | -21% | 1% | -19% | 86% | -30% | -48% |
| 18 | already_produced | counts_and_timing | -57% | — | -0% | -32% | -0% | -19% | 82% | -84% | -86% |
| 21 | season_total | counts | -44% | 20% | 37% | -25% | -1% | -15% | 51% | -61% | 0% |
| 21 | season_total | counts_and_timing | -93% | -19% | 38% | 4% | 0% | -20% | 35% | -59% | -11% |
| 21 | remaining | counts | -4% | 20% | 40% | -20% | — | -15% | -29% | -59% | -1% |
| 21 | remaining | counts_and_timing | -32% | -19% | 41% | -8% | — | -20% | -61% | -61% | -4% |
| 21 | already_produced | counts | -56% | — | -6% | -12% | -1% | -14% | 66% | -26% | -36% |
| 21 | already_produced | counts_and_timing | -78% | — | -12% | -23% | 0% | -20% | 77% | -62% | -75% |
| 24 | season_total | counts | 53% | 57% | 13% | -25% | -5% | -44% | -8% | -12% | -68% |
| 24 | season_total | counts_and_timing | -44% | 3% | 38% | -6% | -0% | -12% | -3% | -20% | -46% |
| 24 | season_total | own_product_demand | -19% | 66% | -17% | 52% | 0% | -43% | 13% | 67% | 0% |
| 24 | remaining | counts | 2% | 61% | 8% | -31% | — | -45% | -5% | 4% | 0% |
| 24 | remaining | counts_and_timing | 1% | 5% | 49% | -27% | — | -13% | -69% | -5% | -0% |
| 24 | already_produced | counts | -3% | -4% | 8% | -25% | -5% | -44% | -18% | -25% | -99% |
| 24 | already_produced | counts_and_timing | -46% | -0% | 3% | 5% | -0% | -12% | 35% | -39% | -73% |

## M & M & P & Q — 56254996

| Known by day | Target | Model | Wheat | Carrot | Tomato | Strawberry | Melon | Egg | Milk | Wool | Fertilizer |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 12 | season_total | counts | -19% | 20% | -15% | 55% | -20% | 47% | 11% | 14% | -45% |
| 12 | season_total | counts_and_timing | -8% | 67% | -24% | 65% | -33% | 32% | -0% | -33% | -33% |
| 12 | remaining | counts | -6% | 22% | -15% | 55% | -15% | 51% | 7% | 16% | -30% |
| 12 | remaining | counts_and_timing | -32% | 72% | -24% | 65% | -13% | 32% | -4% | -38% | 0% |
| 12 | remaining | own_product_demand | 5% | 75% | 2% | 82% | 0% | 29% | 55% | 73% | 0% |
| 12 | already_produced | counts | -16% | -2% | — | — | -9% | -41% | -2% | 22% | -88% |
| 12 | already_produced | counts_and_timing | -4% | -20% | — | — | -26% | -28% | -2% | -13% | -66% |
| 15 | season_total | counts | -6% | 7% | -62% | -6% | -91% | 7% | 20% | 73% | -33% |
| 15 | season_total | counts_and_timing | 4% | 49% | -46% | 38% | -131% | 24% | 18% | 15% | -76% |
| 15 | remaining | counts | 0% | -3% | -62% | 7% | -1% | 14% | 11% | 45% | -77% |
| 15 | remaining | counts_and_timing | -1% | 12% | -46% | 48% | 17% | 30% | -33% | 14% | -132% |
| 15 | already_produced | counts | 0% | -62% | — | -20% | -8% | 20% | -33% | -90% | 28% |
| 15 | already_produced | counts_and_timing | -24% | -38% | — | 3% | -4% | 35% | -40% | -69% | 10% |
| 18 | season_total | counts | -0% | -8% | -20% | -7% | 38% | 60% | -3% | 69% | -30% |
| 18 | season_total | counts_and_timing | -191% | 47% | -49% | 9% | -37% | 63% | 51% | 58% | -74% |
| 18 | remaining | counts | -3% | 4% | -20% | 11% | -61% | 69% | 7% | 57% | -54% |
| 18 | remaining | counts_and_timing | -4% | 23% | -49% | 28% | -23% | 66% | -4% | 43% | -162% |
| 18 | already_produced | counts | -72% | -51% | — | -39% | -33% | -2% | -13% | 33% | 5% |
| 18 | already_produced | counts_and_timing | -89% | 9% | — | -44% | -2% | 9% | -6% | 6% | 7% |
| 21 | season_total | counts | 0% | -38% | -90% | -2% | 74% | -24% | -18% | 66% | -73% |
| 21 | season_total | counts_and_timing | 0% | -3% | -61% | 20% | 18% | 35% | -11% | 58% | -45% |
| 21 | remaining | counts | -20% | -52% | -76% | 41% | -10% | -31% | -8% | 63% | -70% |
| 21 | remaining | counts_and_timing | -8% | -11% | -48% | 65% | -46% | 36% | -3% | 20% | 0% |
| 21 | already_produced | counts | 0% | -1% | -17% | -33% | 23% | -40% | -32% | 50% | -10% |
| 21 | already_produced | counts_and_timing | -24% | -17% | -29% | -50% | -83% | 31% | -37% | 51% | -33% |
| 24 | season_total | counts | 0% | -68% | -34% | -7% | 38% | 3% | -22% | -34% | -92% |
| 24 | season_total | counts_and_timing | 0% | 17% | -80% | 20% | 36% | 21% | -21% | 44% | -13% |
| 24 | season_total | own_product_demand | -13% | 30% | 13% | 73% | 0% | 57% | 3% | 62% | 0% |
| 24 | remaining | counts | -17% | 37% | -168% | -12% | -40% | 36% | -9% | -35% | -27% |
| 24 | remaining | counts_and_timing | -2% | 19% | -56% | -14% | -39% | 49% | -8% | -8% | 0% |
| 24 | already_produced | counts | -88% | -4% | -32% | -25% | -46% | -40% | -40% | 1% | -62% |
| 24 | already_produced | counts_and_timing | -88% | -47% | -32% | -74% | -47% | 13% | -36% | 37% | -60% |

## Limits and reproducibility

- Historical versions only; n=30,30,8,8; sparse combinations.
- No future shop input, but season_total and already_produced include harvests preceding the observed shop reveals.
- Remaining output is the forward-looking test; it is not feasibility, value or win-rate.
- Timing uses counts plus shop-days since reveal, a summary of order rather than full ordered history.
- Model class is a simple regularized linear model; poor predictions do not prove absence of nonlinear information. Own-product-demand is a separately reported exploratory low-dimensional check, not a winner selected on test scores.
- No uncertainty intervals or multiple-comparison significance claims; no architecture or exact rule recovered.

Source: `results/fresh/leader_segments/segments-*.json`, previously exact-replayed and identity-checked. All fold predictions, actual quantities, mean absolute errors and chosen model penalties are in `results/fresh/production_continuation/shop_cumulative_output.json`. Reproduce with `scripts/analyze_shop_cumulative_output.py`.
