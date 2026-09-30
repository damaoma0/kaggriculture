"""Opening/data contract checks without playing games."""
from copy import deepcopy
import gzip
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from analyze_semantic_opening_20260928 import cohorts, trace_rows
from semantic_strategy_opening_20260928 import make_opening


class TestSemanticStrategyOpening(unittest.TestCase):
    def test_cohort_features_have_observed_births_without_positions(self):
        farm = dict(tiles=[[dict(kind='PLANT', crop='STRAWBERRY', planted_day=2),
                           dict(kind='PASTURE', animal='COW', placed_day=0)]], money=42,
                    hands=[], unlocked_quadrants=['NW'])
        assert cohorts(farm) == dict(own_crop_cohorts=[dict(crop='STRAWBERRY', birth=2, count=1)],
            own_animal_cohorts=[dict(species='COW', birth=0, count=1)], own_structures={'PASTURE': 1},
            cash=42, owned_quadrants=['NW'], hands=0)


    def test_features_do_not_depend_on_future_source_labels(self):
        path = ROOT / 'results/fresh/coherent_opening_20260924_01a0/extraction/full/trace-112802103-seat1.json.gz'
        with gzip.open(path, 'rt') as f:
            trace = json.load(f)
        before = trace_rows(trace, {'episode': 1})[6]['features']
        changed = deepcopy(trace)
        changed['shops_by_day'] = [['POISON_FUTURE']] * 31
        for day in range(7, 31):
            changed['daily'][day]['shops'] = ['POISON_FUTURE']
            changed['daily'][day]['farm']['money'] = -999999
        changed['source_sha256'] = 'different-source-identity'
        after = trace_rows(changed, {'episode': 999})[6]['features']
        assert before == after


    def test_training_and_opening_sources_exclude_reserved_worlds(self):
        data = json.loads((ROOT / 'results/fresh/semantic_strategy_20260928/causal_daily_rows.json').read_text())
        reserved = set(data['excluded_episodes'])
        assert data['holdout_audit']['reserved_recorded_episodes'] == 183
        assert not reserved & {r['meta']['episode'] for r in data['rows']}
        for row in data['rows']:
            assert not {'episode', 'seat', 'seed', 'rewards', 'tile', 'board', 'future_shops'} & row['features'].keys()
            assert all(x['birth'] <= row['day'] for x in row['features']['own_crop_cohorts'])
            assert all(x['birth'] <= row['day'] for x in row['features']['own_animal_cohorts'])
        with gzip.open(ROOT / 'data/semantic_strategy/opening_v5_contracts_20260928.json.gz', 'rt') as f:
            opening = json.load(f)
        assert not reserved & {t['ep'] for t in opening['library']['tapes']}


    def test_opening_refuses_day6_before_reading_any_other_state(self):
        opening = make_opening()
        with self.assertRaisesRegex(ValueError, 'day 6'):
            opening({'step': 144})


if __name__ == '__main__':
    unittest.main()
