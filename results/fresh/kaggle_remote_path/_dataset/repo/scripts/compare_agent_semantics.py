"""Compare our agent's extracted game (scripts/extract_agent_semantics.py) with the leader's game in the same world:
units harvested per planting per crop, plantings, maintenance counts.
usage: compare_agent_semantics.py <agent_dir> [leader_semantics_root=data/leader_semantics]"""
import gzip, json, sys, glob
from pathlib import Path

agent_dir = Path(sys.argv[1])
root = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('data/leader_semantics')
CROPS = ('WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON')


def summary(g):
    out = {}
    for c in CROPS:
        planted = sum(len(d['planted'].get(c, [])) for d in g['days'])
        units = sum(d['harvested']['units'].get(c, 0) for d in g['days'])
        out[c] = (planted, units)
    m = {k: sum(len(d['maintenance'].get(k, [])) for d in g['days']) for k in ('WATER', 'FEED', 'CARE', 'FERTILIZE')}
    return out, m


rows = []
for f in sorted(agent_dir.glob('*.json.gz')):
    lead = next(iter(root.glob(f'*/{f.name}')), None)
    if lead is None:
        continue
    a, b = json.load(gzip.open(f, 'rt')), json.load(gzip.open(lead, 'rt'))
    (ca, ma), (cb, mb) = summary(a), summary(b)
    print(f.name, 'agent final', a['meta']['final_cash'], 'leader recorded', b['meta']['rewards'])
    for c in CROPS:
        (pa, ua), (pb, ub) = ca[c], cb[c]
        print(f'  {c:10s} agent {pa:4d} plantings {ua:5d} units ({ua / max(pa, 1):.2f}/planting) | leader {pb:4d} {ub:5d} ({ub / max(pb, 1):.2f})')
    print('  maintenance agent', ma, '| leader', mb)
