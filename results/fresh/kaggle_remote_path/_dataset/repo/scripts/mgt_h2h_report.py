"""Head to head: live <agent> against Mother-Goose's ORIGINAL recorded tape, in her recorded worlds.

Reads results/fresh/mg_tape/loo/mgtape_vs_<agent>-<arm>-<episode>.json (written by mgt_loo.py, arms mg_vs and
mg_vs_only). Margins are reported from OUR side (agent minus her tape). The frozen-tape handicap (her tape cannot
react) was calibrated at -2,468 for a policy like our old benchmark (docs/tape_vs_bench.md); "net" adds it to her.

Usage: python mgt_h2h_report.py <agent> [offset=80] [n=128]
"""
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOO = ROOT / 'results/fresh/mg_tape/loo'
HANDICAP = 2468


def ci(xs, n=10000, seed=7):
    rng = random.Random(seed)
    k = len(xs)
    means = sorted(sum(rng.choices(xs, k=k)) / k for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n)]


def wtl(xs):
    return f'{sum(1 for x in xs if x > 0)}-{sum(1 for x in xs if x == 0)}-{sum(1 for x in xs if x < 0)}'


def line(label, xs):
    lo, hi = ci(xs)
    return f'  {label:<34} n={len(xs):<4} W-T-L {wtl(xs):<10} mean {sum(xs) / len(xs):>+8,.0f}  (95% CI {lo:+,.0f} to {hi:+,.0f})'


def main():
    agent = sys.argv[1]
    off = int(sys.argv[2]) if len(sys.argv) > 2 else 80
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 128
    files = sorted(p for s in ('56266758', '56266899') for p in (ROOT / 'data/mg_tapes' / s).glob('*.json.gz'))
    random.Random(20260920).shuffle(files)
    eps = [p.name.split('.')[0] for p in files[off:off + n]]
    rows = {}
    for arm in ('mg_vs', 'mg_vs_only'):
        rows[arm] = {}
        for ep in eps:
            f = LOO / f'mgtape_vs_{agent}-{arm}-{ep}.json'
            if f.exists():
                rows[arm][ep] = json.loads(f.read_text(encoding='utf-8'))
    out = {}
    for arm, title in (('mg_vs', 'A. LADDER CASE: her tape for this world is NOT in our library (router picks a neighbour)'),
                       ('mg_vs_only', 'B. SAME PLAN: we are restricted to her tape for this world (repairs + overlay only)')):
        R = rows[arm]
        if not R:
            continue
        ours = [-r['margin'] for r in R.values()]
        print(f'\n{title}')
        print(line('raw (ours minus her tape)', ours))
        print(line(f'net of tape handicap ({HANDICAP:,})', [x - HANDICAP for x in ours]))
        for seat in (0, 1):
            xs = [-r['margin'] for r in R.values() if r['seat'] == 1 - seat]
            if xs:
                print(line(f'  our seat {seat}', xs))
        k = len(R)
        print(f'  finals: ours {sum(r["rival_final"] for r in R.values()) / k:,.0f}, her tape {sum(r["final"] for r in R.values()) / k:,.0f}')
        print(f'  her tape validity: commands with no effect {sum(r["no_effect"] for r in R.values()) / k:.1f} a game, '
              f'commands to a hand that was never hired {sum(r["missing"] for r in R.values()) / k:.1f}')
        prod = Counter()
        for r in R.values():
            for p, v in (r.get('rival_revenue') or {}).items():
                prod[p] += v
            for p, v in (r.get('revenue') or {}).items():
                prod[p] -= v
        print('  revenue by product, ours minus hers: ' + ', '.join(f'{p} {v / k:+,.0f}' for p, v in sorted(prod.items(), key=lambda kv: kv[1])))
        if all('rival_spend' in r for r in R.values()):
            sp = Counter()
            for r in R.values():
                for c, v in r['rival_spend'].items():
                    sp[c] += v
                for c, v in r['spend'].items():
                    sp[c] -= v
            big = [(c, v / k) for c, v in sp.items() if abs(v / k) >= 50]
            print('  spending, ours minus hers (|x| >= 50): ' + ', '.join(f'{c} {v:+,.0f}' for c, v in sorted(big, key=lambda kv: kv[1])))
            print(f'  total revenue {sum(prod.values()) / k:+,.0f}, total spending {sum(sp.values()) / k:+,.0f}')
        out[arm] = dict(n=k, mean=sum(ours) / k, ci=ci(ours), wtl=wtl(ours))
    both = [ep for ep in eps if ep in rows['mg_vs'] and ep in rows['mg_vs_only']]
    if both:
        diff = [(-rows['mg_vs'][ep]['margin']) - (-rows['mg_vs_only'][ep]['margin']) for ep in both]
        print('\nA minus B, paired by world = what routing to a NEIGHBOUR\'s tape costs against having her own:')
        print(line('routing loss', diff))
    (ROOT / f'results/fresh/mg_tape/h2h_{agent}.json').write_text(json.dumps(out), encoding='utf-8')


if __name__ == '__main__':
    main()
