from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import random
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'agents' / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture(seed):
    rng = random.Random(seed)
    tiles = [[None for _ in range(10)] for _ in range(10)]
    day = 8 + seed % 17
    stops = []
    for i in range(32):
        idx = (i * 7 + 3) % 100
        if i % 2:
            species = ('COW', 'SHEEP', 'GOOSE')[i % 3]
            tile = dict(kind='COOP' if species == 'GOOSE' else 'PASTURE', animal=species,
                        placed_day=2 + i % 5, fed_today=bool(i % 5 == 0),
                        pending_care_bonus=i % 6, consecutive_unfed=i % 2,
                        yield_units=i % 7)
            ops = [('FEED', i % 4 == 1), ('CARE', False), ('HARVEST', True)]
            if i % 3 == 0:
                ops.insert(0, ('COLLECT_FERTILIZER', False))
        else:
            crop = ('WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY')[i // 2 % 4]
            tile = dict(kind='PLOT', crop=crop, planted_day=day - (i % 11 + 2),
                        yield_units=i % 5, watered_today=False,
                        fertilized_until_day=day - 1, consecutive_unwatered=i % 2)
            ops = [('WATER', i % 4 == 0), ('HARVEST', True)]
            if i % 3 == 0:
                ops.insert(0, ('FERTILIZE', i % 6 == 0))
        tiles[idx // 10][idx % 10] = tile
        stops.append(dict(tile=idx, rel=i % 4, ops=[dict(c=[c], m=m, v=10., rank=j)
                                                  for j, (c, m) in enumerate(ops)]))
    rng.shuffle(stops)
    segs = [dict(p0=44 + i % 2, t0=i % 3, fpick=i % 2, hold0=(i == 0),
                 stops=stops[i::8], ver=0) for i in range(8)]
    # Shared identities between the candidate pool and a current stop matter to
    # the final bookkeeping, even when an operation has the same command text.
    rest = [dict(tile=x['tile'], rel=x['rel'], v=10.,
                 ops=[dict(c=['COLLECT_FERTILIZER' if i % 2 else 'FERTILIZE'],
                           m=False, v=10., rank=4)]) for i, x in enumerate(stops[:12])]
    shared = dict(c=['CARE'], m=False, v=50., rank=3)
    rest.append(dict(tile=10, rel=0, v=50., ops=[shared]))
    prices = dict(WHEAT=35., CARROT=65., TOMATO=80., STRAWBERRY=150., MELON=250.,
                  MILK=140., WOOL=200., EGG=65., FERTILIZER=35.)
    return (dict(_tier_prices=prices, _tier_last_day=29), segs, rest, tiles, day,
            dict(_dump_day={'left': 73}))


class PolishCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = load('_polish_original_test', 'mgt_lead_kb115lt2.py')
        cls.fast = load('_polish_cached_test', 'mgt_lead_kb115lt2_polishcache.py')
        recipe = json.loads((ROOT / 'results/fresh/semantic_strategy_20260928/executor_recipe_online.json').read_text())
        for module in (cls.base, cls.fast):
            module.CFG.update(recipe)

    def compare(self, seed, cache=True):
        original = fixture(seed)
        left, right = deepcopy(original), deepcopy(original)
        for module in (self.base, self.fast):
            module.CFG.update(sd_polish=240, sd_polish_seed=seed + 1,
                              sd_polish_xch=.2, sd_polish_water_c=20.,
                              sd_wheat_fert_mand=seed % 2, sd_tier_turnaround=seed % 2)
            module._TIER_WY = {3: 4, 31: 5} if seed % 2 else {}
        self.fast.CFG['sd_polish_cache'] = int(cache)
        self.base._tier_polish(*left)
        self.fast._tier_polish(*right)
        self.assertEqual(left, right, f'seed={seed}; cache={cache}')
        # The fixtures supplied to each implementation are isolated copies.
        self.assertEqual(original, fixture(seed))

    def test_same_moves_operations_and_scores_with_route_supply_variants(self):
        for seed in range(12):
            with self.subTest(seed=seed):
                self.compare(seed)

    def test_disabled_cache_and_cross_call_state_isolation(self):
        for seed, enabled in ((3, False), (7, True), (3, True), (7, False)):
            self.compare(seed, enabled)

    def test_original_hash_and_builder_scope(self):
        import ast
        import hashlib
        path = ROOT / 'agents/mgt_lead_kb115lt2.py'
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                         '527d4c48b5d6bbef7854d430797e8691858724242d50eeec1e1636665ee124e7')
        def defs(path):
            tree = ast.parse(path.read_text())
            return {n.name: ast.dump(n, include_attributes=False)
                    for n in tree.body if isinstance(n, ast.FunctionDef)}
        old, new = defs(path), defs(ROOT / 'agents/mgt_lead_kb115lt2_polishcache.py')
        self.assertEqual(old.keys(), new.keys())
        self.assertEqual([name for name in old if old[name] != new[name]], ['_tier_polish'])


if __name__ == '__main__':
    unittest.main()
