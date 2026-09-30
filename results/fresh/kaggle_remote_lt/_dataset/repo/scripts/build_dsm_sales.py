"""The leader's sell plan for sd_books_sell: per step (all days, from step 0, so the cumulative matches the agent's sold counter, which the harness starts with
the leader's days 0-10) of one recorded game, the units the leader actually
sold of each product and the list position of its sell order. Written to results/fresh/threads_20260928/dsm_sales/<ep>.json.
usage: build_dsm_sales.py <team:ep>[,<team:ep>...]"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
R = {'w': None, 'seat': 0, 't': 0, 'sold': None}
_commit = E._commit_unit


def commit(op, item, price, farm, private, market, shed_capacity=100):
    r = _commit(op, item, price, farm, private, market, shed_capacity)
    w = R['w']
    if r and w is not None and op == 'SELL' and farm is w.farms[R['seat']]:
        R['sold'][(R['t'], item)] += 1
    return r


E._commit_unit = commit
OUT = ROOT / 'results/fresh/threads_20260928/dsm_sales'
OUT.mkdir(parents=True, exist_ok=True)
for g in sys.argv[1].split(','):
    team, ep = g.split(':')
    tape = UE.load_tape(int(team), int(ep))
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    R.update(w=w, seat=seat, sold=Counter())
    pos = {}
    while w.t < 719:
        t = w.t
        R['t'] = t
        own = UE.tape_action(tape['actions'], t)
        if t >= 264:
            for i, o in enumerate((own.get('market') or [])[:10]):
                if isinstance(o, list) and o and o[0] == 'SELL':
                    pos.setdefault(str(t), {})[o[1]] = i
        acts = [None, None]
        acts[seat], acts[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(acts)
    steps = defaultdict(dict)
    for (t, p), n in R['sold'].items():
        steps[str(t)][p] = {'n': n, 'pos': pos.get(str(t), {}).get(p, 0)}
    (OUT / f'{ep}.json').write_text(json.dumps({'game': g, 'steps': steps}), encoding='utf-8')
    pc = Counter(v['pos'] for st in steps.values() for p, v in st.items() if p in ('STRAWBERRY', 'WOOL', 'MILK'))
    print('written', OUT / f'{ep}.json', 'strawberry/wool/milk sell positions:', dict(sorted(pc.items())))
