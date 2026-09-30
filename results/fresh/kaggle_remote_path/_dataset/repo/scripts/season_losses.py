"""Season replay (leader tape vs our season stream, same world): units DELETED at each midnight dump (shed cap 100) by
product, and the sheep / wool chain per day (sheep on the board in the morning, wool harvested, sheep fed / cared, wool
sold). usage: season_losses.py <team:ep> <arm> -> JSON on stdout"""
import copy
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
REC = {'seat': 0, 'w': None, 'day': 0, 'lost': None, 'shed_before': None}
_orig_drop = E._drop_inventories_to_shed


def _drop(private, capacity):
    w = REC['w']
    if w is not None and private is w.private(REC['seat']):
        carried = defaultdict(int)
        for inv in private['inventories']:
            for k, v in inv.items():
                if v > 0:
                    carried[k] += v
        before = dict(private['shed'])
        _orig_drop(private, capacity)
        for k, v in carried.items():
            kept = private['shed'].get(k, 0) - before.get(k, 0)
            if v - kept > 0:
                REC['lost'][REC['day']][k] += v - kept
        REC['shed_before'][REC['day']] = [sum(before.values()), sum(carried.values())]
        return
    return _orig_drop(private, capacity)


E._drop_inventories_to_shed = _drop


def run(tape, stream):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    REC.update(w=w, seat=seat, lost=defaultdict(lambda: defaultdict(int)), shed_before={})
    daily = defaultdict(lambda: defaultdict(int))
    while w.t < 720:
        t = w.t
        REC['day'] = t // 24
        if stream is None or t < 264:
            own = UE.tape_action(tape['actions'], t)
        else:
            a = stream[t] if t < len(stream) else {}
            own = a if isinstance(a, dict) and a else dict(UE.PASS)
        farm = w.farms[seat]
        if t % 24 == 0:
            daily[t // 24]['sheep'] = sum(1 for r in farm['tiles'] for x in r if isinstance(x, dict) and x.get('animal') == 'SHEEP')
            daily[t // 24]['cows'] = sum(1 for r in farm['tiles'] for x in r if isinstance(x, dict) and x.get('animal') == 'COW')
        units = [farm['farmer']] + list(farm['hands'])
        cmds = [own.get('farmer')] + list(own.get('hands') or []) if own else []
        for u, c in enumerate(cmds):
            if not c or u >= len(units):
                continue
            x, y = units[u]
            tl = farm['tiles'][y][x]
            if isinstance(tl, dict) and tl.get('animal') == 'SHEEP':
                if c[0] == 'HARVEST':
                    daily[t // 24]['wool_harv'] += int(tl.get('yield_units', 0) or 0)
                elif c[0] == 'FEED' and not tl.get('fed_today'):
                    daily[t // 24]['sheep_fed'] += 1
                elif c[0] == 'CARE' and not tl.get('cared_today'):
                    daily[t // 24]['sheep_cared'] += 1
        acts = [None, None]
        acts[seat], acts[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(acts)
    REC['w'] = None
    return dict(final=[float(w.farms[seat]['money']), float(w.farms[1 - seat]['money'])],
                lost={d: dict(v) for d, v in REC['lost'].items()}, shed_before=REC['shed_before'],
                daily={d: dict(v) for d, v in daily.items()})


if __name__ == '__main__':
    game, arm = sys.argv[1], sys.argv[2]
    team, ep = game.split(':')
    tape = UE.load_tape(int(team), int(ep))
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm}_streams' / f'{ep}.json').read_text(encoding='utf-8'))
    json.dump({'leader': run(tape, None), arm: run(tape, s['actions'])}, sys.stdout)
