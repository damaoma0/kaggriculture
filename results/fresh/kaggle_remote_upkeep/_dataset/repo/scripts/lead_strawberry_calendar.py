"""Strawberry calendar: first day strawberry units are sold (and first day strawberry tiles are on the board),
leader vs our cells in the 12 G1 worlds, and y3 vs the deploy build in the p2750 smoke-test worlds.

usage: lead_strawberry_calendar.py [cell,...]   (default E2,R16)
"""
import gzip
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/lead_agent_20260924'
PANEL = ROOT / 'results/fresh/ladder_panel'


def first(seq):
    return next((i for i, v in enumerate(seq) if v), None)


def fmt(v):
    return '-' if v is None else str(v)


def leader_calendar(team, ep):
    sem = json.load(gzip.open(ROOT / f'data/leader_semantics/{team}/{ep}.json.gz', 'rt'))
    sold = [0] * 30
    rev = [0.0] * 30
    for i, d in enumerate(sem['days']):          # market of index i = actual day i+1 (index 0 = days 0+1)
        day = 1 if i == 0 else i + 1
        if day < 30:
            sold[day] += d['market']['sold_units'].get('STRAWBERRY', 0)
            rev[day] += d['market']['sold_revenue'].get('STRAWBERRY', 0)
    tiles = [sum(1 for x in d['board'] if x == 'ST') for d in sem['days']]
    return sold, rev, tiles


def cell_calendar(cell, ep):
    r = json.load(open(OUT / f'abl_{cell}/{ep}.json'))
    sold = [d['sold'].get('STRAWBERRY', 0) for d in r['days']]
    rev = [d['rev'].get('STRAWBERRY', 0) for d in r['days']]
    tiles = [sum(1 for i in range(0, 200, 2) if d['board'] and d['board'][i:i + 2] == 'ST') for d in r['days']]
    return sold, rev, tiles


def main():
    cells = (sys.argv[1] if len(sys.argv) > 1 else 'E2,R16').split(',')
    rows = sorted((OUT / f'abl_{cells[0]}').glob('1*.json'))
    print('G1 worlds: first strawberry tile day / first strawberry sale day / units sold by day 15 / revenue total')
    head = 'episode    leader' + ''.join(f'{c:>26}' for c in cells)
    print(head)
    agg = {c: [] for c in ['leader'] + cells}
    for f in rows:
        r = json.load(open(f))
        team, ep = r['game'].split(':')
        cal = {'leader': leader_calendar(team, ep)}
        for c in cells:
            if (OUT / f'abl_{c}/{ep}.json').exists():
                cal[c] = cell_calendar(c, ep)
        line = f'{ep} '
        for c in ['leader'] + cells:
            if c not in cal:
                line += f'{"n/a":>26}'
                continue
            sold, rev, tiles = cal[c]
            a, b = first(tiles), first(sold)
            u15 = sum(sold[:16])
            agg[c].append((a, b, u15, sum(rev)))
            line += f'{fmt(a):>6}/{fmt(b):>3}/{u15:>4}/{sum(rev):>8.0f} '
        print(line)
    print('mean       ' + '  '.join(
        f'{c}: tile d{st.mean(x[0] for x in v if x[0] is not None):.1f} sale d{st.mean(x[1] for x in v if x[1] is not None):.1f} '
        f'u15 {st.mean(x[2] for x in v):.0f} rev {st.mean(x[3] for x in v):.0f}' for c, v in agg.items() if v))
    # p2750 smoke worlds
    a, b = 'mgt_y3_cal', 'mgt_lead_deploy_s1'
    eps = sorted(f.stem for f in (PANEL / b).glob('*.json'))
    if eps:
        print(f'\np2750 smoke worlds: first strawberry sale day / units sold by day 15 / strawberry revenue ({a} vs {b})')
        fa, fb = [], []
        for e in eps:
            ra, rb = (json.load(open(PANEL / x / f'{e}.json')) for x in (a, b))
            out = []
            for rr, acc in ((ra, fa), (rb, fb)):
                rd = rr.get('revenue_daily') or []          # CUMULATIVE revenue snapshots, index = day boundary
                cum = [d.get('STRAWBERRY', 0) for d in rd]
                fd = first(cum)                              # first snapshot after the first strawberry sale
                fd = None if fd is None else fd - 1          # -> the day of the first sale
                by15 = cum[16] if len(cum) > 16 else 0
                acc.append((fd, by15, rr['revenue'].get('STRAWBERRY', 0), rr['sold'].get('STRAWBERRY', 0)))
                out.append(f'{fmt(fd):>3} {by15:>7.0f} {rr["revenue"].get("STRAWBERRY", 0):>7.0f} ({rr["sold"].get("STRAWBERRY", 0)} u)')
            print(e, ' | '.join(out))
        for name, acc in ((a, fa), (b, fb)):
            fd = [x[0] for x in acc if x[0] is not None]
            print(f'{name}: first sale day mean {st.mean(fd):.1f} (n={len(fd)}), strawberry revenue by day 15 {st.mean(x[1] for x in acc):.0f}, '
                  f'total {st.mean(x[2] for x in acc):.0f}, units {st.mean(x[3] for x in acc):.0f}')


if __name__ == '__main__':
    main()
