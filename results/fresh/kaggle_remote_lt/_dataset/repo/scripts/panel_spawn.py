"""Hand spawns (arm, or DSM for its hiring pattern, over the 40-world panel, days 11-28). Engine rule: a hire spawns on the
least occupied shed-access tile (NW, NE, SW, SE on ties) counting the farmer and hands standing there after that step's
unit actions; hires are placed one by one. Per day: hires at hour 0 / 1 / 2+. For the hour-1 hires (arm only): the plan's
assumed spawn tiles (summary 'spawn', after the hour-0 hires) vs the actual ones; whether the plan was self-consistent
(its assumed tiles = the engine rule applied to its own predicted hour-1 positions 'after1'); whether our units' actual
hour-1 positions matched 'after1'; whether the buffer was used (hour-1 hire routes planned from hour 3); per hour-1 hire
the steps its spawn was off and what that cost (start of its first job vs plan, unfinished planned ops).
usage: panel_spawn.py <ARM>[,<ARM>...] [--workers 4]"""
import ast
import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

ORDER = [(4, 4), (5, 4), (4, 5), (5, 5)]
WORK = ('WATER', 'HARVEST', 'FEED', 'CARE', 'COLLECT_FERTILIZER', 'FERTILIZE', 'PLANT', 'DIG', 'PLACE_HARVEST', 'DELIVER', 'DROP', 'PLACE')


def spawn(pos, k):
    occ = {q: 0 for q in ORDER}
    for p in pos:
        if tuple(p) in occ:
            occ[tuple(p)] += 1
    out = []
    for _ in range(k):
        q = sorted(ORDER, key=lambda q: (occ[q], ORDER.index(q)))[0]
        occ[q] += 1
        out.append(q)
    return out


def d(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def lst(x):
    return ast.literal_eval(x) if isinstance(x, str) else (x or [])


def job(args):
    g, arm = args
    team, ep = g.split(':')
    ep = ep.strip()
    tape = UE.load_tape(int(team), int(ep))
    s = None if arm == 'DSM' else json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    res = None if arm == 'DSM' else json.loads((ROOT / 'results/fresh/sector_20260925/multi' / arm / f'{ep}.json').read_text())
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    c = Counter()
    first_pos = {}                                        # (day, u) -> (hour first seen, pos)
    pos_h1 = {}                                           # day -> positions of our units after the hour-1 unit actions
    while w.t < 696:
        t = w.t
        dd, h = t // 24, t % 24
        own = UE.tape_action(tape['actions'], t) if (s is None or t < 264) else (s[t] if isinstance(s[t], dict) and s[t] else dict(UE.PASS))
        if t >= 264:
            farm = w.farms[seat]
            for u, q in enumerate([tuple(farm['farmer'])] + [tuple(x) for x in farm['hands']]):
                first_pos.setdefault((dd, u), (h, q))
            if h == 2:                                    # positions at the start of hour 2 = after the hour-1 actions
                n_h1 = sum(1 for (d0, u), (hh, q) in first_pos.items() if d0 == dd and hh == 2)
                older = [q for (d0, u), (hh, q) in sorted(first_pos.items()) if d0 == dd and hh <= 1]
                pos_h1[dd] = ([tuple(farm['farmer'])] + [tuple(x) for x in farm['hands']])[:len(older)]
        a2 = [None, None]
        a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
    days = sorted(set(d0 for d0, _ in first_pos))
    for dd in days:
        hs = Counter(hh for (d0, u), (hh, q) in first_pos.items() if d0 == dd and u > 0)
        c['days'] += 1
        c['hire_h0'] += hs.get(1, 0)
        c['hire_h1'] += hs.get(2, 0)
        c['hire_h2p'] += sum(v for k, v in hs.items() if k >= 3)
        if res is None:
            continue
        v = res['tier_days'].get(str(dd)) or {}
        if not v.get('units'):
            continue
        k0 = int(v.get('k0', 0) or 0)
        sp = [tuple(x) for x in (v.get('spawn') or [])]
        late = sorted(u for (d0, u), (hh, q) in first_pos.items() if d0 == dd and hh == 2 and u > 0)
        if not late:
            continue
        c['days_h1'] += 1
        units = {r['u']: r for r in v['units']}
        buf = any(units.get(u, {}).get('t0') == 3 for u in late)
        c['days_buffer'] += buf
        after1 = [tuple(x) for x in (v.get('after1') or [])]
        sp1 = sp[k0:k0 + len(late)] if len(sp) >= k0 + len(late) else None
        actual = [first_pos[(dd, u)][1] for u in late]
        if sp1 is not None:
            consistent = spawn(after1, len(late)) == sp1
            c['plan_consistent'] += consistent
            c['after1_right'] += (after1 == pos_h1.get(dd, [])[:len(after1)])
            c['engine_check'] += spawn(pos_h1.get(dd, []), len(late)) == actual
            for u, a, p in zip(late, actual, sp1):
                c['h1_hires'] += 1
                off = d(a, p)
                c['off_%d' % off] += 1
                c[('buf_' if buf else 'nobuf_') + 'off_%d' % off] += 1
            c['day_all_right'] += list(actual) == list(sp1)
            c[('buf_' if buf else 'nobuf_') + 'days_right'] += list(actual) == list(sp1)
        ex = v.get('exec') or {}
        for u in late:
            e = ex.get(str(u)) or {}
            plan, done = lst(e.get('plan')), lst(e.get('done'))
            pw = [x for x in plan if x[1] in WORK]
            dw = [x for x in done if x[2] in WORK]
            if pw and dw:
                c['h1_first_gap'] += pw[0][2] - dw[0][0]           # planned - actual hour of the first job
                c['h1_first_n'] += 1
            c['h1_unfinished'] += sum(len(x[1]) if isinstance(x, list) and len(x) > 1 else 0 for x in ((v.get('unfinished') or {}).get(str(u)) or []))
            c['h1_notdone'] += max(0, len(pw) - len(dw))
    return arm, dict(c)


if __name__ == '__main__':
    arms = sys.argv[1].split(',')
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
    tot = {a: Counter() for a in arms}
    with Pool(nw) as pool:
        for arm, c in pool.imap_unordered(job, [(g, a) for a in arms for g in games]):
            tot[arm].update(c)
    n = len(games)
    for a in arms:
        c = tot[a]
        dd = max(1, c['days'])
        print(f'\n{a}: hires a day - hour 0: {c["hire_h0"] / dd:.2f}, hour 1: {c["hire_h1"] / dd:.2f}, hour 2+: {c["hire_h2p"] / dd:.2f}')
        if a == 'DSM':
            continue
        m = max(1, c['h1_hires'])
        k = max(1, c['days_h1'])
        print(f'   days with hour-1 hires {c["days_h1"] / n:.1f} a world; buffer used on {c["days_buffer"] / k:.0%}; plan self-consistent (assumed tiles = rule on its own '
              f'after1) {c["plan_consistent"] / k:.0%}; our hour-1 positions = after1 {c["after1_right"] / k:.0%}; engine rule on actual positions reproduces the spawns {c["engine_check"] / k:.0%}')
        print(f'   hour-1 hires {c["h1_hires"] / n:.1f} a world: spawn off by 0 / 1 / 2 steps: ' + ' / '.join(f'{100 * c["off_%d" % i] / m:.0f}%' for i in range(3))
              + f'; whole day right {c["day_all_right"] / k:.0%} (buffer days {c["buf_days_right"] / max(1, c["days_buffer"]):.0%}, others '
              f'{c["nobuf_days_right"] / max(1, c["days_h1"] - c["days_buffer"]):.0%})')
        print(f'   hour-1 hires: first job planned - actual {c["h1_first_gap"] / max(1, c["h1_first_n"]):+.2f} h, planned jobs not done {c["h1_notdone"] / m:.2f}, '
              f'unfinished at day end {c["h1_unfinished"] / m:.2f}')
