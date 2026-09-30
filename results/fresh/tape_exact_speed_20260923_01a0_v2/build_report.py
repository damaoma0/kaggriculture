"""Assemble the exact-speed evidence after all serial runs finish."""
import ast
import json
import statistics
import run_local as H

H.verify()
summary = json.loads((H.ROOT / 'summary.json').read_text())
edges = json.loads((H.ROOT / 'cache_edge_checks.json').read_text())
prior = H.ROOT.parent / 'tape_exact_speed_20260923_01a0'
structural = json.loads((prior / 'structural_equivalence.json').read_text())
old_source = (prior / 'payload/scripts/value_tape_search_v9.py').read_text()
new_source = (H.PAYLOAD / 'scripts/value_tape_search_v9.py').read_text()
assert old_source.count('maxsize=8192') == 1
assert old_source.replace('maxsize=8192', 'maxsize=32768') == new_source
assert H.sha(H.PROJECT / 'scripts/value_tape_search_v9.py') == H.sha(H.PAYLOAD / 'scripts/value_tape_search_v9.py')
games = [json.loads((H.ROOT / 'full_game' / (name + '.json')).read_text())
         for name in ('2-v56', '5-v56')]
assert all(g['completed'] and g['actions_and_cash_equal'] for g in games)
assert summary['all_semantic_decisions_equal']
metrics = summary['metrics']
def mean(policy, phase, measure='wall_seconds'):
    return metrics[policy][phase][measure]['mean']
warm_reduction = 1 - mean('v9', 'warm') / mean('v8', 'warm')
cpu_reduction = 1 - mean('v9', 'warm', 'cpu_seconds') / mean('v8', 'warm', 'cpu_seconds')
forecast_count = sum(sum(len(v) for v in r['forecasts'].values()) for r in summary['rows']
                     if r['policy'] == 'v8' and r['repeat'] == 0)
lines = [
    '# Exact tape-search speed improvements', '',
    '## Result', '',
    f'V9 preserves the V8 search decisions and forecasts while reducing mean warm '
    f'local wall time by **{100*warm_reduction:.1f}%** '
    f'({mean("v8", "warm"):.2f}s → {mean("v9", "warm"):.2f}s). '
    f'Mean process CPU time falls **{100*cpu_reduction:.1f}%**. '
    'This is an exact implementation optimization of V8; V8 itself still uses '
    'an approximate top-two scout to decide which candidates receive more worlds.', '',
    '## What changed', '',
    '1. One decision-scoped rival production profile replaces eight identical '
    'profile simulations. Public-board donor ranking is built once: **115 '
    'board-distance calculations instead of 928**. Future-shop reranking, '
    'donor choices, trade corrections and all eight scenario contents stay equal.',
    '2. The private simulated agent counts board mismatches using XOR and '
    'packed 16-bit tile labels. A bounded, content-addressed cache holds '
    '32,768 encodings. List mutation cannot produce a stale encoding. Unusual '
    'labels, unequal lengths and unhashable labels use the original comparison.',
    '3. V9 executes V8\'s existing candidate-search and admission function with '
    'private dependency bindings. Cohort protection, failed-hire checks, risk '
    'thresholds, three-day commitments and complete-eight-world admission are unchanged.', '',
    '## Serial local benchmark', '',
    'Six frozen checkpoints: two each at D12, D15 and D18, with four accepted '
    'commitments and two unchanged controls. Three policies run in separate '
    'fresh processes, one worker at a time. All six policy orders are used once. '
    'Each process makes one cold and two warm complete `choose` calls. No '
    'forecast cache is used. Source and input hashes are verified before each worker. '
    'Cold timing includes the first choose call and its lazy runtime construction; '
    'Python and module import time are excluded here and included separately '
    'in the full-game accounting.', '',
    '| Full choose measurement | V8 | Shared scenarios only | V9: both changes |',
    '|---|---:|---:|---:|',
]
for label, phase, metric in [('Warm mean wall time', 'warm', 'wall_seconds'),
                             ('Warm median wall time', 'warm', 'wall_seconds'),
                             ('Warm mean CPU time', 'warm', 'cpu_seconds'),
                             ('Cold mean wall time', 'cold', 'wall_seconds')]:
    key = 'median' if 'median' in label else 'mean'
    values = [metrics[p][phase][metric][key] for p in ('v8', 'worlds', 'v9')]
    lines.append('| ' + label + ' | ' + ' | '.join(f'{v:.3f}s' for v in values) + ' |')
lines += ['', '| Checkpoint | V8 warm mean | V9 warm mean | Reduction |',
          '|---|---:|---:|---:|']
for c in summary['comparisons']:
    old, new = [c['warm'][p]['wall_seconds'] for p in ('v8', 'v9')]
    lines.append(f'| {c["case"]} | {old:.3f}s | {new:.3f}s | {100*(1-new/old):.1f}% |')
lines += ['', 'The host is the shared Windows 11 laptop, Python 3.12.14, 32 logical '
    'CPUs and approximately 4.10 GiB free memory at panel start. Other agent '
    'systems may affect scheduling and processor speed. Process CPU time also '
    'depends on processor speed; it is not a hardware-independent work count. '
    'These local times must not be directly compared with the earlier Kaggle '
    'Xeon timings. Warm samples number 12 per policy; cold samples number six.', '',
    '## Verification', '',
    f'- **{summary["decisions"]}/{summary["decisions"]} complete decisions** agree in '
    'all non-timing fields except the expected planner source hash, across all '
    'three versions and repetitions. Simulated turns and rollout counts also agree.',
    f'- **{forecast_count} distinct case/route/world forecasts** are exactly equal '
    'across implementations; repeated forecasts and every compared historical label agree.',
    f'- **{structural["equal_worlds"]} worlds across {structural["checkpoints"]} checkpoints** '
    'have identical full scenario contents. Input and output mutation isolation pass. '
    'This structural run used the first snapshot; the report builder verifies '
    'that its only source difference from the final snapshot is the cache capacity.',
    f'- **{structural["hamming_checks"] + edges["packed_lane_and_mutation_checks"]} '
    'focused board-comparison checks** cover random labels, individual character '
    'bits in every tile, unequal lengths, fallback labels, list mutation and eviction.',
    '- Cancellation restores input ownership, engine hooks, deadline state and '
    'cohort guards. An A → B → A input sequence after cancellation reproduces '
    'the original full decisions and available historical forecasts.', '',
    '## Complete-game checks and time bank', '',
    'Two prespecified existing V8 recovery games against the frozen V56 opponent '
    'were replayed in separate processes, one per seat. The opponent entry is '
    '`e410_agent`. Every action, both ending cash balances, and all three reveal '
    'decisions match the recorded V8 game. Both ledgers reconcile. These are '
    'regression checks, not new independent profit evidence.', '',
    '| Known game | Retained margin recovery | D12 / D15 / D18 call time | Remaining overage |',
    '|---|---:|---:|---:|']
for g in games:
    times = ' / '.join(f'{r["seconds"]:.2f}s' for r in g['reveals'])
    lines.append(f'| {g["case"]} | +{g["retained_margin_gain"]:,.0f} | {times} | '
                 f'{g["remaining_overage_seconds"]:.2f}s |')
lines += ['', 'For this diagnostic, the starting bank is 60 seconds, and each own '
    'turn consumes `max(0, search + action time - 1 second)`. Planner imports and '
    'native-agent construction are additionally charged on the first turn. '
    'Opponent execution, engine stepping and report writing are excluded. '
    'The subtraction matches the bundled framework. No competition subprocess, '
    'serialization overhead or actual competition hardware is reproduced, and '
    'the manual simulator records rather than enforces timeout.', '',
    f'Measured bank exhaustion: **{sum(g["measured_bank_exhausted"] for g in games)}/2 games**. '
    'This supports a small number of reveal-time searches on this diagnostic '
    'panel; a bank-aware deployment policy and the actual submission runner '
    'remain to be validated.', '',
    'Deadline probes remain cooperative:', '',
    '| Requested budget | Actual wall time | Selected route |',
    '|---|---:|---|']
for p in edges['deadline_probes']:
    lines.append(f'| {p["budget"]:.1f}s | {p["wall_seconds"]:.3f}s | {p["selected"]} |')
lines += ['', 'An unfinished forecast cannot justify a switch. These deadlines '
    'are not hard bounds on initialization or an individual engine call.', '',
    '## Failed first implementation', '',
    'The first board cache held only 8,192 encodings. That is below a full '
    'rollout\'s board working set. On the strawberry checkpoint, each warm '
    'decision rebuilt **70,956 encodings** and the combined version was slower '
    'than V8. The trial was stopped, and all completed raw samples were kept '
    'under `tape_exact_speed_20260923_01a0/`. The final cache holds the full '
    'immutable library plus room for observed boards. Repeating the same '
    'checkpoint now adds no encoding misses. The cache remains bounded.', '',
    '## Use and artifacts', '',
    'Research entry: `scripts/value_tape_search_v9.py`, with '
    '`choose(obs, own_memory, count=7, keep=2, budget_seconds=None)`. Use one '
    'serial runtime per process. This modular research selector is not a '
    'self-contained competition submission.', '',
    'Final experiment: `results/fresh/tape_exact_speed_20260923_01a0_v2/`:', '',
    '- `payload/manifest.json`: 150 frozen source/input files.',
    '- `summary.json`, `measurements/`, `hardware.json`: complete latency and equality records.',
    '- `cache_edge_checks.json`: cancellation, mutation and packed-lane checks.',
    '- `full_game/`: full decisions, exact-game checks and per-turn time-bank accounting.',
    '- `hamming_microbenchmark.json`: cache-size diagnostic, not end-to-end performance.',
    '- `run_local.py`, `check_cache_edges.py`, `check_full_game.py`: reproducible serial drivers.', '',
    'The production `agents/mgt_m1.py` remains byte-identical at SHA256 '
    '`1152ef2e12c4535dbc381b9c54ac7d7a0b1a9ad3d0a8018a7567dcf5c4a52470`. '
    'No submission or production selection was changed.', '',
    'The next deployment step is to allocate the measured overage bank across '
    'reveals and retain a reserve for native execution. Faster physical '
    'rollouts and continuation-value models remain possible subsequent improvements.', '']
target = H.PROJECT / 'docs/value_tape_exact_speed_20260923.md'
target.write_text('\n'.join(lines), encoding='utf-8')
H.write(H.ROOT / 'report_audit.json', dict(warm_wall_reduction=warm_reduction,
    warm_cpu_reduction=cpu_reduction, exact_forecasts=forecast_count,
    inherited_structural_validation=True, only_change_from_first_snapshot='cache capacity',
    report_sha256=H.sha(target), planner_sha256=H.sha(H.PAYLOAD / 'scripts/value_tape_search_v9.py'),
    native_sha256=H.sha(H.PROJECT / 'agents/mgt_m1.py')))
print(json.dumps(dict(report=str(target), warm_wall_reduction=warm_reduction,
    warm_cpu_reduction=cpu_reduction, exact_forecasts=forecast_count)), flush=True)
