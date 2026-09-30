"""sd_tier_pdrop telemetry over the 40-world panel for an arm: drops a world in the day's final planning pass and in any
pass, units by product, reject reasons (summed over passes).
usage: pdrop_stats.py <ARM>"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
arm = sys.argv[1]
games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
F, A, U, W = Counter(), Counter(), Counter(), Counter()
for g in games:
    ep = g.split(':')[1].strip()
    d = json.loads((ROOT / 'results/fresh/sector_20260925/multi' / arm / f'{ep}.json').read_text())
    for v in d['tier_days'].values():
        pd = (v or {}).get('pdrop') or []
        if isinstance(pd, dict):
            pd = [pd]
        if not pd:
            continue
        F['drops'] += pd[-1].get('drops', 0)
        for k, x in (pd[-1].get('units') or {}).items():
            U[k] += x
        A['drops'] += sum(c.get('drops', 0) for c in pd)
        for c in pd:
            for k, x in (c.get('why') or {}).items():
                W[k] += x
n = len(games)
print(f'{arm}: drops a world, final pass {F["drops"] / n:.1f} (units ' + ', '.join(f'{k} {v / n:.1f}' for k, v in U.items())
      + f'), any pass {A["drops"] / n:.1f} | reasons (all passes, a world): ' + ', '.join(f'{k} {v / n:.0f}' for k, v in W.most_common()))
