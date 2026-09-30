"""Ceiling of a search-based dispatcher on OUR OWN days (stored data only, no games).

Ours   = the current default deploy (tie_value) with the passive dropped-job tracer: Kaggle run wtr7, agent
         mgt_lpv_mpt0, 12 smoke worlds (lead_world_trace json = our returned action dicts; lead_idle/mp0 jsonl = the
         tracer, one file per game, matched to its episode by the per-day command counts).
Leader = the leader's own actions in the 12 lead_g1.GAMES worlds (data/leader_tapes).

Per day, exactly as scripts/labour_search.py does for Mother-Goose tapes: positions rebuilt from the recorded moves
(spawn rule of the engine; a hand exists once it appears in the returned 'hands' list, as scripts/lead_route_order.py),
jobs = one unit's commands on one tile in one stay (labour_search.instance), the actual arrangement scored in the same
time model (labour_search.finish), units whose own route does not fit the model (finish > 24) frozen. Two changes:
(instance_timeorder) the order constraint for tiles worked by two units is taken in time order, not unit-index order
(labour_search's version freezes 14% of our unit-days and 24% of the leader's; both are recorded); (finish_due) the
earlier job of such a pair may not start after its actual hour, so a re-arrangement cannot reverse the order.
  (a) min-sum re-arrangement at the SAME units: 2-opt / or-opt per route, inter-route relocate, spatial
      ruin-and-recreate with regret insertion; objective = total busy unit-steps (finish - first hour), all <= 24.
  (b) labour_search.search: hands emptied with all jobs still done; fib wages of the dropped (latest) hires.
  (c) ours only: the tracer's dropped production-affecting jobs (open at 23h, value > 0) inserted by value into the
      same crew's routes before midnight: (i) our actual routes as scored in the model, (ii) the (a) routes.
usage: search_ceiling.py [ours|leader|both] [max_games] [--long SECONDS --every N]
"""
import gzip
import json
import random
import statistics as st
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import labour_search as LS  # noqa: E402  (module import only; its main() is not run)
import lead_g1  # noqa: E402

TR = ROOT / 'results/fresh/kaggle_remote_lead/wtr7/output/kgr-wtr7-s0/out/repo/results/fresh'
SMOKE = [110937191, 111374151, 111376633, 111416249, 111554912, 111577649, 111681195, 111688786, 111871547,
         111902048, 111916514, 111941962]
MOVES = LS.MOVES
BUDGETS = (0.3, 1.0)
OPS = ('WATER', 'FEED', 'CARE', 'HARVEST', 'FERTILIZE', 'COLLECT_FERTILIZER')


# ------------------------------------------------------------------ order-safe time model
# labour_search bounds the LATER job of a two-unit tile below by the earlier job's actual hour, but never bounds the
# EARLIER job above, so a re-arrangement can reverse the order (e.g. PLANT before the HARVEST that clears the tile).
# Here the earlier job also gets due = its actual start hour (it may move earlier, never later): the order is kept.
# LS.finish is replaced by the same function plus that one check (plain LS.Job instances have due = 99: unchanged).
LS.Job.due = 99
_finish_orig = LS.finish


class DJob(LS.Job):
    __slots__ = ('due',)

    def __init__(self, tile, ops, today=False, release=0, due=99):
        super().__init__(tile, ops, today=today, release=release)
        self.due = due


def finish_due(unit, route):
    """labour_search.finish, plus: a job starting after its due hour makes the route infeasible (99)."""
    if not route:
        return unit[0]
    t, pos = unit
    need = bal = 0
    for j in route:
        bal -= j.fert
        need = max(need, -bal)
    t += (any(j.wheat for j in route)) + (need > 0) + (any(j.animal for j in route))
    last_today = max((k for k, j in enumerate(route) if j.today), default=-1)
    for k, j in enumerate(route):
        t = max(t + LS.d(pos, j.tile), j.release)
        if t > j.due:
            return 99
        t += j.n
        pos = j.tile
        if k == last_today:
            q = LS.home(pos)
            t += LS.d(pos, q) + 1
            pos = q
    return t


LS.finish = finish_due


# ------------------------------------------------------------------ stored streams -> labour_search's sim format
def sim_from_actions(actions):
    """{step: [(x, y, cmd), ...]} (positions BEFORE the step's command), units = farmer + the returned hands list."""
    out, pos = {}, []
    for t, a in enumerate(actions[:719]):
        if t % 24 == 0:
            pos = [(4, 4)]
        a = a if isinstance(a, dict) else {}
        hands = a.get('hands') or []
        while len(pos) - 1 < len(hands):
            pos.append(LS.ns['_tc_spawn'](pos))
        cmds = [a.get('farmer') or ['PASS']] + [h or ['PASS'] for h in hands]
        out[t] = [(p[0], p[1], cmds[i] if i < len(cmds) else ['PASS']) for i, p in enumerate(pos)]
        for i, p in enumerate(pos):
            c = cmds[i] if i < len(cmds) else ['PASS']
            if c and c[0] in MOVES:
                dx, dy = MOVES[c[0]]
                nx, ny = p[0] + dx, p[1] + dy
                if 0 <= nx < 10 and 0 <= ny < 10:
                    pos[i] = (nx, ny)
    return out


def day_counts(sim, day):
    """The tracer's per-day 'work' counters recomputed from the stream (for matching tracer files to episodes)."""
    c = Counter()
    for t in range(day * 24, min(719, day * 24 + 24)):
        for x, y, cmd in sim.get(t, []):
            op = cmd[0] if cmd else 'PASS'
            if op in MOVES:
                c['move'] += 1
            elif op in OPS:
                c['op_' + op] += 1
            elif op in ('PICKUP', 'DROP', 'PLACE'):
                c['shed_' + op] += 1
            elif op == 'PASS':
                c['pass'] += 1
            else:
                c['plan_' + op] += 1
    return c


def actual_parts(sim, day):
    """per unit: counts of moves / work commands / shed commands / PASS up to the unit's last non-PASS command."""
    seq = defaultdict(list)
    for t in range(day * 24, min(719, day * 24 + 24)):
        for u, (x, y, c) in enumerate(sim.get(t, [])):
            seq[u].append(((x, y), c[0] if c else 'PASS'))
    out = {}
    for u, v in seq.items():
        work = [k for k, (_, op) in enumerate(v) if op != 'PASS']
        last = work[-1] if work else -1
        c = Counter()
        for p, op in v[:last + 1]:
            if op in MOVES:
                c['moves'] += 1
            elif op == 'PASS':
                c['pass'] += 1
            elif LS.is_work(p, op):
                c['work'] += 1
            else:
                c['shed'] += 1
        c['present'] = len(v)
        out[u] = c
    return out


def instance_timeorder(sim, day):
    """labour_search.instance with ONE change: the 'tiles worked by two units' order constraint is taken in TIME order.
    labour_search keys first_on_tile in unit-index order, so a higher-index unit that worked a tile EARLIER than a
    lower-index one gets release = the lower-index unit's (later) hour and its own actual route stops fitting the
    model. Here a unit's job on a tile gets release = the latest start hour of another unit's job on that tile that
    started strictly earlier (same-hour jobs are simultaneous, no constraint). Everything else is identical."""
    seq = {}
    for t in range(day * 24, min(719, day * 24 + 24)):
        for u, (x, y, c) in enumerate(sim.get(t, [])):
            seq.setdefault(u, []).append((t % 24, (x, y), c[0] if c else 'PASS'))
    units, routes, busy, cal = {}, {}, {}, Counter()
    raw = {}
    for u, v in seq.items():
        units[u] = (v[0][0], v[0][1])
        drops = [h for h, p, op in v if p in LS.SHED and op in ('DROP', 'PLACE')]
        last_drop = drops[-1] if drops else -1
        jobs, cur, pos = [], None, None
        for h, p, op in v:
            if LS.is_work(p, op) and cur is not None and p == pos:
                cur[1].append(op)
            elif LS.is_work(p, op):
                cur, pos = [h, [op]], p
                jobs.append((p, cur))
            else:
                cur = None
        merged, out = {}, []
        for p, (h, ops) in jobs:
            if p in merged:
                merged[p][1].extend(ops)
                cal['same-unit revisits'] += 1
            else:
                merged[p] = [h, list(ops)]
                out.append(p)
        raw[u] = (out, merged, last_drop)
        work = [k for k, (_, _, op) in enumerate(v) if op != 'PASS']
        busy[u] = (work[-1] + 1) if work else 0
        if work:
            cal['mid-route PASS'] += sum(1 for k in range(work[-1]) if v[k][2] == 'PASS')
            cal['PICKUP commands'] += sum(1 for _, _, op in v if op == 'PICKUP')
            cal['shed DROP/PLACE commands'] += len(drops)
    starts = defaultdict(list)
    for u, (out, merged, _) in raw.items():
        for p in out:
            starts[p].append((merged[p][0], u))
    byp = defaultdict(list)                                   # tile -> jobs of all units on it
    for u, (out, merged, last_drop) in raw.items():
        routes[u] = []
        for p in out:
            h, ops = merged[p]
            job = DJob(p, ops, today=h < last_drop and any(o in ('HARVEST', 'COLLECT_FERTILIZER') for o in ops),
                       release=h if any(o in LS.BOUGHT for o in ops) else 0)
            ORIG[id(job)] = (h, u)
            routes[u].append(job)
            byp[p].append(job)
    # order pairs (earlier E, later L: different units, same tile, E started strictly earlier). Threshold T_E per
    # earlier job, fixed point: T_E = max(E's actual hour, E's start in the model timing of the actual routes), with
    # L.release >= max T_E of its earlier jobs and E.due = T_E. Then start(E) <= T_E <= start(L) in ANY arrangement,
    # and every unit's own actual route stays feasible unless its release waits push it past midnight.
    prior, earlier = {}, set()
    for p, js in byp.items():
        for L in js:
            hl, ul = ORIG[id(L)]
            pr = [E for E in js if ORIG[id(E)][1] != ul and ORIG[id(E)][0] < hl]
            if pr:
                prior[id(L)] = pr
                earlier.update(id(E) for E in pr)
                cal['tiles worked by two units'] += 1
    base_rel = {id(j): j.release for r in routes.values() for j in r}
    T = {i: None for i in earlier}
    for j in (j for r in routes.values() for j in r):
        if id(j) in earlier:
            T[id(j)] = ORIG[id(j)][0]
    for _ in range(100):
        for r in routes.values():
            for j in r:
                if id(j) in prior:
                    j.release = max(base_rel[id(j)], max(T[id(E)] for E in prior[id(j)]))
        stt = {}
        for u, r in routes.items():
            stt.update(starts_of(units[u], r))
        newT = {i: max(ORIG_H, stt[i]) for i, ORIG_H in ((i, T[i]) for i in T)}
        if newT == T:
            break
        T = newT
    for r in routes.values():
        for j in r:
            if id(j) in earlier:
                j.due = T[id(j)]
    return units, routes, busy, cal


ORIG = {}
STRUCT = ('PLANT', 'PLACE', 'BUILD_PASTURE', 'BUILD_COOP', 'DIG', 'HARVEST')


def starts_of(unit, route):
    """start hour of every job in labour_search.finish's timing."""
    out = {}
    if not route:
        return out
    t, pos = unit
    need = bal = 0
    for j in route:
        bal -= j.fert
        need = max(need, -bal)
    t += (any(j.wheat for j in route)) + (need > 0) + (any(j.animal for j in route))
    last_today = max((k for k, j in enumerate(route) if j.today), default=-1)
    for k, j in enumerate(route):
        t = max(t + LS.d(pos, j.tile), j.release)
        out[id(j)] = t
        t += j.n
        pos = j.tile
        if k == last_today:
            q = LS.home(pos)
            t += LS.d(pos, q) + 1
            pos = q
    return out


def order_violations(units, routes):
    """Pairs of jobs on one tile that different units did in the actual day (earlier E, later L) whose order the
    solution reverses (start L < start E): the model only bounds L below by E's actual hour, not E above."""
    st_, tile = {}, defaultdict(list)
    for u, r in routes.items():
        st_.update(starts_of(units[u], r))
        for j in r:
            if id(j) in ORIG:
                tile[j.tile].append(j)
    pairs = bad = bad_struct = 0
    for p, js in tile.items():
        for a in js:
            for b in js:
                ha, ua = ORIG[id(a)]
                hb, ub = ORIG[id(b)]
                if ua != ub and ha < hb:
                    pairs += 1
                    if st_[id(b)] < st_[id(a)]:
                        bad += 1
                        if any(o in STRUCT for o in a.ops + b.ops):
                            bad_struct += 1
    return dict(pairs=pairs, reversed=bad, reversed_struct=bad_struct)


# ------------------------------------------------------------------ model helpers
def parts(unit, route):
    """labour_search.finish split into (finish, travel, commands, pickups, drop steps, wait)."""
    if not route:
        return unit[0], 0, 0, 0, 0, 0
    t, pos = unit
    need = bal = 0
    for j in route:
        bal -= j.fert
        need = max(need, -bal)
    pk = (any(j.wheat for j in route)) + (need > 0) + (any(j.animal for j in route))
    t += pk
    travel = cmds = drop = wait = 0
    last_today = max((k for k, j in enumerate(route) if j.today), default=-1)
    for k, j in enumerate(route):
        dd = LS.d(pos, j.tile)
        travel += dd
        arr = t + dd
        if j.release > arr:
            wait += j.release - arr
        t = max(arr, j.release) + j.n
        cmds += j.n
        pos = j.tile
        if k == last_today:
            q = LS.home(pos)
            travel += LS.d(pos, q)
            drop += 1
            t += LS.d(pos, q) + 1
            pos = q
    return t, travel, cmds, pk, drop, wait


def cost(units, u, r):
    return (LS.finish(units[u], r) - units[u][0]) if r else 0


def totals(units, routes):
    agg = Counter()
    for u, r in routes.items():
        f, tr, cm, pk, dr, wt = parts(units[u], r)
        agg['busy'] += (f - units[u][0]) if r else 0
        agg['travel'] += tr
        agg['cmds'] += cm
        agg['pickups'] += pk
        agg['drops'] += dr
        agg['wait'] += wt
        agg['jobs'] += len(r)
    return agg


def minsum(units, routes, budget, rng, frozen):
    """Min total busy steps at the same units: improve, relocate descent, then spatial ruin-and-recreate."""
    t0 = time.perf_counter()
    free = [u for u in routes if u not in frozen]
    R = {u: (list(r) if u in frozen else LS.improve(units[u], list(r))) for u, r in routes.items()}
    C = {u: cost(units, u, R[u]) for u in R}
    trace = [(time.perf_counter() - t0, sum(C.values()))]

    def over():
        return time.perf_counter() - t0 > budget

    # relocate descent
    moved = True
    while moved and not over():
        moved = False
        for a in free:
            i = 0
            while i < len(R[a]) and not over():
                j = R[a][i]
                ra = R[a][:i] + R[a][i + 1:]
                ca = cost(units, a, ra)
                gain = C[a] - ca
                best = (0, None, None)
                for b in free:
                    if b == a:
                        continue
                    rb, sb = R[b], units[b][0]
                    for k in range(len(rb) + 1):
                        f = LS.finish(units[b], rb[:k] + [j] + rb[k:])
                        if f <= 24:
                            dl = (f - sb) - C[b] - gain
                            if dl < best[0]:
                                best = (dl, b, k)
                if best[1] is not None:
                    _, b, k = best
                    R[a], C[a] = ra, ca
                    R[b] = LS.improve(units[b], R[b][:k] + [j] + R[b][k:])
                    C[b] = cost(units, b, R[b])
                    moved = True
                    trace.append((time.perf_counter() - t0, sum(C.values())))
                    continue
                i += 1
    # ruin and recreate
    best_R, best_tot = {u: list(r) for u, r in R.items()}, sum(C.values())
    cur_tot = best_tot
    iters = 0
    while not over():
        pool_all = [(u, j) for u in free for j in R[u]]
        if len(pool_all) < 3:
            break
        iters += 1
        seed = rng.choice(pool_all)[1]
        k = rng.randint(3, min(10, len(pool_all)))
        near = sorted(pool_all, key=lambda uj: LS.d(uj[1].tile, seed.tile) + rng.random() * 1.5)[:k]
        take = {id(j) for _, j in near}
        ruined = {u: [j for j in r if id(j) not in take] for u, r in R.items()}
        new = LS.insert_all([j for _, j in near], ruined, units, set(frozen), rng)
        if new is None:
            continue
        touched = {u for u, _ in near} | {u for u in free if new[u] != ruined[u]}
        for u in touched:
            if u not in frozen:
                new[u] = LS.improve(units[u], new[u])
        nc = {u: cost(units, u, new[u]) for u in new}
        tot = sum(nc.values())
        if tot <= cur_tot:
            R, C, cur_tot = new, nc, tot
            if tot < best_tot:
                best_R, best_tot = {u: list(r) for u, r in R.items()}, tot
                trace.append((time.perf_counter() - t0, tot))
    return best_R, time.perf_counter() - t0, trace, iters


def insert_value(extra, routes, units, frozen, vals):
    """Insert extra jobs by value (highest first), cheapest feasible position, route re-optimised after each insert;
    a second pass retries the rest. Returns the inserted jobs."""
    R = {u: list(r) for u, r in routes.items()}
    C = {u: cost(units, u, R[u]) for u in R}
    left = sorted(extra, key=lambda j: -vals[id(j)])
    placed = []
    for _ in range(2):
        rest = []
        for j in left:
            best = None
            for u, r in R.items():
                if u in frozen:
                    continue
                for k in range(len(r) + 1):
                    f = LS.finish(units[u], r[:k] + [j] + r[k:])
                    if f <= 24:
                        dl = (f - units[u][0]) - C[u]
                        if best is None or dl < best[0]:
                            best = (dl, u, k)
            if best is None:
                rest.append(j)
                continue
            _, u, k = best
            R[u] = LS.improve(units[u], R[u][:k] + [j] + R[u][k:])
            C[u] = cost(units, u, R[u])
            placed.append(j)
        left = rest
        if not left:
            break
    return placed


def wages(n_hired, n_drop):
    return sum(LS.FIB[min(16, n_hired - 1 - i)] for i in range(n_drop))


# ------------------------------------------------------------------ loading
def load_ours():
    games = []
    for ep in SMOKE:
        f = TR / f'lead_world_trace/mgt_lpv_mpt0_{ep}.json'
        d = json.load(open(f, encoding='utf-8'))
        games.append(dict(side='ours', ep=ep, seat=d['seat'], margin=d['margin'], file=str(f.relative_to(ROOT)),
                          actions=[json.loads(x) for x in d['actions']]))
    # tracer files -> episodes by per-day command counts
    recs = {}
    for f in sorted((TR / 'lead_idle/mp0').glob('*.jsonl')):
        recs[f] = [json.loads(x) for x in open(f, encoding='utf-8')]
    sims = {g['ep']: sim_from_actions(g['actions']) for g in games}
    keys = ('move', 'op_WATER', 'op_FEED', 'op_CARE', 'op_HARVEST', 'op_FERTILIZE', 'pass')
    used = set()
    for g in games:
        sim = sims[g['ep']]
        best = None
        for f, rr in recs.items():
            if f in used:
                continue
            ok = sum(1 for r in rr if all(r['work'].get(k, 0) == day_counts(sim, r['day']).get(k, 0) for k in keys))
            if best is None or ok > best[0]:
                best = (ok, f)
        g['tracer'] = {r['day']: r for r in recs[best[1]]}
        g['tracer_file'] = str(best[1].relative_to(ROOT))
        g['tracer_match_days'] = best[0]
        g['tracer_seat'] = int(best[1].stem.split('_')[-1])
        used.add(best[1])
        g['sim'] = sim
    return games


def load_leader():
    games = []
    for gname in lead_g1.GAMES:
        team, ep = gname.split(':')
        tp = next(p for p in sorted(lead_g1.TAPES.glob(f'{team}_*/{ep}.json.gz')))
        t = json.load(gzip.open(tp, 'rt', encoding='utf-8'))
        acts = [a if isinstance(a, dict) else {} for a in t['actions']]
        games.append(dict(side='leader', ep=int(ep), team=lead_g1.TEAM[team], seat=t['seat'],
                          file=str(tp.relative_to(ROOT)), actions=acts, sim=sim_from_actions(acts)))
    return games


def check_positions(g):
    """tracer idle records carry the unit position at decision time: compare with the rebuilt positions."""
    ok = bad = 0
    for day, r in g.get('tracer', {}).items():
        for h, u, pos, *_ in r['idle']:
            s = g['sim'].get(day * 24 + h)
            if s is None or u >= len(s):
                bad += 1
                continue
            if (s[u][0], s[u][1]) == tuple(pos):
                ok += 1
            else:
                bad += 1
    return ok, bad


# ------------------------------------------------------------------ per day
def run_day(g, day, rng, long_budget=None):
    u_ls, r_ls, _, _ = LS.instance(g['sim'], day)          # labour_search exactly (unit-index order constraint)
    frozen_ls = sum(1 for u in u_ls if _finish_orig(u_ls[u], r_ls[u]) > 24)
    model_ls = sum((_finish_orig(u_ls[u], r_ls[u]) - u_ls[u][0]) if r_ls[u] else 0 for u in u_ls)
    ORIG.clear()
    units, routes, busy, cal = instance_timeorder(g['sim'], day)
    if not units:
        return None
    row_order0 = order_violations(units, routes)
    act = actual_parts(g['sim'], day)
    model = {u: cost(units, u, routes[u]) for u in units}
    fin = {u: LS.finish(units[u], routes[u]) for u in units}
    frozen = {u for u in units if fin[u] > 24}
    hired = [u for u in units if u > 0]
    worked = [u for u in hired if routes[u]]
    row = dict(side=g['side'], ep=g['ep'], day=day, units=len(units), hired=len(hired), worked=len(worked),
               idle_hands=len(hired) - len(worked), frozen=len(frozen), frozen_ls=frozen_ls, model_ls=model_ls, cal=dict(cal),
               present_steps=sum(act[u]['present'] for u in units),
               actual_busy=sum(busy.values()), actual_moves=sum(act[u]['moves'] for u in units),
               actual_work=sum(act[u]['work'] for u in units), actual_shed=sum(act[u]['shed'] for u in units),
               actual_pass=sum(act[u]['pass'] for u in units))
    base = totals(units, routes)
    row['model'] = dict(base)
    ud = []
    for u in units:
        f, tr, cm, pk, dr, wt = parts(units[u], routes[u])
        ud.append(dict(u=u, start=units[u][0], jobs=len(routes[u]), model=model[u], actual=busy[u], finish=f, travel=tr,
                       cmds=cm, pickups=pk, drops=dr, wait=wt, moves=act[u]['moves'], work=act[u]['work'],
                       shed=act[u]['shed'], passes=act[u]['pass'],
                       nrel=sum(1 for j in routes[u] if j.release > 0)))
    row['unit_days'] = ud
    row['order_actual'] = row_order0
    # frozen diagnosis: does the unit fit when the releases (purchase / other-unit order) are ignored?
    diag = []
    for u in frozen:
        r0 = [DJob(j.tile, j.ops, today=j.today) for j in routes[u]]
        diag.append(dict(u=u, finish=fin[u], actual=busy[u], start=units[u][0], jobs=len(routes[u]),
                         finish_no_release=LS.finish(units[u], r0),
                         finish_no_due=LS.finish(units[u], [DJob(j.tile, j.ops, today=j.today, release=j.release) for j in routes[u]])))
    row['frozen_diag'] = diag
    # (a) min-sum at the same units
    row['a'] = {}
    best_routes = None
    for b in BUDGETS + ((long_budget,) if long_budget else ()):
        R, secs, trace, iters = minsum(units, routes, b, rng, frozen)
        tt = totals(units, R)
        tot = tt['busy']
        t95 = next((t for t, c in trace if base['busy'] - c >= 0.95 * (base['busy'] - tot)), 0.0) if base['busy'] > tot else 0.0
        row['a'][str(b)] = dict(model=dict(tt), secs=secs, rr_iters=iters, t95=t95,
                                emptied=sum(1 for u in hired if routes[u] and not R[u]),
                                order=order_violations(units, R))
        if b == 1.0:
            best_routes = R
    # (b) hands dropped with all jobs done
    row['b'] = {}
    for b in BUDGETS:
        t0 = time.perf_counter()
        new, dropped = LS.search(units, routes, b, rng, frozen)
        secs = time.perf_counter() - t0
        saved = len([u for u in dropped if routes[u]])
        row['b'][str(b)] = dict(saved=saved, secs=secs, wage_saved=wages(len(hired), saved),
                                wage_saved_incl_idle=wages(len(hired), saved + row['idle_hands']),
                                busy_after=totals(units, new)['busy'])
    row['wage_paid'] = wages(len(hired), len(hired))
    # (c) tracer's dropped jobs
    tr = g.get('tracer', {}).get(day)
    if tr is not None:
        vals, meta, extra = {}, {}, []
        for jd in tr['dropped']:
            idx = jd['idx']
            rel = jd['first_open'] if jd.get('first_open') is not None else 0
            j = DJob((idx % 10, idx // 10), [jd['cmd']], release=rel)
            vals[id(j)] = jd['value']
            meta[id(j)] = jd
            extra.append(j)

        def summ(placed):
            s = Counter()
            for j in placed:
                m = meta[id(j)]
                s['n'] += 1
                s['value'] += m['value']
                s['units'] += m.get('units') or 0
                if (m.get('units') or 0) > 0:
                    s['n_prod'] += 1
                    s['v_prod'] += m['value']
                s['n_' + m['cmd']] += 1
                s['v_' + m['cmd']] += m['value']
                s['n_in_task' if m['in_task'] else 'n_not_in_task'] += 1
                s['v_in_task' if m['in_task'] else 'v_not_in_task'] += m['value']
                reasons = Counter(p[2] for p in m['idle']) if m['idle'] else Counter()
                if any(str(k).startswith('lack') for k in reasons):
                    s['n_lack_seen'] += 1
            return dict(s)
        row['c'] = dict(all=summ(extra),
                        fit_actual=summ(insert_value(extra, routes, units, frozen, vals)),
                        fit_search=summ(insert_value(extra, best_routes, units, frozen, vals)))
    return row


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else 'both'
    maxg = int(sys.argv[2]) if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else 99
    long_budget = float(sys.argv[sys.argv.index('--long') + 1]) if '--long' in sys.argv else None
    every = int(sys.argv[sys.argv.index('--every') + 1]) if '--every' in sys.argv else 1
    games = []
    if which in ('ours', 'both'):
        games += load_ours()[:maxg]
    if which in ('leader', 'both'):
        games += load_leader()[:maxg]
    rng = random.Random(20260925)
    tag = which + ('' if maxg == 99 else f'_g{maxg}') + (f'_long{long_budget:g}_e{every}' if long_budget else '')
    out = HERE / f'rows_{tag}.jsonl'
    meta = []
    t_start = time.perf_counter()
    with open(out, 'w', encoding='utf-8') as fo:
        for gi, g in enumerate(games):
            ok, bad = check_positions(g)
            m = dict(side=g['side'], ep=g['ep'], seat=g['seat'], file=g['file'], pos_check_ok=ok, pos_check_bad=bad)
            for k in ('tracer_file', 'tracer_match_days', 'tracer_seat', 'margin', 'team'):
                if k in g:
                    m[k] = g[k]
            meta.append(m)
            for day in range(0, 30, every):
                row = run_day(g, day, rng, long_budget)
                if row is not None:
                    fo.write(json.dumps(row) + '\n')
                    fo.flush()
            print(f'{gi + 1}/{len(games)} {g["side"]} {g["ep"]} pos {ok}/{ok + bad} '
                  f'{time.perf_counter() - t_start:.0f}s', flush=True)
    (HERE / f'meta_{tag}.json').write_text(json.dumps(meta, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
