"""Engine and isolation checks for the new semantic daily contract boundary."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from cumulative_engine_profiles import ENGINE as E
import semantic_strategy as S
from build_semantic_strategy_study import study_trace


class Dot(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


def observation(day=0):
    return Dot(step=24*day, day=day, hour=0, player=0,
        farms=[E._new_farm(10, 3000), E._new_farm(10, 3000)],
        private=E._new_private(), market=E._new_market(), town=E._new_town())


def official_day(obs, actions):
    own = deepcopy(obs)
    other = Dot(own, player=1, private=E._new_private())
    state = [Dot(observation=own, status='ACTIVE', reward=None),
             Dot(observation=other, status='ACTIVE', reward=None)]
    config = Dot(episodeSteps=720, boardSize=10, turnsPerDay=24, shedCapacity=100,
                  maxMarketOrdersPerTurn=10, farmHandCostMult=1,
                  townShopUnlockInterval=10000, weedSpawnChance=0)
    env = SimpleNamespace(done=False, info={'seed':0}, configuration=config)
    for offset, action in enumerate(actions):
        for item in state:
            item.observation.step = obs['step'] + offset
        state[0].action = deepcopy(action)
        state[1].action = {'farmer':['PASS'], 'hands':[], 'market':[]}
        E.interpreter(state, env)
    return state[0].observation


class SemanticStrategyTests(unittest.TestCase):
    def test_center_assignment_respects_ownership_and_existing_assets(self):
        obs = observation()
        farm = obs.farms[0]
        farm['tiles'][4][4] = E._new_animal('COW', 0)
        original = deepcopy(farm)
        result = S.place_cohorts(farm, [S.Cohort('MELON', 2, 8), S.Cohort('SHEEP', 2, 25)])
        self.assertEqual(original, farm)
        self.assertTrue(all(a['tile'][0] < 5 and a['tile'][1] < 5 for a in result))
        self.assertNotIn([4,4], [a['tile'] for a in result])
        self.assertEqual([a['species'] for a in result[:2]], ['SHEEP', 'SHEEP'])
        self.assertLessEqual(max(a['shed_distance'] for a in result[:2]),
                             min(a['shed_distance'] for a in result[2:]))

    def test_no_silent_truncation_of_quantity(self):
        with self.assertRaisesRegex(ValueError, 'insufficient'):
            S.place_cohorts(observation().farms[0], [S.Cohort('WHEAT', 26, 1)])

    def test_fertilizer_window_and_persistent_effect(self):
        tile = E._new_plant('STRAWBERRY', 0, 24)
        self.assertNotIn(['FERTILIZE'], S.maintenance(tile, 8, E)[0])
        self.assertIn(['FERTILIZE'], S.maintenance(tile, 9, E)[0])
        tile['fertilized_until_day'] = 10
        self.assertNotIn(['FERTILIZE'], S.maintenance(tile, 9, E)[0])

    def test_planting_day_water_is_required_for_survival(self):
        tile = E._new_plant('MELON', 0, 24)
        self.assertIn(['WATER'], S.maintenance(tile, 0, E)[0])
        farm = {'tiles':[[tile]]}
        E._daily_refresh_plants(farm, 0, 24)
        self.assertEqual(farm['tiles'][0][0], {'kind':'WEED'})

    def test_care_bonus_is_credited_after_tonights_production(self):
        tile = E._new_animal('SHEEP', 0)
        tile.update(fed_today=True, cared_today=True)
        farm = {'tiles':[[tile]]}
        E._daily_refresh_animals(farm, 5)
        self.assertEqual(tile['yield_units'], 1)
        self.assertEqual(tile['pending_care_bonus'], 1)
        for day in (6,7,8):
            tile['fed_today'] = True
            E._daily_refresh_animals(farm, day)
        self.assertEqual(tile['yield_units'], 3)

    def test_care_at_end_does_not_credit_nonexistent_day30(self):
        tile = E._new_animal('SHEEP', 23)  # first output day 29
        self.assertIn(['CARE'], S.maintenance(tile, 27, E)[0])
        self.assertNotIn(['CARE'], S.maintenance(tile, 28, E)[0])
        self.assertEqual(S.production_days(tile, E), [29])

    def test_single_skip_can_be_harmless_but_planting_day_skip_kills(self):
        cow = S.maintenance_skip_effect(E._new_animal('COW',0),0,'CARE',E)
        self.assertTrue(cow['applicable'])
        self.assertTrue(all(v == 0 for v in cow['output_delta'].values()), cow)
        wheat = E._new_plant('WHEAT',0,24)
        dead = S.maintenance_skip_effect(wheat,0,'WATER',E)
        self.assertTrue(dead['skipped']['lost_to_lack_of_service'])
        self.assertLess(dead['output_delta']['WHEAT'], 0)
        wheat.update(consecutive_unwatered=0)
        safe = S.maintenance_skip_effect(wheat,1,'WATER',E)
        self.assertEqual(safe['output_delta']['WHEAT'], 0)
        self.assertFalse(safe['skipped']['lost_to_lack_of_service'])

    def test_terminal_feed_and_ongoing_water_are_not_bought(self):
        self.assertNotIn(['FEED'], S.maintenance(E._new_animal('COW',0),29,E)[0])
        self.assertNotIn(['WATER'], S.maintenance(E._new_plant('STRAWBERRY',13,24),29,E)[0])

    def test_scheduler_establishes_fresh_quantities_in_full_interpreter(self):
        obs = observation()
        initial = deepcopy(obs)
        contract = S.compile_day(obs, [S.Cohort('SHEEP',2,29), S.Cohort('WHEAT',2,4)],
                                 E, workers=4, cash_reserve=8)
        result = S.check_scheduled_day(obs, contract)
        self.assertTrue(result['ok'], result)
        self.assertEqual(obs, initial)
        actual = official_day(obs, result['actions'])
        self.assertEqual(actual.farms[0], result['end_observation']['farms'][0])
        self.assertEqual(actual.private, result['end_observation']['private'])
        assets = Counter(t.get('crop') or t.get('animal') for row in actual.farms[0]['tiles']
                         for t in row if isinstance(t,dict))
        self.assertEqual(assets, {'SHEEP':2, 'WHEAT':2})
        self.assertEqual(result['completed_jobs'], len(contract['jobs']))

    def test_care_failure_is_rejected_even_if_other_jobs_succeed(self):
        obs = observation(8)
        obs.farms[0]['tiles'][4][4] = E._new_animal('SHEEP', 0)
        node = S.compile_day(obs, [], E, workers=1)
        original = S.scheduled_action
        def suppress_care(current, state):
            action = original(current, state)
            if action['farmer'] == ['CARE']:
                action['farmer'] = ['PASS']
            return action
        with patch.object(S, 'scheduled_action', suppress_care):
            result = S.check_scheduled_day(obs, node)
        self.assertFalse(result['ok'])
        self.assertEqual(result['failure']['reason'], 'unfulfilled_job')
        self.assertEqual(result['failure']['command'], ['CARE'])

    def test_budget_shortfall_returns_no_executable_partial_plan(self):
        obs = observation()
        obs.farms[0]['money'] = 2
        node = S.compile_day(obs, [S.Cohort('SHEEP',1,29)], E, workers=2)
        result = S.check_scheduled_day(obs, node)
        self.assertFalse(result['ok'])
        self.assertNotIn('actions', result)

    def test_same_tile_labels_with_changed_age_or_stock_require_recompile(self):
        obs = observation(8)
        obs.farms[0]['tiles'][4][4] = E._new_animal('SHEEP',0)
        node = S.compile_day(obs, [], E, workers=1)
        changed = deepcopy(obs)
        changed.farms[0]['tiles'][4][4]['placed_day'] = 1
        with self.assertRaisesRegex(ValueError, 'prerequisites_changed'):
            S.start_scheduled_day(changed, node)
        changed = deepcopy(obs)
        changed.private['shed']['WHEAT'] += 1
        with self.assertRaisesRegex(ValueError, 'prerequisites_changed'):
            S.start_scheduled_day(changed, node)

    def test_final_day_has_23_actions_and_delivers_output(self):
        obs = observation(29)
        tile = E._new_plant('STRAWBERRY', 13, 24)
        tile['yield_units'] = 4
        obs.farms[0]['tiles'][4][4] = tile
        node = S.compile_day(obs, [], E, workers=1)
        result = S.check_scheduled_day(obs, node)
        self.assertTrue(result['ok'], result)
        self.assertEqual(len(result['actions']), 23)
        self.assertEqual(result['end_observation']['private']['shed']['STRAWBERRY'], 4)

    def test_donor_features_exclude_future_shops_and_record_omission_uncertainty(self):
        obs = observation(5)
        obs.farms[0]['tiles'][4][4] = E._new_animal('SHEEP',0)
        daily = dict(day=5, shops=[], farm=obs.farms[0], private=obs.private, cash=3000)
        trace = dict(episode=7,seat=0,jobs=[],daily=[daily],shops_by_day=[['YARN_STORE']]*31)
        first = study_trace(trace,E)
        trace['shops_by_day'] = [['PIZZA_SHOP']]*31
        self.assertEqual(first, study_trace(trace,E))
        self.assertTrue(all(r['classification'] == 'not_observed_intent_unknown' for r in first[1]))


if __name__ == '__main__':
    unittest.main()
