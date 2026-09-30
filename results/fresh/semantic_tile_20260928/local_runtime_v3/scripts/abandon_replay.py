"""Abandonment research (2026-09-26): full-season replays that record every animal's daily life, every trade unit of
both players (price and the market inventory it was priced at) and the market inventory at the start of every step.

Sides: LEADER = the leader's recorded tape for all 720 steps; any arm name (KS1, KC8, ...) = the arm's action stream
results/fresh/day12_viz/<arm lowercase>_streams/<ep>.json (leader tape for steps < 264). The rival always replays
its recorded opp_actions. Engine = scripts/upkeep_engine.py (official 1.32.7 interpreter, forced shops).

Recorded per game (results/fresh/abandon_20260926/replay/<side>/<ep>.json):
  seat, money[step d*24] for d = 0..30 (both seats, [ours, rival]), final money,
  inv[step] = market inventory of every product at the START of the step (before actions),
  trades = [step, who (0 ours / 1 rival), op, item, price, inventory before the unit] for every committed unit,
  animals = {key: {...}} for BOTH seats, key 'seat,x,y,placed_day,ANIMAL':
      nights: [day, fed, cared, bank_before, yield_before, prod_tonight, made, escaped]
      acts:   [step, cmd, units]   (effective FEED / CARE / HARVEST / COLLECT_FERTILIZER only)
      dawn:   [day, consecutive_unfed, bank, yield, fertilizer_available]  (state at hour 0)
usage: abandon_replay.py <side,...> <panel file | team:ep,...> [--workers 2]
"""
import json
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

OUT = ROOT / 'results/fresh/abandon_20260926/replay'
E = UE.engine()
AN = E.ANIMALS
PRODUCTS = E.PRODUCTS
REC = {'w': None, 'on': False, 'R': None}
_ua, _refresh, _commit = E._apply_unit_action, E._daily_refresh_animals, E._commit_unit


def _who(farm):
    w = REC['w']
    if w is None:
        return None
    fs = w.farms
    return 0 if farm is fs[REC['seat']] else 1 if farm is fs[1 - REC['seat']] else None


def _key(who, x, y, t):
    return '%d,%d,%d,%d,%s' % (who, x, y, int(t['placed_day']), t['animal'])


def _arec(key):
    A = REC['R']['animals']
    r = A.get(key)
    if r is None:
        r = A[key] = {'nights': [], 'acts': [], 'dawn': []}
    return r


def prod_tonight(t, day):
    a = AN[t['animal']]
    ds = day + 1 - t['placed_day'] - a['first_yield_day']
    return ds >= 0 and ds % a['interval'] == 0


def ua(farm, private, idx, action, board_size, day, *a, **k):
    if not (REC['on'] and isinstance(action, list) and action
            and action[0] in ('FEED', 'CARE', 'HARVEST', 'COLLECT_FERTILIZER')):
        return _ua(farm, private, idx, action, board_size, day, *a, **k)
    who = _who(farm)
    pos = E._farmer_position(farm, idx)
    t = farm['tiles'][pos[1]][pos[0]] if (pos and who is not None) else None
    if not (isinstance(t, dict) and 'animal' in t):
        return _ua(farm, private, idx, action, board_size, day, *a, **k)
    before = (bool(t['fed_today']), bool(t['cared_today']), int(t['yield_units']), bool(t['fertilizer_available']))
    key = _key(who, pos[0], pos[1], t)
    r = _ua(farm, private, idx, action, board_size, day, *a, **k)
    cmd = action[0]
    units = 0
    eff = False
    if cmd == 'FEED':
        eff = (not before[0]) and t['fed_today']
    elif cmd == 'CARE':
        eff = (not before[1]) and t['cared_today']
    elif cmd == 'HARVEST':
        units = before[2] - int(t['yield_units'])
        eff = units > 0
    elif cmd == 'COLLECT_FERTILIZER':
        eff = before[3] and not t['fertilizer_available']
    if eff:
        _arec(key)['acts'].append([REC['step'], cmd, units])
    return r


def refresh(farm, day):
    who = _who(farm)
    if not (REC['on'] and who is not None):
        return _refresh(farm, day)
    pre = {}
    for y, row in enumerate(farm['tiles']):
        for x, t in enumerate(row):
            if isinstance(t, dict) and 'animal' in t:
                p = prod_tonight(t, day)
                bank = int(t.get('pending_care_bonus', 0) or 0)
                made = (1 + (bank if t['fed_today'] else 0)) if p else 0
                # escapes before production when this is the second unfed day in a row
                if (not t['fed_today']) and int(t['consecutive_unfed']) + 1 >= 2:
                    made = 0
                pre[(x, y)] = (_key(who, x, y, t), [day, int(bool(t['fed_today'])), int(bool(t['cared_today'])), bank,
                                                     int(t['yield_units']), int(p), made])
    r = _refresh(farm, day)
    for (x, y), (key, row) in pre.items():
        t = farm['tiles'][y][x]
        esc = not (isinstance(t, dict) and 'animal' in t)
        _arec(key)['nights'].append(row + [int(esc)])
    return r


def commit(op, item, price, farm, private, market, *a, **k):
    inv0 = market['inventory'].get(item) if isinstance(market.get('inventory'), dict) else None
    ok = _commit(op, item, price, farm, private, market, *a, **k)
    if ok and REC['on'] and op in ('SELL', 'BUY_PRODUCT', 'BUY_ANIMAL'):
        who = _who(farm)
        if who is not None:
            REC['R']['trades'].append([REC['step'], who, op, item, int(price), inv0])
    return ok


E._apply_unit_action, E._daily_refresh_animals, E._commit_unit = ua, refresh, commit


def run(tape, stream):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    R = {'seat': seat, 'money': {}, 'inv': [], 'trades': [], 'animals': {}}
    REC.update(w=w, seat=seat, R=R, on=True)
    while w.t < 719:                      # the framework never executes step 719 (DONE after 718)
        t = w.t
        REC['step'] = t
        inv = w.market['inventory']
        R['inv'].append([int(inv[p]) for p in PRODUCTS])
        if t % 24 == 0:
            fs = w.farms
            R['money'][t // 24] = [float(fs[seat]['money']), float(fs[1 - seat]['money'])]
            for who, s_ in ((0, seat), (1, 1 - seat)):
                for y, row in enumerate(fs[s_]['tiles']):
                    for x, tl in enumerate(row):
                        if isinstance(tl, dict) and 'animal' in tl:
                            _arec(_key(who, x, y, tl))['dawn'].append(
                                [t // 24, int(tl['consecutive_unfed']), int(tl.get('pending_care_bonus', 0) or 0),
                                 int(tl['yield_units']), int(bool(tl['fertilizer_available']))])
        if stream is None or t < 264:
            own = UE.tape_action(tape['actions'], t)
        else:
            a = stream[t] if t < len(stream) else {}
            own = a if isinstance(a, dict) and a else dict(UE.PASS)
        acts = [None, None]
        acts[seat], acts[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(acts)
    fs = w.farms
    R['money'][30] = [float(fs[seat]['money']), float(fs[1 - seat]['money'])]   # after step 718 (final)
    R['final'] = R['money'][30]
    R['products'] = PRODUCTS
    REC['w'] = None
    return R


def job(args):
    g, side = args
    team, ep = g.split(':')
    out = OUT / side / f'{ep}.json'
    if out.exists():
        return side, ep, 'cached'
    tape = UE.load_tape(int(team), int(ep))
    stream = None
    if side != 'LEADER':
        s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{side.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))
        stream = s['actions']
    R = run(tape, stream)
    R['game'], R['side'] = g, side
    if side == 'LEADER':
        R['check'] = [round(x) for x in R['final']] == [round(x) for x in (tape['rewards'][tape['seat']], tape['rewards'][1 - tape['seat']])]
    else:
        R['check'] = round(R['final'][0]) == round(s['cash'][-1])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(R, separators=(',', ':')), encoding='utf-8')
    return side, ep, R['check']


if __name__ == '__main__':
    sides, games = sys.argv[1].split(','), sys.argv[2]
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    p = Path(games)
    games = p.read_text().replace(',', ' ').split() if p.exists() else games.split(',')
    jobs = [(g, s) for s in sides for g in games]
    if nw <= 1:
        for j in jobs:
            print(*job(j), flush=True)
    else:
        with Pool(nw) as pool:
            for r in pool.imap_unordered(job, jobs):
                print(*r, flush=True)
