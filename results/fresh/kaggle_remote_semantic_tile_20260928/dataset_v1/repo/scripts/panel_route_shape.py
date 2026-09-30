"""Route shapes, the leader vs arms over the 40-world panel (days 11-28), per hand-day (hands only; the farmer on its own
line). Distance = steps from the nearest shed access tile. Classes:
  local       - never more than 2 steps out
  radial      - goes out and never comes back within 1 step of the shed before the day ends (ends out)
  ends home   - one trip out, back within 1 step of the shed at the end of its work
  two trips   - back within 1 step of the shed mid-day (then out again)
Also: the hour the hand is farthest, distance of its first / last work tile, share of work done far-first (work distance
falls over the day) vs near-first, quadrants worked, and a per-day table.
usage: panel_route_shape.py <ARM>[,<ARM>...] [--workers 4] [--d0 1 (DSM from day 1; arms replay DSM before day 11)]"""
import json
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]
MOVES = ('NORTH', 'SOUTH', 'EAST', 'WEST', 'PASS')
CLASSES = ('local', 'radial', 'ends home', 'two trips')


def dsh(p):
    return min(abs(p[0] - a) + abs(p[1] - b) for a, b in SHED)


def quad(p):
    return ('N' if p[1] <= 4 else 'S') + ('W' if p[0] <= 4 else 'E')


def shape(ev):
    """ev: [(hour, pos, kind)] of one hand-day -> dict of shape facts (None if the hand never works)."""
    work = [(h, p) for h, p, k, _ in ev if k == 'work']
    if not work:
        return None
    last_h = work[-1][0]
    ds = [(h, dsh(p)) for h, p, _, _ in ev if h <= last_h + 1]
    dmax = max(d for _, d in ds)
    h_far = next(h for h, d in ds if d == dmax)
    far = False
    mid = 0
    for h, d in ds:
        if d >= 2:
            if far is None:
                mid += 1                                # came back within 1 and went out again
            far = True
        elif d <= 1 and far:
            far = None
    end_d = ds[-1][1]
    if dmax <= 2:
        cls = 'local'
    elif mid:
        cls = 'two trips'
    elif end_d <= 1:
        cls = 'ends home'
    else:
        cls = 'radial'
    wd = [dsh(p) for _, p in work]
    k = len(wd) // 2
    trend = (sum(wd[k:]) / max(1, len(wd) - k) - sum(wd[:k]) / max(1, k)) if len(wd) >= 2 else 0.0
    two = None
    if cls == 'two trips':                              # the first mid-day return: when, exchange there, trip 1 / trip 2
        far = False
        h_ret = None
        for i, (h, p, k, op) in enumerate(ev):
            d = dsh(p)
            if d >= 2:
                if h_ret is not None:
                    h_out = h
                    break
                far = True
            elif d <= 1 and far and h_ret is None:
                h_ret = h
        else:
            h_out = None
        t1 = Counter(op for h, p, k, op in ev if k == 'work' and h < h_ret)
        t2 = Counter(op for h, p, k, op in ev if k == 'work' and h_out is not None and h >= h_out)
        exch = Counter(op for h, p, k, op in ev if k == 'shed' and h_ret <= h < (h_out or 24))
        near = sum(1 for h, p, k, op in ev if k == 'work' and h_ret <= h < (h_out or 24))
        two = {'near': near, 'h_ret': h_ret, 'h_out': h_out, 't1': t1, 't2': t2, 'exch': exch,
               'd1': max([dsh(p) for h, p, k, op in ev if h < h_ret] or [0]),
               'd2': max([dsh(p) for h, p, k, op in ev if h_out is not None and h >= h_out] or [0])}
    return {'two': two, 'cls': cls, 'dmax': dmax, 'h_far': h_far, 'first_d': wd[0], 'last_d': wd[-1], 'trend': trend, 'end_d': end_d,
            'quads': len(set(quad(p) for _, p in work)), 'first_h': work[0][0], 'last_h': last_h, 'n_work': len(work)}


D0 = 11


def job(args):
    g, arm, d0 = args
    team, ep = g.split(':')
    ep = ep.strip()
    tape = UE.load_tape(int(team), int(ep))
    s = None if arm == 'DSM' else json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    log = defaultdict(list)
    while w.t < 696:
        t = w.t
        dd, h = t // 24, t % 24
        own = UE.tape_action(tape['actions'], t) if (s is None or t < 264) else (s[t] if isinstance(s[t], dict) and s[t] else dict(UE.PASS))
        if t >= d0 * 24:
            farm = w.farms[seat]
            units = [tuple(farm['farmer'])] + [tuple(q) for q in farm['hands']]
            cmds = [own.get('farmer')] + list(own.get('hands') or [])
            for u, p in enumerate(units):
                cm = cmds[u] if u < len(cmds) else None
                op = cm[0] if isinstance(cm, list) and cm else 'PASS'
                if op in MOVES:
                    k = 'move'
                elif op in ('DROP', 'PICKUP') or (op == 'PLACE' and dsh(p) == 0 and len(cm) > 1 and cm[1] not in ('COW', 'SHEEP', 'GOOSE')):
                    k = 'shed'
                else:
                    k = 'work'
                    tl = farm['tiles'][p[1]][p[0]]
                    what = (tl.get('animal') or tl.get('crop') or tl.get('kind')) if isinstance(tl, dict) else '-'
                    k = 'work'
                    log[(dd, u)].append((h, p, k, op + ':' + str(what)))
                    continue
                log[(dd, u)].append((h, p, k, op))
        a2 = [None, None]
        a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
    out = []
    for (dd, u), ev in log.items():
        r = shape(ev)
        if r is not None:
            r['day'], r['u'] = dd, u
            out.append(r)
    return arm, ep, out


if __name__ == '__main__':
    arms = sys.argv[1].split(',')
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    d0 = int(sys.argv[sys.argv.index('--d0') + 1]) if '--d0' in sys.argv else 11
    games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
    rows = defaultdict(list)
    with Pool(nw) as pool:
        for arm, ep, out in pool.imap_unordered(job, [(g, a, d0 if a == 'DSM' else 11) for a in arms for g in games]):
            rows[arm] += out
    n = len(games)
    for a in arms:
        R = [r for r in rows[a] if r['u'] > 0]
        F = [r for r in rows[a] if r['u'] == 0]
        cc = Counter(r['cls'] for r in R)
        print(f'\n{a}: {len(R) / n:.0f} working hand-days a world - ' + ', '.join(f'{c} {cc[c] / n:.1f} ({100 * cc[c] / len(R):.0f}%)' for c in CLASSES)
              + ' | farmer: ' + ', '.join(f'{c} {sum(1 for r in F if r["cls"] == c) / n:.1f}' for c in CLASSES))
        for c in CLASSES:
            X = [r for r in R if r['cls'] == c]
            if not X:
                continue
            m = len(X)
            print(f'   {c:10s}: max out {sum(r["dmax"] for r in X) / m:.1f} steps at hour {sum(r["h_far"] for r in X) / m:.1f}; first work {sum(r["first_d"] for r in X) / m:.1f} '
                  f'-> last work {sum(r["last_d"] for r in X) / m:.1f} steps (far-first {100 * sum(1 for r in X if r["trend"] < -0.5) / m:.0f}%, near-first '
                  f'{100 * sum(1 for r in X if r["trend"] > 0.5) / m:.0f}%); work h{sum(r["first_h"] for r in X) / m:.1f}-h{sum(r["last_h"] for r in X) / m:.1f}, '
                  f'{sum(r["n_work"] for r in X) / m:.1f} ops, {sum(r["quads"] for r in X) / m:.1f} quadrants')
        T = [r['two'] for r in R if r['two']]
        if T:
            m = len(T)
            ex = sum(1 for x in T if x['exch'])
            print(f'   two trips detail: back at hour {sum(x["h_ret"] for x in T) / m:.1f}, out again at {sum((x["h_out"] or 24) for x in T) / m:.1f}; exchange at the shed on '
                  f'{100 * ex / m:.0f}% ({", ".join(f"{k} {v / m:.2f}" for k, v in sum((x["exch"] for x in T), Counter()).most_common(4))}); trip 1 out {sum(x["d1"] for x in T) / m:.1f} steps, '
                  f'trip 2 out {sum(x["d2"] for x in T) / m:.1f}')
            t1 = sum((x['t1'] for x in T), Counter())
            t2 = sum((x['t2'] for x in T), Counter())
            print(f'      work ops: trip 1 {sum(sum(x["t1"].values()) for x in T) / m:.1f}, near the shed between trips {sum(x["near"] for x in T) / m:.1f}, '
                  f'trip 2 {sum(sum(x["t2"].values()) for x in T) / m:.1f}')
            print('      trip 1 ops a hand-day: ' + ', '.join(f'{k} {v / m:.1f}' for k, v in t1.most_common(7)))
            print('      trip 2 ops a hand-day: ' + ', '.join(f'{k} {v / m:.1f}' for k, v in t2.most_common(7)))
        byd = defaultdict(Counter)
        for r in R:
            byd[r['day']][r['cls']] += 1
            if r['two'] and r['two']['exch']:
                byd[r['day']]['exch'] += 1
        print('   per day, hands a world:  day | radial | back to centre (two trips + ends home) [two trips with a shed drop / pickup] | local | working hands')
        for d in sorted(byd):
            b = byd[d]
            print(f'      d{d:2d} | {b["radial"] / n:5.1f} | {(b["two trips"] + b["ends home"]) / n:5.1f} ({b["two trips"] / n:.1f} + {b["ends home"] / n:.1f}) [{b["exch"] / n:.1f}] | '
                  f'{b["local"] / n:4.1f} | {sum(v for k, v in b.items() if k != "exch") / n:5.1f}')
