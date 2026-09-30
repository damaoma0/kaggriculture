"""Labour slack in Mother-Goose's tapes (offline, all 584): how many paid hand-steps are idle, where in the day the
slack sits, whether the lightest hand's work would fit into the others' idle steps, and what the last hand costs.

A hand hired at step t exists from t+1 to the end of the day. Commands: PASS = idle; NORTH/SOUTH/EAST/WEST = travel;
anything else = work. Wages: the n-th hire of a day costs fib(n) (1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, ...).
Output: results/fresh/mg_tape/slack.json
"""
import glob
import gzip
import json
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOVES = {'NORTH', 'SOUTH', 'EAST', 'WEST'}
FIB = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987]


def day_units(actions, day):
    """{unit index: [command op per step it exists]} for one day (unit 0 = farmer)."""
    units = defaultdict(list)
    for t in range(day * 24, min(len(actions), day * 24 + 24)):
        a = actions[t] if isinstance(actions[t], dict) else {}
        cmds = [a.get('farmer') or ['PASS']] + [c or ['PASS'] for c in (a.get('hands') or [])]
        for i, c in enumerate(cmds):
            units[i].append((t % 24, c[0] if c else 'PASS'))
    return units


def main():
    paths = sorted(glob.glob(str(ROOT / 'data/mg_tapes/*/*.json.gz')))
    per_day = defaultdict(lambda: Counter())
    by_hour = Counter()
    hour_total = Counter()
    fits = Counter()
    light = []
    trailing = []
    last_wage = []
    wage_total = []
    hands_hist = Counter()
    for p in paths:
        t = json.load(gzip.open(p, 'rt', encoding='utf-8'))
        acts = t['actions']
        lw = wt = 0
        for day in range(30):
            units = day_units(acts, day)
            hands = {i: v for i, v in units.items() if i > 0}
            n = len(hands)
            if n:
                hands_hist[n] += 1
                lw += FIB[min(15, n - 1)]
                wt += sum(FIB[min(15, k)] for k in range(n))
            load = {}
            for i, seq in units.items():
                ops = [o for _, o in seq]
                pas = sum(1 for o in ops if o == 'PASS')
                mov = sum(1 for o in ops if o in MOVES)
                work = len(ops) - pas - mov
                last_busy = max([k for k, o in enumerate(ops) if o != 'PASS'], default=-1)
                per_day[day].update(steps=len(ops), idle=pas, travel=mov, work=work, units=1)
                if i > 0:
                    load[i] = (work, mov, pas)
                    trailing.append(len(ops) - 1 - last_busy)
                for h, o in seq:
                    hour_total[h] += 1
                    by_hour[h] += o == 'PASS'
            if 6 <= day <= 28 and len(load) >= 3:
                i_min = min(load, key=lambda i: load[i][0] + load[i][1])
                need = load[i_min][0] + load[i_min][1]
                spare = sum(v[2] for i, v in load.items() if i != i_min)
                light.append((load[i_min][0], load[i_min][1], spare))
                fits['days'] += 1
                fits['spare>=need'] += spare >= need
                fits['spare>=2x need'] += spare >= 2 * need
        last_wage.append(lw)
        wage_total.append(wt)
    tot = Counter()
    for d in per_day.values():
        tot.update(d)
    n = len(paths)
    print(f'{n} tapes. Paid unit-steps per game {tot["steps"] / n:,.0f}: work {tot["work"] / n:,.0f} ({tot["work"] / tot["steps"]:.0%}), '
          f'travel {tot["travel"] / n:,.0f} ({tot["travel"] / tot["steps"]:.0%}), idle {tot["idle"] / n:,.0f} ({tot["idle"] / tot["steps"]:.0%})')
    print('hands hired per day (days with hands):', {k: f'{v / sum(hands_hist.values()):.0%}' for k, v in sorted(hands_hist.items())})
    print('by phase          units/day   idle share   idle steps/day   work/day   travel/day')
    for lo, hi in ((0, 5), (6, 11), (12, 17), (18, 23), (24, 29)):
        c = Counter()
        for d in range(lo, hi + 1):
            c.update(per_day[d])
        days = (hi - lo + 1) * n
        print(f'  days {lo:>2}-{hi:<2}      {c["units"] / days:6.1f}      {c["idle"] / c["steps"]:6.0%}        {c["idle"] / days:6.1f}        {c["work"] / days:6.1f}     {c["travel"] / days:6.1f}')
    print('idle share by hour of day:', ' '.join(f'{h}:{by_hour[h] / max(1, hour_total[h]):.0%}' for h in range(24)))
    print(f'trailing idle per hand-day (steps after its last non-PASS command): median {st.median(trailing)}, mean {st.mean(trailing):.1f}, '
          f'share with >= 6 trailing idle steps {sum(1 for x in trailing if x >= 6) / len(trailing):.0%}')
    w = [x[0] for x in light]
    m = [x[1] for x in light]
    s = [x[2] for x in light]
    print(f'lightest hand of the day (days 6-28): work {st.mean(w):.1f} + travel {st.mean(m):.1f} steps; idle steps of all OTHER hands that day {st.mean(s):.1f}')
    print(f'  days where the others\' idle steps cover the lightest hand\'s work + travel: {fits["spare>=need"] / fits["days"]:.0%}; cover it twice: {fits["spare>=2x need"] / fits["days"]:.0%}')
    print(f'wages per game {st.mean(wage_total):,.0f}; the LAST hand of each day costs {st.mean(last_wage):,.0f} per game ({st.mean(last_wage) / st.mean(wage_total):.0%} of all wages); '
          f'marginal wage per paid step of that hand ~{st.mean(last_wage) / (25 * 22):.1f}')
    out = dict(tapes=n, per_game={k: v / n for k, v in tot.items()}, last_hand_wage=st.mean(last_wage), wages=st.mean(wage_total),
               fits={k: v for k, v in fits.items()})
    (ROOT / 'results/fresh/mg_tape/slack.json').write_text(json.dumps(out), encoding='utf-8')


if __name__ == '__main__':
    main()
