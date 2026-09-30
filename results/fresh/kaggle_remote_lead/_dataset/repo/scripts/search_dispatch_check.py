"""Static checks of agents/mgt_lpv_search.py (NO games: no env, no opponent, no market):

  static  parse + compile of the agent and its variants; Kaggle's loader entry (kaggle_environments get_last_callable
          must return mgt_lead_deploy_agent); "off" = the source by construction: the line diff against the source
          snapshot is additions only (the inserted blocks are listed).
  plans   synthetic day-12 boards (grown with the engine's own daily refresh from random plantings): the planner's
          plan re-checked by an INDEPENDENT route simulator (items never negative at FEED / FERTILIZE / PLACE with the
          planned pickups, hard ops on time, day end, order pairs, pickups within the shed stock, seeds, the eval's
          value / end hour reproduced) and compared with the executor-greedy event simulation in the same time model.
  timing  planner time of the day's first plan and of warm-started steps on synthetic days of ~60 / ~80 / ~96 jobs.
  days    synthetic single days (hour 1..23 of day 12; the engine's _apply_unit_action + plant decay, nothing else)
          played by the greedy (shadow) and by the planner (active) from the same start: dropped jobs / value (the
          executor's maintenance module at 23h), tile ops, moves per op, fallbacks, step times.

usage: search_dispatch_check.py [static|plans|timing|days|all] [--seeds N]
Output: results/fresh/search_dispatch_20260925/static_check.json and .txt
"""
import copy
import difflib
import importlib.util
import json
import random
import statistics as stt
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/search_dispatch_20260925'
sys.path.insert(0, str(ROOT / 'scripts'))
import search_dispatch_build as SDB  # noqa: E402  (the targets: snapshots, outputs)
LEAD = ROOT / SDB.TARGETS['lead']['out']
EXEC_CFG = {'p1_min_value': 30, 'release_stale_d': True, 'fert_hold': 1}   # the deploy's executor defaults (G1 / sem4 runs)
SEM_GAME = ('16732748', '112655730')                                       # the leader plan used on the synthetic boards
SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]
LOG = []


def say(*a):
    s = ' '.join(str(x) for x in a)
    print(s, flush=True)
    LOG.append(s)


# ------------------------------------------------------------------------------------------------ static
def static():
    from kaggle_environments.agent import get_last_callable
    res = {}
    for name, T in SDB.TARGETS.items():
        out = ROOT / T['out']
        text = out.read_text(encoding='utf-8')
        compile(text, str(out), 'exec')
        r = {'out': T['out'], 'source': T['orig'], 'source_sha256': T['sha'], 'compiles': True}
        if name == 'deploy':
            f = get_last_callable(text, path=str(out))
            r['kaggle_loader_entry'] = getattr(f, '__name__', '?')
            assert r['kaggle_loader_entry'] == 'mgt_lead_deploy_agent', r
        a = (ROOT / T['src']).read_bytes().decode('utf-8').replace(chr(13) + chr(10), chr(10)).split(chr(10))
        b = text.split(chr(10))
        sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
        ops = sm.get_opcodes()
        bad = [o for o in ops if o[0] not in ('equal', 'insert')]
        ins = [o for o in ops if o[0] == 'insert']
        say(f"{T['out']}: compiles; diff vs {T['src']} ({len(a)} lines) -> {len(b)} lines: {len(ins)} inserted blocks, "
            f"{sum(o[4] - o[3] for o in ins)} inserted lines, {len(bad)} deleted / replaced blocks"
            + (f"; Kaggle loader entry {r['kaggle_loader_entry']}" if 'kaggle_loader_entry' in r else ''))
        r['inserted_blocks'] = []
        for o in ins:
            first = b[o[3]].strip()[:100]
            r['inserted_blocks'].append({'before_source_line': o[1] + 1, 'lines': o[4] - o[3], 'first': first})
            say(f"   + {o[4] - o[3]:5d} lines before source line {o[1] + 1}: {first}")
        r['deleted_or_replaced'] = len(bad)
        assert not bad, bad[:3]
        res[name] = r
    return res


# ------------------------------------------------------------------------------------------------ synthetic boards
_SEM = {}


def load_mod(name, cfg):
    """agents/mgt_lead_search.py configured with a leader plan (T) + EXEC_CFG + cfg."""
    import gzip
    if not _SEM:
        _SEM['s'] = json.load(gzip.open(ROOT / f'data/leader_semantics/{SEM_GAME[0]}/{SEM_GAME[1]}.json.gz', 'rt',
                                        encoding='utf-8'))
    spec = importlib.util.spec_from_file_location(name, LEAD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    import os
    extra = json.loads(os.environ.get('SD_CHECK_CFG') or '{}')   # research: planner settings under test
    mod.configure(_SEM['s'], **dict(EXEC_CFG, **dict(cfg, **extra)))
    return mod


def grow_board(E, seed, quads, density, n_animals, day):
    """a mid-season farm grown with the engine's daily refresh from random plantings (watering ~85%, never two
    misses; feeding ~95%; care ~70%; harvests on some days)."""
    rng = random.Random(seed)
    unlocked = ['NW', 'NE', 'SW', 'SE'][:quads]
    tiles = [[None if E._quadrant_of(x, y, 10) in unlocked else 'LOCKED' for x in range(10)] for y in range(10)]
    farm = {'money': 6000.0, 'tiles': tiles, 'farmer': [4, 4], 'hands': [], 'unlocked_quadrants': unlocked,
            'hires_today': 0}
    cells = [(x, y) for y in range(10) for x in range(10) if tiles[y][x] is None and (x, y) not in SHED]
    rng.shuffle(cells)
    an = cells[:n_animals]
    crops = cells[n_animals:n_animals + int(density * (len(cells) - n_animals))]
    life = {'WHEAT': 4, 'CARROT': 3, 'TOMATO': 11, 'STRAWBERRY': 16, 'MELON': 12}
    plan = {}
    for c in crops:
        crop = rng.choices(['WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON'], weights=[4, 2, 2, 2, 1])[0]
        plan[c] = (crop, day - rng.randint(0, life[crop]))
    aplan = {}
    for c in an:
        sp = rng.choice(['GOOSE', 'GOOSE', 'COW', 'SHEEP'])
        aplan[c] = (sp, rng.randint(1, 8))
        tiles[c[1]][c[0]] = {'kind': E.ANIMALS[sp]['structure']}
    for d in range(0, day):
        for (x, y), (crop, pd) in plan.items():
            if pd == d:
                tiles[y][x] = E._new_plant(crop, d, 24)
        for (x, y), (sp, pd) in aplan.items():
            if pd == d:
                tiles[y][x] = E._new_animal(sp, d)
        for y in range(10):
            for x in range(10):
                t = tiles[y][x]
                if not isinstance(t, dict):
                    continue
                if t.get('kind') == 'PLANT':
                    if t['consecutive_unwatered'] >= 1 or rng.random() < 0.85:
                        E._apply_unit_action(farm, {'shed': {}, 'seeds': {}, 'inventories': [{}]}, 0, ['WATER'], 10, d, 24)
                        t['watered_today'] = True
                    if E.CROPS[t['crop']]['ongoing'] and rng.random() < 0.2:
                        t['fertilized_until_day'] = d + 2
                    cd = E.CROPS[t['crop']]
                    if (d - t['planted_day'] >= cd['first_yield_day'] and t['yield_units'] > 0
                            and cd['ongoing'] and rng.random() < 0.5):
                        t['yield_units'] = 0
                elif 'animal' in t:
                    if t['consecutive_unfed'] >= 1 or rng.random() < 0.95:
                        t['fed_today'] = True
                    if rng.random() < 0.7:
                        t['cared_today'] = True
                    if rng.random() < 0.5:
                        t['yield_units'] = 0
                    if rng.random() < 0.6:
                        t['fertilizer_available'] = False
        E._daily_refresh_plants(farm, d, 24)
        E._daily_refresh_animals(farm, d)
        for (x, y), (crop, pd) in plan.items():     # a crop that died / decayed before day 12 is replanted as planned
            t = tiles[y][x]
            if isinstance(t, dict) and t.get('kind') == 'WEED':
                tiles[y][x] = None
    return farm


def synth_obs(E, seed, quads=3, density=0.9, n_animals=10, day=12, hour=1, n_hands=12):
    farm = grow_board(E, seed, quads, density, n_animals, day)
    pos = [(4, 4)]
    for _ in range(n_hands):
        farm['hands'].append(E._spawn_hand(farm, 10))
    rng = random.Random(seed + 1)
    prices = {k: max(1, int(round(v['base'] * rng.uniform(0.6, 1.3)))) for k, v in E.MARKET_PARAMS.items()}
    private = {'shed': {k: 0 for k in E.PRODUCTS + list(E.ANIMALS)}, 'seeds': {c: 0 for c in E.CROPS},
               'inventories': [{} for _ in range(n_hands + 1)]}
    private['shed']['WHEAT'] = 60
    private['shed']['FERTILIZER'] = 6
    for c in E.CROPS:
        private['seeds'][c] = 4
    opp = copy.deepcopy(farm)
    obs = {'step': day * 24 + hour, 'player': 0, 'day': day, 'hour': hour, 'farms': [farm, opp],
           'market': {'prices': prices, 'inventory': {k: 10000 for k in E.PRODUCTS}},
           'town': {'unlocked_shops': ['BAKERY', 'PIZZA_SHOP', 'YARN_STORE', 'ICE_CREAM_SHOP', 'PET_CAFE']},
           'private': private, 'remainingOverageTime': 60}
    return obs


# ------------------------------------------------------------------------------------------------ independent verifier
def verify_plan(mod, P):
    """re-simulate every route with its planned pickup (position, amounts) and the executor's delivery rule, written
    independently of the planner's _sd_eval; returns (errors, per-route (value, end))."""
    errs = []
    D = P.d
    fin = {}
    per = {}
    sheds = [q[1] * 10 + q[0] for q in SHED]

    def run(u, final):
        r = P.routes[u]
        kp, npk = P.rkp[u]
        pw, pf, pa = P.rpw[u], P.rpf[u], list(P.rpa[u])
        t, pos = P.ut0[u], P.up[u]
        w, f, an = P.uw[u], P.uf[u], list(P.ua[u])
        du, dv, ty = P.udu[u], P.udv[u], P.uty[u]
        val = 0.0
        picked = npk == 0
        E_ = P.ue[u]
        for k, j in enumerate(r):
            jb = P.jb[j]
            b = jb[0]
            if k == kp and not picked:
                s = min(sheds, key=lambda q: (D[pos][q] + D[q][b], D[pos][q], q))
                t += D[pos][s] + npk
                pos = s
                w, f = w + pw, f + pf
                an = [an[i] + pa[i] for i in range(3)]
                picked = True
            t += D[pos][b]
            pos = b
            rel = jb[9]
            if jb[11] >= 0:
                pf_ = fin.get(jb[11])
                if pf_ is None:
                    if final:
                        errs.append(('successor without a planned predecessor', u, P.key[j]))
                    return None
                rel = max(rel, pf_ + jb[12])
            t = max(t, rel)
            # the executor's usable_ops: without wheat in hand no FEED (and no CARE after it), without fertilizer no
            # FERTILIZE; a hard op among them is an error; everything else is the plan's own choice of pickups
            cmds = [o[0] for o in P.ops[j]]
            skip = set()
            nw_, nf_ = jb[2], jb[3]
            if jb[2] and w < jb[2]:
                skip |= {i for i, c in enumerate(cmds) if c == 'FEED' or (c == 'CARE' and 'FEED' in cmds)}
                nw_ = 0
            if jb[3] and f < jb[3]:
                skip |= {i for i, c in enumerate(cmds) if c == 'FERTILIZE'}
                nf_ = 0
            if jb[10] >= 0 and jb[10] in skip:
                errs.append(('hard op without its item', u, P.key[j]))
            if jb[4] >= 0 and an[jb[4]] < 1:
                errs.append(('animal missing at PLACE', u, P.key[j]))
            n = jb[1]
            ex = [i for i in range(n) if i not in skip]
            m = len(ex)
            if t + m > E_:
                mm = E_ - t
                if k != len(r) - 1 or mm <= 0 or mm > jb[14]:
                    errs.append(('job past the day end', u, P.key[j], t, m))
                ex = ex[:max(0, mm)]
                if jb[10] >= 0 and jb[10] not in ex and jb[10] not in skip:
                    errs.append(('hard op cut by the day end', u, P.key[j]))
            for q, i in enumerate(ex):
                on = t + q <= jb[8][i]
                if i == jb[10] and not on:
                    errs.append(('hard op late', u, P.key[j], t + q, jb[8][i]))
                val += jb[7][i] * (1.0 if on else P.late_frac)
            if t + m > E_:
                t = E_
                break
            t += m
            w += jb[5] - nw_
            f += jb[6] - nf_
            if jb[4] >= 0:
                an[jb[4]] -= 1
            fin[j] = t
            if P.deliv and jb[15]:
                du, dv, ty = du + jb[15], dv + jb[16], ty + jb[17]
                trig = t < 22 and ((t < P.late_h and (du >= P.dunits or dv >= P.dval)) or (P.short and dv > 0)
                                   or (t < 20 and dv >= P.dval_late))
                if trig:
                    s = P.ns[b]
                    other = w > 0 or sum(an) > 0 or (f > 0 and P.fert_keep)
                    t += D[b][s] + (min(4, ty) if other else 1)
                    pos = s
                    du, dv, ty = 0, 0.0, 0
                    if not picked and kp > k:
                        t += npk
                        w, f = w + pw, f + pf
                        an = [an[i] + pa[i] for i in range(3)]
                        picked = True
        if P.lastday and t + P.ds[pos] + 1 > E_:
            errs.append(('day-29 route cannot return', u))
        te = min(t, E_)
        sw = P.switch_w * P.uswn[u] if (P.uswn[u] and (not r or P.key[r[0]] != P.uswk[u])) else 0.0
        return val - P.lam * (te - P.ut0[u]) - sw, t
    for _ in range(3):                             # predecessors in other routes: iterate to a fixed point
        for u in range(P.U):
            if P.routes[u]:
                run(u, False)
    for u in range(P.U):
        if P.routes[u]:
            per[u] = run(u, True)
            if per[u] is not None:
                if abs(per[u][0] - P.rsc[u]) > 1e-6 or per[u][1] != P.rend[u]:
                    errs.append(('eval mismatch', u, round(per[u][0], 3), round(P.rsc[u], 3), per[u][1], P.rend[u]))
    # shared stock, seeds, duplicates
    if sum(P.rpw) > P.avw or sum(P.rpf) > P.avf:
        errs.append(('pickups above the shed stock', sum(P.rpw), P.avw, sum(P.rpf), P.avf))
    for i in range(3):
        if sum(pa[i] for pa in P.rpa) > P.ava[i]:
            errs.append(('animal pickups above the shed stock', i))
    used = Counter(P.cropi[j] for r in P.routes for j in r if P.cropi[j] is not None and P.real[j])
    for c, k in used.items():
        if k > P.seeds.get(c, 0):
            errs.append(('seeds', c, k, P.seeds.get(c, 0)))
    allj = [j for r in P.routes for j in r]
    if len(allj) != len(set(allj)):
        errs.append(('job planned twice',))
    for j in range(P.J):
        if P.where[j] >= 0 and j not in P.routes[P.where[j]]:
            errs.append(('where[] inconsistent', j))
    return errs, per


def plan_stats(P, routes):
    busy = val = 0.0
    n = 0
    for u, r in enumerate(routes):
        if not r:
            continue
        busy += max(0, P.rend[u] - P.ut0[u])
        n += len(r)
    val = sum(P.vraw[j] for r in routes for j in r)
    return busy, val, n


def plans(E, seeds):
    say('\n== synthetic day-12 plans (hour 1, 13 units)')
    rows = []
    for seed in seeds:
        mod = load_mod(f'sdchk_plan_{seed}', {'dispatch_search': 'shadow', 'sd_keep': 1})
        obs = synth_obs(E, seed, quads=3 + (seed % 2), density=0.95, n_animals=8 + seed % 7)
        mod.agent(obs)
        L = mod._S['sd']
        P = L['lastP']
        errs, per = verify_plan(mod, P)
        # the executor-greedy event simulation in the same time model, from scratch on the same problem
        G = copy.copy(P)
        for k in ('routes', 'rsc', 'rend', 'rpw', 'rpf', 'rpa', 'rkp', 'rfin', 'where', 'ft', 'tpa', 'seed_used'):
            v = getattr(P, k)
            setattr(G, k, copy.copy(v))
        G.routes = [[] for _ in range(P.U)]
        G.rsc = [0.0] * P.U
        G.rend = list(P.ut0)
        G.rpw, G.rpf, G.rpa, G.rkp, G.rfin = [0] * P.U, [0] * P.U, [(0, 0, 0)] * P.U, [(-1, 0)] * P.U, [None] * P.U
        G.where = [-1] * P.J
        G.ft, G.tpw, G.tpf, G.tpa, G.seed_used, G.load = {}, 0, 0, [0, 0, 0], Counter(), P.base_load
        for u in range(G.U):
            ev = mod._sd_eval(G, u, [])
            G.rsc[u], G.rend[u] = ev[1], ev[2]
        mod._sd_construct(G)
        gerrs, _ = verify_plan(mod, G)
        pb, pv, pn = plan_stats(P, P.routes)
        gb, gv, gn = plan_stats(G, G.routes)
        real = [j for j in range(P.J) if P.real[j]]
        un_p = [j for j in real if P.where[j] < 0]
        un_g = [j for j in real if G.where[j] < 0]
        travel_p = sum(P.rend[u] - P.ut0[u] - sum(P.jb[j][1] for j in P.routes[u]) for u in range(P.U) if P.routes[u])
        travel_g = sum(G.rend[u] - G.ut0[u] - sum(G.jb[j][1] for j in G.routes[u]) for u in range(G.U) if G.routes[u])
        row = dict(seed=seed, jobs=P.J, real=len(real), ops=sum(P.jb[j][1] for j in real), units=P.U,
                   plan_ms=L['st']['plan_ms'][-1], evals=P.nev, errors=len(errs), greedy_errors=len(gerrs),
                   plan=dict(busy=pb, value=round(pv, 1), jobs=pn, unplanned=len(un_p),
                             unplanned_value=round(sum(P.vraw[j] for j in un_p), 1), obj=round(mod._sd_obj(P), 1),
                             travel=travel_p, pickups=sum(1 for u in range(P.U) if P.rkp[u][1])),
                   greedy=dict(busy=gb, value=round(gv, 1), jobs=gn, unplanned=len(un_g),
                               unplanned_value=round(sum(G.vraw[j] for j in un_g), 1), obj=round(mod._sd_obj(G), 1),
                               travel=travel_g, pickups=sum(1 for u in range(G.U) if G.rkp[u][1])),
                   hard_unplanned=sum(1 for j in un_p if P.hard[j]), preds=sum(1 for j in range(P.J) if not P.real[j]))
        rows.append(row)
        say(f"seed {seed}: {row['real']} jobs ({row['ops']} ops, {row['preds']} predicted), {P.U} units, "
            f"plan {row['plan_ms']:.0f} ms / {P.nev} evals | verifier errors {len(errs)} (greedy sim {len(gerrs)}) | "
            f"busy steps plan {pb} vs greedy {gb} ({100.0 * (pb - gb) / max(1, gb):+.1f}%), travel {travel_p} vs "
            f"{travel_g}, value {pv:.0f} vs {gv:.0f}, unplanned {len(un_p)} ({row['plan']['unplanned_value']:.0f}) vs "
            f"{len(un_g)} ({row['greedy']['unplanned_value']:.0f}), hard unplanned {row['hard_unplanned']}")
        for e in errs[:6]:
            say('     ERROR', e)
        for e in gerrs[:3]:
            say('     greedy-sim error', e)
    return rows


# ------------------------------------------------------------------------------------------------ timing
def timing(E, seeds):
    say('\n== planner time on synthetic days (first plan = hour 1; then 8 warm steps with the plan executed)')
    out = []
    for quads, dens, na, label in ((3, 0.85, 8, '~60'), (4, 0.8, 10, '~80'), (4, 1.0, 12, '~96')):
        for seed in seeds[:3]:
            mod = load_mod(f'sdchk_time_{label}_{seed}', {'dispatch_search': 'active', 'sd_keep': 1})
            obs = synth_obs(E, 100 + seed, quads=quads, density=dens, n_animals=na)
            r = play_day(E, mod, obs, hours=9)
            st = mod._S['sd']['st']
            P = mod._S['sd']['lastP']
            first = st['plan_ms_first'][0] if st['plan_ms_first'] else None
            warm = st['plan_ms'][1:]
            row = dict(label=label, seed=seed, jobs0=r['jobs0'], ops0=r['ops0'], units=len(obs['farms'][0]['hands']) + 1,
                       first_ms=first, warm_mean=round(stt.mean(warm), 1) if warm else None,
                       warm_max=max(warm) if warm else None, step_max=max(r['step_ms']),
                       capped=st['time_capped'], evals=st['evals'])
            out.append(row)
            say(f"  {label} jobs (seed {seed}): {r['jobs0']} jobs / {r['ops0']} ops, first plan {first:.0f} ms, warm "
                f"mean {row['warm_mean']} ms max {row['warm_max']} ms, whole step max {row['step_max']:.0f} ms, "
                f"time-capped {st['time_capped']} of {st['steps']}")
    return out


# ------------------------------------------------------------------------------------------------ synthetic single days
def play_day(E, mod, obs, hours=23):
    """hours 1..hours of the synthetic day: our commands through the engine's _apply_unit_action (atomic PLANT rule
    as in the interpreter), plant decay; no market, no hires, no opponent."""
    farm, private = obs['farms'][0], obs['private']
    day = obs['day']
    step_ms = []
    jobs0 = ops0 = None
    for h in range(obs['hour'], hours + 1):
        obs['step'] = day * 24 + h
        obs['hour'] = h
        t0 = time.perf_counter()
        a = mod.agent(obs)
        step_ms.append(1000.0 * (time.perf_counter() - t0))
        if jobs0 is None:
            P = mod._S['sd'].get('lastP')
            jobs0 = sum(1 for j in range(P.J) if P.real[j]) if P else None
            ops0 = sum(P.jb[j][1] for j in range(P.J) if P.real[j]) if P else None
        cmds = [a['farmer']] + list(a['hands'])
        demand = Counter(c[1] for c in cmds if isinstance(c, list) and len(c) >= 2 and c[0] == 'PLANT')
        blocked = {c for c, k in demand.items() if k > private['seeds'].get(c, 0)}
        for i, c in enumerate(cmds):
            if isinstance(c, list) and len(c) >= 2 and c[0] == 'PLANT' and c[1] in blocked:
                c = ['PASS']
            E._apply_unit_action(farm, private, i, c, 10, day, 24, 100)
        E._decay_plants(farm, obs['step'])
    return dict(step_ms=step_ms, jobs0=jobs0, ops0=ops0)


def days(E, seeds):
    say('\n== synthetic single days (day 12, hours 1-23): greedy (shadow) vs planner (active), same start')
    rows = []
    for seed in seeds:
        obs0 = synth_obs(E, 200 + seed, quads=3 + (seed % 2), density=0.95, n_animals=8 + seed % 7)
        res = {}
        for mode in ('shadow', 'active'):
            mod = load_mod(f'sdchk_day_{mode}_{seed}', {'dispatch_search': mode, 'sd_keep': 1})
            obs = copy.deepcopy(obs0)
            r = play_day(E, mod, obs)
            st = mod._S['sd']['st']
            res[mode] = dict(dropped=st['dropped_jobs'], dropped_value=round(st['dropped_value']),
                             dropped_prod=st['dropped_prod_jobs'], dropped_hard=st['dropped_hard'], work=st['work'],
                             moves=st['moves'], moves_per_op=round(st['moves'] / max(1, st['work']), 3),
                             shed_arrivals=st['shed_arrivals'], passes=st['passes'], fb_unit=st['fb_unit'],
                             fb=dict(pickup=st['fb_pickup'], noop=st['fb_noop'], notask=st['fb_notask']),
                             idle=st['idle_unit'], errors=st['errors'], last_error=st['last_error'],
                             step_max=round(max(r['step_ms'])), plan_max=max(st['plan_ms']) if st['plan_ms'] else 0,
                             jobs0=r['jobs0'], ops0=r['ops0'], agree=(st['agree'], st['agree_n']))
        rows.append(dict(seed=seed, **res))
        g, p = res['shadow'], res['active']
        say(f"seed {seed}: {g['jobs0']} jobs / {g['ops0']} ops | dropped at 23h: greedy {g['dropped']} "
            f"({g['dropped_value']}) vs planner {p['dropped']} ({p['dropped_value']}); production {g['dropped_prod']} vs "
            f"{p['dropped_prod']}; hard {g['dropped_hard']} vs {p['dropped_hard']} | tile ops {g['work']} vs {p['work']} | "
            f"moves/op {g['moves_per_op']} vs {p['moves_per_op']} | shed arrivals {g['shed_arrivals']} vs "
            f"{p['shed_arrivals']} | planner fallbacks {p['fb_unit']} {p['fb']} idle {p['idle']} errors "
            f"{p['errors']} {p['last_error']} | step max {g['step_max']} / {p['step_max']} ms | shadow agreement "
            f"{g['agree'][0]}/{g['agree'][1]}")
    return rows


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else 'all'
    ns = 6
    if '--seeds' in sys.argv:
        ns = int(sys.argv[sys.argv.index('--seeds') + 1])
    seeds = list(range(1, ns + 1))
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    out = {}
    if what in ('static', 'all'):
        out['static'] = static()
    if what in ('plans', 'all'):
        out['plans'] = plans(E, seeds)
    if what in ('timing', 'all'):
        out['timing'] = timing(E, seeds)
    if what in ('days', 'all'):
        out['days'] = days(E, seeds)
    OUT.mkdir(parents=True, exist_ok=True)
    tag = '' if what == 'all' else '_' + what
    (OUT / f'static_check{tag}.json').write_text(json.dumps(out, indent=1, default=str), encoding='utf-8')
    (OUT / f'static_check{tag}.txt').write_text('\n'.join(LOG) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
