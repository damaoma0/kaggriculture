"""Skeptic re-check (2/3): the three-reason decomposition (production / labour / timing, market depth separately) and
the production split (cutoff / plantings / crop care / animal-days / output per animal-day), re-implemented from the
definitions stated in the analysis text (not imported from gap_analysis.py). Also the opponent-cash side of each arm.
Raw per-(arm, game) JSONs only; one process, no games.
"""
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
from scipy import stats

OUT = Path(__file__).resolve().parent
ARMS = ['LEADER', 'T0', 'T', 'S', 'S0', 'D', 'Dp']
OURS = ARMS[1:]
PRODUCTS = ['WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON', 'EGG', 'MILK', 'WOOL', 'FERTILIZER']
CROPS = ['WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON']
ANIMAL_PRODUCT = {'COW': 'MILK', 'SHEEP': 'WOOL', 'GOOSE': 'EGG'}
# engine 1.32.7 CROPS: first_yield_day, interval, max_yield, ongoing; one-time crops: units at harvest (max_yield_day)
ENG = {'WHEAT': (2, 0, 6, False), 'CARROT': (2, 0, 4, False), 'TOMATO': (8, 1, 4, True),
       'STRAWBERRY': (10, 2, 4, True), 'MELON': (10, 0, 6, False)}
ONE_TIME_POT = {'WHEAT': 4, 'CARROT': 3, 'MELON': 6}   # the analysis' base potential (full water, no fertilizer)
CUTOFF = {'STRAWBERRY': 13, 'TOMATO': 18, 'MELON': 19, 'WHEAT': 25, 'CARROT': 26}


def tci(x):
    x = np.asarray(x, float)
    m = x.mean()
    h = stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / math.sqrt(len(x))
    return m, m - h, m + h


def ft(x):
    m, lo, hi = tci(x)
    return f'{m:+8,.0f} ({lo:+,.0f}..{hi:+,.0f})'


def potential(crop, d):
    first, interval, mx, ongoing = ENG[crop]
    if ongoing:
        # production j is credited at the end of day d + first - 1 + j*interval, harvestable next day; last day 29
        return sum(1 for j in range(mx) if d + first + j * interval <= 29)
    if 29 - d < first:
        return 0
    return 6 if crop == 'MELON' else min(ONE_TIME_POT[crop], 29 - d)


def fill(prices):
    """linear interpolation over days with no sale, flat at the ends"""
    xs = [d for d in range(30) if prices[d] is not None]
    if not xs:
        return np.zeros(30)
    return np.interp(np.arange(30), xs, [prices[d] for d in xs])


W = json.loads((OUT / 'worlds.json').read_text(encoding='utf-8'))
worlds = {w['episode']: w for w in W['worlds']}
R = {a: {} for a in ARMS}
for a in ARMS:
    for f in sorted((OUT / a).glob('*.json')):
        r = json.loads(f.read_text(encoding='utf-8'))
        R[a][r['episode']] = r
common = sorted(worlds)
union = set()
for a in ARMS:
    union |= {e for e in common if R[a][e]['opp_final'] < 0.8 * R[a][e]['target_opp']}
union |= {e for e in common if worlds[e]['flags']}
clean = [e for e in common if e not in union]


def dser(r, key, p):
    return np.array([dd.get(key, {}).get(p, 0) for dd in r['days']], float)


def decompose(L, X):
    tL, tX = L['totals'], X['totals']
    out = Counter()
    PL, PX = {}, {}
    for p in PRODUCTS:
        qL, qX = tL['sold'].get(p, 0), tX['sold'].get(p, 0)
        rL, rX = tL['rev'].get(p, 0), tX['rev'].get(p, 0)
        PL[p] = rL / qL if qL else (rX / qX if qX else 0.0)
        PX[p] = rX / qX if qX else PL[p]
    # revenue identity pieces
    for p in PRODUCTS:
        qL, qX = tL['sold'].get(p, 0), tX['sold'].get(p, 0)
        if p == 'FERTILIZER':
            hL, hX = qL, qX
        else:
            hL, hX = tL['harvested'].get(p, 0), tX['harvested'].get(p, 0)
        out['A'] += (hL - hX) * PL[p]
        out['C1'] += -((hL - qL) - (hX - qX)) * PL[p]
        # C2 split into timing / depth using daily realised prices
        dqL, dqX = dser(L, 'sold', p), dser(X, 'sold', p)
        drL, drX = dser(L, 'rev', p), dser(X, 'rev', p)
        c2 = qX * (PL[p] - PX[p])
        if dqL.sum() == 0 or dqX.sum() == 0:
            out['depth'] += c2
            continue
        pLd = fill([drL[d] / dqL[d] if dqL[d] else None for d in range(30)])
        pXd = fill([drX[d] / dqX[d] if dqX[d] else None for d in range(30)])
        wL, wX = dqL / dqL.sum(), dqX / dqX.sum()
        tim = dqX.sum() * float(((wL - wX) * pXd).sum())
        dep = dqX.sum() * float((wL * (pLd - pXd)).sum())
        assert abs(tim + dep - c2) < 1e-6
        out['timing_moved'] += tim
        out['depth'] += dep
        out[f'depth_{p}'] += dep
        out[f'timing_{p}'] += tim
        if p not in ('WHEAT', 'FERTILIZER'):
            hdL, hdX = dser(L, 'harv', p), dser(X, 'harv', p)
            if hdL.sum() and hdX.sum():
                out['later_supply'] += dqX.sum() * float(((hdL / hdL.sum() - hdX / hdX.sum()) * pXd).sum())
    # purchases
    def cat(k):
        return 'animals' if k in ANIMAL_PRODUCT else 'wheat' if k == 'WHEAT' else 'fert' if k == 'FERTILIZER' else 'seeds'
    sp = {s: Counter() for s in 'LX'}
    for s, t in (('L', tL), ('X', tX)):
        for k, v in t['spend'].items():
            sp[s][cat(k)] += v
    for k in ('animals', 'wheat', 'fert', 'seeds'):
        out['buy_' + k] = sp['X'][k] - sp['L'][k]
    out['land'] = tX['land_spend'] - tL['land_spend']
    out['wages'] = tX['wages'] - tL['wages']
    # C1 components: fed wheat, discards, wheat bought as product (bought - planted), held at end = rest
    fedL, fedX = tL['eff_ops'].get('FEED', 0), tX['eff_ops'].get('FEED', 0)
    out['c1_fed'] = -(fedL - fedX) * PL['WHEAT']
    out['c1_disc'] = -sum((tL['discards'].get(p, 0) - tX['discards'].get(p, 0)) * PL[p] for p in PRODUCTS if p != 'FERTILIZER')
    bpL = max(0, tL['bought'].get('WHEAT', 0) - tL['plant'].get('WHEAT', 0))
    bpX = max(0, tX['bought'].get('WHEAT', 0) - tX['plant'].get('WHEAT', 0))
    out['c1_bought'] = (bpL - bpX) * PL['WHEAT']
    out['c1_held'] = out['C1'] - out['c1_fed'] - out['c1_disc'] - out['c1_bought']
    gap = L['final'] - X['final']
    out['PRODUCTION'] = (out['A'] + out['buy_animals'] + out['buy_wheat'] + out['buy_fert'] + out['buy_seeds'] + out['land']
                         + out['c1_fed'] + out['c1_disc'] + out['c1_bought'])
    out['LABOUR'] = out['wages']
    out['TIMING'] = out['timing_moved'] + out['c1_held']
    out['DEPTH'] = out['depth']
    out['resid'] = gap - out['PRODUCTION'] - out['LABOUR'] - out['TIMING'] - out['DEPTH']
    out['gap'] = gap
    # production split of A
    cut_applies = X['arm'] in ('T0', 'T', 'S', 'S0')
    for c in CROPS:
        agg = {}
        for s, r in (('L', L), ('X', X)):
            n = pot = post = 0
            for d, dd in enumerate(r['days']):
                k = dd.get('plant', {}).get(c, 0)
                pot += k * potential(c, d)
                if d > CUTOFF[c]:
                    post += k * potential(c, d)
            agg[s] = (pot, post, r['totals']['harvested'].get(c, 0))
        (pL, postL, hL), (pX, _, hX) = agg['L'], agg['X']
        rL = hL / pL if pL else None
        rX = hX / pX if pX else None
        if rL is None and rX is None:
            out['crop_care'] += (hL - hX) * PL[c]
            continue
        rL = rX if rL is None else rL
        rX = rL if rX is None else rX
        plant = (pL - pX) * rL * PL[c]
        care = (hL - hX) * PL[c] - plant
        cut = postL * rL * PL[c] if cut_applies else 0.0
        out['cutoff'] += cut
        out['plantings'] += plant - cut
        out['crop_care'] += care
        out[f'harvgap_{c}'] += (hL - hX) * PL[c]
    for sp_, prod in ANIMAL_PRODUCT.items():
        adL = sum(q['occ_tile_days'].get(sp_, 0) for q in L['quadrants'].values())
        adX = sum(q['occ_tile_days'].get(sp_, 0) for q in X['quadrants'].values())
        hL, hX = L['totals']['harvested'].get(prod, 0), X['totals']['harvested'].get(prod, 0)
        yL = hL / adL if adL else (hX / adX if adX else 0.0)
        days_term = (adL - adX) * yL * PL[prod]
        out['animal_days'] += days_term
        out['animal_yield'] += (hL - hX) * PL[prod] - days_term
    out['fert_sold'] = (L['totals']['sold'].get('FERTILIZER', 0) - X['totals']['sold'].get('FERTILIZER', 0)) * PL['FERTILIZER']
    out['split_resid'] = out['A'] - sum(out[k] for k in ('cutoff', 'plantings', 'crop_care', 'animal_days', 'animal_yield', 'fert_sold'))
    # opponent side
    out['opp_delta'] = X['opp_final'] - L['opp_final']        # + = opponent richer against us than against the leader
    out['margin_gap'] = (L['final'] - L['opp_final']) - (X['final'] - X['opp_final'])
    return out


DEC = {a: {e: decompose(R['LEADER'][e], R[a][e]) for e in common} for a in OURS}
print('max |residual| of the three-reason identity per arm:',
      {a: max(abs(DEC[a][e]['resid']) for e in common) for a in OURS})
print('max |residual| of the production split per arm:', {a: max(abs(DEC[a][e]['split_resid']) for e in common) for a in OURS})
keys = ['gap', 'PRODUCTION', 'LABOUR', 'TIMING', 'DEPTH', 'A', 'cutoff', 'plantings', 'crop_care', 'animal_days',
        'animal_yield', 'fert_sold', 'buy_seeds', 'buy_animals', 'land', 'buy_wheat', 'buy_fert', 'c1_bought', 'c1_fed',
        'c1_disc', 'timing_moved', 'c1_held', 'later_supply']
for sub, es in (('ALL 48', common), (f'CLEAN {len(clean)}', clean)):
    print(f'\n=== {sub} worlds: mean (paired-t 95% CI), positive = leader ahead')
    print(f'{"line":14s}' + ''.join(f'{a:>30s}' for a in OURS))
    for k in keys:
        print(f'{k:14s}' + ''.join(f'{ft([DEC[a][e][k] for e in es]):>30s}' for a in OURS))
    print(f'{"prod+depth":14s}' + ''.join(f'{ft([DEC[a][e]["PRODUCTION"] + DEC[a][e]["DEPTH"] for e in es]):>30s}' for a in OURS))
    print(f'{"wheat+fert buy":14s}' + ''.join(
        f'{ft([DEC[a][e]["buy_wheat"] + DEC[a][e]["buy_fert"] + DEC[a][e]["c1_bought"] for e in es]):>30s}' for a in OURS))

# shares for T
T = DEC['T']
g = np.mean([T[e]['gap'] for e in common])
pd_ = np.mean([T[e]['PRODUCTION'] + T[e]['DEPTH'] for e in common])
print(f'\nT shares of the gap: production net of depth {pd_ / g:.1%}, labour {np.mean([T[e]["LABOUR"] for e in common]) / g:.1%}, '
      f'timing {np.mean([T[e]["TIMING"] for e in common]) / g:.1%}')
print('T harvest gap per crop at leader price:', {c: round(np.mean([T[e][f'harvgap_{c}'] for e in common])) for c in CROPS})
print('T depth per product:', {p: round(np.mean([T[e][f'depth_{p}'] for e in common])) for p in PRODUCTS})

# ---------------------------------------------------------------- opponent side (not in the analysis)
print('\nopponent cash vs its recorded cash, and margin gap (leader margin - our margin), mean (t CI):')
for a in OURS:
    for sub, es in (('all', common), ('clean', clean)):
        od = [DEC[a][e]['opp_delta'] for e in es]
        mg = [DEC[a][e]['margin_gap'] for e in es]
        up = sum(1 for e in es if R[a][e]['opp_final'] > R[a][e]['target_opp'])
        print(f'  {a:4s} {sub:5s} opp +{ft(od)}  opp richer in {up}/{len(es)} | own gap {ft([DEC[a][e]["gap"] for e in es])} '
              f'| margin gap {ft(mg)} | leader-margin wins lost: '
              f'{sum(1 for e in es if R["LEADER"][e]["final"] > R["LEADER"][e]["opp_final"] and R[a][e]["final"] <= R[a][e]["opp_final"])}'
              f' (leader wins {sum(1 for e in es if R["LEADER"][e]["final"] > R["LEADER"][e]["opp_final"])}, arm wins '
              f'{sum(1 for e in es if R[a][e]["final"] > R[a][e]["opp_final"])})')
# correlation of opponent gain with our production shortfall (market channel?)
for a in ('T', 'S', 'D'):
    x = [DEC[a][e]['A'] for e in clean]
    y = [DEC[a][e]['opp_delta'] for e in clean]
    print(f'  corr(our output shortfall A, opponent gain) {a} clean: r={np.corrcoef(x, y)[0, 1]:+.2f}')
