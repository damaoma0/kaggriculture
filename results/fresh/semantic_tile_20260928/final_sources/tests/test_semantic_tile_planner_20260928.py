"""Compiler validation on semantic data only; no engine games or cloud jobs."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import semantic_tile_inputs_20260928 as INPUTS
import semantic_tile_planner_20260928 as PLANNER


def fixture(n, handoff, cells):
    board = [" ."] * 100
    for t, cell in cells.items():
        board[int(t)] = PLANNER.label(cell)
    return {
        "n": n, "handoff_day": handoff,
        "initial_state": {"tiles": deepcopy(cells)},
        "opening_plan": {
            "plant": [{} for _ in range(handoff)], "events": [],
            "board": [list(board) for _ in range(handoff + 1)],
            "struct_by_day": [{t: c["kind"] for t, c in cells.items() if c.get("kind") in ("COOP", "PASTURE")} for _ in range(handoff)],
            "animals_by_day": [{t: c["animal"] for t, c in cells.items() if c.get("animal")} for _ in range(handoff)],
            "harv_tiles": [[] for _ in range(handoff)], "removals": [[] for _ in range(handoff)],
            "hands": [1] * handoff, "cum_sold": [{} for _ in range(handoff)],
            "land_day": {"NE": 0, "SW": 0, "SE": 0},
        },
        "days": [{"day": day, "hands": 1} for day in range(n)],
    }


class SemanticTilePlannerTest(unittest.TestCase):
    def test_prior_crop_harvest_on_new_ongoing_planting_day_is_not_new_cohort_harvest(self):
        semantic = fixture(10, 3, {"4": {"kind": "PLANT", "crop": "TOMATO", "planted_day": 1}})
        # A wheat harvest and tomato planting share the tile on D1. The first
        # tomato harvest can only belong to this new cohort on D9, not D1.
        semantic["opening_plan"]["plant"][1] = {"4": "TOMATO"}
        semantic["opening_plan"]["events"] = [[1, 4, "TOMATO"]]
        semantic["opening_plan"]["harv_tiles"][1] = [4]
        semantic["days"][9]["first_harvest_counts"] = {"TOMATO": 1}
        plan = PLANNER.compile_plan(semantic, variant="distance")
        self.assertEqual(plan["harv_tiles"][9], [4])

    def test_retirement_preserves_physical_occupancy_until_second_night(self):
        semantic = fixture(4, 1, {"44": {"kind": "PASTURE", "animal": "COW", "placed_day": 0}})
        semantic["days"][1]["animal_retire_counts"] = {"COW": 1}
        semantic["days"][2]["animal_exit_counts"] = {"COW": 1}
        plan = PLANNER.compile_plan(semantic, variant="distance")
        daily = {row["day"]: row for row in plan["planner_metadata"]["daily"]}
        self.assertEqual(daily[1]["tiles"]["44"]["animal"], "COW")
        self.assertEqual(daily[1]["tiles"]["44"]["retiring_since"], 1)
        self.assertEqual(plan["animals_by_day"][1], {"44": "COW"})
        self.assertEqual(plan["animals_by_day"][2], {})
        self.assertEqual(daily[2]["tiles"]["44"]["kind"], "PASTURE")
        self.assertEqual(plan["planner_metadata"]["warnings"], [])

    def test_all_40_semantic_inputs_compile_and_preserve_daily_counts(self):
        path = ROOT / "results/fresh/semantic_tile_20260928/semantic_inputs.json"
        worlds = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(worlds), 40)
        for episode, semantic in worlds.items():
            with self.subTest(episode=episode):
                INPUTS.assert_coordinate_free_days(semantic)
                before = deepcopy(semantic)
                plan = PLANNER.compile_plan(semantic, variant="distance")
                self.assertEqual(before, semantic)
                self.assertEqual(plan["board"][11], semantic["initial_state"]["board"])
                daily = {row["day"]: row for row in plan["planner_metadata"]["daily"]}
                for day in range(11, 30):
                    change = semantic["days"][day]
                    self.assertEqual(dict(Counter(plan["plant"][day].values())), change["plant_counts"], (episode, day, "plant"))
                    self.assertEqual(plan["hands"][day], change["hands"], (episode, day, "hands"))
                    self.assertEqual(len(daily[day]["end_board"]), 100)
                    self.assertEqual(set(daily[day]["tiles"]), set(map(str, range(100))))
                    exp = change["end_occupancy_counts"]
                    if exp is not None:
                        cells = daily[day]["tiles"].values()
                        self.assertEqual(dict(Counter(c["crop"] for c in cells if c.get("crop"))), exp["crops"])
                        self.assertEqual(dict(Counter(c["kind"] for c in cells if c.get("kind") in ("COOP", "PASTURE"))), exp["structures"])
                        self.assertEqual(dict(Counter(c["animal"] for c in cells if c.get("animal"))), exp["animals"])
                    for retiring in daily[day]["retirements_started"]:
                        tile = str(retiring["tile"])
                        self.assertEqual(plan["animals_by_day"][day].get(tile), retiring["animal"])
                        if day + 1 < 30:
                            self.assertNotEqual(plan["animals_by_day"][day + 1].get(tile), retiring["animal"])


if __name__ == "__main__":
    unittest.main()
