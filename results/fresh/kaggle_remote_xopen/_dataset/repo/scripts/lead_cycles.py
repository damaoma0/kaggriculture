"""Crop cycles of an agent in ladder-panel worlds, from its own observations (no engine hooks): per tile the plantings,
harvests (units, crop age), deaths, and day-start crop counts. Then per crop: plantings, harvested units, units per
planting, harvest age vs full-yield age, cycle length per tile (planting -> next planting on the same tile), tile-days.

usage: lead_cycles.py run <agent>[,<agent>...] <episodes|smoke> [submission=p2750]    -> results/fresh/lead_cycles/<agent>/<ep>.json
       lead_cycles.py report <agent>[,<agent>...]
       lead_cycles.py quad <agent>[,<agent>...]       per-quadrant land use / harvests / labour (records with 'boards')
env:   (runs serially: ~16 s a game on Kaggle)
       LC_IDLE=1 (or --idle)   also switch on the executor's passive idle trace (CFG idle_trace) -> <agent>/idle/<ep>/
       LC_OUT=dir     output root (default results/fresh/lead_cycles)
Per record (2026-09-25 additions, all passive reads of the agent's own observations / returned actions): 'boards'
(day-start 100 two-char labels per day), 'aevents' (animal harvests per tile), 'hands' / 'money' / 'unlocked' per day,
'work' (per day, per quadrant: unit-steps by kind; moves are charged to the quadrant of the unit's next tile op),
'panel' (the full ladder_panel result), 'agent_log' (executor S.log, deploy _DEP.log / picks / land_day).
"""
import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import os as _os
OUT = ROOT / _os.environ.get('LC_OUT', 'results/fresh/lead_cycles')
MAXDAY = {'WHEAT': 4, 'CARROT': 3, 'MELON': 10, 'TOMATO': 8, 'STRAWBERRY': 10}   # full-yield age (melon: 6 at age 10)
ONETIME = {'WHEAT', 'CARROT', 'MELON'}
TILE_OPS = {'WATER', 'FEED', 'CARE', 'HARVEST', 'FERTILIZE', 'COLLECT_FERTILIZER', 'PLANT', 'DIG', 'BUILD_COOP',
            'BUILD_PASTURE'}
MOVE_CMDS = {'NORTH', 'SOUTH', 'EAST', 'WEST'}
SPECIES = {'GOOSE', 'COW', 'SHEEP'}


def quad(idx):
    x, y = idx % 10, idx // 10
    return ('N' if y < 5 else 'S') + ('W' if x < 5 else 'E')


def tile_label(t):
    """two-char label as in data/leader_semantics boards, except weeds are 'we' and empty structures are title-case."""
    if t == 'LOCKED':
        return ' L'
    if t is None:
        return ' .'
    k = t.get('kind')
    if k == 'PLANT':
        return str(t.get('crop'))[:2]
    if k == 'WEED':
        return 'we'
    if t.get('animal'):
        return str(t['animal'])[:2].lower()
    return str(k)[:2].title()        # empty structure: 'Co' / 'Pa' (never confused with a cow 'co')


def _charge_day(units, work):
    """units: {u: [(idx_of_position, cmd, arg)]} of one day -> work[quad][kind] += unit-steps; moves are charged to the
    quadrant of that unit's next tile op ('walk'), or to 'shed' when the next non-move is a shed op."""
    for seq in units.values():
        pend = 0
        for idx, cmd, arg in seq:
            if cmd in MOVE_CMDS:
                pend += 1
                continue
            if cmd in TILE_OPS or (cmd == 'PLACE' and arg in SPECIES):
                q = quad(idx)
                work[q]['walk'] = work[q].get('walk', 0) + pend
                work[q]['op_' + cmd] = work[q].get('op_' + cmd, 0) + 1
                pend = 0
            elif cmd in ('PICKUP', 'DROP', 'PLACE'):
                work['shed']['walk'] = work['shed'].get('walk', 0) + pend
                work['shed']['op_' + cmd] = work['shed'].get('op_' + cmd, 0) + 1
                pend = 0
            else:                                           # PASS / other: count, keep pending moves
                work['other'][cmd] = work['other'].get(cmd, 0) + 1
        if pend:
            work['other']['walk_unattributed'] = work['other'].get('walk_unattributed', 0) + pend


def run(agent, eps, sub):
    for ep in eps:
        run_one(agent, ep, sub)


def recorder():
    """-> (rec, make, close): make(entry) wraps an agent callable so that every call records the observation
    (tile events, day-start states, labour); close() closes the last day's labour account after the game."""
    rec = dict(events=[], counts=[])
    prev = {}
    rec.update(boards=[], aevents=[], hands=[], money=[], unlocked=[], work=[])
    daybuf = {'day': 0, 'units': {}, 'hmax': 0}

    def snap(t):
        if not isinstance(t, dict) or t.get('kind') != 'PLANT':
            return ('WEED',) if isinstance(t, dict) and t.get('kind') == 'WEED' else None
        return ('PLANT', t['crop'], t['planted_day'], t.get('yield_units', 0))

    rec['states'] = []      # per day start: {idx: [crop, planted_day, consecutive_unwatered, fertilized_until_day, yield]}
    aprev = {}


    def make(entry):
        def wrapped(obs, *a, **k):
            step = int(obs['step'])
            me = int(obs['player'])
            tiles = obs['farms'][me]['tiles']
            cur = {}
            for y, row in enumerate(tiles):
                for x, t in enumerate(row):
                    cur[y * 10 + x] = snap(t)
            farm_ = obs['farms'][me]
            if step // 24 != daybuf['day']:                     # day boundary: close the previous day's account
                wk = {'NW': {}, 'NE': {}, 'SW': {}, 'SE': {}, 'shed': {}, 'other': {}}
                _charge_day(daybuf['units'], wk)
                rec['work'].append(wk)
                rec['hands'].append(daybuf['hmax'])
                daybuf.update(day=step // 24, units={}, hmax=0)
            daybuf['hmax'] = max(daybuf['hmax'], len(farm_.get('hands') or []))
            if step % 24 == 0:
                rec['boards'].append(''.join(tile_label(t_) for row_ in tiles for t_ in row_))
                rec['money'].append(farm_.get('money'))
                rec['unlocked'].append(sorted(farm_.get('unlocked_quadrants') or []))
                rec['counts'].append(dict(Counter(v[1] for v in cur.values() if v and v[0] == 'PLANT')))
                stt = {}
                for y_, row_ in enumerate(tiles):
                    for x_, t_ in enumerate(row_):
                        if isinstance(t_, dict) and t_.get('kind') == 'PLANT':
                            stt[y_ * 10 + x_] = [t_['crop'], t_['planted_day'], t_.get('consecutive_unwatered', 0),
                                                 t_.get('fertilized_until_day', -1), t_.get('yield_units', 0)]
                rec['states'].append(stt)
                ast = {}                   # per day start: {idx: [animal, placed_day, consecutive_unfed, bonus, yield]}
                for y_, row_ in enumerate(tiles):
                    for x_, t_ in enumerate(row_):
                        if isinstance(t_, dict) and t_.get('animal'):
                            ast[y_ * 10 + x_] = [t_['animal'], t_.get('placed_day'), t_.get('consecutive_unfed', 0),
                                                 t_.get('pending_care_bonus', 0), t_.get('yield_units', 0)]
                rec.setdefault('astates', []).append(ast)
                lab = Counter()
                for row_ in tiles:
                    for t_ in row_:
                        if t_ == 'LOCKED':
                            lab['LOCKED'] += 1
                        elif t_ is None:
                            lab['EMPTY'] += 1
                        elif t_.get('kind') == 'WEED':
                            lab['WEED'] += 1
                        elif t_.get('kind') == 'PLANT':
                            lab['CROP_' + t_['crop']] += 1
                        elif t_.get('animal'):
                            lab['ANIMAL'] += 1
                        else:
                            lab['STRUCT_EMPTY'] += 1
                rec.setdefault('land', []).append(dict(lab))
            # animal harvests (yield drops to 0 on a live animal tile)
            for y_, row_ in enumerate(tiles):
                for x_, t_ in enumerate(row_):
                    if isinstance(t_, dict) and t_.get('animal'):
                        i_ = y_ * 10 + x_
                        y1 = t_.get('yield_units', 0)
                        y0 = aprev.get(i_, (None, 0))
                        if y0[0] == t_['animal'] and y0[1] > 0 and y1 == 0 and step > 0:
                            rec.setdefault('animal_harvest', Counter())
                            rec['animal_harvest'][t_['animal']] += y0[1]
                            rec['aevents'].append((( step - 1) // 24, i_, t_['animal'], y0[1]))
                        aprev[i_] = (t_['animal'], y1)
            if prev:
                day = (step - 1) // 24
                for idx, v in cur.items():
                    p = prev.get(idx)
                    if v and v[0] == 'PLANT' and (not p or p[0] != 'PLANT' or p[2] != v[2] or p[1] != v[1]):
                        rec['events'].append(('plant', day, idx, v[1], v[2], 0))
                    if p and p[0] == 'PLANT':
                        crop, pd, y0 = p[1], p[2], p[3]
                        if v is None and y0 > 0:
                            rec['events'].append(('harvest', day, idx, crop, pd, y0))
                        elif v and v[0] == 'PLANT' and v[2] == pd and v[3] == 0 and y0 > 0:
                            rec['events'].append(('harvest', day, idx, crop, pd, y0))
                        elif v and v[0] == 'WEED':
                            rec['events'].append(('died', day, idx, crop, pd, y0))
            prev.clear()
            prev.update(cur)
            out_ = entry(obs, *a, **k)
            try:                                            # unit-steps: (position tile, command) per unit
                pos_ = [tuple(farm_['farmer'])] + [tuple(h_) for h_ in (farm_.get('hands') or [])]
                acts_ = [(out_ or {}).get('farmer') or ['PASS']] + list((out_ or {}).get('hands') or [])
                for u_, p_ in enumerate(pos_):
                    c_ = acts_[u_] if u_ < len(acts_) and acts_[u_] else ['PASS']
                    daybuf['units'].setdefault(u_, []).append(
                        (p_[1] * 10 + p_[0], str(c_[0]), str(c_[1]) if len(c_) > 1 else None))
            except Exception:
                rec['work_errors'] = rec.get('work_errors', 0) + 1
            return out_
        return wrapped

    def close():
        wk = {'NW': {}, 'NE': {}, 'SW': {}, 'SE': {}, 'shed': {}, 'other': {}}   # last day's account
        _charge_day(daybuf['units'], wk)
        rec['work'].append(wk)
        rec['hands'].append(daybuf['hmax'])
    return rec, make, close


def run_one(agent, ep, sub):
    import kaggle_environments.agent as KA
    import ladder_panel as LP
    orig = KA.get_last_callable
    if True:
        path = ROOT / f'data/ladder_panel/{sub}/{ep}.json.gz'
        rec, make, close = recorder()
        G = {}

        def patched(raw, path=None):
            inner = orig(raw, path=path)
            G.update(g=inner.__globals__)
            if _os.environ.get('LC_IDLE') and isinstance(inner.__globals__.get('CFG'), dict):
                inner.__globals__['CFG']['idle_trace'] = str(OUT / agent / 'idle' / str(ep))
            return make(inner)
        KA.get_last_callable = patched
        try:
            r = LP.run((agent, str(path)))
        finally:
            KA.get_last_callable = orig
        rec['final'] = r['final']
        rec['margin'] = r['margin']
        rec['sold'] = r['sold']
        close()
        g = G.get('g') or {}
        S_, D_, T_ = g.get('_S'), g.get('_DEP'), g.get('_T')
        num = lambda d_: {str(k_): v_ for k_, v_ in dict(d_ or {}).items() if isinstance(v_, (int, float))}
        rec['agent_log'] = dict(
            exec=num(S_.get('log')) if isinstance(S_, dict) else {},
            dep=num(D_.get('log')) if isinstance(D_, dict) else {},
            picks=list(D_.get('picks', [])) if isinstance(D_, dict) else [],
            land_day=dict(getattr(T_, 'land_day', {}) or {}),
            report=num(g.get('_MGT_REPORT')))
        # ladder_panel reads router / switches from the entry's globals, which here are this wrapper's: refill them
        r['router'] = num(g.get('_MGT_REPORT'))
        hist = [list(h) for h in (g.get('_MGT_HISTORY') or [])]
        r['switches'] = [h for i, h in enumerate(hist) if i == 0 or h[1] != hist[i - 1][1]]
        rec['panel'] = r
        o = OUT / agent
        o.mkdir(parents=True, exist_ok=True)
        (o / f'{ep}.json').write_text(json.dumps(rec), encoding='utf-8')
        print(agent, ep, r['margin'], flush=True)


def report(agents):
    for agent in agents:
        rows = [json.load(open(f)) for f in sorted((OUT / agent).glob('*.json'))]
        n = len(rows)
        if not n:
            continue
        plants, units, died = Counter(), Counter(), Counter()
        ages = defaultdict(list)
        cycles = defaultdict(list)
        tdays = Counter()
        for r in rows:
            last = {}
            for kind, day, idx, crop, pd, y in r['events']:
                if kind == 'plant':
                    plants[crop] += 1
                    if idx in last:
                        cycles[last[idx][1]].append(pd - last[idx][0])
                    last[idx] = (pd, crop)
                elif kind == 'harvest':
                    units[crop] += y
                    if crop in ONETIME:
                        ages[crop].append(day - pd - MAXDAY[crop])
                elif kind == 'died':
                    died[crop] += 1
            for c in r['counts']:
                tdays.update(c)
        print(f'\n{agent} ({n} worlds), per game:')
        print(f'{"crop":11s} {"plantings":>9s} {"harvested":>9s} {"units/plant":>11s} {"harvest age - full-yield age":>28s} {"cycle days":>10s} {"tile-days":>9s} {"died":>5s}')
        for crop in ('WHEAT', 'CARROT', 'STRAWBERRY', 'TOMATO', 'MELON'):
            a = ages[crop]
            cy = cycles[crop]
            upp = units[crop] / max(1, plants[crop])
            print(f'{crop:11s} {plants[crop] / n:9.1f} {units[crop] / n:9.1f} {upp:11.2f} '
                  f'{(st.mean(a) if a else 0):+14.2f} (n={len(a)/n:5.1f}) {(st.mean(cy) if cy else 0):10.2f} '
                  f'{tdays[crop] / n:9.0f} {died[crop] / n:5.1f}')


def fates(agents, crops=('CARROT', 'TOMATO', 'WHEAT', 'STRAWBERRY')):
    """per planting: fate, harvest age / units, water on each age (from next day's consecutive_unwatered == 0),
    fertilized ages (fertilized_until_day), for plantings whose day-start states were recorded."""
    for agent in agents:
        rows = [json.load(open(f)) for f in sorted((OUT / agent).glob('*.json'))]
        rows = [r for r in rows if r.get('states')]
        n = len(rows)
        if not n:
            print(agent, 'no state records'); continue
        print()
        print(f'{agent} ({n} worlds)')
        for crop in crops:
            P = []
            for r in rows:
                st_ = r['states']
                harv = {}
                died = {}
                for kind, day, idx, c, pd, y in r['events']:
                    if c != crop:
                        continue
                    if kind == 'harvest':
                        harv.setdefault((idx, pd), []).append((day, y))
                    elif kind == 'died':
                        died[(idx, pd)] = day
                for kind, day, idx, c, pd, y in r['events']:
                    if kind != 'plant' or c != crop:
                        continue
                    water, fert = [], []
                    for age in range(0, 20):
                        dd = pd + age + 1
                        if dd >= len(st_):
                            break
                        s1 = st_[dd].get(str(idx)) or st_[dd].get(idx)
                        if not s1 or s1[0] != crop or s1[1] != pd:
                            break
                        water.append(1 if s1[2] == 0 else 0)
                        fert.append(1 if s1[3] >= pd + age else 0)
                    h = harv.get((idx, pd), [])
                    P.append(dict(units=sum(y for _, y in h), hn=len(h), hage=(h[-1][0] - pd) if h else None,
                                  died=(died.get((idx, pd)) - pd) if (idx, pd) in died else None, water=water, fert=fert))
            if not P:
                continue
            k = len(P)
            har = [p for p in P if p['hn']]
            dead = [p for p in P if p['died'] is not None and not p['hn']]
            ages = Counter(p['hage'] for p in har)
            upp = sum(p['units'] for p in P) / k
            print(f'  {crop}: {k / n:.1f} plantings/game, units/planting {upp:.2f}; harvested {len(har)} ({len(har) / k:.0%}), '
                  f'died unharvested {len(dead)} ({len(dead) / k:.0%}) at ages {dict(Counter(p["died"] for p in dead))}, '
                  f'other {k - len(har) - len(dead)}')
            print(f'     harvest ages {dict(sorted(ages.items()))}; units by harvest age '
                  f'{ {a: round(st.mean(p["units"] for p in har if p["hage"] == a), 2) for a in sorted(ages)} }')
            for age in range(0, 12):
                w = [p['water'][age] for p in P if len(p['water']) > age]
                f = [p['fert'][age] for p in P if len(p['fert']) > age]
                if w:
                    print(f'     age {age:2d}: alive-next-day {len(w):4d}  watered {sum(w) / len(w):5.0%}  fertilized {sum(f) / len(f):5.0%}')


def land(agents):
    """per day window (from day 6): share of UNLOCKED tiles by use, and units harvested per unlocked tile-day."""
    wins = ((6, 11), (12, 17), (18, 23), (24, 29))
    base = {'WHEAT': 25, 'CARROT': 35, 'TOMATO': 60, 'STRAWBERRY': 120, 'MELON': 250, 'GOOSE': 50, 'COW': 160, 'SHEEP': 200}
    common = None
    for agent in agents:
        eps = {f.stem for f in (OUT / agent).glob('*.json') if json.load(open(f)).get('land')}
        common = eps if common is None else common & eps
    common = sorted(common or [])
    print(f'{len(common)} worlds with land records for all of {agents}')
    for agent in agents:
        rows = [json.load(open(OUT / agent / f'{e}.json')) for e in common]
        print(f'\n{agent}')
        keys = ['EMPTY', 'WEED', 'CROP_WHEAT', 'CROP_CARROT', 'CROP_TOMATO', 'CROP_STRAWBERRY', 'CROP_MELON', 'ANIMAL', 'STRUCT_EMPTY']
        print(f'{"days":8s} {"unlocked":>8s} ' + ' '.join(f'{k.replace("CROP_", "")[:7]:>7s}' for k in keys))
        for lo, hi in wins:
            acc = Counter()
            nd = 0
            for r in rows:
                for d in range(lo, min(hi + 1, len(r['land']))):
                    L = r['land'][d]
                    unl = 100 - L.get('LOCKED', 0)
                    acc['unlocked'] += unl
                    for k in keys:
                        acc[k] += L.get(k, 0)
                    nd += 1
            u = acc['unlocked']
            print(f'{lo:2d}-{hi:2d}    {u / max(1, nd):8.1f} ' + ' '.join(f'{100 * acc[k] / max(1, u):6.1f}%' for k in keys))
        # units harvested per unlocked tile-day (days 6-29)
        units = Counter()
        tdays = 0
        for r in rows:
            for kind, day, idx, crop, pd, y in r['events']:
                if kind == 'harvest' and day >= 6:
                    units[crop] += y
            for a, v in (r.get('animal_harvest') or {}).items():
                units[a] += v           # whole game (animal products; the few before day 6 included)
            for d in range(6, len(r['land'])):
                tdays += 100 - r['land'][d].get('LOCKED', 0)
        tot = sum(units.values())
        val = sum(units[k] * base.get(k, 0) for k in units)
        print(f'   units harvested per unlocked tile-day (days 6-29): {tot / max(1, tdays):.3f}  '
              f'(base-price value {val / max(1, tdays):.1f}/tile-day; units per game {tot / len(rows):.0f}: '
              + ', '.join(f'{k.lower()} {v / len(rows):.0f}' for k, v in units.most_common()) + ')')


def quad_report(agents):
    """per quadrant: tile-days by use per day window, plantings / harvested units / deaths by crop, animal output,
    labour unit-steps (tile ops + the walking charged to them). Records with 'boards' only."""
    wins = ((0, 11), (12, 17), (18, 23), (24, 29))
    common = None
    for agent in agents:
        eps = {f.stem for f in (OUT / agent).glob('*.json') if json.load(open(f)).get('boards')}
        common = eps if common is None else common & eps
    common = sorted(common or [])
    print(f'{len(common)} worlds with per-tile records for all of {agents}')
    for agent in agents:
        rows = [json.load(open(OUT / agent / f'{e}.json')) for e in common]
        n = max(1, len(rows))
        print(f'\n== {agent}')
        for q in ('NW', 'NE', 'SW', 'SE'):
            use = {w: Counter() for w in wins}
            for r in rows:
                for d, b in enumerate(r['boards']):
                    labs = [b[i:i + 2] for i in range(0, 200, 2)]
                    for w in wins:
                        if w[0] <= d <= w[1]:
                            use[w].update(labs[i] for i in range(100) if quad(i) == q)
            ev = Counter()
            for r in rows:
                for kind, day, idx, crop, pd, y in r['events']:
                    if quad(idx) == q:
                        ev[(kind, crop)] += (y if kind == 'harvest' else 1)
                for day, idx, an, u in r.get('aevents', []):
                    if quad(idx) == q:
                        ev[('aharv', an)] += u
            wk = Counter()
            for r in rows:
                for day_w in r.get('work', []):
                    for k, v in day_w.get(q, {}).items():
                        wk[k] += v
            print(f'  {q}: tile-days per game by window: ' + ' | '.join(
                f'{w[0]}-{w[1]}: ' + ', '.join(f'{k.strip() or "?"} {v / n:.0f}' for k, v in use[w].most_common(6)) for w in wins))
            print('      plantings ' + ', '.join(f'{c} {ev[("plant", c)] / n:.1f}' for c in MAXDAY if ev[("plant", c)])
                  + ' | harvested units ' + ', '.join(f'{c} {ev[("harvest", c)] / n:.1f}' for c in MAXDAY if ev[("harvest", c)])
                  + ' | died ' + ', '.join(f'{c} {ev[("died", c)] / n:.1f}' for c in MAXDAY if ev[("died", c)])
                  + ' | animal output ' + ', '.join(f'{a} {ev[("aharv", a)] / n:.1f}' for a in ('GOOSE', 'COW', 'SHEEP') if ev[("aharv", a)]))
            ops = sum(v for k, v in wk.items() if k.startswith('op_'))
            print(f'      labour unit-steps per game: ops {ops / n:.0f}, walk {wk["walk"] / n:.0f} ('
                  + ', '.join(f'{k[3:]} {v / n:.0f}' for k, v in sorted(wk.items(), key=lambda kv: -kv[1]) if k.startswith('op_')) + ')')


def main():
    for a in [x for x in sys.argv if x.startswith('--')]:       # --idle (for remote commands without env)
        sys.argv.remove(a)
        if a == '--idle':
            _os.environ['LC_IDLE'] = '1'
    if sys.argv[1] == 'land':
        land(sys.argv[2].split(','))
        return
    if sys.argv[1] == 'fates':
        fates(sys.argv[2].split(','))
        return
    if sys.argv[1] == 'quad':
        quad_report(sys.argv[2].split(','))
        return
    if sys.argv[1] == 'run':
        agents = sys.argv[2].split(',')
        sub = sys.argv[4] if len(sys.argv) > 4 else 'p2750'
        if sys.argv[3] == 'smoke':
            eps = sorted(f.stem for f in (ROOT / 'results/fresh/ladder_panel/mgt_lead_deploy_s1').glob('*.json'))
        else:
            eps = sys.argv[3].split(',')
        for agent in agents:              # serial (a ProcessPool version hung on Kaggle, 2026-09-25; ~16 s a game)
            run(agent, eps, sub)
    else:
        report(sys.argv[2].split(','))


if __name__ == '__main__':
    main()
