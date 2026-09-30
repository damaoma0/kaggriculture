"""Execution recovery must preserve commitments and ignore unrelated events."""
from copy import deepcopy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

ENTRY = Path(__file__).resolve().parents[1] / 'agents/semantic_strategy_20260928.py'
spec = importlib.util.spec_from_file_location('strategy_recovery_test', ENTRY)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def state(events, retirements=None):
    lower = dict(routes={2:[46,25]},walk={2:'EAST'},lastP=object(),first_of_day=False)
    executor = dict(tier=dict(day=7,log=events),assign={2:46},walk={2:'EAST'},
                    _xretire=retirements or {},done={(6,35)},sold={'WOOL':18},
                    smap={25:25},pmap={(7,16):16})
    kb = SimpleNamespace(_S=executor,CFG={'sd_tier':1},_sd_state=lambda unused:lower)
    return dict(kb=kb,config={'reactive_stock_shortfall':True},daily_diagnostic={}),lower


class RecoveryTests(unittest.TestCase):
    def test_partial_wheat_rebuilds_routes_without_erasing_completed_work(self):
        s,lower=state([[169,2,'pick_short',44,'WHEAT 2/5']])
        before={k:deepcopy(s['kb']._S[k]) for k in ('done','sold','smap','pmap','_xretire')}
        module._stock_execution(s,{'step':170},7,2)
        self.assertEqual(s['kb'].CFG['sd_tier'],0)
        self.assertFalse(lower['routes']);self.assertIsNone(lower['lastP'])
        self.assertTrue(lower['first_of_day'])
        self.assertEqual(before,{k:s['kb']._S[k] for k in before})
        self.assertEqual(s['daily_diagnostic']['execution_recovery'][0]['reason'],'incomplete_wheat_pickup')

    def test_deliberate_retirement_defers_recovery_including_false_tonight_flag(self):
        s,_=state([[169,2,'pick_short',44,'WHEAT 2/5']],{25:False})
        original=s['kb']._S['tier']
        module._stock_execution(s,{'step':170},7,2)
        self.assertEqual(s['kb'].CFG['sd_tier'],1)
        self.assertIs(s['kb']._S['tier'],original)
        self.assertEqual(s['daily_diagnostic']['stock_recovery_deferred'][0]['retirements'],[25])

    def test_stale_other_product_disabled_or_already_rolling_does_not_trigger(self):
        for event in [[168,2,'pick_short',44,'WHEAT 2/5'],[169,2,'pick_short',44,'COW 1/2']]:
            s,_=state([event]);module._stock_execution(s,{'step':170},7,2)
            self.assertEqual(s['kb'].CFG['sd_tier'],1)
        for key in ('disabled','already'):
            s,_=state([[169,2,'pick_none',44,'WHEAT']])
            if key=='disabled':s['config']['reactive_stock_shortfall']=False
            else:s['execution_switched']=True
            module._stock_execution(s,{'step':170},7,2)
            self.assertEqual(s['kb'].CFG['sd_tier'],1)

    def test_window_and_newly_admitted_retirement_are_protected(self):
        for day in (5,11,20):
            s,_=state([[day*24+1,2,'pick_short',44,'WHEAT 2/5']])
            s['kb']._S['tier']['day']=day
            module._stock_execution(s,{'step':day*24+2},day,2)
            self.assertEqual(s['kb'].CFG['sd_tier'],1)
        s,_=state([[169,2,'pick_short',44,'WHEAT 2/5']])
        s['daily_diagnostic']['retirements']=[{'tile':25,'animal':'COW'}]
        module._stock_execution(s,{'step':170},7,2)
        self.assertEqual(s['kb'].CFG['sd_tier'],1)

    def test_land_recovery_also_preserves_existing_retirement(self):
        s,_=state([],{25:False})
        s['config']['reactive_land_unlock']=True;s['morning_land']=2
        module._unlock_execution(s,{'player':0,'farms':[{'unlocked_quadrants':['NW','NE','SW']}]},9,6)
        self.assertEqual(s['kb'].CFG['sd_tier'],1)
        self.assertNotIn('observed_land_unlock',s['daily_diagnostic'])


if __name__=='__main__':unittest.main()
