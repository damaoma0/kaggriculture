"""Skeptic check 7: hands that can be emptied with every job of the day still done (report 2b: ours 2.16 a day /
wages 3,866 of 8,082 a game; leader 0.71 a day / 404 of 6,153). Own implementation in the report's model:
min-sum ILS for 40% of the budget, then repeatedly empty the non-frozen hand with the fewest commands by regret-2
insertion of its jobs into the other free routes, with up to 6 ruin-and-recreate repairs (a third of the jobs of
up to 3 other routes) when a job does not fit; stop at the budget. Wages = fib of the latest hires, as the report.
usage: verify_handdrop.py [budget=1.0] [games_per_side=3]
"""
import random
import sys
import time
from collections import Counter

import verify_common as V

FIB = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987, 1597]
OURS_PICK = [110937191, 111554912, 111688786, 111941962]
LEAD_PICK = [('16732748', 112655730), ('16770421', 112714050), ('16730612', 112444381), ('16732748', 112667461)]


def regret_insert(S, R, free, jobs, rng):
    R = {u: list(r) for u, r in R.items()}
    C = {u: V.cost(S.units[u], R[u]) for u in R}
    left = list(jobs)
    while left:
        best = None
        for j in left:
            opts = []
            for u in free:
                for k in range(len(R[u]) + 1):
                    c = S.c_of(u, R[u][:k] + [j] + R[u][k:])
                    if c is not None:
                        opts.append((c - C[u], u, k))
            if not opts:
                return None
            opts.sort()
            reg = (opts[1][0] - opts[0][0]) if len(opts) > 1 else 99
            key = reg + rng.random() * 0.5
            if best is None or key > best[0]:
                best = (key, j, opts[0])
        _, j, (dc, u, k) = best
        R[u] = R[u][:k] + [j] + R[u][k:]
        C[u] += dc
        left.remove(j)
    return R


def hand_drop(units, routes, frozen, budget, rng):
    t0 = time.perf_counter()
    S = V.Search(units, routes, frozen, rng=rng)
    R, tot, _, _ = S.run(budget * 0.4)
    dropped = set()
    while time.perf_counter() - t0 < budget:
        cands = sorted((u for u in R if u > 0 and u not in frozen and u not in dropped and R[u]),
                       key=lambda u: sum(j.n for j in R[u]))
        progress = False
        for u in cands:
            if time.perf_counter() - t0 >= budget:
                break
            free = [v for v in R if v not in frozen and v not in dropped and v != u]
            base = {v: (R[v] if v != u else []) for v in R}
            new = regret_insert(S, base, free, R[u], rng)
            tries = 0
            while new is None and tries < 6 and time.perf_counter() - t0 < budget:
                tries += 1
                others = [v for v in free if base[v]]
                if not others:
                    break
                ruined, pool = dict(base), list(R[u])
                for v in rng.sample(others, min(3, len(others))):
                    take = set(id(x) for x in rng.sample(ruined[v], max(1, len(ruined[v]) // 3)))
                    pool += [x for x in ruined[v] if id(x) in take]
                    ruined[v] = [x for x in ruined[v] if id(x) not in take]
                new = regret_insert(S, ruined, free, pool, rng)
            if new is not None:
                for v in free:
                    new[v], _ = S.intra(v, new[v])
                R = new
                dropped.add(u)
                progress = True
                break
        if not progress:
            break
    return R, dropped


def main():
    budget = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
    ng = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    games = [('ours', V.load_ours(ep)) for ep in OURS_PICK[:ng]] + [('leader', V.load_leader(t, ep)) for t, ep in LEAD_PICK[:ng]]
    agg = {s: Counter() for s in ('ours', 'leader')}
    import json
    rep = {}
    for line in open(V.HERE / 'rows_both.jsonl', encoding='utf-8'):
        r = json.loads(line)
        rep[(r['side'], r['ep'], r['day'])] = r
    for side, g in games:
        days, _ = V.rebuild(g['actions'])
        for d in range(30):
            if not days[d]:
                continue
            units, routes, busy, info = V.instance(days[d])
            frozen = {u for u in units if routes[u] and V.finish(units[u], routes[u]) > 24}
            hired = [u for u in units if u > 0]
            worked = [u for u in hired if routes[u]]
            R, dropped = hand_drop(units, routes, frozen, budget, random.Random(7 + d))
            pairs, bad = V.check_solution(units, routes, R, frozen=frozen)
            n = len(hired)
            saved = len(dropped)
            a = agg[side]
            a['days'] += 1
            a['worked'] += len(worked)
            a['saved'] += saved
            a['wage_saved'] += sum(FIB[min(16, n - 1 - i)] for i in range(saved))
            a['wage_paid'] += sum(FIB[min(16, i)] for i in range(n))
            a['bad'] += sum(v for k, v in bad.items() if k != 'over_cap_frozen')
            rr = rep.get((side, g['ep'], d))
            if rr:
                a['rep_saved'] += rr['b']['1.0']['saved']
                a['rep_wage_saved'] += rr['b']['1.0']['wage_saved']
        print(f"{side} {g['ep']} done", flush=True)
    L = [f'VERIFY 7: hands emptied with all jobs done (own implementation, report model, {budget:g} s/day, {ng} games per side)']
    for s, a in agg.items():
        gm = ng
        L.append(f"  {s}: hands with jobs {a['worked'] / a['days']:.2f} a day; emptied {a['saved'] / a['days']:.2f} a day "
                 f"({a['saved'] / gm:.1f} hand-days a game); wages saved {a['wage_saved'] / gm:,.0f} of {a['wage_paid'] / gm:,.0f} a game; "
                 f"solution violations {a['bad']}; report rows same days (1 s): {a['rep_saved'] / a['days']:.2f} a day, wages {a['rep_wage_saved'] / gm:,.0f}")
    txt = '\n'.join(L) + '\n'
    (V.HERE / 'verify_handdrop.txt').write_text(txt, encoding='utf-8')
    print(txt)


if __name__ == '__main__':
    main()
