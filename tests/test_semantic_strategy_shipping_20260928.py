from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from report_semantic_strategy_shipping_20260928 import technical_errors,digest


def fixture():
    actions=[[{}]*719,[{}]*719]
    ledger=dict(money=3000,revenue={},spend={})
    row=dict(completed=True,eligible=False,errors=[],ledger_verified=True,
        engine_audit=dict(statuses=['DONE','DONE'],steps=720,final_step=719,
                          act_timeout=1,remaining_overage=[60.,60.]),
        action_sha256=[digest(a) for a in actions],timings=[[0.]*719,[0.]*719],
        cash_by_seat=[3000,3000],daily=[[deepcopy(ledger) for _ in range(31)] for _ in range(2)],
        recorded_rival_audit=dict(material_command_break=True,additional_failed_commands=100),
        final_diagnostics={'0':[dict(executor_errors_cumulative=0)]})
    return row,actions


class ShippingTechnicalValidity(unittest.TestCase):
    def test_script_command_break_alone_is_not_technical_failure(self):
        row,actions=fixture()
        self.assertEqual(technical_errors(row,actions),[])

    def test_fragility_does_not_mask_timeout_or_caught_error(self):
        row,actions=fixture();row['engine_audit']['remaining_overage'][0]=-1
        row['timings'][0][0]=62.
        row['final_diagnostics']['0'][0]['executor_errors_cumulative']=1
        errors=technical_errors(row,actions)
        self.assertIn('engine_overage',errors)
        self.assertIn('measured_runtime',errors)
        self.assertIn('executor_caught_error',errors)

    def test_incomplete_actions_and_ledger_fail(self):
        row,actions=fixture();actions[0].pop()
        row['daily'][1][5]['money']=3001
        errors=technical_errors(row,actions)
        self.assertIn('action_count',errors)
        self.assertIn('action_hash',errors)
        self.assertIn('ledger_arithmetic',errors)


if __name__=='__main__':unittest.main()
