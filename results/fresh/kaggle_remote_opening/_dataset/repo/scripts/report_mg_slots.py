"""Report the MG slot-layer isolation panel (scripts/verify_mg_slots.py).

Per variant, paired with mgs_null on the same world and seat:
  servicing  - swaps committed / planted, units harvested vs expected, drought deaths and decay loss of the
               swapped crop, plantings missed;
  isolation  - production of every other crop vs the null run; seeds left at season end;
  economics  - margin vs the live benchmark, own cash and benchmark cash vs the null run (both sides).
"""
import glob, json, random, statistics as st, sys
from collections import Counter, defaultdict
from market_corpus import ROOT

OUT = ROOT / 'results/fresh/mg_slots'


def ci(v, n=10000, seed=7):
    if len(v) < 2:
        return (v[0], v[0]) if v else (0, 0)
    rng = random.Random(seed)
    d = sorted(st.mean(rng.choice(v) for _ in v) for _ in range(n))
    return d[int(0.025 * n)], d[int(0.975 * n) - 1]


def load():
    rows = defaultdict(dict)
    for p in glob.glob(str(OUT / '*.json')):
        r = json.loads(open(p, encoding='utf-8').read())
        rows[r['variant']][(r['episode'], r['seat'])] = r
    return rows


def produced(r):
    return {k[9:]: v for k, v in r['physical'].items() if k.startswith('produced:')}


def main():
    rows = load()
    null = rows.get('mgs_null', {})
    print(f"null control: {len(null)} games; margin vs benchmark {sorted(set(r['margin'] for r in null.values()))[:5]}")
    variants = [v for v in (sys.argv[1].split(',') if len(sys.argv) > 1 else sorted(rows)) if v != 'mgs_null']
    for v in variants:
        games = rows.get(v, {})
        keys = sorted(set(games) & set(null))
        if not keys:
            continue
        tel = Counter()
        for k in keys:
            tel.update({a: b for a, b in games[k]['telemetry'].items() if isinstance(b, (int, float))})
        print(f'\n=== {v}  (n={len(keys)} paired games)')
        print(f"servicing: swaps {tel['swaps_committed']}, planted {tel['plantings_confirmed']}, missed {tel['plantings_missed']}, "
              f"expected units {tel['expected_units']}, harvest issued {tel['harvest_issued_units']}, lost plants {tel['lost_plants']}, "
              f"layer errors {tel['errors']}, calendar resyncs {tel['calendar_resync']}")
        rej = {a[9:]: b for a, b in tel.items() if a.startswith('rejected_')}
        if rej:
            print(f'   rejected candidates: {rej}')
        crops = set()
        for k in keys:
            for r in (games[k], null[k]):
                crops |= set(produced(r))
        # engine truth for the swapped crop: tomato units actually harvested by the seat
        swapped = [produced(games[k]).get('TOMATO', 0) - produced(null[k]).get('TOMATO', 0) for k in keys]
        dry = sum(1 for k in keys for d in games[k]['dry'] if d[3] == 'TOMATO')
        dry_null = sum(1 for k in keys for d in null[k]['dry'] if d[3] == 'TOMATO')
        dec = sum(games[k]['decay'].get('TOMATO', 0) for k in keys)
        print(f'engine: extra tomato units harvested {sum(swapped)} (layer issued {tel["harvest_issued_units"]}); '
              f'tomato drought deaths {dry} (null {dry_null}); tomato units lost to decay {dec}')
        print('production change vs null, all games (units):')
        line = []
        for c in sorted(crops):
            d = [produced(games[k]).get(c, 0) - produced(null[k]).get(c, 0) for k in keys]
            line.append(f'{c.lower()} {sum(d):+d} (games changed {sum(1 for x in d if x)})')
        print('   ' + '; '.join(line))
        seeds = Counter()
        seeds_null = Counter()
        for k in keys:
            seeds.update(games[k]['seeds_left'])
            seeds_null.update(null[k]['seeds_left'])
        print(f'seeds left at season end (all games): {dict(seeds)}  null: {dict(seeds_null)}')
        dry_all = Counter(d[3] for k in keys for d in games[k]['dry'])
        dry_all_null = Counter(d[3] for k in keys for d in null[k]['dry'])
        print(f'drought deaths by crop: {dict(dry_all)}  null: {dict(dry_all_null)}')
        m = [games[k]['margin'] for k in keys]
        own = [games[k]['final'] - null[k]['final'] for k in keys]
        opp = [games[k]['bench_final'] - null[k]['bench_final'] for k in keys]
        w = sum(x > 0 for x in m); t = sum(x == 0 for x in m); l = sum(x < 0 for x in m)
        lo, hi = ci(m); olo, ohi = ci(own); blo, bhi = ci(opp)
        print(f'margin vs live benchmark: {w}-{t}-{l}, mean {st.mean(m):+,.0f} ({lo:+,.0f} to {hi:+,.0f})')
        print(f'own cash vs null {st.mean(own):+,.0f} ({olo:+,.0f} to {ohi:+,.0f}); '
              f'benchmark cash vs null {st.mean(opp):+,.0f} ({blo:+,.0f} to {bhi:+,.0f})')
        rev = Counter(); rev_null = Counter()
        for k in keys:
            rev.update(games[k]['revenue']); rev_null.update(null[k]['revenue'])
        print('own revenue change by product (mean/game): ' + ', '.join(
            f'{p.lower()} {(rev[p] - rev_null[p]) / len(keys):+,.0f}' for p in sorted(set(rev) | set(rev_null))
            if abs(rev[p] - rev_null[p]) / len(keys) >= 20))


if __name__ == '__main__':
    main()
