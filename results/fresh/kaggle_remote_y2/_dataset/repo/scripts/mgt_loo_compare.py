"""Paired comparison of two tape-router builds over the leave-one-out worlds (scripts/mgt_loo.py results).

usage: mgt_loo_compare.py <candidate> <reference> [arm=loo]
Reports the paired margin / own-cash / rival-cash differences with a bootstrap interval, split by whether the
candidate's sheep overlay acted (when that telemetry is present), and the per-product revenue differences.
"""
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOO = ROOT / 'results' / 'fresh' / 'mg_tape' / 'loo'


def load(agent, arm):
    out = {}
    for p in LOO.glob(f'{agent}-{arm}-*.json'):
        d = json.loads(p.read_text())
        if d.get('final') is not None:
            out[int(d['episode'])] = d
    return out


def boot(xs, n=4000, seed=7):
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(xs) for _ in xs) / len(xs) for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n)]


def line(label, xs):
    if not xs:
        return f'{label:<28} n=0'
    lo, hi = boot(xs) if len(xs) > 2 else (min(xs), max(xs))
    xs2 = sorted(xs)
    return (f'{label:<28} n={len(xs):>2}  mean {sum(xs) / len(xs):>+8.0f}  ({lo:+.0f}..{hi:+.0f})  '
            f'median {xs2[len(xs2) // 2]:>+7.0f}  better {sum(x > 0 for x in xs)}-{sum(x < 0 for x in xs)}')


def main():
    cand, ref = sys.argv[1], sys.argv[2]
    arm = sys.argv[3] if len(sys.argv) > 3 else 'loo'
    a, b = load(cand, arm), load(ref, arm)
    eps = sorted(set(a) & set(b))
    print(f'{cand} vs {ref} ({arm}): {len(eps)} paired worlds')
    print(f'  {cand}: {sum(a[e]["margin"] > 0 for e in eps)}-{sum(a[e]["margin"] <= 0 for e in eps)} '
          f'mean margin {sum(a[e]["margin"] for e in eps) / len(eps):+.0f}; '
          f'{ref}: {sum(b[e]["margin"] > 0 for e in eps)}-{sum(b[e]["margin"] <= 0 for e in eps)} '
          f'mean margin {sum(b[e]["margin"] for e in eps) / len(eps):+.0f}')
    print(line('margin diff', [a[e]['margin'] - b[e]['margin'] for e in eps]))
    print(line('own cash diff', [a[e]['final'] - b[e]['final'] for e in eps]))
    print(line('rival cash diff', [a[e]['rival_final'] - b[e]['rival_final'] for e in eps]))
    print(line('dead commands diff', [a[e].get('no_effect', 0) - b[e].get('no_effect', 0) for e in eps]))

    def acted(d):
        t = d.get('telemetry') or d.get('sheep') or {}
        return bool(t.get('commitments') or t.get('sheep_bought'))

    if any(acted(a[e]) for e in eps):
        fired = [e for e in eps if acted(a[e])]
        print(line('  overlay acted', [a[e]['margin'] - b[e]['margin'] for e in fired]))
        print(line('  overlay idle', [a[e]['margin'] - b[e]['margin'] for e in eps if e not in fired]))
        for e in fired:
            t = a[e].get('telemetry') or a[e].get('sheep') or {}
            yarn = [i + 1 for i, s in enumerate(a[e]['shops'][:8] if isinstance(a[e]['shops'], list) else []) if s == 'YARN_STORE']
            print(f'    {e}: margin {a[e]["margin"] - b[e]["margin"]:>+7.0f} own {a[e]["final"] - b[e]["final"]:>+7.0f} '
                  f'sheep +{t.get("sheep_bought", 0)} commitments {t.get("commitments", 0)} lost {t.get("sheep_lost", 0)} '
                  f'wool {a[e]["sold"].get("WOOL", 0) - b[e]["sold"].get("WOOL", 0):+d} yarn shops {yarn}')
    products = sorted({k for e in eps for k in list(a[e]['revenue']) + list(b[e]['revenue'])})
    rows = [(k, sum(a[e]['revenue'].get(k, 0) - b[e]['revenue'].get(k, 0) for e in eps) / len(eps)) for k in products]
    print('  revenue diff by product: ' + ', '.join(f'{k} {v:+.0f}' for k, v in sorted(rows, key=lambda r: -abs(r[1])) if abs(v) >= 50))
    spend = sorted({k for e in eps for k in list(a[e]['spend']) + list(b[e]['spend'])})
    rows = [(k, sum(a[e]['spend'].get(k, 0) - b[e]['spend'].get(k, 0) for e in eps) / len(eps)) for k in spend]
    print('  spend diff: ' + ', '.join(f'{k} {v:+.0f}' for k, v in sorted(rows, key=lambda r: -abs(r[1])) if abs(v) >= 50))


if __name__ == '__main__':
    main()
