"""The 3000+ leaders' programme for the FOURTH quadrant (SE, $4,000), from data/leader_semantics (540 clean games).

usage: q4_leader_programme.py [--json out.json]

Per game: SE purchase day (= the day before the first day-start board with no locked SE tile; checked against the first
PLANT on an SE tile), SE tile-days by use per day window, SE plantings by crop and first SE planting day, SE tile ops
(PLANT / HARVEST / WATER / FEED / CARE / FERTILIZE that took effect on SE tiles) vs all tile ops, hands_present per
day (correctly dated in the corpus), and SE output: each day's harvested units of a product are split over that day's
harvested tiles of the matching crop / species (day-start label) in equal shares, so SE units = units x (SE tiles /
all tiles harvested of that product that day). That equal-share split is an ASSUMPTION (a fertilised or better-cared
tile yields more); it is exact whenever all of a product's harvests that day were in one quadrant. SE value = SE units x
the game's average sale price of the product. Costs attributable to SE: land 4,000, seeds of SE plantings, animals
placed on SE tiles (structures are free to build in this engine: BUILD_* has no market cost).
Known corpus issues (README): market / animals.bought / hires_arrived are one day late (not used here except
game-level price averages); 'co' = cow or empty coop (SE 'co' tiles are counted as 'co' and reported as such).
"""
import gzip
import glob
import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMES = {'16915014': 'Boey', '16623559': 'DECEM', '16681125': 'MMPQ', '16730612': 'MG', '16770421': 'Vadim',
         '16732748': 'DSM'}
SEED = {'WHEAT': 10, 'CARROT': 20, 'TOMATO': 50, 'STRAWBERRY': 100, 'MELON': 80}
ANIMAL_COST = {'GOOSE': 300, 'COW': 400, 'SHEEP': 500}
CODE = {'WH': 'WHEAT', 'CA': 'CARROT', 'TO': 'TOMATO', 'ST': 'STRAWBERRY', 'ME': 'MELON',
        'sh': 'WOOL', 'co': 'MILK', 'go': 'EGG'}
SPECIES_OF = {'sh': 'SHEEP', 'co': 'COW', 'go': 'GOOSE'}
WINS = ((10, 11), (12, 17), (18, 23), (24, 29))
SE = {y * 10 + x for y in range(5, 10) for x in range(5, 10)}


def quad(i):
    return ('N' if i // 10 < 5 else 'S') + ('W' if i % 10 < 5 else 'E')


def labels(b):
    if isinstance(b, list) and b and len(b[0]) == 2:
        return b
    s = ''.join(b)
    return [s[i:i + 2] for i in range(0, len(s), 2)]


def game_stats(g):
    days = g['days']
    L = [labels(d['board']) for d in days]
    unlock = next((d for d in range(30) if all(L[d][i] != ' L' for i in SE)), None)
    first_plant = next((d for d in range(30) if any(i in SE for v in days[d]['planted'].values() for i in v)), None)
    buy = None if unlock is None else unlock - 1
    out = dict(buy=buy, unlock=unlock, first_plant=first_plant)
    # average sale price per product (game level)
    su, sr = Counter(), Counter()
    for d in days:
        su.update(d['market']['sold_units'])
        sr.update(d['market']['sold_revenue'])
    price = {p: sr[p] / su[p] for p in su if su[p]}
    out['revenue'] = sum(sr.values())
    out['hands'] = [d['labour']['hands_present'] for d in days]
    # SE tile use per window, plantings, ops, output
    use = {w: Counter() for w in WINS}
    plant = Counter()
    plant_win = {w: Counter() for w in WINS}
    ops_se, ops_all = Counter(), Counter()
    units_se, units_all = Counter(), Counter()
    unmapped = 0
    placed_se = Counter()
    for d, day in enumerate(days):
        for w in WINS:
            if w[0] <= d <= w[1]:
                use[w].update(L[d][i] for i in SE)
        for crop, tl in day['planted'].items():
            for i in tl:
                ops_all['PLANT'] += 1
                if i in SE:
                    ops_se['PLANT'] += 1
                    plant[crop] += 1
                    for w in WINS:
                        if w[0] <= d <= w[1]:
                            plant_win[w][crop] += 1
        for op, tl in (day.get('maintenance') or {}).items():
            ops_all[op] += len(tl)
            ops_se[op] += sum(1 for i in tl if i in SE)
        for i in (day.get('animals') or {}).get('placed', []):
            if i in SE:
                lab = L[min(d + 1, 29)][i]
                placed_se[SPECIES_OF.get(lab, '?')] += 1
        h = day.get('harvested') or {}
        tl = h.get('tiles', [])
        ops_all['HARVEST'] += len(tl)
        ops_se['HARVEST'] += sum(1 for i in tl if i in SE)
        by_prod = defaultdict(list)
        for i in tl:
            p = CODE.get(L[d][i])
            if p is None:
                unmapped += 1
                continue
            by_prod[p].append(i)
        for p, u in (h.get('units') or {}).items():
            ts = by_prod.get(p, [])
            units_all[p] += u
            if ts:
                units_se[p] += u * sum(1 for i in ts if i in SE) / len(ts)
    out.update(use={f'{a}-{b}': dict(c) for (a, b), c in use.items()}, plant=dict(plant),
               plant_win={f'{a}-{b}': dict(c) for (a, b), c in plant_win.items()}, ops_se=dict(ops_se),
               ops_all=dict(ops_all), units_se=dict(units_se), units_all=dict(units_all), unmapped=unmapped,
               price=price, placed_se=dict(placed_se))
    out['value_se'] = sum(units_se[p] * price.get(p, 0) for p in units_se)
    out['seed_se'] = sum(SEED[c] * n for c, n in plant.items())
    out['animal_se'] = sum(ANIMAL_COST.get(s, 0) * n for s, n in placed_se.items())
    # whole-farm crop tile-days days 12-29 and animals at day 20 (for with / without SE contrasts)
    td = Counter()
    for d in range(12, 30):
        td.update(x for x in L[d] if x in CODE or x in ('we',))
    out['tiledays_12_29'] = dict(td)
    out['animals_d20'] = dict(Counter(x for x in L[20] if x in ('sh', 'co', 'go')))
    s = g['meta']['seat']
    r = g['meta']['rewards']
    out.update(final=r[s], margin=r[s] - r[1 - s], team=NAMES.get(str(g['meta'].get('team_id', '')), ''))
    return out


def ms(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return '-'
    return f'{st.mean(xs):.1f}'


def main():
    rows = defaultdict(list)
    for f in sorted(glob.glob(str(ROOT / 'data/leader_semantics/*/*.json.gz'))):
        team = Path(f).parent.name
        g = json.load(gzip.open(f, 'rt', encoding='utf-8'))
        s = game_stats(g)
        s['team'] = NAMES[team]
        s['episode'] = g['meta']['episode']
        rows[NAMES[team]].append(s)
    allrows = [r for v in rows.values() for r in v]
    print(f'{len(allrows)} games')
    print('\n== SE purchase and first SE planting (days)')
    for t in ('DSM', 'DECEM', 'Vadim', 'MG', 'MMPQ', 'Boey'):
        rs = rows[t]
        se = [r for r in rs if r['buy'] is not None]
        print(f'{t:6s} SE in {len(se):3d}/{len(rs)}; buy day {dict(sorted(Counter(r["buy"] for r in se).items()))}; '
              f'first SE planting minus buy day {dict(sorted(Counter((r["first_plant"] - r["buy"]) if r["first_plant"] is not None else None for r in se).items(), key=lambda kv: (kv[0] is None, kv[0])))}')
    se_teams = ('DSM', 'DECEM', 'Vadim', 'MG')
    print('\n== SE tile-days per game by use, per window (SE-buying games; 25 tiles x days in window)')
    for t in se_teams:
        se = [r for r in rows[t] if r['buy'] is not None]
        n = len(se)
        print(f'{t} (n={n})')
        for w in WINS:
            k = f'{w[0]}-{w[1]}'
            c = Counter()
            for r in se:
                c.update(r['use'][k])
            tot = sum(c.values()) / n
            print(f'   days {k}: ' + ', '.join(f'{lab.strip() or "?"} {v / n:.1f}' for lab, v in c.most_common(9)) + f'  (total {tot:.0f})')
    print('\n== SE plantings per game by crop and window')
    for t in se_teams:
        se = [r for r in rows[t] if r['buy'] is not None]
        n = len(se)
        line = []
        for w in WINS:
            k = f'{w[0]}-{w[1]}'
            c = Counter()
            for r in se:
                c.update(r['plant_win'][k])
            line.append(f'{k}: ' + ', '.join(f'{cr[:2]} {v / n:.1f}' for cr, v in c.most_common()))
        tot = Counter()
        for r in se:
            tot.update(r['plant'])
        print(f'{t:6s} ' + ' | '.join(line) + ' || total ' + ', '.join(f'{cr[:2]} {v / n:.1f}' for cr, v in tot.most_common()))
    print('\n== SE tile ops per game (took effect) and share of all tile ops')
    for t in se_teams:
        se = [r for r in rows[t] if r['buy'] is not None]
        n = len(se)
        a, b = Counter(), Counter()
        for r in se:
            a.update(r['ops_se'])
            b.update(r['ops_all'])
        print(f'{t:6s} SE ops {sum(a.values()) / n:.0f} of {sum(b.values()) / n:.0f} ({sum(a.values()) / sum(b.values()):.1%}): '
              + ', '.join(f'{k} {a[k] / n:.0f}/{b[k] / n:.0f}' for k in ('PLANT', 'HARVEST', 'WATER', 'FEED', 'CARE', 'FERTILIZE')))
    print('\n== SE output (equal-share split of each day\'s harvested units over that product\'s harvested tiles), per game')
    for t in se_teams:
        se = [r for r in rows[t] if r['buy'] is not None]
        n = len(se)
        u, ua = Counter(), Counter()
        val, seed, anim, rev, unm = [], [], [], [], []
        pl = Counter()
        for r in se:
            u.update(r['units_se'])
            ua.update(r['units_all'])
            val.append(r['value_se'])
            seed.append(r['seed_se'])
            anim.append(r['animal_se'])
            rev.append(r['revenue'])
            unm.append(r['unmapped'])
            pl.update(r['placed_se'])
        print(f'{t:6s} SE units ' + ', '.join(f'{p.lower()} {u[p] / n:.0f}/{ua[p] / n:.0f}' for p in sorted(u, key=lambda p: -u[p]) if u[p] / n >= 0.5)
              + f'\n       SE value {st.mean(val):,.0f} (median {st.median(val):,.0f}) of revenue {st.mean(rev):,.0f} '
              f'({st.mean(val) / st.mean(rev):.1%}); SE seeds {st.mean(seed):,.0f}, SE animals placed {dict((k, round(v / n, 2)) for k, v in pl.items())} '
              f'cost {st.mean(anim):,.0f}; land 4,000 -> SE value - (land + seeds + animals) = {st.mean(val) - 4000 - st.mean(seed) - st.mean(anim):,.0f}'
              f' (before wages); unmapped harvested tiles {st.mean(unm):.1f}/game')
    print('\n== hands_present by day (mean), SE games vs no-SE games')
    for t in ('DSM', 'DECEM', 'Vadim', 'MG', 'MMPQ', 'Boey'):
        for lab_, sel in (('SE', lambda r: r['buy'] is not None), ('noSE', lambda r: r['buy'] is None)):
            rs = [r for r in rows[t] if sel(r)]
            if not rs:
                continue
            hs = [st.mean(r['hands'][d] for r in rs) for d in range(30)]
            print(f'{t:6s} {lab_:4s} n={len(rs):3d} days 6-16: ' + ' '.join(f'{h:4.1f}' for h in hs[6:17])
                  + f' | mean d12-28 {st.mean(hs[12:29]):.1f}, hand-days d0-28 {sum(hs[:29]):.0f}')
    print('\n== MG with vs without SE (within-team, confounded by world)')
    for lab_, sel in (('SE', lambda r: r['buy'] is not None), ('noSE', lambda r: r['buy'] is None)):
        rs = [r for r in rows['MG'] if sel(r)]
        td = Counter()
        an = Counter()
        for r in rs:
            td.update(r['tiledays_12_29'])
            an.update(r['animals_d20'])
        n = len(rs)
        print(f'  {lab_:4s} n={n}: crop tile-days d12-29 ' + ', '.join(f'{k} {v / n:.0f}' for k, v in td.most_common())
              + f' | animals d20 ' + ', '.join(f'{k} {v / n:.1f}' for k, v in an.most_common())
              + f' | revenue {st.mean(r["revenue"] for r in rs):,.0f}, final {st.mean(r["final"] for r in rs):,.0f}, margin {st.mean(r["margin"] for r in rs):+,.0f}')
    if '--json' in sys.argv:
        out = sys.argv[sys.argv.index('--json') + 1]
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps({t: v for t, v in rows.items()}), encoding='utf-8')
        print('wrote', out)


if __name__ == '__main__':
    main()
