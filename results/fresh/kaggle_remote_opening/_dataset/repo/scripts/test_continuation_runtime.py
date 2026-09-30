"""Integration tests for physical projection, atomic activation and recovery."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import io
import json
from pathlib import Path
import unittest

from fragments import continuation_executor as C
from fragments import continuation_projection as P
from fragments.continuation_control import ContinuationController
from fragments.continuation_calendar import adapt_calendar
from validate_segment_executor import selected_nodes

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    nodes = selected_nodes(json.loads((ROOT / 'results/fresh/segment_stitch/library.json').read_text())['segments'])
    n = deepcopy(nodes[0]); n['safety_assets'] = False; n['hire_to'] = 11
    obs = {'player': 0, 'step': n['day'] * 24, 'day': n['day'], 'hour': 0,
           'farms': [deepcopy(n['start_farm']), deepcopy(n['start_farm'])],
           'private': deepcopy(n['start_private']), 'market': deepcopy(n['start_market']),
           'town': {'unlocked_shops': list(n['start_shops'])}}
    return obs, n


class ContinuationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.obs, cls.node = fixture()

    def test_full_window_matches_official_interpreter(self):
        obs, node = deepcopy(self.obs), deepcopy(self.node)
        result = P.check_window(obs, node, C)
        self.assertTrue(result['ok'], result)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            from kaggle_environments import make
            from kaggle_environments.envs.kaggriculture import kaggriculture as E
            from kaggle_environments.utils import structify
            env = make('kaggriculture', configuration={'episodeSteps': 720, 'weedSpawnChance': 0}, info={'seed': 20260922})
            env.reset()
        state = env.state
        state[0].observation.farms[0] = structify(deepcopy(obs['farms'][0]))
        state[0].observation.private = structify(deepcopy(obs['private']))
        state[0].observation.market = structify(deepcopy(obs['market']))
        state[0].observation.town.unlocked_shops = deepcopy(obs['town']['unlocked_shops'])
        for offset, action in enumerate(result['actions']):
            t = obs['step']
            for seat in (0, 1): state[seat].observation.step = t
            state[0].action = deepcopy(action); state[1].action = {'farmer': ['PASS'], 'hands': [], 'market': []}
            E.interpreter(state, env)
            obs, report = P.project_step(obs, action)
            self.assertEqual(obs['farms'][0], state[0].observation.farms[0], (offset, report))
            self.assertEqual(obs['private'], state[0].observation.private, offset)
            self.assertEqual(obs['market'], state[0].observation.market, offset)
            # The independent engine reveals shops after this window; projection
            # intentionally never invents that unseen branch.
        self.assertEqual(result['end_farm'], obs['farms'][0])

    def test_rejects_later_day_before_activation(self):
        node = deepcopy(self.node)
        node['jobs'].append({'day': 1, 'hour': 0, 'tile': [9, 9], 'cmd': ['PLANT', 'WHEAT']})
        result = P.check_window(deepcopy(self.obs), node, C)
        self.assertFalse(result['ok'])
        self.assertGreaterEqual(result.get('step', 0), self.obs['step'] + 24)

    def test_projection_detects_short_purchase(self):
        obs = deepcopy(self.obs); obs['farms'][0]['money'] = 0
        _, report = P.project_step(obs, {'farmer': ['PASS'], 'hands': [], 'market': [['BUY_SEED', 'WHEAT', 1]]})
        self.assertIn('purchase_shortfall', report['failures'])

    def test_displaced_worker_discards_continuation(self):
        control = ContinuationController(); control.active = True
        control.expected = deepcopy(self.obs)
        obs = deepcopy(self.obs); obs['farms'][0]['farmer'] = [0, 0]
        control.actions[obs['step']] = {'farmer': ['PLANT', 'MELON'], 'hands': [], 'market': []}
        action = control.action(obs)
        self.assertEqual(control.report['recoveries'][0]['reason'], 'worker_positions')
        self.assertTrue(all(a.get('farmer') != ['PLANT', 'MELON'] for a in control.actions.values()))
        self.assertNotEqual(action['farmer'], ['PLANT', 'MELON'])

    def test_missing_feed_never_advances_dead_commands(self):
        obs = deepcopy(self.obs)
        pos = next((x, y) for y, row in enumerate(obs['farms'][0]['tiles']) for x, tile in enumerate(row)
                   if isinstance(tile, dict) and tile.get('animal'))
        obs['farms'][0]['farmer'] = list(pos)
        obs['private']['inventories'][0] = {}
        control = ContinuationController(); control.active = True
        control.actions[obs['step']] = {'farmer': ['FEED'], 'hands': [], 'market': []}
        control.actions[obs['step'] + 1] = {'farmer': ['CARE'], 'hands': [], 'market': []}
        control.action(obs)
        self.assertEqual(control.report['recoveries'][-1]['reason'], 'action_precondition')
        self.assertFalse(control.actions)

    def test_calendar_preserves_existing_asset_identity(self):
        node = adapt_calendar(deepcopy(self.obs), deepcopy(self.node))
        self.assertTrue(node['jobs'])
        for job in node['jobs']:
            if job['cmd'][0] == 'DIG':
                tile = job.get('pre_tile')
                self.assertFalse(isinstance(tile, dict) and tile.get('animal'))
        self.assertTrue(all(0 <= j['day'] <= 2 for j in node['jobs']))

    def test_feed_shortage_recovery_preserves_herd_in_engine(self):
        obs, node = deepcopy(self.obs), deepcopy(self.node)
        compiled = P.check_window(obs, node, C)
        self.assertTrue(compiled['ok'])
        control = ContinuationController(); control.active = True
        control.actions = {obs['step'] + i: a for i, a in enumerate(compiled['actions'])}
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            from kaggle_environments import make
            from kaggle_environments.envs.kaggriculture import kaggriculture as E
            from kaggle_environments.utils import structify
            env = make('kaggriculture', configuration={'episodeSteps': 720, 'weedSpawnChance': 0}, info={'seed': 20260922})
            env.reset()
        state = env.state
        for key in ('private', 'market', 'town', 'day', 'hour', 'step'):
            setattr(state[0].observation, key, structify(deepcopy(obs[key])))
        state[0].observation.farms[0] = structify(deepcopy(obs['farms'][0]))
        def herd(farm):
            return [(x, y, t['animal'], t['placed_day']) for y, row in enumerate(farm['tiles']) for x, t in enumerate(row)
                    if isinstance(t, dict) and t.get('animal')]
        initial_herd = herd(obs['farms'][0])
        for t in range(obs['step'], obs['step'] + 72):
            for s in (0, 1): state[s].observation.step = t
            if t == obs['step'] + 2:
                state[0].observation.private.shed['WHEAT'] = 0
                for inv in state[0].observation.private.inventories: inv.pop('WHEAT', None)
            self.assertGreaterEqual(len(state[0].observation.private['inventories']), len(state[0].observation.farms[0]['hands']) + 1,
                                    ('invalid_fixture', t, state[0].observation.player))
            action = control.action(state[0].observation)
            state[0].action = action
            state[1].action = {'farmer': ['PASS'], 'hands': [], 'market': []}
            E.interpreter(state, env)
        self.assertTrue(control.report['recoveries'])
        self.assertEqual(initial_herd, herd(state[0].observation.farms[0]))

    def test_expired_planning_budget_abstains(self):
        old = C.set_deadline(-1)
        try:
            with self.assertRaises(C.PlanningBudgetExceeded): C.segment_executor_start(deepcopy(self.obs), deepcopy(self.node))
        finally: C.set_deadline(old)

    def test_rejected_proposal_does_not_change_live_state(self):
        obs = deepcopy(self.obs); obs['farms'][0]['money'] = 0
        before = deepcopy(obs)
        control = ContinuationController()
        self.assertFalse(control.propose(obs, deepcopy(self.node)))
        self.assertFalse(control.active)
        self.assertFalse(control.actions)
        self.assertEqual(obs, before)

    def test_atomic_seed_shortage_rejects_entire_plant_batch(self):
        obs = deepcopy(self.obs)
        obs['farms'][0]['hands'] = [[0, 0]]
        obs['private']['inventories'] = [{}, {}]
        obs['private']['seeds']['WHEAT'] = 1
        control = ContinuationController(); control.active = True
        control.actions[obs['step']] = {'farmer': ['PLANT', 'WHEAT'], 'hands': [['PLANT', 'WHEAT']], 'market': []}
        action = control.action(obs)
        self.assertEqual(control.report['recoveries'][-1]['reason'], 'action_precondition')
        self.assertTrue(all(cmd[0] != 'PLANT' for cmd in [action['farmer']] + action['hands']))
        self.assertEqual(obs['private']['seeds']['WHEAT'], 1)


if __name__ == '__main__': unittest.main(verbosity=2)
