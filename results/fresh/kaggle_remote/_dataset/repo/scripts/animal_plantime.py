"""Hour-0 plan time and executor breakages per arm over panel13 (tier_days summaries): mean / max plan ms per day, skipped
FEED / CARE / COLLECT / other ops, waits, errors. usage: animal_plantime.py ARM,..."""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from run_arms import PANEL13  # noqa: E402

M = ROOT / 'results/fresh/sector_20260925/multi'
for arm in sys.argv[1].split(','):
    pm, c, n, err, days = [], Counter(), 0, 0, 0
    for g in PANEL13:
        f = M / arm / f"{g.split(':')[1]}.json"
        if not f.exists():
            continue
        m = json.loads(f.read_text())
        n += 1
        err += int((m.get('tier_err') or {}).get('errors') or 0)
        for d, s in m['tier_days'].items():
            days += 1
            pm.append(float(s.get('plan_ms', 0)))
            c.update(s.get('cnt') or {})
    print('%-10s worlds %2d days %3d plan ms mean %6.1f max %7.1f | per world: %s | errors %d' % (
        arm, n, days, sum(pm) / max(1, len(pm)), max(pm or [0]),
        ' '.join('%s=%.1f' % (k, v / max(1, n)) for k, v in sorted(c.items()) if k.startswith(('skip', 'wait', 'pick', 'unit'))), err))
