import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import semantic_tile_polish_20260928 as P


def fixture():
    boards=[[" ."]*100 for _ in range(5)]
    for d in range(2,5):
        boards[d][0]="WH"
    for d in range(3,5):
        boards[d][99]="TO"
    return dict(n=5,plant=[{}, {"0":"WHEAT"}, {"99":"TOMATO"}, {}, {}],
                events=[[1,0,"WHEAT"],[2,99,"TOMATO"]],board=boards,
                struct_by_day=[{} for _ in range(5)],animals_by_day=[{} for _ in range(5)],
                harv_tiles=[[],[],[],[0],[]],removals=[[],[],[],[],[[99,"TOMATO",2]]],
                hands=[2]*5,land_day={"NE":0,"SW":0,"SE":0},cum_sold=[{}],
                planner_metadata=dict(handoff_day=1,warnings=[],daily=[]))


class SuffixPolishTests(unittest.TestCase):
    def test_nonempty_boundary_cannot_be_transplanted(self):
        with self.assertRaisesRegex(ValueError,"empty"):
            P.swap_suffix(fixture(),2,0,44)

    def test_suffix_transform_preserves_counts_and_is_its_own_inverse(self):
        plan=fixture(); original=copy.deepcopy(plan)
        signature=P._signature(plan)
        P.swap_suffix(plan,1,0,44)
        self.assertEqual(plan["plant"][1],{"44":"WHEAT"})
        self.assertEqual(plan["events"][0],[1,44,"WHEAT"])
        self.assertEqual(plan["harv_tiles"][3],[44])
        self.assertEqual(plan["board"][0],original["board"][0])
        self.assertEqual(P._signature(plan),signature)
        P.swap_suffix(plan,1,0,44)
        self.assertEqual(plan,original)

    def test_polish_keeps_input_and_reports_recomputed_route_score(self):
        plan=fixture(); before=copy.deepcopy(plan)
        out,audit=P.polish_plan(plan,rounds=2,finalists=16)
        self.assertEqual(plan,before)
        self.assertEqual(P._signature(plan),P._signature(out))
        work=P.work_calendar(out)
        recomputed=sum(P.route_cost(work[d],out["hands"][d]) for d in range(1,5))
        self.assertAlmostEqual(audit["final_surrogate"],recomputed)
        self.assertLessEqual(audit["final_surrogate"],audit["initial_surrogate"])


if __name__=="__main__":
    unittest.main()
