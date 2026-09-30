"""Harvest timing, stage 2: tables from results/fresh/harvest_timing_20260925/<tag>/ (written by
scripts/harvest_timing_extract.py). Stored data only.

usage: .venv/Scripts/python.exe scripts/harvest_timing_report.py [--tag leaders] [--section ages,flow,...]
Sections:
  ages   one-time crops (wheat, carrot, melon): harvest age, units, fertilizer, gain from one more day, hour
  ongo   ongoing crops (tomato, strawberry): held units at harvest, productions accumulated, cap waste, decay
  flow   harvest -> shed -> sale delays (hours, same day / next day)
  teams  wheat / carrot / melon harvest age by team
Periods are by HARVEST day: 0-5, 6-11, 12-17, 18-23, 24-29.
"""
import argparse
import gzip
import json
import math
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from harvest_timing_extract import CROP, OUT  # noqa: E402

PERIODS = [(0, 5), (6, 11), (12, 17), (18, 23), (24, 29)]
PNAME = ['d0-5', 'd6-11', 'd12-17', 'd18-23', 'd24-29']


def period(d):
    return min(4, d // 6)


def iter_games(tag):
    """yield (ep, team, plants, harvests, days) per game; the three files are written in the same game order."""
    base = OUT / tag
    fp = gzip.open(base / 'plants.jsonl.gz', 'rt', encoding='utf-8')
    fh = gzip.open(base / 'harvests.jsonl.gz', 'rt', encoding='utf-8')
    fd = gzip.open(base / 'days.jsonl.gz', 'rt', encoding='utf-8')

    def grouped(f):
        cur, buf = None, []
        for line in f:
            r = json.loads(line)
            if r['ep'] != cur and buf:
                yield cur, buf
                buf = []
            cur = r['ep']
            buf.append(r)
        if buf:
            yield cur, buf

    gp, gh, gd = grouped(fp), grouped(fh), grouped(fd)
    nh = next(gh, (None, []))
    for ep, plants in gp:
        _, days = next(gd)
        hv = []
        if nh[0] == ep:
            hv = nh[1]
            nh = next(gh, (None, []))
        yield ep, plants[0]['team'], plants, hv, days


def q(xs, p):
    if not xs:
        return float('nan')
    xs = sorted(xs)
    k = (len(xs) - 1) * p
    lo, hi = math.floor(k), math.ceil(k)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def one_more_day_gain(c, rec):
    """units gained by harvesting the same plant one day later at the same hour (watered that day if in window);
    negative = decay."""
    age, units, d, h = rec['age'], rec['units'], rec['d'], rec['h']
    gain = 0
    # today's missed watering (harvested before the day's WATER) would still be credited if it waited
    if not rec['wt_before'] and (c['M'] + 1) // 2 <= age <= c['M']:
        gain += min(c['cap'] - units, 2 if rec['fu'] >= d else 1)
    if age + 1 <= c['M']:
        gain += min(c['cap'] - units - gain, 2 if rec['fu'] >= d + 1 else 1)
    else:
        mls = (rec['pd'] + c['M'] + 1) * 24
        s1 = (d + 1) * 24 + h
        s0 = d * 24 + h
        dec = lambda s: 0 if s <= mls else (s - mls + 1) // 2
        gain -= min(units, dec(s1) - dec(s0))
    return gain


def sec_ages(tag):
    A = defaultdict(lambda: defaultdict(list))
    for ep, team, plants, hv, days in iter_games(tag):
        pl = {p['id']: p for p in plants}
        for r in hv:
            c = CROP[r['crop']]
            if c['ongoing']:
                continue
            k = (r['crop'], period(r['d']))
            a = A[k]
            p = pl[r['plant']]
            fert = any(fd <= r['d'] for fd, fh in p['ferts'])
            a['age'].append(r['age'])
            a['units'].append(r['units'])
            a['fert'].append(int(fert))
            a['cap'].append(int(r['units'] >= c['cap']))
            a['hour'].append(r['h'])
            a['gain1'].append(one_more_day_gain(c, r))
            a['wt_before'].append(int(r['wt_before']))
            a['decay'].append(r['decay_loss'])
            # yield at the end of the previous day (harvest one day earlier after that day's watering)
            if r['age'] - 1 >= c['F']:
                a['loss1'].append(r['units'] - p['yend'].get(str(r['d'] - 1), r['units']))
            a['replant_same_day'].append(int(bool(r.get('replant')) and r['replant'][0] == r['d']))
            a['ep'].append(ep)
    out = {}
    for crop in ('WHEAT', 'CARROT', 'MELON'):
        c = CROP[crop]
        ages = sorted({x for (cr, pi), a in A.items() if cr == crop for x in a['age']})
        amax = max(ages) if ages else 0
        agecols = list(range(c['F'], min(amax, c['M'] + 2) + 1))
        print(f"\n{crop} (harvest allowed from age {c['F']}; growth window ages {(c['M'] + 1) // 2}-{c['M']}; cap "
              f"{c['cap']}; decay from age {c['M'] + 1} hour 0)")
        print('| period | harvests (games) | mean age | ' + ' | '.join(f'age {x}' for x in agecols[:-1]) +
              f' | age {agecols[-1]}+ | mean units | at cap | fertilized | watered before harvest | units lost '
              f'by harvesting 1 day earlier | units gained by 1 day later | hour median (IQR) | hour < 12 | '
              f'replanted same day |')
        print('|' + '---|' * (13 + len(agecols)))
        for pi in range(5):
            a = A.get((crop, pi))
            if not a or not a['age']:
                continue
            n = len(a['age'])
            ac = Counter(a['age'])
            shares = [ac.get(x, 0) / n for x in agecols[:-1]] + [sum(v for k, v in ac.items() if k >= agecols[-1]) / n]
            row = [PNAME[pi], f"{n} ({len(set(a['ep']))})", f"{st.mean(a['age']):.2f}"]
            row += [f'{100 * s:.0f}%' for s in shares]
            row += [f"{st.mean(a['units']):.2f}", f"{100 * st.mean(a['cap']):.0f}%", f"{100 * st.mean(a['fert']):.0f}%",
                    f"{100 * st.mean(a['wt_before']):.0f}%",
                    f"{st.mean(a['loss1']):.2f} (n {len(a['loss1'])})" if a['loss1'] else '-',
                    f"{st.mean(a['gain1']):+.2f}",
                    f"{q(a['hour'], .5):.0f} ({q(a['hour'], .25):.0f}-{q(a['hour'], .75):.0f})",
                    f"{100 * st.mean([h < 12 for h in a['hour']]):.0f}%",
                    f"{100 * st.mean(a['replant_same_day']):.0f}%"]
            print('| ' + ' | '.join(row) + ' |')
            out[f'{crop}|{pi}'] = {'n': n, 'mean_age': st.mean(a['age']), 'age_share': dict(zip(map(str, agecols), shares)),
                                   'units': st.mean(a['units']), 'hour_median': q(a['hour'], .5)}
    return out


def sec_ongo(tag):
    A = defaultdict(lambda: defaultdict(list))
    P = defaultdict(lambda: defaultdict(list))
    for ep, team, plants, hv, days in iter_games(tag):
        for r in hv:
            if not CROP[r['crop']]['ongoing']:
                continue
            a = A[(r['crop'], period(r['d']))]
            a['held'].append(r['units'])
            a['n_since'].append(r['n_since'])
            a['wasted_since'].append(r['wasted_since'])
            a['age'].append(r['age'])
            a['hour'].append(r['h'])
            a['at4'].append(int(r['units'] >= 4))
            a['ep'].append(ep)
        for p in plants:
            c = CROP[p['crop']]
            if not c['ongoing']:
                continue
            b = P[(p['crop'], period(p['pd']))]
            produced = sum(x[1] for x in p['prods'])
            wasted = sum(x[2] for x in p['prods'])
            harvested = sum(x[2] for x in p['harv'])
            end = p['end'] or ['?', 0, 0]
            b['n'].append(1)
            b['prods'].append(len(p['prods']))
            b['produced'].append(produced)
            b['wasted'].append(wasted)
            b['harvested'].append(harvested)
            b['harvests'].append(len(p['harv']))
            b['decay'].append(p['decay_loss'])
            b['weed_lost'].append(end[2] if end[0] == 'weed' else 0)
            b['dug_lost'].append(end[2] if end[0] == 'dug' else 0)
            b['end_alive'].append(int(end[0] == 'alive_end'))
            b['full4'].append(int(len(p['prods']) == 4))
            b['fert'].append(int(bool(p['ferts'])))
    for crop in ('TOMATO', 'STRAWBERRY'):
        c = CROP[crop]
        prod_ages = [c['F'] + k * c['I'] for k in range(4)]
        print(f"\n{crop}: productions at ages {prod_ages} (from the watering / fertilizer of the day before), held cap 4,"
              f" decay from age {prod_ages[-1] + 1} hour 0; harvests by HARVEST period")
        print('| period | harvests (games) | mean age | held units at harvest (mean) | held = 4 (cap) | productions '
              'since last harvest (mean) | harvests after a production was cut by the cap | units cut per harvest | '
              'hour median (IQR) |')
        print('|---|---|---|---|---|---|---|---|---|')
        for pi in range(5):
            a = A.get((crop, pi))
            if not a or not a['held']:
                continue
            n = len(a['held'])
            print(f"| {PNAME[pi]} | {n} ({len(set(a['ep']))}) | {st.mean(a['age']):.1f} | {st.mean(a['held']):.2f} | "
                  f"{100 * st.mean(a['at4']):.0f}% | {st.mean(a['n_since']):.2f} | "
                  f"{100 * st.mean([w > 0 for w in a['wasted_since']]):.1f}% | {st.mean(a['wasted_since']):.3f} | "
                  f"{q(a['hour'], .5):.0f} ({q(a['hour'], .25):.0f}-{q(a['hour'], .75):.0f}) |")
        print(f"\n{crop} plants by PLANTING period: output accounting per plant")
        print('| planted | plants | fertilized | productions (mean; all 4) | units produced | cut by cap | lost to decay |'
              ' lost when weeded / dug | harvests per plant | harvested units | alive at game end |')
        print('|---|---|---|---|---|---|---|---|---|---|---|')
        for pi in range(5):
            b = P.get((crop, pi))
            if not b or not b['n']:
                continue
            n = len(b['n'])
            print(f"| {PNAME[pi]} | {n} | {100 * st.mean(b['fert']):.0f}% | {st.mean(b['prods']):.2f} "
                  f"({100 * st.mean(b['full4']):.0f}%) | {st.mean(b['produced']):.2f} | {st.mean(b['wasted']):.3f} | "
                  f"{st.mean(b['decay']):.3f} | {st.mean(b['weed_lost']):.3f} / {st.mean(b['dug_lost']):.3f} | "
                  f"{st.mean(b['harvests']):.2f} | {st.mean(b['harvested']):.2f} | {100 * st.mean(b['end_alive']):.0f}% |")


def sec_flow(tag):
    A = defaultdict(lambda: defaultdict(list))
    for ep, team, plants, hv, days in iter_games(tag):
        for r in hv:
            a = A[(r['crop'], period(r['d']))]
            hs = r['d'] * 24 + r['h']
            n = r['units']
            dl = r['deliv']
            if dl:
                a['to_shed_h'].extend([s - hs for s, k in dl for _ in range(k)])
                a['shed_same_day'].extend([int(s < (r['d'] + 1) * 24) for s, k in dl for _ in range(k)])
            for s, k in r['sold']:
                for _ in range(k):
                    a['sale_h'].append(s - hs)
                    a['sale_day'].append(s // 24 - r['d'])
            a['units'].append(n)
            a['sold_units'].append(sum(k for s, k in r['sold']))
            a['fed'].append(r['fed'])
            a['hour'].append(r['h'])
    print('\nHarvest -> shed -> sale (per unit, FIFO per product; the harvesting unit carries the units until its DROP /'
          ' PLACE at the shed, else the midnight dump; sales = the leader\'s SELL orders)')
    print('| crop | period | units | reach the shed same day | hours to the shed (median) | sold same day | next day | '
          '2+ days later | not sold / fed | hours to sale (median, IQR) |')
    print('|---|---|---|---|---|---|---|---|---|---|')
    for crop in ('WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON'):
        for pi in range(5):
            a = A.get((crop, pi))
            if not a or not a['units']:
                continue
            U = sum(a['units'])
            sd = Counter(min(2, x) for x in a['sale_day'])
            print(f"| {crop} | {PNAME[pi]} | {U} | {100 * st.mean(a['shed_same_day']):.0f}% | "
                  f"{q(a['to_shed_h'], .5):.0f} | {100 * sd.get(0, 0) / U:.0f}% | {100 * sd.get(1, 0) / U:.0f}% | "
                  f"{100 * sd.get(2, 0) / U:.0f}% | {100 * (U - len(a['sale_day'])) / U:.0f}% | "
                  f"{q(a['sale_h'], .5):.0f} ({q(a['sale_h'], .25):.0f}-{q(a['sale_h'], .75):.0f}) |")


def sec_teams(tag):
    A = defaultdict(list)
    for ep, team, plants, hv, days in iter_games(tag):
        for r in hv:
            if CROP[r['crop']]['ongoing']:
                continue
            A[(r['crop'], team, period(r['d']))].append((r['age'], r['units'], r['h']))
    teams = sorted({k[1] for k in A})
    for crop in ('WHEAT', 'CARROT', 'MELON'):
        print(f'\n{crop}: mean harvest age / units / median hour by team and period')
        print('| team | ' + ' | '.join(PNAME) + ' |')
        print('|---|' + '---|' * 5)
        for t in teams:
            cells = []
            for pi in range(5):
                v = A.get((crop, t, pi))
                cells.append(f"{st.mean(x[0] for x in v):.2f} / {st.mean(x[1] for x in v):.2f} / "
                             f"{q([x[2] for x in v], .5):.0f} (n {len(v)})" if v else '-')
            print(f'| {t} | ' + ' | '.join(cells) + ' |')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tag', default='leaders')
    ap.add_argument('--section', default='ages,ongo,flow,teams')
    args = ap.parse_args()
    secs = args.section.split(',')
    if 'ages' in secs:
        sec_ages(args.tag)
    if 'ongo' in secs:
        sec_ongo(args.tag)
    if 'flow' in secs:
        sec_flow(args.tag)
    if 'teams' in secs:
        sec_teams(args.tag)


if __name__ == '__main__':
    main()
