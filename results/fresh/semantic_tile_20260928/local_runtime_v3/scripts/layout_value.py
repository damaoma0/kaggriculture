"""How much is tile LAYOUT freedom worth, separate from routing freedom?

`scripts/labour_search.py` already shows the leaders' ROUTING (job order, which unit does which job) is
near the calibrated model's optimum for the layout they actually used. This script asks the other
question: keep every job's WORK (same commands, same day, same counts) but ask whether physically
reassigning which tile each crop/animal cohort sits on -- putting the tiles visited most across the
whole game nearest the shed -- would have cut travel, using the SAME calibrated time model and search
machinery (imported unmodified from labour_search.py; this file only reads it).

Method per DSM tape (data/dsm_tapes/56444344/*.json.gz, a 3000-rated leader, 109 games):
1. Dead-reckon the tape into a visit calendar (tape_calendar, via labour_search.simulate) and, for every
   day, turn it into a job set (labour_search.instance): one Job per (unit, tile, day).
2. Whole-game visit frequency and first-use day per tile (freq[tile], first_day[tile]).
3. Quadrant-unlock day per game read off the board snapshots (a corner tile of each quadrant flips from
   ' L' to unlocked the day it is bought) -- NOT assumed from other agents' patterns.
4. Greedy relayout: process tiles by descending whole-game frequency (ties: earlier first-use day, then
   tile id); assign each the nearest not-yet-taken tile (Manhattan distance to the nearest shed corner)
   among tiles in a quadrant unlocked by that tile's first-use day. One tile per cohort; shed tiles
   excluded from the pool. This is the "simple greedy" the task allows, not a joint optimum.
5. Rewrite every day's jobs onto the mapped tiles (ops/day/release unchanged) and re-run
   labour_search.search() (2-opt/or-opt + regret-insertion hand dropping) on both the actual-layout jobs
   and the relaid-out jobs, with the SAME frozen-unit set (units whose real route does not fit the model,
   left untouched in both, exactly as labour_search.py does). Compare hands needed, unit-hours
   (sum of finish()-start over all units), and fib() wages of that many hires.

Caveats (see report): (a) a tile's "cohort" is its physical (x,y), not a specific planting -- rotations
at the same tile are treated as one cohort, which is generous to the leaders' actual layout; (b) the
relayout does not replan planting ORDER, pasture/coop build cost, or in-route inventory chains, only
tile identity; (c) the time model is the same one labour_search.py calibrates against her recorded
steps (220.8 model vs 222.5 real steps/day), so it inherits that model's known gaps (shed cap, per-route
inventory); (d) quadrant purchase day/order is taken as recorded, not re-optimised.

usage: layout_value.py [every_nth_tape=1] [seconds_per_day=0.08]
Output: results/fresh/layout_value/layout_value.json
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

# Reuse labour_search.py's calibrated time model + search machinery verbatim (read-only import by exec,
# since it is a script, not a package). __name__ is set so its own `if __name__ == '__main__'` does not fire.
_src = (ROOT / 'scripts/labour_search.py').read_text(encoding='utf-8')
ns = {'__name__': 'layout_value_lib', '__file__': str(ROOT / 'scripts/labour_search.py')}
exec(compile(_src, 'labour_search', 'exec'), ns)
instance, finish, search = ns['instance'], ns['finish'], ns['search']
Job, SHED, FIB, is_work, MOVES, simulate, dman = (ns['Job'], ns['SHED'], ns['FIB'], ns['is_work'],
                                                   ns['MOVES'], ns['simulate'], ns['d'])

QCORNER = {'NW': (0, 0), 'NE': (9, 0), 'SW': (0, 9), 'SE': (9, 9)}


def quadrant_of(t):
    x, y = t
    return 'NW' if (x < 5 and y < 5) else 'NE' if y < 5 else 'SW' if x < 5 else 'SE'


def unlocked_by_day(boards):
    """day -> set of quadrant names unlocked as of that day's board snapshot (corner-tile check: a
    locked tile reads ' L'; the whole quadrant unlocks in one BUY_LAND, so one corner is enough)."""
    out = {}
    for day, b in enumerate(boards):
        flat = ''.join(b)
        u = set()
        for q, (x, y) in QCORNER.items():
            i = y * 10 + x
            if flat[2 * i:2 * i + 2] != ' L':
                u.add(q)
        out[day] = u
    return out


def dist_shed(t):
    return min(dman(t, s) for s in SHED)


ALL_TILES = [(x, y) for y in range(10) for x in range(10) if (x, y) not in SHED]


def greedy_relayout(freq, first_day, unlocked):
    """Sort cohorts by descending whole-game visit frequency; give each the nearest free tile in a
    quadrant unlocked by its first-use day. One item per tile; ties broken by earlier first use."""
    order = sorted(freq, key=lambda t: (-freq[t], first_day[t], t))
    taken, mapping = set(), {}
    for t in order:
        # boards[day] is a START-of-day snapshot; a quadrant bought DURING day `first_day[t]` only shows
        # unlocked in boards[day+1], but a job that same day (after the buy) is legitimate -> look one day ahead.
        allowed = unlocked.get(min(first_day[t] + 1, 29), {'NW'})
        cands = sorted((c for c in ALL_TILES if c not in taken and quadrant_of(c) in allowed),
                       key=lambda c: (dist_shed(c), c))
        new = cands[0] if cands else t          # no room left (should not happen: same constraint bound her)
        mapping[t] = new
        taken.add(new)
    return mapping


def day_raw_shares(sim, day):
    """(farmer move/work/other, hands move/work/other) step counts read straight off the tape."""
    fm = fw = fo = hm = hw = ho = 0
    for t in range(day * 24, min(719, day * 24 + 24)):
        for u, (x, y, c) in enumerate(sim.get(t, [])):
            op = c[0] if c else 'PASS'
            move, work = op in MOVES, is_work((x, y), op)
            if u == 0:
                fm += move; fw += work; fo += (not move and not work)
            else:
                hm += move; hw += work; ho += (not move and not work)
    return fm, fw, fo, hm, hw, ho


def remap_routes(routes, mapping):
    return {u: [Job(mapping.get(j.tile, j.tile), j.ops, today=j.today, release=j.release) for j in r]
            for u, r in routes.items()}


def cost(units, routes, budget, rng, frozen):
    new, _ = search(units, routes, budget, rng, frozen)
    hands = [u for u in new if u > 0 and new[u]]
    unit_hours = sum(finish(units[u], new[u]) - units[u][0] for u in new)
    wages = sum(FIB[min(16, i)] for i in range(len(hands)))
    return len(hands), unit_hours, wages


def main():
    nth = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    budget = float(sys.argv[2]) if len(sys.argv) > 2 else 0.08
    rng = random.Random(20260924)
    paths = sorted(glob.glob(str(ROOT / 'data/dsm_tapes/56444344/*.json.gz')))[::nth]
    game_rows, day_rows = [], []
    t_start = time.perf_counter()
    for gi, p in enumerate(paths):
        t = json.load(gzip.open(p, 'rt', encoding='utf-8'))
        acts = [a if isinstance(a, dict) else {} for a in t['actions']]
        sim = simulate(lambda s: acts[s] if s < len(acts) else {}, 0, 718, [(4, 4)])
        unlocked = unlocked_by_day(t['boards'])

        freq, first_day = Counter(), {}
        day_routes, day_units, day_frozen = {}, {}, {}
        for day in range(30):
            units, routes, busy, c = instance(sim, day)
            day_routes[day], day_units[day] = routes, units
            day_frozen[day] = {u for u in units if finish(units[u], routes[u]) > 24}
            for r in routes.values():
                for j in r:
                    freq[j.tile] += 1
                    first_day[j.tile] = min(first_day.get(j.tile, day), day)
        mapping = greedy_relayout(freq, first_day, unlocked)

        g = dict(wage_a=0.0, wage_c=0.0, uh_a=0.0, uh_c=0.0)
        for day in range(30):
            units, routes = day_units[day], day_routes[day]
            if not any(routes.values()):
                continue
            fm, fw, fo, hm, hw, ho = day_raw_shares(sim, day)
            frozen = day_frozen[day]
            ha, uha, wa = cost(units, {u: list(r) for u, r in routes.items()}, budget, rng, frozen)
            hc, uhc, wc = cost(units, remap_routes(routes, mapping), budget, rng, frozen)
            day_rows.append(dict(game=gi, day=day, hands_a=ha, hands_c=hc, uh_a=uha, uh_c=uhc,
                                  wage_a=wa, wage_c=wc, fm=fm, fw=fw, fo=fo, hm=hm, hw=hw, ho=ho))
            for k, v in (('wage_a', wa), ('wage_c', wc), ('uh_a', uha), ('uh_c', uhc)):
                g[k] += v

        tot_w = sum(freq.values())
        dist_a = sum(freq[x] * dist_shed(x) for x in freq) / tot_w if tot_w else 0
        dist_g = sum(freq[x] * dist_shed(mapping[x]) for x in freq) / tot_w if tot_w else 0
        game_rows.append(dict(game=gi, path=Path(p).name, n_tiles=len(freq),
                               mean_dist_actual=dist_a, mean_dist_greedy=dist_g, **g))
        if (gi + 1) % 10 == 0:
            print(f'{gi + 1}/{len(paths)} games, {time.perf_counter() - t_start:.0f}s', file=sys.stderr)

    print(f'{len(paths)} DSM tapes, {len(day_rows)} tape-days, budget {budget}s/search-call')
    tfm, tfw, tfo = (sum(r[k] for r in day_rows) for k in ('fm', 'fw', 'fo'))
    thm, thw, tho = (sum(r[k] for r in day_rows) for k in ('hm', 'hw', 'ho'))
    print(f'1. farmer  : move {tfm / (tfm + tfw + tfo):.1%}, work {tfw / (tfm + tfw + tfo):.1%}, other {tfo / (tfm + tfw + tfo):.1%}')
    print(f'   hands   : move {thm / (thm + thw + tho):.1%}, work {thw / (thm + thw + tho):.1%}, other {tho / (thm + thw + tho):.1%}')

    for lo, hi in ((0, 6), (7, 17), (18, 29)):
        R = [r for r in day_rows if lo <= r['day'] <= hi]
        if not R:
            continue
        uh_s = sorted(r['uh_a'] - r['uh_c'] for r in R)
        wg_s = sorted(r['wage_a'] - r['wage_c'] for r in R)
        hd_s = sorted(r['hands_a'] - r['hands_c'] for r in R)
        p90 = lambda s: s[min(len(s) - 1, int(.9 * len(s)))]
        print(f'days {lo:>2}-{hi:<2}: n={len(R):4d}  unit-hrs saved/day median {st.median(uh_s):5.2f} p90 {p90(uh_s):5.2f}  |  '
              f'hands saved/day median {st.median(hd_s):4.2f}  |  wage saved/day median {st.median(wg_s):5.1f} p90 {p90(wg_s):5.1f}')

    pw = [g['wage_a'] - g['wage_c'] for g in game_rows]
    puh = [g['uh_a'] - g['uh_c'] for g in game_rows]
    print(f'per game (n={len(game_rows)}): wage saved mean {st.mean(pw):.0f} median {st.median(pw):.0f} (of ~4,720 wages/game); '
          f'unit-hours saved mean {st.mean(puh):.0f}')
    da = st.mean(g['mean_dist_actual'] for g in game_rows)
    dg = st.mean(g['mean_dist_greedy'] for g in game_rows)
    print(f'visit-weighted mean distance to shed: actual layout {da:.2f}, greedy relayout {dg:.2f} ({(da - dg) / da:.0%} closer)')

    out = ROOT / 'results/fresh/layout_value'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'layout_value.json').write_text(
        json.dumps(dict(games=game_rows, days=day_rows, tapes=len(paths), budget=budget)), encoding='utf-8')
    print(f'wrote {out / "layout_value.json"}')


if __name__ == '__main__':
    main()
