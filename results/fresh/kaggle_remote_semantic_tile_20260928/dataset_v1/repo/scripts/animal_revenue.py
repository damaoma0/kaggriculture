"""Per-world mean market ledger (days 11-29) from animal_diag JSONs over panel13: our SELL revenue by product, BUY_PRODUCT
(wheat / fertilizer) and BUY_ANIMAL spend, and the rival's SELL revenue, per arm (the leader's own game first).
usage: animal_revenue.py k5b,ka1,..."""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from run_arms import PANEL13  # noqa: E402

DIAG = ROOT / 'results/fresh/threads_20260928/animal/diag'
P = ['WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON', 'EGG', 'MILK', 'WOOL', 'FERTILIZER']
arms = sys.argv[1].split(',')
rows = {}
for arm in arms:
    for who in (['leader'] if 'leader' not in rows else []) + [arm]:
        acc, n = defaultdict(float), 0
        for g in PANEL13:
            f = DIAG / f"{g.split(':')[1]}_{arm}.json"
            if not f.exists():
                continue
            r = json.loads(f.read_text())[who]
            n += 1
            for k, (cnt, val) in r['mkt'].items():
                side, op, item = k.split('|')
                acc[(side, op, item, 'n')] += cnt
                acc[(side, op, item, 'v')] += val
            acc['final_us'] += r['final'][0]
            acc['final_opp'] += r['final'][1]
        rows[who] = {k: v / max(1, n) for k, v in acc.items()}
print('%-9s' % 'rev/world', ' '.join('%9s' % p[:9] for p in P), '  buyWheat  buyFert  buyAnim |  opp rev |    own   margin')
for who, v in rows.items():
    sells = [v.get(('us', 'SELL', p, 'v'), 0) for p in P]
    bw = v.get(('us', 'BUY_PRODUCT', 'WHEAT', 'v'), 0)
    bf = v.get(('us', 'BUY_PRODUCT', 'FERTILIZER', 'v'), 0)
    ba = sum(x for k, x in v.items() if isinstance(k, tuple) and k[0] == 'us' and k[1] == 'BUY_ANIMAL' and k[3] == 'v')
    orv = sum(x for k, x in v.items() if isinstance(k, tuple) and k[0] == 'opp' and k[1] == 'SELL' and k[3] == 'v')
    print('%-9s' % who[:9], ' '.join('%9.0f' % s for s in sells), ' %8.0f %8.0f %8.0f | %8.0f | %7.0f %8.0f' % (
        bw, bf, ba, orv, v['final_us'], v['final_us'] - v['final_opp']))
print('units sold / world')
for who, v in rows.items():
    print('%-9s' % who[:9], ' '.join('%9.1f' % v.get(('us', 'SELL', p, 'n'), 0) for p in P),
          ' wheat bought %.1f' % v.get(('us', 'BUY_PRODUCT', 'WHEAT', 'n'), 0))
