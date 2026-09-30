"""Fertilize ops on crops, the leader's game vs an arm's, over the 40-world panel (days 11-28): every successful
FERTILIZE (the tile's fertilized_until_day moved) classified by what it can still buy - the engine covers the day and
the next two; an ongoing crop (strawberry) produces every `interval` nights up to max_yield times, a one-time crop
(wheat / carrot / tomato / melon) earns its bonus in the harvest window - as useful (a production night in the window
not yet covered), redundant (every production night in the window already covered), end of life (no production left in
the window: after the last production), or too early (before the first yield). For end-of-life strawberries, the days
until the tile was replanted.
usage: panel_fert_waste.py <ARM> [--workers 4] [--worlds file]"""
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
R = {'farm': None, 'c': None, 'day': 0, 'eol': None}
_ua = E._apply_unit_action


def classify(t, day):
    cd = CROPS[t['crop']]
    if not cd['ongoing']:
        return 'onetime'
    pd = t['planted_day']
    nights = [d for d in (day, day + 1, day + 2)
              if (d + 1 - pd - cd['first_yield_day']) >= 0 and (d + 1 - pd - cd['first_yield_day']) % cd['interval'] == 0
              and (d + 1 - pd - cd['first_yield_day']) // cd['interval'] + 1 <= cd['max_yield']]
    last_night = pd + cd['first_yield_day'] - 1 + cd['interval'] * (cd['max_yield'] - 1)
    if not nights:
        return 'end_of_life' if day > last_night else 'too_early'
    if all(d <= t.get('fertilized_until_day', -1) for d in nights):
        return 'redundant'
    return 'useful'


def ua(farm, private, idx, action, *a, **k):
    if farm is R['farm'] and R['day'] >= 11 and isinstance(action, list) and action and action[0] == 'FERTILIZE':
        x, y = (farm['farmer'] if idx == 0 else farm['hands'][idx - 1])
        t = farm['tiles'][y][x]
        before = dict(t) if isinstance(t, dict) else None
        r = _ua(farm, private, idx, action, *a, **k)
        t2 = farm['tiles'][y][x]
        if before and before.get('kind') == 'PLANT' and isinstance(t2, dict) and t2.get('fertilized_until_day') != before.get('fertilized_until_day'):
            cl = classify(before, R['day'])
            R['c'][before['crop'] + '|' + cl] += 1
            if before['crop'] == 'STRAWBERRY' and cl == 'end_of_life':
                R['eol'].append((R['day'], y * 10 + x))
        return r
    return _ua(farm, private, idx, action, *a, **k)


E._apply_unit_action = ua


def play(tape, stream):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    c, eol = Counter(), []
    R.update(c=c, eol=eol)
    replant = {}
    while w.t < 696:
        t = w.t
        R['farm'] = w.farms[seat]
        R['day'] = t // 24
        own = UE.tape_action(tape['actions'], t) if (stream is None or t < 264) else (stream[t] if isinstance(stream[t], dict) and stream[t] else dict(UE.PASS))
        a2 = [None, None]
        a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
        if t % 24 == 23:
            for d0, i in eol:
                if (d0, i) not in replant:
                    tl = w.farms[seat]['tiles'][i // 10][i % 10]
                    if isinstance(tl, dict) and tl.get('kind') == 'PLANT' and tl.get('planted_day', -1) > d0:
                        replant[(d0, i)] = tl['planted_day'] - d0
    for d0, i in eol:
        k = replant.get((d0, i))
        c['eol_replant_' + (str(min(k, 4)) if k is not None else 'never')] += 1
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
    wf = sys.argv[sys.argv.index('--worlds') + 1] if '--worlds' in sys.argv else 'results/fresh/threads_20260928/panel_dsm40b.txt'
    games = (ROOT / wf).read_text().replace(',', ' ').split()
    tot = Counter()
    with Pool(nw) as pool:
        for r in pool.imap_unordered(job, [(g, arm) for g in games]):
            tot.update(r)
    n = len(games)
    for side, lab in (('L|', 'DSM'), ('A|', arm)):
        g = lambda k: tot[side + k] / n
        print(f'{lab:5s} strawberry fertilizes per world: useful {g("STRAWBERRY|useful"):.1f} | redundant {g("STRAWBERRY|redundant"):.1f} | end of '
              f'life {g("STRAWBERRY|end_of_life"):.1f} | too early {g("STRAWBERRY|too_early"):.1f} | one-time crops {sum(v for k, v in tot.items() if k.startswith(side) and k.endswith("|onetime")) / n:.1f}')
        print(f'      end-of-life strawberry tiles replanted after (days): ' + ', '.join(
            f'{k.split("_")[-1]}: {tot[side + k] / n:.1f}' for k in ('eol_replant_1', 'eol_replant_2', 'eol_replant_3', 'eol_replant_4', 'eol_replant_never')))
