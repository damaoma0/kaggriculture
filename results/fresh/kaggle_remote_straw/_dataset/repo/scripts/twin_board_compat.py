"""Direction 3: can a library branch at each shop reveal? For every pair of UMG tapes whose shop sequences agree
on the first m-1 reveals and differ at reveal m, compare their day-start boards on day 3m (the morning reveal m is
visible) with the router's tile labels (weeds ignored). If her plan is shop-deterministic the two boards should be
compatible (Hamming <= 8), so a farm following one could switch onto the other at the reveal morning: a branching
library of late segments would then be executable. Also reports the same statistic 3 days later (day 3m+3)."""
import gzip, json, sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/newphase_20260923'


def shop_seq(sh):
    out, seen = [], 0
    for cur in sh:
        while len(cur) > seen:
            out.append(cur[seen]); seen += 1
    return out[:8]


def ham(a, b):
    n = 0
    for i in range(0, 200, 2):
        x, y = a[i:i + 2], b[i:i + 2]
        if x == ' w' or y == ' w':
            continue
        n += x != y
    return n


def main():
    tapes = []
    for p in sorted((ROOT / 'data/mg_tapes').rglob('*.json.gz')):
        g = json.load(gzip.open(p, 'rt', encoding='utf-8'))
        tapes.append((shop_seq(g['shops']), g['boards']))
    res = {}
    for m in range(2, 9):
        groups = defaultdict(list)
        for i, (s, b) in enumerate(tapes):
            groups[tuple(s[:m - 1])].append(i)
        h0, h3 = [], []
        for idx in groups.values():
            for i, j in combinations(idx, 2):
                if tapes[i][0][m - 1] == tapes[j][0][m - 1]:
                    continue                                   # agree on reveal m too: not a branch at m
                d = 3 * m
                h0.append(ham(tapes[i][1][d], tapes[j][1][d]))
                if d + 3 < len(tapes[i][1]):
                    h3.append(ham(tapes[i][1][d + 3], tapes[j][1][d + 3]))
        if not h0:
            continue
        a0, a3 = np.array(h0), np.array(h3)
        res[m] = dict(day=3 * m, pairs=len(h0), median_ham=float(np.median(a0)), frac_compatible=float((a0 <= 8).mean()),
                      median_ham_3d_later=float(np.median(a3)) if len(a3) else None,
                      frac_compatible_3d_later=float((a3 <= 8).mean()) if len(a3) else None)
        r = res[m]
        print(f"branch at reveal {m} (day {3*m:2d}): {r['pairs']:6d} pairs; board Hamming median {r['median_ham']:4.1f}, "
              f"compatible (<=8) {100*r['frac_compatible']:5.1f}%; 3 days later median {r['median_ham_3d_later']}, "
              f"compatible {100*(r['frac_compatible_3d_later'] or 0):5.1f}%")
    (OUT / 'twin_board_compat.json').write_text(json.dumps(res, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
