# V12 development result

V12 fails the development strength screen:5/8 wins where6/8 are required. All8 games finish with normal runtime, both ledgers verified, no callback/executor/opponent errors and the same frozen candidate manifest. Mean native margin is+1992.875. No recorded-opponent8 or qualification40 was dispatched.

The candidate is exact frozen V8 plus the reviewed executor source `d6769c6994a9445f96a34e6c517e4fdee8d3bd3160d349e7d480bdc89871452b` and `executor.sd_tier_wheat_retry=1`. Policy, model, tile compiler, recipe and harness remain V8. Candidate manifest is `aafa32c48bc4b32627855bd0f0bf18bf93f4f982c496f5ec5f7411dc43a938a1`. The changes combine residual-wheat route retry, per-call polish memoization, scalar evaluator arithmetic and per-search cost caching. Six focused tests were independently rerun; actual saved inputs preserve evaluator results, search routes/objectives/RNG state and polish outputs in the bound component benchmark. Timed search can remain sensitive to wall time.

| Case | V8 margin | V12 margin | V12 candidate overage |
|---|---:|---:|---:|
| live00 |11163|11163|18.67s|
| live01 |3165|6591|14.44s|
| live02 |1247|1247|29.74s|
| live03 |-1004|-1004|11.94s|
| live04 |1855|1855|24.71s|
| live05 |1641|1641|29.45s|
| live06 |-3391|-3391|48.46s|
| live07 |-6720|-2159|20.75s|

Live06 was a separately frozen normal-budget technical smoke and was reused by hash, never rerun. It reproduces all V8 cash, ledgers, shops and physical commands. Its only two action-list differences reorder distinct-product SELL orders atsteps429/525; strict byte equality is not claimed. Its11.538seconds remaining is the lowest budget in the panel.

Only01/07 change cash margins. Their natural shop sequences also change, so the mean paired native margin gain+998.375 is not an isolated route-retry treatment effect. In01, our cash falls1093 and rival cash falls4519. In07, our cash falls21843 and rival cash falls26404. The remaining six complete ledgers match V8. The report preserves production, sold units, revenue and average realized prices by product.

Artifacts remain under main `results/fresh/semantic_strategy_20260928/`: immutable candidate and `development_dispatches/strategy_v12_kb115lt2_runtime_fast/`; all game results/actions; final independent audit and development shipping-score report; `reports/v12_native_development_comparison.json`; `reports/v12_live06_technical_smoke_report.json`. The final audit initially found the aggregate report still described the one-case smoke. That stale aggregate and the corresponding audit were copied to separate history files before refreshing the eight-case aggregate; no game result was altered.

V9's two timeout failures, V10's failed smoke and the incomplete profiled replay remain preserved. The separate-process harness is an unexecuted proposal, not a retrospective exception to these results. The next behavioral candidate requires separate component evidence and authorization.
