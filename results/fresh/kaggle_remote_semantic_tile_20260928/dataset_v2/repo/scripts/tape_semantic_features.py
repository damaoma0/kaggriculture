"""Cheap dated-plan features, explicitly distinct from successful production.

Only the observation, own memory, and archived candidate plans enter features.
Episode/route/seed/opponent IDs and target future shops are never features.
Ideal new-cohort output assumes complete service; exact rollouts must still
verify the candidate's labor, inventory, survival and actual economics.
"""
from collections import Counter, defaultdict
from functools import lru_cache
from hashlib import sha256
import gzip
import json
from pathlib import Path

from cumulative_engine_profiles import ENGINE, engine_profile
import value_tape_search as V

ROOT = V.ROOT
PROFILE_PATH = ROOT / 'results/fresh/value_tape_ranker_20260923/plan_profiles.json.gz'
PRODUCTS = tuple(ENGINE.PRODUCTS)
SPECIES = tuple(ENGINE.CROPS) + tuple(ENGINE.ANIMALS)
MOVES = {'NORTH', 'SOUTH', 'EAST', 'WEST'}
VERSION = 1


def build_profiles(path=PROFILE_PATH):
    ns = V.fresh_agent().__globals__
    metadata = json.loads((ROOT / 'results/fresh/semantic_tapes/compact_profiles.json').read_text(encoding='utf-8'))
    by_episode = {r['episode']: r for r in metadata}
    profiles = []
    for route, tape in enumerate(ns['_MGT_TAPES']):
        actions = ns['_MGT_ROUTES'][route]
        days = []
        for day in range(30):
            start, end = day*24, min(718, (day+1)*24-1)
            # Requested travel ignores blocking, stock and failed hires.
            sim = ns['_tc_simulate'](lambda t: actions[t], start, end, [(4, 4)])
            counts, jobs = Counter(), []
            for t, units in sim.items():
                for x, y, command in units:
                    op = command[0]
                    counts[f'unit:{op}'] += 1
                    if op in MOVES or op == 'PASS':
                        continue
                    arg = command[1] if len(command) > 1 else ''
                    jobs.append([x, y, op, arg])
                    if op in ('PLANT', 'PLACE', 'PICKUP') and arg in (*SPECIES, *PRODUCTS):
                        amount = int(command[2]) if len(command) > 2 and isinstance(command[2], int) else 1
                        counts[f'{op}:{arg}'] += amount
                for order in actions[t].get('market') or []:
                    if not order:
                        continue
                    op = order[0]
                    if op in ('BUY_ANIMAL', 'BUY_SEED', 'BUY_PRODUCT', 'SELL'):
                        counts[f'{op}:{order[1]}'] += int(order[2])
                    elif op == 'HIRE':
                        counts['HIRE'] += 1
            raw_board = tape['boards'][day]
            labels = [raw_board[i:i+2] for i in range(0, len(raw_board), 2)]
            assert len(labels) == 100
            days.append(dict(requests=dict(counts), jobs=jobs, labels=labels))
        profiles.append(dict(route=route, episode=tape['ep'],
            family=by_episode[tape['ep']]['submission'], days=days))
    result = dict(version=VERSION, native_sha256=V.SOURCE_SHA256,
        extractor_sha256=sha256(Path(__file__).read_bytes()).hexdigest(), profiles=profiles,
        evidence='Requests and ideal travel, not successful jobs. Future target shops and outcomes excluded.')
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, 'wt', encoding='utf-8') as f:
        json.dump(result, f, separators=(',', ':'))
    return result


@lru_cache(maxsize=1)
def library():
    with gzip.open(PROFILE_PATH, 'rt', encoding='utf-8') as f:
        data = json.load(f)
    assert data['version'] == VERSION and data['native_sha256'] == V.SOURCE_SHA256
    return {p['episode']: p for p in data['profiles']}


def tile_label(tile):
    if not isinstance(tile, dict):
        return ' L' if tile == 'LOCKED' else ' .'
    if tile.get('crop'):
        return tile['crop'][:2]
    if tile.get('animal'):
        return tile['animal'][:2].lower()
    return 'pa' if tile.get('kind') == 'PASTURE' else ' .'


@lru_cache(maxsize=256)
def new_cohort(species, day, origin):
    if species in ENGINE.CROPS:
        output, work, inputs, _ = engine_profile(None, day, 30, new_crop=species, fertilize=True)
    else:
        output, work, inputs, _ = engine_profile(ENGINE._new_animal(species, day), day, 30)
    counts = Counter()
    for product, dates in output.items():
        for when, amount in dates.items():
            counts[f'potential:end:{product}'] += amount
            if when < origin+6:
                counts[f'potential:6:{product}'] += amount
    for dates in inputs.values():
        for product, amount in dates.items():
            counts[f'input:end:{product}'] += amount
    counts['work:end'] = sum(sum(c.values()) for c in work.values())
    return dict(counts)


def dated_plan(profile, day, farm):
    features, counts = Counter(), Counter()
    visits = []
    for offset in range(3):
        if day+offset >= 30:
            break
        item = profile['days'][day+offset]
        requests = item['requests']
        jobs = item['jobs']
        visits.append({(x, y, op) for x, y, op, _ in jobs})
        for key, amount in requests.items():
            # No raw route identifiers or archived outcomes in the feature map.
            features[f'request:{offset}:{key}'] += amount
            counts[key] += amount
        for species in SPECIES:
            op = 'PLANT' if species in ENGINE.CROPS else 'PLACE'
            n = requests.get(f'{op}:{species}', 0)
            if n:
                for key, amount in new_cohort(species, day+offset, day).items():
                    features[key] += n*amount
        features['travel_radius'] += sum(abs(x-4)+abs(y-4) for x, y, op, _ in jobs
            if op in ('PLANT', 'PLACE', 'FEED', 'CARE', 'WATER', 'FERTILIZE', 'HARVEST'))
    for key, amount in counts.items():
        features[f'request:total:{key}'] += amount
    labels = profile['days'][day]['labels']
    for y, row in enumerate(farm['tiles']):
        for x, tile in enumerate(row):
            current = tile_label(tile)
            target = labels[y*10+x]
            if current != target:
                features['board:difference'] += 1
            if not isinstance(tile, dict):
                continue
            species = tile.get('animal') or tile.get('crop')
            if species not in SPECIES:
                continue
            if current != target:
                features[f'board:missing:{species}'] += 1
                features['board:perennial_missing'] += species not in ('WHEAT', 'CARROT')
            ops = ('FEED', 'CARE', 'HARVEST') if tile.get('animal') else ('WATER', 'FERTILIZE', 'HARVEST')
            for op in ops:
                covered = sum((x, y, op) in v for v in visits)
                features[f'coverage:{species}:{op}'] += covered
                features[f'uncovered:{species}:{op}'] += 3-covered
            if any((x, y, 'DIG') in v for v in visits):
                features[f'dig_existing:{species}'] += 1
    return features


def context(obs):
    day, player = int(obs['day']), int(obs['player'])
    c = Counter(day=day, days_left=30-day)
    for index, farm in enumerate(obs['farms']):
        role = 'own' if index == player else 'rival'
        c[f'{role}:cash'] = farm.get('money', 0)
        for row in farm['tiles']:
            for tile in row:
                if not isinstance(tile, dict):
                    continue
                species = tile.get('animal') or tile.get('crop')
                if species not in SPECIES:
                    continue
                age = day-tile.get('placed_day', tile.get('planted_day', day))
                c[f'{role}:count:{species}'] += 1
                c[f'{role}:age:{species}:{min(3, max(0, age)//4)}'] += 1
                for field in ('yield_units', 'pending_care_bonus', 'consecutive_unwatered', 'consecutive_unfed'):
                    c[f'{role}:{field}:{species}'] += tile.get(field, 0)
    shops = list(obs['town']['unlocked_shops'])
    for shop in shops:
        c[f'shop:{shop}'] += 1
    for product in PRODUCTS:
        c[f'price:{product}'] = obs['market']['prices'].get(product, 0)
        c[f'market:{product}'] = obs['market']['inventory'].get(product, 10000)-10000
        c[f'stock:{product}'] = obs['private']['shed'].get(product, 0)
        c[f'demand:{product}'] = sum(ENGINE.SHOPS[s].count(product) for s in shops)
        mean_addition = sum(items.count(product) for items in ENGINE.SHOPS.values()) / len(ENGINE.SHOPS)
        # Uniform expected demand after all unrevealed slots. No hidden draw.
        c[f'expected_demand:{product}'] = c[f'demand:{product}'] + (8-len(shops))*mean_addition
    return c


def features(obs, memory, candidates, profiles=None):
    """Return one feature map per alternative, in its original order.

    Candidate metadata is an explicit allowlist. A caller may pass full saved
    forecast rows; predictions, selected status, and labels are ignored.
    """
    profiles = library() if profiles is None else profiles
    assert candidates[0]['route'] is None
    day, player = int(obs['day']), int(obs['player'])
    farm = obs['farms'][player]
    native = dated_plan(profiles[candidates[0]['episode']], day, farm)
    ctx = context(obs)
    output = []
    for c in candidates[1:]:
        assert c['route'] is not None
        plan = dated_plan(profiles[c['episode']], day, farm)
        row = dict(ctx)
        row.update(hamming=float(c['hamming']), shop_distance=float(c['distance']),
            incumbent=float(c['route'] == memory['players'][player]['route']))
        delta = {key: plan[key]-native[key] for key in plan.keys() | native.keys()}
        row.update({f'delta:{key}': value for key, value in delta.items()})
        # Absolute maintenance incompatibility still matters if native is imperfect.
        row.update({f'plan:{key}': value for key, value in plan.items()
            if key.startswith(('board:', 'uncovered:', 'dig_existing:'))})
        for product in PRODUCTS:
            for prefix in ('potential:end:', 'potential:6:', 'request:total:SELL:'):
                amount = delta.get(prefix+product, 0)
                for factor in ('price:', 'demand:', 'expected_demand:', 'market:'):
                    row[f'interaction:{prefix}{product}:{factor}'] = amount*ctx[factor+product]
        row['heuristic_value'] = sum(delta.get('potential:end:'+p, 0)*ctx['price:'+p] for p in PRODUCTS)
        row['heuristic_value'] -= sum(delta.get('input:end:'+p, 0)*ctx['price:'+p] for p in PRODUCTS)
        # A rough work cost helps comparison but is never an admission rule.
        row['heuristic_value'] -= 2*delta.get('work:end', 0)
        output.append({key: float(value) for key, value in row.items()})
    return output


if __name__ == '__main__':
    result = build_profiles()
    print(json.dumps(dict(profiles=len(result['profiles']), path=str(PROFILE_PATH),
        native_sha256=result['native_sha256'])))
