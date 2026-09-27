"""The leader's dawn trips per day for sd_tier_dawn_shape "file": scripts/dsm_dawn_shape.py trips converted to the flag's
format {day: [[unit, first acting hour, start tile idx, [[pen tile idx, animal], ...], drop tile idx], ...]} (trips that
visit no animal pen, e.g. the melon run, are left out). Written to results/fresh/threads_20260928/dsm_dawn/<ep>.json.
usage: build_dsm_dawn.py <team:ep>[,<team:ep>...]"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import dsm_dawn_shape as DD  # noqa: E402

OUT = ROOT / 'results/fresh/threads_20260928/dsm_dawn'
OUT.mkdir(parents=True, exist_ok=True)
idx = lambda p: int(p[1]) * 10 + int(p[0])
for g in sys.argv[1].split(','):
    team, ep = g.split(':')
    T = DD.trips_of(DD.trace(DD.UE.load_tape(int(team), int(ep)), None), 8)
    days = {}
    for d, r in T.items():
        out = []
        for tr in r['trips']:
            pens = [[idx(x[0]), x[2]] for x in tr['tiles'] if x[2] in ('COW', 'SHEEP', 'GOOSE')]
            if pens:
                out.append([tr['u'], tr['act_h'], idx(tr['start']), pens, idx(tr['drop_tile'])])
        if out:
            days[str(d)] = out
    (OUT / f'{ep}.json').write_text(json.dumps({'game': g, 'days': days}), encoding='utf-8')
    print('written', ep, sum(len(v) for v in days.values()), 'trips')
