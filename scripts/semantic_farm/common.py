from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
from cumulative_engine_profiles import ENGINE as E

PASS = {'farmer':['PASS'], 'hands':[], 'market':[]}
SPECIES = tuple(E.CROPS) + tuple(E.ANIMALS)


def tiles(obs):
    for y, row in enumerate(obs['farms'][obs['player']]['tiles']):
        for x, tile in enumerate(row):
            yield (x, y), tile


def species(tile):
    return (tile.get('crop') or tile.get('animal')) if isinstance(tile, dict) else None


def asset_counts(obs):
    return Counter(species(t) for _,t in tiles(obs) if species(t))


def public_features(obs):
    counts = asset_counts(obs)
    ages = Counter()
    for _,tile in tiles(obs):
        if species(tile):
            age = obs['day'] - tile.get('planted_day', tile.get('placed_day', obs['day']))
            ages[f'{species(tile)}:{min(9,age//3)}'] += 1
    rival = obs['farms'][1-obs['player']]
    return dict(day=obs['day'], shops=dict(Counter(obs['town']['unlocked_shops'])),
        assets=dict(counts), ages=dict(ages), money=obs['farms'][obs['player']]['money'],
        land=len(obs['farms'][obs['player']]['unlocked_quadrants']),
        prices=deepcopy(obs['market']['prices']),
        rival=dict(Counter(species(t) for row in rival['tiles'] for t in row if species(t))))


def physical_key(obs):
    farm = deepcopy(obs['farms'][obs['player']])
    farm.pop('money', None)
    return sha256(json.dumps([farm,obs['private']],sort_keys=True).encode()).hexdigest()


def hired_cost(already, extra):
    return sum(E._hire_cost(i) for i in range(already, already+extra))


def output_product(s):
    return E.ANIMALS[s]['product'] if s in E.ANIMALS else s
