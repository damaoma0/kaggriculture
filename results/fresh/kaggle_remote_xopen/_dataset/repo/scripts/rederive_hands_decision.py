"""Re-evaluate the day-10 swap decision offline with owned hands (tomatoes at 7.5 units, hand wages) under
different discounts of the UNDRAWN shops' expected demand, and compare with the observed candidate-v2
outcome in each of her 30 worlds.

Inputs: the model inputs logged by the dry-run probe (mg3_probe3: base_ours, opp_by_day, shops, inv, prices,
batch_P, fe) and the calibrated market model (sales spread over 4 days). For each world and discount d in
{1.0, 0.5, 0.25, 0.0}: the margin-maximising number of tomato slots t (0..13) with hands costed as in the
layer, and the predicted margin gain. Observed: mg9_hands_econ margin vs mgs_null in that world.
"""
import glob, json, statistics as st, sys
from market_corpus import ROOT
from calibrate_straw_model import market, SHOPS, rate

FIB = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610]
W = 4


def daily_d(shops, product, day, discount):
    total = 1.0
    expected = sum(rate(s, product) for s in SHOPS) / 8.0 * discount
    for i in range(8):
        if 3 * (i + 1) > day:
            break
        total += rate(shops[i], product) if i < len(shops) else expected
    return total


def market_d(product, inv0, day0, shops, ours, opp, discount):
    import calibrate_straw_model as C
    orig = C.daily
    C.daily = lambda sh, pr, dy, known_only=None: daily_d(sh, pr, dy, discount)
    try:
        return market(product, inv0, day0, shops, ours, opp, 'spread', W)
    finally:
        C.daily = orig


def load(v):
    return {json.load(open(p))['episode']: json.load(open(p)) for p in glob.glob(str(ROOT / f'results/fresh/mg_slots/{v}-*.json'))}


def evaluate(d, discount, units_per_tomato=7.5, F=1.875):
    base = {int(k): v for k, v in d['base_ours'].items()}
    opp = {int(k): v for k, v in d['opp_by_day'].items()}
    shops, day0 = d['shops'], d['day0']
    P = sorted(d['batch_P'])
    n = len(P)
    fert_price = float(d['prices'].get('FERTILIZER') or 30)
    fe = d['fe']
    tom_shops = sum(s in ('PIZZA_SHOP', 'FARMERS_MARKET') for s in shops)
    v219 = {x: 20.0 for x in range(26, 30)} if tom_shops >= 2 else {}
    out = {}
    for k in range(n + 1):
        t = n - k
        so = dict(base)
        for p in P[:k]:
            for j in range(4):
                x = p + 10 + 2 * j
                if x <= 29:
                    so[x] = so.get(x, 0.0) + F
        rs_o, rs_p = market_d('STRAWBERRY', d['inv']['STRAWBERRY'], day0, shops, so, opp, discount)
        to = dict(v219)
        for p in P[k:]:
            for j in range(4):
                to[p + 8 + j] = to.get(p + 8 + j, 0.0) + units_per_tomato / 4.0
        if to or v219:
            rt_o, rt_p = market_d('TOMATO', d['inv']['TOMATO'], day0, shops, to, v219, discount)
        else:
            rt_o, rt_p = 0.0, 0.0
        cost = 50.0 * t - 100.0 * t
        fert = fert_price * sum(fe[k:])
        hands = 0.0
        if t:
            kh = min(3, max(1, -(-(3 * t + 2) // 20)))
            hands = 3.0 * sum(FIB[11 + j] for j in range(kh)) + 2.0 * t * (fert_price + 10.0)
        out[k] = (rs_o + rt_o + fert - cost - hands, rs_p + rt_p)
    return out, n


def main():
    probe, null, v2 = load('mg3_probe3'), load('mgs_null'), load('mg9_hands_econ')
    discounts = (1.0, 0.5, 0.25, 0.0)
    print('world             tomShops  obs v2 margin  decision(t tomatoes) & predicted gain by undrawn-demand discount ' + ' '.join(f'{x:>12}' for x in discounts))
    totals = {x: 0.0 for x in discounts}
    obs_by = {x: [] for x in discounts}
    for eid, r in sorted(probe.items()):
        d = r['telemetry'].get('econ_diag')
        if not d or eid not in v2 or eid not in null:
            continue
        obs = v2[eid]['margin'] - null[eid]['margin']
        swapped = (v2[eid]['telemetry'].get('econ_decision') or {}).get('tomatoes', 0) >= 10
        tom_shops = sum(s in ('PIZZA_SHOP', 'FARMERS_MARKET') for s in d['shops'])
        line = f'{eid}  {tom_shops:8d}  {obs:+13,.0f}  '
        for x in discounts:
            res, n = evaluate(d, x)
            base_o, base_p = res[n]
            best_k = max(res, key=lambda k: (res[k][0] - base_o) - (res[k][1] - base_p))
            gain = (res[best_k][0] - base_o) - (res[best_k][1] - base_p)
            t = n - best_k
            line += f'  t={t:2d} {gain:+7,.0f}'
            # attribute observed outcome: if this discount would swap (t>=10) count the observed margin when v2 swapped
            if t >= 10 and swapped:
                totals[x] += obs
                obs_by[x].append(obs)
            elif t >= 10 and not swapped:
                obs_by[x].append(float('nan'))
        print(line)
    for x in discounts:
        v = [o for o in obs_by[x] if o == o]
        unk = sum(1 for o in obs_by[x] if o != o)
        print(f'discount {x}: would swap in {len(obs_by[x])} worlds; observed v2 margin where v2 also swapped: n={len(v)} sum {sum(v):+,.0f} mean {st.mean(v) if v else 0:+,.0f}; unobserved swaps {unk}')


if __name__ == '__main__':
    main()
