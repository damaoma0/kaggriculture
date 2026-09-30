"""Causal compact-archive extraction checks; no environment games."""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build_semantic_strategy_modern_data_20260928 import features_from_prefix, NULL_FIELDS

OUT = ROOT / 'results/fresh/semantic_strategy_20260928'


class Restricted(dict):
    def __getitem__(self, key):
        if key not in self:
            raise AssertionError('Non-contract field read: ' + str(key))
        return super().__getitem__(key)


class TestModernCausalData(unittest.TestCase):
    def test_prefix_only_reconstruction_ignores_market_and_current_labels(self):
        path = next((ROOT / 'data/leader_semantics/16732748').glob('*.json.gz'))
        with gzip.open(path, 'rt') as f:
            sem = json.load(f)
        for day in (6, 12, 29):
            prefix = [Restricted(planted=source['planted'],
                        animals=Restricted(placed=source['animals']['placed']),
                        built=source['built'], board=source['board']) for source in sem['days'][:day]]
            shops = [row['shop'] for row in sem['shops'] if row['reveal_day'] <= day]
            expected = features_from_prefix(sem['days'][:day], sem['days'][day]['board'],
                                            sem['days'][day]['cash_start'], shops)
            actual = features_from_prefix(prefix, sem['days'][day]['board'],
                                          sem['days'][day]['cash_start'], shops)
            self.assertEqual(expected, actual)
            changed = deepcopy(sem)
            for source in changed['days'][day:]:
                for key in list(source):
                    if key not in ('board', 'cash_start'):
                        source[key] = object()
            for source in changed['days'][day + 1:]:
                source['board'] = object()
                source['cash_start'] = object()
            after = features_from_prefix(changed['days'][:day], changed['days'][day]['board'],
                                         changed['days'][day]['cash_start'], shops)
            self.assertEqual(expected, after)

    def test_coop_cow_ambiguity_uses_observed_structure_history(self):
        history = [dict(planted={'WHEAT': [2]}, animals={'placed': [1]},
                        built={'BUILD_COOP': [0], 'BUILD_PASTURE': [1]}, board=[' .'] * 100)]
        board = [' L'] * 100
        board[:3] = ['co', 'co', 'WH']
        features = features_from_prefix(history, board, 12, [])
        self.assertEqual(features['own_structures'], {'COOP': 1, 'PASTURE': 1})
        self.assertEqual(features['own_animal_cohorts'], [dict(species='COW', birth=0, count=1)])
        self.assertEqual(features['own_crop_cohorts'], [dict(crop='WHEAT', birth=0, count=1)])
        self.assertTrue(all(features[field] is None for field in NULL_FIELDS))
        self.assertEqual(features['hands'], 0)

    def test_extension_preserves_frozen_rows_and_excludes_all_reserved_aliases(self):
        baseline = json.loads((OUT / 'causal_daily_rows.json').read_text())
        modern = json.loads((OUT / 'causal_daily_rows_modern60.json').read_text())
        combined = json.loads((OUT / 'causal_daily_rows_204.json').read_text())
        self.assertEqual(combined['rows'][:len(modern['rows'])], modern['rows'])
        restored = deepcopy(combined['rows'][len(modern['rows']):])
        for row_id, row in enumerate(restored):
            row['row_id'] = row_id
        self.assertEqual(restored, baseline['rows'])
        self.assertEqual(len(modern['rows']), 1440)
        self.assertEqual(len(combined['rows']), 4896)
        self.assertEqual(combined['training_seats'], 204)
        self.assertEqual(combined['training_games'], 203)
        self.assertFalse(set(combined['excluded_episodes']) & {r['meta']['episode'] for r in combined['rows']})
        for row in modern['rows']:
            self.assertTrue(all(row['features'][field] is None for field in NULL_FIELDS))
            self.assertNotIn('first_harvest_counts', row['target'])
            self.assertFalse({'episode', 'seed', 'rewards', 'tile', 'board'} & set(row['features']))
            self.assertTrue(all(c['birth'] < row['day'] for key in ('own_crop_cohorts', 'own_animal_cohorts') for c in row['features'][key]))
            if row['day'] == 29:
                self.assertIsNone(row['target']['end_crop_counts'])
                self.assertIsNone(row['target']['end_animal_counts'])

    def test_manifest_hashes_match_new_model_and_unchanged_baseline(self):
        audit = json.loads((OUT / 'modern_training_audit.json').read_text())
        manifest = json.loads((OUT / 'training_episodes_modern204.json').read_text())
        self.assertEqual(hashlib.sha256((OUT / 'causal_daily_rows.json').read_bytes()).hexdigest(), audit['baseline_sha256'])
        self.assertEqual(hashlib.sha256((OUT / 'causal_daily_rows_204.json').read_bytes()).hexdigest(), manifest['model_sha256'])
        self.assertEqual(manifest['model_sha256'], audit['combined_model_sha256'])
        self.assertEqual(audit['checked_prefix_states'], 1440)
        self.assertEqual(manifest['holdout_audit']['reserved_recorded_episodes'], 183)
        self.assertFalse(manifest['holdout_audit']['training_reserved_overlap'])

    def test_authorized_stage1_reuse_keeps_new_protocol_reserved(self):
        data = json.loads((OUT / 'causal_daily_rows_modern100.json').read_text())
        audit = json.loads((OUT / 'modern_training_audit_modern100.json').read_text())
        self.assertEqual(data['training_seats'], 100)
        self.assertEqual(len(data['rows']), 2400)
        self.assertEqual(len(data['excluded_episodes']), 183)
        self.assertEqual(len(data['holdout_audit']['training_stage1_overlap']), 40)
        self.assertIn('no longer independent', data['holdout_audit']['stage1_reuse_authorization'])
        self.assertFalse(set(data['excluded_episodes']) & {r['meta']['episode'] for r in data['rows']})
        self.assertEqual(hashlib.sha256((OUT / 'causal_daily_rows_modern100.json').read_bytes()).hexdigest(), audit['modern_model_sha256'])

    def test_oracle_d6_has_only_observed_prefix_coordinates(self):
        from semantic_tile_inputs_20260928 import assert_coordinate_free_days
        inputs = json.loads((OUT / 'semantic_inputs_oracle_d6_40.json').read_text())
        self.assertEqual(len(inputs), 40)
        for game in inputs.values():
            self.assertEqual(game['handoff_day'], 6)
            self.assertEqual(game['initial_state']['day'], 6)
            self.assertEqual(len(game['opening_plan']['board']), 7)
            self.assertTrue(all(event[0] < 6 for event in game['opening_plan']['events']))
            self.assertTrue(all('first_harvest_counts' not in day for day in game['days']))
            assert_coordinate_free_days(game)

    def test_corrected_oracle_d6_preserves_locks_until_purchase(self):
        from semantic_tile_planner_20260928 import compile_plan
        from audit_semantic_oracle_d6_locks_20260928 import validate
        inputs = json.loads((OUT / 'semantic_inputs_oracle_d6_40_locked_v2.json').read_text())
        self.assertEqual(len(inputs), 40)
        selected = {row['episode'] for row in json.loads((OUT / 'oracle_diagnostics/d6_exact_vs_retile_v3/manifest.json').read_text())['cases']}
        for episode, game in inputs.items():
            with self.subTest(episode=episode):
                expected = {str(t) for t, label in enumerate(game['initial_state']['board']) if label == ' L'}
                self.assertEqual(expected, {t for t, cell in game['initial_state']['tiles'].items() if cell.get('locked')})
                self.assertEqual(len(expected), 75)
                if episode in selected:
                    result = validate(game, compile_plan(game))
                    self.assertEqual(result['locked_at_handoff'], 75)


if __name__ == '__main__':
    unittest.main()
