"""What fills the shed: at every midnight dump (days 11-28), the shed's contents by product just before the dump, what the
units carry in (by product), and what is deleted; plus the shed at hour 12. Leader tape vs an arm's season stream.
usage: season_shed.py <arm lowercase> <team:ep,...|panel13>  -> JSON on stdout: {ep: {game: {day: {...}}}}"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402
from run_arms import PANEL13  # noqa: E402

E = UE.engine()
REC = {'w': None, 'seat': 0, 'day': 0, 'out': None}
_orig_drop = E._drop_inventories_to_shed


def _drop(private, capacity):
    w = REC['w']
    if w is not None and private is w.private(REC['seat']):
        carried = defaultdict(int)
        for inv in private['inventories']:
            for k, v in inv.items():
                if v > 0:
                    carried[k] += v
        before = {k: v for k, v in private['shed'].items() if v > 0}
        _orig_drop(private, capacity)
        lost = {k: v - (private['shed'].get(k, 0) - before.get(k, 0)) for k, v in carried.items()}
        REC['out'][REC['day']].update(shed23=before, carried=dict(carried), lost={k: v for k, v in lost.items() if v > 0})
        return
    return _orig_drop(private, capacity)


E._drop_inventories_to_shed = _drop


def run(tape, stream):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    REC.update(w=w, seat=seat, out=defaultdict(dict))
    while w.t < 720:
        t = w.t
        REC['day'] = t // 24
        if t % 24 == 12:
            REC['out'][t // 24]['shed12'] = {k: v for k, v in w.private(seat)['shed'].items() if v > 0}
        if stream is None or t < 264:
            own = UE.tape_action(tape['actions'], t)
        else:
            a = stream[t] if t < len(stream) else {}
            own = a if isinstance(a, dict) and a else dict(UE.PASS)
        acts = [None, None]
        acts[seat], acts[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(acts)
    REC['w'] = None
    return {d: v for d, v in REC['out'].items() if 11 <= d <= 28}


if __name__ == '__main__':
    arm = sys.argv[1]
    games = PANEL13 if sys.argv[2] == 'panel13' else sys.argv[2].split(',')
    out = {}
    for g in games:
        team, ep = g.split(':')
        tape = UE.load_tape(int(team), int(ep))
        s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm}_streams' / f'{ep}.json').read_text(encoding='utf-8'))
        out[ep] = {'leader': run(tape, None), arm: run(tape, s['actions'])}
    json.dump(out, sys.stdout)
