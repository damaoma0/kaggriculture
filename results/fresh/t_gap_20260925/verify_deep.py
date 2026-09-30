"""Independent spot checks of headline numbers in deep.txt (stored data only, one process, own code).

  1. C2 split: market depth / timing (our and leader daily prices) / later supply / holding, plus sensitivity to
     the price imputation on no-sale days and to the supply definition.
  2. Crops: plantings (and after T's plant_cutoff) and the 'fewer plantings x leader units per planting' memo.
  3. Shed: midnight shed-cap discards and end holdings from the day-0..28 stock identity; valued at P_L.
  Plus: animal escapes, sales below 10% of base, failed seed buys, and the frozen opponent's cash (margin view).
Uses the local copy results/fresh/lead_ledger (identical to E1's ledger on every shared field, see verify_top.py)
because E1's ledger lacks overflow / shed_after.
"""
import json
import math
import statistics as st
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LOC = ROOT / 'results/fresh/lead_ledger'
PRODUCTS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"]
CROPS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"]
BASE = {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120, "MELON": 250, "EGG": 50, "MILK": 160,
        "WOOL": 200, "FERTILIZER": 100}
CUTOFF = {"STRAWBERRY": 13, "TOMATO": 18, "MELON": 19, "WHEAT": 25, "CARROT": 26}   # agents/mgt_lead.py line 80
FOUR = {'112449129', '112655730', '112661570', '112667461', '112673479', '112708229', '112714050', '112721923'}
T95 = {12: 2.201, 8: 2.365}


def ci(xs):
    m = st.mean(xs)
    h = T95.get(len(xs), 2.0) * st.stdev(xs) / math.sqrt(len(xs))
    return f'{m:+9,.0f} ({m - h:+,.0f}..{m + h:+,.0f})'


def csum(r, key):
    c = Counter()
    for d in r['days']:
        c.update(d.get(key) or {})
    return c


def opsum(day, prefix):
    return sum(v for k, v in (day.get('opk') or {}).items() if k.startswith(prefix))


def net_flow(day, p):
    v = (day.get('harv') or {}).get(p, 0) - (day.get('sold') or {}).get(p, 0)
    if p == 'WHEAT':
        v += (day.get('bought') or {}).get('BUY_PRODUCT:WHEAT', 0) - opsum(day, 'FEED:')
    if p == 'FERTILIZER':
        v += (day.get('bought') or {}).get('BUY_PRODUCT:FERTILIZER', 0) + opsum(day, 'COLLECT_FERTILIZER:') \
            - opsum(day, 'FERTILIZE:')
    return v


def shed_check(r):
    """Stock identity days 0..28: stock_after(d) = stock_after(d-1) + net_flow(d) - overflow(d)."""
    prev, disc, bad = Counter(), Counter(), 0
    for d in range(29):
        day = r['days'][d]
        after = Counter({k: v for k, v in (day.get('shed_after') or {}).items() if k in PRODUCTS})
        for p in PRODUCTS:
            ov = (day.get('overflow') or {}).get(p, 0)
            disc[p] += ov
            if prev[p] + net_flow(day, p) - ov != after[p]:
                bad += 1
        prev = after
    held = Counter({p: prev[p] + net_flow(r['days'][29], p) for p in PRODUCTS})
    return disc, held, bad


def impute(prices, how):
    obs = [d for d in range(30) if prices[d] is not None]
    out = []
    for d in range(30):
        if prices[d] is not None:
            out.append(prices[d])
            continue
        lo = [o for o in obs if o < d]
        hi = [o for o in obs if o > d]
        if how == 'linear' and lo and hi:
            a, b = lo[-1], hi[0]
            out.append(prices[a] + (prices[b] - prices[a]) * (d - a) / (b - a))
        elif how == 'carry' and lo:
            out.append(prices[lo[-1]])
        else:
            out.append(prices[lo[-1]] if lo else prices[hi[0]])
    return out


def c2_split(L, O, p, how='linear', supply_mode='net'):
    qL = [(d.get('sold') or {}).get(p, 0) for d in L['days']]
    qO = [(d.get('sold') or {}).get(p, 0) for d in O['days']]
    rL = [(d.get('rev') or {}).get(p, 0) for d in L['days']]
    rO = [(d.get('rev') or {}).get(p, 0) for d in O['days']]
    QL, QO = sum(qL), sum(qO)
    PL = sum(rL) / QL if QL else 0.0
    PO = sum(rO) / QO if QO else PL
    c2 = QO * (PL - PO)
    if QL == 0 or QO == 0:
        return dict(c2=c2, depth=c2, timing=0, timing_alt=0, supply=0, hold=0, supply_alt=0, hold_alt=0)
    pL = impute([rL[d] / qL[d] if qL[d] else None for d in range(30)], how)
    pO = impute([rO[d] / qO[d] if qO[d] else None for d in range(30)], how)
    wL = [x / QL for x in qL]
    wO = [x / QO for x in qO]
    timing = QO * sum((wL[d] - wO[d]) * pO[d] for d in range(30))
    depth = c2 - timing
    timing_alt = QO * sum((wL[d] - wO[d]) * pL[d] for d in range(30))

    def sup(r):
        s = []
        for day in r['days']:
            h = (day.get('harv') or {}).get(p, 0)
            b = (day.get('bought') or {}).get('BUY_PRODUCT:' + p, 0)
            if p == 'WHEAT':
                v = h + b - (opsum(day, 'FEED:') if supply_mode != 'gross' else 0)
            elif p == 'FERTILIZER':
                v = opsum(day, 'COLLECT_FERTILIZER:') + b - (opsum(day, 'FERTILIZE:') if supply_mode != 'gross' else 0)
            else:
                v = h
            if supply_mode == 'clip':
                v = max(0, v)
            s.append(v)
        return s
    sL, sO = sup(L), sup(O)
    if sum(sL) <= 0 or sum(sO) <= 0:
        return dict(c2=c2, depth=depth, timing=timing, timing_alt=timing_alt, supply=float('nan'), hold=float('nan'),
                    supply_alt=float('nan'), hold_alt=float('nan'), neg=True)
    vL = [x / sum(sL) for x in sL]
    vO = [x / sum(sO) for x in sO]
    supply = QO * sum((vL[d] - vO[d]) * pO[d] for d in range(30))
    supply_alt = QO * sum((vL[d] - vO[d]) * pL[d] for d in range(30))
    neg = any(x < 0 for x in sL + sO)
    return dict(c2=c2, depth=depth, timing=timing, timing_alt=timing_alt, supply=supply, hold=timing - supply,
                supply_alt=supply_alt, hold_alt=timing_alt - supply_alt, neg=neg)


def main():
    eps = sorted(p.name[7:-5] for p in LOC.glob('leader_1*.json'))
    rows = []
    for ep in eps:
        L = json.load(open(LOC / f'leader_{ep}.json'))
        O = json.load(open(LOC / f'ours_{ep}.json'))
        row = dict(ep=ep, four=ep in FOUR)
        PL = {}
        for p in PRODUCTS:
            q, rv = csum(L, 'sold')[p], csum(L, 'rev')[p]
            qo, rvo = csum(O, 'sold')[p], csum(O, 'rev')[p]
            PL[p] = rv / q if q else (rvo / qo if qo else 0.0)
        # 1. C2 split, several variants
        for how in ('linear', 'carry', 'nearest'):
            for sm in ('net', 'gross', 'clip'):
                parts = [c2_split(L, O, p, how, sm) for p in PRODUCTS]
                key = f'{how}/{sm}'
                row[key] = {k: sum(x[k] for x in parts) for k in ('c2', 'depth', 'timing', 'timing_alt', 'supply',
                                                                  'hold', 'supply_alt', 'hold_alt')}
                row[key + '/neg'] = [p for p, x in zip(PRODUCTS, parts) if x.get('neg')]
                if how == 'linear' and sm == 'net':
                    row['c2_p'] = {p: x for p, x in zip(PRODUCTS, parts)}
        # 2. crops
        plL, plO = csum(L, 'plant'), csum(O, 'plant')
        hL = csum(L, 'harv')
        memo = 0.0
        post = {}
        for c in CROPS:
            if plL[c]:
                memo += (plL[c] - plO[c]) * hL[c] / plL[c] * PL[c]
            post[c] = (sum((d.get('plant') or {}).get(c, 0) for i, d in enumerate(L['days']) if i > CUTOFF[c]),
                       sum((d.get('plant') or {}).get(c, 0) for i, d in enumerate(O['days']) if i > CUTOFF[c]))
        row['plant_memo'] = memo
        row['plantings'] = {c: (plL[c], plO[c]) for c in CROPS}
        row['post_cutoff'] = post
        # 3. shed stock identity, discards and holdings
        dL, heL, badL = shed_check(L)
        dO, heO, badO = shed_check(O)
        row['shed_bad'] = badL + badO
        row['disc_units'] = (sum(dL.values()), sum(dO.values()), dL['WHEAT'], dO['WHEAT'])
        row['disc_value'] = sum(-(dL[p] - dO[p]) * PL[p] for p in PRODUCTS)
        row['held_value'] = sum(-(heL[p] - heO[p]) * PL[p] for p in PRODUCTS)
        row['held_units'] = (sum(heL.values()), sum(heO.values()))
        # extras
        escL = sum(v for k, v in csum(L, 'died').items() if k.startswith('animal_'))
        escO = sum(v for k, v in csum(O, 'died').items() if k.startswith('animal_'))
        row['esc'] = (escL, escO)
        low = {}
        for p in ('MILK', 'WOOL'):
            f = lambda r: sum((d.get('sold') or {}).get(p, 0) for d in r['days']
                              if (d.get('sold') or {}).get(p, 0)
                              and d['rev'][p] / d['sold'][p] < 0.1 * BASE[p])
            low[p] = (f(L), f(O))
        row['low'] = low
        row['failed_seed'] = (sum(v for k, v in csum(L, 'failed').items() if k.startswith('BUY_SEED')),
                              sum(v for k, v in csum(O, 'failed').items() if k.startswith('BUY_SEED')))
        row['gap'] = L['final'] - O['final']
        row['opp_gain'] = O['opp_final'] - L['opp_final']
        row['margin_gap'] = (L['final'] - L['opp_final']) - (O['final'] - O['opp_final'])
        row['win'] = (L['final'] > L['opp_final'], O['final'] > O['opp_final'])
        rows.append(row)

    for lab, sel in (('all 12', rows), ('four-quadrant 8', [r for r in rows if r['four']])):
        g = len(sel)
        print(f'\n===== {lab} (n={g})')
        print('1. C2 split (deep.txt all 12: C2 -7,852, depth -15,202, timing +7,350, later supply +5,921, holding +1,429;'
              ' leader prices: timing +8,304, supply +7,982, holding +322)')
        for key in ('linear/net', 'linear/gross', 'linear/clip', 'carry/net', 'nearest/net'):
            vals = {k: [r[key][k] for r in sel] for k in sel[0][key]}
            neg = sorted({p for r in sel for p in r[key + '/neg']})
            print(f'  {key:13s} C2 {ci(vals["c2"])} | depth {ci(vals["depth"])} | timing {ci(vals["timing"])} | '
                  f'supply {ci(vals["supply"])} | hold {ci(vals["hold"])}')
            print(f'  {"":13s} at leader prices: timing {ci(vals["timing_alt"])} | supply {ci(vals["supply_alt"])} | '
                  f'hold {ci(vals["hold_alt"])}   (products with negative daily supply: {neg})')
        print('  per product (linear/net): depth / timing / supply / hold')
        for p in PRODUCTS:
            m = lambda k: sum(r['c2_p'][p][k] for r in sel) / g
            print(f'    {p:11s} {m("depth"):+8,.0f} {m("timing"):+8,.0f} {m("supply"):+8,.0f} {m("hold"):+8,.0f}')
        print('2. crops (deep.txt all 12: memo fewer plantings x leader units +13,497; wheat 171.1/134.6, after cutoff'
              ' 15.4/0.0)')
        print('  memo', ci([r['plant_memo'] for r in sel]))
        for c in CROPS:
            print(f'  {c:11s} plantings L/O {sum(r["plantings"][c][0] for r in sel) / g:6.1f}/'
                  f'{sum(r["plantings"][c][1] for r in sel) / g:6.1f}  after cutoff day {CUTOFF[c]}: '
                  f'{sum(r["post_cutoff"][c][0] for r in sel) / g:4.1f}/{sum(r["post_cutoff"][c][1] for r in sel) / g:4.1f}')
        print('3. shed (deep.txt all 12: shed-cap loss +1,053, units 8.7/31.6, wheat 3.2/16.1; held at end +183)')
        print('  stock identity failures:', sum(r['shed_bad'] for r in sel))
        print('  discards value', ci([r['disc_value'] for r in sel]), ' units L/O %.1f/%.1f wheat %.1f/%.1f' % tuple(
            sum(r['disc_units'][i] for r in sel) / g for i in range(4)))
        print('  held at end value', ci([r['held_value'] for r in sel]), ' units L/O %.1f/%.1f' % tuple(
            sum(r['held_units'][i] for r in sel) / g for i in range(2)))
        print('extras: escapes L/O %.2f/%.2f; milk sold <10%% base L/O %.1f/%.1f; wool %.1f/%.1f; failed seed buys L/O '
              '%.2f/%.2f' % (sum(r['esc'][0] for r in sel) / g, sum(r['esc'][1] for r in sel) / g,
                             sum(r['low']['MILK'][0] for r in sel) / g, sum(r['low']['MILK'][1] for r in sel) / g,
                             sum(r['low']['WOOL'][0] for r in sel) / g, sum(r['low']['WOOL'][1] for r in sel) / g,
                             sum(r['failed_seed'][0] for r in sel) / g, sum(r['failed_seed'][1] for r in sel) / g))
        print('margin view: cash gap', ci([r['gap'] for r in sel]), '| frozen opponent gains vs T',
              ci([r['opp_gain'] for r in sel]), '| margin gap', ci([r['margin_gap'] for r in sel]),
              '| wins leader %d, T %d' % (sum(r['win'][0] for r in sel), sum(r['win'][1] for r in sel)))
    Path(__file__).with_name('verify_deep.json').write_text(json.dumps(rows, indent=1, default=str), encoding='utf-8')


if __name__ == '__main__':
    main()
