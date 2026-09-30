"""Dawn-leg trace for one world (dawn thread): is the code doing what was intended, and why did the money move?
Reads the arm's season file (results/fresh/sector_20260925/multi/<ARM>/<ep>.json; run the arm with sd_tier_dawn_cf 1 for
the displaced-work part) and replays the arm's and the reference arm's games on the engine.
  1. code check: every planned dawn leg (tier_days units' "dawn"; mode 3 also DSM's trip) vs what the unit really did
     (HARVEST on the pen: hour, units; PLACE / DROP on a shed tile: hour, goods), planned vs actual hours, a step table
     for the sample days; breakages (executor counters / log, spawn tiles planned vs actual, idle unit-hours)
  2. displaced work: per day, the same-state plan without the legs (cf) vs the real plan: ops only in cf (displaced,
     with the planner's values), by op type and unit; unplanned extras' value real vs cf
  3. consequences: deaths (tile, crop / animal, day, last watering / feed), executed upkeep ops vs the reference arm
  4. what the early goods earned: per leg the sale step and prices of its goods (the arm sells a delivery at once)
usage: dawn_trace.py <team:ep> <ARM> [--ref KS1fl] [--days 12,15,20] [--json out.json]"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
M = ROOT / 'results/fresh/sector_20260925/multi'
SHED = {(4, 4), (5, 4), (4, 5), (5, 5)}
PRODS = ('WOOL', 'MILK', 'EGG', 'STRAWBERRY', 'TOMATO', 'CARROT', 'WHEAT', 'MELON', 'FERTILIZER')
XY = lambda i: '%d%d' % (i % 10, i // 10)              # tile index -> "xy" as the viewer prints it
REC = {'w': None, 'seat': 0, 't': 0, 'sales': None}
_commit = E._commit_unit


def commit(op, item, price, farm, private, market, shed_capacity=100):
    r = _commit(op, item, price, farm, private, market, shed_capacity)
    w = REC['w']
    if r and w is not None and REC['t'] >= 264 and op == 'SELL':
        REC['sales'].append((REC['t'], 'us' if farm is w.farms[REC['seat']] else 'opp', item, float(price)))
    return r


E._commit_unit = commit


def replay(tape, stream):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    REC.update(w=w, seat=seat, sales=[])
    steps = {}
    deaths = []
    last_w = {}                                            # plant tile -> last day watered
    last_f = {}                                            # animal tile -> last day fed
    while w.t < 719:
        t = w.t
        REC['t'] = t
        if stream is None or t < 264:
            own = UE.tape_action(tape['actions'], t)
        else:
            a = stream[t] if t < len(stream) else {}
            own = a if isinstance(a, dict) and a else dict(UE.PASS)
        f = w.farms[seat]
        tiles0 = f['tiles']
        if t >= 264:
            pos = [tuple(f['farmer'])] + [tuple(p) for p in f['hands']]
            acts = [own.get('farmer')] + list(own.get('hands') or [])
            tl = [tiles0[p[1]][p[0]] for p in pos]
            tl = [dict(animal=x.get('animal'), crop=x.get('crop'), y=int(x.get('yield_units', 0) or 0)) if isinstance(x, dict) else None
                  for x in tl]
            inv0 = [dict(x) for x in w.private(seat)['inventories']]
        before = None
        if t % 24 == 23 and t >= 264:
            before = {}
            for y in range(10):
                for x in range(10):
                    c = tiles0[y][x]
                    if isinstance(c, dict) and (c.get('crop') or c.get('animal')):
                        before[y * 10 + x] = dict(c)
                        if c.get('crop') and c.get('watered_today'):
                            last_w[y * 10 + x] = t // 24
                        if c.get('animal') and c.get('fed_today'):
                            last_f[y * 10 + x] = t // 24
        acts2 = [None, None]
        acts2[seat], acts2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(acts2)
        if t < 264:
            continue
        inv1 = w.private(seat)['inventories'] if t % 24 != 23 else None
        rows = []
        for i, p in enumerate(pos):
            a = acts[i] if i < len(acts) and isinstance(acts[i], list) and acts[i] else ['PASS']
            d = {}
            if inv1 is not None and i < len(inv1):
                for k in PRODS:
                    q = int(inv1[i].get(k, 0) or 0) - int((inv0[i] if i < len(inv0) else {}).get(k, 0) or 0)
                    if q:
                        d[k] = q
            rows.append((list(p), a, d, tl[i]))
        steps[t] = rows
        if before is not None:
            tiles1 = w.farms[seat]['tiles']
            harvested = {tuple(r[0]) for r in rows if r[1][0] in ('HARVEST', 'DIG')}
            for idx, c in before.items():
                x, y = idx % 10, idx // 10
                n = tiles1[y][x]
                if c.get('crop') and (x, y) not in harvested and not (isinstance(n, dict) and n.get('crop') == c['crop']):
                    deaths.append({'day': t // 24, 'tile': idx, 'what': c['crop'], 'last_water': last_w.get(idx),
                                   'watered_today': bool(c.get('watered_today')), 'kind': 'plant'})
                if c.get('animal') and not (isinstance(n, dict) and n.get('animal') == c['animal']):
                    deaths.append({'day': t // 24, 'tile': idx, 'what': c['animal'], 'last_feed': last_f.get(idx),
                                   'fed_today': bool(c.get('fed_today')), 'kind': 'animal'})
    out = {'steps': steps, 'sales': list(REC['sales']), 'deaths': deaths,
           'money': (w.farms[seat]['money'], w.farms[1 - seat]['money'])}
    REC['w'] = None
    return out


def legs_of(season):
    L = {}
    for d, t in sorted((season.get('tier_days') or {}).items(), key=lambda x: int(x[0])):
        ex = t.get('exec') or {}
        for un in t.get('units') or []:
            if 'dawn' not in un:
                continue
            u = un['u']
            plan = (ex.get(str(u)) or {}).get('plan') or []
            done = (ex.get(str(u)) or {}).get('done') or []
            L.setdefault(int(d), []).append({'u': u, 'pen': un['dawn'][0], 'units': un['dawn'][1], 'drop': un['dawn'][2],
                                             'pens': un.get('dawn_pens') or [un['dawn'][0]], 'dsm': un.get('dawn_dsm'),
                                             'plan': plan, 'done': done, 't0': un['t0']})
    return L


def check_legs(L, R, sample, out):
    """planned vs executed dawn legs."""
    cnt = Counter()
    lines = []
    for d, legs in sorted(L.items()):
        for lg in legs:
            u = lg['u']
            pens = set(lg['pens'])
            hv, dr = [], None
            for h in range(24):
                rows = R['steps'].get(d * 24 + h)
                if not rows or u >= len(rows):
                    continue
                p, a, dd, tl = rows[u]
                idx = p[1] * 10 + p[0]
                if a[0] == 'HARVEST' and idx in pens:
                    hv.append((h, XY(idx), sum(v for k, v in dd.items() if v > 0)))
                if a[0] in ('PLACE', 'DROP') and tuple(p) in SHED and any(v < 0 for k, v in dd.items() if k != 'WHEAT') and dr is None and hv:
                    dr = (h, XY(idx), {k: -v for k, v in dd.items() if v < 0})
            ph = [x[2] for x in lg['plan'] if x[1] == 'HARVEST' and x[0] in pens]
            pd = lg['drop']
            ok_h = bool(hv) and len(hv) == len(pens)
            ok_d = dr is not None
            late = (hv[0][0] - ph[0]) if (hv and ph) else None
            dlate = (dr[0] - pd) if (dr and pd is not None) else None
            cnt['planned'] += 1
            cnt['executed'] += ok_h and ok_d
            cnt['harvest_missing'] += not ok_h
            cnt['drop_missing'] += ok_h and not ok_d
            cnt['on_time'] += ok_h and ok_d and late == 0 and dlate == 0
            cnt['late'] += ok_h and ok_d and ((late or 0) > 0 or (dlate or 0) > 0)
            cnt['early'] += ok_h and ok_d and ((late or 0) < 0 or (dlate or 0) < 0)
            cnt['units_dropped'] += sum(dr[2].values()) if dr else 0
            s = (f'd{d} u{u} pens {"+".join(XY(x) for x in lg["pens"])} plan harvest h{ph} drop h{pd} | done harvest '
                 f'{hv} drop {dr}' + (f' | DSM trip u{lg["dsm"][0]} act h{lg["dsm"][1]} start {XY(lg["dsm"][2])} '
                                       f'pens {"+".join(XY(int(x[0])) for x in lg["dsm"][3])} drop {XY(lg["dsm"][4])}' if lg['dsm'] else ''))
            lines.append(s)
            out.setdefault('legs', []).append({'day': d, 'u': u, 'pens': lg['pens'], 'plan_h': ph, 'plan_drop': pd,
                                               'harvest': hv, 'drop': dr, 'dsm': lg['dsm']})
    print('--- 1. planned vs executed dawn legs:', dict(cnt))
    for s in lines:
        if int(s[1:s.index(' ')]) in sample:
            print('   ' + s)
    bad = [s for s in lines if 'drop None' in s or 'harvest []' in s]
    for s in bad:
        print('   BROKEN: ' + s)
    out['leg_counts'] = dict(cnt)


def step_table(L, R, d, hmax=7):
    units = sorted({lg['u'] for lg in L.get(d, [])})
    print(f'   day {d} dawn units, hours 0-{hmax} (pos:action, +harvested / -placed):')
    for u in units:
        cells = []
        for h in range(hmax + 1):
            rows = R['steps'].get(d * 24 + h)
            if not rows or u >= len(rows):
                cells.append('')
                continue
            p, a, dd, tl = rows[u]
            g = ''.join(('+' if v > 0 else '') + str(v) + k[:1] for k, v in dd.items())
            cells.append(f'{p[0]}{p[1]}:{" ".join(str(x) for x in a)[:12]}{(" " + g) if g else ""}')
        print(f'     u{u:2d} | ' + ' | '.join(f'{c:22s}' for c in cells))


def breakages(season, ref, R, RR, out):
    def agg(s):
        c = Counter()
        for d, t in (s.get('tier_days') or {}).items():
            for k, v in (t.get('cnt') or {}).items():
                if not k.startswith('q_'):
                    c[k] += v
        return c
    ca, cr = agg(season), agg(ref)
    keys = sorted(set(ca) | set(cr))
    print('--- executor counters (arm / reference): ' + ', '.join(f'{k} {ca[k]}/{cr[k]}' for k in keys if ca[k] or cr[k]))

    def spawn_err(s, RP):
        bad = tot = 0
        for d, t in (s.get('tier_days') or {}).items():
            sp = t.get('spawn') or []
            d = int(d)
            for j, q in enumerate(sp):
                u = j + 1
                for h in (1, 2):
                    rows = RP['steps'].get(d * 24 + h)
                    if rows and u < len(rows):
                        first = rows[u][0]
                        break
                else:
                    continue
                tot += 1
                bad += list(first) != list(q)
        return bad, tot

    def idle(RP):
        n = 0
        for t, rows in RP['steps'].items():
            for i, r in enumerate(rows):
                if r[1][0] == 'PASS' and not (i == 0 and t % 24 == 0):
                    n += 1
        return n
    sa, sr = spawn_err(season, R), spawn_err(ref, RR)
    print(f'--- hires on a different tile than planned at their first hour: arm {sa[0]}/{sa[1]}, reference {sr[0]}/{sr[1]}; '
          f'PASS unit-hours (farmer hour-0 hold excluded): arm {idle(R)}, reference {idle(RR)}')
    out['counters'] = {'arm': dict(ca), 'ref': dict(cr)}


def displaced(season, sample, out):
    """same state: the plan without the legs (cf) vs the real plan. Ops only in cf = displaced, ops only in the real plan =
    added (the legs' own harvests are in neither: the cf plan's harvest of a leg pen counts as displaced and is reported
    apart as 'moved into legs'). Values are the planner's own op values."""
    gone_n, gone_v, add_n, add_v = Counter(), Counter(), Counter(), Counter()
    moved = 0
    unp = [0.0, 0.0]
    lines = []
    for d, t in sorted((season.get('tier_days') or {}).items(), key=lambda x: int(x[0])):
        cf = t.get('cf')
        if not cf:
            continue
        legs = set()
        for un in t.get('units') or []:
            if un.get('dawn'):
                legs |= set(un.get('dawn_pens') or [un['dawn'][0]])

        def ops_of(units):
            c, v = Counter(), {}
            for un in units:
                for st in un.get('stops_v') or un.get('stops') or []:
                    for o in st[1]:
                        if isinstance(o, list):
                            c[(st[0], o[0])] += 1
                            v[(st[0], o[0])] = (o[3], o[1])
            return c, v
        rc, rv = ops_of(t.get('units') or [])
        cc, cv = ops_of(cf['units'])
        g_day, a_day = Counter(), Counter()
        for (tile, op), n in (cc - rc).items():
            if tile in legs and op in ('HARVEST', 'PLACE_HARVEST'):
                moved += n
                continue
            gone_n[op] += n
            gone_v[op] += n * cv[(tile, op)][0]
            g_day[op + ('*' if cv[(tile, op)][1] else '')] += n
        for (tile, op), n in (rc - cc).items():
            add_n[op] += n
            add_v[op] += n * rv[(tile, op)][0]
            a_day[op + ('*' if rv[(tile, op)][1] else '')] += n
        u_r = sum(x[2] for x in t.get('unplanned') or [])
        u_c = sum(x[2] for x in cf.get('unplanned') or [])
        unp[0] += u_r
        unp[1] += u_c
        dl = sum(x.get('dawn') is not None for x in t.get('units') or [])
        lines.append((int(d), f'd{d}: {dl} legs; only without the legs {dict(g_day)}; only with them {dict(a_day)} (* = mandatory); '
                              f'unplanned extras {u_r:.0f} vs {u_c:.0f}; mandatory lateness {t.get("mand_late")} vs {cf.get("mand_late")}'))
    if not lines:
        print('--- 2. displaced work: no cf plans in the season file (run the arm with sd_tier_dawn_cf 1)')
        return
    net = {k: gone_n[k] - add_n[k] for k in set(gone_n) | set(add_n)}
    netv = sum(gone_v.values()) - sum(add_v.values())
    print(f'--- 2. displaced work (same state; plan without the legs vs with them; the {moved} leg harvest ops moved into the legs '
          f'not counted): net ops lost {dict((k, v) for k, v in net.items() if v)}; planner value lost net {netv:.0f} '
          f'(displaced {sum(gone_v.values()):.0f}, gained {sum(add_v.values()):.0f}); unplanned extras value {unp[0]:.0f} with the legs vs {unp[1]:.0f} without')
    for d, s in lines:
        if d in sample:
            print('   ' + s)
    out['displaced'] = {'gone': dict(gone_n), 'gone_v': dict(gone_v), 'added': dict(add_n), 'added_v': dict(add_v), 'unplanned': unp,
                        'moved': moved}


def consequences(season, ref, R, RR, out):
    print('--- 3. deaths (arm): ' + '; '.join(f'd{x["day"]} {x["what"]} {XY(x["tile"])} '
                                                 + (f'last watered d{x["last_water"]}' if x['kind'] == 'plant' else f'last fed d{x["last_feed"]}')
                                                 for x in R['deaths']))
    print('    deaths (reference): ' + '; '.join(f'd{x["day"]} {x["what"]} {XY(x["tile"])}' for x in RR['deaths']))

    def ops(RP):
        c = Counter()
        for t, rows in RP['steps'].items():
            for r in rows:
                op = r[1][0]
                if op in ('FEED', 'CARE', 'COLLECT_FERTILIZER', 'WATER', 'FERTILIZE', 'HARVEST', 'PLANT'):
                    what = (r[3] or {}).get('animal') or (r[3] or {}).get('crop') or '-'
                    c[op + '|' + what] += 1
        return c
    oa, orf = ops(R), ops(RR)
    diff = {k: oa[k] - orf[k] for k in sorted(set(oa) | set(orf)) if oa[k] != orf[k]}
    print('    commands issued, arm - reference: ' + ', '.join(f'{k} {v:+d}' for k, v in diff.items()))
    out['deaths'] = R['deaths']
    out['ops_diff'] = diff
    td_all = season.get('tier_days') or {}

    def where(td, idx, op='WATER'):
        pl = ['u%d%s' % (un['u'], '(leg unit)' if un.get('dawn') else '') + ':' + '/'.join(
              '%s%s%.0f@h%s' % (o[0][:5], '*' if o[1] else '', o[3], next((h for (b_, c_, h) in ((td.get('exec') or {}).get(str(un['u'])) or {}).get('plan') or []
                                                                           if b_ == idx and c_ == o[0]), '?'))
              for o in st[1] if o[0] == op)
              for un in td.get('units') or [] for st in un.get('stops_v') or [] if st[0] == idx and any(o[0] == op for o in st[1])]
        unf = ['u' + u for u, items in (td.get('unfinished') or {}).items() for it in items if it[0] == idx
               and any((x[0] if isinstance(x, list) else x) == op for x in (it[1] if isinstance(it[1], list) else []))]
        unp = [x[2] for x in td.get('unplanned') or [] if x[0] == idx and op in x[1]]
        done = ['u%s@h%d' % (u, x[0]) for u, e in (td.get('exec') or {}).items() for x in e.get('done') or [] if x[1] == idx and x[2] == op]
        cf = ['u%d' % un['u'] for un in ((td.get('cf') or {}).get('units') or []) for st in un['stops'] if st[0] == idx
              and any((o[0] if isinstance(o, list) else o) == op for o in st[1])]
        return f'planned {pl} unfinished {unf} unplanned {unp} done {done} | same-state plan without legs: {cf}'
    for x in R['deaths']:
        if x['kind'] != 'plant':
            continue
        print(f'    death d{x["day"]} {x["what"]} {XY(x["tile"])}:')
        for dd in (x['day'] - 1, x['day']):
            td = td_all.get(str(dd))
            if td:
                print(f'       d{dd} WATER {where(td, x["tile"])}')


def earnings(L, R, out):
    """sale steps and prices of each leg's goods (a dawn delivery is sold at the drop step)."""
    by = defaultdict(list)
    for s in R['sales']:
        if s[1] == 'us':
            by[(s[0], s[2])].append(s[3])
    tot = Counter()
    rows = []
    for lg in out.get('legs', []):
        if not lg['drop']:
            continue
        d = lg['day']
        h, tile, goods = lg['drop']
        for k, n in goods.items():
            px = by.get((d * 24 + h, k), [])
            nxt = by.get(((d + 1) * 24 + 1, k), [])
            tot[k + '|n'] += n
            tot[k + '|sold_at_drop'] += min(n, len(px))
            tot[k + '|$'] += sum(px[-n:]) if px else 0
            rows.append(f'd{d} h{h} {k} {n} placed; sold that step {len(px)} @ {sum(px) / max(1, len(px)):.0f}; '
                        f'next day h1 our {k} sales {len(nxt)} @ {sum(nxt) / max(1, len(nxt)):.0f}')
    print('--- 4. dawn goods: ' + ', '.join(f'{k} {v:.0f}' for k, v in tot.items()))
    for r in rows[:12]:
        print('   ' + r)
    out['earn'] = dict(tot)


if __name__ == '__main__':
    g, arm = sys.argv[1], sys.argv[2]
    ref = sys.argv[sys.argv.index('--ref') + 1] if '--ref' in sys.argv else 'KS1fl'
    sample = [int(x) for x in sys.argv[sys.argv.index('--days') + 1].split(',')] if '--days' in sys.argv else [12, 15, 20]
    team, ep = g.split(':')
    tape = UE.load_tape(int(team), int(ep))
    season = json.loads((M / arm / f'{ep}.json').read_text(encoding='utf-8'))
    sref = json.loads((M / ref / f'{ep}.json').read_text(encoding='utf-8'))
    st_a = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    st_r = json.loads((ROOT / 'results/fresh/day12_viz' / f'{ref.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    R = replay(tape, st_a)
    RR = replay(tape, st_r)
    o, v = season['money']['30']
    o0, v0 = sref['money']['30']
    print(f'=== {arm} vs {ref}: own {o:.0f} ({o - o0:+.0f}), rival {v:.0f} ({v - v0:+.0f}), margin {o - v:.0f} ({(o - v) - (o0 - v0):+.0f})')
    out = {'arm': arm, 'ref': ref}
    L = legs_of(season)
    check_legs(L, R, sample, out)
    for d in sample:
        step_table(L, R, d)
    breakages(season, sref, R, RR, out)
    displaced(season, sample, out)
    consequences(season, sref, R, RR, out)
    earnings(L, R, out)
    if '--json' in sys.argv:
        json.dump(out, open(sys.argv[sys.argv.index('--json') + 1], 'w'), default=list)
