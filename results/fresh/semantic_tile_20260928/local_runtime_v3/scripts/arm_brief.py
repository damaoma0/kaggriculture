"""One-line health and margin summary of arms on one world: own / rival / margin, deaths, unfinished waterings, skipped
feeds, deliveries, bank stops, and (optional) midnight deletions from the multi json.
usage: arm_brief.py <ep> ARM[,ARM...]"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = ROOT / 'results/fresh/sector_20260925/multi'
ep, arms = sys.argv[1], sys.argv[2].split(',')
for a in arms:
    f = M / a / f'{ep}.json'
    if not f.exists():
        print(f'{a:10s} missing')
        continue
    d = json.loads(f.read_text())
    m = d['money'].get('30') or [0, 0]
    died = {}
    for dd in d['died'].values():
        for k, v in dd.items():
            died[k] = died.get(k, 0) + v
    td = d.get('tier_days') or {}
    cnt = lambda k: sum(((v or {}).get('cnt') or {}).get(k, 0) for v in td.values() if isinstance(((v or {}).get('cnt') or {}).get(k, 0), (int, float)))
    unf = sum(1 for v in td.values() for u, its in ((v or {}).get('unfinished') or {}).items() for it in its if 'WATER' in str(it[1]))
    err = str((d.get('tier_err') or {}).get('last_error', ''))[:30]
    print(f"{a:10s} own {m[0]:7.0f} rival {m[1]:7.0f} margin {m[0] - m[1]:+7.0f} | deaths {sum(died.values()):2d} "
          f"(plants {sum(v for k, v in died.items() if k.startswith('plant'))}, animals {sum(v for k, v in died.items() if k.startswith('animal'))}) "
          f"| unfinished waterings {unf:2d} | feed skips {cnt('skip_FEED'):2d} | deliveries {cnt('deliver'):2d} | {err}")
