"""Exact forecasts, reset isolation, and portable memory for reused search."""
from copy import deepcopy
import json
import unittest

import audit_value_forecast_components as A
import rival_trajectory_model_v3 as M
import value_tape_search as V
import value_tape_search_v2 as V2
import value_tape_search_v5 as F


class SpeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        c = A.context('wool')
        cls.obs, cls.memory = c['observation'], c['memory']
        cls.runner = F.runtime()
        cls.world = M.world(cls.obs, 0)

    def test_reuse_matches_fresh_after_other_route_and_world(self):
        obs, memory = deepcopy(self.obs), deepcopy(self.memory)
        before = deepcopy([obs, memory])
        engine = V.isolated_engine()
        hooks = engine._commit_unit, engine._apply_unit_action, engine._do_hire
        expected = V2.rollout(obs, memory, 0, self.world)
        self.runner.prepare(obs)
        self.runner.rollout(obs, memory, 196, M.world(obs, 3))
        self.assertEqual(expected, self.runner.rollout(obs, memory, 0, self.world))
        self.runner.rollout(obs, memory, None, M.world(obs, 5))
        self.assertEqual(expected, self.runner.rollout(obs, memory, 0, self.world))
        self.assertEqual([obs, memory], before)
        self.assertEqual(hooks, (engine._commit_unit, engine._apply_unit_action, engine._do_hire))

    def test_projection_has_shared_engine_state_but_no_cross_rollout_aliases(self):
        self.runner.prepare(self.obs)
        _, a = self.runner.project(self.obs)
        _, b = self.runner.project(self.obs)
        self.assertIs(a[0].observation.farms, a[1].observation.farms)
        a[0].observation.farms[0]['money'] += 777
        self.assertNotEqual(a[0].observation.farms, b[0].observation.farms)
        self.assertEqual(b[0].observation.farms, self.obs['farms'])

    def test_snapshot_copies_mutable_leaves(self):
        copy = F.observation_copy(self.obs)
        self.assertEqual(copy, self.obs)
        self.assertIs(type(copy), dict)
        copy['private']['inventories'][0]['WHEAT'] = -555
        self.assertNotEqual(copy['private'], self.obs['private'])

    def test_portable_memory_ignores_only_derived_tape_ids(self):
        a, b = deepcopy(self.memory), deepcopy(self.memory)
        a['_SHP_STATES']['_crop_tiles'] = {(5, 3)}
        b['_SHP_STATES']['_crop_tiles'] = {(5, 3)}
        state = next(iter(b['_SHP_STATES'].values()))
        state['cal'] = {(123456789, 19): ({(1, 2)}, set(), set())}
        if state.get('inplace') is not None:
            state['inplace']['tape'] = -98765
        self.assertEqual(F.semantic_memory(a), F.semantic_memory(b))
        state['wheat_credit'] = state.get('wheat_credit', 0) + 1
        self.assertNotEqual(F.semantic_memory(a), F.semantic_memory(b))


if __name__ == '__main__':
    unittest.main()
