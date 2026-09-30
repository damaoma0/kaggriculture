"""Paired full-game report, including lower tails, runtime and recovery use."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def bootstrap(values):
    a = np.asarray(values, dtype=float)
    samples = np.random.default_rng(20260922).choice(a, size=(20000, len(a)), replace=True).mean(axis=1)
    return np.quantile(samples, [.025, .975]).tolist()


def main():
    p = argparse.ArgumentParser(); p.add_argument('--out', required=True); args = p.parse_args()
    folder = ROOT / args.out
    manifest = json.loads((folder / 'manifest.json').read_text())
    rows = [json.loads(f.read_text()) for f in (folder / 'games').glob('*.json')]
    expected = {(a, o, s, seat) for a in manifest['agents'] for o in manifest['opponents']
                for s in manifest['seeds'] for seat in (0, 1)}
    seen, errors, groups = set(), [], defaultdict(list)
    for name, relative in manifest['source_paths'].items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != manifest['source_hashes'][name]:
            errors.append('frozen_source_changed:' + name)
    for r in rows:
        key = r['agent'], r['opponent'], r['seed'], r['seat']
        if key in seen or key not in expected: errors.append('duplicate_or_unexpected:' + str(key))
        seen.add(key)
        if not r.get('completed') or r.get('errors') or r.get('statuses') != ['DONE', 'DONE'] or not r.get('ledger_verified'):
            errors.append('invalid_game:' + str(key)); continue
        if r.get('actions') != 719 or r.get('states') != 720: errors.append('wrong_horizon:' + str(key))
        if r['own_sha256'] != manifest['source_hashes'][r['agent']]: errors.append('own_hash:' + str(key))
        if r['opponent_sha256'] != manifest['source_hashes'][r['opponent']]: errors.append('opponent_hash:' + str(key))
        for seat, value in ((r['seat'], r['cash']), (1-r['seat'], r['opponent_cash'])):
            ledger = r['daily'][seat][-1]
            if value != 3000 + sum(ledger['revenue'].values()) - sum(ledger['spend'].values()): errors.append('ledger:' + str(key))
        groups[r['agent'], r['opponent']].append(r)
    summary = {'complete': seen == expected and not errors, 'expected': len(expected), 'received': len(rows),
               'errors': errors, 'missing': sorted(expected-seen), 'matchups': {}, 'paired': {}}
    for (a, o), rs in groups.items():
        margins = [r['margin'] for r in rs]
        by_seed = defaultdict(list)
        for r in rs: by_seed[r['seed']].append(r['margin'])
        reports = [r.get('agent_reports', {}).get('own', {}).get('SEGMENT_REPORT', {}) for r in rs]
        metric = {'games': len(rs), 'wins': sum(m > 0 for m in margins), 'ties': sum(m == 0 for m in margins),
                  'losses': sum(m < 0 for m in margins), 'mean_margin': statistics.mean(margins),
                  'mean_cash': statistics.mean(r['cash'] for r in rs), 'worst_margin': min(margins),
                  'worst_decile_mean': statistics.mean(sorted(margins)[:max(1, math.ceil(.1*len(margins)))]),
                  'losses_below_minus10000': sum(m < -10000 for m in margins),
                  'mean_margin_seed_ci': bootstrap([statistics.mean(v) for v in by_seed.values()]),
                  'max_action_seconds': max(r['timing']['own']['max_seconds'] for r in rs),
                  'calls_over_1s': sum(r['timing']['own']['over_1s'] for r in rs),
                  'active_games': sum(bool(t.get('activations')) for t in reports),
                  'activations': sum(t.get('activations', 0) for t in reports),
                  'emergency_steps': sum(t.get('emergency_steps', 0) for t in reports),
                  'maintenance_planned_days': sum(t.get('maintenance_days', 0) for t in reports),
                  'maintenance_rejections': dict(Counter(e['failure']['reason'] for t in reports for e in t.get('maintenance_rejections', []))),
                  'recovery_reasons': dict(Counter(e['reason'] for t in reports for e in t.get('recoveries', []))),
                  'rejection_reasons': dict(Counter(e['failure']['reason'] for t in reports for e in t.get('rejections', [])))}
        summary['matchups'][a + ' vs ' + o] = metric
    for (a, o), rs in groups.items():
        if a == 'mgt_m1' or ('mgt_m1', o) not in groups: continue
        controls = {(r['seed'], r['seat']): r for r in groups['mgt_m1', o]}
        deltas = defaultdict(list); cash = []; same_shops = 0
        for r in rs:
            base = controls[r['seed'], r['seat']]
            deltas[r['seed']].append(r['margin']-base['margin']); cash.append(r['cash']-base['cash'])
            same_shops += r['shops'] == base['shops']
        means = [statistics.mean(v) for v in deltas.values()]
        summary['paired'][a + ' vs ' + o] = {'margin_delta': statistics.mean(means), 'seed_ci': bootstrap(means),
            'cash_delta': statistics.mean(cash), 'better_seeds': sum(v>0 for v in means),
            'unchanged_seeds': sum(v==0 for v in means), 'worse_seeds': sum(v<0 for v in means),
            'same_shop_path_games': same_shops}
    (folder / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__': main()
