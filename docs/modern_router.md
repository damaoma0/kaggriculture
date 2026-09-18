# Modern router: working baseline and joint input planning

## Result

Selected **baseline** as the local working agent: `agents/modern_router_selected.py`. The candidate did not clear the predeclared gate; retain the exact public V45 baseline.

Confirmation average candidate-minus-baseline margin: **-20.7**; own cash: **+41.6**. Positive seed averages: **3/8**. These results do not estimate a leaderboard rating.

The currently uploaded `agents/market_impact_selected.py` and submission 56273827 are unchanged. Local selection is not a Kaggle submission.

## What was implemented

- `modern_router_baseline.py` is an exact, hash-verified copy of the downloaded V45 source. It retains economic feeding, shop-dependent production, crop-input planning, execution safeguards and source attributions.
- `modern_router_candidate.py` is a standalone build of that source plus our new joint fertilizer-tour selector. The feeding rule remains intact. The candidate retains up to six distinct first-worker routes, tries compatible second-worker routes, and values the pair together.
- Candidate valuation sums marginal fertilizer purchase quotes and output sale quotes, includes Fibonacci hiring costs, and retains the existing cash reserve, warehouse/order caps and profit safety factors. Profitable shorter tours may be considered. Existing tours are retained unless the candidate estimates a higher joint net value.
- Physical execution remains with the existing observed-state controller. Gain estimates use scheduled watering and harvest deadlines. Current-price valuation is conservative but is not a reliable forecast of future market prices.

## Frozen evaluation

One candidate, frozen before panel results. Development: four seeds (137000–137003), both seats, three modern rivals, 48 games. Confirmation: eight different seeds (138000–138007), both seats, four rivals, 128 games. One prior smoke game gives 177 full games total. No parameter tuning occurred between panels.

Shop draws are uniform with replacement, shared across each comparison, and hidden until revealed. The effective independent confirmation sample is eight seeds; the opponents include related public-code descendants. Both cash ledgers and wheat conservation after every turn were checked.

| Panel | Opponent | Baseline W/T/L | Candidate W/T/L | Paired margin gain | Own-cash gain |
|---|---|---:|---:|---:|---:|
| development | farmingv5 | 8/0/0 | 8/0/0 | -161.0 | -71.0 |
| development | twocoins | 8/0/0 | 8/0/0 | -107.2 | -94.2 |
| development | v44 | 8/0/0 | 8/0/0 | +83.8 | +36.0 |
| confirmation | farmingv5 | 14/0/2 | 14/0/2 | -116.8 | -1.5 |
| confirmation | twocoins | 16/0/0 | 16/0/0 | +0.2 | +39.1 |
| confirmation | v44 | 14/0/2 | 14/0/2 | +38.5 | +85.0 |
| confirmation | v45 | 0/16/0 | 6/6/4 | -4.8 | +43.8 |

## What changed economically

Candidate minus baseline, averaged across confirmation games. Extra fertilizer and hiring must earn back their costs; an improvement in the planner's current-price score does not guarantee a better game outcome.

| Quantity or cash flow | Average change |
|---|---:|
| actual_wheat_harvest | +5.88 |
| input_confirmed_applications | +4.38 |
| input_confirmed_hires | +0.72 |
| revenue:WHEAT | +201.81 |
| revenue:CARROT | +14.16 |
| revenue:FERTILIZER | +68.19 |
| cost:BUY_PRODUCT:FERTILIZER | +139.50 |
| cost:HIRE | +136.88 |

The full cash accounting is in `summary.json`; it includes all other products and costs. Current-price input valuation remains approximate because output arrives later and both players alter market supply. The shortlist also makes this a bounded heuristic rather than an exact joint optimizer.

## Promotion gate

Confirmation: positive mean paired margin; nonnegative mean paired margin against each rival; positive seed-averaged paired margin on at least 6 of 8 seeds; no fewer total wins than baseline; mean own-cash delta >= -500; no nonzero error/fallback counters; max observed call < 1 second. Otherwise retain exact V45 baseline locally. Never submit automatically.

| Condition | Passed |
|---|---|
| positive_mean_margin | False |
| nonnegative_each_rival | False |
| six_positive_seeds | False |
| no_fewer_wins | True |
| own_cash_floor | True |
| no_errors_or_fallbacks | True |
| action_time_below_one_second | True |

## Runtime and execution

The selected standalone file also passed a full 720-state game through the official file-path agent loader with native shop RNG, exact cash ledgers and per-turn wheat conservation. This extra packaging check brings the total to **178 full games**. Focused planner checks also passed for disjoint feasible tours, yield/harvest deadlines, cash reserves, capacity/order limits and observation immutability (`scripts/verify_modern_inputs.py`).

Maximum candidate action time on confirmation under concurrent local load: 0.365s. Mean changed joint-planning calls per game: 1.22. Nonzero candidate confirmation error/fallback counters: 0. Timing on a competition host remains untested.

## Decision and next target

Keep the modern baseline's economic feeding and existing crop-input planner. This candidate produces more wheat, but the additional fertilizer and labor nearly consume the added revenue, and the opponent also benefits from changed market conditions. Enlarging the route search alone did not establish a competitive gain.

The next improvement should calibrate marginal input decisions against output prices at delivery time and their effect on winning margin, using this frozen modern opponent panel. Preserve this failed candidate as evidence; do not retune it on the confirmation seeds and call that independent validation.

## Files and reproduction

- Build: `scripts/build_modern_router.py`; editable build fragment: `agents/modern_input_overlay.py`.
- Evaluate: `scripts/evaluate_modern_router.py --phase smoke`, `--phase development`, then `--phase confirmation`.
- Verify and select locally: `scripts/report_modern_router.py`.
- Frozen source hashes, all game ledgers, comparisons and selection: `results/fresh/modern_router/`.
- Public source: [V45 by Ahmed Berat Ozer](https://www.kaggle.com/code/ahmedberatozer/kaggriculture-v45-first-turn-wheat-round-trip). Original source notices are preserved in both standalone files.

Selected SHA-256: `2536d41ed5a00c75204b6350f1c76c54259c774cb065ba2a3a0072eedf210d94`.
