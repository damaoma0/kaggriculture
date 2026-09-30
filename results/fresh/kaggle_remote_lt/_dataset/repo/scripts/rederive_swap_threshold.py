"""Re-derive the strawberry -> tomato swap threshold for a given tomato yield per plant.

Uses the day-10 model inputs logged in her 30 worlds (mg3_probe3) and the calibrated market model (sales
spread over 4 days, scripts/calibrate_straw_model.py). For each world and tomato yield u, it finds the keep
count k (0..n strawberries kept of the day-11 batch, the rest tomatoes) that maximises margin, net of seeds
(tomato 50, strawberry 100) and the fertilizer the tape would have used on the dropped strawberries (sold at the
logged price, minus the one unit a fertilized tomato uses when u > 4). It reports each world's forecast batch
strawberry price, the optimal k, and the price at which the decision flips from 'swap all' to 'keep all'.
"""
import glob, json, statistics as st, sys
from market_corpus import ROOT
from calibrate_straw_model import market

W = 4


def load(v):
    return {json.load(open(p))['episode']: json.load(open(p)) for p in glob.glob(str(ROOT / f'results/fresh/mg_slots/{v}-*.json'))}


def evaluate(d, u_tomato, F=1.875):
    base = {int(k): v for k, v in d['base_ours'].items()}
    opp = {int(k): v for k, v in d['opp_by_day'].items()}
    shops, day0 = d['shops'], d['day0']
    P = sorted(d['batch_P'])
    n = len(P)
    fert_price = float(d['prices'].get('FERTILIZER') or 30)
    fe = d['fe']
    out = {}
    for k in range(n + 1):
        so = dict(base)
        for p in P[:k]:
            for j in range(4):
                x = p + 10 + 2 * j
                if x <= 29:
                    so[x] = so.get(x, 0.0) + F
        rs_o, rs_p = market('STRAWBERRY', d['inv']['STRAWBERRY'], day0, shops, so, opp, 'spread', W)
        t = n - k
        to = {}
        for p in P[k:]:
            for j in range(4):
                to[p + 8 + j] = to.get(p + 8 + j, 0.0) + u_tomato / 4.0
        rt_o = market('TOMATO', d['inv']['TOMATO'], day0, shops, to, {}, 'spread', W)[0] if t else 0.0
        used = t if u_tomato > 4 else 0
        fert = fert_price * (sum(fe[k:]) - used)
        cost = 50.0 * t - 100.0 * t
        out[k] = (rs_o + rt_o + fert - cost, rs_p, rs_o / max(1e-9, sum(so.values())))
    return out, n


def main():
    probe = load('mg3_probe3')
    for u in (4.0, 5.0, 6.0):
        rows = []
        for eid, r in probe.items():
            d = r['telemetry'].get('econ_diag')
            if not d:
                continue
            res, n = evaluate(d, u)
            base_o, base_p, price = res[n]
            best_k = max(res, key=lambda k: (res[k][0] - base_o) - (res[k][1] - base_p))
            gain = (res[best_k][0] - base_o) - (res[best_k][1] - base_p)
            rows.append((price, best_k, n, gain, eid))
        rows.sort()
        swap = [r for r in rows if r[1] < r[2] / 2]
        keep = [r for r in rows if r[1] >= r[2] / 2]
        lo = max((r[0] for r in swap), default=float('nan'))
        hi = min((r[0] for r in keep), default=float('nan'))
        print(f'tomato {u:.0f} units/plant: swap (keep < half) in {len(swap)}/{len(rows)} worlds; '
              f'highest forecast strawberry price still swapped {lo:.0f}, lowest kept {hi:.0f}; '
              f'predicted mean margin gain {st.mean(r[3] for r in rows):+,.0f}')
        if '-v' in sys.argv:
            for r in rows:
                print(f'    price {r[0]:6.1f}  keep {r[1]:2d}/{r[2]}  gain {r[3]:+7,.0f}  {r[4]}')


if __name__ == '__main__':
    main()
