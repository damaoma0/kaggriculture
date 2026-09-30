"""Strawberry sales, item by item, the leader's game vs an arm's game over the 40-world panel (days 11-29): our k-th
strawberry sold vs DSM's k-th (unit-matched by cumulative count from day 11), classified as same step / ours later /
ours earlier / unmatched, with the price difference per class; why a later unit was late (at DSM's sale step: the unit
was not yet in our shed = not arrived, or it was in the shed = held); the rival's strawberry revenue change split the same
way; per-day totals; and a per-day detail for one world.
usage: strawberry_trace.py <ARM> [--world team:ep] [--workers 4]"""
import bisect
import json
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import panel_windfall as PW  # noqa: E402

UE = PW.UE
P = 'STRAWBERRY'


def job(args):
    g, arm, detail = args
    team, ep = g.split(':')
    ep = ep.strip()
    tape = UE.load_tape(int(team), int(ep))
    L, shL = PW.play(tape, None, (P,))
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    A, shA = PW.play(tape, s, (P,))
    us_L = sorted((e[0], e[3]) for e in L if e[1] == 'us')
    us_A = sorted((e[0], e[3]) for e in A if e[1] == 'us')
    c = Counter()
    day = defaultdict(Counter)
    for k in range(max(len(us_L), len(us_A))):
        if k >= len(us_A):
            tl, pl = us_L[k]
            c['dsm_only_n'] += 1
            c['dsm_only_$'] += pl
            day[tl // 24]['loss'] += pl
            continue
        if k >= len(us_L):
            ta, pa = us_A[k]
            c['ours_only_n'] += 1
            c['ours_only_$'] += pa
            day[ta // 24]['loss'] -= pa
            continue
        (tl, pl), (ta, pa) = us_L[k], us_A[k]
        key = 'same' if ta == tl else ('later' if ta > tl else 'earlier')
        c[key + '_n'] += 1
        c[key + '_dp'] += pa - pl
        day[tl // 24]['loss'] += pl - pa
        if key == 'later':
            c['later_delay'] += ta - tl
            held = shA.get(tl, {}).get(P, 0) > 0         # at DSM's sale step our shed held strawberries: held back
            c['later_' + ('held' if held else 'not_arrived')] += 1
            c['later_' + ('held' if held else 'not_arrived') + '_dp'] += pa - pl
            c['later_d%s' % min((ta - tl) // 24, 2)] += 1
    rA = defaultdict(float)
    rL = defaultdict(float)
    for e in A:
        if e[1] == 'opp':
            rA[e[0]] += e[3]
    for e in L:
        if e[1] == 'opp':
            rL[e[0]] += e[3]
    for t in set(rA) | set(rL):
        c['rival_$'] += rA.get(t, 0) - rL.get(t, 0)
        day[t // 24]['rival'] += rA.get(t, 0) - rL.get(t, 0)
    det = None
    if detail:
        det = {}
        for dd in range(11, 30):
            fL = [x for x in us_L if x[0] // 24 == dd]
            fA = [x for x in us_A if x[0] // 24 == dd]
            oL = sorted((e[0], e[3]) for e in L if e[1] == 'opp' and e[0] // 24 == dd)
            oA = sorted((e[0], e[3]) for e in A if e[1] == 'opp' and e[0] // 24 == dd)
            det[dd] = {'dsm': (len(fL), sum(p for _, p in fL)), 'us': (len(fA), sum(p for _, p in fA)),
                       'rivL': (len(oL), sum(p for _, p in oL)), 'rivA': (len(oA), sum(p for _, p in oA)),
                       'hours_dsm': dict(Counter(t % 24 for t, _ in fL)), 'hours_us': dict(Counter(t % 24 for t, _ in fA)),
                       'shed0': shA.get(dd * 24, {}).get(P, 0), 'shed0_dsm': shL.get(dd * 24, {}).get(P, 0)}
    return dict(c), {d: dict(v) for d, v in day.items()}, det


if __name__ == '__main__':
    arm = sys.argv[1]
    world = sys.argv[sys.argv.index('--world') + 1] if '--world' in sys.argv else '16732748:112604454'
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
    tot = Counter()
    days = defaultdict(Counter)
    det = None
    with Pool(nw) as pool:
        for c, dd, dt in pool.imap_unordered(job, [(g, arm, g.strip() == world) for g in games]):
            tot.update(c)
            for d, v in dd.items():
                days[d].update(v)
            if dt:
                det = dt
    n = len(games)
    g = lambda k: tot[k] / n
    print(f'{arm} vs DSM, strawberries, per world (unit-matched: our k-th sold vs DSM k-th)')
    for key, lab in (('same', 'same step'), ('later', 'ours later'), ('earlier', 'ours earlier')):
        m = max(1, tot[key + '_n'])
        print(f'   {lab:13s}: {g(key + "_n"):6.1f} units, our price - DSM price {tot[key + "_dp"] / m:+6.1f} a unit ({g(key + "_dp"):+7.0f} a world)')
    m = max(1, tot['later_n'])
    print(f'      later: mean delay {tot["later_delay"] / m:.1f} h; not yet arrived at DSM\'s sale step {g("later_not_arrived"):.1f} units '
          f'({tot["later_not_arrived_dp"] / max(1, tot["later_not_arrived"]):+.1f} a unit), in our shed (held) {g("later_held"):.1f} '
          f'({tot["later_held_dp"] / max(1, tot["later_held"]):+.1f} a unit); same day {g("later_d0"):.1f}, next day {g("later_d1"):.1f}, 2+ days {g("later_d2"):.1f}')
    print(f'   DSM sold, we never: {g("dsm_only_n"):.1f} units ({g("dsm_only_$"):.0f}) | we sold beyond DSM: {g("ours_only_n"):.1f} units ({g("ours_only_$"):.0f})')
    print(f'   rival strawberry revenue change: {g("rival_$"):+.0f}')
    print('   by day (our revenue loss vs DSM on DSM\'s sale days | rival gain): ' +
          ', '.join(f'{d}: {days[d]["loss"] / n:+.0f} | {days[d]["rival"] / n:+.0f}' for d in sorted(days) if d >= 11))
    if det:
        print(f'\nworld {world}, per day: DSM n@avg | ours n@avg | rival (DSM game) n@avg | rival (our game) n@avg | our shed at hour 0 (DSM\'s)')
        for dd in sorted(det):
            x = det[dd]
            f = lambda nv: f'{nv[0]:3d}@{(nv[1] / nv[0] if nv[0] else 0):5.1f}'
            print(f'   d{dd}: DSM {f(x["dsm"])} | us {f(x["us"])} | rival {f(x["rivL"])} -> {f(x["rivA"])} | shed {x["shed0"]} ({x["shed0_dsm"]})'
                  f' | hours DSM {dict(sorted(x["hours_dsm"].items()))} us {dict(sorted(x["hours_us"].items()))}')
