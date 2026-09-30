"""Labor use, the leader's game vs an arm's game (one world, days 11-28): every unit-hour classified as a move, idle
(PASS / no command), a successful op by type (the tile, the unit's inventory, the shed or seeds changed) or a no-effect
op (nothing changed: already watered, nothing to harvest, blocked...); hand-days and wages.
usage: case_labor.py <team:ep> <arm>"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
R = {'w': None, 'seat': 0, 't': 0, 'C': None}
_ua, _hire = E._apply_unit_action, E._do_hire
MOVES = {'NORTH', 'SOUTH', 'EAST', 'WEST'}


def ua(farm, private, idx, action, *a, **k):
    w = R['w']
    if w is None or R['t'] < 264 or R['t'] >= 696 or farm is not w.farms[R['seat']]:
        return _ua(farm, private, idx, action, *a, **k)
    C = R['C']
    op = action[0] if isinstance(action, list) and action else 'PASS'
    if op == 'PASS':
        C['idle'] += 1
        return _ua(farm, private, idx, action, *a, **k)
    before = json.dumps([farm['tiles'], private, E._farmer_position(farm, idx)], sort_keys=True, default=str)
    r = _ua(farm, private, idx, action, *a, **k)
    after = json.dumps([farm['tiles'], private, E._farmer_position(farm, idx)], sort_keys=True, default=str)
    if op in MOVES:
        C['move' if after != before else 'move_blocked'] += 1
    else:
        C[('ok|' if after != before else 'noeffect|') + op] += 1
    return r


def hire(farm, private, board_size, *a, **k):
    m0 = farm['money']
    r = _hire(farm, private, board_size, *a, **k)
    w = R['w']
    if w is not None and 264 <= R['t'] < 696 and farm is w.farms[R['seat']] and farm['money'] < m0:
        R['C']['hires'] += 1
        R['C']['wages'] += m0 - farm['money']
    return r


E._apply_unit_action, E._do_hire = ua, hire


def run(tape, stream):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    C = Counter()
    R.update(w=w, seat=seat, C=C)
    while w.t < 719:
        t = w.t
        R['t'] = t
        if stream is None or t < 264:
            own = UE.tape_action(tape['actions'], t)
        else:
            a = stream[t] if t < len(stream) else {}
            own = a if isinstance(a, dict) and a else dict(UE.PASS)
        if 264 <= t < 696:
            n = 1 + len(w.farms[seat]['hands'])
            C['unit_hours'] += n
            given = 1 + len(own.get('hands') or [])
            C['no_command'] += max(0, n - given)
        acts = [None, None]
        acts[seat], acts[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(acts)
    R['w'] = None
    return C


if __name__ == '__main__':
    g, arm = sys.argv[1], sys.argv[2]
    team, ep = g.split(':')
    tape = UE.load_tape(int(team), int(ep))
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))
    L, A = run(tape, None), run(tape, s['actions'])
    print(f'world {g}, days 11-28: DSM | {arm} | difference (unit-hours unless noted)')
    keys = ['unit_hours', 'hires', 'wages', 'move', 'move_blocked', 'idle', 'no_command']
    ops = sorted({k for k in set(L) | set(A) if k.startswith(('ok|', 'noeffect|'))}, key=lambda k: (k.split('|')[0], -L.get(k, 0)))
    for k in keys + ['ok total', 'noeffect total'] + ops:
        if k == 'ok total':
            a, b = sum(v for kk, v in L.items() if kk.startswith('ok|')), sum(v for kk, v in A.items() if kk.startswith('ok|'))
        elif k == 'noeffect total':
            a, b = sum(v for kk, v in L.items() if kk.startswith('noeffect|')), sum(v for kk, v in A.items() if kk.startswith('noeffect|'))
        else:
            a, b = L.get(k, 0), A.get(k, 0)
        print(f'  {k:28s} {a:7.0f} | {b:7.0f} | {b - a:+7.0f}')
