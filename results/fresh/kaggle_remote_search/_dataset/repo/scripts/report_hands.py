"""Report the owned-hands stage (scripts/verify_mg_slots.py output), paired on her 30 worlds.

  isolation : mg9_hands_t11 (all 13 slots -> tomatoes, hands on) against mg3_t11v (same swaps, tape visits
              only) and mg7_fert_t11 (fertilizer on the tape visit): tomato units per plant, wages, fertilizer
              bought, own cash, margin.
  candidate : mg9_hands_econ against mgs_null and mg5_econ_m (its predecessor's crop rule).
"""
import glob, json, random, statistics as st
from collections import Counter
from market_corpus import ROOT

OUT = ROOT / 'results/fresh/mg_slots'


def load(v):
    return {json.load(open(p))['episode']: json.load(open(p)) for p in glob.glob(str(OUT / f'{v}-*.json'))}


def ci(v, n=5000, seed=7):
    if len(v) < 2:
        return (v[0], v[0]) if v else (0, 0)
    rng = random.Random(seed)
    d = sorted(st.mean(rng.choice(v) for _ in v) for _ in range(n))
    return d[int(0.025 * n)], d[int(0.975 * n) - 1]


def fmt(v):
    lo, hi = ci(v)
    return f'{st.mean(v):+,.0f} ({lo:+,.0f} to {hi:+,.0f})'


def tomatoes(r):
    return r['physical'].get('produced:TOMATO', 0)


def pair(name, a, b, label_b):
    keys = sorted(set(a) & set(b))
    if not keys:
        print(f'{name}: no paired games with {label_b}')
        return
    tel = Counter()
    for k in keys:
        tel.update({x: y for x, y in a[k]['telemetry'].items() if isinstance(y, (int, float))})
    plants = tel.get('plantings_confirmed', 0)
    print(f'\n=== {name} vs {label_b} (n={len(keys)})')
    print(f"  hands: requested {tel['hands_requested']}, hired {tel['hands_hired']}, shortfalls {tel['hands_shortfall']}, "
          f"declined cash {tel['hands_declined_cash']}, wages {tel['hands_hire_cost']:,.0f}, fertilizer bought {tel['hands_fert_bought']}, "
          f"fertilize {tel['hands_fertilize']}, water {tel['hands_water']}, harvest units {tel['hands_harvest_units']}; errors {tel['errors']}")
    own = lambda r: r['telemetry'].get('harvest_issued_tomato', 0) + r['telemetry'].get('harvest_issued_units', 0) + r['telemetry'].get('hands_harvest_units', 0)
    ta = sum(own(a[k]) for k in keys); tb = sum(own(b[k]) for k in keys)
    pa = sum(1 for k in keys for _ in range(a[k]['telemetry'].get('swaps_tomato', a[k]['telemetry'].get('swaps_committed', 0))))
    pb = sum(1 for k in keys for _ in range(b[k]['telemetry'].get('swaps_tomato', b[k]['telemetry'].get('swaps_committed', 0))))
    print(f'  own tomatoes (layer harvests): {ta} on {pa} swapped plants = {ta / max(1, pa):.2f}/plant; {label_b}: {tb} on {pb} = {tb / max(1, pb):.2f}/plant')
    dry = sum(1 for k in keys for d in a[k]['dry'] if d[3] == 'TOMATO'); dec = sum(a[k]['decay'].get('TOMATO', 0) for k in keys)
    miss = sum(a[k]['physical'].get('missing_worker_commands', 0) for k in keys)
    print(f'  tomato drought deaths {dry}, decay units {dec}, missing-worker commands {miss}')
    own = [a[k]['final'] - b[k]['final'] for k in keys]
    opp = [a[k]['bench_final'] - b[k]['bench_final'] for k in keys]
    m = [a[k]['margin'] for k in keys]; mb = [b[k]['margin'] for k in keys]
    dm = [x - y for x, y in zip(m, mb)]
    print(f'  own cash vs {label_b}: {fmt(own)}; benchmark cash: {fmt(opp)}; margin change: {fmt(dm)}')
    w = sum(x > 0 for x in m); t = sum(x == 0 for x in m); l = sum(x < 0 for x in m)
    print(f'  margin vs live benchmark: {w}-{t}-{l}, {fmt(m)}')
    rev = Counter(); revb = Counter(); sp = Counter(); spb = Counter()
    for k in keys:
        rev.update(a[k]['revenue']); revb.update(b[k]['revenue']); sp.update(a[k]['spend']); spb.update(b[k]['spend'])
    n = len(keys)
    print('  revenue change: ' + ', '.join(f'{p.lower()} {(rev[p] - revb[p]) / n:+,.0f}' for p in sorted(set(rev) | set(revb)) if abs(rev[p] - revb[p]) / n >= 30))
    print('  spend change:   ' + ', '.join(f'{p.lower()} {(sp[p] - spb[p]) / n:+,.0f}' for p in sorted(set(sp) | set(spb)) if abs(sp[p] - spb[p]) / n >= 30))


def main():
    import sys
    tag = sys.argv[1] if len(sys.argv) > 1 else 'mg9'
    null, t11v, fert = load('mgs_null'), load('mg3_t11v'), load('mg7_fert_t11')
    hands_t11, econ_v1, hands_econ = load(f'{tag}_hands_t11'), load('mg5_econ_m'), load(f'{tag}_hands_econ')
    if hands_t11:
        pair(f'{tag}_hands_t11', hands_t11, t11v, 'mg3_t11v (tape visits only)')
        pair(f'{tag}_hands_t11', hands_t11, fert, 'mg7_fert_t11 (fertilizer on tape visit)')
    if hands_econ:
        pair(f'{tag}_hands_econ', hands_econ, null, 'mgs_null')
        pair(f'{tag}_hands_econ', hands_econ, econ_v1, 'mg5_econ_m (v1 crop rule)')
        if tag != 'mg9' and load('mg9_hands_econ'):
            pair(f'{tag}_hands_econ', hands_econ, load('mg9_hands_econ'), 'mg9_hands_econ (hands v1)')
        dec = Counter()
        for r in hands_econ.values():
            d = r['telemetry'].get('econ_decision') or {}
            dec[(d.get('keep'), d.get('tomatoes'), d.get('melons'), d.get('add'))] += 1
        print('  decisions (keep, tomatoes, melons, add):', dict(dec))


if __name__ == '__main__':
    main()
