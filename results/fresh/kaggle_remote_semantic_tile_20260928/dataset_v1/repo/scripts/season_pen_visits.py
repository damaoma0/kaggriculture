"""Pen visits, leader game vs an arm's game (days 11-28, same world). A VISIT = consecutive steps of one unit on one
animal tile doing work there (HARVEST / FEED / CARE / COLLECT_FERTILIZER). Records per visit: animal, distance to the
nearest shed-access tile, ops done, units harvested, hour; and per shed DELIVERY (DROP / PLACE of produce at an access
tile): animal-product units delivered, pen visits with a harvest since the unit's last shed visit.
usage: season_pen_visits.py <arm> <panel file | team:ep,...> <out.json> [--workers 2]"""
import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
ACCESS = [tuple(p) for p in E._shed_access_tiles(10)]
APROD = {'EGG', 'MILK', 'WOOL'}
PROD = ('WHEAT', 'CARROT', 'TOMATO', 'MELON', 'STRAWBERRY', 'MILK', 'EGG', 'WOOL', 'FERTILIZER')
WORK = ('HARVEST', 'FEED', 'CARE', 'COLLECT_FERTILIZER')


def dshed(p):
    return min(abs(p[0] - a[0]) + abs(p[1] - a[1]) for a in ACCESS)


def run(tape, stream):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    C = Counter()
    cur = {}          # unit -> open visit {tile, animal, d, ops set, units}
    trip = {}         # unit -> pen harvest visits since last shed visit
    while w.t < 696:
        t = w.t
        if stream is None or t < 264:
            own = UE.tape_action(tape['actions'], t)
        else:
            a = stream[t] if t < len(stream) else {}
            own = a if isinstance(a, dict) and a else dict(UE.PASS)
        track = t >= 264
        if track:
            f = w.farms[seat]
            pv = w.private(seat)
            pos = [tuple(f['farmer'])] + [tuple(p) for p in f['hands']]
            acts = [own.get('farmer')] + list(own.get('hands') or [])
            inv0 = [dict(pv['inventories'][i]) if i < len(pv['inventories']) else {} for i in range(len(pos))]
            tiles0 = [f['tiles'][p[1]][p[0]] for p in pos]
            h = t % 24
            if h == 0:
                for u, v in list(cur.items()):
                    C.update(v['c'])
                cur, trip = {}, {}
                for row in f['tiles']:
                    for x in row:
                        if isinstance(x, dict) and 'animal' in x:
                            C['animal_days'] += 1
        acts2 = [None, None]
        acts2[seat], acts2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(acts2)
        if not track:
            continue
        pv = w.private(seat)
        for i, p in enumerate(pos):
            a = acts[i] if i < len(acts) else None
            op = a[0] if isinstance(a, list) and a else None
            tl = tiles0[i]
            inv1 = pv['inventories'][i] if i < len(pv['inventories']) else {}
            on_pen = isinstance(tl, dict) and 'animal' in tl and op in WORK
            v = cur.get(i)
            if v is not None and (not on_pen or v['tile'] != p):
                C.update(v['c'])                  # close the visit
                if v['units'] > 0:
                    trip[i] = trip.get(i, 0) + 1
                del cur[i]
                v = None
            if on_pen:
                if v is None:
                    d = dshed(p)
                    v = cur[i] = {'tile': p, 'units': 0, 'c': Counter()}
                    v['key'] = f"{tl['animal']}|d{min(d, 3)}"
                    v['c'][f"visits|{v['key']}"] += 1
                    v['c'][f'visits_h|{h}'] += 1
                gained = sum(max(0, inv1.get(k, 0) - inv0[i].get(k, 0)) for k in APROD)
                done = (inv1 != inv0[i]) or op in ('FEED', 'CARE')
                v['c'][f"ops|{v['key']}"] += 1
                v['c'][f"op_{op}|{v['key']}"] += 1
                if op == 'HARVEST' and gained:
                    v['units'] += gained
                    v['c'][f"hv|{v['key']}"] += 1
                    v['c'][f"hv_units|{v['key']}"] += gained
            if p in ACCESS and op in ('DROP', 'PLACE') and not (op == 'PLACE' and len(a) > 1 and a[1] in ('COW', 'SHEEP', 'GOOSE')):
                moved = {k: inv0[i].get(k, 0) - inv1.get(k, 0) for k in PROD if inv0[i].get(k, 0) - inv1.get(k, 0) > 0}
                am = sum(v2 for k, v2 in moved.items() if k in APROD)
                if moved:
                    C['deliveries'] += 1
                    C['deliv_units'] += sum(moved.values())
                    if am:
                        C['deliv_animal'] += 1
                        C['deliv_animal_units'] += am
                        C[f'deliv_animal_pens_{min(trip.get(i, 0), 4)}'] += 1
                        C[f'deliv_animal_h|{h}'] += am
                trip[i] = 0
            elif p in ACCESS:
                trip[i] = 0 if op not in WORK else trip.get(i, 0)
    return dict(C)


def job(args):
    g, arm = args
    team, ep = g.split(':')
    tape = UE.load_tape(int(team), int(ep))
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))
    return ep, {'leader': run(tape, None), arm: run(tape, s['actions'])}


if __name__ == '__main__':
    arm, games, out = sys.argv[1], sys.argv[2], sys.argv[3]
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    p = Path(games)
    games = p.read_text().replace(',', ' ').split() if p.exists() else games.split(',')
    res = {}
    with Pool(nw) as pool:
        for ep, r in pool.imap_unordered(job, [(g, arm) for g in games]):
            res[ep] = r
            print('done', ep, len(res), flush=True)
    json.dump(res, open(out, 'w'))
