"""Step reports for the MG-policy build (scripts/verify_mg_slots.py output), paired with mgs_null.

Usage: python report_mg_steps.py variant[,variant...] [--probe mg3_probe] [--observed keep:variant,...]
"""
import glob, json, random, statistics as st, sys
from collections import Counter, defaultdict
from market_corpus import ROOT

OUT = ROOT / 'results/fresh/mg_slots'
STRAW_SHOPS = {'BRUNCH_SPOT', 'ICE_CREAM_SHOP', 'SMOOTHIE_SHOP', 'FARMERS_MARKET'}
TOM_SHOPS = {'PIZZA_SHOP', 'FARMERS_MARKET'}


def ci(v, n=10000, seed=7):
    if len(v) < 2:
        return (v[0], v[0]) if v else (0, 0)
    rng = random.Random(seed)
    d = sorted(st.mean(rng.choice(v) for _ in v) for _ in range(n))
    return d[int(0.025 * n)], d[int(0.975 * n) - 1]


def load(v):
    out = {}
    for p in glob.glob(str(OUT / f'{v}-*.json')):
        r = json.loads(open(p, encoding='utf-8').read())
        out[(r['episode'], r['seat'])] = r
    return out


def shops4(eid):
    ev = json.loads((ROOT / f'results/fresh/mg_policy/events-{eid}.json').read_text(encoding='utf-8'))
    return ev['days'][12]['shops'][:4]


def produced(r):
    return {k[9:]: v for k, v in r['physical'].items() if k.startswith('produced:')}


def issued(r, crop):
    t = r['telemetry']
    return t.get('harvest_issued_' + crop.lower(), 0) + (t.get('harvest_issued_units', 0) if crop == 'TOMATO' else 0)


def section(v, null):
    games = load(v)
    keys = sorted(set(games) & set(null))
    if not keys:
        print(f'\n=== {v}: no games')
        return games
    tel = Counter()
    for k in keys:
        tel.update({a: b for a, b in games[k]['telemetry'].items() if isinstance(b, (int, float))})
    print(f'\n=== {v}  (n={len(keys)})')
    crops = sorted({a.split('_')[-1].upper() for a in tel if a.startswith('swaps_') and a != 'swaps_committed'})
    for crop in crops:
        c = crop.lower()
        dry = sum(1 for k in keys for d in games[k]['dry'] if d[3] == crop) - sum(1 for k in keys for d in null[k]['dry'] if d[3] == crop)
        dec = sum(games[k]['decay'].get(crop, 0) - null[k]['decay'].get(crop, 0) for k in keys)
        print(f'  {crop.lower():10s} swaps {tel["swaps_" + c]}, expected units {tel["expected_units_" + c]}, '
              f'harvest issued {tel["harvest_issued_" + c]}, lost plants {tel["lost_plants_" + c]}, '
              f'drought deaths vs null {dry:+d}, decay units vs null {dec:+d}')
    print(f'  planted {tel["plantings_confirmed"]} of {tel["swaps_committed"]} (missed {tel["plantings_missed"]}); '
          f'layer errors {tel["errors"]}; V219 checks masked {tel["v219_masked_checks"]}')
    rej = {a[9:]: b for a, b in tel.items() if a.startswith('rejected_')}
    if rej:
        print(f'  rejected: {rej}')
    # V219 status: tomatoes the engine produced beyond our own issued harvests
    v219_null = [k for k in keys if produced(null[k]).get('TOMATO', 0) > 0]
    if v219_null:
        kept = sum(1 for k in v219_null if produced(games[k]).get('TOMATO', 0) - issued(games[k], 'TOMATO') > 0)
        print(f'  V219 worlds (tomatoes in null): {len(v219_null)}; V219 still producing in variant: {kept}')
    seeds = Counter()
    for k in keys:
        seeds.update({a: b for a, b in games[k]['seeds_left'].items() if b})
    print(f'  seeds left: {dict(seeds)} (null {dict(sum((Counter({a: b for a, b in null[k]["seeds_left"].items() if b}) for k in keys), Counter()))})')
    m = [games[k]['margin'] for k in keys]
    own = [games[k]['final'] - null[k]['final'] for k in keys]
    opp = [games[k]['bench_final'] - null[k]['bench_final'] for k in keys]
    w = sum(x > 0 for x in m); t = sum(x == 0 for x in m); l = sum(x < 0 for x in m)
    lo, hi = ci(m); olo, ohi = ci(own); blo, bhi = ci(opp)
    print(f'  margin vs live benchmark: {w}-{t}-{l}, {st.mean(m):+,.0f} ({lo:+,.0f} to {hi:+,.0f})')
    print(f'  own cash vs null {st.mean(own):+,.0f} ({olo:+,.0f} to {ohi:+,.0f}); benchmark cash vs null '
          f'{st.mean(opp):+,.0f} ({blo:+,.0f} to {bhi:+,.0f})')
    by = defaultdict(list)
    for k in keys:
        s4 = sum(s in STRAW_SHOPS for s in shops4(k[0]))
        by[min(s4, 4)].append((own[keys.index(k)], m[keys.index(k)], games[k]['telemetry'].get('econ_decision')))
    for s4 in sorted(by):
        rows = by[s4]
        dec = Counter()
        for _, _, d in rows:
            if d:
                dec[(d['keep'], d['add'], d.get('melons', 0))] += 1
        print(f'    strawberry shops in first four = {s4}: n {len(rows)}, own {st.mean(r[0] for r in rows):+,.0f}, '
              f'margin {st.mean(r[1] for r in rows):+,.0f}' + (f'; decisions (keep, add, melons): {dict(dec)}' if dec else ''))
    rev = Counter(); rev_null = Counter()
    for k in keys:
        rev.update(games[k]['revenue']); rev_null.update(null[k]['revenue'])
    print('  own revenue change by product (mean/game): ' + ', '.join(
        f'{p.lower()} {(rev[p] - rev_null[p]) / len(keys):+,.0f}' for p in sorted(set(rev) | set(rev_null))
        if abs(rev[p] - rev_null[p]) / len(keys) >= 20))
    return games


def validate(probe_v, observed, null):
    """Model predictions (dry-run probe) vs observed own-cash change for fixed allocations."""
    probe = load(probe_v)
    for keep, v in observed:
        games = load(v)
        pairs = []
        for k, r in probe.items():
            pr = (r['telemetry'].get('econ_probe') or {}).get(str(keep))
            if pr is None or k not in games or k not in null:
                continue
            pairs.append((pr[0], games[k]['final'] - null[k]['final'], pr[1], games[k]['bench_final'] - null[k]['bench_final']))
        if len(pairs) < 3:
            continue
        po = [p[0] for p in pairs]; oo = [p[1] for p in pairs]
        pp = [p[2] for p in pairs]; op = [p[3] for p in pairs]
        corr = st.correlation(po, oo) if len(set(po)) > 1 else float('nan')
        sign = sum(1 for a, b in zip(po, oo) if (a > 0) == (b > 0))
        pm = [a - b for a, b in zip(po, pp)]; om = [a - b for a, b in zip(oo, op)]
        signm = sum(1 for a, b in zip(pm, om) if (a > 0) == (b > 0))
        print(f'\nmodel check, keep {keep} of the batch vs observed {v} (n={len(pairs)}): own predicted {st.mean(po):+,.0f} '
              f'observed {st.mean(oo):+,.0f}, corr {corr:+.2f}, sign agreement {sign}/{len(pairs)}; '
              f'margin predicted {st.mean(pm):+,.0f} observed {st.mean(om):+,.0f}, sign agreement {signm}/{len(pairs)}')


def main():
    null = load('mgs_null')
    variants = sys.argv[1].split(',')
    for v in variants:
        section(v, null)
    if '--probe' in sys.argv:
        probe_v = sys.argv[sys.argv.index('--probe') + 1]
        obs = []
        if '--observed' in sys.argv:
            for item in sys.argv[sys.argv.index('--observed') + 1].split(','):
                keep, v = item.split(':')
                obs.append((int(keep), v))
        validate(probe_v, obs, null)


if __name__ == '__main__':
    main()
