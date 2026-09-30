"""Full-panel report for a deploy build: paired margin vs references (95% bootstrap CI), W-L, per-product units.

usage: lead_panel_report.py <results_dir_of_build> [refs=mgt_y3,mgt_m1] [submission=p2750]
The build's results dir may be a remote output tree (all *.json below it with 'agent'/'episode' keys are read).
"""
import json
import random
import statistics as st
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / 'results/fresh/ladder_panel'
PRODS = ('WHEAT', 'CARROT', 'MILK', 'WOOL', 'STRAWBERRY', 'TOMATO', 'MELON', 'EGG', 'FERTILIZER')


def boot(v, n=4000):
    rng = random.Random(1)
    s = sorted(st.mean(rng.choice(v) for _ in v) for _ in range(n))
    return s[int(.025 * n)], s[int(.975 * n)]


def main():
    src = Path(sys.argv[1])
    refs = (sys.argv[2] if len(sys.argv) > 2 else 'mgt_y3,mgt_m1').split(',')
    sub = sys.argv[3] if len(sys.argv) > 3 else 'p2750'
    eps = {p.name.split('.')[0] for p in (ROOT / 'data/ladder_panel' / sub).glob('*.json.gz')}
    rows = {}
    for f in src.rglob('*.json'):
        try:
            r = json.loads(f.read_text(encoding='utf-8'))
        except Exception:
            continue
        if isinstance(r, dict) and 'episode' in r and 'margin' in r and str(r['episode']) in eps:
            rows[str(r['episode'])] = r
    print(f'{src}: {len(rows)} of {len(eps)} {sub} games')
    R = {a: {e: json.load(open(P / a / f'{e}.json')) for e in rows if (P / a / f'{e}.json').exists()} for a in refs}
    m = [r['margin'] for r in rows.values()]
    ref0 = R[refs[0]]
    broken = [e for e in rows if e in ref0 and rows[e].get('opp_dead', 0) - ref0[e].get('opp_dead', 0) > 40]
    print(f'build: mean margin {st.mean(m):+,.0f}, W-L {sum(x > 0 for x in m)}-{sum(x < 0 for x in m)}, '
          f'own cash {st.mean(r["final"] for r in rows.values()):,.0f}; opponent tape broken vs {refs[0]} '
          f'(its commands without effect +40): {len(broken)}')
    for a in refs:
        common = sorted(set(rows) & set(R[a]))
        d = [rows[e]['margin'] - R[a][e]['margin'] for e in common]
        lo, hi = boot(d)
        ma = [R[a][e]['margin'] for e in common]
        print(f'vs {a:10s} n={len(common)}: {st.mean(d):+,.0f} (95% CI {lo:+,.0f} .. {hi:+,.0f}), build better in '
              f'{sum(x > 0 for x in d)}/{len(d)}; {a} W-L {sum(x > 0 for x in ma)}-{sum(x < 0 for x in ma)}, '
              f'mean margin {st.mean(ma):+,.0f}')
    print(f'{"units per game":16s}' + ' '.join(f'{p[:6]:>7s}' for p in PRODS))
    for name, rr in [('build', rows)] + [(a, R[a]) for a in refs]:
        u = Counter()
        rv = Counter()
        for r in rr.values():
            u.update(r['sold'])
            rv.update(r['revenue'])
        n = max(1, len(rr))
        print(f'{name:16s}' + ' '.join(f'{u[p] / n:7.0f}' for p in PRODS) + f'   revenue {sum(rv.values()) / n:,.0f}')


if __name__ == '__main__':
    main()
