"""Offline check of the strawberry market model against observed swap outcomes.

Inputs: the day-10 model inputs logged by the dry-run probe (mg3_probe3) in each of her 30 worlds, and the
observed own/opponent strawberry revenue change when the whole day-11 batch became tomatoes (mg3_t11v vs
mgs_null). The model varies only in how sales are timed: 'same_day' (every unit sold on its harvest day, the
first version), or 'spread' (each day's harvest sold evenly over the next W days, with consumption applied in
six slots per day as the engine does every 4 turns).
"""
import glob, json, statistics as st, sys
from market_corpus import ROOT
from kaggle_environments.envs.kaggriculture.kaggriculture import market_price

SHOPS = {'BAKERY': ('EGG', 'WHEAT'), 'PIZZA_SHOP': ('MILK', 'TOMATO', 'WHEAT'),
         'BRUNCH_SPOT': ('EGG', 'WHEAT', 'STRAWBERRY'), 'YARN_STORE': ('WOOL',),
         'ICE_CREAM_SHOP': ('STRAWBERRY', 'MILK', 'WHEAT'), 'PET_CAFE': ('CARROT',),
         'SMOOTHIE_SHOP': ('STRAWBERRY', 'MILK'), 'FARMERS_MARKET': ('WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY')}


def rate(shop, product):
    d = SHOPS.get(shop, ())
    return (12.0 if len(d) == 1 else 6.0) if product in d else 0.0


def daily(shops, product, day, known_only=None):
    total = 1.0
    expected = sum(rate(s, product) for s in SHOPS) / 8.0
    for i in range(8):
        if 3 * (i + 1) > day:
            break
        total += rate(shops[i], product) if i < len(shops) else expected
    return total


def market(product, inv0, day0, shops, ours, opp, mode='spread', W=3):
    """Revenue (ours, opp). mode 'same_day' = first version; 'spread' = harvest sold over W days, 6 slots/day."""
    inv = float(inv0)
    r_o = r_p = 0.0
    if mode == 'same_day':
        co = cp = 0.0
        for d in range(day0, 30):
            inv -= daily(shops, product, d)
            co += ours.get(d, 0.0); cp += opp.get(d, 0.0)
            a, b = int(co), int(cp); co -= a; cp -= b
            while a > 0 or b > 0:
                if a > 0:
                    r_o += market_price(product, int(round(inv))); inv += 1; a -= 1
                if b > 0:
                    r_p += market_price(product, int(round(inv))); inv += 1; b -= 1
        return r_o, r_p
    # spread: per-slot sale quotas
    so, sp = {}, {}
    for sched, q in ((ours, so), (opp, sp)):
        for d, u in sched.items():
            days = [x for x in range(d, min(30, d + W))] or [29]
            for x in days:
                for k in range(6):
                    q[(x, k)] = q.get((x, k), 0.0) + u / (len(days) * 6.0)
    co = cp = 0.0
    for d in range(day0, 30):
        per = daily(shops, product, d)
        for k in range(6):
            inv -= (per - 1.0) / 6.0 + (1.0 if k == 0 else 0.0)
            co += so.get((d, k), 0.0); cp += sp.get((d, k), 0.0)
            a, b = int(co), int(cp); co -= a; cp -= b
            while a > 0 or b > 0:
                if a > 0:
                    r_o += market_price(product, int(round(inv))); inv += 1; a -= 1
                if b > 0:
                    r_p += market_price(product, int(round(inv))); inv += 1; b -= 1
    return r_o, r_p


def load(v):
    return {json.load(open(p))['episode']: json.load(open(p)) for p in glob.glob(str(ROOT / f'results/fresh/mg_slots/{v}-*.json'))}


def predict(d, keep, mode, W, F=1.875):
    base = {int(k): v for k, v in d['base_ours'].items()}
    opp = {int(k): v for k, v in d['opp_by_day'].items()}
    shops, day0 = d['shops'], d['day0']
    def straw(k):
        so = dict(base)
        for P in sorted(d['batch_P'])[:k]:
            for j in range(4):
                x = P + 10 + 2 * j
                if x <= 29:
                    so[x] = so.get(x, 0.0) + F
        return market('STRAWBERRY', d['inv']['STRAWBERRY'], day0, shops, so, opp, mode, W)
    n = len(d['batch_P'])
    b_o, b_p = straw(n)
    k_o, k_p = straw(keep)
    return k_o - b_o, k_p - b_p, b_o


def main():
    probe, null, t = load('mg3_probe3'), load('mgs_null'), load('mg3_t11v')
    for mode, W in (('same_day', 1), ('spread', 2), ('spread', 3), ('spread', 4), ('spread', 6)):
        rows = []
        for eid, r in probe.items():
            d = r['telemetry'].get('econ_diag')
            if not d or eid not in t:
                continue
            po, pp, base = predict(d, 0, mode, W)
            oo = t[eid]['revenue'].get('STRAWBERRY', 0) - null[eid]['revenue'].get('STRAWBERRY', 0)
            op = t[eid]['bench_revenue'].get('STRAWBERRY', 0) - null[eid]['bench_revenue'].get('STRAWBERRY', 0)
            actual_base = null[eid]['revenue'].get('STRAWBERRY', 0)
            rows.append((po, oo, pp, op, base, actual_base))
        err_o = [a - b for a, b, *_ in rows]
        err_p = [c - dd for _, _, c, dd, *_ in rows]
        lvl = [e - f for *_, e, f in rows]
        print(f'{mode:8s} W={W}: own strawberry delta pred {st.mean(r[0] for r in rows):+8,.0f} obs {st.mean(r[1] for r in rows):+8,.0f} '
              f'(mean abs err {st.mean(abs(x) for x in err_o):6,.0f}, corr {st.correlation([r[0] for r in rows], [r[1] for r in rows]):+.2f}); '
              f'opp pred {st.mean(r[2] for r in rows):+7,.0f} obs {st.mean(r[3] for r in rows):+7,.0f} (abs err {st.mean(abs(x) for x in err_p):5,.0f}); '
              f'base level err {st.mean(lvl):+7,.0f}')


if __name__ == '__main__':
    main()
