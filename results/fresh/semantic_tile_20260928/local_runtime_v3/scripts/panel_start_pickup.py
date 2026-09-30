"""Start-of-day shed pickups over the 40-world panel (days 11-28) for an arm: for every hand-day, whether the hand's
first action(s) at the shed include a PICKUP (and of what), its first non-shed action hour, the shed's fertilizer at the
start of the day (after the midnight dump) and at the first pickup hour, whether the hand ends the day with idle hours,
and fertilizer carried. Answers: how many hands leave without picking anything up, and how much fertilizer the shed holds
when they leave.
usage: panel_start_pickup.py <ARM> [--workers 4]"""
import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

SHED = {(4, 4), (5, 4), (4, 5), (5, 5)}


def job(args):
    g, arm = args
    team, ep = g.split(':')
    ep = ep.strip()
    tape = UE.load_tape(int(team), int(ep))
    s = None if arm == 'DSM' else json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    c = Counter()
    days = {}                                          # (day, unit) -> info
    while w.t < 696:
        t = w.t
        d, h = t // 24, t % 24
        own = UE.tape_action(tape['actions'], t) if (s is None or t < 264) else (s[t] if isinstance(s[t], dict) and s[t] else dict(UE.PASS))
        if t >= 264:
            farm = w.farms[seat]
            units = [tuple(farm['farmer'])] + [tuple(q) for q in farm['hands']]
            cmds = [own.get('farmer')] + list(own.get('hands') or [])
            shed_f = w.private(seat)['shed'].get('FERTILIZER', 0)
            if h == 0:
                c['shed_fert_h0'] += shed_f
                c['days'] += 1
            for u, p in enumerate(units):
                cm = cmds[u] if u < len(cmds) else None
                op = cm[0] if isinstance(cm, list) and cm else 'PASS'
                k = (d, u)
                if k not in days:
                    days[k] = {'left': False, 'pick': [], 'idle_end': 0, 'fert_start': None}
                I = days[k]
                if not I['left']:
                    if op == 'PICKUP':
                        I['pick'].append(cm[1] if len(cm) > 1 else '?')
                        if cm[1:2] == ['FERTILIZER']:
                            c['fert_picked'] += int(cm[2]) if len(cm) > 2 else 1
                    elif op != 'PASS' and op != 'DROP' and p not in SHED or op in ('NORTH', 'SOUTH', 'EAST', 'WEST') and p in SHED:
                        I['left'] = True
                        I['shed_fert_left'] = shed_f
                I['idle_end'] = I['idle_end'] + 1 if op == 'PASS' else 0
        a2 = [None, None]
        a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
    for (d, u), I in days.items():
        if u == 0:
            continue                                   # hands only
        c['hand_days'] += 1
        kinds = set(I['pick'])
        key = 'none' if not kinds else '+'.join(sorted(kinds))
        c['pick|' + key] += 1
        spare = I['idle_end'] >= 1
        c['spare|' + ('yes' if spare else 'no')] += 1
        if spare and not kinds:
            c['spare_nopick'] += 1
        if spare and kinds:
            c['spare_pick'] += 1
        c['shed_fert_when_left'] += I.get('shed_fert_left', 0)
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
    hd = tot['hand_days']
    print(f'{arm}: hand-days {hd / n:.0f} a world | start-of-day pickups: ' +
          ', '.join(f'{k.split("|")[1]} {v / n:.1f}' for k, v in sorted(tot.items(), key=lambda kv: -kv[1]) if k.startswith('pick|')))
    print(f'   hand-days ending with idle hours {tot["spare|yes"] / n:.1f} (of them no pickup at the start {tot["spare_nopick"] / n:.1f}, with a pickup '
          f'{tot["spare_pick"] / n:.1f}) | shed fertilizer at hour 0 {tot["shed_fert_h0"] / max(1, tot["days"]):.1f} a day, when a hand leaves '
          f'{tot["shed_fert_when_left"] / max(1, hd):.1f} | fertilizer picked up {tot["fert_picked"] / n:.1f} a world')
