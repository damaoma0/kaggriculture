"""Leader plantings T misses or delays inside its planting window (stored ledger replays, 12 G1 worlds; no games).

usage: lead_missed_plantings.py [side=ours]
Per day and crop: the leader's plantings (data/leader_semantics 'planted') vs T's effective PLANTs (ledger 'plants').
A leader planting is 'on time' if T planted that crop the same day (count match), 'late' if T's cumulative count of
that crop catches up within the executor's catch-up window, else 'missed'. For deficits: T's seed purchases of that
crop that day (ledger 'bought' BUY_SEED:<crop>), failed seed buys, day-start cash, the plant_cutoff day, and T's PASS /
no-effect unit-steps that day (idle capacity).
"""
import gzip
import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
LED = ROOT / 'results/fresh/lead_ledger'
CUT = {'STRAWBERRY': 13, 'TOMATO': 18, 'MELON': 19, 'WHEAT': 25, 'CARROT': 26}
LATE = {'STRAWBERRY': 6, 'TOMATO': 5, 'MELON': 3, 'WHEAT': 1, 'CARROT': 1}
WIN = ((0, 5), (6, 11), (12, 17), (18, 23), (24, 29))


def main():
    import lead_g1
    side = sys.argv[1] if len(sys.argv) > 1 else 'ours'
    rows = {}
    for f in LED.glob('*_1*.json'):
        r = json.load(open(f))
        rows[(r['side'], r['episode'])] = r
    eps = sorted(e for s, e in rows if s == 'leader' and (side, e) in rows)
    g = len(eps)
    tot = Counter()
    by_win = defaultdict(Counter)
    reasons = Counter()
    day_detail = []
    for e in eps:
        team = next(x.split(':')[0] for x in lead_g1.GAMES if x.endswith(str(e)))
        sem = json.load(gzip.open(lead_g1.SEM / team / f'{e}.json.gz', 'rt', encoding='utf-8'))
        O = rows[(side, e)]
        for crop in CUT:
            lead = [len(sem['days'][d]['planted'].get(crop, [])) for d in range(30)]
            ours = [sum(1 for t, c in O['days'][d].get('plants', []) if c == crop) for d in range(30)]
            cum_l = cum_o = 0
            for d in range(30):
                cum_l += lead[d]
                cum_o += ours[d]
                if not lead[d]:
                    continue
                w = next(i for i, (a, b) in enumerate(WIN) if a <= d <= b)
                on = min(lead[d], ours[d])
                tot['leader'] += lead[d]
                tot['on time'] += on
                by_win[w]['leader'] += lead[d]
                by_win[w]['on time'] += on
                short = lead[d] - on
                if short <= 0:
                    continue
                # caught up within the catch-up window?
                later = sum(ours[d2] for d2 in range(d + 1, min(30, d + 1 + LATE[crop])))
                extra_later = max(0, min(short, later - sum(lead[d2] for d2 in range(d + 1, min(30, d + 1 + LATE[crop])))))
                late = min(short, max(0, extra_later))
                missed = short - late
                tot['late'] += late
                tot['missed'] += missed
                by_win[w]['late'] += late
                by_win[w]['missed'] += missed
                if d > CUT[crop]:
                    reasons['after the cutoff'] += short
                    continue
                dd = O['days'][d]
                bought = dd.get('bought', {}).get(f'BUY_SEED:{crop}', 0)
                failed = sum(v for k, v in dd.get('failed', {}).items() if k.startswith(f'BUY_SEED:{crop}'))
                idle = dd.get('passes', 0)
                if failed:
                    reasons['seed purchase failed (cash)'] += short
                elif bought < short and ours[d] == 0:
                    reasons['no / too few seeds bought that day'] += short
                elif idle >= 10:
                    reasons['seeds there, units idle (not dispatched / tile)'] += short
                else:
                    reasons['seeds there, crew busy'] += short
                day_detail.append((e, d, crop, lead[d], ours[d], bought, failed, dd.get('cash'), idle))
    print(f'{g} G1 worlds, leader plantings vs {side} (per game): leader {tot["leader"] / g:.1f}, on time {tot["on time"] / g:.1f}, '
          f'late (caught up in the catch-up window) {tot["late"] / g:.1f}, missed {tot["missed"] / g:.1f}')
    print('by planting window (leader / on time / late / missed): ' + '; '.join(
        f'd{a}-{b} {by_win[i]["leader"] / g:.1f} / {by_win[i]["on time"] / g:.1f} / {by_win[i]["late"] / g:.1f} / {by_win[i]["missed"] / g:.1f}'
        for i, (a, b) in enumerate(WIN)))
    print('short plantings by reason (per game): ' + '; '.join(f'{k} {v / g:.1f}' for k, v in reasons.most_common()))
    # days 5-11 (the handoff / cash-tight window): detail
    print('days 5-11 detail (per game, summed over crops): leader plantings / ours / seeds bought / failed seed buys / day-start cash / PASS steps')
    for d in range(5, 12):
        rows_d = [x for x in day_detail if x[1] == d]
        L = sum(sum(len(json.load(gzip.open(lead_g1.SEM / next(y.split(':')[0] for y in lead_g1.GAMES if y.endswith(str(e))) / f'{e}.json.gz', 'rt', encoding='utf-8'))['days'][d]['planted'].get(c, [])) for c in CUT) for e in eps) / g
        O_ = sum(sum(1 for t, c in rows[(side, e)]['days'][d].get('plants', [])) for e in eps) / g
        B_ = sum(sum(v for k, v in rows[(side, e)]['days'][d].get('bought', {}).items() if k.startswith('BUY_SEED')) for e in eps) / g
        F_ = sum(sum(v for k, v in rows[(side, e)]['days'][d].get('failed', {}).items() if k.startswith('BUY_SEED')) for e in eps) / g
        C_ = st.mean(rows[(side, e)]['days'][d].get('cash') or 0 for e in eps)
        P_ = sum(rows[(side, e)]['days'][d].get('passes', 0) for e in eps) / g
        CL = st.mean(rows[('leader', e)]['days'][d].get('cash') or 0 for e in eps)
        print(f'  day {d}: leader {L:.1f} / ours {O_:.1f} / bought {B_:.1f} / failed {F_:.1f} / cash {C_:,.0f} (leader {CL:,.0f}) / PASS {P_:.0f}')


if __name__ == '__main__':
    main()
