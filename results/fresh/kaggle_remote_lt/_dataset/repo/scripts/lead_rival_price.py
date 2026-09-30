"""Rival revenue per unit we sell, from PAIRED panel runs already on disk (no games).

usage: lead_rival_price.py
Every build in the same world meets the same frozen recorded rival, so within-world differences between builds in the
rival's revenue come from the market (prices / fills), not from its decisions. Per product: slope of the rival's
revenue on our units sold, within world (demeaned by world), bootstrap CI over worlds.
Part 1: the 185-world p2750 builds (whole season; builds whose rival tape breaks, i.e. its commands without effect
exceed the world's best build by more than 40, are excluded). Part 2: the 12 smoke-world traces (per season third,
same third). Part 3: the engine price formula's marginal price at the rival's realised price level, for comparison.
"""
import json
import math
import random
import statistics as st
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / 'results/fresh/ladder_panel'
T = ROOT / 'results/fresh/lead_world_trace'
PRODS = ('WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON', 'EGG', 'MILK', 'WOOL', 'FERTILIZER')
# engine price model above the reference inventory (oversupply side): (base, T, shape, target)
ABOVE = {'WHEAT': (25, 400, 'log', .20), 'CARROT': (35, 450, 'sqrt', .70), 'TOMATO': (60, 200, 'sqrt', .60),
         'STRAWBERRY': (120, 100, 'linear', 1.60), 'MELON': (250, 300, 'sq', 3.60), 'EGG': (50, 332, 'log', .20),
         'MILK': (160, 122, 'linear', 1.60), 'WOOL': (200, 105, 'sq', 3.20), 'FERTILIZER': (100, 200, 'linear', .40)}
BUILDS_185 = ['mgt_lpv_tw0', 'mgt_lpv_tievalff', 'mgt_lpv_rs1', 'mgt_lpv_rpc1', 'mgt_lpv_rp1', 'mgt_lpv_pv30',
              'mgt_lpv_me3', 'mgt_lpv_hs1', 'mgt_lpv_ff1', 'mgt_lpv_cut', 'mgt_lpv_c27', 'mgt_y3_cal']


def f(shape, u):
    return {'log': math.log1p(u), 'sqrt': math.sqrt(u), 'linear': u, 'sq': u * u}[shape]


def df(shape, u):
    return {'log': 1 / (1 + u), 'sqrt': 0.5 / math.sqrt(max(u, 1e-6)), 'linear': 1.0, 'sq': 2 * u}[shape]


def marginal(p, price):
    """d price / d inventory at the oversupply level that gives this price (engine formula, per unit)."""
    base, t, shape, tg = ABOVE[p]
    if price >= base:
        return 0.0
    amp = tg * base / f(shape, 1.0)                  # f is applied to x / T (units of T)
    # price = base - amp * f(x / T): solve for u = x / T by bisection
    lo, hi = 0.0, 50.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if base - amp * f(shape, mid) > price:
            lo = mid
        else:
            hi = mid
    return amp * df(shape, lo) / t


def slope(rows_by_world, reps=1000):
    """within-world OLS slope of y on x; rows_by_world: {world: [(x, y), ...]}; bootstrap over worlds."""
    def est(worlds):
        sxy = sxx = 0.0
        for w in worlds:
            r = rows_by_world[w]
            if len(r) < 2:
                continue
            mx = st.mean(x for x, y in r)
            my = st.mean(y for x, y in r)
            sxy += sum((x - mx) * (y - my) for x, y in r)
            sxx += sum((x - mx) ** 2 for x, y in r)
        return sxy / sxx if sxx > 0 else float('nan'), sxx
    ws = list(rows_by_world)
    b, sxx = est(ws)
    rng = random.Random(7)
    bs = sorted(est([rng.choice(ws) for _ in ws])[0] for _ in range(reps))
    bs = [x for x in bs if x == x]
    return b, (bs[int(.025 * len(bs))], bs[int(.975 * len(bs))]) if bs else (float('nan'), float('nan')), sxx


def part1():
    data = defaultdict(dict)
    for b in BUILDS_185:
        for fpath in (P / b).glob('*.json'):
            r = json.load(open(fpath))
            data[fpath.stem][b] = r
    rows = {p: defaultdict(list) for p in PRODS}
    kept = dropped = 0
    for w, builds in data.items():
        if len(builds) < 3:
            continue
        m = min(r.get('opp_dead', 0) for r in builds.values())
        for b, r in builds.items():
            if r.get('opp_dead', 0) > m + 40:
                dropped += 1
                continue
            kept += 1
            for p in PRODS:
                rows[p][w].append((r['sold'].get(p, 0), r['rival_revenue'].get(p, 0)))
    print(f'Part 1: 185-world builds, {len(data)} worlds, {kept} world-builds kept, {dropped} dropped (rival tape broken)')
    out = {}
    for p in PRODS:
        b, ci, sxx = slope(rows[p])
        out[p] = (b, ci)
        print(f'  {p:11s} rival revenue per extra unit we sell: {b:+7.2f} (95% CI {ci[0]:+.2f} .. {ci[1]:+.2f}); within-world spread of our units (sd) {math.sqrt(sxx / max(1, kept)):.1f}')
    return out


def part2():
    runs = defaultdict(dict)
    for fpath in T.glob('*.json'):
        r = json.load(open(fpath))
        runs[str(r['episode'])][r['agent']] = r
    thirds = [(0, 9), (10, 19), (20, 29)]
    print(f'Part 2: smoke-world traces, {len(runs)} worlds, {sum(len(v) for v in runs.values())} world-builds; per season third')
    res = {}
    for p in PRODS:
        line = []
        for a, b in thirds:
            rows = defaultdict(list)
            for w, builds in runs.items():
                for ag, r in builds.items():
                    u = sum(d['sold'].get(p, 0) for d in r['days'][a:b + 1])
                    rv = sum(d['rrev'].get(p, 0) for d in r['days'][a:b + 1])
                    rows[w].append((u, rv))
            s, ci, sxx = slope(rows, reps=500)
            res[(p, a)] = (s, ci)
            line.append(f'{s:+7.2f} ({ci[0]:+.1f}..{ci[1]:+.1f})')
        print(f'  {p:11s} days 0-9 / 10-19 / 20-29: ' + ' | '.join(line))
    return res, runs


def part3(runs):
    print('Part 3: engine formula: marginal price per unit of oversupply at the rival\'s realised price, x rival units sold '
          'per third / 2 (a unit sold at a random moment of the third affects half of the rival\'s later units, no decay)')
    for p in PRODS:
        vals = []
        for a, b in ((0, 9), (10, 19), (20, 29)):
            u = rv = 0
            for w, builds in runs.items():
                for ag, r in builds.items():
                    u += sum(d['rsold'].get(p, 0) for d in r['days'][a:b + 1])
                    rv += sum(d['rrev'].get(p, 0) for d in r['days'][a:b + 1])
            nb = sum(len(v) for v in runs.values())
            if u:
                price = rv / u
                mp = marginal(p, price)
                vals.append(f'price {price:6.1f} dP/dx {mp:5.2f} -> {-mp * (u / nb) / 2:+7.1f}')
            else:
                vals.append('-')
        print(f'  {p:11s} ' + ' | '.join(vals))


def main():
    part1()
    res, runs = part2()
    part3(runs)


if __name__ == '__main__':
    main()
