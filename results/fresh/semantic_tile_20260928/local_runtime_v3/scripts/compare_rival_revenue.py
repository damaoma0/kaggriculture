"""Rival's sales per product when the recorded opponent faces the LEADER vs faces our agent in the same world
(both extracted by scripts/extract_agent_semantics.py; the opponent replays its recorded actions in both).
usage: compare_rival_revenue.py <agent_dir> [leader_dir=results/fresh/agent_semantics/LEADER] [collapse=0.8]"""
import gzip, json, sys, collections
from pathlib import Path

agent_dir = Path(sys.argv[1])
leader_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('results/fresh/agent_semantics/LEADER')
collapse = float(sys.argv[3]) if len(sys.argv) > 3 else 0.8


def tot(g, key):
    out = collections.defaultdict(lambda: [0, 0.0])
    if key == 'rival':
        for d in g['rival_sales']:
            for item, (u, r) in d.items():
                out[item][0] += u; out[item][1] += r
    else:
        for d in g['days']:
            for item, u in d['market']['sold_units'].items():
                out[item][0] += u
            for item, r in d['market']['sold_revenue'].items():
                out[item][1] += r
    return out


rows, keep = [], []
for f in sorted(agent_dir.glob('*.json.gz')):
    lf = leader_dir / f.name
    if not lf.exists():
        continue
    a, l = json.load(gzip.open(f, 'rt')), json.load(gzip.open(lf, 'rt'))
    if 'rival_sales' not in a or 'rival_sales' not in l:
        continue
    s = a['meta']['seat']
    fa, fl = a['meta']['final_cash'], l['meta']['final_cash']
    collapsed = fa[1 - s] < collapse * fl[1 - s]
    rows.append((f.name.split('.')[0], fa[s] - fl[s], fa[1 - s] - fl[1 - s], collapsed))
    if not collapsed:
        keep.append((tot(a, 'rival'), tot(l, 'rival'), tot(a, 'own'), tot(l, 'own')))
for r in rows:
    print(f'{r[0]}  own {r[1]:+8.0f}  rival {r[2]:+8.0f}  {"(rival collapsed)" if r[3] else ""}')
n = len(keep)
print(f'\n{n} worlds without a collapsed rival: per-game difference (agent world minus leader world)')
items = sorted({i for k in keep for part in k for i in part})
print(f'{"product":12s} {"rival units":>11s} {"rival rev":>10s} {"rival price":>11s} | {"own units":>9s} {"own rev":>9s}')
for i in items:
    ru = sum(k[0][i][0] - k[1][i][0] for k in keep) / n
    rr = sum(k[0][i][1] - k[1][i][1] for k in keep) / n
    ua = sum(k[0][i][0] for k in keep); ra = sum(k[0][i][1] for k in keep)
    ul = sum(k[1][i][0] for k in keep); rl = sum(k[1][i][1] for k in keep)
    pa, pl = (ra / ua if ua else 0), (rl / ul if ul else 0)
    ou = sum(k[2][i][0] - k[3][i][0] for k in keep) / n
    orr = sum(k[2][i][1] - k[3][i][1] for k in keep) / n
    print(f'{i:12s} {ru:+11.1f} {rr:+10.0f} {pa - pl:+11.1f} | {ou:+9.1f} {orr:+9.0f}')
