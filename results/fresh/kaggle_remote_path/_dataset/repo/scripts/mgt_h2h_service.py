"""Animal servicing of both sides in the head-to-head worlds, by demand group (from mgt_loo.py trace['service']).

Usage: python mgt_h2h_service.py <agent> [offset=80] [n=128]
"""
import gzip
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOO = ROOT / 'results/fresh/mg_tape/loo'
BUYERS = {'SHEEP': {'YARN_STORE': 12}, 'COW': {'PIZZA_SHOP': 6, 'ICE_CREAM_SHOP': 6, 'SMOOTHIE_SHOP': 6}}
OPEN = [3, 6, 9, 12, 15, 18, 21, 24]


def capacity(shops, sp, day):
    return sum(BUYERS[sp].get(s, 0) for i, s in enumerate(shops) if OPEN[i] <= day)


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
    for sp in ('SHEEP', 'COW'):
        acc = defaultdict(lambda: [0] * 8)        # group -> her n, fed, cared, ours A n, fed, cared; count of world-days
        tele = defaultdict(lambda: defaultdict(float))
        for ep in eps:
            f = LOO / f'mgtape_vs_{agent}-mg_vs-{ep}.json'
            if not f.exists():
                continue
            a = json.loads(f.read_text(encoding='utf-8'))
            if not a.get('trace', {}).get('service'):
                continue
            W, N = shops_of[ep], shops_of[str(a['rival_history'][-1][1])]
            for day in range(15, 29):
                cw, cn = capacity(W, sp, day), capacity(N, sp, day)
                g = 'world has MORE open demand than tape world' if cw > cn else 'world has LESS' if cw < cn else ('same, none' if cw == 0 else 'same, some')
                her, ours = a['trace']['service'][0][day].get(sp), a['trace']['service'][1][day].get(sp)
                v = acc[g]
                if her:
                    v[0] += her[0]; v[1] += her[1]; v[2] += her[2]
                if ours:
                    v[3] += ours[0]; v[4] += ours[1]; v[5] += ours[2]
                v[6] += 1
            g2 = 'ALL'
            for k, x in (a.get('rival_sheep') or {}).items():
                if isinstance(x, (int, float)):
                    tele[g2][k] += x
            tele[g2]['_n'] += 1
        print(f'\n{sp}, days 15-28, arm A (we play a neighbour tape): animals per day and fed / cared share at hour 23')
        print(f'  {"group (by demand OPEN that day)":<46} {"world-days":>10} | {"her herd":>8} {"fed":>5} {"cared":>6} | {"our herd":>8} {"fed":>5} {"cared":>6}')
        for g, v in sorted(acc.items()):
            print(f'  {g:<46} {v[6]:>10} | {v[0] / v[6]:>8.1f} {v[1] / max(1, v[0]):>5.0%} {v[2] / max(1, v[0]):>6.0%} | {v[3] / v[6]:>8.1f} {v[4] / max(1, v[3]):>5.0%} {v[5] / max(1, v[3]):>6.0%}')
    t = tele['ALL']
    k = max(1, t.pop('_n', 1))
    print('\noverlay telemetry per game (arm A): ' + ', '.join(f'{kk} {vv / k:.1f}' for kk, vv in sorted(t.items()) if vv))


if __name__ == '__main__':
    main()
