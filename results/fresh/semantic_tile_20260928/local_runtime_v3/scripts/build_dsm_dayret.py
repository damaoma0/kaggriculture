"""The leader's daytime returns (shape) for sd_tier_dayret_shape "file": per day 11-28 of one recorded game, every leader
hand that drops goods into the shed at hour >= 5, with the drop hour, the drop tile and the tiles it harvested those goods
on (in harvest order, with product and harvest hour). Written to results/fresh/threads_20260928/dsm_dayret/<ep>.json as
{day: [[unit, drop hour, drop tile idx, [[tile idx, product, harvest hour], ...]], ...]}.
usage: build_dsm_dayret.py <team:ep>[,<team:ep>...]"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.argv += ['--prods', 'STRAWBERRY,WOOL,MILK,EGG,WHEAT,CARROT,TOMATO,FERTILIZER,MELON']
import case_delivery as CD  # noqa: E402

OUT = ROOT / 'results/fresh/threads_20260928/dsm_dayret'
OUT.mkdir(parents=True, exist_ok=True)
for g in sys.argv[1].split(','):
    team, ep = g.split(':')
    L = CD.run(CD.UE.load_tape(int(team), int(ep)), None)
    ev = defaultdict(list)
    drop_at = {}
    for e in L['events']:
        if e['op'] in ('DROP', 'PLACE') and e['n'] > 0:
            drop_at[(e['t'], e['unit'])] = e['at']
    for u in L['units']:
        if u['how'] == 'day' and u['d'] % 24 >= 5 and u['h'] >= 264 and u['tile'] is not None and 11 <= u['d'] // 24 <= 28:
            ev[(u['d'], u['unit'])].append((u['h'], u['tile'][1] * 10 + u['tile'][0], u['p']))
    days = defaultdict(list)
    for (t, unit), us in sorted(ev.items()):
        tiles, seen = [], set()
        for h, ti, p in sorted(us):
            if ti not in seen:
                seen.add(ti)
                tiles.append([ti, p, h % 24])
        at = drop_at.get((t, unit))
        days[str(t // 24)].append([unit, t % 24, (at[1] * 10 + at[0]) if at else 44, tiles])
    (OUT / f'{ep}.json').write_text(json.dumps({'game': g, 'days': days}), encoding='utf-8')
    print('written', ep, sum(len(v) for v in days.values()), 'returns')
