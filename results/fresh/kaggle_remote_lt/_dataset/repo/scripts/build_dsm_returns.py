"""The leader's daytime shed returns for sd_tier_copy_returns: per day 11-28 of one recorded game, the hands that drop
goods into the shed during the day at hour >= 5 (the returns after the dawn drops at the shed tiles), their drop hours
and units, and the units carried into the midnight dump. Written to results/fresh/threads_20260928/dsm_returns/<ep>.json.
usage: build_dsm_returns.py <team:ep>[,<team:ep>...]"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.argv += ['--prods', 'STRAWBERRY,WOOL,MILK,EGG,WHEAT,CARROT,TOMATO,FERTILIZER,MELON']
import case_delivery as CD  # noqa: E402

OUT = ROOT / 'results/fresh/threads_20260928/dsm_returns'
OUT.mkdir(parents=True, exist_ok=True)
for g in sys.argv[1].split(','):
    team, ep = g.split(':')
    L = CD.run(CD.UE.load_tape(int(team), int(ep)), None)
    days = {}
    for day in range(11, 29):
        ev = defaultdict(int)
        for u in L['units']:
            if u['how'] == 'day' and u['d'] // 24 == day and u['h'] >= 264 and u['d'] % 24 >= 5:
                ev[(u['unit'], u['d'] % 24)] += 1
        mid = sum(1 for u in L['units'] if u['how'] == 'midnight' and u['d'] == (day + 1) * 24)
        days[str(day)] = {'hands': len({k[0] for k in ev}), 'drops': sorted([k[1], v] for k, v in ev.items()), 'midnight': mid}
    (OUT / f'{ep}.json').write_text(json.dumps({'game': g, 'days': days}), encoding='utf-8')
    print('written', OUT / f'{ep}.json', {d: v['hands'] for d, v in days.items()})
