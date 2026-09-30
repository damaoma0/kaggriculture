"""Input and handoff contracts; no game or live opponent is executed."""
import ast
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import semantic_strategy_oracle_gate_20260928 as O


class OracleContracts(unittest.TestCase):
    def test_prefix_and_private_handoff_are_both_required(self):
        row={"handoff_observation_sha256":{"0":"a","1":"b"}}
        actions=[[{"farmer":["PASS"]} for _ in range(719)] for _ in range(2)]
        self.assertTrue(O.prefix_parity(row,row,actions,actions))
        changed=deepcopy(actions);changed[1][143]={"farmer":["MOVE","N"]}
        self.assertFalse(O.prefix_parity(row,row,changed,actions))
        self.assertFalse(O.prefix_parity({}, {},actions,actions))
        changedrow=deepcopy(row);changedrow["handoff_observation_sha256"]["0"]="different_private"
        self.assertFalse(O.prefix_parity(changedrow,row,actions,actions))

    def test_selection_does_not_depend_on_input_order(self):
        episodes=[str(x) for x in range(40)]
        self.assertEqual(O.ordered_episodes(episodes),O.ordered_episodes(reversed(episodes)))

    def test_prepared_pair_has_only_observed_prefix_sales(self):
        study=ROOT/"results/fresh/semantic_strategy_20260928"
        directory,manifest=O.verify(study,"d6_exact_vs_retile_locked_v4")
        exact=O.G.read(directory/"exact_plans.json")
        retile=O.G.read(directory/"retile_plans.json")
        self.assertEqual(len(exact),8)
        for ep in exact:
            self.assertEqual(len(exact[ep]["cum_sold"]),6)
            self.assertEqual(exact[ep]["cum_sold"],retile[ep]["cum_sold"])
            self.assertEqual(exact[ep]["hands"],retile[ep]["hands"])
            self.assertEqual(exact[ep]["board"][:7],retile[ep]["board"][:7])
            self.assertEqual(exact[ep]["land_day"],retile[ep]["land_day"])
            self.assertEqual(O.placement_violations(retile[ep]),[])
            self.assertEqual(retile[ep]["planner_metadata"]["warnings"],[])
        self.assertEqual(manifest["options"],{"reactive_land_unlock":True,"early_financing":{"enabled":True}})

    def test_hooks_are_exact_frozen_v4_implementation(self):
        prefix=ROOT/"results/fresh/semantic_strategy_20260928/candidates/strategy_v4_modern4_finance/project"
        source=ast.parse((prefix/"agents/semantic_strategy_20260928.py").read_text())
        hooks=ast.parse((ROOT/O.HOOKS).read_text())
        functions={n.name:n for n in source.body if isinstance(n,ast.FunctionDef)}
        for node in hooks.body:
            if isinstance(node,ast.FunctionDef):
                self.assertEqual(ast.dump(node),ast.dump(functions[node.name]))


if __name__=="__main__":
    unittest.main()
