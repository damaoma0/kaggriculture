"""Strawberry fertilize timing over the 40-world panel (days 11-28), the leader's game vs an arm's: every successful
FERTILIZE on a strawberry by its day in the plant's cycle (day - planted day; productions at the end of p+9, p+11, p+13,
p+15), the production nights it newly covers (0 / 1 / 2), and for every production night whether it was fertilized,
watered, both (2 units) - so which part of the cycle each side leaves unfertilized.
usage: panel_straw_fert_timing.py <ARM> [--workers 4]"""
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
R = {'farm': None, 'c': None, 'day': 0}
_ua, _rp = E._apply_unit_action, E._daily_refresh_plants


def nights(pd):
    return [pd + CD['first_yield_day'] - 1 + CD['interval'] * k for k in range(CD['max_yield'])]


def ua(farm, private, idx, action, *a, **k):
    if farm is R['farm'] and R['day'] >= 11 and isinstance(action, list) and action and action[0] == 'FERTILIZE':
        x, y = (farm['farmer'] if idx == 0 else farm['hands'][idx - 1])
        t = farm['tiles'][y][x]
        if isinstance(t, dict) and t.get('crop') == 'STRAWBERRY':
            fu0 = t.get('fertilized_until_day', -1)
            r = _ua(farm, private, idx, action, *a, **k)
            if t.get('fertilized_until_day', -1) != fu0:
                d, pd = R['day'], t['planted_day']
                new = sum(1 for n in nights(pd) if d <= n <= d + 2 and n > fu0)
                R['c']['fday|%+d' % (d - pd)] += 1
                R['c']['covers|%d' % new] += 1
            return r
    return _ua(farm, private, idx, action, *a, **k)


def rp(farm, current_day, turns_per_day):
    if farm is R['farm'] and current_day >= 11:
        for row in farm['tiles']:
            for t in row:
                if isinstance(t, dict) and t.get('kind') == 'PLANT' and t.get('crop') == 'STRAWBERRY':
                    pd = t['planted_day']
                    if current_day in nights(pd):
                        k = nights(pd).index(current_day) + 1
                        f = t.get('fertilized_until_day', -1) >= current_day
                        w = bool(t['watered_today'])
                        R['c']['night%d|%s' % (k, 'fert+water' if f and w else ('fert,dry' if f else ('water' if w else 'none')))] += 1
    return _rp(farm, current_day, turns_per_day)


E._apply_unit_action, E._daily_refresh_plants = ua, rp


def play(tape, stream):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    c = Counter()
    R.update(c=c)
    while w.t < 696:
        t = w.t
        R['farm'] = w.farms[seat]
        R['day'] = t // 24
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
        fk = [(k, v) for k, v in tot.items() if k.startswith(side + 'fday|')]
        fd = {k.split('|')[-1]: round(v / n, 1) for k, v in sorted(fk, key=lambda kv: int(kv[0].split('|')[-1]))}
        print(f'{lab}: strawberry fertilizes by day in the cycle (day - planted; productions at +9/+11/+13/+15): {fd}')
        print(f'      production nights newly covered per fertilize: 2 -> {g("covers|2"):.1f}, 1 -> {g("covers|1"):.1f}, 0 -> {g("covers|0"):.1f}')
        for k in range(1, 5):
            print(f'      production {k}: ' + ', '.join(f'{s_} {g("night%d|%s" % (k, s_)):.1f}' for s_ in ('fert+water', 'fert,dry', 'water', 'none')))
