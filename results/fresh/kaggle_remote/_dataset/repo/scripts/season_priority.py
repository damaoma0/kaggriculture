"""Market counterfactuals on a season game (our stream replayed with the official engine, the rival's recorded moves):
  deliver:<P>:<h>   every day d in 11..28 at hour h, the units of P our hands carry are moved into the shed and sold that
                    hour (instead of the midnight dump and the next morning's sale). The walk is free (upper bound).
  h23room           at hour 23, when shed + carried would pass the 100 cap, shed stock is sold (cheapest per unit first,
                    wheat kept for tomorrow's feeds up to the herd size) so the dump loses nothing.
Reports final cash (us, rival), margin and revenue by product vs the unchanged replay.
usage: season_priority.py <team:ep> <arm> <case,...>   (case = deliver:WOOL:12[:day] | h23room | base)"""
import copy
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
PRODUCTS = ['WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON', 'EGG', 'MILK', 'WOOL', 'FERTILIZER']
REC = {'w': None, 'seat': 0, 'rev': None, 'lost': None}
_orig_commit = E._commit_unit
_orig_drop = E._drop_inventories_to_shed


def _commit(op, item, price, farm, private, market, shed_capacity=100):
    r = _orig_commit(op, item, price, farm, private, market, shed_capacity)
    w = REC['w']
    if r and w is not None and op == 'SELL':
        side = 0 if farm is w.farms[REC['seat']] else 1
        REC['rev'][side][item] += float(price)
    return r


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
            REC['lost'][k] += v - (private['shed'].get(k, 0) - before.get(k, 0))
        return
    return _orig_drop(private, capacity)


E._commit_unit = _commit
E._drop_inventories_to_shed = _drop


def run(tape, stream, case):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    REC.update(w=w, seat=seat, rev=[defaultdict(float), defaultdict(float)], lost=defaultdict(int))
    kind = case.split(':')
    moved = defaultdict(int)
    while w.t < 720:
        t = w.t
        d, h = divmod(t, 24)
        if t < 264:
            own = UE.tape_action(tape['actions'], t)
        else:
            a = stream[t] if t < len(stream) else {}
            own = copy.deepcopy(a) if isinstance(a, dict) and a else dict(UE.PASS)
        priv = w.private(seat)
        if kind[0] == 'deliver' and 11 <= d <= 28 and h == int(kind[2]) and (len(kind) < 4 or d == int(kind[3])):
            p = kind[1]
            n = 0
            for inv in priv['inventories']:
                if inv.get(p, 0) > 0:
                    n += inv[p]
                    del inv[p]
            room = max(0, 100 - sum(priv['shed'].values()))
            k = min(n, room)
            if k:
                priv['shed'][p] = priv['shed'].get(p, 0) + k
                own.setdefault('market', [])
                own['market'] = [['SELL', p, k]] + [o for o in own['market']][:9]
                moved[p] += k
            if n - k:                                  # no room: back in hand (the dump handles it as before)
                priv['inventories'][0][p] = priv['inventories'][0].get(p, 0) + n - k
        if kind[0] == 'h23room' and 11 <= d <= 28 and h == 23:
            carried = sum(v for inv in priv['inventories'] for v in inv.values() if v > 0)
            shed = priv['shed']
            over = sum(shed.values()) + carried - 100
            if over > 0:
                prices = w.market['prices']
                n_anim = sum(1 for r in w.farms[seat]['tiles'] for x in r if isinstance(x, dict) and x.get('animal'))
                sells = []
                for p in sorted((q for q in PRODUCTS if shed.get(q, 0) > 0), key=lambda q: prices[q]):
                    avail = shed[p] - (min(shed[p], n_anim) if p == 'WHEAT' else 0)
                    k = min(avail, over)
                    if k > 0:
                        sells.append(['SELL', p, k])
                        over -= k
                    if over <= 0:
                        break
                if sells:
                    own.setdefault('market', [])
                    own['market'] = sells + [o for o in own['market'] if o[0] != 'SELL'][:max(0, 10 - len(sells))]
        acts = [None, None]
        acts[seat], acts[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(acts)
    REC['w'] = None
    return dict(final=[float(w.farms[seat]['money']), float(w.farms[1 - seat]['money'])],
                rev=[dict(REC['rev'][0]), dict(REC['rev'][1])], lost=dict(REC['lost']), moved=dict(moved))


if __name__ == '__main__':
    game, arm, cases = sys.argv[1], sys.argv[2], sys.argv[3].split(',')
    team, ep = game.split(':')
    tape = UE.load_tape(int(team), int(ep))
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm}_streams' / f'{ep}.json').read_text(encoding='utf-8'))
    out = {c: run(tape, s['actions'], c) for c in ['base'] + cases}
    json.dump(out, sys.stdout)
