"""Abandonment research (2026-09-26): our arm with DSM's herd cuts. In each world, for every animal DSM abandoned
mid-season (animals.json LEADER 'mid', escape >= 12) on stop day s, one of OUR animals of the same kind alive at dawn
of s is dropped at s (the one with the most units still to make; ties: first key). Its units made on nights >= s are
not produced (our sales of the product removed FIFO after each production, as abandon_drop.py), its feed wheat on
days >= s is saved, its fertilizer collections on days >= s+2 are lost. Exact repricing of both players.
usage: abandon_dsmcut.py <arm,...> <panel>"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import abandon_market as AM  # noqa: E402

PI = AM.PI

if __name__ == '__main__':
    arms = sys.argv[1].split(',')
    games = Path(sys.argv[2]).read_text().replace(',', ' ').split()
    rows = json.loads((AM.OUT / 'animals.json').read_text(encoding='utf-8'))
    cuts = defaultdict(list)
    for r in rows:
        if r['side'] == 'LEADER' and r['who'] == 0 and r['cls'] == 'mid' and r['escape'] >= 12:
            cuts[r['ep']].append((r['stop'], r['kind']))
    for arm in arms:
        tot = defaultdict(float)
        per = []
        for g in games:
            ep = g.split(':')[1]
            R = json.loads((AM.RDIR / arm / f'{ep}.json').read_text(encoding='utf-8'))
            dropped = set()
            rem = defaultdict(list)
            used = defaultdict(set)
            wheat = fert = 0.0
            n = 0
            for s, kind in sorted(cuts[ep]):
                item = AM.PROD[kind]
                cand = []
                for k, a in R['animals'].items():
                    w, x, y, pd, kd = k.split(',')
                    if w != '0' or kd != kind or k in dropped or s not in {dw[0] for dw in a['dawn']}:
                        continue
                    made = [(nn[0], nn[6]) for nn in a['nights'] if nn[0] >= s and nn[6] > 0]
                    if made:
                        cand.append((-sum(u for _, u in made), k, made, a))
                if not cand:
                    continue
                _, k, made, a = sorted(cand)[0]
                dropped.add(k)
                n += 1
                ours = [u for u in AM.sells(R, item) if u[1] == 0]
                for nn, u in made:
                    c = [x for x in ours if x[0] >= (nn + 1) * 24 and x[4] not in used[item]][:u]
                    for x in c:
                        used[item].add(x[4])
                        rem[item].append(x[4])
                wheat += sum(AM.price('WHEAT', R['inv'][nn[0] * 24][PI['WHEAT']]) for nn in a['nights'] if nn[0] >= s and nn[1])
                fert += sum(AM.price('FERTILIZER', R['inv'][min(718, (st // 24) * 24)][PI['FERTILIZER']])
                            for st, c, u in a['acts'] if c == 'COLLECT_FERTILIZER' and st // 24 >= s + 2)
            do = dr = 0.0
            for item, rr in rem.items():
                o, v = AM.reprice(R, item, removes=rr)
                do += o
                dr += v
            own = do + wheat - fert
            per.append((ep, n, round(own), round(own - dr)))
            tot['n'] += n
            tot['own'] += own
            tot['rival'] += dr
            tot['margin'] += own - dr
        N = len(games)
        print(f"{arm:5s} DSM-style cuts: {tot['n'] / N:.2f} animals/world | own {tot['own'] / N:+.0f} rival {tot['rival'] / N:+.0f} margin {tot['margin'] / N:+.0f} per world"
              f" | worlds margin>0: {sum(1 for p in per if p[3] > 0)}, <0: {sum(1 for p in per if p[3] < 0)}")
        worst = sorted(per, key=lambda p: p[3])
        print('   worst', worst[:3], 'best', worst[-3:])
