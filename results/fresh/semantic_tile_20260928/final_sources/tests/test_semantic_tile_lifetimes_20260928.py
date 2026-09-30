"""Anonymous lifecycle feasibility checks; these do not execute games."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import semantic_tile_lifetimes_20260928 as L
import semantic_tile_inputs_20260928 as I


def make_semantic(n, handoff, cells):
    return {"n": n, "handoff_day": handoff, "initial_state": {"tiles": cells},
            "opening_plan": {"harv_tiles": [[] for _ in range(handoff)]},
            "days": [{"day": day} for day in range(n)]}


class SemanticLifetimeTests(unittest.TestCase):
    def test_strict_all40_paths_require_no_copied_ongoing_harvest_timing(self):
        class HarvestReadForbidden(dict):
            def get(self, key, *default):
                if key == "first_harvest_counts":
                    raise AssertionError("Strict solver consulted forbidden copied harvest timing")
                return super().get(key, *default)

        worlds = json.loads((ROOT / "results/fresh/semantic_tile_20260928/semantic_inputs_strict.json").read_text(encoding="utf-8"))
        self.assertEqual(len(worlds), 40)
        for episode, semantic in worlds.items():
            with self.subTest(episode=episode):
                I.assert_coordinate_free_days(semantic)
                self.assertTrue(all("first_harvest_counts" not in row for row in semantic["days"]))
                semantic["days"] = [HarvestReadForbidden(row) for row in semantic["days"]]
                result = L.solve_lifetimes(semantic)
                self.assertFalse(result["use_first_harvest_counts"])
                L.validate_lifetimes(semantic, result)
                for crop in L.ONGOING:
                    for path in result["by_crop"][crop]:
                        if path["prior_first_harvest"] is not None:
                            self.assertEqual(path["first_harvest"], path["prior_first_harvest"])
                            continue
                        earliest = max(semantic["handoff_day"], path["birth"] + L.FIRST[crop])
                        end = semantic["n"] - 1 if path["exit_day"] is None else path["exit_day"]
                        expected = earliest if earliest <= end else None
                        self.assertEqual(path["first_harvest"], expected)

    def test_strict_solution_is_unchanged_when_forbidden_timing_is_poisoned(self):
        semantic = make_semantic(18, 11, {"1": {"crop": "TOMATO", "planted_day": 8}})
        expected, _ = L.solve_crop(semantic, "TOMATO")
        for row in semantic["days"]:
            row["first_harvest_counts"] = {"TOMATO": 99999}
        actual, _ = L.solve_crop(semantic, "TOMATO")
        self.assertEqual(expected, actual)

    def test_all_40_count_schedules_have_exact_maturity_and_lifespan_feasible_paths(self):
        worlds = json.loads((ROOT / "results/fresh/semantic_tile_20260928/semantic_inputs.json").read_text(encoding="utf-8"))
        self.assertEqual(len(worlds), 40)
        for episode, semantic in worlds.items():
            with self.subTest(episode=episode):
                before = deepcopy(semantic)
                paths = L.solve_lifetimes(semantic, use_first_harvest_counts=True)
                self.assertTrue(paths["use_first_harvest_counts"])
                self.assertEqual(before, semantic)
                L.validate_lifetimes(semantic, paths)
                for crop, rows in paths["by_crop"].items():
                    for path in rows:
                        self.assertEqual(set(path), {"crop", "birth", "initial", "prior_first_harvest", "first_harvest", "exit_day", "exit_type", "count"})
                        first = path["first_harvest"]
                        if first is not None:
                            self.assertGreaterEqual(first - path["birth"], L.FIRST[crop])
                            self.assertLessEqual(first - path["birth"], L.LAST_HARVEST[crop])
                        end = path["exit_day"]
                        if end is not None:
                            self.assertLessEqual(end - path["birth"], L.EXPIRY[crop])

    def test_release_young_unharvested_crop_preserves_older_first_harvest(self):
        semantic = make_semantic(18, 11, {
            "1": {"crop": "TOMATO", "planted_day": 8},
            "2": {"crop": "TOMATO", "planted_day": 10},
        })
        semantic["days"][12]["crop_remove_counts"] = {"TOMATO": 1}
        semantic["days"][16]["first_harvest_counts"] = {"TOMATO": 1}
        paths, _ = L.solve_crop(semantic, "TOMATO", use_first_harvest_counts=True)
        removed = next(path for path in paths if path["exit_type"] == "remove")
        harvested = next(path for path in paths if path["first_harvest"] == 16)
        self.assertEqual(removed["birth"], 10)
        self.assertEqual(harvested["birth"], 8)

    def test_first_harvest_then_dig_on_same_day_is_feasible(self):
        semantic = make_semantic(18, 11, {"1": {"crop": "TOMATO", "planted_day": 8}})
        semantic["days"][16]["crop_remove_counts"] = {"TOMATO": 1}
        semantic["days"][16]["first_harvest_counts"] = {"TOMATO": 1}
        paths, _ = L.solve_crop(semantic, "TOMATO", use_first_harvest_counts=True)
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0]["first_harvest"], paths[0]["exit_day"])

    def test_an_impossible_early_harvest_is_rejected(self):
        semantic = make_semantic(15, 11, {"1": {"crop": "TOMATO", "planted_day": 10}})
        semantic["days"][12]["first_harvest_counts"] = {"TOMATO": 1}
        with self.assertRaises(L.LifetimeInfeasible):
            L.solve_crop(semantic, "TOMATO", use_first_harvest_counts=True)

    def test_renaming_initial_tiles_cannot_change_anonymous_paths(self):
        semantic = make_semantic(18, 11, {
            "1": {"crop": "TOMATO", "planted_day": 8},
            "2": {"crop": "TOMATO", "planted_day": 10},
        })
        semantic["days"][12]["crop_remove_counts"] = {"TOMATO": 1}
        semantic["days"][16]["first_harvest_counts"] = {"TOMATO": 1}
        expected, _ = L.solve_crop(semantic, "TOMATO", use_first_harvest_counts=True)
        semantic["initial_state"]["tiles"] = {"98": semantic["initial_state"]["tiles"]["2"],
                                                   "14": semantic["initial_state"]["tiles"]["1"]}
        actual, _ = L.solve_crop(semantic, "TOMATO", use_first_harvest_counts=True)
        self.assertEqual(expected, actual)

    def test_default_cli_is_strict_and_extension_requires_explicit_flag(self):
        semantic = make_semantic(20, 11, {"1": {"crop": "TOMATO", "planted_day": 8}})
        semantic["days"][17]["first_harvest_counts"] = {"TOMATO": 1}
        with tempfile.TemporaryDirectory(prefix="semantic-lifetime-cli-") as folder:
            source = Path(folder) / "input.json"
            source.write_text(json.dumps({"example": semantic}), encoding="utf-8")
            for extra, expected_first, extended in (([], 16, False), (["--extended-first-harvest-counts"], 17, True)):
                dest = Path(folder) / ("extended.json" if extended else "strict.json")
                subprocess.run([sys.executable, str(ROOT / "scripts/semantic_tile_lifetimes_20260928.py"),
                                "--inputs", str(source), "--out", str(dest), *extra],
                               check=True, capture_output=True, text=True)
                result = json.loads(dest.read_text(encoding="utf-8"))["example"]
                self.assertEqual(result["use_first_harvest_counts"], extended)
                self.assertEqual(result["by_crop"]["TOMATO"][0]["first_harvest"], expected_first)


if __name__ == "__main__":
    unittest.main()
