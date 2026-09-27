"""Could our idle hand-hours fertilize strawberries or wheat? Over the 40-world panel (days 11-28), for every idle
stretch of a hand in the arm's game (consecutive PASS hours from its first idle hour to the end of the day, length L),
the useful fertilize targets it could reach in time: a target at distance D needs D + 1 hours (FERTILIZE), + 1 more to
WATER a plant not yet watered today and not watered later that day by anyone.
Useful (engine rules):
  STRAWBERRY: tonight is a production night (end of p+9/+11/+13/+15), not fertilized through today; gain = production
    nights in today..today+2 not yet covered (the later one pays only if watered that night).
  WHEAT (one-time crops in general): inside the growth window (days (maxday+1)//2 .. maxday after planting), not
    fertilized; a WATER in the window adds +2 when fertilized, +1 otherwise: gain = today's water if still to come
    (+1) plus the window days tomorrow / the day after (+1 each, if watered then).
Counts stretches with a reachable target (one target per stretch, distinct targets per day, nearest first), the gain,
and whether the hand carried fertilizer at the start of the stretch.
usage: panel_idle_fert.py <ARM> [--workers 4]"""
import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
CROPS = E.CROPS


def gain(t, day):
    cd = CROPS[t['crop']]
    pd = t['planted_day']
    fu = t.get('fertilized_until_day', -1)
    if fu >= day:
        return 0
    if cd['ongoing']:
        def prod(dd):
            k = dd + 1 - pd - cd['first_yield_day']
            return k >= 0 and k % cd['interval'] == 0 and k // cd['interval'] + 1 <= cd['max_yield']
        if not prod(day):
            return 0
        return sum(1 for dd in (day, day + 1, day + 2) if prod(dd))
    w0, w1 = (cd['max_yield_day'] + 1) // 2, cd['max_yield_day']
    g = 0
    for dd in (day, day + 1, day + 2):
        if w0 <= dd - pd <= w1 and (dd > day or not t.get('watered_today')):
            g += 1
    return min(g, max(0, cd['max_yield'] - int(t.get('yield_units', 0) or 0)))


def job(args):
    g, arm = args
    team, ep = g.split(':')
    ep = ep.strip()
    tape = UE.load_tape(int(team), int(ep))
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    c = Counter()

    def cmd(t, u):
        a = s[t] if t < len(s) and isinstance(s[t], dict) else {}
        cs = [a.get('farmer')] + list(a.get('hands') or [])
        x = cs[u] if u < len(cs) else None
        return x[0] if isinstance(x, list) and x else 'PASS'

    claimed = set()
    while w.t < 696:
        t = w.t
        d, h = t // 24, t % 24
        if h == 0:
            claimed = set()
        if t >= 264 and h >= 1:
            farm = w.farms[seat]
            units = [tuple(farm['farmer'])] + [tuple(q) for q in farm['hands']]
            later_w = set()                          # tiles someone waters later today
            for tt in range(t, d * 24 + 24):
                a = s[tt] if tt < len(s) and isinstance(s[tt], dict) else {}
            for u, p in enumerate(units):
                if cmd(t, u) != 'PASS' or (t > d * 24 and cmd(t - 1, u) == 'PASS' and h > 1):
                    continue                         # only the first hour of an idle stretch
                L = 0
                while t + L < d * 24 + 24 and cmd(t + L, u) == 'PASS':
                    L += 1
                if t + L < d * 24 + 24:
                    continue                         # not an end-of-day stretch (the hand works again later)
                c['stretches'] += 1
                c['stretch_hours'] += L
                inv = w.private(seat)['inventories'][u] if u < len(w.private(seat)['inventories']) else {}
                has_f = int((inv or {}).get('FERTILIZER', 0) or 0) > 0
                best = {}
                for y, row in enumerate(farm['tiles']):
                    for x, tl in enumerate(row):
                        if not (isinstance(tl, dict) and tl.get('kind') == 'PLANT') or (y * 10 + x) in claimed:
                            continue
                        crop = tl['crop'] if tl['crop'] in ('STRAWBERRY', 'WHEAT') else None
                        if crop is None:
                            continue
                        gg = gain(tl, d)
                        if gg <= 0:
                            continue
                        need = abs(p[0] - x) + abs(p[1] - y) + 1 + (0 if tl.get('watered_today') else 1)
                        if need <= L and (crop not in best or (gg, -need) > best[crop][:2]):
                            best[crop] = (gg, -need, y * 10 + x)
                for crop, (gg, nn, idx) in best.items():
                    c[crop + '|reach'] += 1
                    c[crop + '|gain'] += gg
                    c[crop + '|hours'] += -nn
                    if has_f:
                        c[crop + '|reach_with_fert'] += 1
                if best:
                    crop = max(best, key=lambda k: best[k][0])
                    claimed.add(best[crop][2])
                    c['any|reach'] += 1
        own = s[t] if (t >= 264 and t < len(s) and isinstance(s[t], dict) and s[t]) else (UE.tape_action(tape['actions'], t) if t < 264 else dict(UE.PASS))
        a2 = [None, None]
        a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
    return dict(c)


if __name__ == '__main__':
    arm = sys.argv[1]
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
    tot = Counter()
    with Pool(nw) as pool:
        for r in pool.imap_unordered(job, [(g, arm) for g in games]):
            tot.update(r)
    n = len(games)
    print(f'{arm}: end-of-day idle stretches {tot["stretches"] / n:.1f} a world ({tot["stretch_hours"] / n:.1f} hand-hours)')
    for crop in ('STRAWBERRY', 'WHEAT'):
        k = tot[crop + '|reach']
        print(f'   {crop:10s}: stretches that could reach a useful fertilize {k / n:.1f} a world (with fertilizer in hand at the time '
              f'{tot[crop + "|reach_with_fert"] / n:.1f}) | gain {tot[crop + "|gain"] / n:.1f} units a world | hours used {tot[crop + "|hours"] / n:.1f}')
    print(f'   either crop (distinct targets): {tot["any|reach"] / n:.1f} stretches a world')
