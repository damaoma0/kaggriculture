"""Supplement to scripts/analyze_price_awareness.py (2026-09-24).

A day-start price is price(I0 - town consumption + DSM net sales + opponent net sales). Town consumption is an exact
function of the ORDERED shop sequence (which shop, revealed when), so the recorded price also carries shop-timing
information that the count features of the shop model do not. Two games with the same shops have the same
shop-implied price price(I0 - consumption); only the player-caused part differs. Here the base model gets the 8
shop-implied prices as extra shop features, and the tested blocks are only the player-caused price parts:
  PLAYER_PRICE = price - price(inv - dsm_net - opp_net)  (8)       PRICE_OPP = price - price(inv - opp_net)  (8)
  CASH, OPP (as in the main script), ALL2 = PLAYER_PRICE + CASH + OPP.
Also: (a) the pre-specified price channels with the channel product's shop-implied price in the base, (b) a
catch-up test: does DSM's day-6 / day-9 cash residual still predict its herd and land at days 9..18, (c) the base R^2
with the older feature definition (k = d // 3 shops, which includes the shop revealed at the day-d boundary).
Output: price_awareness/shopprice.json and shopprice.md.
"""
import json, math, sys
import numpy as np

import analyze_price_awareness as A

OUT = A.OUTDIR


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    games = A.load_games()
    n = len(games)
    groups = np.array([g['ep'] for g in games])
    P = A.SELLABLE

    shopp, player, oppp, rec = {}, {}, {}, {}
    for i, g in enumerate(games):
        for w in range(0, 28):
            t = 24 * w
            for p in P:
                inv = g['inv_day'][w][A.PI[p]]
                dn = A.net_units(g['orders'], p, t); on = A.net_units(g['opp_orders'], p, t)
                pr = g['prices'][t][A.PI[p]]
                ps = A.K.market_price(p, inv - dn - on)
                shopp[i, w, p] = ps; player[i, w, p] = pr - ps; oppp[i, w, p] = pr - A.K.market_price(p, inv - on); rec[i, w, p] = pr

    def blk(i, w, item, name):
        g = games[i]
        if name == 'PLAYER_PRICE':
            return [player[i, w, p] for p in P]
        if name == 'PLAYER_PRICE_OWN':
            return [player[i, w, A.PROD_OF[item]]]
        if name == 'PRICE_OPP':
            return [oppp[i, w, p] for p in P]
        if name == 'CASH':
            m = g['money'][24 * w]
            return [m, math.log1p(max(m, 0))]
        if name == 'OPP':
            oc = g['opp_counts'][w]
            return [A.cnt(oc, item), g['opp_money'][24 * w], sum(A.cnt(oc, a) for a in A.ANIMALS), sum(A.cnt(oc, c) for c in A.CROPS)]
        if name == 'ALL2':
            return blk(i, w, item, 'PLAYER_PRICE') + blk(i, w, item, 'CASH') + blk(i, w, item, 'OPP')
        raise KeyError(name)

    BL = ['PLAYER_PRICE_OWN', 'PLAYER_PRICE', 'PRICE_OPP', 'CASH', 'OPP', 'ALL2']
    cache_path = OUT / '_shopprice_cache.json'
    cached = json.loads(cache_path.read_text(encoding='utf-8')) if cache_path.exists() and '--redo' not in sys.argv else None
    res = dict(level={}, flow={}, base_compare={})
    for d in ([] if cached else A.DAYS):
        w = d - 3
        Xs = np.array([A.shop_feats(g['seq'], (d - 1) // 3) for g in games], float)
        Xsp = np.array([[shopp[i, w, p] for p in P] + [shopp[i, d, p] for p in P] for i in range(n)], float)
        Xsold = np.array([A.shop_feats(g['seq'], d // 3) for g in games], float)
        Xlag = np.array([[A.cnt(g['counts'][w], it) for it in A.ITEMS] for g in games], float)
        base = np.hstack([Xs, Xsp]); basef = np.hstack([Xs, Xsp, Xlag])
        for key in ('level', 'flow', 'base_compare'):
            res[key][d] = {}
        for item in A.ITEMS:
            y = np.array([A.cnt(g['counts'][d], item) for g in games], float)
            if np.var(y) == 0:
                continue
            res['base_compare'][d][item] = dict(
                old_k_d_over_3=round(A.r2(y, A.ridge_logo(Xsold, y, groups)), 3),
                visible_shops=round(A.r2(y, A.ridge_logo(Xs, y, groups)), 3),
                visible_shops_plus_shop_prices=round(A.r2(y, A.ridge_logo(base, y, groups)), 3))
            res['level'][d][item], res['flow'][d][item] = {}, {}
            for b in BL:
                Xk = np.array([blk(i, w, item, b) for i in range(n)], float)
                for key, B in (('level', base), ('flow', basef)):
                    inc = A.incremental(y, B, Xk, groups)
                    res[key][d][item][b] = {k: v for k, v in inc.items() if not k.startswith('_')}
            print(d, item, res['base_compare'][d][item], 'level ALL2', res['level'][d][item]['ALL2']['delta'],
                  res['level'][d][item]['ALL2']['ci'], 'flow ALL2', res['flow'][d][item]['ALL2']['delta'], res['flow'][d][item]['ALL2']['ci'], flush=True)

    if cached:
        res = cached
    else:
        res = json.loads(json.dumps(res, default=float))
        cache_path.write_text(json.dumps(res, default=float), encoding='utf-8')
    # price channels with the product's shop-implied price in the base
    ch = {}
    spec = [('strawberry_plantings', 'STRAWBERRY', lambda g, w, d: A.window_sum(g['plant'], 24 * w, 24 * d, 'STRAWBERRY')),
            ('sheep_bought', 'WOOL', lambda g, w, d: A.filled(g['orders'], 'BUY_ANIMAL', 'SHEEP', 24 * w, 24 * d)),
            ('sheep_count', 'WOOL', lambda g, w, d: A.cnt(g['counts'][d], 'SHEEP')),
            ('cows_bought', 'MILK', lambda g, w, d: A.filled(g['orders'], 'BUY_ANIMAL', 'COW', 24 * w, 24 * d)),
            ('wheat_bought', 'WHEAT', lambda g, w, d: A.filled(g['orders'], 'BUY_PRODUCT', 'WHEAT', 24 * w, 24 * d)),
            ('wheat_planted', 'WHEAT', lambda g, w, d: A.window_sum(g['plant'], 24 * w, 24 * d, 'WHEAT')),
            ('tomato_planted', 'TOMATO', lambda g, w, d: A.window_sum(g['plant'], 24 * w, 24 * d, 'TOMATO')),
            ('carrot_planted', 'CARROT', lambda g, w, d: A.window_sum(g['plant'], 24 * w, 24 * d, 'CARROT'))]
    for d in A.DAYS:
        w = d - 3
        Xs = np.array([A.shop_feats(g['seq'], (d - 1) // 3) for g in games], float)
        Xlag = np.array([[A.cnt(g['counts'][w], it) for it in A.ITEMS] for g in games], float)
        ch[d] = {}
        for name, prod, fy in spec:
            y = np.array([fy(g, w, d) for g in games], float)
            if np.var(y) == 0:
                continue
            base = np.hstack([Xs, Xlag, np.array([[shopp[i, w, prod]] for i in range(n)], float)])
            for part, arr in (('player_part', player), ('opp_part', oppp)):
                x = np.array([arr[i, w, prod] for i in range(n)], float)
                if np.var(x) == 0:
                    ch[d][f'{name}~{prod.lower()}_{part}'] = dict(note='constant across games'); continue
                inc = A.incremental(y, base, x[:, None], groups)
                pc = A.partial_corr(y, x, base, groups)
                sig = inc['ci'][0] > 0 or (pc.get('r_ci') and (pc['r_ci'][0] > 0 or pc['r_ci'][1] < 0))
                if sig:
                    inc = A.incremental(y, base, x[:, None], groups, perm=100)
                rec_ = dict(mean_y=round(float(y.mean()), 2),
                            **{k: v for k, v in inc.items() if not k.startswith('_')}, partial=pc)
                if pc.get('r') is not None:
                    rec_['units_per_sd'] = round(pc['slope'] * pc['sd_x_resid'], 2)
                    rec_['units_per_sd_ci'] = [round(pc['slope_ci'][0] * pc['sd_x_resid'], 2), round(pc['slope_ci'][1] * pc['sd_x_resid'], 2)]
                ch[d][f'{name}~{prod.lower()}_{part}'] = rec_
                print('channel', d, name, part, inc['delta'], inc['ci'], inc.get('perm_p'), 'r', pc.get('r'), pc.get('r_ci'), flush=True)
    res['channels'] = ch

    # catch-up: cash residual at day c vs herd / land / board value at later days (base = shops visible at that day)
    v = json.loads((OUT / 'results.json').read_text(encoding='utf-8'))['value_per_item_day']
    cu = {}
    for c in (6, 9):
        cash = np.array([g['money'][24 * c] for g in games], float)
        cu[c] = {}
        for d in range(c + 1, 19):
            Xs = np.array([A.shop_feats(g['seq'], (d - 1) // 3) for g in games], float)
            Xc = np.hstack([Xs, np.array([A.shop_feats(g['seq'], c // 3) for g in games], float)])
            targets = {
                'animals': np.array([sum(A.cnt(g['counts'][d], a) for a in A.ANIMALS) for g in games], float),
                'animals_bought_since_c': np.array([A.filled(g['orders'], 'BUY_ANIMAL', None, 24 * c, 24 * d) for g in games], float),
                'quadrants': np.array([g['quad'][d] for g in games], float),
                'board_value': np.array([sum(v[it] * A.cnt(g['counts'][d], it) for it in A.ITEMS) for g in games], float),
            }
            cu[c][d] = {}
            for tn, y in targets.items():
                if np.var(y) == 0:
                    cu[c][d][tn] = dict(note='constant'); continue
                pc = A.partial_corr(y, cash, Xc, groups, B=1000)
                if pc.get('r') is None:
                    cu[c][d][tn] = dict(note='no residual variance'); continue
                cu[c][d][tn] = dict(r=pc['r'], r_ci=pc['r_ci'], per_sd=round(pc['slope'] * pc['sd_x_resid'], 2),
                                    per_sd_ci=[round(pc['slope_ci'][0] * pc['sd_x_resid'], 2), round(pc['slope_ci'][1] * pc['sd_x_resid'], 2)],
                                    sd_cash_resid=pc['sd_x_resid'])
            print('catch-up cash d', c, '-> day', d, {k: (x.get('r'), x.get('per_sd')) for k, x in cu[c][d].items()}, flush=True)
    res['catch_up'] = cu
    (OUT / 'shopprice.json').write_text(json.dumps(res, indent=1, default=float), encoding='utf-8')

    # ---- markdown
    L = ['# Supplement: shop-implied prices in the base; only player-caused price parts tested\n']
    L.append('## Base R^2 comparison (LOO, grouped): older features k = d//3 / shops DSM could see / + shop-implied prices\n')
    L.append('| item | ' + ' | '.join(f'd{d}' for d in A.DAYS) + ' |'); L.append('|---' * 7 + '|')
    for it in A.ITEMS:
        L.append(f'| {it} | ' + ' | '.join((lambda x: f"{x['old_k_d_over_3']:.2f} / {x['visible_shops']:.2f} / {x['visible_shops_plus_shop_prices']:.2f}" if x else '–')(res['base_compare'][str(d)].get(it)) for d in A.DAYS) + ' |')
    for key, title in (('level', 'Level (base = visible shops + shop-implied prices)'), ('flow', 'Flow (base = visible shops + shop-implied prices + own day-(d-3) board)')):
        L.append(f'\n## {title}: block summary over 8 items x 6 days\n')
        L.append('| block | cells | median delta | mean delta | max delta | CI low > 0 | CI high < 0 |'); L.append('|---' * 7 + '|')
        for b in BL:
            xs = [res[key][str(d)][it][b] for d in A.DAYS for it in A.ITEMS if res[key][str(d)].get(it)]
            ds = sorted(x['delta'] for x in xs)
            L.append(f"| {b} | {len(xs)} | {ds[len(ds) // 2]:+.3f} | {sum(ds) / len(ds):+.3f} | {ds[-1]:+.3f} | {sum(x['ci'][0] > 0 for x in xs)} | {sum(x['ci'][1] < 0 for x in xs)} |")
        L.append(f'\n{title}: ALL2 per item x day, delta [95% CI]\n')
        L.append('| item | ' + ' | '.join(f'd{d}' for d in A.DAYS) + ' |'); L.append('|---' * 7 + '|')
        for it in A.ITEMS:
            L.append(f'| {it} | ' + ' | '.join((lambda x: f"{x['delta']:+.3f} [{x['ci'][0]:+.2f},{x['ci'][1]:+.2f}]" if x else '–')(res[key][str(d)].get(it, {}).get('ALL2')) for d in A.DAYS) + ' |')
    L.append('\n## Price channels, base = visible shops + own day-(d-3) board + the product\'s shop-implied price\n')
    L.append('| day | channel | mean y | SD y | incr R^2 [CI] | perm p | partial r [CI] | units per 1 SD of x [CI] | SD x (coins) |'); L.append('|---' * 9 + '|')
    for d in A.DAYS:
        for name, x in ch[d].items():
            if 'note' in x:
                L.append(f'| {d} | {name} | | | {x["note"]} | | | | |'); continue
            pc = x['partial']
            if pc.get('r') is None:
                continue
            L.append(f"| {d} | {name} | {x['mean_y']} | {x['sd_y']} | {x['delta']:+.3f} [{x['ci'][0]:+.2f},{x['ci'][1]:+.2f}] | {x.get('perm_p', '')} | "
                     f"{pc['r']:+.2f} [{pc['r_ci'][0]:+.2f},{pc['r_ci'][1]:+.2f}] | {x['units_per_sd']:+.2f} [{x['units_per_sd_ci'][0]:+.2f},{x['units_per_sd_ci'][1]:+.2f}] | {pc['sd_x_resid']} |")
    L.append('\n## Catch-up: DSM cash residual at day c (after shops) vs later herd, land, board value (partial r; effect per 1 SD of cash)\n')
    L.append('| cash day | day | animals r [CI] (per SD) | animals bought since c r (per SD) | quadrants r (per SD) | board value r [CI] (coins/day per SD) | SD cash resid |')
    L.append('|---' * 7 + '|')
    for c in cu:
        for d, x in cu[c].items():
            f = lambda k: (f"{x[k]['r']:+.2f} [{x[k]['r_ci'][0]:+.2f},{x[k]['r_ci'][1]:+.2f}] ({x[k]['per_sd']:+.2f})" if 'r' in x[k] else x[k].get('note', ''))
            sdc = next((x[k]['sd_cash_resid'] for k in x if 'sd_cash_resid' in x[k]), '')
            L.append(f"| {c} | {d} | {f('animals')} | {f('animals_bought_since_c')} | {f('quadrants')} | {f('board_value')} | {sdc} |")
    (OUT / 'shopprice.md').write_text('\n'.join(L) + '\n', encoding='utf-8')
    print('wrote', OUT / 'shopprice.json')


if __name__ == '__main__':
    main()
