from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from semantic_strategy_blocks_20260928 import SemanticBlockPolicy
from semantic_strategy_labor_20260928 import apply_early_hands_bonus
from test_semantic_strategy_blocks_20260928 import model,obs


class EarlyHandsTests(unittest.TestCase):
    def proposal(self,day,hands=11):
        return dict(day=day,hands=hands,plant_counts={'WHEAT':4},animal_add_counts={'SHEEP':1},
                    animal_retire_counts={'COW':1},estimated_capital_cost=530.)

    def test_off_hard_window_and_count_cap(self):
        p=[self.proposal(d) for d in range(5,12)];before=deepcopy(p)
        self.assertEqual(apply_early_hands_bonus(p,{})[0],p)
        result,diag=apply_early_hands_bonus(p,{'early_hands_bonus':10})
        self.assertEqual([r['hands'] for r in result],[11,12,12,12,12,12,11])
        self.assertEqual(p,before)
        for a,b in zip(p,result):
            self.assertEqual({k:v for k,v in a.items() if k!='hands'},{k:v for k,v in b.items() if k!='hands'})

    def test_existing_cap_and_lower_configured_cap(self):
        result,_=apply_early_hands_bonus([self.proposal(10,14)],{'early_hands_bonus':1})
        self.assertEqual(result[0]['hands'],14)
        result,_=apply_early_hands_bonus([self.proposal(10,11)],{'early_hands_bonus':1,'max_hands':11})
        self.assertEqual(result[0]['hands'],11)

    def test_wages_and_funding_gap_are_explicit_not_assumed_affordable(self):
        _,diag=apply_early_hands_bonus([self.proposal(10,11)],{'early_hands_bonus':1},100.)
        t=diag['today'];self.assertEqual(t['incremental_wages'],144)
        self.assertFalse(t['cash_covers_added_wage_only'])
        self.assertEqual(t['cash_gap_for_capital_and_wages'],530+376-100)

    def test_integration_preserves_all_quantity_forecasts_and_memory(self):
        base=SemanticBlockPolicy(model(),{'forecast':True})
        plus=SemanticBlockPolicy(model(),{'forecast':True,'early_hands_bonus':1})
        a=base.propose(obs(6));b=plus.propose(obs(6))
        self.assertEqual(a['memory'],b['memory'])
        self.assertEqual(a['diagnostics'],{k:v for k,v in b['diagnostics'].items() if k!='early_hands'})
        for before,after in zip(a['forecast'],b['forecast']):
            self.assertEqual({k:v for k,v in before.items() if k!='hands'},
                             {k:v for k,v in after.items() if k!='hands'})
        self.assertEqual(b['today'],b['forecast'][0])


if __name__=='__main__':unittest.main()
