"""Season-level cash terms for the price-awareness study (2026-09-24).

S = sum over days 6..29 of the board value index V_d = sum_i v_i * count_i(d) (v_i from results.json: DSM's revenue per
item-day), i.e. DSM's production plan valued in coins. Base = the full revealed shop sequence (+ shop-implied prices at
day 12). Tested blocks at day 6 / 12 (player-caused prices, cash, opponent): out-of-sample increment, and the largest SD
of S they could explain (sqrt of the CI upper bound x SD(S)). Also final cash: SD and shop-model residual.
Output: price_awareness/season_value.json
"""
import json, math, sys
import numpy as np

import analyze_price_awareness as A


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    games = A.load_games(); n = len(games)
    groups = np.array([g['ep'] for g in games])
    v = json.loads((A.OUTDIR / 'results.json').read_text(encoding='utf-8'))['value_per_item_day']
    S = np.array([sum(v[it] * A.cnt(g['counts'][d], it) for d in range(6, 30) for it in A.ITEMS) for g in games], float)
    fin = np.array([g['final'] for g in games], float)
    margin = np.array([g['final'] - g['opp_final'] for g in games], float)

    def player_part(g, w):
        out = []
        for p in A.SELLABLE:
            inv = g['inv_day'][w][A.PI[p]]; t = 24 * w
            out.append(g['prices'][t][A.PI[p]] - A.K.market_price(p, inv - A.net_units(g['orders'], p, t) - A.net_units(g['opp_orders'], p, t)))
        return out

    def shop_price(g, w):
        out = []
        for p in A.SELLABLE:
            inv = g['inv_day'][w][A.PI[p]]; t = 24 * w
            out.append(A.K.market_price(p, inv - A.net_units(g['orders'], p, t) - A.net_units(g['opp_orders'], p, t)))
        return out

    Xs = np.array([A.shop_feats(g['seq'], 8) + shop_price(g, 12) for g in games], float)
    blocks = {
        'CASH_d6': np.array([[g['money'][144], math.log1p(g['money'][144])] for g in games], float),
        'CASH_d12': np.array([[g['money'][288], math.log1p(g['money'][288])] for g in games], float),
        'PLAYER_PRICE_d12': np.array([player_part(g, 12) for g in games], float),
        'OPP_d12': np.array([[g['opp_money'][288]] + [A.cnt(g['opp_counts'][12], it) for it in A.ITEMS] for g in games], float),
    }
    blocks['ALL_d12'] = np.hstack([blocks['CASH_d12'], blocks['PLAYER_PRICE_d12'], blocks['OPP_d12']])
    out = dict(season_value=dict(mean=round(float(S.mean())), sd=round(float(S.std()))), final_cash=dict(mean=round(float(fin.mean())), sd=round(float(fin.std()))),
               margin=dict(mean=round(float(margin.mean())), sd=round(float(margin.std()))))
    pb = A.ridge_logo(Xs, S, groups)
    out['season_value'].update(shop_r2=round(A.r2(S, pb), 3), sd_shop_pred=round(float(np.std(pb))), resid_rmse=round(float(np.sqrt(np.mean((S - pb) ** 2)))))
    pf = A.ridge_logo(Xs, fin, groups)
    out['final_cash'].update(shop_r2=round(A.r2(fin, pf), 3), resid_rmse=round(float(np.sqrt(np.mean((fin - pf) ** 2)))))
    out['blocks'] = {}
    for b, Xk in blocks.items():
        inc = A.incremental(S, Xs, Xk, groups)
        out['blocks'][b] = dict(delta=inc['delta'], ci=inc['ci'], upper_sd_coins=round(math.sqrt(max(0.0, inc['ci'][1])) * float(S.std())),
                                sd_incr_pred_coins=round(float(np.std(inc['_pf'] - inc['_pb']))))
        print(b, out['blocks'][b], flush=True)
    print(json.dumps({k: out[k] for k in ('season_value', 'final_cash', 'margin')}))
    (A.OUTDIR / 'season_value.json').write_text(json.dumps(out, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
