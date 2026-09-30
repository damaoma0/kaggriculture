"""xfix: full games, T vs T + fixes in the leader worlds (stored results only, no games).

Reads results/fresh/xfix_20260925/full/<arm>/<ep>.json (lead_ledger records, scripts/xfix_run.py full) and the baseline T
(results/fresh/xopen_20260925/g1/T = the same T with the xopen T settings, played by the same lead_ledger harness; or
full/T when present). Per world set (the 12 lead_g1 worlds, the 48 four-quadrant worlds of lead_sem4, all 52):
final cash paired vs T (mean, t-CI, bootstrap CI, better / worse), gap to the leader, and season totals: FERTILIZE by
crop, fertilizer collected / applied / sold / discarded at midnight, animals escaped (retired) and alive at the end,
harvested units by product, plantings.
usage: xfix_full_report.py arm[,arm...] [--base T]  -> results/fresh/xfix_20260925/full_report.txt
"""
import json
import math
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
OUT = ROOT / 'results/fresh/xfix_20260925'
XO = ROOT / 'results/fresh/xopen_20260925/g1'
LINES = []


def say(s=''):
    LINES.append(s)
    print(s)


def tci(xs):
    from scipy import stats
    n = len(xs)
    m = sum(xs) / n
    if n < 2:
        return m, m, m
    s = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    h = stats.t.ppf(0.975, n - 1) * s / math.sqrt(n)
    return m, m - h, m + h


def bci(xs, n=10000, seed=7):
    rng = random.Random(seed)
    k = len(xs)
    ms = sorted(sum(rng.choices(xs, k=k)) / k for _ in range(n))
    return ms[int(0.025 * n)], ms[int(0.975 * n)]


def load_dir(d):
    out = {}
    for f in Path(d).glob('*.json'):
        r = json.loads(f.read_text(encoding='utf-8'))
        out[int(r['episode'])] = r
    return out


def season(r, key):
    c = Counter()
    for d in r['days']:
        c.update(d.get(key) or {})
    return c


def main():
    arms = sys.argv[1].split(',')
    base = 'T'
    if '--base' in sys.argv:
        base = sys.argv[sys.argv.index('--base') + 1]
    B = load_dir(OUT / 'full' / base) if (OUT / 'full' / base).exists() else {}
    for e, r in load_dir(XO / 'T').items():
        B.setdefault(e, r)
    Ld = load_dir(XO / 'LEADER')
    import lead_g1
    g1 = {int(g.split(':')[1]) for g in lead_g1.GAMES}
    s4 = {int(x['episode']) for x in json.loads((ROOT / 'results/fresh/lead_sem4_20260925/worlds.json').read_text(encoding='utf-8'))['worlds']}
    for a in arms:
        A = load_dir(OUT / 'full' / a)
        say(f'\n== {a} vs {base} (full games, T from step 0; T settings p1_min_value 30, release_stale_d, fert_hold 1)')
        for nm, sel in (('12 lead_g1', g1), ('48 four-quadrant', s4), ('all 52', g1 | s4)):
            es = sorted(e for e in sel if e in A and e in B)
            if not es:
                continue
            d = [A[e]['final'] - B[e]['final'] for e in es]
            m, lo, hi = tci(d) if any(d) else (0.0, 0.0, 0.0)
            blo, bhi = bci(d) if any(d) else (0.0, 0.0)
            gap = [Ld[e]['final'] - A[e]['final'] for e in es if e in Ld]
            gb = [Ld[e]['final'] - B[e]['final'] for e in es if e in Ld]
            say(f'  {nm:18s} n={len(es):2d}: {m:+,.0f} (t {lo:+,.0f}..{hi:+,.0f}; boot {blo:+,.0f}..{bhi:+,.0f}), better '
                f'{sum(1 for x in d if x > 0.5)}/{sum(1 for x in d if x < -0.5)}; gap to leader {sum(gap) / max(1, len(gap)):+,.0f} '
                f'(T {sum(gb) / max(1, len(gb)):+,.0f}); opp min {min(A[e]["opp_final"] / max(1, A[e]["target_opp"]) for e in es):.2f}')
        es = sorted(e for e in (g1 | s4) if e in A and e in B)
        if not es:
            continue
        n = len(es)
        for tag, G in (('leader', Ld), (base, B), (a, A)):
            ee = [e for e in es if e in G]
            opk = sum((season(G[e], 'opk') for e in ee), Counter())
            eff = sum((season(G[e], 'eff') for e in ee), Counter())
            sold = sum((season(G[e], 'sold') for e in ee), Counter())
            harv = sum((season(G[e], 'harv') for e in ee), Counter())
            died = sum((season(G[e], 'died') for e in ee), Counter())
            ov = sum((season(G[e], 'overflow') for e in ee), Counter())
            plant = sum((season(G[e], 'plant') for e in ee), Counter())
            alive = Counter()
            for e in ee:
                for k in (G[e]['days'][29].get('board_list') or []):
                    if k in ('GOOSE', 'COW', 'SHEEP'):
                        alive[k] += 1
            k_ = len(ee)
            say(f'  season per game [{tag}]: FERTILIZE ' + ', '.join(f'{c[10:]} {v / k_:.1f}' for c, v in sorted(opk.items()) if c.startswith('FERTILIZE:'))
                + f'; fertilizer collected {eff.get("COLLECT_FERTILIZER", 0) / k_:.0f} sold {sold.get("FERTILIZER", 0) / k_:.0f} '
                  f'discarded {ov.get("FERTILIZER", 0) / k_:.1f}; animals escaped ' + ', '.join(f'{c[7:]} {v / k_:.1f}' for c, v in sorted(died.items()) if c.startswith('animal_'))
                + '; alive at the end ' + ', '.join(f'{c} {v / k_:.1f}' for c, v in sorted(alive.items()))
                + '; harvested ' + ', '.join(f'{c} {v / k_:.0f}' for c, v in sorted(harv.items()))
                + '; plantings ' + ', '.join(f'{c[:4]} {v / k_:.0f}' for c, v in sorted(plant.items()))
                + f'; final {sum(G[e]["final"] for e in ee) / k_:,.0f}')
    (OUT / 'full_report.txt').write_text('\n'.join(LINES) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
