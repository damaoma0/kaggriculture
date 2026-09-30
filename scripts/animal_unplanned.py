"""Tier-plan summaries of season runs (results/fresh/sector_20260925/multi/<ARM>/<ep>.json, tier_days): per arm, the
ops planned and left unplanned by type (with their summed values), the mandatory stops and route ends, over panel13.
usage: animal_unplanned.py ARM,ARM,..."""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from run_arms import PANEL13  # noqa: E402

M = ROOT / 'results/fresh/sector_20260925/multi'
for arm in sys.argv[1].split(','):
    c = Counter()
    n = 0
    for g in PANEL13:
        f = M / arm / f"{g.split(':')[1]}.json"
        if not f.exists():
            continue
        n += 1
        for d, s in json.loads(f.read_text())['tier_days'].items():
            c['mand_stops'] += s.get('n_mand_stops', 0)
            for tile, ops, v in s['unplanned']:
                for o in ops:
                    c['un_' + o] += 1
                    c['unv_' + o] += v / len(ops)
            for u in s['units']:
                for x in u['stops']:
                    for o in x[1]:
                        c['pl_' + o] += 1
    print(arm, n, 'worlds; per world:', ' '.join('%s=%.0f' % (k, v / max(1, n)) for k, v in sorted(c.items())
                                                if k.startswith(('un_', 'pl_', 'mand'))))
    print('   unplanned value per world:', ' '.join('%s=%.0f' % (k[4:], v / max(1, n)) for k, v in sorted(c.items()) if k.startswith('unv_')))
