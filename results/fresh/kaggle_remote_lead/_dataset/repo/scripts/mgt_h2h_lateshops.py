"""Is the late-game price loss of the ladder case explained by shops that opened after the tape was chosen?

Per world (arm A = her tape excluded, arm B = restricted to her tape; results of mgt_loo.py mg_vs / mg_vs_only):
the tape our router ended on (N), the demand of N's world against this world's (W) for each product, split into shops
1-4 (open by day 12) and shops 5-8 (days 15-24), and our late (days 18-29) units / revenue / realised price in A and B.

Usage: python mgt_h2h_lateshops.py <agent> [offset=80] [n=128]
"""
import gzip
import json
import random
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOO = ROOT / 'results/fresh/mg_tape/loo'
DEMAND = {'BAKERY': {'EGG': 1, 'WHEAT': 1}, 'PIZZA_SHOP': {'MILK': 1, 'TOMATO': 1, 'WHEAT': 1},
          'BRUNCH_SPOT': {'EGG': 1, 'WHEAT': 1, 'STRAWBERRY': 1}, 'YARN_STORE': {'WOOL': 2},
          'ICE_CREAM_SHOP': {'STRAWBERRY': 1, 'MILK': 1, 'WHEAT': 1}, 'PET_CAFE': {'CARROT': 2},
          'SMOOTHIE_SHOP': {'STRAWBERRY': 1, 'MILK': 1}, 'FARMERS_MARKET': {'WHEAT': 1, 'CARROT': 1, 'TOMATO': 1, 'STRAWBERRY': 1}}


def dem(shops, item, lo, hi):
    return sum(DEMAND.get(s, {}).get(item, 0) for s in shops[lo:hi])


def late(cum, item, d0=18):
    a = cum[min(d0, len(cum) - 1) - 1].get(item, 0) if d0 > 0 else 0
    return cum[-1].get(item, 0) - a


def main():
    agent = sys.argv[1]
    off = int(sys.argv[2]) if len(sys.argv) > 2 else 80
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 128
    files = sorted(p for s in ('56266758', '56266899') for p in (ROOT / 'data/mg_tapes' / s).glob('*.json.gz'))
    shops_of = {}
    for p in files:
        t = json.load(gzip.open(p, 'rt', encoding='utf-8'))
        shops_of[str(t['episode'])] = t['shops'][30]
    random.Random(20260920).shuffle(files)
    eps = [p.name.split('.')[0] for p in files[off:off + n]]
    rows = []
    for ep in eps:
        a = json.loads((LOO / f'mgtape_vs_{agent}-mg_vs-{ep}.json').read_text(encoding='utf-8'))
        b = json.loads((LOO / f'mgtape_vs_{agent}-mg_vs_only-{ep}.json').read_text(encoding='utf-8'))
        hist = a.get('rival_history') or []
        if not hist:
            continue
        final = str(hist[-1][1])
        last_switch = max([h[0] for i, h in enumerate(hist) if i == 0 or h[1] != hist[i - 1][1]], default=0)
        rows.append(dict(ep=ep, W=shops_of[ep], N=shops_of[final], last_switch=last_switch, a=a, b=b,
                         loss=(-a['margin']) - (-b['margin'])))
    print(f'{len(rows)} worlds. Day of the router\'s last switch: median {st.median(r["last_switch"] for r in rows)}, '
          f'after day 12 in {sum(1 for r in rows if r["last_switch"] > 12)} worlds, after day 18 in {sum(1 for r in rows if r["last_switch"] > 18)}')
    same_all = sum(1 for r in rows if sorted(r['W']) == sorted(r['N']))
    print(f'final tape has the same 8 shops (any order) as the world in {same_all} worlds; same first four in '
          f'{sum(1 for r in rows if sorted(r["W"][:4]) == sorted(r["N"][:4]))}; same last four in {sum(1 for r in rows if sorted(r["W"][4:]) == sorted(r["N"][4:]))}')
    for item in ('WOOL', 'MILK', 'STRAWBERRY', 'TOMATO'):
        print(f'\n{item}: late (days 18-29) result by how the final tape\'s world differs from this world in {item} demand')
        print(f'  {"group":<44} {"n":>4} {"routing loss":>13} | {"our units B":>11} {"A":>7} | {"our price B":>11} {"A":>7} | {"our late rev A-B":>16} | {"her price B":>11} {"A":>7}')
        groups = defaultdict(list)
        for r in rows:
            e = dem(r['N'], item, 0, 4) - dem(r['W'], item, 0, 4)
            l = dem(r['N'], item, 4, 8) - dem(r['W'], item, 4, 8)
            key = ('early shops differ' if e else 'early same') + ', ' + ('late: tape world has MORE' if l > 0 else 'late: tape world has FEWER' if l < 0 else 'late same')
            groups[key].append(r)
            groups['ALL'].append(r)
        for key in sorted(groups, key=lambda k: (k != 'ALL', k)):
            G = groups[key]
            k = len(G)
            ub = sum(late(r['b']['rival_units_daily'], item) for r in G) / k
            ua = sum(late(r['a']['rival_units_daily'], item) for r in G) / k
            rb = sum(late(r['b']['rival_revenue_daily'], item) for r in G) / k
            ra = sum(late(r['a']['rival_revenue_daily'], item) for r in G) / k
            hb_u = sum(late(r['b']['units_daily'], item) for r in G) / k
            hb_r = sum(late(r['b']['revenue_daily'], item) for r in G) / k
            ha_u = sum(late(r['a']['units_daily'], item) for r in G) / k
            ha_r = sum(late(r['a']['revenue_daily'], item) for r in G) / k
            print(f'  {key:<44} {k:>4} {sum(r["loss"] for r in G) / k:>+13,.0f} | {ub:>11.1f} {ua:>7.1f} | {rb / max(1e-9, ub):>11.1f} {ra / max(1e-9, ua):>7.1f} | '
                  f'{ra - rb:>+16,.0f} | {hb_r / max(1e-9, hb_u):>11.1f} {ha_r / max(1e-9, ha_u):>7.1f}')


if __name__ == '__main__':
    main()
