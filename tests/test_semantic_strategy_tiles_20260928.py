import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from semantic_strategy_tiles_20260928 import build_plan, observe_own


def observation(day=11, cells=None, quadrants=None):
    quadrants = quadrants or ["NW", "NE", "SW", "SE"]
    tiles = [[None for _ in range(10)] for _ in range(10)]
    for y in range(10):
        for x in range(10):
            q = ("S" if y >= 5 else "N") + ("E" if x >= 5 else "W")
            if q not in quadrants:
                tiles[y][x] = "LOCKED"
    for tile, cell in (cells or {}).items():
        tiles[tile//10][tile%10] = cell
    farm = dict(tiles=tiles, hands=[], farmer=[4, 4], money=5000, unlocked_quadrants=quadrants)
    return dict(step=day*24, player=0, farms=[farm, copy.deepcopy(farm)], private={}, market={})


def request(day, **changes):
    row = dict(day=day, plant_counts={}, animal_add_counts={}, animal_retire_counts={}, hands=10)
    row.update(changes)
    return dict(today=row, forecast=[row])


class StrategyTileTests(unittest.TestCase):
    def test_same_day_mature_wheat_replacement_has_valid_lifetime(self):
        obs = observation(cells={44: dict(kind="PLANT", crop="WHEAT", planted_day=8, yield_units=5)})
        before = copy.deepcopy(obs)
        plan, _, audit = build_plan(obs, request(11, plant_counts={"WHEAT": 1}))
        self.assertEqual(plan["plant"][11], {"44": "WHEAT"})
        self.assertIn(44, plan["harv_tiles"][11])
        self.assertEqual(obs, before)
        self.assertEqual(audit["semantic_today"]["crop_end_counts"], {"WHEAT": 1})

    def test_retiring_pen_stays_occupied_and_continues_next_morning(self):
        cow = dict(kind="PASTURE", animal="COW", placed_day=3, consecutive_unfed=0)
        obs = observation(cells={44: cow})
        plan, memory, _ = build_plan(obs, request(11, animal_retire_counts={"COW": 1}))
        self.assertEqual(plan["animals_by_day"][11], {"44": "COW"})
        self.assertEqual(plan["animals_by_day"][12], {})
        self.assertEqual(memory["retirements"]["44"]["first_unfed_day"], 11)
        obs = observation(12, {44: dict(cow, consecutive_unfed=1)})
        plan, memory, _ = build_plan(obs, request(12), memory)
        self.assertEqual(plan["animals_by_day"][12], {})
        self.assertEqual(plan["planner_metadata"]["warnings"], [])
        # Unexpected care must not silently cancel a committed retirement.
        obs = observation(13, {44: dict(cow, consecutive_unfed=0)})
        plan, memory, _ = build_plan(obs, request(13), memory)
        self.assertEqual(plan["animals_by_day"][13], {"44": "COW"})
        self.assertEqual(plan["animals_by_day"][14], {})
        obs = observation(14, {44: dict(kind="PASTURE")})
        _, memory, _ = build_plan(obs, request(14), memory)
        self.assertEqual(memory["retirements"], {})

    def test_accidental_unfed_day_does_not_create_retirement(self):
        obs = observation(cells={44: dict(kind="PASTURE", animal="SHEEP", placed_day=3, consecutive_unfed=1)})
        plan, _, _ = build_plan(obs, request(11))
        self.assertEqual(plan["animals_by_day"][11], {"44": "SHEEP"})
        self.assertEqual(plan["animals_by_day"][12], {"44": "SHEEP"})

    def test_low_yield_observed_wheat_gets_one_more_day(self):
        obs = observation(cells={44: dict(kind="PLANT", crop="WHEAT", planted_day=8, yield_units=2)})
        plan, _, audit = build_plan(obs, request(11))
        self.assertEqual(audit["semantic_today"]["crop_end_counts"], {})
        self.assertNotIn(44, plan["harv_tiles"][11])
        self.assertIn(44, plan["harv_tiles"][12])

    def test_mixed_ready_initial_cohorts_keep_public_readiness_on_actual_tiles(self):
        for crop, age, high, low in (("WHEAT",3,5,2),("CARROT",3,4,1),("MELON",10,6,3)):
            for ready, unready in ((44,0),(0,44)):
                with self.subTest(crop=crop,ready=ready):
                    obs = observation(cells={
                        ready:dict(kind="PLANT",crop=crop,planted_day=11-age,yield_units=high),
                        unready:dict(kind="PLANT",crop=crop,planted_day=11-age,yield_units=low)})
                    before = copy.deepcopy(obs)
                    plan, _, audit = build_plan(obs, request(11,plant_counts={crop:1}))
                    self.assertEqual(plan["harv_tiles"][11], [ready])
                    self.assertEqual(plan["harv_tiles"][12], [unready])
                    self.assertNotIn(str(unready), plan["plant"][11])
                    self.assertEqual(audit["semantic_today"]["crop_end_counts"], {crop:1})
                    self.assertEqual(obs,before)

    def test_capacity_and_land_constraints_and_empty_pen_conversion(self):
        cells = {10*y+x: dict(kind="PASTURE") for y in range(5) for x in range(5)}
        obs = observation(cells=cells, quadrants=["NW"])
        plan, _, audit = build_plan(obs, request(11, plant_counts={"WHEAT": 26}))
        self.assertEqual(len(plan["plant"][11]), 25)
        self.assertEqual(audit["semantic_today"]["remove_structure_counts"], {"PASTURE": 25})
        self.assertTrue(all(int(t)%10 < 5 and int(t)//10 < 5 for t in plan["plant"][11]))

    def test_terminal_planting_keeps_feasible_harvest_and_rejects_too_late(self):
        obs = observation(27)
        plan, _, _ = build_plan(obs, request(27, plant_counts={"WHEAT": 2, "STRAWBERRY": 1}))
        self.assertEqual(list(plan["plant"][27].values()), ["WHEAT", "WHEAT"])
        self.assertEqual(set(plan["harv_tiles"][29]), set(map(int, plan["plant"][27])))
        self.assertEqual(plan["planner_metadata"]["warnings"], [])

    def test_empty_pen_can_be_converted_to_another_animal_type(self):
        cells = {10*y+x: dict(kind="PASTURE") for y in range(5) for x in range(5)}
        obs = observation(cells=cells, quadrants=["NW"])
        plan, _, audit = build_plan(obs, request(11, animal_add_counts={"GOOSE": 1},
                                               remove_structure_counts={"PASTURE": 1}))
        self.assertEqual(list(plan["animals_by_day"][11].values()), ["GOOSE"])
        row = audit["semantic_today"]
        self.assertEqual(row["build_counts"], {"COOP": 1})
        self.assertEqual(row["remove_structure_counts"], {"PASTURE": 1})
        self.assertEqual(row["end_occupancy_counts"]["empty_structures"], {"PASTURE": 24})

    def test_observed_prefix_contains_only_played_births(self):
        obs = observation(6, {44: dict(kind="PLANT", crop="STRAWBERRY", planted_day=2)})
        memory = observe_own(obs, {})
        plan, _, _ = build_plan(obs, request(6), memory)
        self.assertEqual(plan["plant"][2], {"44": "STRAWBERRY"})
        self.assertEqual(plan["board"][6][44], "ST")
        self.assertEqual(plan["planner_metadata"]["input_contract"], "strict")


if __name__ == "__main__":
    unittest.main()
