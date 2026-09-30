"""Paired decomposition of the fourth-quadrant (SE) margin delta, from lead_cycles records (scripts/lead_cycles.py run
with per-tile boards, animal harvest events, labour by quadrant, the panel result and, with --idle, the executor's idle
trace) of a with-SE build and its baseline in the same worlds.

usage: q4_decompose.py <with_SE_agent> <baseline_agent> [--dir results/fresh/lead_cycles] [--world EP] [--json out]

Margin identity per game (all terms paired deltas, with-SE minus baseline; S = units sold, P = average sale price,
H = units harvested from our own tiles; SE = tiles of the SE quadrant, oth = the other three quadrants):
  d margin = d own cash - d rival cash
  d own cash = d income - d spend  (checked against the panel's final cash)
  d income_p = H1_SE,p * P1_p                       SE output at our realised price
             + (H1_oth,p - H0_p) * P1_p             output change on the other three quadrants
             - d(H - S)_p * P1_p                    units harvested but not sold (feed, stock, end inventory) / bought
             + S0_p * (P1_p - P0_p)                 price change on the units the baseline sold
    (fertilizer is not a harvest: its whole volume change is the 'fertilizer' line = collected - used - held;
     P1 is replaced by P0 when the with-SE build sells none of p)
  d rival cash = rival price effect sum_p S0r_p * (P1r_p - P0r_p) + rival volume sum_p dSr_p * P1r_p - d rival spend
The residual is d margin minus the sum of the lines (rounding only, by construction); the point of the table is which
line carries the loss. Mechanism tables for the other quadrants: plantings / deaths / units per planting, animal-days
and output per animal-day, animals lost, labour unit-steps per quadrant, hands per day, dropped maintenance (idle trace).
"""
import json
import math
import os
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = {'WHEAT': 10, 'CARROT': 20, 'TOMATO': 50, 'STRAWBERRY': 100, 'MELON': 80}
ANIMAL_COST = {'GOOSE': 300, 'COW': 400, 'SHEEP': 500}
PRODUCT_OF = {'GOOSE': 'EGG', 'COW': 'MILK', 'SHEEP': 'WOOL'}
CROPS = ('WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON')
PRODS = CROPS + ('EGG', 'MILK', 'WOOL', 'FERTILIZER')
T975 = {5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 15: 2.131, 20: 2.086}
LAB_CROP = {'WH': 'WHEAT', 'CA': 'CARROT', 'TO': 'TOMATO', 'ST': 'STRAWBERRY', 'ME': 'MELON'}
LAB_AN = {'go': 'GOOSE', 'co': 'COW', 'sh': 'SHEEP'}
WINS = ((0, 9), (10, 11), (12, 17), (18, 23), (24, 29))


def quad(i):
    i = int(i)
    return ('N' if i // 10 < 5 else 'S') + ('W' if i % 10 < 5 else 'E')


def ci(xs):
    n = len(xs)
    m = st.mean(xs) if xs else 0.0
    if n < 2:
        return m, m, m
    s = st.stdev(xs) / math.sqrt(n)
    t = T975.get(n - 1, 1.96)
    return m, m - t * s, m + t * s


def fmt(xs, d=0):
    m, lo, hi = ci(xs)
    return f'{m:+,.{d}f} ({lo:+,.{d}f} .. {hi:+,.{d}f})'


def boards(r):
    return [[b[i:i + 2] for i in range(0, 200, 2)] for b in r['boards']]


def harvest_by_quad(r):
    h = defaultdict(float)                    # (quad, product) -> units
    for kind, day, idx, crop, pd, y in r['events']:
        if kind == 'harvest':
            h[(quad(idx), crop)] += y
    for day, idx, an, u in r.get('aevents', []):
        h[(quad(idx), PRODUCT_OF[an])] += u
    return h


def idle_dropped(ddir, agent, ep):
    """dropped maintenance value (module coins) per quadrant and kind, from the idle trace of one game."""
    d = ddir / agent / 'idle' / str(ep)
    out = Counter()
    if not d.exists():
        return None
    for f in d.glob('*.jsonl'):
        for line in open(f, encoding='utf-8'):
            rec = json.loads(line)
            for j in rec.get('dropped', []):
                out[(quad(j['idx']), j['cmd'])] += j['value']
    return out


def animal_stats(r):
    """per quadrant / species: animal-days (day-start), days fed (next day-start consecutive_unfed == 0), animals lost
    (a live animal tile at day start d that is a bare structure at day start d+1: starved, or stopped by the module)."""
    A = r.get('astates') or []
    B = boards(r)
    out = Counter()
    for d, ast in enumerate(A):
        for idx, v in ast.items():
            q = quad(idx)
            sp = v[0]
            out[(q, sp, 'animal_days')] += 1
            if d + 1 < len(A):
                nxt = A[d + 1].get(idx) or A[d + 1].get(str(idx))
                if nxt and nxt[0] == sp:
                    out[(q, sp, 'fed_days')] += 1 if nxt[2] == 0 else 0
                elif d + 1 < len(B) and B[d + 1][int(idx)] in ('Co', 'Pa'):
                    out[(q, sp, 'lost')] += 1
    return out


def load(ddir, agent):
    rows = {}
    for f in sorted((ddir / agent).glob('*.json')):
        r = json.loads(f.read_text(encoding='utf-8'))
        if r.get('boards') and r.get('panel'):
            rows[f.stem] = r
    return rows


def decompose(a, b):
    """one world: dict of named paired components (with-SE a minus baseline b)."""
    pa, pb = a['panel'], b['panel']
    out = {}
    ha, hb = harvest_by_quad(a), harvest_by_quad(b)
    # spend
    sp = lambda p, pre: sum(v for k, v in p['spend'].items() if k.startswith(pre))
    se_plants = Counter(crop for kind, day, idx, crop, pd, y in a['events'] if kind == 'plant' and quad(idx) == 'SE')
    seed_se = sum(SEED[c] * n for c, n in se_plants.items())
    Ba = boards(a)
    se_placed = Counter()
    for d in range(1, len(Ba)):
        for i in range(100):
            if quad(i) == 'SE' and Ba[d][i] in LAB_AN and Ba[d - 1][i] != Ba[d][i]:
                se_placed[LAB_AN[Ba[d][i]]] += 1
    an_se = sum(ANIMAL_COST[s] * n for s, n in se_placed.items())
    out['spend: land'] = -(sp(pa, 'BUY_LAND') - sp(pb, 'BUY_LAND'))
    out['spend: seeds for SE plantings'] = -seed_se
    out['spend: seeds, rest'] = -(sp(pa, 'BUY_SEED') - sp(pb, 'BUY_SEED') - seed_se)
    out['spend: animals placed on SE'] = -an_se
    out['spend: animals, rest'] = -(sp(pa, 'BUY_ANIMAL') - sp(pb, 'BUY_ANIMAL') - an_se)
    out['spend: wages'] = -(sp(pa, 'HIRE') - sp(pb, 'HIRE'))
    out['spend: bought wheat / fertilizer'] = -(sp(pa, 'BUY_PRODUCT') - sp(pb, 'BUY_PRODUCT'))
    # income
    for p in PRODS:
        S1, S0 = pa['sold'].get(p, 0), pb['sold'].get(p, 0)
        R1, R0 = pa['revenue'].get(p, 0), pb['revenue'].get(p, 0)
        P1 = R1 / S1 if S1 else (R0 / S0 if S0 else 0.0)
        P0 = R0 / S0 if S0 else P1
        price = S0 * (P1 - P0)
        if p == 'FERTILIZER':
            out['income: fertilizer volume (collected - used - held)'] = (S1 - S0) * P1
            out['price: ours, FERTILIZER'] = price
            continue
        H1se = ha.get(('SE', p), 0)
        H1o = sum(v for (q, pp), v in ha.items() if pp == p and q != 'SE')
        H0 = sum(v for (q, pp), v in hb.items() if pp == p)
        out['income: SE output, ' + p] = H1se * P1
        out['income: other quadrants, ' + p] = (H1o - H0) * P1
        out['income: harvested-not-sold change, ' + p] = -((H1se + H1o - S1) - (H0 - S0)) * P1
        out['price: ours, ' + p] = price
        chk = H1se * P1 + (H1o - H0) * P1 - ((H1se + H1o - S1) - (H0 - S0)) * P1 + price - (R1 - R0)
        assert abs(chk) < 1e-6, (p, chk)
    # rival
    for p in sorted(set(pa['rival_sold']) | set(pb['rival_sold'])):
        S1, S0 = pa['rival_sold'].get(p, 0), pb['rival_sold'].get(p, 0)
        R1, R0 = pa['rival_revenue'].get(p, 0), pb['rival_revenue'].get(p, 0)
        P1 = R1 / S1 if S1 else (R0 / S0 if S0 else 0.0)
        P0 = R0 / S0 if S0 else P1
        out['rival: price, ' + p] = -(S0 * (P1 - P0))
        out['rival: volume, ' + p] = -((S1 - S0) * P1)
    out['rival: spend change'] = (sum(pa['rival_spend'].values()) - sum(pb['rival_spend'].values()))
    dm = pa['margin'] - pb['margin']
    out['_residual'] = dm - sum(v for k, v in out.items())
    out['_margin'] = dm
    out['_own'] = pa['final'] - pb['final']
    out['_rival'] = pa['rival'] - pb['rival']
    return out


def group(name):
    if name.startswith('spend: '):
        return name
    if name.startswith('income: SE output'):
        return 'income: SE output (all products)'
    if name.startswith('income: other quadrants'):
        return 'income: other quadrants output change (all products)'
    if name.startswith('income: harvested-not-sold'):
        return 'income: harvested-not-sold change (feed / stock / unsold)'
    if name.startswith('income: fertilizer'):
        return name
    if name.startswith('price: ours'):
        return 'price: our units (price change on baseline units)'
    if name.startswith('rival: price'):
        return 'rival: price effect (its baseline units)'
    if name.startswith('rival: volume') or name.startswith('rival: spend'):
        return 'rival: volume / spend change'
    return name


def main():
    args = sys.argv[1:]
    ddir = ROOT / 'results/fresh/lead_cycles'
    if '--dir' in args:
        ddir = ROOT / args[args.index('--dir') + 1]
    A, B = args[0], args[1]
    ra, rb = load(ddir, A), load(ddir, B)
    eps = sorted(set(ra) & set(rb))
    n = len(eps)
    print(f'{A} vs {B}: {n} paired worlds ({ddir})')
    # checks: panel reproduces the stored ladder-panel results
    for agent, rows in ((A, ra), (B, rb)):
        lp = ROOT / 'results/fresh/ladder_panel' / agent
        same = sum(1 for e in eps if (lp / f'{e}.json').exists()
                   and round(json.load(open(lp / f'{e}.json'))['final']) == round(rows[e]['final'])
                   and round(json.load(open(lp / f'{e}.json'))['rival']) == round(rows[e]['panel']['rival']))
        have = sum(1 for e in eps if (lp / f'{e}.json').exists())
        print(f'  {agent}: traced run = plain ladder-panel run in {same}/{have} worlds (own and rival cash)')
    D = {e: decompose(ra[e], rb[e]) for e in eps}
    keys = sorted({k for e in eps for k in D[e] if not k.startswith('_')})
    # grouped table
    G = defaultdict(lambda: [0.0] * n)
    for j, e in enumerate(eps):
        for k in keys:
            G[group(k)][j] += D[e].get(k, 0.0)
    print('\n== decomposition of d margin per game, mean (t 95% CI)')
    order = ['spend: land', 'spend: seeds for SE plantings', 'spend: seeds, rest', 'spend: animals placed on SE',
             'spend: animals, rest', 'spend: wages', 'spend: bought wheat / fertilizer',
             'income: SE output (all products)', 'income: other quadrants output change (all products)',
             'income: harvested-not-sold change (feed / stock / unsold)',
             'income: fertilizer volume (collected - used - held)',
             'price: our units (price change on baseline units)', 'rival: price effect (its baseline units)',
             'rival: volume / spend change']
    tot = [0.0] * n
    for k in order:
        xs = G[k]
        tot = [t + x for t, x in zip(tot, xs)]
        print(f'  {k:60s} {fmt(xs)}')
    res = [D[e]['_residual'] for e in eps]
    print(f'  {"sum of lines":60s} {fmt(tot)}')
    print(f'  {"residual (d margin - sum)":60s} {fmt(res, 2)}')
    print(f'  {"MEASURED d margin":60s} {fmt([D[e]["_margin"] for e in eps])}')
    print(f'  {"  d own cash / d rival cash":60s} {fmt([D[e]["_own"] for e in eps])} / {fmt([D[e]["_rival"] for e in eps])}')
    print('\n== by product: SE output | other-quadrant change | harvested-not-sold | our price effect (per game)')
    for p in PRODS:
        cols = []
        for pre in ('income: SE output, ', 'income: other quadrants, ', 'income: harvested-not-sold change, ', 'price: ours, '):
            xs = [D[e].get(pre + p, 0.0) for e in eps]
            cols.append(f'{st.mean(xs):+8,.0f}')
        print(f'  {p:11s} ' + ' | '.join(cols))
    print('  rival by product (price / volume): ' + ', '.join(
        f'{p.lower()} {st.mean(D[e].get("rival: price, " + p, 0) for e in eps):+,.0f} / {st.mean(D[e].get("rival: volume, " + p, 0) for e in eps):+,.0f}'
        for p in PRODS if any(D[e].get('rival: price, ' + p) or D[e].get('rival: volume, ' + p) for e in eps)))
    # units
    print('\n== units per game: harvested on SE (with-SE) | other quadrants with-SE vs baseline all | sold with-SE vs baseline')
    for p in PRODS[:-1]:
        se_ = [harvest_by_quad(ra[e]).get(('SE', p), 0) for e in eps]
        o1 = [sum(v for (q, pp), v in harvest_by_quad(ra[e]).items() if pp == p and q != 'SE') for e in eps]
        o0 = [sum(v for (q, pp), v in harvest_by_quad(rb[e]).items() if pp == p) for e in eps]
        s1 = [ra[e]['panel']['sold'].get(p, 0) for e in eps]
        s0 = [rb[e]['panel']['sold'].get(p, 0) for e in eps]
        print(f'  {p:11s} SE {st.mean(se_):6.1f} | other {st.mean(o1):6.1f} vs {st.mean(o0):6.1f}: d {fmt([x - y for x, y in zip(o1, o0)], 1)} '
              f'| sold {st.mean(s1):6.1f} vs {st.mean(s0):6.1f}')
    s1 = [ra[e]['panel']['sold'].get('FERTILIZER', 0) for e in eps]
    s0 = [rb[e]['panel']['sold'].get('FERTILIZER', 0) for e in eps]
    print(f'  FERTILIZER  sold {st.mean(s1):.1f} vs {st.mean(s0):.1f}')
    # plantings / deaths / units per planting by quadrant group
    print('\n== crops on the other three quadrants: plantings | died | units harvested | units per planting (with-SE vs baseline)')
    for c in CROPS:
        def cnt(r, kind, se):
            return sum((y if kind == 'harvest' else 1) for k2, day, idx, crop, pd, y in r['events']
                       if k2 == kind and crop == c and ((quad(idx) == 'SE') == se))
        pl1 = [cnt(ra[e], 'plant', False) for e in eps]
        pl0 = [cnt(rb[e], 'plant', False) for e in eps]
        di1 = [cnt(ra[e], 'died', False) for e in eps]
        di0 = [cnt(rb[e], 'died', False) for e in eps]
        h1 = [cnt(ra[e], 'harvest', False) for e in eps]
        h0 = [cnt(rb[e], 'harvest', False) for e in eps]
        se_pl = [cnt(ra[e], 'plant', True) for e in eps]
        se_di = [cnt(ra[e], 'died', True) for e in eps]
        se_h = [cnt(ra[e], 'harvest', True) for e in eps]
        print(f'  {c:11s} plant {st.mean(pl1):5.1f} vs {st.mean(pl0):5.1f} ({fmt([x - y for x, y in zip(pl1, pl0)], 1)}) '
              f'| died {st.mean(di1):4.1f} vs {st.mean(di0):4.1f} | units {st.mean(h1):6.1f} vs {st.mean(h0):6.1f} '
              f'| upp {sum(h1) / max(1, sum(pl1)):.2f} vs {sum(h0) / max(1, sum(pl0)):.2f} || SE: plant {st.mean(se_pl):.1f}, '
              f'died {st.mean(se_di):.1f}, units {st.mean(se_h):.1f}, upp {sum(se_h) / max(1, sum(se_pl)):.2f}')
    print('\n== animals by quadrant group: animal-days | fed share | lost | output per animal-day (with-SE vs baseline)')
    for sp_ in ('GOOSE', 'COW', 'SHEEP'):
        def agg(rows, se):
            ad = fd = lost = out_ = 0
            for e in eps:
                s = animal_stats(rows[e])
                for (q, s2, k), v in s.items():
                    if s2 != sp_ or ((q == 'SE') != se):
                        continue
                    if k == 'animal_days':
                        ad += v
                    elif k == 'fed_days':
                        fd += v
                    elif k == 'lost':
                        lost += v
                out_ += sum(u for day, idx, an, u in rows[e].get('aevents', []) if an == sp_ and ((quad(idx) == 'SE') == se))
            return ad / n, fd / max(1, ad), lost / n, out_ / max(1, ad)
        o1, o0, s1_ = agg(ra, False), agg(rb, False), agg(ra, True)
        print(f'  {sp_:6s} other: days {o1[0]:6.1f} vs {o0[0]:6.1f}, fed {o1[1]:.1%} vs {o0[1]:.1%}, lost {o1[2]:.2f} vs {o0[2]:.2f}, '
              f'out/day {o1[3]:.3f} vs {o0[3]:.3f} || SE: days {s1_[0]:.1f}, fed {s1_[1]:.1%}, lost {s1_[2]:.2f}, out/day {s1_[3]:.3f}')
    # labour
    print('\n== labour unit-steps per game by quadrant (ops + walking charged to the next op), with-SE vs baseline')
    def lab(r, keys_):
        c = Counter()
        for dw in r.get('work', []):
            for k in keys_:
                for kk, v in dw.get(k, {}).items():
                    c[(k, kk)] += v
        return c
    Q = ('NW', 'NE', 'SW', 'SE', 'shed', 'other')
    for q in Q:
        L1 = [lab(ra[e], Q) for e in eps]
        L0 = [lab(rb[e], Q) for e in eps]
        kinds = sorted({kk for L in L1 + L0 for (qq, kk) in L if qq == q})
        tot1 = [sum(v for (qq, kk), v in L.items() if qq == q) for L in L1]
        tot0 = [sum(v for (qq, kk), v in L.items() if qq == q) for L in L0]
        print(f'  {q:5s} total {st.mean(tot1):7.1f} vs {st.mean(tot0):7.1f} ({fmt([x - y for x, y in zip(tot1, tot0)])}): ' + ', '.join(
            f'{kk.replace("op_", "")} {st.mean(L[(q, kk)] for L in L1):.0f}/{st.mean(L[(q, kk)] for L in L0):.0f}' for kk in kinds))
    h1 = [sum(ra[e]['hands']) for e in eps]
    h0 = [sum(rb[e]['hands']) for e in eps]
    print(f'  hand-days (max hands present per day, summed) {st.mean(h1):.1f} vs {st.mean(h0):.1f}: {fmt([x - y for x, y in zip(h1, h0)], 1)}')
    for lo, hi in WINS:
        x = [sum(ra[e]['hands'][lo:hi + 1]) - sum(rb[e]['hands'][lo:hi + 1]) for e in eps]
        print(f'     days {lo:2d}-{hi:2d}: {fmt(x, 1)}')
    # dropped maintenance (idle trace)
    dr1 = {e: idle_dropped(ddir, A, e) for e in eps}
    dr0 = {e: idle_dropped(ddir, B, e) for e in eps}
    if all(v is not None for v in list(dr1.values()) + list(dr0.values())):
        print('\n== dropped maintenance value at 23h (idle trace, module coins), per game, with-SE vs baseline')
        for q in ('NW', 'NE', 'SW', 'SE'):
            x1 = [sum(v for (qq, c), v in dr1[e].items() if qq == q) for e in eps]
            x0 = [sum(v for (qq, c), v in dr0[e].items() if qq == q) for e in eps]
            cmds = sorted({c for e in eps for (qq, c) in list(dr1[e]) + list(dr0[e]) if qq == q})
            print(f'  {q}: {st.mean(x1):7,.0f} vs {st.mean(x0):7,.0f} ({fmt([a_ - b_ for a_, b_ in zip(x1, x0)])}); by cmd ' + ', '.join(
                f'{c} {st.mean(sum(v for (qq, cc), v in dr1[e].items() if qq == q and cc == c) for e in eps):,.0f}/'
                f'{st.mean(sum(v for (qq, cc), v in dr0[e].items() if qq == q and cc == c) for e in eps):,.0f}' for c in cmds))
    # per world
    print('\n== per world: d margin | land | wages | seeds | SE output | other quadrants | not-sold | fert | our price | rival')
    for e in eps:
        g = defaultdict(float)
        for k, v in D[e].items():
            if not k.startswith('_'):
                g[group(k)] += v
        print(f'  {e} {D[e]["_margin"]:+8,.0f} | {g["spend: land"]:+6,.0f} | {g["spend: wages"]:+6,.0f} | '
              f'{g["spend: seeds for SE plantings"] + g["spend: seeds, rest"]:+6,.0f} | {g["income: SE output (all products)"]:+7,.0f} | '
              f'{g["income: other quadrants output change (all products)"]:+7,.0f} | {g["income: harvested-not-sold change (feed / stock / unsold)"]:+6,.0f} | '
              f'{g["income: fertilizer volume (collected - used - held)"]:+6,.0f} | {g["price: our units (price change on baseline units)"]:+6,.0f} | '
              f'{g["rival: price effect (its baseline units)"] + g["rival: volume / spend change"]:+6,.0f}')
    if '--json' in args:
        p = Path(args[args.index('--json') + 1])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(D, indent=0), encoding='utf-8')


if __name__ == '__main__':
    main()
