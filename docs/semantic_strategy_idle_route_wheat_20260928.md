# Frozen V5 idle workers: route-local wheat shortage

The two requested D10 failures are reproducible execution stalls. Both saved-action replays reproduce all final cash, full daily ledgers, and all 30 dawn observations. Frozen V5 shadow calls match all 264 actions through D10 in each case. No live rival code ran.

| Case | Worker (farmer = 0) | Observed PASS hours at unfunded feed route head | Tile |
| --- | --- | --- | --- |
| live-01 | 1 | 12–21 | 44 |
| live-01 | 0 | 14–18, 22–23 | 45, 36 |
| live-01 | 3 | 19–23 | 24 |
| live-02 | 5 | 15–21 | 42 |
| live-02 | 2 | 18–21 | 43 |

There are 22 such worker-hours in live-01 and 11 in live-02. These counts require the exact current route head, a FEED task, a worker standing on that tile with no wheat, and an actual PASS. They do not classify every idle hour as the same defect. In particular, live-01 worker 1 still passes at H22–23 after its rolling route becomes empty; that separate behavior is outside this count.

The same-age crop readiness permutation is independently real, but it does not explain these feed stalls. At live-01 H14 there are visible empty planting targets, 15 wheat seeds and eight carrot seeds, while worker 1 is stuck on the cow at tile 44. Its route includes later crop jobs that it never reaches.

## Mechanism

Frozen KB115LT's `_market` subtracts **all workers' carried wheat** from global feed demand. `_sd_build` derives available pickup wheat using the same aggregate calculation. At live-01 H14, cash is 3,633, carried wheat is 23, demand is 12, and shed wheat is zero. At live-02 H15, cash is 3,143, carried wheat is 17, demand is 12, and shed wheat is zero. The idle worker has none of that wheat. The market issues no replenishment.

In `_sd_eval1`, unavailable soft FEED and CARE operations are skipped while evaluating the route; a route can retain that animal job followed by useful crop jobs. `_sd_act` still executes only the route's first job. Standing on the animal without wheat, it skips FEED and the dependent CARE, then returns `None`. Greedy fallback encounters the same task and emits PASS. The next hourly search can retain the same route and repeat the stall.

Relevant frozen source locations: `_market` around line 3584, `_sd_build` around 4689, `_sd_eval`/`_sd_eval1` at 5057/5082, `_sd_act` at 6360, and greedy fallback around 2431–2505. Frozen KB SHA-256 is `2ebe94ece8ef48bf0058e620b5803c11050de7e663a63f4f41522f0758186ee0`.

## Narrow prototype

`scripts/semantic_strategy_route_wheat_20260928.py` is optional and defaults to OFF. It appends at most one `BUY_PRODUCT WHEAT` order after the normal executor. It does not change worker commands, scheduler settings, route order, or stored planner state. The purchase quantity is limited to currently observed blocked route heads, accounting for existing shed wheat and native pending wheat orders. Wheat held by another worker does not cancel this local shortage.

The helper requires a current FEED task, PASS, a live unfed animal at that worker's exact integer route head, and zero wheat in that worker's inventory. It is hard bounded to days 6–10 and hours through 20. Any active or admitted retirement intention defers the entire repair, including an `_xretire` entry whose value is false. It respects the ten-order cap and shed capacity and reserves cash for native purchase orders without crediting requested sales. Product quote walks include a small explicit buffer; actual simultaneous market execution remains authoritative.

An observational `_sd_pre` hook exposes current tasks without changing arguments or results. Six focused tests cover default-off behavior, direct local evidence, retirement guards, time window, cash, native orders, capacity, and input immutability.

The expected next-hour native behavior is a pickup: a positive shed stock increases `P.avw`, `_sd_eval1` can schedule its existing pickup step, and `_sd_act` already implements that pickup. Two authorized serial continuations confirmed that behavior, using only the original opponent action stream and stopping at the next dawn. Original shadow actions matched through 254/256 calls, including the first intervention's unchanged worker commands. Each continuation added two bought wheat units and one additional sold wheat unit relative to control; net cash cost was 37/38. No route reset or forced worker action was used.

| One-day change vs exact saved control | live-01 | live-02 |
| --- | ---: | ---: |
| Blocked feed-head PASS hours | 22 → 4 | 11 → 2 |
| All PASS commands | −15 | −8 |
| FEED | +1 | +1 |
| CARE | 0 | +1 |
| PLANT | +1 | −1 |
| WATER | +3 | −2 |
| Moves | +11 | +7 |
| Next-dawn own cash | −37 | −38 |
| Maximum post-trigger call | 45 ms | 43 ms |

The repair has mixed production effects. Live-01 ends with one more wheat and one more strawberry tile, including survival differences. Live-02 ends with one fewer tomato after the native route reassignment. Both preserve the same animal counts at the next dawn. No post-trigger call exceeded one second. These results establish that local wheat availability releases the stall; they do not establish a profitable full-season repair.

KB115LT2's rolling evaluator, executor and market are AST-identical to this old executor. Its fixed-tier pickup block is also unchanged. The diagnosis remains relevant, but these two continuations are explicitly V5 component evidence, not new-baseline performance. The helper remains OFF and is not included in frozen V8.

## Evidence

- `results/fresh/semantic_strategy_20260928/idle_shadows_v5/live-01-d10-10.json.gz`
- `results/fresh/semantic_strategy_20260928/idle_shadows_v5/live-02-d10-10.json.gz`
- `results/fresh/semantic_strategy_20260928/idle_route_wheat_diagnostic_summary.json`
- Reproducer: `scripts/replay_semantic_strategy_idle_shadow_20260928.py`
- Bounded continuation: `scripts/replay_semantic_strategy_route_wheat_20260928.py`
- Summary: `scripts/summarize_semantic_strategy_idle_20260928.py`

The summary includes source, saved actions, frozen candidate manifest, raw control, helper, and summary-script hashes. The cases were selected for debugging; they do not establish full-season profitability or general superiority of the prototype.
