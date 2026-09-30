"""Where a candidate's margin against a rival comes from, by product, paired with a reference candidate.

Reads self-play gate games (results/fresh/selfplay/games/<cand>-<seed>-<seat>-vs-<rival>.json) and, on the
same seeds and seats, compares each candidate with the reference: our revenue and spend change by product,
and the rival's revenue change by product. Usage:
  python report_vs_rival_products.py <rival> <reference> <candidate> [<candidate> ...] [--seeds lo-hi]
"""
import glob, json, random, statistics as st, sys
from collections import Counter
from market_corpus import ROOT

GAMES = ROOT / 'results/fresh/selfplay/games'


def load(cand, rival, lo, hi):
    out = {}
    pattern = f'{cand}-*-vs-{rival}.json' if rival != 'benchmark_frozen_56280048' else f'{cand}-[0-9]*-[01].json'
    for p in glob.glob(str(GAMES / pattern)):
        r = json.loads(open(p, encoding='utf-8').read())
        if lo <= r['seed'] <= hi:
            out[(r['seed'], r['seat'])] = r
    return out


def ci(v, n=5000, seed=3):
    rng = random.Random(seed)
    d = sorted(st.mean(rng.choice(v) for _ in v) for _ in range(n))
    return d[int(0.025 * n)], d[int(0.975 * n) - 1]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    lo, hi = 0, 10 ** 9
    if '--seeds' in sys.argv:
        lo, hi = map(int, sys.argv[sys.argv.index('--seeds') + 1].split('-'))
        args = [a for a in args if a != sys.argv[sys.argv.index('--seeds') + 1]]
    rival, ref, cands = args[0], args[1], args[2:]
    base = load(ref, rival, lo, hi)
    print(f'reference {ref} vs {rival}: n={len(base)}, our cash {st.mean(r["cash"] for r in base.values()):,.0f}, '
          f'{rival} cash {st.mean(r["bench_cash"] for r in base.values()):,.0f}')
    for c in cands:
        games = load(c, rival, lo, hi)
        keys = sorted(set(games) & set(base))
        if not keys:
            continue
        d_own = [games[k]['cash'] - base[k]['cash'] for k in keys]
        d_riv = [games[k]['bench_cash'] - base[k]['bench_cash'] for k in keys]
        d_m = [games[k]['margin'] - base[k]['margin'] for k in keys]
        print(f'\n=== {c} vs {rival}, paired with {ref} (n={len(keys)})')
        for name, v in (('our cash', d_own), (f'{rival} cash', d_riv), ('margin', d_m)):
            a, b = ci(v)
            print(f'  {name:18s} {st.mean(v):+9,.0f} ({a:+,.0f} to {b:+,.0f})')
        rev_o, rev_r, spend = Counter(), Counter(), Counter()
        for k in keys:
            for p, v in games[k]['ledger_candidate']['revenue'].items():
                rev_o[p] += v
            for p, v in base[k]['ledger_candidate']['revenue'].items():
                rev_o[p] -= v
            for p, v in games[k]['ledger_benchmark']['revenue'].items():
                rev_r[p] += v
            for p, v in base[k]['ledger_benchmark']['revenue'].items():
                rev_r[p] -= v
            for p, v in games[k]['ledger_candidate']['spend'].items():
                spend[p] += v
            for p, v in base[k]['ledger_candidate']['spend'].items():
                spend[p] -= v
        n = len(keys)
        print('  our revenue change:   ' + ', '.join(f'{p.lower()} {v / n:+,.0f}' for p, v in sorted(rev_o.items(), key=lambda kv: -abs(kv[1])) if abs(v / n) >= 50))
        print(f'  {rival} revenue change: ' + ', '.join(f'{p.lower()} {v / n:+,.0f}' for p, v in sorted(rev_r.items(), key=lambda kv: -abs(kv[1])) if abs(v / n) >= 50))
        print('  our spend change:     ' + ', '.join(f'{p.lower()} {v / n:+,.0f}' for p, v in sorted(spend.items(), key=lambda kv: -abs(kv[1])) if abs(v / n) >= 50))


if __name__ == '__main__':
    main()
