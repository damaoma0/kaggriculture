"""Shed flow of the leaders (and of an arm's season stream): how goods get from the field to the market, hour by hour.

Replays a recorded episode (both seats' recorded actions, forced shops) through the official engine with hooks on
the leader's seat only, and records
  - nights: at every midnight dump, the shed just before it (after the hour-23 market), what the units carry in by
    product and per unit, what is deleted, animal product still held on the tiles, and the day's sales by hour;
  - drops: every DROP / PLACE at the shed (any hour), with provenance (harvested / collected that day vs picked up
    from the shed), what was sold of it the same hour, the unit's inventory, the trip it ends (start hour, work ops),
    and what the unit does after it (work ops, harvested units, whether it walks out again);
  - hourly: sales / buys by product with revenue, market quotes at the start of every hour, shed totals.
usage: leader_shed_flow.py leaders <out.jsonl.gz> [--teams t1,t2] [--max-per-team N] [--workers 3]
       leader_shed_flow.py arm <arm lowercase> <panel file | team:ep,...> <out.jsonl.gz> [--workers 3]
(arm mode: the leader's recorded actions up to step 264, then the arm's stream from results/fresh/day12_viz/)"""
import gzip
import json
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
PROD = ('WHEAT', 'CARROT', 'TOMATO', 'MELON', 'STRAWBERRY', 'MILK', 'EGG', 'WOOL', 'FERTILIZER')
WORK = ('HARVEST', 'FEED', 'CARE', 'WATER', 'FERTILIZE', 'PLANT', 'COLLECT_FERTILIZER', 'DIG', 'BUILD_COOP',
        'BUILD_PASTURE')
ACCESS = {tuple(p) for p in E._shed_access_tiles(10)}
_ua0, _commit0, _drop0, _refresh0 = (E._apply_unit_action, E._commit_unit, E._drop_inventories_to_shed,
                                     E._daily_refresh_animals)
R = {'w': None}


def _inv(private, idx):
    inv = E._farmer_inventory(private, idx)
    return {k: v for k, v in inv.items() if v > 0} if inv is not None else {}


def ua(farm, private, idx, action, *a, **k):
    w = R['w']
    if w is None or private is not w.private(R['seat']):
        return _ua0(farm, private, idx, action, *a, **k)
    pos = E._farmer_position(farm, idx)
    pos = tuple(pos) if pos is not None else None
    ib = _inv(private, idx)
    sb = dict(private['shed'])
    op = action[0] if isinstance(action, list) and action else 'PASS'
    tile = farm['tiles'][pos[1]][pos[0]] if pos else None
    lab = (tile.get('crop') or tile.get('animal') or tile.get('kind')) if isinstance(tile, dict) else str(tile)
    r = _ua0(farm, private, idx, action, *a, **k)
    ia = _inv(private, idx)
    pa = E._farmer_position(farm, idx)
    pa = tuple(pa) if pa is not None else None
    t = w.t
    R['trace'][idx].append(dict(h=t % 24, op=op, arg=action[1] if isinstance(action, list) and len(action) > 1 else None,
                                pos=pos, pos2=pa, ib=ib, ia=ia, lab=lab, shed_b=sum(sb.values()),
                                shed_a=sum(private['shed'].values()),
                                dshed={kk: private['shed'].get(kk, 0) - sb.get(kk, 0)
                                       for kk in set(sb) | set(private['shed'])
                                       if private['shed'].get(kk, 0) != sb.get(kk, 0)}))
    return r


def commit(op, item, price, farm, private, market, shed_capacity=100):
    ok = _commit0(op, item, price, farm, private, market, shed_capacity)
    w = R['w']
    if ok and w is not None and farm is w.farms[R['seat']]:
        t = w.t
        R['mk'][(t, op, item)][0] += 1
        R['mk'][(t, op, item)][1] += float(price)
    return ok


def drop(private, cap):
    w = R['w']
    if w is None or private is not w.private(R['seat']):
        return _drop0(private, cap)
    per_unit = [{k: v for k, v in inv.items() if v > 0} for inv in private['inventories']]
    carried = Counter()
    for inv in per_unit:
        carried.update(inv)
    before = {k: v for k, v in private['shed'].items() if v > 0}
    _drop0(private, cap)
    lost = {k: v - (private['shed'].get(k, 0) - before.get(k, 0)) for k, v in carried.items()}
    R['night'] = dict(shed23=before, carried=dict(carried), per_unit=[sum(i.values()) for i in per_unit],
                      per_unit_inv=per_unit, lost={k: v for k, v in lost.items() if v > 0}, held=R.get('held', {}))
    return None


def refresh(farm, day):
    """Animal product still on the tiles at the end of the day, before tonight's production."""
    w = R['w']
    if w is not None and farm is w.farms[R['seat']]:
        held = Counter()
        for row in farm['tiles']:
            for x in row:
                if isinstance(x, dict) and x.get('animal') and x.get('yield_units', 0) > 0:
                    held[E.ANIMALS[x['animal']]['product']] += x['yield_units']
        R['held'] = dict(held)
    return _refresh0(farm, day)


E._apply_unit_action, E._commit_unit, E._drop_inventories_to_shed, E._daily_refresh_animals = ua, commit, drop, refresh


def _day_units(trace, day, mk):
    """Per-unit trips and drops of one day from the hook trace."""
    drops, units, harv = [], [], []
    sells_h = defaultdict(Counter)
    for (t, op, item), (n, _) in mk.items():
        if op == 'SELL' and t // 24 == day:
            sells_h[t % 24][item] += n
    for idx, steps in sorted(trace.items()):
        got, picked = Counter(), Counter()       # outstanding units by provenance
        fifo = defaultdict(list)                  # product -> [[harvest hour, units, pos], ...] still in hand

        def take(k, n, fate, fifo=fifo, idx=idx):
            q = fifo[k]
            while n > 0 and q:
                m = min(n, q[0][1])
                harv.append((day, idx, k, q[0][0], m, fate, q[0][2]))
                q[0][1] -= m
                n -= m
                if q[0][1] == 0:
                    q.pop(0)
        trip_start, trip_ops, trip_got = None, 0, Counter()
        first_h = steps[0]['h'] if steps else None
        info = dict(unit=idx, first_h=first_h, work=0, harvested=0, drops=0, left_shed_hours=[], end_pos=None,
                    end_inv=0, trips=0)
        for i, s in enumerate(steps):
            op = s['op']
            ib, ia = Counter(s['ib']), Counter(s['ia'])
            at_shed = s['pos'] in ACCESS
            if s['pos2'] not in ACCESS and trip_start is None:
                trip_start, trip_ops, trip_got = s['h'], 0, Counter()
                info['trips'] += 1
            gained = ia - ib
            lostinv = ib - ia
            if op in WORK:
                info['work'] += 1
                trip_ops += 1
            if op == 'PICKUP':
                picked.update(gained)
            elif op in ('HARVEST', 'COLLECT_FERTILIZER'):
                got.update(gained)
                for k, v in gained.items():
                    fifo[k].append([s['h'], v, s['pos']])
                trip_got.update(gained)
                info['harvested'] += sum(gained.values())
            elif op in ('DROP', 'PLACE') and at_shed and sum(lostinv.values()) > 0:
                delivered = Counter({k: v for k, v in lostinv.items() if k in PROD})
                to_shed = Counter({k: v for k, v in s['dshed'].items() if v > 0})
                produce, putback = Counter(), Counter()
                for k, v in delivered.items():
                    pb = min(v, picked[k])
                    putback[k] += pb
                    picked[k] -= pb
                    pr = min(v - pb, got[k])
                    produce[k] += pr
                    got[k] -= pr
                    take(k, pr, s['h'])
                later = steps[i + 1:]
                later_work = sum(1 for x in later if x['op'] in WORK)
                left_again = any(x['pos2'] not in ACCESS for x in later)
                later_harv = sum(sum((Counter(x['ia']) - Counter(x['ib'])).values()) for x in later
                                 if x['op'] in ('HARVEST', 'COLLECT_FERTILIZER'))
                visit = []
                for x in later:                   # what the unit does during this shed visit
                    if x['pos'] not in ACCESS:
                        break
                    if x['op'] == 'PICKUP':
                        visit.append(('PICKUP', x['arg'], sum((Counter(x['ia']) - Counter(x['ib'])).values())))
                    elif x['op'] not in ('PASS',) and x['op'] not in E.FARMER_MOVES:
                        visit.append((x['op'], x['arg'], 0))
                prev = next((x for x in reversed(steps[:i]) if x['op'] in WORK), None)
                nxt = next((x for x in later if x['op'] in WORK), None)
                drops.append(dict(day=day, h=s['h'], unit=idx, op=op, delivered=dict(delivered), at=s['pos'], visit=visit,
                                  prev=(prev['h'], prev['pos'], prev['op'], prev['lab']) if prev else None,
                                  nxt=(nxt['h'], nxt['pos'], nxt['op'], nxt['lab']) if nxt else None,
                                  keep=dict(ia), trip_labs=Counter(x['lab'] for x in steps[:i] if x['op'] == 'HARVEST'
                                                                   and (trip_start is None or x['h'] >= trip_start)),
                                  produce=dict(+produce), putback=dict(+putback),
                                  lost_at_drop={k: v - to_shed.get(k, 0) for k, v in delivered.items()
                                                if v - to_shed.get(k, 0) > 0},
                                  inv_before=sum(ib.values()), shed_before=s['shed_b'],
                                  sold_same_h=dict(sells_h.get(s['h'], {})), trip_start=trip_start,
                                  trip_ops=trip_ops, trip_got=dict(trip_got), later_work=later_work,
                                  left_again=left_again, later_harv=later_harv, first_h=first_h))
                info['drops'] += 1
                trip_start = None
            else:
                # consumption (FEED / FERTILIZE / PLANT): draw from picked first, then from own produce
                for k, v in lostinv.items():
                    a = min(v, picked[k])
                    picked[k] -= a
                    b = min(v - a, got[k])
                    got[k] -= b
                    take(k, b, -1)
            if s['pos2'] in ACCESS and s['pos'] not in ACCESS:
                info['left_shed_hours'].append(s['h'])
        for k in list(fifo):
            take(k, 10 ** 6, 24)
        if steps:
            info['end_pos'] = steps[-1]['pos2']
            info['end_inv'] = sum(steps[-1]['ia'].values())
            info['end_at_shed'] = steps[-1]['pos2'] in ACCESS
        units.append(info)
    return drops, units, harv


def run(tape, stream=None):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    R.update(w=w, seat=seat, mk=defaultdict(lambda: [0, 0.0]), trace=defaultdict(list), night=None)
    nights, drops, units, quotes, shed_h, harvests = [], [], [], [], [], []
    while w.t < 720:
        t = w.t
        mkt = w.market
        quotes.append([round(E.market_price(p, mkt['inventory'][p], mkt.get('params')), 2) for p in PROD])
        shed_h.append(sum(w.private(seat)['shed'].values()))
        if stream is None or t < 264:
            own = UE.tape_action(tape['actions'], t)
        else:
            a = stream[t] if t < len(stream) else {}
            own = a if isinstance(a, dict) and a else dict(UE.PASS)
        acts = [None, None]
        acts[seat], acts[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(acts)
        if t % 24 == 23:
            day = t // 24
            d, u, hv = _day_units(R['trace'], day, R['mk'])
            harvests += hv
            drops += d
            units.append(dict(day=day, units=u))
            n = R['night'] or {}
            n['day'] = day
            nights.append(n)
            R['trace'], R['night'] = defaultdict(list), None
    mk = [dict(t=t, op=op, item=item, n=v[0], rev=round(v[1], 2)) for (t, op, item), v in sorted(R['mk'].items())]
    money = [float(w.farms[i]['money']) for i in range(2)]
    R['w'] = None
    return dict(seat=seat, money=money, nights=nights, drops=drops, units=units, market=mk, quotes=quotes,
                shed_h=shed_h, harv=harvests)


def job(args):
    mode, team, ep, arm = args
    tape = UE.load_tape(int(team), int(ep))
    stream = None
    if mode == 'arm':
        s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm}_streams' / f'{ep}.json').read_text(encoding='utf-8'))
        stream = s['actions']
    r = run(tape, stream)
    r.update(team=str(team), ep=int(ep), arm=arm or 'leader', rewards=tape['rewards'],
             names=tape.get('names'), shops=tape['shops'])
    if mode == 'leader':
        r['cash_match'] = [round(x) for x in r['money']] == [round(float(x)) for x in tape['rewards']]
    return r


def main():
    a = sys.argv[1:]
    nw = int(a[a.index('--workers') + 1]) if '--workers' in a else 1
    if a[0] == 'leaders':
        out = a[1]
        teams = a[a.index('--teams') + 1].split(',') if '--teams' in a else None
        mx = int(a[a.index('--max-per-team') + 1]) if '--max-per-team' in a else 10 ** 9
        jobs = []
        for d in sorted(UE.TAPES.glob('1*_*')):
            team = d.name.split('_')[0]
            if teams and team not in teams:
                continue
            eps = sorted(p.name.split('.')[0] for p in d.glob('*.json.gz'))[:mx]
            jobs += [('leader', team, ep, None) for ep in eps]
        seen, uniq = set(), []
        for j in jobs:                      # an episode can sit in two submission folders of one team
            if (j[1], j[2]) not in seen:
                seen.add((j[1], j[2]))
                uniq.append(j)
        jobs = uniq
    else:
        arm, games, out = a[1], a[2], a[3]
        p = Path(games)
        games = p.read_text().replace(',', ' ').split() if p.exists() else games.split(',')
        jobs = [('arm', g.split(':')[0], g.split(':')[1], arm) for g in games]
    n = 0
    with gzip.open(out, 'wt', encoding='utf-8') as f, Pool(nw) as pool:
        for r in pool.imap_unordered(job, jobs, chunksize=2):
            f.write(json.dumps(r, default=list) + '\n')
            n += 1
            if n % 25 == 0:
                print('done', n, '/', len(jobs), flush=True)
    print('done', n, flush=True)


if __name__ == '__main__':
    main()
