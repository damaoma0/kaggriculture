"""Current public care-bank tie breaking preserves explicit retirement counts."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from semantic_strategy_tiles_20260928 import build_plan


def fixture(day=15, retire_day=15):
    tiles = [[None for _ in range(10)] for _ in range(10)]
    for tile, birth, bonus in ((44, 0, 2), (50, 9, 4)):
        tiles[tile // 10][tile % 10] = dict(kind='PASTURE', animal='COW', placed_day=birth,
                                          yield_units=0, pending_care_bonus=bonus,
                                          consecutive_unfed=0, fed_today=False)
    obs = dict(step=24 * day, player=0,
               farms=[dict(tiles=tiles, unlocked_quadrants=['NW', 'NE', 'SW', 'SE'], hands=[]), {}])
    forecast = [dict(day=d, plant_counts={}, animal_add_counts={},
                     animal_retire_counts={'COW': 1} if d == retire_day else {},
                     hands=10, target_land_count=4) for d in range(day, 30)]
    return obs, dict(today=forecast[0], forecast=forecast)


def retired(plan, day):
    row = next(row for row in plan['planner_metadata']['daily'] if row['day'] == day)
    return [event['tile'] for event in row['retirements_started']]


class RetirementBankTests(unittest.TestCase):
    def test_same_count_preserves_larger_bank_at_current_dawn(self):
        obs, proposal = fixture()
        saved = deepcopy((obs, proposal))
        base, _, old = build_plan(obs, proposal)
        fast, memory, new = build_plan(obs, proposal, config={'retire_policy': 'current_bank'})
        self.assertEqual(retired(base, 15), [50])
        self.assertEqual(retired(fast, 15), [44])
        self.assertEqual(old['semantic_today'], new['semantic_today'])
        self.assertEqual(new['semantic_today']['animal_retire_counts'], {'COW': 1})
        self.assertEqual(set(memory['retirements']), {'44'})
        self.assertEqual((obs, proposal), saved)

    def test_no_blanket_first_yield_or_survival_veto(self):
        obs, proposal = fixture()
        obs['farms'][0]['tiles'][4][4] = None
        plan, _, audit = build_plan(obs, proposal, config={'retire_policy': 'current_bank'})
        self.assertEqual(retired(plan, 15), [50])
        self.assertEqual(audit['semantic_today']['animal_retire_counts'], {'COW': 1})
        day15 = plan['planner_metadata']['daily'][0]
        self.assertEqual(day15['tiles']['50']['animal'], 'COW')
        self.assertEqual(day15['tiles']['50']['retiring_since'], 15)

    def test_observed_bank_is_not_used_for_future_forecast_ranking(self):
        obs, proposal = fixture(retire_day=16)
        original, _, _ = build_plan(obs, proposal)
        adjusted, _, _ = build_plan(obs, proposal, config={'retire_policy': 'current_bank'})
        self.assertEqual(retired(original, 16), retired(adjusted, 16))

    def test_equal_banks_keep_original_distance_tie_break(self):
        obs, proposal = fixture()
        obs['farms'][0]['tiles'][5][0]['pending_care_bonus'] = 2
        original, _, _ = build_plan(obs, proposal)
        adjusted, _, _ = build_plan(obs, proposal, config={'retire_policy': 'current_bank'})
        self.assertEqual(retired(original, 15), retired(adjusted, 15))

    def test_observed_retirement_commitment_is_not_reversed(self):
        obs, proposal = fixture()
        memory = {'retirements': {'50': dict(animal='COW', placed_day=9, first_unfed_day=14)}}
        obs['farms'][0]['tiles'][5][0]['consecutive_unfed'] = 1
        proposal['today']['animal_retire_counts'] = {}
        adjusted, next_memory, audit = build_plan(obs, proposal, memory, {'retire_policy': 'current_bank'})
        self.assertEqual(retired(adjusted, 15), [])
        self.assertEqual(next_memory['retirements']['50']['first_unfed_day'], 14)
        self.assertEqual(audit['semantic_today']['animal_retire_counts'], {})


if __name__ == '__main__':
    unittest.main()
