"""Public-input isolation and interrupt-safe exact forecast checks."""
from copy import deepcopy
import json
import pickle
import time
import unittest

import tape_semantic_features as S
import train_tape_semantic_ranker as T
import value_tape_search_v8 as Scout
from validate_tape_scout_fixtures import replay


class SemanticInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.points = T.load_points()

    def test_no_target_metadata_forecast_labels_or_numeric_route_identity(self):
        point = next(p for p in self.points if p['panel'] == 'generalization')
        obs, memory, candidates = deepcopy((point['obs'], point['memory'], point['decision']['candidates']))
        original = pickle.dumps((obs, memory, candidates))
        expected = S.features(obs, memory, candidates)
        self.assertEqual(original, pickle.dumps((obs, memory, candidates)))
        obs['seed'] = 123
        obs['future_shops'] = ['YARN_STORE']*8
        obs['opponent_identity'] = 'poison'
        obs['rival_private'] = {'cash': 10**12, 'WOOL': 999999}
        obs['remainingOverageTime'] = -999
        for c in candidates:
            c.update(predictions=[{'cash_gain': 10**15}], admitted=True, risk_score=10**15)
            if c['route'] is not None:
                c['route'] += 100000
        memory['players'][int(obs['player'])]['route'] += 100000
        self.assertEqual(expected, S.features(obs, memory, candidates))
        obs['market']['prices']['WOOL'] += 50
        self.assertNotEqual(expected, S.features(obs, memory, candidates))

    def test_reserved_recoveries_are_retained_by_scout(self):
        for point in self.points:
            if point['panel'] != 'historical':
                continue
            result = replay(point, Scout)
            self.assertEqual(result['selected'], point['decision']['selected'])
            for c in result['candidates']:
                if c['admitted']:
                    self.assertEqual(len(c['predictions']), 8)
                    self.assertFalse(c['protection_failures'])

    def test_pairwise_fit_ignores_query_constant_identity_features(self):
        rows = []
        for q, shift in (('a', 17), ('b', -99)):
            for signal in (-2, -1, 0, 1, 2):
                rows.append(dict(query=q, group=q, utility=signal,
                    features={'signal':signal, 'query_constant':shift}))
        model = T.fit(rows, 1)
        self.assertNotIn('query_constant', model['names'])
        values = [T.predict(model, {'signal':s, 'query_constant':999999}) for s in (-2, 0, 2)]
        self.assertEqual(values, sorted(values))


class DeadlineTests(unittest.TestCase):
    def test_interrupted_rollout_restores_hooks_and_next_forecast(self):
        from kaggle_environments.utils import structify
        point = next(p for p in T.load_points() if p['id'] == 'historical-111269605-15')
        obs, memory = structify(point['obs']), point['memory']
        runner = Scout.runtime()
        runner.prepare(obs)
        world = Scout.M.world(obs, 0)
        engine = Scout.V.isolated_engine()
        names = ('_commit_unit', '_apply_unit_action', '_do_hire')
        before = [getattr(engine, n) for n in names]
        payload = pickle.dumps((obs, memory))
        runner.rollout_impl.__globals__['_deadline'] = time.perf_counter()-1
        try:
            with self.assertRaises(Scout.SearchDeadline):
                runner.rollout(obs, memory, None, world)
        finally:
            runner.rollout_impl.__globals__['_deadline'] = None
        self.assertEqual(before, [getattr(engine, n) for n in names])
        self.assertEqual(payload, pickle.dumps((obs, memory)))
        actual = runner.rollout(obs, memory, None, world)
        expected = point['decision']['candidates'][0]['predictions'][0]
        self.assertEqual(json.loads(json.dumps(actual)), expected)
        route, decision = Scout.choose(obs, memory, budget_seconds=0)
        self.assertIsNone(route)
        self.assertTrue(decision['timed_out'])
        self.assertFalse(any(c['admitted'] for c in decision['candidates']))
        self.assertFalse(runner.busy)


if __name__ == '__main__':
    unittest.main()
