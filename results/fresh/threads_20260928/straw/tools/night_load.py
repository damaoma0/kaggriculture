"""per night: shed stock and units' carried goods right before the midnight dump (after the step-23 actions and market),
for arms on one world. usage: night_load.py <team:ep> ARM [ARM ...] [--days 20,25,28]"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
g = sys.argv[1]
days = [int(x) for x in sys.argv[sys.argv.index('--days') + 1].split(',')] if '--days' in sys.argv else None
arms = [a for a in sys.argv[2:] if not a.startswith('--') and not a[0].isdigit()]
team, ep = g.split(':')
tape = UE.load_tape(int(team), int(ep))
REC = {}
_drop = E._drop_inventories_to_shed


def drop(private, cap):
    w = REC.get('w')
    if w is not None and private is w.private(REC['seat']) and w.t >= 264:
        shed = Counter({k: v for k, v in private['shed'].items() if v})
        car = Counter()
        for inv in private['inventories']:
            for k, v in inv.items():
                if v > 0:
                    car[k] += v
        _drop(private, cap)
        after = Counter({k: v for k, v in private['shed'].items() if v})
        lost = {k: shed[k] + car[k] - after[k] for k in set(shed) | set(car) if shed[k] + car[k] - after[k] > 0}
        REC['nights'][w.t // 24] = (dict(shed), dict(car), sum(shed.values()), sum(car.values()), lost)
        return
    return _drop(private, cap)


E._drop_inventories_to_shed = drop
for arm in arms:
    s = json.loads((UE.ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    REC.update(w=w, seat=seat, nights={})
    while w.t < 719:
        t = w.t
        own = UE.tape_action(tape['actions'], t) if t < 264 else (s[t] if isinstance(s[t], dict) and s[t] else dict(UE.PASS))
        acts = [None, None]
        acts[seat], acts[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(acts)
    REC['w'] = None
    print(f'== {arm}')
    for d, (sh, car, ns, nc, lost) in sorted(REC['nights'].items()):
        if days and d not in days:
            continue
        print(f'  night {d}: shed {ns} {dict(sorted(sh.items()))} + carried {nc} {dict(sorted(car.items()))} -> lost {lost}')
