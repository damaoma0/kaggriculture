"""KW thread: aggregate WHEAT SELL / BUY_PRODUCT totals (units and $) across the panel13 worlds, for the leader tape
and for one or more of our arms' saved streams (results/fresh/day12_viz/<arm>_streams/<ep>.json, written by
scripts/run_arms.py). Read-only.

usage: wheat_panel_sales.py arm1,arm2,... -> prints a per-arm summary table (sold units/revenue, bought units/spend)
       vs the leader, summed over the 13-world panel.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402
from run_arms import PANEL13  # noqa: E402

E = UE.engine()
orig = E._commit_unit
REC = {'w': None, 'seat': 0, 't': 0, 'log': None}


def hook(op, item, price, farm, private, market, shed_capacity=100):
    r = orig(op, item, price, farm, private, market, shed_capacity)
    w = REC['w']
    if r and w is not None and op in ('SELL', 'BUY_PRODUCT') and item == 'WHEAT':
        side = 'us' if farm is w.farms[REC['seat']] else 'opp'
        REC['log'].append((side, op, float(price)))
    return r


E._commit_unit = hook


def run(tape, stream_actions):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    REC.update(w=w, seat=seat, log=[])
    while w.t < 720:
        t = w.t
        if stream_actions is None or t < 264:
            own = UE.tape_action(tape['actions'], t)
        else:
            a = stream_actions[t] if t < len(stream_actions) else {}
            own = a if isinstance(a, dict) and a else dict(UE.PASS)
        opp = UE.tape_action(tape['opp_actions'], t)
        acts = [None, None]
        acts[seat], acts[1 - seat] = own, opp
        w.step(acts)
    fin = [float(w.farms[seat]['money']), float(w.farms[1 - seat]['money'])]
    log = REC['log']
    REC['w'] = None
    return fin, log


def summarize(log, side):
    sell_n = sum(1 for s, op, p in log if s == side and op == 'SELL')
    sell_rev = sum(p for s, op, p in log if s == side and op == 'SELL')
    buy_n = sum(1 for s, op, p in log if s == side and op == 'BUY_PRODUCT')
    buy_cost = sum(p for s, op, p in log if s == side and op == 'BUY_PRODUCT')
    return sell_n, sell_rev, buy_n, buy_cost


def main():
    arms = sys.argv[1].split(',')
    dump = sys.argv[2] if len(sys.argv) > 2 else None
    totals = {a: [0, 0.0, 0, 0.0] for a in ['leader'] + arms}
    totals_opp = {a: [0, 0.0, 0, 0.0] for a in ['leader'] + arms}
    per_world = {a: [] for a in ['leader'] + arms}
    per_world_opp = {a: [] for a in ['leader'] + arms}
    for game in PANEL13:
        team, ep = game.split(':')
        tape = UE.load_tape(team, int(ep))
        _, log = run(tape, None)
        s, so = summarize(log, 'us'), summarize(log, 'opp')
        for i in range(4):
            totals['leader'][i] += s[i]
            totals_opp['leader'][i] += so[i]
        per_world['leader'].append(s)
        per_world_opp['leader'].append(so)
        for arm in arms:
            f = ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json'
            if not f.exists():
                per_world[arm].append(None)
                per_world_opp[arm].append(None)
                continue
            st = json.loads(f.read_text())
            _, log = run(tape, st['actions'])
            s, so = summarize(log, 'us'), summarize(log, 'opp')
            for i in range(4):
                totals[arm][i] += s[i]
                totals_opp[arm][i] += so[i]
            per_world[arm].append(s)
            per_world_opp[arm].append(so)
    print(f'{"arm":8s} {"sold_n":>8s} {"sold_rev":>10s} {"bought_n":>9s} {"bought_cost":>12s} {"net_cost":>10s} '
          f'{"opp_sold_n":>10s} {"opp_sold_rev":>12s}')
    for a in ['leader'] + arms:
        n, rev, bn, bc = totals[a]
        on, orev, _, _ = totals_opp[a]
        print(f'{a:8s} {n:8d} {rev:10.0f} {bn:9d} {bc:12.0f} {bc - rev:10.0f} {on:10d} {orev:12.0f}')
    print()
    for arm in arms:
        print(f'--- {arm} per-world (own sold/bought/net_cost, opp sold_rev) vs leader ---')
        for game, lw, aw, awo in zip(PANEL13, per_world['leader'], per_world[arm], per_world_opp[arm]):
            ep = game.split(':')[1]
            if aw is None:
                print(f'  {ep}: missing stream')
                continue
            print(f'  {ep}: leader sold {lw[0]:3d} bought {lw[2]:3d} | {arm} sold {aw[0]:3d} bought {aw[2]:3d} '
                  f'net_cost {aw[3]-aw[1]:7.0f} | opp sold_rev {awo[1]:8.0f}')
    if dump:
        out = {'totals': totals, 'totals_opp': totals_opp, 'per_world': per_world, 'per_world_opp': per_world_opp,
               'episodes': [g.split(':')[1] for g in PANEL13]}
        Path(dump).write_text(json.dumps(out), encoding='utf-8')
        print('wrote', dump)


if __name__ == '__main__':
    main()
