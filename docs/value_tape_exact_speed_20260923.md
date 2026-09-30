# Exact tape-search speed improvements

## Result

V9 preserves the V8 search decisions and forecasts while reducing mean warm local wall time by **14.4%** (15.70s → 13.44s). Mean process CPU time falls **14.4%**. This is an exact implementation optimization of V8; V8 itself still uses an approximate top-two scout to decide which candidates receive more worlds.

## What changed

1. One decision-scoped rival production profile replaces eight identical profile simulations. Public-board donor ranking is built once: **115 board-distance calculations instead of 928**. Future-shop reranking, donor choices, trade corrections and all eight scenario contents stay equal.
2. The private simulated agent counts board mismatches using XOR and packed 16-bit tile labels. A bounded, content-addressed cache holds 32,768 encodings. List mutation cannot produce a stale encoding. Unusual labels, unequal lengths and unhashable labels use the original comparison.
3. V9 executes V8's existing candidate-search and admission function with private dependency bindings. Cohort protection, failed-hire checks, risk thresholds, three-day commitments and complete-eight-world admission are unchanged.

## Serial local benchmark

Six frozen checkpoints: two each at D12, D15 and D18, with four accepted commitments and two unchanged controls. Three policies run in separate fresh processes, one worker at a time. All six policy orders are used once. Each process makes one cold and two warm complete `choose` calls. No forecast cache is used. Source and input hashes are verified before each worker. Cold timing includes the first choose call and its lazy runtime construction; Python and module import time are excluded here and included separately in the full-game accounting.

| Full choose measurement | V8 | Shared scenarios only | V9: both changes |
|---|---:|---:|---:|
| Warm mean wall time | 15.695s | 14.083s | 13.435s |
| Warm median wall time | 17.375s | 15.571s | 15.044s |
| Warm mean CPU time | 15.599s | 13.979s | 13.350s |
| Cold mean wall time | 16.811s | 15.260s | 14.698s |

| Checkpoint | V8 warm mean | V9 warm mean | Reduction |
|---|---:|---:|---:|
| generalization-0-v56-d18 | 13.041s | 11.042s | 15.3% |
| generalization-4-sixday-d18 | 6.119s | 4.561s | 25.5% |
| generalization-5-pasture-d15 | 16.233s | 13.889s | 14.4% |
| historical-111262874-12-d12 | 18.608s | 16.092s | 13.5% |
| historical-111269605-15-d15 | 18.565s | 16.165s | 12.9% |
| historical-111287532-12-d12 | 21.605s | 18.861s | 12.7% |

The host is the shared Windows 11 laptop, Python 3.12.14, 32 logical CPUs and approximately 4.10 GiB free memory at panel start. Other agent systems may affect scheduling and processor speed. Process CPU time also depends on processor speed; it is not a hardware-independent work count. These local times must not be directly compared with the earlier Kaggle Xeon timings. Warm samples number 12 per policy; cold samples number six.

## Verification

- **54/54 complete decisions** agree in all non-timing fields except the expected planner source hash, across all three versions and repetitions. Simulated turns and rollout counts also agree.
- **124 distinct case/route/world forecasts** are exactly equal across implementations; repeated forecasts and every compared historical label agree.
- **600 worlds across 75 checkpoints** have identical full scenario contents. Input and output mutation isolation pass. This structural run used the first snapshot; the report builder verifies that its only source difference from the final snapshot is the cache capacity.
- **4404 focused board-comparison checks** cover random labels, individual character bits in every tile, unequal lengths, fallback labels, list mutation and eviction.
- Cancellation restores input ownership, engine hooks, deadline state and cohort guards. An A → B → A input sequence after cancellation reproduces the original full decisions and available historical forecasts.

## Complete-game checks and time bank

Two prespecified existing V8 recovery games against the frozen V56 opponent were replayed in separate processes, one per seat. The opponent entry is `e410_agent`. Every action, both ending cash balances, and all three reveal decisions match the recorded V8 game. Both ledgers reconcile. These are regression checks, not new independent profit evidence.

| Known game | Retained margin recovery | D12 / D15 / D18 call time | Remaining overage |
|---|---:|---:|---:|
| 2-v56 | +2,410 | 24.03s / 9.68s / 10.77s | 17.44s |
| 5-v56 | +793 | 23.63s / 7.74s / 9.62s | 20.97s |

For this diagnostic, the starting bank is 60 seconds, and each own turn consumes `max(0, search + action time - 1 second)`. Planner imports and native-agent construction are additionally charged on the first turn. Opponent execution, engine stepping and report writing are excluded. The subtraction matches the bundled framework. No competition subprocess, serialization overhead or actual competition hardware is reproduced, and the manual simulator records rather than enforces timeout.

Measured bank exhaustion: **0/2 games**. This supports a small number of reveal-time searches on this diagnostic panel; a bank-aware deployment policy and the actual submission runner remain to be validated.

Deadline probes remain cooperative:

| Requested budget | Actual wall time | Selected route |
|---|---:|---|
| 0.0s | 0.261s | None |
| 0.8s | 0.812s | None |

An unfinished forecast cannot justify a switch. These deadlines are not hard bounds on initialization or an individual engine call.

## Failed first implementation

The first board cache held only 8,192 encodings. That is below a full rollout's board working set. On the strawberry checkpoint, each warm decision rebuilt **70,956 encodings** and the combined version was slower than V8. The trial was stopped, and all completed raw samples were kept under `tape_exact_speed_20260923_01a0/`. The final cache holds the full immutable library plus room for observed boards. Repeating the same checkpoint now adds no encoding misses. The cache remains bounded.

## Use and artifacts

Research entry: `scripts/value_tape_search_v9.py`, with `choose(obs, own_memory, count=7, keep=2, budget_seconds=None)`. Use one serial runtime per process. This modular research selector is not a self-contained competition submission.

Final experiment: `results/fresh/tape_exact_speed_20260923_01a0_v2/`:

- `payload/manifest.json`: 150 frozen source/input files.
- `summary.json`, `measurements/`, `hardware.json`: complete latency and equality records.
- `cache_edge_checks.json`: cancellation, mutation and packed-lane checks.
- `full_game/`: full decisions, exact-game checks and per-turn time-bank accounting.
- `hamming_microbenchmark.json`: cache-size diagnostic, not end-to-end performance.
- `run_local.py`, `check_cache_edges.py`, `check_full_game.py`: reproducible serial drivers.

The production `agents/mgt_m1.py` remains byte-identical at SHA256 `1152ef2e12c4535dbc381b9c54ac7d7a0b1a9ad3d0a8018a7567dcf5c4a52470`. No submission or production selection was changed.

The next deployment step is to allocate the measured overage bank across reveals and retain a reserve for native execution. Faster physical rollouts and continuation-value models remain possible subsequent improvements.
