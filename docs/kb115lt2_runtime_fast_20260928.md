# Exact scalar evaluation and search-cost caching

The V10 cache-only candidate failed its normal-budget live06 smoke at D28H0.
Its 673 available actions match the V8 physical commands and market quantities;
two calls reorder SELLs for distinct products within a six-order list. The
recorded opponent's entire 719-action sequence matches. Byte equality is false;
the timeout remains an invalid game, not a strength result.

A separate V8 saved-action cProfile diagnostic captured D18 and D24, then
exhausted the normal time bank at D25H0. That diagnostic is preserved as
incomplete, with no full-game parity claim. At D24, five core planning passes
performed 311,864 route evaluations. Evaluation plus its pickup accounting took
4.58 of 11.78 profiled seconds; polish took 4.40 seconds, overlapping some of
those evaluations. Passive GC time was only 0.0048 seconds. This recorded-action
process does not contain the live opponent's large heap, so it cannot rule out
GC effects in the live test.

Two further exact transformations are isolated in a new experimental source:

- The scalar evaluator removes wheat and animal inventory counters whose values
  never affect the returned time, lateness, travel penalty or fertilizer failure
  count. It still charges all wheat, fertilizer and distinct animal pickups.
  Detailed operation-hour requests use the unchanged reference evaluator.
- Within one mandatory-route search, repeated costs for the same segment and
  ordered stop IDs are memoized. Inputs and scoring globals are fixed during
  that call. The cache is bounded at 16,384 entries and discarded on return.

Neither transformation changes search iterations, random draws, objectives,
time limits, garbage collection or worker scheduling. The original implementation
remains selectable with the corresponding option disabled. As with any speed
change, a search actually stopped by its wall-clock budget could explore a
different number of iterations; full-game equality is not assumed.

Builders are `build_kb115lt2_eval_fast_20260928.py` and
`build_kb115lt2_search_cache_20260928.py`. The resulting
`agents/mgt_lead_kb115lt2_runtime_fast.py` SHA256 is
`d6769c6994a9445f96a34e6c517e4fdee8d3bd3160d349e7d480bdc89871452b`.
It includes the earlier exact polish caches and the default-OFF route-local
wheat retry. Original KB115LT2 remains unchanged.

Three new test methods pass: 2,500 varied evaluator inputs, changed configuration
and wheat state, and twelve searches with exact routes, objective and RNG state.
A separate complete saved-action replay captures 100 actual evaluator inputs
(85 scalar, 15 detailed) and two whole searches. All 30 dawn states and both full
cash ledgers reproduce. Its strict action-order verification remains false
because the same two independent SELL permutations occur; the fixture benchmark
explicitly verifies this narrower scope rather than silently relabeling it.

Across original, polish-cache and runtime-fast executors, all 300 captured
evaluator input/output checks, 18 whole-search result/input/RNG comparisons and
36 prior polish-output comparisons pass. Component timings are noisy, including
large variation in the unchanged detailed evaluator; no reliable scalar speed
claim follows. The two captured search medians changed from 0.120/0.138 seconds
to 0.101/0.090 seconds. A normal-budget full-stack smoke, not these component
timings, determines whether the runtime blocker is resolved.

Append-only evidence in the original workspace study:

- `tier_pre_profile_v8_live06_v1/`: incomplete profiled diagnostic.
- `eval_search_fixtures_v8_live06_v1/`: complete replay, narrowed parity above.
- `reports/kb115lt2_runtime_fast_fixture_benchmark_v1.json`: pure-call comparisons.

No 40-world panel or shipping qualification is authorized by these component
results. A failed eight-world development screen stops that candidate.

## V12 normal-budget smoke

Frozen candidate `strategy_v12_kb115lt2_runtime_fast`, manifest SHA256
`aafa32c48bc4b32627855bd0f0bf18bf93f4f982c496f5ec5f7411dc43a938a1`,
changes only the V8 runtime executor and enables the reviewed route-local wheat
retry. Semantic policy, tile compiler, models, recipe and harness stay identical.

Its one live06 smoke completes 720 steps with both players DONE, both ledgers
reconciled, and zero executor or opponent-search errors. Cash 118,555 versus
121,946 and margin -3,391 reproduce V8. All physical commands and market
quantities reproduce; the same two SELL-order permutations remain. Measured
candidate overage is 48.4595 seconds, leaving 11.5379 seconds of the normal bank;
maximum call is 6.0984 seconds. This is a technical pass on one known case, not a
strength or all-world runtime pass. The seven remaining live development cases
are screened sequentially, retaining this exact frozen result without rerunning
it. Any technical invalidity or inability to reach six wins stops dispatch.
