"""Strawberry watering over the 40-world panel (days 11-28), the leader's game vs an arm's: every strawberry tile-day at
the end-of-day refresh classified by whether it was watered, whether tonight is a production night (end of p+9 / p+11 /
p+13 / p+15), fertilized, and whether it was watered yesterday - production-night water on a fertilized plant (buys the
second unit), production-night water unfertilized (survival only), off-night water after a watered day (no survival or
yield need: wasted), off-night water after a dry day (survival), and dry days. Also the number of strawberry waters a
day by day parity, and the planting-day parity mix (staggered blocks).
usage: panel_straw_water.py <ARM> [--workers 4]"""
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
R = {'farm': None, 'c': None}
_rp = E._daily_refresh_plants


def rp(farm, current_day, turns_per_day):
    if farm is R['farm'] and current_day >= 11:
        c = R['c']
        for row in farm['tiles']:
            for t in row:
                if not (isinstance(t, dict) and t.get('kind') == 'PLANT' and t.get('crop') == 'STRAWBERRY'):
                    continue
                pd = t['planted_day']
                k = current_day + 1 - pd - CD['first_yield_day']
                prod = k >= 0 and k % CD['interval'] == 0 and k // CD['interval'] + 1 <= CD['max_yield']
                w = bool(t['watered_today'])
                dry_y = t['consecutive_unwatered'] >= 1          # yesterday was dry (value before tonight's update)
                fz = t.get('fertilized_until_day', -1) >= current_day
                if w:
                    c['water_par%d' % (current_day % 2)] += 1
                    if prod:
                        key = 'w_prod_fert' if fz else 'w_prod_nofert'
                    else:
                        key = 'w_off_after_dry' if dry_y else 'w_off_after_wet'
                else:
                    key = 'dry_prod' if prod else 'dry_off'
                c[key] += 1
                c['plantday_par%d' % (pd % 2)] += 1
    return _rp(farm, current_day, turns_per_day)


E._daily_refresh_plants = rp


def play(tape, stream):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    c = Counter()
    R.update(c=c)
    while w.t < 696:
        t = w.t
        R['farm'] = w.farms[seat]
        own = UE.tape_action(tape['actions'], t) if (stream is None or t < 264) else (stream[t] if isinstance(stream[t], dict) and stream[t] else dict(UE.PASS))
        a2 = [None, None]
        a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
    return c


def job(args):
    g, arm = args
    team, ep = g.split(':')
    ep = ep.strip()
    tape = UE.load_tape(int(team), int(ep))
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    out = Counter({'L|' + k: v for k, v in play(tape, None).items()})
    out.update({'A|' + k: v for k, v in play(tape, s).items()})
    return dict(out)


if __name__ == '__main__':
    arm = sys.argv[1]
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
    tot = Counter()
    with Pool(nw) as pool:
        for r in pool.imap_unordered(job, [(g, arm) for g in games]):
            tot.update(r)
    n = len(games)
    for side, lab in (('L|', 'DSM'), ('A|', arm)):
        g = lambda k: tot[side + k] / n
        tw = sum(g(k) for k in ('w_prod_fert', 'w_prod_nofert', 'w_off_after_dry', 'w_off_after_wet'))
        print(f'{lab}: strawberry waters {tw:.1f} a world | production night + fertilized {g("w_prod_fert"):.1f} | production night, unfertilized '
              f'{g("w_prod_nofert"):.1f} | off night after a dry day (survival) {g("w_off_after_dry"):.1f} | off night after a watered day (no need) '
              f'{g("w_off_after_wet"):.1f} | dry: production night {g("dry_prod"):.1f}, off night {g("dry_off"):.1f}')
        print(f'      waters on even days {g("water_par0"):.1f} / odd days {g("water_par1"):.1f} | strawberry tile-days planted on even {g("plantday_par0"):.0f} / odd {g("plantday_par1"):.0f} days')
