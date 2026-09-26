"""Animal economics, leader vs an arm, days 11-29, same world: per animal kind, harvests (units, whether needed: tonight's
production would overflow max_held), production (units made, units lost to the cap, bank realised), feed / care rates on
production days vs other days, escapes.
usage: season_animals.py <arm> <panel file | team:ep,...> <out.json> [--workers 4]"""
import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
AN = E.ANIMALS
REC = {'w': None, 'seat': 0, 'on': False, 'C': None, 'day': 0}
_ua, _refresh = E._apply_unit_action, E._daily_refresh_animals


def prod_tonight(t, day):
    a = AN[t['animal']]
    ds = day + 1 - t['placed_day'] - a['first_yield_day']
    return ds >= 0 and ds % a['interval'] == 0


def ua(farm, private, idx, action, *a, **k):
    w = REC['w']
    if not (w is not None and REC['on'] and isinstance(action, list) and action and action[0] == 'HARVEST'
            and farm is w.farms[REC['seat']]):
        return _ua(farm, private, idx, action, *a, **k)
    pos = E._farmer_position(farm, idx)
    t = farm['tiles'][pos[1]][pos[0]] if pos else None
    if not (isinstance(t, dict) and 'animal' in t and t.get('yield_units', 0) > 0):
        return _ua(farm, private, idx, action, *a, **k)
    an, y, day = t['animal'], t['yield_units'], REC['day']
    exp = 1 + (t.get('pending_care_bonus', 0) or 0)          # tonight's production if fed
    needed = prod_tonight(t, day) and y + exp > AN[an]['max_held']
    r = _ua(farm, private, idx, action, *a, **k)
    C = REC['C']
    C[f'{an}|harvests'] += 1
    C[f'{an}|harvest_units'] += y
    C[f'{an}|harvest_needed'] += needed
    C[f'{an}|harvest_u{y}'] += 1
    return r


def refresh(farm, day):
    w = REC['w']
    if not (w is not None and REC['on'] and farm is w.farms[REC['seat']]):
        return _refresh(farm, day)
    C = REC['C']
    pre = {}
    for y, row in enumerate(farm['tiles']):
        for x, t in enumerate(row):
            if isinstance(t, dict) and 'animal' in t:
                an = t['animal']
                p = prod_tonight(t, day)
                C[f'{an}|days'] += 1
                C[f'{an}|fed'] += bool(t['fed_today'])
                C[f'{an}|cared'] += bool(t['cared_today'])
                C[f'{an}|fed_cared'] += bool(t['fed_today'] and t['cared_today'])
                if p:
                    C[f'{an}|prod_days'] += 1
                    C[f'{an}|prod_days_fed'] += bool(t['fed_today'])
                    bank = t.get('pending_care_bonus', 0) or 0
                    made = 1 + (bank if t['fed_today'] else 0)
                    C[f'{an}|made'] += made
                    C[f'{an}|bank_lost'] += 0 if t['fed_today'] else bank
                    C[f'{an}|cap_lost'] += max(0, t['yield_units'] + made - AN[an]['max_held'])
                pre[(x, y)] = an
    r = _refresh(farm, day)
    for (x, y), an in pre.items():
        t = farm['tiles'][y][x]
        if not (isinstance(t, dict) and 'animal' in t):
            C[f'{an}|escaped'] += 1
    return r


E._apply_unit_action, E._daily_refresh_animals = ua, refresh


def run(tape, stream):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    C = Counter()
    REC.update(w=w, seat=seat, C=C, on=False)
    while w.t < 720:
        t = w.t
        REC['on'] = t >= 264
        REC['day'] = t // 24
        if stream is None or t < 264:
            own = UE.tape_action(tape['actions'], t)
        else:
            a = stream[t] if t < len(stream) else {}
            own = a if isinstance(a, dict) and a else dict(UE.PASS)
        acts = [None, None]
        acts[seat], acts[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(acts)
    REC['w'] = None
    return dict(C)


def job(args):
    g, arm = args
    team, ep = g.split(':')
    tape = UE.load_tape(int(team), int(ep))
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))
    return ep, {'leader': run(tape, None), arm: run(tape, s['actions'])}


def summary(res, arm):
    n = len(res)
    for side in ('leader', arm):
        C = Counter()
        for r in res.values():
            C.update(r[side])
        print(f'\n{side} ({n} worlds, per world)')
        for an in ('GOOSE', 'COW', 'SHEEP'):
            g = lambda k: C.get(f'{an}|{k}', 0)
            d = max(1, g('days'))
            pd = max(1, g('prod_days'))
            h = max(1, g('harvests'))
            dist = {u: round(g(f'harvest_u{u}') / h, 2) for u in range(1, 7) if g(f'harvest_u{u}')}
            print(f'  {an:5s} animal-days {g("days")/n:5.0f} | fed {g("fed")/d:.0%} cared {g("cared")/d:.0%} both {g("fed_cared")/d:.0%}'
                  f' | production days {g("prod_days")/n:4.0f}, fed {g("prod_days_fed")/pd:.0%}; made {g("made")/n:5.1f}'
                  f' ({g("made")/pd:.2f}/production), bank lost {g("bank_lost")/n:4.1f}, cap lost {g("cap_lost")/n:4.1f}, escaped {g("escaped")/n:.2f}')
            print(f'        harvests {g("harvests")/n:5.1f}, {g("harvest_units")/h:.2f} units each, needed {g("harvest_needed")/h:.0%}; units dist {dist}')


if __name__ == '__main__':
    arm, games, out = sys.argv[1], sys.argv[2], sys.argv[3]
    if games == '--report':
        summary(json.load(open(out)), arm)
        sys.exit()
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    p = Path(games)
    games = p.read_text().replace(',', ' ').split() if p.exists() else games.split(',')
    res = {}
    with Pool(nw) as pool:
        for ep, r in pool.imap_unordered(job, [(g, arm) for g in games]):
            res[ep] = r
    json.dump(res, open(out, 'w'))
    summary(res, arm)
