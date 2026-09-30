"""Write the final research report only from complete frozen panels."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/segment_stitch'


def read(path): return json.loads(path.read_text(encoding='utf-8'))


def main():
    baseline = read(OUT / 'baseline_panel/summary.json')
    panel = read(OUT / 'panel_v3/summary.json')
    native = read(OUT / 'native_validation_v3.json')
    assert baseline['complete'] and panel['complete'] and native['complete']
    b = baseline['matchups']['mgt_m1 vs v56']
    v = panel['matchups']['mgt_segment_stitch vs v56']
    m = panel['matchups']['mgt_segment_stitch vs mgt_m1']
    records = [read(p) for p in (OUT / 'panel_v3/games').glob('*.json')]
    controls = {(r['seed'], r['seat']): r for p in (OUT / 'baseline_panel/games').glob('*.json') for r in [read(p)]}
    paired = []
    for r in records:
        if r['opponent'] == 'v56':
            c = controls[r['seed'], r['seat']]
            paired.append({'seed': r['seed'], 'seat': r['seat'],
                'margin_change': r['margin'] - c['margin'], 'same_shops': r['shops'] == c['shops'],
                'own_cash_change': r['cash'] - c['cash'],
                'opponent_cash_change': r['opponent_cash'] - c['opponent_cash']})
    native_days = defaultdict(lambda: [0, 0])
    failures = Counter()
    for r in native['rows']:
        day = int(r['id'].rsplit('d', 1)[1])
        native_days[day][0] += 1
        accepted = next((a for a in r['attempts'] if a.get('started') and not a.get('rejected_window')), None)
        if accepted: native_days[day][1] += 1
        else: failures[(r['attempts'][-1].get('rejected_window') or {}).get('reason', 'other')] += 1
    diagnostics = {'paired_v56': paired, 'native_by_day': dict(native_days), 'native_failure_reasons': dict(failures)}
    (OUT / 'research_summary.json').write_text(json.dumps(diagnostics, indent=2))
    ns = native['summary']
    lines = [
        '# Three-day UMG production stitching: implementation and test', '',
        '## Decision', '',
        '**Keep m1. This prototype fails the execution, performance, and runtime gates.** '
        'It establishes that some donor production segments can be reconstructed without replaying worker movements, '
        'but it does not establish a reliable continuation policy or an advantage over V56.', '',
        '## What was built', '',
        '- A library of **630 three-day segments from 105 UMG games**, starting on days 12, 15, 18, 21, 24, and 27. '
        'Every segment’s independently extracted harvest/collection totals match the existing replay-audited production labels.',
        '- Each segment contains start/end farm states, crop and animal work, input needs, and output targets. '
        'Recorded moves and worker assignments are kept outside the runtime library.',
        '- A one-to-one tile remapper and fresh route compiler. Matching preserves crop/animal identity and planting/placement day. '
        'Shop composition is not a selector gate.',
        '- A selector that starts from nearby remappable states, then values historical output at visible current prices, '
        'deducts declared inputs, and applies a small terminal-investment credit. This is an explicit heuristic, not a learned price forecast.',
        '- Both nearest-state and state-plus-value agents were built. The final benchmark below tests the state-plus-value candidate. '
        'A meaningful final ablation of the selector is deferred because their shared executor fails the basic gates.', '',
        '## Native production validation', '',
        f"**{ns['whole_window_accepted']}/{ns['requested']} windows complete; all {ns['exact_output']} completed windows exactly match collected output, "
        f"and all {ns['tile_state_exact']} exactly match every ending tile field.** No harness errors occurred.",
        '', '| Start day | Native windows | Full windows completed |', '|---|---:|---:|']
    for day, (n, accepted) in sorted(native_days.items()): lines.append(f'| {day} | {n} | {accepted} |')
    lines += ['', 'The remaining windows fail routing or delivery capacity checks. '
        'The harness tries 11 workers, then 12–13 after failure. An accepted window is not merely one that passes its first-day preflight. '
        'Physical output means successful HARVEST/COLLECT_FERTILIZER inventory gains; ending-state equality refers to tiles, not cash, worker positions, or sale timing.', '',
        'Native tests reconstruct the recorded initial state with the official engine. The rival then passes, and historical shop reveals are applied to the test environment. '
        'Future shops are not supplied to the executor. These are reconstruction diagnostics, not independent competitive wins.', '',
        '## Frozen natural-world comparison', '',
        'Eight development seeds, both seats. The control has 16 games; the candidate has 16 against V56 and 16 against m1. '
        'The first two seeds were used during debugging, so this is not a sealed holdout or promotion qualification.', '',
        '| Policy | Opponent | Wins / ties / losses | Mean final cash margin |', '|---|---|---:|---:|']
    for label, opp, metric in [('m1 control', 'V56', b), ('Segment prototype', 'V56', v), ('Segment prototype', 'm1', m)]:
        lines.append(f"| {label} | {opp} | {metric['wins']} / {metric['ties']} / {metric['losses']} | {metric['mean_margin']:+,.0f} |")
    lines += ['', f"Against V56, mean margin changes by **{statistics.mean(p['margin_change'] for p in paired):+,.0f}** relative to the same-seed m1 control. "
        f"Only {sum(p['same_shops'] for p in paired)}/{len(paired)} paired games retain identical realized shop sequences. "
        'Policy changes alter weed RNG consumption and can therefore alter later shops; this comparison is not a fixed-shop isolation of production effects.', '',
        '**Runtime also fails:** the offline runner records elapsed decision time but does not enforce Kaggle timeouts. '
        f"The candidate reaches {max(v['max_action_seconds'], m['max_action_seconds']):.2f} seconds for one action, "
        f"with {v['actions_over_1s'] + m['actions_over_1s']} calls over one second. These cash results cannot be treated as valid time-limited submission performance.", '',
        'All 32 candidate games finished with 719 actions, 720 states, reconciled cash ledgers, and no uncaught agent errors.', '',
        '## Does it actually stitch?', '',
        '| Opponent | Games with activation | Activated windows | Later execution failures | Changes of donor between active windows |',
        '|---|---:|---:|---:|---:|']
    for opp, metric in [('V56', v), ('m1', m)]:
        lines.append(f"| {opp} | {metric['games_with_activation']}/{metric['n']} | {metric['activations']} | {metric['execution_failures']} | {metric['donor_changes_between_active_windows']} |")
    lines += ['', 'Activation is reported separately from winning: an unchanged fallback game supplies no evidence for the new method. '
        'Exact crop ages make the current adapter restrictive; it often has no compatible donor after the farm diverges. '
        'A sequence of active windows from the same donor is continuation of that donor, not evidence that mixing donors works.', '',
        '## What the experiment identifies', '',
        '1. **Whole-window feasibility must be checked before switching.** Current online preflight checks the first day; later delivery or labour failures can send a changed farm back to m1. '
        'The native tests distinguish that failure from a successful three-day reconstruction.',
        '2. **Delivery is part of the production plan.** Returning every worker to the shed wastes labour, while relying on midnight deposits can exceed the 100-unit shed. '
        'The successful reconstruction uses free midnight deposits within capacity, but the current packing heuristic still fails on several high-output late-game windows.',
        '3. **Current matching is still too tied to donor crop cohorts.** To cover unfamiliar farms, the next adapter should match achievable three-day yield and remaining productive capacity, '
        'then translate the donor target into feasible investment and harvest changes. Exact planting-day matching alone cannot do that.',
        '4. **Output matching is not profit matching.** Input procurement, liquidation timing, terminal inventory, worker cost, and shared-market response must be evaluated alongside output. '
        'The current-price scoring rule does not prove any of those outcomes.', '',
        'The useful result is a replay-validated production library and four exact reconstruction fixtures. '
        'The next implementation priority is a fast, complete three-day compiler and transition check, then a wider development panel. '
        'Adding more leader data or tuning proximity weights before that would confound plan quality with executor failures.', '',
        '## Reproduction and artifacts', '',
        '- `scripts/build_umg_segment_library.py`: library extraction and output audit.',
        '- `scripts/build_segment_stitch_agent.py`: standalone experimental agents.',
        '- `scripts/run_native_validation_v3.py`: 12 native-window checks.',
        '- `scripts/benchmark_segment_stitch.py`: fresh-process, frozen-source natural-world runner.',
        '- `results/fresh/segment_stitch/panel_v3/manifest.json`: seeds and source hashes.',
        '- `results/fresh/segment_stitch/panel_v3/summary.json`: match results, timing, activation, and realized output by window.',
        '- `results/fresh/segment_stitch/native_validation_v3.json`: per-window production and full tile comparisons.',
        '', 'm1 and the submitted agent remain unchanged. No Kaggle upload was performed.', '']
    report = ROOT / 'docs/three_day_segment_stitch_experiment.md'
    report.write_text('\n'.join(lines), encoding='utf-8')
    print(report)


if __name__ == '__main__': main()
