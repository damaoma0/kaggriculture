"""Summarize frozen segment experiments, retaining failures and seed clusters."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import statistics
from report_random_v56 import outcome


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--out', required=True)
    args = p.parse_args()
    root = Path(args.out)
    manifest = json.loads((root / 'manifest.json').read_text())
    expected = {(a, b, s, t) for a in manifest['agents'] for b in manifest['opponents']
                for s in manifest['seeds'] for t in (0, 1)}
    groups = defaultdict(list)
    records = {}
    errors = []
    for path in sorted((root / 'games').glob('*.json')):
        r = json.loads(path.read_text())
        key = (r['agent'], r['opponent'], r['seed'], r['seat'])
        if key in records or key not in expected:
            errors.append({'file': str(path), 'reason': 'duplicate_or_unexpected'})
        records[key] = r
        valid = (r.get('completed') and r.get('states') == 720 and r.get('actions') == 719
                 and r.get('ledger_verified') and r.get('statuses') == ['DONE', 'DONE']
                 and not r.get('errors')
                 and r.get('own_sha256') == manifest['source_hashes'][r['agent']]
                 and r.get('opponent_sha256') == manifest['source_hashes'][r['opponent']])
        if not valid:
            errors.append({'file': str(path), 'reason': 'invalid_game', 'error': r.get('error')})
            continue
        groups[key[:2]].append(r)
    summary = {'complete': set(records) == expected and not errors,
               'expected': len(expected), 'received': len(records),
               'missing': sorted(expected - records.keys()), 'errors': errors, 'matchups': {}}
    for (a, b), rs in sorted(groups.items()):
        metric = outcome(rs)
        metric['max_action_seconds'] = max(r['timing']['own']['max_seconds'] for r in rs)
        metric['actions_over_1s'] = sum(r['timing']['own']['over_1s'] for r in rs)
        reports = [r.get('agent_reports', {}).get('own', {}).get('SEGMENT_REPORT') for r in rs]
        metric['activations'] = sum(t.get('activations', 0) for t in reports if t)
        metric['execution_failures'] = sum(len(t.get('failures', [])) for t in reports if t)
        metric['games_with_activation'] = sum(bool(t and t.get('activations')) for t in reports)
        metric['donor_changes_between_active_windows'] = sum(
            a['id'].split(':')[0] != b['id'].split(':')[0]
            for t in reports if t for a, b in zip(t.get('decisions', []), t.get('decisions', [])[1:]))
        metric['coverage_by_day'] = {}
        for day in (12, 15, 18, 21, 24, 27):
            attempts = [a for t in reports if t for a in t.get('attempts', []) if a['day'] == day]
            metric['coverage_by_day'][str(day)] = {'attempts': len(attempts),
                'remappable': sum(a['remappable'] > 0 for a in attempts),
                'activated': sum(d['day'] == day for t in reports if t for d in t.get('decisions', []))}
        metric['observed_output_windows'] = []
        for row, report in zip(rs, reports):
            if not report: continue
            daily = row['daily'][row['seat']]
            for decision in report.get('decisions', []):
                day = decision['day']
                start = daily[day]['physical']
                end = daily[min(day + 3, len(daily) - 1)]['physical']
                target = report.get('outputs', {}).get(str(day), {})
                actual = {p: end.get('produced:' + p, 0) - start.get('produced:' + p, 0) for p in target}
                metric['observed_output_windows'].append({'seed': row['seed'], 'seat': row['seat'],
                    'day': day, 'target': target, 'actual_including_any_fallback': actual,
                    'difference': {p: actual[p] - target[p] for p in target}})
        metric['segment_reports'] = [dict(seed=r['seed'], seat=r['seat'], report=t)
                                     for r, t in zip(rs, reports) if t is not None]
        summary['matchups'][a + ' vs ' + b] = metric
    (root / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    # Keep per-game diagnostics in JSON; concise human-readable table here.
    lines = ['# Three-day segment stitching experiment', '',
             'Complete panel: **%s**. %s/%s game records.' % (summary['complete'], len(records), len(expected)), '',
             '| Policy | Opponent | Games | Wins–ties–losses | Mean cash margin | Score 95% seed-cluster interval |',
             '|---|---|---:|---:|---:|---|']
    for (a, b), rs in sorted(groups.items()):
        m = summary['matchups'][a + ' vs ' + b]
        lo, hi = m['world_cluster_score_ci']
        lines.append(f"| {a} | {b} | {m['n']} | {m['wins']}–{m['ties']}–{m['losses']} | {m['mean_margin']:+,.0f} | {lo:.1%}–{hi:.1%} |")
    lines += ['', 'Both seats of one random seed are one statistical cluster. This is an experimental panel, not an Elo estimate or promotion qualification.', '']
    (root / 'summary.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k != 'matchups'}))
    for name, m in summary['matchups'].items():
        print(name, json.dumps({k: v for k, v in m.items() if k not in ('segment_reports', 'observed_output_windows')}))


if __name__ == '__main__':
    main()
