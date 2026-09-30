"""Feasibility, isolation and objective checks for the semantic placement layer."""
import copy
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from semantic_tile_allocator_20260928 import DIST, assign_tiles


class TileAllocatorTests(unittest.TestCase):
    def test_assignment_uses_only_released_slots_and_preserves_inputs(self):
        requests = [{"kind": "WHEAT"}, {"crop": "STRAWBERRY"}, {"animal": "GOOSE"}]
        available = [11, 25, 44, 66, 82]
        state = {11: {"released_kind": "WHEAT"},
                 44: {"released_kind": "MELON"},
                 45: {"animal": "COW", "placed_day": 3}}
        original = copy.deepcopy((requests, available, state))
        result = assign_tiles(11, requests, available, state)
        self.assertEqual(len(result), len(requests))
        self.assertEqual(len(set(result)), len(result))
        self.assertTrue(set(result) <= set(available))
        self.assertNotIn(45, result)
        self.assertEqual((requests, available, state), original)

    def test_shed_sites_are_valid_crop_sites(self):
        self.assertEqual(assign_tiles(12, ["WHEAT"], [44], {}), [44])

    def test_same_crop_reuse_is_preferred_when_travel_is_equal(self):
        state = {34: {"released_kind": "WHEAT"}, 43: {"released_kind": "MELON"}}
        self.assertEqual(assign_tiles(12, ["WHEAT"], [43, 34], state, "reuse"), [34])

    def test_infeasible_request_is_reported(self):
        with self.assertRaisesRegex(ValueError, "insufficient"):
            assign_tiles(12, ["WHEAT", "STRAWBERRY"], [11], {})
        with self.assertRaisesRegex(ValueError, "distinct"):
            assign_tiles(12, ["WHEAT"], [11, 11], {})
        with self.assertRaisesRegex(ValueError, "expanded"):
            assign_tiles(12, [{"kind": "WHEAT", "count": 2}], [11, 12], {})

    def test_independent_of_available_and_state_insertion_order(self):
        requests = ["WHEAT", "GOOSE", "WHEAT", "TOMATO"]
        available = [30, 31, 32, 33, 40, 41, 43]
        state = {t: {"released_kind": "WHEAT" if t % 2 else "MELON"} for t in available}
        first = assign_tiles(15, requests, available, state)
        second = assign_tiles(15, requests, list(reversed(available)), dict(reversed(list(state.items()))))
        self.assertEqual(first, second)

    def test_same_day_cohorts_group_into_compact_patches(self):
        requests = ["WHEAT", "TOMATO"] * 4
        available = [0, 1, 10, 11, 88, 89, 98, 99]
        a = assign_tiles(15, requests, available, {},
                         dict(variant="cohort", distance=0, balance=0, reuse=0,
                              fertilizer=0, anchor=0))
        for kind in ("WHEAT", "TOMATO"):
            ts = [t for k, t in zip(requests, a) if k == kind]
            self.assertLessEqual(max(DIST[x][y] for x in ts for y in ts), 2)

    def test_optimization_never_worsens_its_declared_objective(self):
        rng = random.Random(982304)
        for _ in range(16):
            available = rng.sample(range(100), 22)
            requests = [rng.choice(["WHEAT", "CARROT", "STRAWBERRY", "GOOSE"])
                        for _ in range(10)]
            state = {t: {"released_kind": rng.choice(["WHEAT", "CARROT", "MELON"])}
                     for t in available}
            base = dict(variant="cohort", starts=3, return_details=True)
            _, before = assign_tiles(15, requests, available, state, dict(base, rounds=0))
            after_tiles, after = assign_tiles(15, requests, available, state, dict(base, rounds=4))
            self.assertLessEqual(after["objective"], before["objective"] + 1e-8)
            self.assertEqual(len(set(after_tiles)), len(requests))


if __name__ == "__main__":
    unittest.main()
