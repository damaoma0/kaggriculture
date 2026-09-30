"""Per-tile crop servicing schedule of Unknown Mother-Goose (56266758), from her 30 recorded games.

For every plant she puts in the ground we reconstruct the tile's whole life: the PLANT / WATER /
FERTILIZE / HARVEST / DIG visits (step, hour, which unit), the units each HARVEST actually moved
into that unit's inventory (inventory delta, not the tile's advertised yield), and the end-of-day
production events read off the tile's yield_units. From those we derive the age-indexed schedule
(which day of a plant's life is watered, fertilized, harvested) that an executor could replay.

Run from scripts/:  ../.venv/Scripts/python.exe mg_servicing.py
Writes results/fresh/mg_executor/servicing.json
"""
import json
from collections import Counter, defaultdict

from market_corpus import ROOT
from tape_vs_bench import mg_games

OUT = ROOT / 'results/fresh/mg_executor'
CROPS = ('TOMATO', 'STRAWBERRY', 'WHEAT', 'CARROT')
TILE_OPS = ('PLANT', 'WATER', 'FERTILIZE', 'HARVEST', 'DIG')
ONGOING = ('TOMATO', 'STRAWBERRY')


def tile_at(tiles, x, y):
    cell = tiles[y][x]
    return cell if isinstance(cell, dict) else None


def is_same_plant(cell, crop, planted_day):
    return (cell is not None and cell.get('kind') == 'PLANT'
            and cell.get('crop') == crop and cell.get('planted_day') == planted_day)


def scan_game(path, eid, seat):
    replay = json.loads(open(path, encoding='utf-8').read())
    steps = replay['steps']
    n = len(steps)
    farms = [steps[t][seat]['observation']['farms'][seat] for t in range(n)]
    invs = [steps[t][seat]['observation']['private']['inventories'] for t in range(n)]

    episodes = []
    live = {}                      # (x, y) -> episode dict

    def close(key, step, reason):
        ep = live.pop(key, None)
        if ep is not None:
            ep['end_step'] = step
            ep['end_reason'] = reason

    for t in range(n - 1):
        farm, nxt = farms[t], farms[t + 1]
        tiles, tiles_n = farm['tiles'], nxt['tiles']

        # a plant that is no longer on its tile at the start of step t is finished
        for key in list(live):
            x, y = key
            if not is_same_plant(tile_at(tiles, x, y), live[key]['crop'], live[key]['plant_day']):
                cell = tile_at(tiles, x, y)
                close(key, t, 'weed' if (cell and cell.get('kind') != 'PLANT') else
                      ('empty' if cell is None else 'other_plant'))

        act = steps[t + 1][seat].get('action') or {}
        units = []
        if act.get('farmer'):
            units.append((0, act['farmer']))
        for i, op in enumerate(act.get('hands') or []):
            if op:
                units.append((i + 1, op))

        for u, op in units:
            name = op[0]
            if name not in TILE_OPS:
                continue
            if u == 0:
                pos = farm['farmer']
            else:
                hands = farm['hands']
                if u - 1 >= len(hands):
                    continue
                pos = hands[u - 1]
            x, y = pos
            before, after = tile_at(tiles, x, y), tile_at(tiles_n, x, y)

            if name == 'PLANT':
                crop = op[1] if len(op) > 1 else None
                close((x, y), t, 'replant')
                if crop in CROPS and after is not None and after.get('crop') == crop \
                        and after.get('kind') == 'PLANT':
                    ep = {'episode': eid, 'seat': seat, 'tile': [x, y], 'crop': crop,
                          'plant_step': t, 'plant_day': after['planted_day'],
                          'plant_unit': u, 'plant_hour': t % 24,
                          'visits': [], 'productions': [], 'end_step': None, 'end_reason': None}
                    live[(x, y)] = ep
                    episodes.append(ep)
                continue

            ep = live.get((x, y))
            if ep is None:
                continue
            day = t // 24
            gained = taken = 0
            if name == 'HARVEST':
                crop = ep['crop']
                # inventory delta is the truth EXCEPT across midnight, where the engine flushes
                # every unit's inventory into the shed; there we fall back on the tile's own delta.
                gained = (invs[t + 1][u].get(crop, 0) if u < len(invs[t + 1]) else 0) \
                    - (invs[t][u].get(crop, 0) if u < len(invs[t]) else 0)
                yb = (before or {}).get('yield_units', 0) or 0
                ya = (after or {}).get('yield_units', 0) or 0
                taken = max(yb - ya, 0)
                if t % 24 != 23 and gained > 0:
                    taken = gained
            ep['visits'].append({
                'step': t, 'day': day, 'hour': t % 24, 'age': day - ep['plant_day'],
                'unit': u, 'op': name, 'gained': gained, 'taken': taken,
                'yield_before': (before or {}).get('yield_units'),
                'yield_after': (after or {}).get('yield_units'),
                'watered_before': (before or {}).get('watered_today'),
                'watered_after': (after or {}).get('watered_today'),
                'fert_until_before': (before or {}).get('fertilized_until_day'),
                'fert_until_after': (after or {}).get('fertilized_until_day'),
                'unwatered_before': (before or {}).get('consecutive_unwatered'),
            })

        # end-of-day / passive production: yield_units rising with no action on that tile
        for key, ep in list(live.items()):
            x, y = key
            b, a = tile_at(tiles, x, y), tile_at(tiles_n, x, y)
            if b is None or a is None or not is_same_plant(a, ep['crop'], ep['plant_day']):
                continue
            d = a.get('yield_units', 0) - b.get('yield_units', 0)
            acted = any(v['step'] == t for v in ep['visits'])
            if d > 0 and not acted:
                ep['productions'].append({'step': t, 'day': t // 24,
                                          'age': t // 24 - ep['plant_day'], 'delta': d,
                                          'watered': b.get('watered_today'),
                                          'fert_until': b.get('fertilized_until_day')})

    for key in list(live):
        close(key, n - 1, 'game_end')

    # daily water/fert presence of each farm, for the age matrices
    for ep in episodes:
        ep['end_step'] = ep['end_step'] if ep['end_step'] is not None else n - 1
        ep['last_age'] = ep['end_step'] // 24 - ep['plant_day']
        ep['units'] = sum(v['taken'] for v in ep['visits'] if v['op'] == 'HARVEST')
        ep['units_inv'] = sum(v['gained'] for v in ep['visits'] if v['op'] == 'HARVEST')
        ep['produced'] = sum(p['delta'] for p in ep['productions'])
    return episodes


def hist(values):
    return dict(sorted(Counter(values).items()))


def mean(values):
    return round(sum(values) / len(values), 3) if values else None


def crop_summary(eps, detailed=False):
    if not eps:
        return {}
    waters = [sum(1 for v in ep['visits'] if v['op'] == 'WATER') for ep in eps]
    eff_waters = [sum(1 for v in ep['visits'] if v['op'] == 'WATER' and not v['watered_before'])
                  for ep in eps]
    ferts = [sum(1 for v in ep['visits'] if v['op'] == 'FERTILIZE') for ep in eps]
    harv = [sum(1 for v in ep['visits'] if v['op'] == 'HARVEST') for ep in eps]
    units = [ep['units'] for ep in eps]
    out = {
        'plants': len(eps),
        'units_per_plant_mean': mean(units),
        'units_per_plant_hist': hist(units),
        'produced_per_plant_mean': mean([ep['produced'] for ep in eps]),
        'waters_per_plant_mean': mean(waters),
        'effective_waters_per_plant_mean': mean(eff_waters),
        'waters_per_plant_hist': hist(waters),
        'ferts_per_plant_mean': mean(ferts),
        'ferts_per_plant_hist': hist(ferts),
        'harvests_per_plant_mean': mean(harv),
        'harvests_per_plant_hist': hist(harv),
        'fertilize_age_hist': hist([v['age'] for ep in eps for v in ep['visits']
                                    if v['op'] == 'FERTILIZE']),
        'harvest_age_hist': hist([v['age'] for ep in eps for v in ep['visits']
                                  if v['op'] == 'HARVEST']),
        'water_age_hist': hist([v['age'] for ep in eps for v in ep['visits'] if v['op'] == 'WATER']),
        'production_age_hist': hist([p['age'] for ep in eps for p in ep['productions']]),
        'lifespan_age_hist': hist([ep['last_age'] for ep in eps]),
        'end_reason': hist([ep['end_reason'] for ep in eps]),
        'hour_hist': {op: hist([v['hour'] for ep in eps for v in ep['visits'] if v['op'] == op])
                      for op in ('PLANT', 'WATER', 'FERTILIZE', 'HARVEST')},
        'plant_hour_hist': hist([ep['plant_hour'] for ep in eps]),
        'units_inv_per_plant_mean': mean([ep['units_inv'] for ep in eps]),
        'harvest_hour23_count': sum(1 for ep in eps for v in ep['visits']
                                    if v['op'] == 'HARVEST' and v['hour'] == 23),
        'yield_units_before_harvest_hist': hist([v['yield_before'] for ep in eps
                                                 for v in ep['visits'] if v['op'] == 'HARVEST']),
        'units_taken_per_harvest_hist': hist([v['taken'] for ep in eps
                                              for v in ep['visits'] if v['op'] == 'HARVEST']),
    }
    if not detailed:
        return out

    # age matrix: of the plants alive on day plant_day+a, what fraction got each service
    ages = defaultdict(lambda: {'alive': 0, 'watered': 0, 'fertilized': 0, 'fert_active': 0,
                                'harvested': 0, 'harvest_units': 0, 'produced': 0,
                                'produced_watered': 0, 'n_prod': 0})
    for ep in eps:
        by_age = defaultdict(list)
        for v in ep['visits']:
            by_age[v['age']].append(v)
        prod_age = defaultdict(int)
        prod_watered = defaultdict(int)
        for p in ep['productions']:
            prod_age[p['age']] += p['delta']
            if p['watered']:
                prod_watered[p['age']] += 1
        for a in range(0, ep['last_age'] + 1):
            row = ages[a]
            row['alive'] += 1
            vs = by_age.get(a, [])
            if any(v['op'] == 'WATER' for v in vs):
                row['watered'] += 1
            if any(v['op'] == 'FERTILIZE' for v in vs):
                row['fertilized'] += 1
            hv = [v for v in vs if v['op'] == 'HARVEST']
            if hv:
                row['harvested'] += 1
                row['harvest_units'] += sum(v['taken'] for v in hv)
            # fertilizer active on that day, read off the tile at any visit that day
            fu = [v['fert_until_before'] for v in vs if v['fert_until_before'] is not None]
            if fu and max(fu) >= ep['plant_day'] + a:
                row['fert_active'] += 1
            if a in prod_age:
                row['produced'] += prod_age[a]
                row['n_prod'] += 1
                row['produced_watered'] += prod_watered[a]
    out['age_matrix'] = {str(a): {**v,
                                  'p_watered': round(v['watered'] / v['alive'], 3),
                                  'p_fertilized': round(v['fertilized'] / v['alive'], 3),
                                  'p_fert_active': round(v['fert_active'] / v['alive'], 3),
                                  'p_harvested': round(v['harvested'] / v['alive'], 3),
                                  'units_per_alive': round(v['harvest_units'] / v['alive'], 3),
                                  'produced_per_alive': round(v['produced'] / v['alive'], 3)}
                         for a, v in sorted(ages.items())}

    # ordering of WATER and HARVEST when both land on the same day
    order = Counter()
    for ep in eps:
        by_day = defaultdict(list)
        for v in ep['visits']:
            by_day[v['day']].append(v)
        for day, vs in by_day.items():
            w = [v['step'] for v in vs if v['op'] == 'WATER']
            h = [v['step'] for v in vs if v['op'] == 'HARVEST']
            if w and h:
                order['same_step' if min(w) == min(h) else
                      ('water_first' if min(w) < min(h) else 'harvest_first')] += 1
                order['same_unit' if len({v['unit'] for v in vs if v['op'] in ('WATER', 'HARVEST')}) == 1
                      else 'different_units'] += 1
                order['gap_%+d' % (min(h) - min(w))] += 1
    out['water_harvest_same_day'] = dict(order)

    # the op sequence a tile gets on each day of its life, and the step gaps inside a day
    seqs = defaultdict(Counter)
    gaps = Counter()
    same_unit_day = Counter()
    for ep in eps:
        by_day = defaultdict(list)
        for v in ep['visits']:
            by_day[v['age']].append(v)
        for age, vs in by_day.items():
            vs = sorted(vs, key=lambda v: v['step'])
            seqs[age]['+'.join(v['op'] for v in vs)] += 1
            for a, b in zip(vs, vs[1:]):
                gaps[b['step'] - a['step']] += 1
            same_unit_day['one_unit' if len({v['unit'] for v in vs}) == 1
                          else 'several_units'] += 1
    out['day_sequences'] = {str(a): dict(c.most_common(6)) for a, c in sorted(seqs.items())}
    out['visit_step_gap_hist'] = dict(sorted(gaps.items()))
    out['day_serviced_by'] = dict(same_unit_day)

    # productions that were doubled (delta 2) vs single
    out['production_delta_hist'] = hist([p['delta'] for ep in eps for p in ep['productions']])
    out['production_delta_by_fert'] = {}
    for ep in eps:
        for p in ep['productions']:
            active = p['fert_until'] is not None and p['fert_until'] >= p['day']
            key = f"fert={bool(active)},watered={bool(p['watered'])}"
            d = out['production_delta_by_fert'].setdefault(key, Counter())
            d[p['delta']] += 1
    out['production_delta_by_fert'] = {k: dict(sorted(v.items()))
                                       for k, v in out['production_delta_by_fert'].items()}
    return out


def main():
    games = mg_games()
    all_eps = []
    per_game = []
    for path, eid, seat in games:
        eps = scan_game(path, eid, seat)
        all_eps.extend(eps)
        tom = [ep for ep in eps if ep['crop'] == 'TOMATO']
        # who services which tomato tile on which day
        owner = defaultdict(set)          # (day, unit) -> tiles
        tile_units = defaultdict(set)     # tile -> units that ever serviced it
        for ep in tom:
            for v in ep['visits']:
                if v['op'] in ('WATER', 'HARVEST', 'FERTILIZE'):
                    owner[(v['day'], v['unit'])].add(tuple(ep['tile']))
                    tile_units[tuple(ep['tile'])].add((v['day'], v['unit']))
        cluster = Counter(len(s) for s in owner.values())
        tiles = sorted({tuple(ep['tile']) for ep in tom})
        tset = set(tiles)
        nbr = sum(1 for (x, y) in tiles
                  if {(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)} & tset)
        per_game.append({
            'tomato_adjacent_frac': round(nbr / len(tiles), 3) if tiles else None,
            'tomato_bbox': [min(x for x, _ in tiles), min(y for _, y in tiles),
                            max(x for x, _ in tiles), max(y for _, y in tiles)] if tiles else None,
            'episode': eid, 'seat': seat,
            'counts': {c: sum(1 for ep in eps if ep['crop'] == c) for c in CROPS},
            'tomato_tiles': sorted({tuple(ep['tile']) for ep in tom}),
            'tomato_plant_days': hist([ep['plant_day'] for ep in tom]),
            'tomato_units_total': sum(ep['units'] for ep in tom),
            'tiles_per_unit_per_day_hist': dict(sorted(cluster.items())),
            'tiles_per_unit_per_day_mean': mean([len(s) for s in owner.values()]),
        })
        print(f"{eid} seat{seat}: " + " ".join(
            f"{c}={sum(1 for ep in eps if ep['crop'] == c)}" for c in CROPS)
            + f"  tomato units={sum(ep['units'] for ep in tom)}"
            + f"  mean units/plant={mean([ep['units'] for ep in tom])}")

    summary = {c: crop_summary([ep for ep in all_eps if ep['crop'] == c], detailed=True)
               for c in CROPS}

    # tomato tile coordinates across all games, and whether they are contiguous
    tom = [ep for ep in all_eps if ep['crop'] == 'TOMATO']
    summary['TOMATO']['tile_hist'] = {f"{x},{y}": c for (x, y), c in
                                      sorted(Counter(tuple(ep['tile']) for ep in tom).items())}
    summary['TOMATO']['quadrant_share'] = hist(
        [('W' if x < 5 else 'E') + ('N' if y < 5 else 'S') for ep in tom for x, y in [ep['tile']]])
    summary['TOMATO']['plant_day_hist'] = hist([ep['plant_day'] for ep in tom])
    summary['TOMATO']['plant_unit_hist'] = hist([ep['plant_unit'] for ep in tom])
    # units per plant split by planting day, to separate first from later waves
    by_wave = defaultdict(list)
    for ep in tom:
        by_wave[ep['plant_day']].append(ep['units'])
    summary['TOMATO']['units_by_plant_day'] = {
        str(d): {'n': len(v), 'mean_units': mean(v), 'hist': hist(v)}
        for d, v in sorted(by_wave.items())}

    # per-plant compact records (tomato only)
    records = [{'episode': ep['episode'], 'tile': ep['tile'], 'plant_day': ep['plant_day'],
                'plant_step': ep['plant_step'], 'end_step': ep['end_step'],
                'end_reason': ep['end_reason'], 'units': ep['units'],
                'water_ages': sorted(v['age'] for v in ep['visits'] if v['op'] == 'WATER'),
                'fert_ages': sorted(v['age'] for v in ep['visits'] if v['op'] == 'FERTILIZE'),
                'harvests': [[v['age'], v['hour'], v['taken'], v['yield_before']]
                             for v in ep['visits'] if v['op'] == 'HARVEST'],
                'productions': [[p['age'], p['delta']] for p in ep['productions']]}
               for ep in tom]

    # the modal tomato schedule: exact (water ages, fert ages, harvest ages) signatures
    sig = Counter()
    for r in records:
        sig[(tuple(r['water_ages']), tuple(r['fert_ages']),
             tuple(h[0] for h in r['harvests']))] += 1
    summary['TOMATO']['top_signatures'] = [
        {'water_ages': list(w), 'fert_ages': list(f), 'harvest_ages': list(h), 'n': c}
        for (w, f, h), c in sig.most_common(12)]

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'servicing.json').write_text(json.dumps(
        {'games': len(games), 'per_game': per_game, 'summary': summary,
         'tomato_plants': records}, indent=1, default=str), encoding='utf-8')
    print('\nwrote', OUT / 'servicing.json')
    for c in CROPS:
        s = summary[c]
        if s:
            print(f"{c}: n={s['plants']} units/plant={s['units_per_plant_mean']} "
                  f"waters={s['waters_per_plant_mean']} ferts={s['ferts_per_plant_mean']} "
                  f"harvests={s['harvests_per_plant_mean']}")


if __name__ == '__main__':
    main()
