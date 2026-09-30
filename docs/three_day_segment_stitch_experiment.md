# Three-day UMG production stitching: implementation and test

## Decision

**Keep m1. This prototype fails the execution, performance, and runtime gates.** It establishes that some donor production segments can be reconstructed without replaying worker movements, but it does not establish a reliable continuation policy or an advantage over V56.

## What was built

- A library of **630 three-day segments from 105 UMG games**, starting on days 12, 15, 18, 21, 24, and 27. Every segment’s independently extracted harvest/collection totals match the existing replay-audited production labels.
- Each segment contains start/end farm states, crop and animal work, input needs, and output targets. Recorded moves and worker assignments are kept outside the runtime library.
- A one-to-one tile remapper and fresh route compiler. Matching preserves crop/animal identity and planting/placement day. Shop composition is not a selector gate.
- A selector that starts from nearby remappable states, then values historical output at visible current prices, deducts declared inputs, and applies a small terminal-investment credit. This is an explicit heuristic, not a learned price forecast.
- Both nearest-state and state-plus-value agents were built. The final benchmark below tests the state-plus-value candidate. A meaningful final ablation of the selector is deferred because their shared executor fails the basic gates.

## Native production validation

**4/12 windows complete; all 4 completed windows exactly match collected output, and all 4 exactly match every ending tile field.** No harness errors occurred.

| Start day | Native windows | Full windows completed |
|---|---:|---:|
| 12 | 2 | 2 |
| 15 | 2 | 1 |
| 18 | 2 | 1 |
| 21 | 2 | 0 |
| 24 | 2 | 0 |
| 27 | 2 | 0 |

The remaining windows fail routing or delivery capacity checks. The harness tries 11 workers, then 12–13 after failure. An accepted window is not merely one that passes its first-day preflight. Physical output means successful HARVEST/COLLECT_FERTILIZER inventory gains; ending-state equality refers to tiles, not cash, worker positions, or sale timing.

Native tests reconstruct the recorded initial state with the official engine. The rival then passes, and historical shop reveals are applied to the test environment. Future shops are not supplied to the executor. These are reconstruction diagnostics, not independent competitive wins.

## Frozen natural-world comparison

Eight development seeds, both seats. The control has 16 games; the candidate has 16 against V56 and 16 against m1. The first two seeds were used during debugging, so this is not a sealed holdout or promotion qualification.

| Policy | Opponent | Wins / ties / losses | Mean final cash margin |
|---|---|---:|---:|
| m1 control | V56 | 9 / 0 / 7 | +1,760 |
| Segment prototype | V56 | 9 / 0 / 7 | -1,682 |
| Segment prototype | m1 | 0 / 4 / 12 | -6,094 |

Against V56, mean margin changes by **-3,442** relative to the same-seed m1 control. Only 9/16 paired games retain identical realized shop sequences. Policy changes alter weed RNG consumption and can therefore alter later shops; this comparison is not a fixed-shop isolation of production effects.

**Runtime also fails:** the offline runner records elapsed decision time but does not enforce Kaggle timeouts. The candidate reaches 21.56 seconds for one action, with 64 calls over one second. These cash results cannot be treated as valid time-limited submission performance.

All 32 candidate games finished with 719 actions, 720 states, reconciled cash ledgers, and no uncaught agent errors.

## Does it actually stitch?

| Opponent | Games with activation | Activated windows | Later execution failures | Changes of donor between active windows |
|---|---:|---:|---:|---:|
| V56 | 9/16 | 21 | 7 | 0 |
| m1 | 10/16 | 23 | 8 | 0 |

Activation is reported separately from winning: an unchanged fallback game supplies no evidence for the new method. Exact crop ages make the current adapter restrictive; it often has no compatible donor after the farm diverges. A sequence of active windows from the same donor is continuation of that donor, not evidence that mixing donors works.

## What the experiment identifies

1. **Whole-window feasibility must be checked before switching.** Current online preflight checks the first day; later delivery or labour failures can send a changed farm back to m1. The native tests distinguish that failure from a successful three-day reconstruction.
2. **Delivery is part of the production plan.** Returning every worker to the shed wastes labour, while relying on midnight deposits can exceed the 100-unit shed. The successful reconstruction uses free midnight deposits within capacity, but the current packing heuristic still fails on several high-output late-game windows.
3. **Current matching is still too tied to donor crop cohorts.** To cover unfamiliar farms, the next adapter should match achievable three-day yield and remaining productive capacity, then translate the donor target into feasible investment and harvest changes. Exact planting-day matching alone cannot do that.
4. **Output matching is not profit matching.** Input procurement, liquidation timing, terminal inventory, worker cost, and shared-market response must be evaluated alongside output. The current-price scoring rule does not prove any of those outcomes.

The useful result is a replay-validated production library and four exact reconstruction fixtures. The next implementation priority is a fast, complete three-day compiler and transition check, then a wider development panel. Adding more leader data or tuning proximity weights before that would confound plan quality with executor failures.

## Reproduction and artifacts

- `scripts/build_umg_segment_library.py`: library extraction and output audit.
- `scripts/build_segment_stitch_agent.py`: standalone experimental agents.
- `scripts/run_native_validation_v3.py`: 12 native-window checks.
- `scripts/benchmark_segment_stitch.py`: fresh-process, frozen-source natural-world runner.
- `results/fresh/segment_stitch/panel_v3/manifest.json`: seeds and source hashes.
- `results/fresh/segment_stitch/panel_v3/summary.json`: match results, timing, activation, and realized output by window.
- `results/fresh/segment_stitch/native_validation_v3.json`: per-window production and full tile comparisons.

m1 and the submitted agent remain unchanged. No Kaggle upload was performed.
