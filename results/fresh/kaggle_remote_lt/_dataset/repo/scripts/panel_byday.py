"""Per-day product flows, the leader's game vs an arm's, averaged over the 40-world panel: our units sold and revenue,
the rival's units and revenue, units left on the tiles at the day-start (animals / plants holding yield) and the herd /
plant count. Shows WHEN a product's margin gap (and the rival's windfall) opens.
usage: panel_byday.py <ARM> <PRODUCT> [--workers 4]"""
import json
import sys
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import panel_windfall as PW  # noqa: E402

UE = PW.UE
E = PW.E
PROD_OF = {a: v['product'] for a, v in E.ANIMALS.items()}


def tiles_held(w, seat, p):
    n = k = 0
    for row in w.farms[seat]['tiles']:
        for tl in row:
            if not isinstance(tl, dict):
                continue
            prod = PROD_OF.get(tl.get('animal')) if tl.get('animal') else tl.get('crop')
            if prod == p:
                k += 1
                n += int(tl.get('yield_units', 0) or 0)
    return n, k


def play(tape, stream, p):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    PW.R.update(w=w, seat=seat, ev=[], P=(p,))
    held = {}
    while w.t < 719:
        t = w.t
        PW.R['t'] = t
        if t >= 264 and t % 24 == 0:
            held[t // 24] = tiles_held(w, seat, p)
        own = UE.tape_action(tape['actions'], t) if (stream is None or t < 264) else (stream[t] if isinstance(stream[t], dict) and stream[t] else dict(UE.PASS))
        a2 = [None, None]
        a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
    PW.R['w'] = None
    return list(PW.R['ev']), held


def job(args):
    g, arm, p = args
    team, ep = g.split(':')
    ep = ep.strip()
    tape = UE.load_tape(int(team), int(ep))
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    out = {}
    for name, stream in (('L', None), ('A', s)):
        ev, held = play(tape, stream, p)
        c = defaultdict(float)
        for t, who, item, px in ev:
            d = t // 24
            c[(d, who, 'n')] += 1
            c[(d, who, '$')] += px
        for d, (n, k) in held.items():
            c[(d, 'tiles', 'n')] += n
            c[(d, 'tiles', 'k')] += k
        out[name] = {'|'.join(map(str, k)): v for k, v in c.items()}
    return out


if __name__ == '__main__':
    arm, p = sys.argv[1], sys.argv[2]
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
    tot = {'L': defaultdict(float), 'A': defaultdict(float)}
    with Pool(nw) as pool:
        for r in pool.imap_unordered(job, [(g, arm, p) for g in games]):
            for name, c in r.items():
                for k, v in c.items():
                    tot[name][k] += v
    n = len(games)
    g = lambda name, d, who, kk: tot[name].get(f'{d}|{who}|{kk}', 0.0) / n
    print(f'{p}: per world and day, DSM game vs {arm} game (units / revenue); tiles = yield held on our tiles at the day start')
    print(' day | our n DSM->arm | our $ DSM->arm (diff) | rival n | rival $ DSM->arm (diff) | tiles held DSM->arm | tiles DSM->arm')
    cum = [0.0, 0.0]
    for d in range(11, 30):
        ou = g('A', d, 'us', '$') - g('L', d, 'us', '$')
        rv = g('A', d, 'opp', '$') - g('L', d, 'opp', '$')
        cum[0] += ou
        cum[1] += rv
        print(f' {d:3d} | {g("L", d, "us", "n"):5.1f} -> {g("A", d, "us", "n"):5.1f} | {g("L", d, "us", "$"):6.0f} -> {g("A", d, "us", "$"):6.0f} ({ou:+5.0f})'
              f' | {g("L", d, "opp", "n"):5.1f} -> {g("A", d, "opp", "n"):5.1f} | {g("L", d, "opp", "$"):6.0f} -> {g("A", d, "opp", "$"):6.0f} ({rv:+5.0f})'
              f' | {g("L", d, "tiles", "n"):5.1f} -> {g("A", d, "tiles", "n"):5.1f} | {g("L", d, "tiles", "k"):4.1f} -> {g("A", d, "tiles", "k"):4.1f}'
              f' | margin cum {cum[0] - cum[1]:+6.0f}')
