"""Surplus strawberry/tomato watering: why leaders water beyond the module's bonus/survival jobs (thread upkeep,
step 2 addendum: scripts/upkeep_value.py's docstring asks this explicitly). Stored data only
(results/fresh/upkeep_20260925/skips/*.json.gz, from scripts/upkeep_skips.py); no new engine replay.

Table H (skips_report.txt) already splits every leader WATER op on these two crops into survival (dry yesterday) /
fertilized production day / two preventive classes (today earns nothing). This script asks, for each class, what the
op actually COST in labour:
  same-tile bundle: the SAME unit also did another effective op on that SAME tile that day (FERTILIZE for the bonus,
    or HARVEST): the water is free, no extra travel.
  other tile that day: that unit visited >=1 OTHER tile that day too: the water stop is at most one detour on a trip
    that was happening anyway ("while passing"), not a dedicated round trip.
  dedicated trip: WATER was that unit's only effective tile op all day.
and, for the two preventive classes, the number of days from d to that tile's NEXT scheduled production (its fixed
interval), to test the "future production day" hypothesis: is preventive watering concentrated right before a
production day, or spread out with no near payoff?

usage: water_extra.py > results/fresh/upkeep_20260925/water_extra.txt
"""
import gzip
import json
import statistics as stt
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SK = ROOT / 'results/fresh/upkeep_20260925/skips'
# crop: (first_yield_day, max_yield_day, max_yield, ongoing, interval) -- same layout as upkeep_skip_report.py
CROPS = {'TOMATO': (8, 8, 4, True, 1), 'STRAWBERRY': (10, 10, 4, True, 2)}


def classify(kind, st, d):
    cdi = CROPS[kind]
    if st[1] >= 1:
        return 'survival (dry yesterday)'
    dsf = d + 1 - st[0] - cdi[0]
    prod_day = dsf >= 0 and dsf % cdi[4] == 0 and dsf // cdi[4] + 1 <= cdi[2]
    if prod_day:
        return 'fertilized production day' if st[3] >= d else 'production day, unfertilized (preventive)'
    return 'ongoing, no production (preventive)'


def days_to_next_prod(kind, st, d):
    cdi = CROPS[kind]
    for dd in range(d, d + cdi[4] * cdi[2] + 2):
        dsf = dd + 1 - st[0] - cdi[0]
        if dsf >= 0 and dsf % cdi[4] == 0 and dsf // cdi[4] + 1 <= cdi[2]:
            return dd - d
        if dsf < 0:
            continue
        if dsf // cdi[4] + 1 > cdi[2]:
            return None      # already past the last production: none left
    return None


def main():
    files = sorted(SK.glob('*.json.gz'))
    n_games = 0
    cls_n = defaultdict(Counter)
    bundle = defaultdict(lambda: defaultdict(Counter))
    horizon = defaultdict(lambda: defaultdict(list))
    for f in files:
        try:
            r = json.load(gzip.open(f, 'rt', encoding='utf-8'))
        except Exception:
            continue
        if not r.get('cash_match'):
            continue
        n_games += 1
        by_day_unit_tiles = defaultdict(lambda: defaultdict(set))
        for a in r['assets']:
            d = a['d']
            for (cmd, h, u) in a['ops']:
                by_day_unit_tiles[d][u].add(a['i'])
        for a in r['assets']:
            kind = a['k']
            if kind not in CROPS:
                continue
            d = a['d']
            st = tuple(a['st'])
            ops = a['ops']
            water_units = [u for (cmd, h, u) in ops if cmd == 'WATER']
            if not water_units:
                continue
            c_ = classify(kind, st, d)
            cls_n[kind][c_] += 1
            other_cmd_units = {u for (cmd, h, u) in ops if cmd != 'WATER'}
            for u in water_units:
                if u in other_cmd_units:
                    bundle[kind][c_]['same_tile'] += 1
                elif len(by_day_unit_tiles[d][u]) > 1:
                    bundle[kind][c_]['other_tile'] += 1
                else:
                    bundle[kind][c_]['dedicated'] += 1
            if 'preventive' in c_:
                dn = days_to_next_prod(kind, st, d)
                horizon[kind][c_].append(dn if dn is not None else -1)   # -1 = no production left at all
    print(f'Surplus strawberry/tomato watering ({n_games} leader games, days 0-29, every leader WATER op on these crops; '
          f'classes from skips_report.txt table H)')
    print()
    print('| crop | class | n / game | same-tile bundle (free) | other tile that day (low cost) | dedicated trip | '
          'median days to next production | share with none left |')
    print('|---|---|---|---|---|---|---|---|')
    for kind in CROPS:
        for c_, n in cls_n[kind].most_common():
            b = bundle[kind][c_]
            tb = sum(b.values()) or 1
            hz = horizon[kind].get(c_)
            if hz:
                left = [x for x in hz if x >= 0]
                none_left = sum(1 for x in hz if x < 0) / len(hz)
                med = f'{stt.median(left):.0f} (n={len(left)})' if left else '-'
            else:
                med, none_left = '-', None
            print(f"| {kind} | {c_} | {n / n_games:.1f} | {b['same_tile'] / tb:.0%} | {b['other_tile'] / tb:.0%} | "
                  f"{b['dedicated'] / tb:.0%} | {med} | {f'{none_left:.0%}' if none_left is not None else '-'} |")
    print()
    print('same-tile bundle = the SAME unit also did another effective op on that tile that day (zero extra travel).')
    print('other tile that day = that unit visited >=1 other tile that day too (the water was one detour on a trip that')
    print('  was happening anyway -- "while passing" -- not a dedicated round trip).')
    print('dedicated trip = WATER was that unit\'s only effective tile op all day (the full labour cost is charged to it).')
    print('median days to next production = for the two classes that earn nothing today, how far off the next payoff is;')
    print('  "share with none left" = the plant has already used all its productions (upkeep with no further payoff at all).')


if __name__ == '__main__':
    main()
