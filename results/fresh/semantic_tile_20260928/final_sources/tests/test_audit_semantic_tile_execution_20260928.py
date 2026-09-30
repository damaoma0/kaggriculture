from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import audit_semantic_tile_execution_20260928 as A


def empty_plan(n=6):
    return {"n": n, "plant": [{} for _ in range(n)], "board": [[" ."] * 100 for _ in range(n)],
            "struct_by_day": [{} for _ in range(n)], "animals_by_day": [{} for _ in range(n)],
            "hands": [1] * n, "planner_metadata": {"handoff_day": 1}}


def empty_days(n=6):
    return [{"board_list": ["EMPTY"] * 100, "plants": [], "hires": []} for _ in range(n)]


class ExecutionAuditTests(unittest.TestCase):
    def test_plan_label_disambiguates_empty_coop_from_cow(self):
        plan = empty_plan()
        plan["board"][1][0] = plan["board"][1][1] = "co"
        plan["struct_by_day"][0] = {"0": "COOP", "1": "PASTURE"}
        plan["animals_by_day"][0] = {"1": "COW"}
        self.assertEqual(A.planned_board(plan, 1)[:2], ["S_COOP", "COW"])

    def test_exact_day_planting_claims_its_cohort_before_older_missed_cohort(self):
        plan, days = empty_plan(), empty_days()
        plan["plant"][1] = {"0": "WHEAT"}
        plan["plant"][3] = {"0": "WHEAT"}
        plan["plant"][2] = {"2": "CARROT"}
        days[3]["plants"] = [[0, "WHEAT"], [2, "CARROT"]]
        result = A.event_matches(plan, days, handoff=1)
        self.assertEqual((result["on_time"], result["late"], result["unmatched_planned"]), (1, 1, 1))
        self.assertEqual(result["unmatched_planned_events"][0]["day"], 1)
        self.assertEqual(result["late_events"][0]["delay"], 1)

    def test_intended_animal_exit_is_distinct_from_outside_plan_exit(self):
        plan, days = empty_plan(), empty_days()
        for d in (0, 1):
            plan["animals_by_day"][d] = {"0": "COW"}
        for d in (1, 2):
            days[d]["board_list"][0] = "COW"
            days[d]["board_list"][1] = "SHEEP"
        days[3]["board_list"][0] = days[3]["board_list"][1] = "S_PASTURE"
        result = A.retirement_audit(plan, days, handoff=1)
        self.assertEqual(result["classification_counts"], {"planned_same_day": 1, "outside_tile_plan": 1})
        self.assertEqual(result["missing_after_first_unfed_day"], [])
        self.assertIn("not itself proof", result["interpretation"])

    def test_overflow_and_harvest_are_reported_as_measured_units(self):
        ledger = {"days": empty_days(), "final": 100, "opp_final": 80}
        ledger["days"][1].update(harv={"WHEAT": 6}, overflow={"WHEAT": 2}, eff={"HARVEST": 1, "PICKUP": 1},
                                 rev={"WHEAT": 50}, spend={"BUY_SEED:WHEAT": 10}, hires=[0, 1], move=3)
        result = A.metrics(ledger, handoff=1)
        self.assertEqual(result["harvested_units"], 6)
        self.assertEqual(result["deleted_units"], 2)
        self.assertEqual(result["effective_farm_operations"], 1)
        self.assertEqual(result["effective_nonmovement_actions"], 2)
        self.assertEqual(result["hires"], 2)
        self.assertNotIn("production", result)


if __name__ == "__main__":
    unittest.main()
