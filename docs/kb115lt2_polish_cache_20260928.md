# Exact route-score cache experiment

`agents/mgt_lead_kb115lt2_polishcache.py` is generated from the original
KB115LT2 by `scripts/build_kb115lt2_polish_cache_20260928.py`. Only
`_tier_polish` changes. The original source hash remains
`527d4c48b5d6bbef7854d430797e8691858724242d50eeec1e1636665ee124e7`.

Within a single polish call, repeated stop values and route evaluations are
cached. Keys include each command, mandatory flag, tile, release time, dawn and
turnaround markers, segment identity, and current-route feeding context.
Observed tiles, prices, day, configuration and segment attributes remain fixed
for the call. Cached stop identities retain their objects to prevent identity
reuse. All three caches are bounded and discarded on return. Iteration count,
random draws, score arithmetic and accepted-move order are unchanged.

Three pure tests pass, including twelve varied synthetic planning inputs,
cache-disabled equivalence, cross-call isolation, and a check that no other
function changed. A verified V8 live01 recorded-action replay captured four
actual polish inputs: all648 shadow actions, both full cash/ledgers and all30
morning public/private observations reproduced.

Three alternating original/cached repetitions of each captured input reproduce
all output values exactly. Median isolated-call timings:

| Day | Original seconds | Cached seconds | Ratio |
| --- | ---: | ---: | ---: |
| 7 | 0.397 | 0.171 | 2.31 |
| 12 | 0.570 | 0.249 | 2.29 |
| 18 | 0.518 | 0.267 | 1.94 |
| 26 | 0.532 | 0.266 | 2.00 |

These are component timings. Re-serialized pickle bytes differ from the capture
for both the original and cached implementations; the equality claim concerns
the entire resulting argument values, including all route/operation lists,
remaining work and statistics. No serialized-byte identity claim is made.

The isolated V10 cache-only candidate subsequently FAILED its normal-budget
live06 technical smoke: candidate overage60.242seconds, timeout atD28H0.
The failure is preserved; no eight-world or qualification panel is justified by
the component speedup. Profiling the rest of the daily planner and passive GC
timing is the next runtime investigation.

The separately generated `mgt_lead_kb115lt2_routefix_fast.py` composes this exact
transformation with the reviewed route-local wheat retry source. Its V11 freeze
keeps the exact V8 semantic policy, tile planner and recipe; only executor source
and the retry-enable configuration change. V11 game dispatch remains held until
the runtime problem is addressed.

Central append-only evidence:

- `polish_fixtures_v8_live01/manifest.json`
- `reports/kb115lt2_polishcache_fixture_benchmark_v1.json`
- `candidates/strategy_v10_kb115lt2_polishcache/manifest.json`
- `candidates/strategy_v11_kb115lt2_routefix_fast/manifest.json`

All paths above are relative to the original workspace study
`results/fresh/semantic_strategy_20260928/`.
