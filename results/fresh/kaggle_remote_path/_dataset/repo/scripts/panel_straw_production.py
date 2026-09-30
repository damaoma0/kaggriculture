"""Strawberry production, the leader's game vs an arm's, over the 40-world panel (days 11-28): at every end-of-day
refresh (engine _daily_refresh_plants, our farm only) each strawberry tile that produces tonight - fertilized AND
watered (2 units) / fertilized but not watered (bonus lost, 1) / not fertilized (1) - plus plants that die tonight
(two unwatered days), units lost at the max-yield cap, and the planting day of every producing tile compared with
the same tile in the leader's game (same tile, same planting day = same production calendar).
usage: panel_straw_production.py <ARM> [--workers 4] [--worlds file]"""
import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
CD = E.CROPS['STRAWBERRY']
R = {'farm': None, 'c': None, 'pd': None}
_orig = E._daily_refresh_plants


def hook(farm, current_day, turns_per_day):
    if farm is R['farm'] and current_day >= 11:
        c = R['c']
        for y, row in enumerate(farm['tiles']):
            for x, t in enumerate(row):
                if not (isinstance(t, dict) and t.get('kind') == 'PLANT' and t.get('crop') == 'STRAWBERRY'):
                    continue
                w = bool(t['watered_today'])
                if not w and t['consecutive_unwatered'] + 1 >= 2:
                    c['died'] += 1
                    continue
                dsf = current_day + 1 - t['planted_day'] - CD['first_yield_day']
                if dsf < 0 or dsf % CD['interval'] != 0 or dsf // CD['interval'] + 1 > CD['max_yield']:
                    continue
                fz = t.get('fertilized_until_day', -1) >= current_day
                add = 2 if (fz and w) else 1
                c['prod_events'] += 1
                c['prod_fw' if (fz and w) else ('prod_f_nowater' if fz else 'prod_nofert')] += 1
                c['units_made'] += min(CD['max_yield'], t['yield_units'] + add) - t['yield_units']
                c['units_capped'] += t['yield_units'] + add - min(CD['max_yield'], t['yield_units'] + add)
                R['pd'][(current_day, y * 10 + x)] = t['planted_day']
    return _orig(farm, current_day, turns_per_day)


E._daily_refresh_plants = hook


def play(tape, stream):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    c, pd = Counter(), {}
    R.update(farm=w.farms[seat], c=c, pd=pd)
    while w.t < 696:
        t = w.t
        R['farm'] = w.farms[seat]
        own = UE.tape_action(tape['actions'], t) if (stream is None or t < 264) else (stream[t] if isinstance(stream[t], dict) and stream[t] else dict(UE.PASS))
        a2 = [None, None]
        a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
    return c, pd


def job(args):
    g, arm = args
    team, ep = g.split(':')
    ep = ep.strip()
    tape = UE.load_tape(int(team), int(ep))
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    cL, pL = play(tape, None)
    cA, pA = play(tape, s)
    out = Counter({'L_' + k: v for k, v in cL.items()})
    out.update({'A_' + k: v for k, v in cA.items()})
    for key, p in pA.items():                          # our producing tile-nights vs the leader's same tile
        if key in pL:
            out['same_night_same_tile'] += 1
            out['same_planting_day' if pL[key] == p else 'other_planting_day'] += 1
        else:
            out['ours_only_night'] += 1
    for key in pL:
        if key not in pA:
            out['dsm_only_night'] += 1
    return dict(out)


if __name__ == '__main__':
    arm = sys.argv[1]
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    wf = sys.argv[sys.argv.index('--worlds') + 1] if '--worlds' in sys.argv else 'results/fresh/threads_20260928/panel_dsm40b.txt'
    games = (ROOT / wf).read_text().replace(',', ' ').split()
    tot = Counter()
    with Pool(nw) as pool:
        for r in pool.imap_unordered(job, [(g, arm) for g in games]):
            tot.update(r)
    n = len(games)
    for side, lab in (('L_', 'DSM'), ('A_', arm)):
        g = lambda k: tot[side + k] / n
        print(f'{lab:5s} per world: production events {g("prod_events"):.1f} | fertilized+watered (2 units) {g("prod_fw"):.1f} | '
              f'fertilized, not watered (bonus lost) {g("prod_f_nowater"):.1f} | not fertilized {g("prod_nofert"):.1f} | units made '
              f'{g("units_made"):.1f} | lost at the 4-unit cap {g("units_capped"):.1f} | plants died {g("died"):.1f}')
    print(f'production tile-nights: both {tot["same_night_same_tile"] / n:.1f} (same planting day {tot["same_planting_day"] / n:.1f}, other '
          f'{tot["other_planting_day"] / n:.1f}) | DSM only {tot["dsm_only_night"] / n:.1f} | ours only {tot["ours_only_night"] / n:.1f}')
