"""Animal production diagnosis (thread "animal", 2026-09-28): leader tape vs our season stream in the same world.

For each player (the leader's own game, then each arm's stream: leader tape for t < 264, the arm for 264..719) the engine
is replayed with hooks and every animal-day of OUR farm from day 11 on is recorded at the day end (before / after the
engine's _daily_refresh_animals): species, fed, cared, production night, bank before, units produced (capped) and the
uncapped units (lost to max_held), a bank wiped by an unfed production day, escapes; harvests (hour, units) and feeds /
cares / collects (hour) from the unit actions; midnight shed deletions by product; SELL units / revenue by product and
BUY_ANIMAL by species (both sides).

usage: animal_diag.py <team:ep> <arm,...>  (arm = stream dir name, e.g. k5b)  -> JSON on stdout
       animal_diag.py --summary <team:ep> <arm,...>   (a short table instead of JSON)
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
D0 = 11
PROD = {'GOOSE': 'EGG', 'COW': 'MILK', 'SHEEP': 'WOOL'}
REC = {'w': None, 'seat': 0, 't': 0}
_orig_refresh = E._daily_refresh_animals
_orig_apply = E._apply_unit_action
_orig_drop = E._drop_inventories_to_shed
_orig_commit = E._commit_unit


def _animals(farm):
    out = {}
    for y, row in enumerate(farm['tiles']):
        for x, t in enumerate(row):
            if isinstance(t, dict) and 'animal' in t:
                out[y * 10 + x] = t
    return out


def _refresh(farm, day):
    w = REC['w']
    if w is None or farm is not w.farms[REC['seat']] or day < D0:
        return _orig_refresh(farm, day)
    before = {}
    for i, t in _animals(farm).items():
        a = E.ANIMALS[t['animal']]
        dsf = day + 1 - t['placed_day'] - a['first_yield_day']
        prod = dsf >= 0 and dsf % a['interval'] == 0
        bank = int(t.get('pending_care_bonus', 0) or 0)
        unc = (1 + (bank if t['fed_today'] else 0)) if prod else 0
        before[i] = dict(sp=t['animal'], placed=t['placed_day'], fed=bool(t['fed_today']), cared=bool(t['cared_today']),
                         prod=prod, bank=bank, y0=int(t['yield_units']), unc=unc,
                         unfed_prev=int(t['consecutive_unfed']), fert=bool(t.get('fertilizer_available')))
    _orig_refresh(farm, day)
    after = _animals(farm)
    for i, r in before.items():
        t = after.get(i)
        if t is None or t.get('animal') != r['sp'] or t.get('placed_day') != r['placed']:
            r['escaped'] = True
            r['got'] = 0
        else:
            r['escaped'] = False
            r['got'] = int(t['yield_units']) - r['y0']
        r['cap_loss'] = max(0, r['unc'] - r['got']) if not r['escaped'] else 0
        r['wipe'] = r['bank'] if (r['prod'] and not r['fed']) else 0
        REC['days'][day][i] = r


def _apply(farm, private, idx, action, board_size, day, turns_per_day, shed_capacity=100):
    w = REC['w']
    if w is None or farm is not w.farms[REC['seat']] or not isinstance(action, list) or not action \
            or action[0] not in ('FEED', 'CARE', 'HARVEST', 'COLLECT_FERTILIZER') or day < D0:
        return _orig_apply(farm, private, idx, action, board_size, day, turns_per_day, shed_capacity)
    pos = E._farmer_position(farm, idx)
    t = farm['tiles'][pos[1]][pos[0]] if pos is not None else None
    if not (isinstance(t, dict) and 'animal' in t):
        if action[0] == 'HARVEST' and isinstance(t, dict) and t.get('kind') == 'PLANT':
            crop, y0 = t['crop'], int(t.get('yield_units', 0) or 0)
            _orig_apply(farm, private, idx, action, board_size, day, turns_per_day, shed_capacity)
            t2 = farm['tiles'][pos[1]][pos[0]]
            if y0 > 0 and (t2 is None or int(t2.get('yield_units', 0) or 0) == 0):
                REC['pharv'][crop] += y0
            return
        return _orig_apply(farm, private, idx, action, board_size, day, turns_per_day, shed_capacity)
    snap = (t['fed_today'], t['cared_today'], int(t['yield_units']), t.get('fertilizer_available'))
    _orig_apply(farm, private, idx, action, board_size, day, turns_per_day, shed_capacity)
    op = action[0]
    hour = REC['t'] % 24
    i = pos[1] * 10 + pos[0]
    if op == 'FEED' and not snap[0] and t['fed_today']:
        REC['ops'][day][i].append(('F', hour))
    elif op == 'CARE' and not snap[1] and t['cared_today']:
        REC['ops'][day][i].append(('C', hour))
    elif op == 'HARVEST' and snap[2] > 0 and int(t['yield_units']) == 0:
        REC['ops'][day][i].append(('H', hour, snap[2]))
    elif op == 'COLLECT_FERTILIZER' and snap[3] and not t.get('fertilizer_available'):
        REC['ops'][day][i].append(('K', hour))


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
        day = REC['t'] // 24
        for k, v in carried.items():
            kept = private['shed'].get(k, 0) - before.get(k, 0)
            if v - kept > 0:
                REC['lost'][day][k] += v - kept
        return
    return _orig_drop(private, capacity)


def _commit(op, item, price, farm, private, market, shed_capacity=100):
    r = _orig_commit(op, item, price, farm, private, market, shed_capacity)
    w = REC['w']
    if r and w is not None and REC['t'] >= D0 * 24 and op in ('SELL', 'BUY_ANIMAL', 'BUY_PRODUCT'):
        side = 'us' if farm is w.farms[REC['seat']] else 'opp'
        k = (side, op, item)
        REC['mkt'][k][0] += 1
        REC['mkt'][k][1] += float(price)
    return r


E._daily_refresh_animals = _refresh
E._apply_unit_action = _apply
E._drop_inventories_to_shed = _drop
E._commit_unit = _commit


def run(tape, stream):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    REC.update(w=w, seat=seat, days=defaultdict(dict), ops=defaultdict(lambda: defaultdict(list)),
               lost=defaultdict(lambda: defaultdict(int)), mkt=defaultdict(lambda: [0, 0.0]), pharv=defaultdict(int), shed_am={})
    held_end = {}
    stock_end = {}
    while w.t < 720:
        t = w.t
        REC['t'] = t
        if stream is None or t < 264:
            own = UE.tape_action(tape['actions'], t)
        else:
            a = stream[t] if t < len(stream) else {}
            own = a if isinstance(a, dict) and a else dict(UE.PASS)
        if t % 24 == 0 and t >= D0 * 24:        # the shed each morning (before the day's first step)
            REC['shed_am'][t // 24] = {k_: v_ for k_, v_ in w.private(seat)['shed'].items() if v_}
        acts = [None, None]
        acts[seat], acts[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(acts)
        if t == 718:
            held_end = {i: (t_['animal'], int(t_['yield_units'])) for i, t_ in _animals(w.farms[seat]).items()}
            pv = w.private(seat)
            stock_end = dict(pv['shed'])
            for inv in pv['inventories']:
                for k_, v_ in inv.items():
                    stock_end[k_] = stock_end.get(k_, 0) + v_
    days = {d: dict(v) for d, v in REC['days'].items()}
    ops = {d: {i: list(v) for i, v in dv.items()} for d, dv in REC['ops'].items()}
    out = dict(final=[float(w.farms[seat]['money']), float(w.farms[1 - seat]['money'])], days=days, ops=ops,
               lost={d: dict(v) for d, v in REC['lost'].items()},
               mkt={'|'.join(k): v for k, v in REC['mkt'].items()}, held_end=held_end,
               pharv=dict(REC['pharv']), stock_end=stock_end, shed_am=dict(REC['shed_am']))
    REC['w'] = None
    return out


def summarize(r):
    """per species: animal-days, production nights, fed / cared shares, units produced, cap loss, bank wipes, escapes,
    harvested units, sold units / revenue, midnight deletions, units held at the end."""
    S = {}
    for sp, prod in PROD.items():
        ad = [x for d, dv in r['days'].items() for x in dv.values() if x['sp'] == sp and int(d) <= 28]
        pn = [x for x in ad if x['prod']]
        harv = sum(o[2] for d, dv in r['ops'].items() for i, v in dv.items() for o in v if o[0] == 'H'
                   and r['days'].get(d, {}).get(i, {}).get('sp', sp) == sp and _sp_of(r, d, i) == sp)
        sold = r['mkt'].get(f'us|SELL|{prod}', [0, 0.0])
        osold = r['mkt'].get(f'opp|SELL|{prod}', [0, 0.0])
        bought = r['mkt'].get(f'us|BUY_ANIMAL|{sp}', [0, 0.0])
        lost = sum(v.get(prod, 0) for v in r['lost'].values())
        S[sp] = dict(
            animal_days=len(ad), prod_nights=len(pn),
            fed=sum(x['fed'] for x in ad), cared=sum(x['cared'] for x in ad),
            fed_cared=sum(x['fed'] and x['cared'] for x in ad),
            prod_fed=sum(x['fed'] for x in pn), prod_unfed=sum(not x['fed'] for x in pn),
            units=sum(x['got'] for x in pn), units_unc=sum(x['unc'] for x in pn),
            cap_loss=sum(x['cap_loss'] for x in pn), wipe=sum(x['wipe'] for x in pn),
            bank_at_prod=sum(x['bank'] for x in pn),
            escaped=sum(x['escaped'] for x in ad), bought=bought[0],
            harvested=harv, sold=sold[0], revenue=round(sold[1]), avg=round(sold[1] / sold[0], 1) if sold[0] else 0,
            opp_sold=osold[0], opp_rev=round(osold[1]), deleted=lost,
            held_end=sum(v[1] for v in r['held_end'].values() if v[0] == sp))
    return S


def _sp_of(r, d, i):
    x = r['days'].get(d, {}).get(i)
    if x:
        return x['sp']
    return None


def main():
    args = sys.argv[1:]
    summary = False
    if args and args[0] == '--summary':
        summary, args = True, args[1:]
    game, arms = args[0], args[1].split(',')
    team, ep = game.split(':')
    tape = UE.load_tape(int(team), int(ep))
    res = {'leader': run(tape, None)}
    for arm in arms:
        s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm}_streams' / f'{ep}.json').read_text(encoding='utf-8'))
        res[arm] = run(tape, s['actions'])
    if not summary:
        json.dump(res, sys.stdout, default=str)
        return
    for who, r in res.items():
        print(f'== {game} {who} final {r["final"]}')
        for sp, v in summarize(r).items():
            print('  %-5s' % sp, ' '.join(f'{k}={v_}' for k, v_ in v.items()))


if __name__ == '__main__':
    main()
