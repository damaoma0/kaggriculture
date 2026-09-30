"""Abandonment research (2026-09-26): check scripts/abandon_market.py reprice() against the official engine.
Replays a side's game, and at chosen steps puts n extra units of an item into OUR shed and sells them with an extra
first market order; compares both players' final cash change with reprice(). Steps are picked where neither player
sells that item in the same step (reprice inserts extra units first in the step; the engine interleaves orders).
usage: abandon_validate.py <side> <team:ep> <ITEM> <step:n,...>"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402
import abandon_market as AM  # noqa: E402


def play(tape, stream, inject):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    while w.t < 719:
        t = w.t
        if stream is None or t < 264:
            own = UE.tape_action(tape['actions'], t)
        else:
            a = stream[t] if t < len(stream) else {}
            own = copy.deepcopy(a) if isinstance(a, dict) and a else dict(UE.PASS)
        if t in inject:
            item, n = inject[t]
            sh = w.private(seat)['shed']
            sh[item] = sh.get(item, 0) + n
            own = dict(own)
            m = list(own.get('market', []))
            if len(m) >= 10:
                raise SystemExit('step %d already has 10 market orders; pick another step' % t)
            own['market'] = m + [['SELL', item, n]]      # appended: no recorded order is displaced
        acts = [None, None]
        acts[seat], acts[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(acts)
    return [float(w.farms[seat]['money']), float(w.farms[1 - seat]['money'])]


if __name__ == '__main__':
    side, game, item = sys.argv[1], sys.argv[2], sys.argv[3]
    inj = {int(a.split(':')[0]): (item, int(a.split(':')[1])) for a in sys.argv[4].split(',')}
    team, ep = game.split(':')
    tape = UE.load_tape(int(team), int(ep))
    stream = None
    if side != 'LEADER':
        stream = json.loads((ROOT / 'results/fresh/day12_viz' / f'{side.lower()}_streams' / f'{ep}.json').read_text())['actions']
    R = json.loads((AM.RDIR / side / f'{ep}.json').read_text())
    busy = {t[0] for t in R['trades'] if t[3] == item}
    for s in inj:
        if s in busy:
            print('warning: step', s, 'has recorded', item, 'sales (order interleaving differs)')
    base = play(tape, stream, {})
    mod = play(tape, stream, inj)
    d_own, d_riv = AM.reprice(R, item, [(s, n) for s, (it, n) in inj.items()])
    print('engine: own %+.0f rival %+.0f | reprice: own %+.0f rival %+.0f' % (mod[0] - base[0], mod[1] - base[1], d_own, d_riv))
