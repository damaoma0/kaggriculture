"""Report for a Kaggle arms run (path_trial.py games.json + the fetched multi files): per arm wins (final ours > rival),
mean margin, paired difference to a base arm (bootstrap 95%), win flips, seconds per game, and the tier logs' polish /
collect-at-floor counters when present.

usage: kgr_arms_report.py <out dir with games.json> <BASE> [ARM,...]"""
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def margin(arm, ep):
    p = ROOT / 'results/fresh/sector_20260925/multi' / arm / f'{ep}.json'
    if not p.exists():
        return None, None
    d = json.loads(p.read_text())
    m = d['money']
    k = max(m, key=int)
    return (m[k][0] - m[k][1]) if int(k) >= 30 else None, d


def main():
    out, base = Path(sys.argv[1]), sys.argv[2]
    rows = json.loads((ROOT / out / 'games.json').read_text())
    arms = sys.argv[3].split(',') if len(sys.argv) > 3 else sorted({r['arm'] for r in rows})
    eps = sorted({r['game'].split(':')[1] for r in rows})
    secs = Counter()
    nsec = Counter()
    for r in rows:
        secs[r['arm']] += r['seconds']
        nsec[r['arm']] += 1
        if r['err']:
            print('FAILED', r['arm'], r['game'], r['err'][-300:])
    M = {a: {e: margin(a, e)[0] for e in eps} for a in set(arms) | {base}}
    print(f'{len(eps)} worlds')
    for a in arms:
        v = [M[a][e] for e in eps if M[a][e] is not None]
        line = f'{a:11s} wins {sum(x > 0 for x in v)}/{len(v)} mean {sum(v) / max(1, len(v)):+7.0f} | {secs[a] / max(1, nsec[a]):5.0f} s/game'
        if a != base:
            d = [M[a][e] - M[base][e] for e in eps if M[a][e] is not None and M[base][e] is not None]
            if d:
                random.seed(1)
                bs = sorted(sum(random.choice(d) for _ in d) / len(d) for _ in range(4000))
                fl = [(e, round(M[base][e]), round(M[a][e])) for e in eps if M[a][e] is not None and M[base][e] is not None
                      and (M[a][e] > 0) != (M[base][e] > 0)]
                line += f' | vs {base}: {sum(d) / len(d):+6.0f} (95% {bs[100]:+.0f}..{bs[3900]:+.0f}), better {sum(x > 0 for x in d)} worse {sum(x < 0 for x in d)}; flips {fl}'
        print(line)
    print('\nper world margin:')
    print(f'{"world":10s} ' + ' '.join(f'{a:>10s}' for a in arms))
    for e in eps:
        print(f'{e:10s} ' + ' '.join(f'{M[a][e]:+10.0f}' if M[a][e] is not None else f'{"-":>10s}' for a in arms))
    for a in arms:
        pol = Counter()
        cf = 0
        for e in eps:
            d = margin(a, e)[1]
            if not d:
                continue
            for day, T in d['tier_days'].items():
                p = T.get('polish')
                if p:
                    pol['days'] += 1
                    pol['gain'] += p.get('gain', 0)
                    for k, v in (p.get('added') or {}).items():
                        pol['add ' + k] += v
                    for k, v in (p.get('dropped') or {}).items():
                        pol['drop ' + k] += v
        if pol:
            print(f'\n{a} polish per world: ' + ', '.join(f'{k} {v / len(eps):.1f}' for k, v in sorted(pol.items())))


if __name__ == '__main__':
    main()
