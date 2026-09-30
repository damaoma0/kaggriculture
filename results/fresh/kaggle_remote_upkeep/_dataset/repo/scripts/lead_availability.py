"""'Units available later' (T vs the leader, same G1 worlds) from the stored ledger replays (no games).

usage: lead_availability.py [side=ours]
Supply per product and day (as in results/fresh/t_gap_20260925/deep_decomp.py): harvested units; wheat + bought - fed;
fertilizer collected + bought - applied. Timing value = our units x sum_d (leader share_d - our share_d) x our price_d
(interpolated): value lost because our supply comes on later days. Then per one-time crop the cohort harvest age
(leader: data/leader_semantics planted / harvested tiles; ours: our PLANT records + the day-start boards: the day the
tile stops showing the crop), per animal product the animal-days by day window, and the holding time (mean sale day -
mean supply day).
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
PRODUCTS = ('WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON', 'EGG', 'MILK', 'WOOL', 'FERTILIZER')
ONE_TIME = {'WHEAT': 4, 'CARROT': 3, 'MELON': 12}          # full-yield age
ANIMAL_OF = {'EGG': 'GOOSE', 'MILK': 'COW', 'WOOL': 'SHEEP'}


def supply(side, p):
    out = []
    for dd in side['days']:
        v = dd.get('harv', {}).get(p, 0)
        k_ = dd.get('opk') or {}
        if p == 'WHEAT':
            v += dd.get('bought', {}).get('BUY_PRODUCT:WHEAT', 0) - sum(x for k, x in k_.items() if k.startswith('FEED:'))
        elif p == 'FERTILIZER':
            v = (sum(x for k, x in k_.items() if k.startswith('COLLECT_FERTILIZER:'))
                 + dd.get('bought', {}).get('BUY_PRODUCT:FERTILIZER', 0)
                 - sum(x for k, x in k_.items() if k.startswith('FERTILIZE:')))
        out.append(v)
    return out


def interp(xs):
    known = [(i, x) for i, x in enumerate(xs) if x is not None]
    if not known:
        return [0.0] * len(xs)
    out = []
    for i in range(len(xs)):
        if xs[i] is not None:
            out.append(xs[i])
            continue
        lo = [k for k in known if k[0] < i]
        hi = [k for k in known if k[0] > i]
        if lo and hi:
            (a, xa), (b, xb) = lo[-1], hi[0]
            out.append(xa + (xb - xa) * (i - a) / (b - a))
        else:
            out.append((lo[-1] if lo else hi[0])[1])
    return out


def ages_ours(side):
    """one-time crop cohorts: (crop, planting day, harvest day) from our PLANT records + day-start boards."""
    res = []
    days = side['days']
    plants = [(d, t, crop) for d, dd in enumerate(days) for t, crop in dd.get('plants', [])]
    for d, t, crop in plants:
        if crop not in ONE_TIME:
            continue
        nxt = min((d2 for d2, t2, c2 in plants if t2 == t and d2 > d), default=None)   # a replant ends the cohort
        end = None
        for d2 in range(d + 1, 30):
            bl = days[d2].get('board_list') or []
            if bl and bl[t] != crop:
                end = d2 - 1
                break
        if nxt is not None and (end is None or nxt < end):
            end = nxt
        if end is not None:
            res.append((crop, d, end))
    return res


def ages_leader(sem):
    res = []
    days = sem['days']
    for d, day in enumerate(days):
        for crop, ts in day['planted'].items():
            if crop not in ONE_TIME:
                continue
            for t in ts:
                for d2 in range(d + 1, 30):
                    if t in set((days[d2].get('harvested') or {}).get('tiles', [])):
                        res.append((crop, d, d2))
                        break
    return res


def main():
    import lead_g1
    side_name = sys.argv[1] if len(sys.argv) > 1 else 'ours'
    rows = {}
    for f in LED.glob('*_1*.json'):
        r = json.load(open(f))
        rows[(r['side'], r['episode'])] = r
    eps = sorted(e for s, e in rows if s == 'leader' and (side_name, e) in rows)
    g = len(eps)
    val = Counter(); md = defaultdict(lambda: [[], []]); hold = defaultdict(lambda: [[], []])
    for e in eps:
        L, O = rows[('leader', e)], rows[(side_name, e)]
        for p in PRODUCTS:
            sL, sO = supply(L, p), supply(O, p)
            qO = [dd.get('sold', {}).get(p, 0) for dd in O['days']]
            rO = [dd.get('rev', {}).get(p, 0) for dd in O['days']]
            QO = sum(qO)
            if sum(sL) <= 0 or sum(sO) <= 0 or QO <= 0:
                continue
            pO = interp([rO[d] / qO[d] if qO[d] else None for d in range(30)])
            wL = [x / sum(sL) for x in sL]
            wO = [x / sum(sO) for x in sO]
            val[p] += QO * sum((wL[d] - wO[d]) * pO[d] for d in range(30)) / g
            for i, (S_, side) in enumerate(((sL, L), (sO, O))):
                pos = [max(0, x) for x in S_]
                if sum(pos):
                    md[p][i].append(sum(d * x for d, x in enumerate(pos)) / sum(pos))
                q = [dd.get('sold', {}).get(p, 0) for dd in side['days']]
                if sum(q) and sum(pos):
                    hold[p][i].append(sum(d * x for d, x in enumerate(q)) / sum(q) - sum(d * x for d, x in enumerate(pos)) / sum(pos))
    print(f'{g} G1 worlds, leader vs {side_name}: value of later supply (our units x (leader share - ours) x our price), per game')
    print('| product | later-supply value | mean supply day leader / ours | holding days (sale - supply) leader / ours |')
    print('|---|---:|---|---|')
    for p in sorted(val, key=lambda k: -val[k]):
        print(f"| {p} | {val[p]:+,.0f} | {st.mean(md[p][0]):.1f} / {st.mean(md[p][1]):.1f} | {st.mean(hold[p][0]):+.1f} / {st.mean(hold[p][1]):+.1f} |")
    print(f'| total | {sum(val.values()):+,.0f} | | |')
    # one-time crop harvest ages
    agL, agO = defaultdict(list), defaultdict(list)
    for e in eps:
        team = next(x.split(':')[0] for x in lead_g1.GAMES if x.endswith(str(e)))
        sem = json.load(gzip.open(lead_g1.SEM / team / f'{e}.json.gz', 'rt', encoding='utf-8'))
        for crop, pd, hd in ages_leader(sem):
            agL[crop].append(hd - pd)
        for crop, pd, hd in ages_ours(rows[(side_name, e)]):
            agO[crop].append(hd - pd)
    pw = ((0, 11), (12, 19), (20, 25), (26, 29))
    for crop in ('WHEAT', 'CARROT'):
        cl = Counter(); co = Counter()
        for e in eps:
            team = next(x.split(':')[0] for x in lead_g1.GAMES if x.endswith(str(e)))
            sem = json.load(gzip.open(lead_g1.SEM / team / f'{e}.json.gz', 'rt', encoding='utf-8'))
            for d, day in enumerate(sem['days']):
                for t in day['planted'].get(crop, []):
                    cl[next(i for i, (a, b) in enumerate(pw) if a <= d <= b)] += 1
            for d, dd in enumerate(rows[(side_name, e)]['days']):
                for t, c in dd.get('plants', []):
                    if c == crop:
                        co[next(i for i, (a, b) in enumerate(pw) if a <= d <= b)] += 1
        print(f'{crop} plantings per game by planting day, leader / ours: ' + ', '.join(
            f'd{a}-{b} {cl[i] / g:.1f}/{co[i] / g:.1f}' for i, (a, b) in enumerate(pw)))
    print('one-time crop cohorts: harvest (or loss) age, leader / ours (full-yield age in brackets):')
    for crop, full in ONE_TIME.items():
        if agL[crop] and agO[crop]:
            cL, cO = Counter(agL[crop]), Counter(agO[crop])
            print(f"  {crop} ({full}): mean {st.mean(agL[crop]):.2f} / {st.mean(agO[crop]):.2f}; share harvested before full yield "
                  f"{sum(v for a, v in cL.items() if a < full) / len(agL[crop]):.0%} / {sum(v for a, v in cO.items() if a < full) / len(agO[crop]):.0%}; "
                  f"cohorts per game {len(agL[crop]) / g:.1f} / {len(agO[crop]) / g:.1f}")
    # animals: animal-days by window
    wins = ((0, 5), (6, 11), (12, 17), (18, 23), (24, 29))
    print('animal-days per game by day window, leader / ours:')
    for p, sp in ANIMAL_OF.items():
        parts = []
        for a, b in wins:
            l_ = sum(sum(rows[('leader', e)]['days'][d]['board'].get(sp, 0) for d in range(a, b + 1)) for e in eps) / g
            o_ = sum(sum(rows[(side_name, e)]['days'][d]['board'].get(sp, 0) for d in range(a, b + 1)) for e in eps) / g
            parts.append(f'd{a}-{b} {l_:.0f}/{o_:.0f}')
        print(f'  {sp}: ' + ', '.join(parts))


if __name__ == '__main__':
    main()
