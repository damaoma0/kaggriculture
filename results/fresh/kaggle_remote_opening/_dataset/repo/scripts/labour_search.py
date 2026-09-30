"""Labour arrangement as a search problem: can a search match or beat Mother-Goose's crew on HER OWN daily task sets?

Offline benchmark (no games). For every tape-day the jobs are read off the tape calendar: a job = the commands one unit
gives on one tile in one stay (HARVEST, PLANT, WATER, FEED, CARE, ...). The arrangement problem: assign the jobs to the
farmer (free, acts from hour 0, starts at (4,4)) and to hired hands (the n-th hire costs fib(n); a hand exists from the
hour after its hire and spawns on a shed tile), order them, and finish every route before midnight.

Time model of a route (hours of the day): start at the unit's first hour; one PICKUP step per item type it must take
from the shed (wheat for FEED; fertilizer when it applies more than it collects on the way, in route order; an animal
for PLACE), taken at the spawn tile; then Manhattan travel + one step per command. A job that depends on a PURCHASE of
the day (PLANT, PLACE, BUILD_*) cannot start before the hour she started it (the seed / animal / cash is not there
earlier). Produce she brought to the shed the same day must be brought the same day: after the last such job the unit
walks to the nearest shed tile and DROPs (one step). Everything else rides home for free at midnight (she does that
with 86% of her produce-carrying hand-days). Jobs on the same tile are merged into one job when the same unit does
them; when different units work one tile on one day the later job may not start before the earlier one's hour.

Her own arrangement is scored in the SAME model (`model` vs `actual` = how close the model is to the steps she used;
a unit whose own route does not fit the model is left untouched).

Search: improve every route (2-opt / or-opt), then empty one hand after another by cheapest regret insertion into the
others, with ruin-and-recreate in between, inside a time budget per day.
A = hands dropped with all her jobs done; B = FEED / CARE jobs she skips that fit at her hand count.

usage: labour_search.py [every_nth_tape=8] [seconds_per_day=0.3]
Output: results/fresh/mg_tape/labour_search.json
"""
import glob
import gzip
import json
import random
import statistics as st
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ns = {}
exec(compile((ROOT / 'scripts/fragments/tape_calendar.py').read_text(encoding='utf-8'), 'tape_calendar', 'exec'), ns)
simulate, MOVES = ns['_tc_simulate'], ns['_TC_MOVES']
SHED = ((4, 4), (5, 4), (4, 5), (5, 5))
FIB = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987, 1597]
BOUGHT = ('PLANT', 'PLACE', 'BUILD_PASTURE', 'BUILD_COOP')
ANIMALS = ('sh', 'co', 'go')


def d(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def home(p):
    return min(SHED, key=lambda q: d(p, q))


class Job:
    __slots__ = ('tile', 'n', 'wheat', 'fert', 'animal', 'ops', 'today', 'release')

    def __init__(self, tile, ops, today=False, release=0):
        self.tile, self.ops, self.n = tile, ops, len(ops)
        self.wheat = sum(1 for o in ops if o == 'FEED')
        self.fert = sum(1 for o in ops if o == 'FERTILIZE') - sum(1 for o in ops if o == 'COLLECT_FERTILIZER')
        self.animal = sum(1 for o in ops if o == 'PLACE')
        self.today = today
        self.release = release


def is_work(p, op):
    return op != 'PASS' and op not in MOVES and op not in ('PICKUP', 'DROP') and not (op == 'PLACE' and p in SHED)


def instance(sim, day):
    """units {u: (first hour, spawn tile)}, her routes {u: [Job]}, her busy steps {u}, calibration counters."""
    seq = {}
    for t in range(day * 24, min(719, day * 24 + 24)):
        for u, (x, y, c) in enumerate(sim.get(t, [])):
            seq.setdefault(u, []).append((t % 24, (x, y), c[0] if c else 'PASS'))
    units, routes, busy, cal = {}, {}, {}, Counter()
    first_on_tile = {}
    for u, v in seq.items():
        units[u] = (v[0][0], v[0][1])
        drops = [h for h, p, op in v if p in SHED and op in ('DROP', 'PLACE')]
        last_drop = drops[-1] if drops else -1
        jobs, cur, pos = [], None, None
        for h, p, op in v:
            if is_work(p, op) and cur is not None and p == pos:
                cur[1].append(op)
            elif is_work(p, op):
                cur, pos = [h, [op]], p
                jobs.append((p, cur))
            else:
                cur = None
        merged = {}
        out = []
        for p, (h, ops) in jobs:                                   # the same unit on the same tile twice: one job
            if p in merged:
                merged[p][1].extend(ops)
                cal['same-unit revisits'] += 1
            else:
                merged[p] = [h, list(ops)]
                out.append(p)
        routes[u] = []
        for p in out:
            h, ops = merged[p]
            rel = h if any(o in BOUGHT for o in ops) else 0
            if p in first_on_tile and first_on_tile[p][0] != u:
                rel = max(rel, first_on_tile[p][1])                # another unit worked this tile first: keep the order
                cal['tiles worked by two units'] += 1
            first_on_tile.setdefault(p, (u, h))
            routes[u].append(Job(p, ops, today=h < last_drop and any(o in ('HARVEST', 'COLLECT_FERTILIZER') for o in ops), release=rel))
        work = [k for k, (_, _, op) in enumerate(v) if op != 'PASS']
        busy[u] = (work[-1] + 1) if work else 0
        if work:
            cal['mid-route PASS'] += sum(1 for k in range(work[-1]) if v[k][2] == 'PASS')
            cal['PICKUP commands'] += sum(1 for _, _, op in v if op == 'PICKUP')
            cal['shed DROP/PLACE commands'] += len(drops)
    return units, routes, busy, cal


def finish(unit, route):
    """Hour at which the route is done (24 = midnight)."""
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
        t = max(t + d(pos, j.tile), j.release) + j.n
        pos = j.tile
        if k == last_today:
            q = home(pos)
            t += d(pos, q) + 1
            pos = q
    return t


def improve(unit, route):
    best, bc = route, finish(unit, route)
    better = True
    while better and len(best) > 2:
        better = False
        n = len(best)
        for i in range(n - 1):
            for k in range(i + 1, n):
                r = best[:i] + best[i:k + 1][::-1] + best[k + 1:]
                c = finish(unit, r)
                if c < bc:
                    best, bc, better = r, c, True
        for i in range(n):
            j = best[i]
            rest = best[:i] + best[i + 1:]
            for k in range(len(rest) + 1):
                r = rest[:k] + [j] + rest[k:]
                c = finish(unit, r)
                if c < bc:
                    best, bc, better = r, c, True
                    break
            if better:
                break
    return best


def insert_all(jobs, routes, units, skip, rng=None, partial=False):
    """Cheapest regret insertion. Returns the new routes (None when a job does not fit), or with partial=True the
    routes and the number of jobs placed."""
    routes = {u: list(r) for u, r in routes.items()}
    left, placed = list(jobs), 0
    while left:
        options = []
        for j in left:
            cand = []
            for u, r in routes.items():
                if u in skip:
                    continue
                base = finish(units[u], r)
                for k in range(len(r) + 1):
                    c = finish(units[u], r[:k] + [j] + r[k:])
                    if c <= 24:
                        cand.append((c - base, u, k))
            if not cand:
                if partial:
                    continue
                return None
            cand.sort()
            regret = (cand[1][0] - cand[0][0]) if len(cand) > 1 else 99
            options.append((-regret + (rng.random() * 0.5 if rng else 0), cand[0], j))
        if not options:
            break
        options.sort(key=lambda o: o[0])
        _, (_, u, k), j = options[0]
        routes[u].insert(k, j)
        left.remove(j)
        placed += 1
    return (routes, placed) if partial else routes


def search(units, routes, budget, rng, frozen=()):
    routes = {u: (r if u in frozen else improve(units[u], r)) for u, r in routes.items()}
    dropped = set(u for u, r in routes.items() if u > 0 and not r)
    t0 = time.perf_counter()
    while True:
        progress = False
        hands = sorted((u for u in routes if u > 0 and u not in dropped and u not in frozen), key=lambda u: sum(j.n for j in routes[u]))
        for u in hands:
            trial = {k: v for k, v in routes.items() if k != u}
            new = insert_all(routes[u], trial, units, dropped | set(frozen) | {u})
            tries = 0
            while new is None and tries < 6 and time.perf_counter() - t0 < budget:
                tries += 1
                others = [k for k in trial if k not in dropped and k not in frozen and trial[k]]
                if not others:
                    break
                ruined, pool = dict(trial), list(routes[u])
                for k in rng.sample(others, min(3, len(others))):
                    take = rng.sample(ruined[k], max(1, len(ruined[k]) // 3))
                    ruined[k] = [j for j in ruined[k] if j not in take]
                    pool += take
                new = insert_all(pool, ruined, units, dropped | set(frozen) | {u}, rng)
            if new is not None:
                routes = {k: (r if k in frozen else improve(units[k], r)) for k, r in new.items()}
                routes[u] = []
                dropped.add(u)
                progress = True
                break
        if not progress or time.perf_counter() - t0 > budget:
            break
    return routes, dropped


def main():
    nth = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    budget = float(sys.argv[2]) if len(sys.argv) > 2 else 0.3
    rng = random.Random(20260920)
    paths = sorted(glob.glob(str(ROOT / 'data/mg_tapes/*/*.json.gz')))[::nth]
    rows, secs, cal = [], [], Counter()
    for p in paths:
        t = json.load(gzip.open(p, 'rt', encoding='utf-8'))
        acts = [a if isinstance(a, dict) else {} for a in t['actions']]
        sim = simulate(lambda s: acts[s] if s < len(acts) else {}, 0, 718, [(4, 4)])
        for day in range(3, 29):
            units, routes, busy, c = instance(sim, day)
            hands = [u for u in units if u > 0 and routes[u]]
            if len(hands) < 3:
                continue
            cal.update(c)
            model = {u: finish(units[u], routes[u]) - units[u][0] for u in units}
            frozen = {u for u in units if finish(units[u], routes[u]) > 24}
            t0 = time.perf_counter()
            new, dropped = search(units, routes, budget, rng, frozen)
            secs.append(time.perf_counter() - t0)
            board = ''.join(t['boards'][day])
            fed = {j.tile for r in routes.values() for j in r if 'FEED' in j.ops}
            cared = {j.tile for r in routes.values() for j in r if 'CARE' in j.ops}
            extras = []
            for i in range(100):
                if board[2 * i:2 * i + 2] in ANIMALS:
                    tile = (i % 10, i // 10)
                    ops = ([] if tile in fed else ['FEED']) + ([] if tile in cared else ['CARE'])
                    if ops:
                        extras.append(Job(tile, ops))
            _, fit_hers = insert_all(extras, routes, units, set(frozen), partial=True)
            _, fit_after = insert_all(extras, new, units, set(frozen) | dropped, partial=True)
            n_hired = len([u for u in units if u > 0])
            saved = len([u for u in dropped if routes[u]])
            rows.append(dict(day=day, hired=n_hired, used=len(hands), saved=saved, frozen=len(frozen),
                             wage_saved=sum(FIB[min(16, n_hired - 1 - i)] for i in range(saved)),
                             jobs=sum(len(r) for r in routes.values()), model=sum(model.values()), actual=sum(busy.values()),
                             extras=len(extras), fit_hers=fit_hers, fit_after=fit_after))
    g, n = len(paths), len(rows)
    print(f'{g} tapes, {n} tape-days (days 3-28), budget {budget}s a day')
    print(f'model check: her routes cost {sum(r["model"] for r in rows) / n:.1f} steps a day in the model, she used {sum(r["actual"] for r in rows) / n:.1f} busy steps '
          f'({cal["mid-route PASS"] / n:.1f} of them PASS before her last command, {cal["PICKUP commands"] / n:.1f} PICKUPs, {cal["shed DROP/PLACE commands"] / n:.1f} shed drops); '
          f'units left untouched because her own route does not fit the model: {sum(r["frozen"] for r in rows) / n:.2f} a day')
    print(f'   same unit back on a tile {cal["same-unit revisits"] / n:.1f} a day (merged), tiles worked by two different units {cal["tiles worked by two units"] / n:.1f} a day (order kept)')
    c = Counter(r['saved'] for r in rows)
    print('A. hands dropped with ALL of her jobs still done:', {k: f'{v / n:.0%}' for k, v in sorted(c.items())})
    print(f'   wages saved {sum(r["wage_saved"] for r in rows) / g:,.0f} a game of ~4,720; hands used {sum(r["used"] for r in rows) / n:.2f} -> {sum(r["used"] - r["saved"] for r in rows) / n:.2f} a day')
    print(f'B. FEED / CARE jobs she skips: {sum(r["extras"] for r in rows) / g:.0f} a game; they fit at her hand count {sum(r["fit_hers"] for r in rows) / g:.0f}, '
          f'and still {sum(r["fit_after"] for r in rows) / g:.0f} AFTER the hands of A are dropped')
    for lo, hi in ((3, 11), (12, 17), (18, 23), (24, 28)):
        R = [r for r in rows if lo <= r['day'] <= hi]
        print(f'   days {lo:>2}-{hi:<2}: jobs {st.mean(r["jobs"] for r in R):5.1f}, hands {st.mean(r["used"] for r in R):5.2f} -> {st.mean(r["used"] - r["saved"] for r in R):5.2f}, '
              f'wages saved {sum(r["wage_saved"] for r in R) / g:6,.0f} a game | skipped servicing {st.mean(r["extras"] for r in R):4.1f} a day: fits {st.mean(r["fit_hers"] for r in R):4.1f}, after dropping {st.mean(r["fit_after"] for r in R):4.1f}')
    print(f'search time a day: mean {st.mean(secs):.3f}s, max {max(secs):.3f}s')
    (ROOT / 'results/fresh/mg_tape/labour_search.json').write_text(json.dumps(dict(rows=rows, tapes=g)), encoding='utf-8')


if __name__ == '__main__':
    main()
