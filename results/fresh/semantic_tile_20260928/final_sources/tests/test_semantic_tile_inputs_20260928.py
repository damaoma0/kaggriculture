"""Schema, coordinate isolation, endpoint and engine-timing checks; no games."""
from copy import deepcopy
import gzip
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import semantic_tile_inputs_20260928 as S


class SemanticTileInputsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.executor = S.load_executor()
        cls.panel = S.read_panel(S.DEFAULT_PANEL)

    def load(self, team, episode):
        sem = json.loads(gzip.decompress((ROOT / "data/leader_semantics" / team / f"{episode}.json.gz").read_bytes()))
        exact = self.executor.TilePlanView(self.executor.Target(sem)).to_dict()
        return sem, exact

    def test_all_40_inputs_conserve_crop_counts_and_observed_retirements(self):
        self.assertEqual(len(self.panel), 40)
        retirement_count = 0
        for team, episode in self.panel:
            sem, exact = self.load(team, episode)
            before = deepcopy((sem, exact))
            game, audit = S.extract_game(sem, exact)
            self.assertEqual((sem, exact), before, "Extraction mutated source evidence")
            S.assert_coordinate_free_days(game)
            for row in game["days"][:-1]:
                d = row["day"]
                start = S.counts(S.LABEL_CROP[x] for x in exact["board"][d] if x in S.LABEL_CROP)
                for crop in S.LABEL_CROP.values():
                    planned_end = start.get(crop, 0) + row["plant_counts"].get(crop, 0)
                    planned_end -= sum(row[field].get(crop, 0) for field in ("crop_end_counts", "crop_remove_counts", "crop_disappear_counts"))
                    self.assertEqual(planned_end, row["end_occupancy_counts"]["crops"].get(crop, 0), (episode, d, crop))
                prior_structs = S.counts(exact["struct_by_day"][d - 1].values()) if d else {}
                prior_animals = S.counts(exact["animals_by_day"][d - 1].values()) if d else {}
                for kind in ("PASTURE", "COOP"):
                    net = prior_structs.get(kind, 0) + row["build_counts"].get(kind, 0) - row["remove_structure_counts"].get(kind, 0)
                    self.assertEqual(net, row["end_occupancy_counts"]["structures"].get(kind, 0), (episode, d, kind))
                for species in ("COW", "SHEEP", "GOOSE"):
                    net = prior_animals.get(species, 0) + row["animal_add_counts"].get(species, 0) - row["animal_exit_counts"].get(species, 0)
                    self.assertEqual(net, row["end_occupancy_counts"]["animals"].get(species, 0), (episode, d, species))
                for animal in audit["days"][d]["retiring_animals"]:
                    tile, species = animal["tile"], animal["species"]
                    self.assertEqual(animal["exit_day"], d + 1)
                    self.assertEqual(exact["animals_by_day"][d].get(str(tile)), species)
                    self.assertNotEqual(exact["animals_by_day"][d + 1].get(str(tile)), species)
                    self.assertNotIn(tile, sem["days"][d]["maintenance"]["FEED"])
                    self.assertNotIn(tile, sem["days"][d + 1]["maintenance"]["FEED"])
                    retirement_count += d >= 11
            self.assertIsNone(game["days"][-1]["end_occupancy_counts"])
            self.assertIsNone(audit["days"][-1]["board_end"])
        self.assertEqual(retirement_count, 454)

    def test_future_coordinate_permutation_cannot_change_semantics(self):
        sem, exact = self.load(*self.panel[0])
        expected, _ = S.extract_game(sem, exact)
        perm = {t: (37 * t + 17) % 100 for t in range(100)}

        def board(row):
            out = [None] * 100
            for tile, label in enumerate(row):
                out[perm[tile]] = label
            return out

        for d in sem["days"]:
            d["board"] = board(d["board"])
            for field in ("planted", "built", "maintenance"):
                d[field] = {k: [perm[int(t)] for t in tiles] for k, tiles in d[field].items()}
            d["dug"] = [perm[int(t)] for t in d["dug"]]
            d["harvested"]["tiles"] = [perm[int(t)] for t in d["harvested"]["tiles"]]
            for field in ("placed", "culled"):
                d["animals"][field] = [perm[int(t)] for t in d["animals"][field]]
        for field in ("plant", "struct_by_day", "animals_by_day"):
            exact[field] = [{str(perm[int(t)]): value for t, value in row.items()} for row in exact[field]]
        exact["board"] = [board(row) for row in exact["board"]]
        exact["events"] = [[d, perm[int(t)], c] for d, t, c in exact["events"]]
        exact["harv_tiles"] = [[perm[int(t)] for t in row] for row in exact["harv_tiles"]]
        exact["removals"] = [[[perm[int(t)], c, d] for t, c, d in row] for row in exact["removals"]]
        actual, _ = S.extract_game(sem, exact)
        self.assertEqual(expected["days"], actual["days"])
        self.assertEqual(expected["terminal_unfed_counts"], actual["terminal_unfed_counts"])
        self.assertEqual(expected["terminal_two_unfed_counts"], actual["terminal_two_unfed_counts"])
        self.assertNotEqual(expected["initial_state"]["tiles"], actual["initial_state"]["tiles"])

    def test_final_hires_are_successful_orders_not_missing_midnight_snapshot(self):
        for team, episode in self.panel:
            sem, exact = self.load(team, episode)
            game, _ = S.extract_game(sem, exact)
            self.assertEqual(exact["hands"][-1], 0)
            self.assertEqual(game["days"][-1]["hands"], sem["days"][-2]["labour"]["hires_arrived"])
            self.assertEqual(game["days"][-1]["hands"], 10)

    def test_opening_has_no_future_planned_tile_coordinates(self):
        sem, exact = self.load(*self.panel[0])
        game, _ = S.extract_game(sem, exact)
        opening = game["opening_plan"]
        self.assertEqual(len(opening["board"]), 12)
        self.assertTrue(all(d <= 10 for d, _, _ in opening["events"]))
        self.assertTrue(all(len(opening[f]) == 11 for f in ("plant", "struct_by_day", "animals_by_day", "hands", "harv_tiles", "removals")))
        game["days"][11]["tile"] = 33
        with self.assertRaises(AssertionError):
            S.assert_coordinate_free_days(game)

    def test_strict_input_removes_ongoing_first_harvest_timing_without_mutation(self):
        sem, exact = self.load(*self.panel[0])
        expanded, _ = S.extract_game(sem, exact)
        before = deepcopy(expanded)
        strict = S.strict_input(expanded)
        self.assertEqual(expanded, before)
        self.assertTrue(all("first_harvest_counts" not in row for row in strict["days"]))
        self.assertNotIn("terminal_unfed_counts", strict)
        self.assertNotIn("terminal_two_unfed_counts", strict)
        self.assertIn("terminal_unfed_counts", expanded)
        self.assertIn("terminal_two_unfed_counts", expanded)
        self.assertEqual(strict["opening_plan"], expanded["opening_plan"])
        S.assert_coordinate_free_days(strict)

    def test_clean_strict_input_reproduces_all_frozen_final_plans(self):
        import semantic_tile_planner_20260928 as planner
        base = ROOT / "results/fresh/semantic_tile_20260928"
        clean = json.loads((base / "semantic_inputs_strict_clean.json").read_text(encoding="utf-8"))
        frozen = json.loads((base / "plans/reuse_strict.json").read_text(encoding="utf-8"))
        self.assertEqual(len(clean), 40)
        for episode, semantic in clean.items():
            with self.subTest(episode=episode):
                self.assertNotIn("terminal_unfed_counts", semantic)
                self.assertNotIn("terminal_two_unfed_counts", semantic)
                self.assertTrue(all("first_harvest_counts" not in row for row in semantic["days"]))
                self.assertEqual(planner.compile_plan(semantic), frozen[episode])

    def test_engine_keeps_retiring_animal_occupied_for_first_unfed_day(self):
        import upkeep_engine
        engine = upkeep_engine.engine()
        cow = dict(kind="PASTURE", animal="COW", placed_day=0, fed_today=False,
                   consecutive_unfed=0, cared_today=False, pending_care_bonus=0,
                   yield_units=0, fertilizer_available=False)
        farm = {"tiles": [[cow]]}
        engine._daily_refresh_animals(farm, 10)
        self.assertEqual(farm["tiles"][0][0]["animal"], "COW")
        self.assertEqual(farm["tiles"][0][0]["consecutive_unfed"], 1)
        engine._daily_refresh_animals(farm, 11)
        self.assertEqual(farm["tiles"][0][0], {"kind": "PASTURE"})


if __name__ == "__main__":
    unittest.main()
