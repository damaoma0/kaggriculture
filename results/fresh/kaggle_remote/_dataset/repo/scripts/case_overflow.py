"""Midnight overflow days, one world: whose goods the dump deleted and the labor behind them. The engine drops the
farmer's inventory first, then the hands in index order (items in inventory order) and discards everything once the
shed holds 100, so the deleted units belong to specific hands. For every day with deletions: the shed content before
the dump (what held the room), each hand's carry and loss, the successful work that produced the deleted goods that day
(harvest / collect ops of that product by that hand, prorated by the share deleted), and the day's labor (moves, idle,
ops) of those hands; the leader's same day for comparison.
usage: case_overflow.py <team:ep> <arm>"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
R = {'w': None, 'seat': 0, 't': 0, 'L': None}
_ua, _drop = E._apply_unit_action, E._drop_inventories_to_shed
MOVES = {'NORTH', 'SOUTH', 'EAST', 'WEST'}


def ua(farm, private, idx, action, *a, **k):
    w = R['w']
    if w is None or R['t'] < 264 or farm is not w.farms[R['seat']]:
        return _ua(farm, private, idx, action, *a, **k)
    L = R['L']
    d = R['t'] // 24
    op = action[0] if isinstance(action, list) and action else 'PASS'
    ib = dict(E._farmer_inventory(private, idx))
    before = json.dumps([farm['tiles'], private], sort_keys=True, default=str)
    r = _ua(farm, private, idx, action, *a, **k)
    ok = json.dumps([farm['tiles'], private], sort_keys=True, default=str) != before
    lab = 'move' if op in MOVES else ('idle' if op == 'PASS' else ('op' if ok else 'noeffect'))
    L['labor'][(d, idx)][lab] += 1
    if ok and op in ('HARVEST', 'COLLECT_FERTILIZER'):
        for kk, v in E._farmer_inventory(private, idx).items():
            if v - ib.get(kk, 0) > 0:
                L['made'][(d, idx, kk)][0] += v - ib.get(kk, 0)
                L['made'][(d, idx, kk)][1] += 1          # ops
    return r


def drop(private, cap):
    w = R['w']
    if w is not None and R['t'] >= 264 and private is w.private(R['seat']):
        L = R['L']
        d = R['t'] // 24
        shed = dict(private['shed'])
        L['shed_before'][d] = {k: v for k, v in shed.items() if v}
        room = cap - sum(shed.values())
        for i, inv in enumerate(private['inventories']):
            for item, n in inv.items():
                if n <= 0:
                    continue
                take = max(0, min(n, room))
                room -= take
                L['carry'][(d, i)][item] += n
                if n - take:
                    L['lost'][(d, i)][item] += n - take
    return _drop(private, cap)


E._apply_unit_action, E._drop_inventories_to_shed = ua, drop


def run(tape, stream):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    L = {'labor': defaultdict(Counter), 'made': defaultdict(lambda: [0, 0]), 'carry': defaultdict(Counter),
         'lost': defaultdict(Counter), 'shed_before': {}}
    R.update(w=w, seat=seat, L=L)
    while w.t < 696:
        t = w.t
        R['t'] = t
        if stream is None or t < 264:
            own = UE.tape_action(tape['actions'], t)
        else:
            a = stream[t] if t < len(stream) else {}
            own = a if isinstance(a, dict) and a else dict(UE.PASS)
        acts = [None, None]
        acts[seat], acts[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(acts)
    R['w'] = None
    return L


def report(L, lab, days):
    tot_lost, tot_ops, tot_h = 0, 0.0, 0
    for d in days:
        lost = {i: c for (dd, i), c in L['lost'].items() if dd == d and sum(c.values())}
        carry = sum(sum(c.values()) for (dd, i), c in L['carry'].items() if dd == d)
        sb = L['shed_before'].get(d, {})
        n_lost = sum(sum(c.values()) for c in lost.values())
        print(f'  {lab} day {d}: shed before the dump {sum(sb.values())} {sb} | carried {carry} | deleted {n_lost}')
        for i, c in sorted(lost.items()):
            wasted = 0.0
            for item, n in c.items():
                made, ops = L['made'].get((d, i, item), (0, 0))
                if made:
                    wasted += ops * min(1.0, n / made)
            lb = L['labor'].get((d, i), Counter())
            tot_ops += wasted
            tot_h += lb['idle']
            print(f'     unit {i:2d} lost {dict(c)} of carry {dict(L["carry"][(d, i)])} | work that made the lost goods today ~{wasted:.1f} op-hours'
                  f' | its day: ops {lb["op"]}, moves {lb["move"]}, idle {lb["idle"]}, no-effect {lb["noeffect"]}')
        tot_lost += n_lost
    print(f'  {lab} total: {tot_lost} units deleted, ~{tot_ops:.1f} op-hours of harvest / collect work lost with them')


if __name__ == '__main__':
    g, arm = sys.argv[1], sys.argv[2]
    team, ep = g.split(':')
    tape = UE.load_tape(int(team), int(ep))
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))
    A = run(tape, s['actions'])
    days = sorted({d for (d, i), c in A['lost'].items() if sum(c.values())})
    print(f'world {g}: {arm} overflow days {days}')
    report(A, arm, days)
    Ld = run(tape, None)
    print('\nDSM on the same days:')
    report(Ld, 'DSM', days)
    print('\nall units, those days: ' + ' | '.join(
        f'{lab} moves {sum(c["move"] for (d, i), c in G["labor"].items() if d in days)}, idle {sum(c["idle"] for (d, i), c in G["labor"].items() if d in days)}, '
        f'ops {sum(c["op"] for (d, i), c in G["labor"].items() if d in days)}, no-effect {sum(c["noeffect"] for (d, i), c in G["labor"].items() if d in days)}'
        for lab, G in ((arm, A), ('DSM', Ld))))
