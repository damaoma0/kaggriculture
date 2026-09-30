"""Harvest days of an animal's pens (or a crop's tiles), the leader's game vs an arm's, over the 40-world panel (days
11-29; the boards are tile-exact, so the same tile is the same pen). A harvest = the tile's yield drops during a step.
Per world: pen-days harvested by both / by DSM only / by us only; for DSM-only days, how many days later we harvested
that tile and the units we left on it; our yield on the tile when DSM harvested it.
usage: panel_harvest_days.py <ARM> <ANIMAL-or-CROP> [--workers 4]"""
import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402


def kind_of(tl):
    if not isinstance(tl, dict):
        return None
    return tl.get('animal') or tl.get('crop')


def play(tape, stream, what):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    hv = {}                                           # (day, idx) -> units harvested
    ystart = {}                                       # (day, idx) -> yield at the day start
    while w.t < 719:
        t = w.t
        before = {}
        for y, row in enumerate(w.farms[seat]['tiles']):
            for x, tl in enumerate(row):
                if kind_of(tl) == what:
                    before[y * 10 + x] = int(tl.get('yield_units', 0) or 0)
                    if t % 24 == 0:
                        ystart[(t // 24, y * 10 + x)] = before[y * 10 + x]
        own = UE.tape_action(tape['actions'], t) if (stream is None or t < 264) else (stream[t] if isinstance(stream[t], dict) and stream[t] else dict(UE.PASS))
        a2 = [None, None]
        a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
        if t < 264 or t % 24 == 23:
            continue                                   # skip the end-of-day step (production / death change yields)
        for y, row in enumerate(w.farms[seat]['tiles']):
            for x, tl in enumerate(row):
                i = y * 10 + x
                if i in before and kind_of(tl) == what and int(tl.get('yield_units', 0) or 0) < before[i]:
                    hv[(t // 24, i)] = hv.get((t // 24, i), 0) + before[i] - int(tl.get('yield_units', 0) or 0)
    return hv, ystart


def job(args):
    g, arm, what = args
    team, ep = g.split(':')
    ep = ep.strip()
    tape = UE.load_tape(int(team), int(ep))
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    hL, _ = play(tape, None, what)
    hA, yA = play(tape, s, what)
    c = Counter()
    for (d, i), n in hL.items():
        if d < 11:
            continue
        if (d, i) in hA:
            c['both'] += 1
            continue
        c['dsm_only'] += 1
        c['dsm_only_units'] += n
        c['our_yield_then'] += yA.get((d, i), 0)
        later = [dd for (dd, ii) in hA if ii == i and dd > d]
        if later:
            k = min(later) - d
            c['we_later_%s' % (k if k < 3 else '3+')] += 1
        else:
            c['we_never'] += 1
    for (d, i), n in hA.items():
        if d >= 11 and (d, i) not in hL:
            c['us_only'] += 1
            c['us_only_units'] += n
    return dict(c)


if __name__ == '__main__':
    arm, what = sys.argv[1], sys.argv[2]
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
    tot = Counter()
    with Pool(nw) as pool:
        for r in pool.imap_unordered(job, [(g, arm, what) for g in games]):
            tot.update(r)
    n = len(games)
    print(f'{what} ({arm}) per world: pen-days harvested by both {tot["both"] / n:.1f} | DSM only {tot["dsm_only"] / n:.1f} '
          f'({tot["dsm_only_units"] / n:.1f} units DSM took; our yield on those tiles then {tot["our_yield_then"] / max(1, tot["dsm_only"]):.1f} a pen) '
          f'| us only {tot["us_only"] / n:.1f} ({tot["us_only_units"] / n:.1f} units)')
    print('   DSM-only pen-days, when we harvested that pen next: ' + ', '.join(
        f'{k} {tot[k] / n:.1f}' for k in ('we_later_1', 'we_later_2', 'we_later_3+', 'we_never')))
