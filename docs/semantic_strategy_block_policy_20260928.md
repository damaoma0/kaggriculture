# Causal three-day semantic budgets

The isolated `SemanticBlockPolicy` in `scripts/semantic_strategy_blocks_20260928.py` is a practical candidate for the next development comparison. It replaces daily donor end-board chasing with a fixed joint budget for the current reveal interval. It has not played a game and does not establish the requested 30/40 qualification performance.

## Why change the strategic interface

Modern DSM choices respond strongly to revealed demand. Among the modern60 D6 records, Pizza plus a milk-consuming shop consistently adds eight cows; Bakery plus Yarn adds five or six sheep and two cows; double Bakery adds four cows and four geese; several berry-rich pairs add eleven to fourteen strawberries but only one wheat. These are joint investment decisions, not independent fixed per-species quotas.

Daily nearest retrieval changes reference farms after execution slips. An absolute donor end count can then prompt another animal purchase to repair a historical difference; a subsequent donor retirement can remove another animal despite our already smaller active herd. Current development ledgers separately show substantial unfinished early work and retained purchased inputs. More funding or a new target cannot by itself execute a failed pickup/placement route. The proposed block policy addresses the strategic accounting problem; reactive land dispatch and the separately tested financing exception address different execution mechanisms.

The modern100 expansion improves coverage but does not make whole-prefix lookup sufficient. Unique unordered prefixes at D6 increase from 30 to 35 of 36 possible pairs; at D9, from 45 to 61 of 120 triples. Of the original60 cases, leaving each episode out still finds an exact D6 prefix in 47 cases with the smaller library and 53 with the expansion. At D18 those counts are only six and seven. A fitted demand response is therefore useful after the opening, even with the additional records.

## Offline evidence

`block_strategy_diagnostic.json` contains 480 modern60 three-day blocks with leave-one-episode-out predictions. Each block's archived rows was checked to retain exactly the same revealed shop prefix. All fitting, normalization and nearest lookup exclude the target episode. These are development imitation diagnostics, not profit estimates; variants were compared on this same diagnostic.

| Method | Mean absolute error per species per block |
|---|---:|
| Calendar median | 1.619 |
| Daily joint nearest | 1.257 |
| One joint neighbor at reveal | 1.352 |
| Three-neighbor mean at reveal | 1.177 |
| Ridge on demand | 1.035 |
| Ridge on demand and current own counts | 0.939 |
| Ridge with wheat/carrot net replacement targets | 0.954 |

D6 remains better described by nearest joint examples: 0.438 error versus about 0.530 for regression. The runtime candidate uses nearest examples only at D6 and the replacement-aware fitted model later. The latter predicts net annual crop expansion after subtracting existing cohorts due to release; runtime adds back the live farm's own releases. The slightly higher imitation error is accepted to make replacement respond to actual cohort timing.

The separately saved `block_training_expansion_diagnostic.json` holds each original60 episode out of both fitting pools. Adding the authorized40 records reduces net-replacement regression error from 0.954 to 0.915. No new qualification outcomes were used. This is still an internal training diagnostic, and is not independent confirmation of the selected model.

## Runtime behavior and integration

Use `SemanticBlockPolicy(block_model_path, config)` with the same `propose` and `observe` API as the daily policy. Suggested wrapper configuration is `policy_kind="three_day_budget"`, `model_file="block_model_modern100.json"`; the parent owns wrapper integration. The existing policy, tiler, harness and frozen candidates were not edited for this prototype.

At each reveal the policy predicts a complete three-day budget and a daily release schedule. It retains that budget until the next reveal. Actual successful plantings and placements are counted by observed species/birth cohorts; planned, purchased, capacity-clipped and merely requested actions do not count as completed establishments. Missing work carries within the block. A repeated observation does not consume the budget twice. Previously observed successful establishments remain counted if they later disappear, so a transient loss does not silently repurchase the same commitment.

Wheat/carrot replanting dates follow the live cohorts. Existing low-yield crops can defer a day according to the same observed-readiness rule as the base policy. Purchased but unplaced animals in the shed or hands are urgent placement commitments, including across a reveal; private stock receives full credit during capital admission. Crop seeds remain available inputs rather than a requirement to plant an obsolete strategy.

The wrapper's validated `committed_retirement_counts` reduces the active herd while retired animals still occupy their tiles. Missed feeding alone is never treated as an intention. Death can reduce the excess above the active-herd goal without being recorded as an issued retirement. The inherited anonymous forecast reserves two further nights for existing intents because counts do not specify their exact physical exit timing; the tiler still uses observed tile identities and unfed state.

Current end-count fields are computed from our survivors plus the outstanding requests. They are internal admission inputs, not copied donor boards. Forecasts simulate successful admitted changes, but never write simulated completion back into actual memory. Future reveal blocks use a uniform expectation for missing shop draws; actual future shops, world IDs, outcomes, coordinates and private rival state are unavailable to this policy.

The fitted budget uses revealed shop demand and current own counts. Public rival cohorts/history and current prices currently affect inherited marginal values and capital admission, but **do not directly change the fitted total budget when all requests are affordable**. A bounded market-response extension remains separate work; this prototype should not be described as a learned opponent-supply response.

## Artifacts, provenance and limits

The model is built by `scripts/build_semantic_block_model_20260928.py`, with fixed ridge penalty3 and an unpenalized intercept. Runtime requires no NumPy. The source is `causal_daily_rows_modern100.json`; the separate `block_model_modern100_training_manifest.json` retains identities for exclusion checks. The runtime model contains anonymous D6 examples and coefficients, not source episode identifiers.

The old DSM40 are explicitly authorized stage2 training. They are consequently no longer an independent test of a policy trained on this model. All183 newly reserved recorded-world source identities remain excluded. The full candidate's provenance must additionally include the inherited opening and pace training sources.

Nine tests pass, covering observed-only completion, clipped work, carried purchased inputs, actual cohort release dates, repeat-call identity, explicit retirement intent, forecast isolation, source exclusion and ignored runtime identity/future fields. A synthetic full-size D6→29 call took about0.035 seconds locally; this is not an official-runner runtime guarantee.

The candidate can still overload late hours while catching up a block, inherits approximate production/price assumptions for capital ordering, and relies on KB for successful care, delivery and placement. Fitted budgets do not prove better economic choices, and cumulative labels do not guarantee feasible routes. Compare it separately from financing changes against the same corrected execution baseline before spending the untouched qualification panels.
