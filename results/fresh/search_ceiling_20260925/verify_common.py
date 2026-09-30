"""Independent skeptic re-implementation for the search-ceiling report (2026-09-25).

Written from the engine source (kaggle_environments/envs/kaggriculture/kaggriculture.py) and the report's stated model;
it does NOT import scripts/labour_search.py or search_ceiling.py. Stored data only.

  rebuild()     unit positions from the returned action dicts (engine _spawn_hand: least-occupied shed-access tile,
                NWSE order; farmer back to (4,4) at hour 0; a hand exists once the returned hands list covers it)
  unit_day()    one unit's (hour, pos_before, op, cmd) sequence for a day
  jobs()        tile jobs of one unit-day, with switches for the choices that matter:
                  merge=True     same unit back on a tile later the same day -> one job at the FIRST stay (report/LS)
                  merge=False    every stay its own job
                  strict_rel     purchase release (PLANT/PLACE/BUILD_*) = hour of the stay that holds that op
                                 (report/LS: the first stay's hour even when the PLANT happened at a later stay)
  Model         route time = start + one step per item type picked (wheat if any FEED, fertilizer if the running
                balance goes negative, animal if any PLACE) + Manhattan travel + one step per command; release waits;
                after the last 'today' job (HARVEST/COLLECT before the unit's last shed drop) walk to the nearest
                shed tile + 1 DROP step; a job starting after its due hour -> infeasible.
  order         jobs of different units on one tile: earlier E (strictly earlier actual first hour), later L.
                T_E fixed point = max(actual hour, E's start in the model timing of the actual routes);
                L.release >= T_E, E.due = T_E  (the report's order-safe version, re-coded).
"""
import gzip
import json
import random
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TR = ROOT / 'results/fresh/kaggle_remote_lead/wtr7/output/kgr-wtr7-s0/out/repo/results/fresh'
SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]
SHEDSET = set(SHED)
MV = {'NORTH': (0, -1), 'SOUTH': (0, 1), 'EAST': (1, 0), 'WEST': (-1, 0)}
BOUGHT = {'PLANT', 'PLACE', 'BUILD_PASTURE', 'BUILD_COOP'}
OURS = [110937191, 111374151, 111376633, 111416249, 111554912, 111577649, 111681195, 111688786, 111871547,
        111902048, 111916514, 111941962]
LEADER = [('16732748', 112655730), ('16732748', 112661570), ('16732748', 112667461), ('16732748', 112673479),
          ('16770421', 112708229), ('16770421', 112714050), ('16770421', 112715010), ('16770421', 112721923),
          ('16730612', 112444381), ('16730612', 112445586), ('16730612', 112447950), ('16730612', 112449129)]


def dist(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def near_shed(p):
    return min(SHED, key=lambda q: (dist(p, q), SHED.index(q)))


def spawn(pos):
    occ = {s: 0 for s in SHED}
    for p in pos:
        if p in occ:
            occ[p] += 1
    return min(SHED, key=lambda s: (occ[s], SHED.index(s)))


# ------------------------------------------------------------------ loading
def load_ours(ep):
    d = json.load(open(TR / f'lead_world_trace/mgt_lpv_mpt0_{ep}.json', encoding='utf-8'))
    acts = [json.loads(x) if isinstance(x, str) else x for x in d['actions']]
    return dict(side='ours', ep=ep, seat=d['seat'], actions=[a if isinstance(a, dict) else {} for a in acts], raw=d)


def load_leader(team, ep):
    tp = sorted((ROOT / 'data/leader_tapes').glob(f'{team}_*/{ep}.json.gz'))[0]
    t = json.load(gzip.open(tp, 'rt', encoding='utf-8'))
    return dict(side='leader', ep=ep, seat=t['seat'], actions=[a if isinstance(a, dict) else {} for a in t['actions']],
                raw=t, team=team)


def load_tracer_files():
    out = {}
    for f in sorted((TR / 'lead_idle/mp0').glob('*.jsonl')):
        out[f.name] = [json.loads(x) for x in open(f, encoding='utf-8')]
    return out


# ------------------------------------------------------------------ rebuild
def rebuild(actions, nsteps=719):
    """days[d][u] = [(hour, pos_before, op, cmd)], plus per-step position lists."""
    days = [defaultdict(list) for _ in range(30)]
    pos_at = {}
    pos = []
    for t in range(min(nsteps, len(actions))):
        d, h = divmod(t, 24)
        if h == 0:
            pos = [(4, 4)]
        a = actions[t]
        hands = a.get('hands') or []
        if not isinstance(hands, list):
            hands = []
        while len(pos) - 1 < len(hands):
            pos.append(spawn(pos))
        cmds = [a.get('farmer') or ['PASS']] + [x if isinstance(x, list) and x else ['PASS'] for x in hands]
        pos_at[t] = list(pos)
        for u in range(len(pos)):
            c = cmds[u] if u < len(cmds) else ['PASS']
            if not isinstance(c, list) or not c:
                c = ['PASS']
            op = c[0]
            days[d][u].append((h, pos[u], op, c))
            if op in MV:
                nx, ny = pos[u][0] + MV[op][0], pos[u][1] + MV[op][1]
                if 0 <= nx < 10 and 0 <= ny < 10:
                    pos[u] = (nx, ny)
    return days, pos_at


ONE_TIME = {'WHEAT', 'CARROT', 'MELON'}


def harvest_crops(days):
    """crop of every HARVEST command from the PLANT history of the rebuilt stream: {day: {(unit, hour): crop}}
    (tile crop set by PLANT on a tile with no crop, cleared by HARVEST of a one-time crop or DIG)."""
    crop, out = {}, {}
    for d in range(30):
        ev = []
        for u, seq in days[d].items():
            for h, p, op, cmd in seq:
                if op in ('PLANT', 'HARVEST', 'DIG'):
                    ev.append((h, u, p, op, cmd))
        ev.sort(key=lambda e: (e[0], e[1]))
        o = {}
        for h, u, p, op, cmd in ev:
            if op == 'PLANT' and p not in crop and len(cmd) > 1:
                crop[p] = cmd[1]
            elif op == 'HARVEST':
                c = crop.get(p)
                o[(u, h)] = c
                if c in ONE_TIME:
                    crop.pop(p, None)
            elif op == 'DIG':
                crop.pop(p, None)
        out[d] = o
    return out


def is_work(p, op):
    return op not in MV and op not in ('PASS', 'PICKUP', 'DROP') and not (op == 'PLACE' and p in SHEDSET)


def busy_of(seq):
    w = [k for k, (h, p, op, c) in enumerate(seq) if op != 'PASS']
    return (w[-1] + 1) if w else 0


# ------------------------------------------------------------------ jobs
class J:
    __slots__ = ('tile', 'n', 'wheat', 'fert', 'animal', 'today', 'release', 'due', 'h', 'u', 'ops', 'tag', 'val', 'wg')

    def __init__(self, tile, ops, h=0, u=-1, today=False, release=0, due=99, tag=None, val=0.0, wg=0):
        self.tile, self.ops, self.n = tile, list(ops), len(ops)
        self.wheat = sum(1 for o in ops if o == 'FEED')
        self.fert = sum(1 for o in ops if o == 'FERTILIZE') - sum(1 for o in ops if o == 'COLLECT_FERTILIZER')
        self.animal = sum(1 for o in ops if o == 'PLACE')
        self.today, self.release, self.due, self.h, self.u, self.tag, self.val = today, release, due, h, u, tag, val
        self.wg = wg


WHEAT_FLOW = [False]      # switch: True = a job that HARVESTs wheat gives WHEAT_GAIN wheat (pickup only on a deficit)
WHEAT_GAIN = 3


def npick(route):
    """pickup steps at the route start: wheat, fertilizer, animal."""
    bal = need = 0
    wb = wneed = 0
    anyw = animal = False
    for j in route:
        bal -= j.fert
        if -bal > need:
            need = -bal
        wb -= j.wheat
        if -wb > wneed:
            wneed = -wb
        wb += j.wg
        if j.wheat:
            anyw = True
        if j.animal:
            animal = True
    w = (wneed > 0) if WHEAT_FLOW[0] else anyw
    return w + (need > 0) + animal


def jobs(seq, u, merge=True, strict_rel=False, hcrop=None):
    """tile jobs of one unit-day in first-visit order."""
    drops = [h for h, p, op, c in seq if p in SHEDSET and op in ('DROP', 'PLACE')]
    last_drop = drops[-1] if drops else -1
    stays, cur = [], None
    for h, p, op, c in seq:
        if is_work(p, op):
            if cur is not None and cur[0] == p:
                cur[2].append((h, op))
            else:
                cur = [p, h, [(h, op)]]
                stays.append(cur)
        else:
            cur = None
    groups = []
    if merge:
        by = {}
        for s in stays:
            if s[0] in by:
                by[s[0]][2].extend(s[2])
            else:
                g = [s[0], s[1], list(s[2])]
                by[s[0]] = g
                groups.append(g)
    else:
        groups = [[s[0], s[1], list(s[2])] for s in stays]
    out = []
    for p, h, hops in groups:
        ops = [o for _, o in hops]
        wg = 0
        if hcrop is not None:
            wg = WHEAT_GAIN * sum(1 for hh, o in hops if o == 'HARVEST' and hcrop.get((u, hh)) == 'WHEAT')
        if strict_rel:
            # the purchase op may not happen before its actual hour: start + (its index in the job) >= its hour
            rel = max([hh - k for k, (hh, o) in enumerate(hops) if o in BOUGHT], default=0)
            today = any(o in ('HARVEST', 'COLLECT_FERTILIZER') and hh < last_drop for hh, o in hops)
        else:
            rel = h if any(o in BOUGHT for o in ops) else 0
            today = h < last_drop and any(o in ('HARVEST', 'COLLECT_FERTILIZER') for o in ops)
        out.append(J(p, ops, h=h, u=u, today=today, release=rel, wg=wg))
    return out


# ------------------------------------------------------------------ model
def finish(unit, route):
    """unit = (first hour, spawn tile). Route end hour (99 = a due hour violated)."""
    t, pos = unit
    if not route:
        return t
    lt = -1
    for k, j in enumerate(route):
        if j.today:
            lt = k
    t += npick(route)
    for k, j in enumerate(route):
        t += abs(pos[0] - j.tile[0]) + abs(pos[1] - j.tile[1])
        if t < j.release:
            t = j.release
        if t > j.due:
            return 99
        t += j.n
        pos = j.tile
        if k == lt:
            q = near_shed(pos)
            t += dist(pos, q) + 1
            pos = q
    return t


def starts(unit, route):
    t, pos = unit
    out = {}
    if not route:
        return out
    t += npick(route)
    lt = max((k for k, j in enumerate(route) if j.today), default=-1)
    for k, j in enumerate(route):
        t = max(t + dist(pos, j.tile), j.release)
        out[id(j)] = t
        t += j.n
        pos = j.tile
        if k == lt:
            q = near_shed(pos)
            t += dist(pos, q) + 1
            pos = q
    return out


def breakdown(unit, route):
    """(finish, travel, cmds, pickups, drops, wait)"""
    t, pos = unit
    if not route:
        return t, 0, 0, 0, 0, 0
    pk = npick(route)
    t += pk
    tr = cm = dr = wt = 0
    lt = max((k for k, j in enumerate(route) if j.today), default=-1)
    for k, j in enumerate(route):
        dd = dist(pos, j.tile)
        tr += dd
        a = t + dd
        wt += max(0, j.release - a)
        t = max(a, j.release) + j.n
        cm += j.n
        pos = j.tile
        if k == lt:
            q = near_shed(pos)
            tr += dist(pos, q)
            dr += 1
            t += dist(pos, q) + 1
            pos = q
    return t, tr, cm, pk, dr, wt


def cost(unit, route):
    return (finish(unit, route) - unit[0]) if route else 0


# ------------------------------------------------------------------ one day instance
def instance(day_units, merge=True, strict_rel=False, order='time', hcrop=None):
    """units {u: (first hour, first pos)}, routes {u: [J]} (actual order), busy {u}, info Counter.
    order='time'  : report's order-safe constraint (T_E fixed point, E.due and L.release).
    order='unit'  : labour_search's constraint (first unit by INDEX that has a job on the tile sets the release of
                    every later-index unit's job there, whatever the hours; no due)."""
    units, routes, busy, info = {}, {}, {}, Counter()
    for u in sorted(day_units):
        seq = day_units[u]
        units[u] = (seq[0][0], seq[0][1])
        routes[u] = jobs(seq, u, merge=merge, strict_rel=strict_rel, hcrop=hcrop)
        busy[u] = busy_of(seq)
    if order == 'unit':
        first = {}
        for u in sorted(routes):
            for j in routes[u]:
                if j.tile in first and first[j.tile][0] != u:
                    j.release = max(j.release, first[j.tile][1])
                first.setdefault(j.tile, (u, j.h))
        return units, routes, busy, info
    bytile = defaultdict(list)
    for u, r in routes.items():
        for j in r:
            bytile[j.tile].append(j)
    prior, early = {}, {}
    for p, js in bytile.items():
        for L in js:
            pr = [E for E in js if E.u != L.u and E.h < L.h]
            if pr:
                prior[id(L)] = (L, pr)
                for E in pr:
                    early[id(E)] = E
                info['order_pairs_L'] += 1
    base = {id(j): j.release for r in routes.values() for j in r}
    T = {i: E.h for i, E in early.items()}
    for _ in range(200):
        for i, (L, pr) in prior.items():
            L.release = max(base[i], max(T[id(E)] for E in pr))
        st = {}
        for u, r in routes.items():
            st.update(starts(units[u], r))
        new = {i: max(T[i], st[i]) for i in T}
        if new == T:
            break
        T = new
    for i, E in early.items():
        E.due = T[i]
    return units, routes, busy, info


# ------------------------------------------------------------------ search (own ILS; different from search_ceiling.minsum)
class Search:
    """Min total busy steps at the same units; all routes end <= cap (24). Moves: intra 2-opt / or-opt(1-3),
    inter relocate (best position), inter swap (best positions), perturbation = remove k jobs (random seed + its
    spatial neighbours, or random) and re-insert by cheapest insertion in random order; accept if <= current + tol
    (tol decays), keep the best."""

    def __init__(self, units, routes, frozen, cap=24, rng=None):
        self.units, self.frozen, self.cap = units, set(frozen), cap
        self.free = [u for u in routes if u not in self.frozen]
        self.R = {u: list(r) for u, r in routes.items()}
        self.rng = rng or random.Random(1)
        self.C = {u: cost(units[u], self.R[u]) for u in self.R}

    def ok(self, u, r):
        f = finish(self.units[u], r)
        return f if f <= self.cap else None

    def c_of(self, u, r):
        if not r:
            return 0
        f = finish(self.units[u], r)
        return (f - self.units[u][0]) if f <= self.cap else None

    def intra(self, u, r):
        best = self.c_of(u, r)
        if best is None or len(r) < 2:
            return r, best
        improved = True
        while improved:
            improved = False
            n = len(r)
            for L in (1, 2, 3):
                for i in range(n - L + 1):
                    seg = r[i:i + L]
                    rest = r[:i] + r[i + L:]
                    for k in range(len(rest) + 1):
                        if k == i:
                            continue
                        for s in ((seg, seg[::-1]) if L > 1 else (seg,)):
                            cand = rest[:k] + s + rest[k:]
                            c = self.c_of(u, cand)
                            if c is not None and c < best:
                                r, best, improved = cand, c, True
                                break
                        if improved:
                            break
                    if improved:
                        break
                if improved:
                    break
            if improved:
                continue
            for i in range(n - 1):
                for k in range(i + 1, n):
                    cand = r[:i] + r[i:k + 1][::-1] + r[k + 1:]
                    c = self.c_of(u, cand)
                    if c is not None and c < best:
                        r, best, improved = cand, c, True
                        break
                if improved:
                    break
        return r, best

    def local(self, R, C, deadline):
        for u in self.free:
            R[u], C[u] = self.intra(u, R[u])
        improved = True
        while improved and time.perf_counter() < deadline:
            improved = False
            # relocate
            for a in self.free:
                i = 0
                while i < len(R[a]) and time.perf_counter() < deadline:
                    j = R[a][i]
                    ra = R[a][:i] + R[a][i + 1:]
                    ca = self.c_of(a, ra)
                    if ca is None:
                        i += 1
                        continue
                    gain = C[a] - ca
                    best = None
                    for b in self.free:
                        if b == a:
                            continue
                        for k in range(len(R[b]) + 1):
                            cb = self.c_of(b, R[b][:k] + [j] + R[b][k:])
                            if cb is not None and cb - C[b] - gain < (best[0] if best else 0):
                                best = (cb - C[b] - gain, b, k, cb)
                    if best:
                        _, b, k, cb = best
                        R[a], C[a] = self.intra(a, ra)
                        R[b], C[b] = self.intra(b, R[b][:k] + [j] + R[b][k:])
                        improved = True
                    else:
                        i += 1
            # swap
            if time.perf_counter() >= deadline:
                break
            fr = self.free
            for ai in range(len(fr)):
                a = fr[ai]
                for bi in range(ai + 1, len(fr)):
                    b = fr[bi]
                    done = False
                    for i in range(len(R[a])):
                        for k in range(len(R[b])):
                            ra = R[a][:i] + [R[b][k]] + R[a][i + 1:]
                            rb = R[b][:k] + [R[a][i]] + R[b][k + 1:]
                            ca, cb = self.c_of(a, ra), self.c_of(b, rb)
                            if ca is not None and cb is not None and ca + cb < C[a] + C[b]:
                                R[a], C[a] = self.intra(a, ra)
                                R[b], C[b] = self.intra(b, rb)
                                improved = done = True
                                break
                        if done:
                            break
                    if time.perf_counter() >= deadline:
                        break
        return R, C

    def run(self, budget):
        t0 = time.perf_counter()
        deadline = t0 + budget
        R, C = {u: list(r) for u, r in self.R.items()}, dict(self.C)
        R, C = self.local(R, C, deadline)
        best = ({u: list(r) for u, r in R.items()}, sum(C.values()))
        cur = best[1]
        trace = [(time.perf_counter() - t0, cur)]
        rng = self.rng
        it = 0
        while time.perf_counter() < deadline:
            it += 1
            pool = [(u, j) for u in self.free for j in R[u]]
            if len(pool) < 2:
                break
            k = rng.randint(2, min(8, len(pool)))
            if rng.random() < 0.7:
                seed = rng.choice(pool)[1]
                take = sorted(pool, key=lambda x: dist(x[1].tile, seed.tile) + rng.random() * 2)[:k]
            else:
                take = rng.sample(pool, k)
            ids = {id(j) for _, j in take}
            R2 = {u: [j for j in r if id(j) not in ids] for u, r in R.items()}
            C2 = {u: (C[u] if u in self.frozen else self.c_of(u, R2[u])) for u in R2}
            if any(v is None for v in C2.values()):
                continue
            order = [j for _, j in take]
            rng.shuffle(order)
            fail = False
            for j in order:
                bb = None
                for b in self.free:
                    for kk in range(len(R2[b]) + 1):
                        cb = self.c_of(b, R2[b][:kk] + [j] + R2[b][kk:])
                        if cb is not None and (bb is None or cb - C2[b] < bb[0]):
                            bb = (cb - C2[b], b, kk, cb)
                if bb is None:
                    fail = True
                    break
                _, b, kk, cb = bb
                R2[b] = R2[b][:kk] + [j] + R2[b][kk:]
                C2[b] = cb
            if fail:
                continue
            R2, C2 = self.local(R2, C2, deadline)
            tot = sum(C2.values())
            tol = 2.0 * max(0.0, 1 - (time.perf_counter() - t0) / budget)
            if tot <= cur + tol * rng.random():
                R, C, cur = R2, C2, tot
                if tot < best[1]:
                    best = ({u: list(r) for u, r in R.items()}, tot)
                    trace.append((time.perf_counter() - t0, tot))
        return best[0], best[1], trace, it


def check_solution(units, routes_before, routes_after, cap=24, frozen=()):
    """independent feasibility check of a solution: same job multiset, every route <= cap with releases / dues,
    order pairs kept (start L >= start E for every earlier/later pair on a tile), purchase releases respected."""
    a = sorted(id(j) for r in routes_before.values() for j in r)
    b = sorted(id(j) for r in routes_after.values() for j in r)
    bad = Counter()
    if a != b:
        bad['job_multiset'] += 1
    st = {}
    for u, r in routes_after.items():
        f = finish(units[u], r)
        if r and f > cap:
            bad['over_cap_frozen' if u in frozen else 'over_cap'] += 1
        st.update(starts(units[u], r))
        for j in r:
            if st[id(j)] < j.release:
                bad['release'] += 1
    bytile = defaultdict(list)
    for r in routes_after.values():
        for j in r:
            bytile[j.tile].append(j)
    pairs = 0
    for p, js in bytile.items():
        for E in js:
            for L in js:
                if E.u != L.u and E.h < L.h and E.u >= 0 and L.u >= 0:     # inserted (tracer) jobs: u = -1
                    pairs += 1
                    if st[id(L)] < st[id(E)]:
                        bad['order_reversed'] += 1
    return pairs, bad
