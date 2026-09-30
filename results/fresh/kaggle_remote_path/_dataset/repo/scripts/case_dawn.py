"""Dawn deliveries of animal products, the leader's recorded game vs arms' games (one world, days 11-29).
Replays each game on the engine and follows every WOOL / MILK (default) unit from harvest to the shed:
  - harvests by hour bin (0-5 / 6-11 / 12-17 / 18-23), units, size per harvest, pen distance to the shed tiles
  - deliveries: daytime PLACE / DROP on a shed tile (sold from that step) vs the midnight dump; carry time per unit
    (harvest -> in the shed), delivered within 2 h of the harvest
  - short round trips: a unit standing on a shed tile at hour <= 5 walks to a pen OFF the shed tiles within 2 tiles,
    HARVESTs it and is back on a shed tile with a PLACE / DROP of that product within sd 4 steps of leaving
  - mid-day returns: daytime deliveries at hours 6-11 / 12-17 / 18-23
usage: case_dawn.py <team:ep> <arm>[,<arm>...] [--prods WOOL,MILK] [--json out.json] [--days 20]   (the leader always)
Arms are read from results/fresh/day12_viz/<arm>_streams/<ep>.json."""
import json
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

PRODS = tuple(sys.argv[sys.argv.index('--prods') + 1].split(',')) if '--prods' in sys.argv else ('WOOL', 'MILK')
SRC = {'WOOL': 'SHEEP', 'MILK': 'COW', 'EGG': 'GOOSE'}
SHED = {(4, 4), (5, 4), (4, 5), (5, 5)}


def dshed(p):
    return min(abs(p[0] - q[0]) + abs(p[1] - q[1]) for q in SHED)


def run(tape, stream):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    harv, units, trips = [], [], []
    fifo = defaultdict(deque)
    hist = defaultdict(list)          # unit -> [(t, pos, op, cmd)]
    while w.t < 719:
        t = w.t
        if stream is None or t < 264:
            own = UE.tape_action(tape['actions'], t)
        else:
            a = stream[t] if t < len(stream) else {}
            own = a if isinstance(a, dict) and a else dict(UE.PASS)
        track = t >= 264
        if track:
            f, pv = w.farms[seat], w.private(seat)
            pos = [tuple(f['farmer'])] + [tuple(p) for p in f['hands']]
            acts = [own.get('farmer')] + list(own.get('hands') or [])
            inv0 = [dict(pv['inventories'][i]) if i < len(pv['inventories']) else {} for i in range(len(pos))]
            tiles0 = f['tiles']
            if t == 264:
                for i, inv in enumerate(inv0):
                    for k, v in inv.items():
                        if k in PRODS:
                            fifo[i].extend([(k, 264, None)] * int(v))
            shed0 = dict(pv['shed'])
        acts2 = [None, None]
        acts2[seat], acts2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(acts2)
        if not track:
            continue
        pv = w.private(seat)
        for i, p in enumerate(pos):
            a = acts[i] if i < len(acts) else None
            op = a[0] if isinstance(a, list) and a else 'PASS'
            hist[i].append((t, p, op))
            inv1 = pv['inventories'][i] if i < len(pv['inventories']) else {}
            for k in PRODS:
                d = int(inv1.get(k, 0) or 0) - int(inv0[i].get(k, 0) or 0)
                if d > 0:
                    if op == 'HARVEST':
                        tl = tiles0[p[1]][p[0]]
                        harv.append({'t': t, 'unit': i, 'tile': list(p), 'p': k, 'n': d, 'ds': dshed(p),
                                     'animal': tl.get('animal') if isinstance(tl, dict) else None})
                    fifo[i].extend([(k, t, list(p), op)] * d)
                elif d < 0:
                    n = -d
                    kept, moved = deque(), []
                    q = fifo[i]
                    while q and n:
                        u = q.popleft()
                        if u[0] == k:
                            moved.append(u)
                            n -= 1
                        else:
                            kept.append(u)
                    kept.extend(q)
                    q.clear()
                    q.extend(kept)
                    how = 'day' if p in SHED and op in ('PLACE', 'DROP') else ('midnight' if t % 24 == 23 else 'other:' + op)
                    for u in moved:
                        units.append({'p': k, 'h': u[1], 'tile': u[2], 'unit': i, 'd': t, 'how': how, 'op': op})
        if t % 24 == 23:                       # the midnight dump: whatever is left in hands is in the shed next hour
            for i in list(fifo):
                for u in fifo[i]:
                    units.append({'p': u[0], 'h': u[1], 'tile': u[2], 'unit': i, 'd': t + 1, 'how': 'midnight', 'op': 'dump'})
                fifo[i].clear()
    # short round trips: on a shed tile at step a (hour <= 5), HARVEST at an off-shed pen within 2 at step h > a,
    # daytime delivery of that product at step d <= a + 4
    ev = defaultdict(list)
    for u in units:
        if u['how'] == 'day' and u['tile'] is not None:
            ev[(u['unit'], u['d'])].append(u)
    for (i, d), us in sorted(ev.items()):
        H = {x[0]: x for x in hist[i]}
        src = Counter((tuple(x['tile']), x['h']) for x in us)
        for (tl, h), n in src.items():
            if tl in SHED or dshed(tl) > 2:
                continue
            a = None                            # the last step before h the unit stood on a shed tile
            for s in range(h - 1, max(263, h - 6), -1):
                if s in H and H[s][1] in SHED:
                    a = s
                    break
            if a is None or (a % 24) > 5 or d - a > 4:
                continue
            trips.append({'unit': i, 'leave': a, 'harvest': h, 'deliver': d, 'tile': list(tl), 'n': n,
                          'p': us[0]['p'], 'day': a // 24, 'hour': a % 24, 'ds': dshed(tl)})
    return {'harv': harv, 'units': units, 'trips': trips}


def summary(name, L, out):
    print(f'=== {name}')
    hb = lambda t: ('0-5', '6-11', '12-17', '18-23')[(t % 24) // 6]
    for p in PRODS:
        H = [x for x in L['harv'] if x['p'] == p]
        by = Counter()
        for x in H:
            by[hb(x['t'])] += x['n']
        near = [x for x in H if x['ds'] <= 2]
        nearb = Counter()
        for x in near:
            nearb[hb(x['t'])] += x['n']
        sz = [x['n'] for x in H]
        U = [u for u in L['units'] if u['p'] == p and u['h'] >= 264]
        dd = Counter(u['how'].split(':')[0] for u in U)
        w2 = sum(1 for u in U if u['how'] == 'day' and u['d'] - u['h'] <= 2)
        carry = sorted(u['d'] - u['h'] for u in U)
        med = carry[len(carry) // 2] if carry else None
        dayd = Counter(hb(u['d']) for u in U if u['how'] == 'day')
        print(f'  {p}: harvested {sum(sz)} in {len(sz)} harvests (mean {sum(sz) / max(1, len(sz)):.2f}); by hour '
              + ' '.join(f'{k}:{by[k]}' for k in ('0-5', '6-11', '12-17', '18-23'))
              + f'; near pens (<=2) {sum(x["n"] for x in near)} by hour ' + ' '.join(f'{k}:{nearb[k]}' for k in ('0-5', '6-11', '12-17', '18-23')))
        print(f'     delivered: {dict(dd)}; daytime by hour ' + ' '.join(f'{k}:{dayd[k]}' for k in ('0-5', '6-11', '12-17', '18-23'))
              + f'; within 2 h of harvest {w2}; carry median {med} h, mean {sum(carry) / max(1, len(carry)):.1f} h')
        out.setdefault(name, {})[p] = {'harvested': sum(sz), 'harvests': len(sz), 'by_hour': dict(by), 'near_by_hour': dict(nearb),
                                       'delivered': dict(dd), 'day_by_hour': dict(dayd), 'within2': w2, 'carry_med': med,
                                       'carry_mean': round(sum(carry) / max(1, len(carry)), 2)}
    T = L['trips']
    print(f'  short round trips: {len(T)} trips, {sum(x["n"] for x in T)} units; by leave hour {dict(Counter(x["hour"] for x in T))}; '
          f'by product {dict(Counter(x["p"] for x in T))}; mean size {sum(x["n"] for x in T) / max(1, len(T)):.2f}; '
          f'leave->deliver {dict(Counter(x["deliver"] - x["leave"] for x in T))}')
    for x in T[:40]:
        print(f'     d{x["day"]} h{x["hour"]} u{x["unit"]} {x["p"]} {x["n"]} from {x["tile"]} (ds {x["ds"]}): leave {x["leave"] % 24} harvest {x["harvest"] % 24} deliver {x["deliver"] % 24}')
    out.setdefault(name, {})['trips'] = T
    out[name]['harv'] = L['harv']
    out[name]['units'] = L['units']


if __name__ == '__main__':
    g, arms = sys.argv[1], sys.argv[2].split(',')
    team, ep = g.split(':')
    tape = UE.load_tape(int(team), int(ep))
    out = {'game': g, 'prods': PRODS}
    L = run(tape, None)
    summary('leader', L, out)
    for arm in arms:
        s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))
        summary(arm, run(tape, s['actions']), out)
    if '--json' in sys.argv:
        json.dump(out, open(sys.argv[sys.argv.index('--json') + 1], 'w'), default=list)
