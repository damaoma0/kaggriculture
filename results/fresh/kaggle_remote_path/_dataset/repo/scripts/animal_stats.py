"""Paired statistics of arms vs a base arm over panel13 (season runs, final money): mean / SE / median of the own-cash and
margin deltas, worlds better, and the own / margin gap to the leader and wins. usage: animal_stats.py ARM,... [--base K5b]"""
import json
import statistics as stt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from run_arms import PANEL13  # noqa: E402

M = ROOT / 'results/fresh/sector_20260925/multi'
args = sys.argv[1:]
base = 'K5b'
if '--base' in args:
    base = args[args.index('--base') + 1]
eps = [g.split(':')[1] for g in PANEL13]


def fin(arm, ep):
    f = M / arm / f'{ep}.json'
    return json.loads(f.read_text())['money']['30'] if f.exists() else None


print('%-10s %5s %17s %17s %8s %8s %8s %8s %5s' % ('arm', 'n', 'own d (se) [+]', 'margin d (se) [+]', 'med own', 'med mar',
                                                   'own gap', 'mar gap', 'wins'))
for arm in args[0].split(','):
    do, dm, og, mg, w = [], [], [], [], 0
    for ep in eps:
        L, R, B = fin('LEADER', ep), fin(arm, ep), fin(base, ep)
        if not (L and R and B):
            continue
        do.append(R[0] - B[0])
        dm.append((R[0] - R[1]) - (B[0] - B[1]))
        og.append(R[0] - L[0])
        mg.append((R[0] - R[1]) - (L[0] - L[1]))
        w += R[0] > R[1]
    n = len(do)
    if not n:
        print(arm, 'no data')
        continue
    se = lambda x: stt.stdev(x) / n ** 0.5 if n > 1 else 0.0
    print('%-10s %5d %+7.0f (%4.0f) [%2d] %+7.0f (%4.0f) [%2d] %+8.0f %+8.0f %+8.0f %+8.0f %2d/%d' % (
        arm, n, stt.mean(do), se(do), sum(x > 0 for x in do), stt.mean(dm), se(dm), sum(x > 0 for x in dm),
        stt.median(do), stt.median(dm), stt.mean(og), stt.mean(mg), w, n))
