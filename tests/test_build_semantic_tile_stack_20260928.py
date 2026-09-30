"""Contract checks for the convenience stack; no simulated games."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_semantic_tile_stack_20260928 as STACK


def fixture():
    fields = ("plant_counts", "build_counts", "remove_structure_counts", "animal_add_counts",
              "animal_exit_counts", "animal_retire_counts", "crop_end_counts", "first_harvest_counts",
              "crop_remove_counts", "crop_disappear_counts")
    days = [dict(day=d, hands=2, land_add_count=0, end_occupancy_counts=None,
                 **{field: {} for field in fields}) for d in range(4)]
    days[1]["animal_retire_counts"] = {"COW": 1}
    days[2]["animal_exit_counts"] = {"COW": 1}
    board = [" ."] * 100
    board[44] = "co"
    return dict(n=4, handoff_day=1, days=days,
                initial_state={"tiles": {"44": {"kind": "PASTURE", "animal": "COW", "placed_day": 0}}},
                opening_plan=dict(plant=[{}], events=[], board=[board, list(board)],
                    struct_by_day=[{"44": "PASTURE"}], animals_by_day=[{"44": "COW"}],
                    harv_tiles=[[]], removals=[[]], hands=[2], cum_sold=[{}],
                    land_day={"NE": 0, "SW": 0, "SE": 0}))


class StackContractTests(unittest.TestCase):
    def test_pure_api_keeps_input_and_explicit_retirement(self):
        semantic = fixture()
        semantic["unrelated_opponent_data"] = {"actions": ["never consulted"]}
        before = copy.deepcopy(semantic)
        with patch.object(Path, "read_text", side_effect=AssertionError("make_plan must not read recordings")):
            result = STACK.make_plan(semantic, polish_rounds=0)
        self.assertEqual(semantic, before)
        self.assertEqual(result["hands"], [2] * 4)
        self.assertEqual(result["animals_by_day"][1], {"44": "COW"})
        self.assertEqual(result["animals_by_day"][2], {})
        self.assertEqual(result["planner_metadata"]["daily"][0]["tiles"]["44"]["retiring_since"], 1)
        self.assertNotIn("suffix_polish", result["planner_metadata"])

    def test_future_coordinates_and_invalid_rounds_are_rejected(self):
        bad = fixture()
        bad["days"][2]["source_tiles"] = [44]
        with self.assertRaisesRegex(ValueError, "count-based"):
            STACK.make_plan(bad)
        with self.assertRaisesRegex(ValueError, "nonnegative"):
            STACK.make_plan(fixture(), polish_rounds=-1)

    def test_future_prefix_and_misaligned_days_are_rejected(self):
        semantic = fixture()
        semantic["opening_plan"]["land_day"]["SE"] = 2
        with self.assertRaisesRegex(ValueError, "future purchase"):
            STACK.make_plan(semantic)
        semantic = fixture()
        semantic["days"][2]["day"] = 1
        with self.assertRaisesRegex(ValueError, "day order"):
            STACK.make_plan(semantic)

    def test_observed_locked_land_cannot_be_omitted(self):
        semantic=fixture()
        semantic["opening_plan"]["board"][1][99]=" L"
        with self.assertRaisesRegex(ValueError,"locked"):
            STACK.make_plan(semantic)
        semantic["initial_state"]["tiles"]["99"]={"locked":True}
        STACK._validate_boundary(semantic)

    def test_cli_rejects_output_file_collision_before_writing(self):
        with patch.object(sys, "argv", ["builder", "--inputs", "semantic.json", "--out", "plan.json", "--spec", "plan.json"]):
            with self.assertRaises(SystemExit) as error:
                STACK.main()
        self.assertEqual(error.exception.code, 2)

    def test_default_strict_mode_and_explicit_polish(self):
        result = STACK.make_plan(fixture())
        self.assertEqual(result["planner_metadata"]["variant"], "reuse")
        self.assertEqual(result["planner_metadata"]["input_contract"], "strict")
        self.assertNotIn("suffix_polish", result["planner_metadata"])
        result = STACK.make_plan(fixture(), polish_rounds=2)
        self.assertIn("suffix_polish", result["planner_metadata"])

    def test_default_discards_legacy_first_harvest_timing(self):
        semantic = fixture()
        reference = STACK.make_plan(semantic)
        semantic["days"][3]["first_harvest_counts"] = {"STRAWBERRY": 999}
        self.assertEqual(STACK.make_plan(semantic), reference)
        with self.assertRaises(AssertionError):
            STACK.make_plan(semantic, mode="expanded")

    def test_frozen_config_is_preserved(self):
        frozen = ROOT / "results/fresh/kaggle_remote_semantic_tile_20260928/dataset_v1/repo/results/fresh/semantic_tile_20260928/spec.json"
        expected = json.loads(frozen.read_text())["ST28EXACT"]
        produced = STACK.make_spec(ROOT / "example_plans.json")["ST28STACK"]
        self.assertEqual(produced["agent"], expected["agent"])
        self.assertEqual(produced["base"], expected["base"])
        p_cfg, e_cfg = copy.deepcopy(produced["cfg"]), copy.deepcopy(expected["cfg"])
        p_cfg.pop("sd_tp_file"); e_cfg.pop("sd_tp_file")
        self.assertEqual(p_cfg, e_cfg)
        produced["cfg"]["sd_books_sell"].append("POISON")
        self.assertNotIn("POISON", STACK.KB115LT_RECIPE["cfg"]["sd_books_sell"])


if __name__ == "__main__":
    unittest.main()
