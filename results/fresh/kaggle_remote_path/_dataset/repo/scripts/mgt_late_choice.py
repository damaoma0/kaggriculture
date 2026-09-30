"""What is there to choose from LATE? (offline, no games)

For each of the 128 head-to-head worlds and each day D in 12, 15, 18, 21, 24: the tape our router is on (from the
recorded history of the ladder-case games), the library tapes whose recorded board on day D is within the router's
compatibility limit of it (Hamming <= 8; the world's own tape excluded), and how well the best of them fits the
world's FULL shop list in hindsight - against the same hindsight choice with no compatibility limit (= what the
library could offer at all) and against the tape we actually ended on.

Distance = the router's own demand distance over all 8 shops (weights STRAWBERRY 3, TOMATO 2, WOOL 2, CARROT 1.5,
MILK 1.5, EGG 1, WHEAT .5; checkpoints at 2, 4, 5, 6, 8 shops). 0 = identical demand at every checkpoint.
usage: mgt_late_choice.py [agent=mgt_m1]
"""
import gzip
import json
import random
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOO = ROOT / 'results/fresh/mg_tape/loo'
DEMAND = {'BAKERY': {'EGG': 1, 'WHEAT': 1}, 'PIZZA_SHOP': {'MILK': 1, 'TOMATO': 1, 'WHEAT': 1},
          'BRUNCH_SPOT': {'EGG': 1, 'WHEAT': 1, 'STRAWBERRY': 1}, 'YARN_STORE': {'WOOL': 2},
          'ICE_CREAM_SHOP': {'STRAWBERRY': 1, 'MILK': 1, 'WHEAT': 1}, 'PET_CAFE': {'CARROT': 2},
          'SMOOTHIE_SHOP': {'STRAWBERRY': 1, 'MILK': 1}, 'FARMERS_MARKET': {'WHEAT': 1, 'CARROT': 1, 'TOMATO': 1, 'STRAWBERRY': 1}}
PRODUCTS = ('STRAWBERRY', 'TOMATO', 'WOOL', 'CARROT', 'MILK', 'EGG', 'WHEAT')
W = (3.0, 2.0, 2.0, 1.5, 1.5, 1.0, 0.5)
CHECK = (2, 4, 5, 6, 8)


def vec(shops, j):
    c = [0] * len(PRODUCTS)
    for s in shops[:j]:
        for p, n in DEMAND.get(s, {}).items():
            c[PRODUCTS.index(p)] += n
    return c


def dist(a, b, k=8):
    d = 0.0
    for j in CHECK:
        jj = min(j, k)
        d += sum(w * abs(x - y) for w, x, y in zip(W, vec(a, jj), vec(b, jj)))
        if j >= k:
            break
    return d


def labels(board):
    s = ''.join(board)
    return [' .' if s[i:i + 2] == ' w' else s[i:i + 2] for i in range(0, len(s), 2)]


def main():
    agent = sys.argv[1] if len(sys.argv) > 1 else 'mgt_m1'
    files = sorted(p for s in ('56266758', '56266899') for p in (ROOT / 'data/mg_tapes' / s).glob('*.json.gz'))
    tapes = {}
    for p in files:
        t = json.load(gzip.open(p, 'rt', encoding='utf-8'))
        tapes[str(t['episode'])] = dict(shops=t['shops'][30], lab=[labels(b) for b in t['boards']])
    random.Random(20260920).shuffle(files)
    eps = [p.name.split('.')[0] for p in files[80:208]]
    print(f'{len(tapes)} tapes; {len(eps)} worlds; router history of {agent} in the ladder case')
    print(f'{"day":>4} {"shops known":>11} | {"compatible tapes: median / share of worlds with <= 1, <= 3":>58} | '
          f'{"full-shop distance: tape we are on":>36} {"best compatible (hindsight)":>28} {"best in library (hindsight)":>28} | {"worlds where a compatible tape is closer by >= 3":>48}')
    for day in (6, 9, 12, 15, 18, 21, 24):
        n_comp, d_cur, d_comp, d_all, better = [], [], [], [], 0
        for ep in eps:
            r = json.loads((LOO / f'mgtape_vs_{agent}-mg_vs-{ep}.json').read_text(encoding='utf-8'))
            hist = r.get('rival_history') or []
            cur = next((str(h[1]) for h in reversed(hist) if h[0] <= day), None)
            if cur is None:
                continue
            world = tapes[ep]['shops']
            board = tapes[cur]['lab'][day]
            comp = [e for e, t in tapes.items() if e != ep and sum(1 for x, y in zip(board, t['lab'][day]) if x != y) <= 8]
            n_comp.append(len(comp))
            dc = dist(world, tapes[cur]['shops'])
            db = min(dist(world, tapes[e]['shops']) for e in comp) if comp else dc
            da = min(dist(world, t['shops']) for e, t in tapes.items() if e != ep)
            d_cur.append(dc)
            d_comp.append(db)
            d_all.append(da)
            better += db <= dc - 3
        k = len(n_comp)
        print(f'{day:>4} {min(8, day // 3):>11} | {st.median(n_comp):>20.0f} / {sum(1 for x in n_comp if x <= 1) / k:>6.0%} / {sum(1 for x in n_comp if x <= 3) / k:>6.0%}{"":>18} | '
              f'{st.mean(d_cur):>36.1f} {st.mean(d_comp):>28.1f} {st.mean(d_all):>28.1f} | {better / k:>48.0%}')


if __name__ == '__main__':
    main()
