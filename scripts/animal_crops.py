"""Per-world means from animal_diag JSONs over panel13: plant units harvested by crop (days 11-29) and the stock left in
the shed / hands at the end (unsold = lost), per arm (leader first). usage: animal_crops.py k5b,ka1,..."""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from run_arms import PANEL13  # noqa: E402

DIAG = ROOT / 'results/fresh/threads_20260928/animal/diag'
C = ['WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON']
S = ['WHEAT', 'EGG', 'MILK', 'WOOL', 'STRAWBERRY', 'FERTILIZER']
rows = {}
for arm in sys.argv[1].split(','):
    for who in (['leader'] if 'leader' not in rows else []) + [arm]:
        acc, n = defaultdict(float), 0
        for g in PANEL13:
            f = DIAG / f"{g.split(':')[1]}_{arm}.json"
            if not f.exists():
                continue
            r = json.loads(f.read_text())[who]
            if 'pharv' not in r:
                continue
            n += 1
            for k, v in r['pharv'].items():
                acc['h_' + k] += v
            for k, v in r['stock_end'].items():
                acc['s_' + k] += v
        rows[who] = ({k: v / max(1, n) for k, v in acc.items()}, n)
print('%-9s' % '', ' '.join('%9s' % ('h ' + c[:7]) for c in C), '|', ' '.join('%9s' % ('end ' + c[:5]) for c in S))
for who, (v, n) in rows.items():
    print('%-9s' % who[:9], ' '.join('%9.1f' % v.get('h_' + c, 0) for c in C), '|', ' '.join('%9.1f' % v.get('s_' + c, 0) for c in S), f'n={n}')
