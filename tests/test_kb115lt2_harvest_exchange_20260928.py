"""Pure optional-harvest exchange invariants; no environment or game calls."""
import ast
from collections import Counter
from copy import deepcopy
import hashlib
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = '5c2dfb70eaf68e1b415fe14fd6414774b467afa81b4f66f9d170e792e0dfe833'


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'agents'/(name+'.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


BASE = load('mgt_lead_kb115lt2_routefix_fast')
EX = load('mgt_lead_kb115lt2_harvestx')
CFG = dict(EX.CFG)


def fixture():
    tiles = [[None]*10 for _ in range(10)]
    tiles[4][4] = dict(kind='PLANT', crop='WHEAT', planted_day=16, watered_today=False,
                       consecutive_unwatered=1, yield_units=1)
    tiles[4][5] = dict(kind='PASTURE', animal='COW', placed_day=6, yield_units=0,
                       fertilizer_available=True, consecutive_unfed=0, pending_care_bonus=0)
    tiles[4][6] = dict(kind='PASTURE', animal='SHEEP', placed_day=6, yield_units=4,
                       fertilizer_available=False, consecutive_unfed=0, pending_care_bonus=0)
    stops = [dict(tile=44, rel=0, ops=[EX._tier_op(['WATER'], True, 100, 2)]),
             dict(tile=45, rel=0, ops=[EX._tier_op(['COLLECT_FERTILIZER'], False, 10, 4)]),
             dict(tile=46, rel=0, ops=[EX._tier_op(['FEED'], True, 100, 2)])]
    segs = [dict(u=0, kind='out', p0=44, t0=0, fpick=0, ver=0, stops=stops)]
    rest = [dict(tile=46, rel=0, ops=[EX._tier_op(['HARVEST'], False, 120, 4)], v=120)]
    S = dict(_tier_prices={'WOOL':100., 'MILK':40., 'FERTILIZER':10., 'WHEAT':30.}, _tier_last_day=29)
    st = dict(_dump_day={'left':1, 'deferred':0}, _harvest_exchange_blocked={'day':18, 'tiles':[]})
    return S, segs, rest, tiles, 18, st


def ops(args, mandatory=False):
    return Counter((x['tile'], tuple(o['c'])) for sg in args[1] for x in sg['stops']
                   for o in x['ops'] if not mandatory or o['m'])


class HarvestExchangeTests(unittest.TestCase):
    def setUp(self):
        EX.CFG.clear(); EX.CFG.update(CFG)
        EX.CFG.update(sd_polish=0, sd_polish_final=1, sd_polish_harvest_exchange=1,
                      sd_polish_water_c=20., sd_tier_anim_harv=1, sd_tier_turnaround=1,
                      sd_tier_copy_returns=0, sd_wheat_fert_mand=0)
        EX._TIER_WY.clear()

    def run_exchange(self, args):
        EX._tier_polish(*args)
        return args[-1]['_polish_day']['harvest_exchange']

    def test_source_hash_scope_and_default_off(self):
        path = ROOT/'agents/mgt_lead_kb115lt2_routefix_fast.py'
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), BASE_SHA)
        def defs(p):
            return {n.name:ast.dump(n, include_attributes=False) for n in ast.parse(p.read_text()).body
                    if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        old, new = defs(path), defs(ROOT/'agents/mgt_lead_kb115lt2_harvestx.py')
        self.assertEqual({n for n in old if old[n] != new[n]}, {'_tier_deliver', '_tier_polish'})
        self.assertEqual(set(new)-set(old), {'_tier_harvest_exchange'})
        self.assertEqual(CFG['sd_polish_harvest_exchange'], 0)

    def test_off_exact_polish_and_delivery_parity(self):
        EX.CFG['sd_polish_harvest_exchange'] = 0
        BASE.CFG.update({k:v for k,v in EX.CFG.items() if k in BASE.CFG})
        for count in (0, 80):
            EX.CFG['sd_polish'] = BASE.CFG['sd_polish'] = count
            a, b = fixture(), fixture()
            EX._tier_polish(*a); BASE._tier_polish(*b)
            self.assertEqual(a, b)
            EX._tier_deliver(a[0], a[1], a[3], a[4], a[5])
            BASE._tier_deliver(b[0], b[1], b[3], b[4], b[5])
            self.assertEqual(a, b)

    def test_one_profitable_same_visit_exchange_preserves_mandatory(self):
        a = fixture(); before = deepcopy(a)
        d = self.run_exchange(a)
        self.assertTrue(d['accepted'])
        self.assertEqual((d['tile'], d['removed_tile'], d['removed_command']), (46, 45, ['COLLECT_FERTILIZER']))
        self.assertAlmostEqual(d['score_gain'], 110.)
        self.assertEqual(d['planned_receipt'], 'automatic_midnight')
        self.assertEqual(ops(a, True), ops(before, True))
        self.assertEqual(ops(a)[(46, ('HARVEST',))], 1)
        self.assertFalse(any(o['c'][0]=='HARVEST' for bd in a[2] for o in bd['ops']))
        self.assertEqual(a[0]['_harvest_exchange_committed_day'], 18)
        d2 = self.run_exchange(a)
        self.assertEqual(d2['reason'], 'not_final_or_already_committed')

    def test_cap_is_hard_and_deterministic(self):
        EX.CFG['sd_polish_harvest_exchange_cap'] = 1
        a, b = fixture(), fixture()
        a[1][0]['stops'][1]['ops'].append(EX._tier_op(['CARE'], False, 40, 4))
        b = deepcopy(a)
        da, db = self.run_exchange(a), self.run_exchange(b)
        self.assertEqual(da, db); self.assertEqual(da['examined'], 1)
        self.assertEqual(a, b)
        self.assertLessEqual(da['examined'], da['cap'])

    def test_capacity_and_fertilizer_supply_are_hard_constraints(self):
        a = fixture(); a[-1]['_dump_day']['left'] = 100
        d = self.run_exchange(a)
        self.assertFalse(d['accepted']); self.assertGreater(d['rejected'].get('midnight_capacity', 0), 0)
        a = fixture()
        a[1][0]['stops'].append(dict(tile=44, rel=0, ops=[EX._tier_op(['FERTILIZE'], True, 20, 2)]))
        d = self.run_exchange(a)
        self.assertFalse(d['accepted']); self.assertGreater(d['rejected'].get('time_or_supply', 0), 0)

    def test_strict_positive_gain_and_finish_before_midnight(self):
        a = fixture(); a[2][0]['ops'][0]['v'] = 1.
        self.assertFalse(self.run_exchange(a)['accepted'])
        a = fixture(); a[1][0]['t0'] = 22
        d = self.run_exchange(a)
        self.assertFalse(d['accepted'])
        self.assertGreater(d['rejected'].get('time_or_supply', 0), 0)

    def test_retirement_false_blocked_tile_and_unknown_deferral_reject(self):
        for case in ('retired', 'blocked', 'unknown'):
            a = fixture()
            if case == 'retired': a[0]['_xretire'] = {46:False}
            if case == 'blocked': a[-1]['_harvest_exchange_blocked']['tiles'] = [46]
            if case == 'unknown':
                del a[-1]['_harvest_exchange_blocked']; a[-1]['_dump_day']['deferred'] = 4
            before = deepcopy(a[1:3]); d = self.run_exchange(a)
            self.assertFalse(d['accepted'], case)
            self.assertEqual(a[1:3], before)

    def test_existing_harvest_and_feed_and_first_visit_are_protected(self):
        a = fixture(); a[1][0]['stops'][2]['ops'].append(EX._tier_op(['HARVEST'], False, 120, 4))
        before = ops(a); d = self.run_exchange(a)
        self.assertFalse(d['accepted']); self.assertEqual(ops(a), before)
        a = fixture(); a[1][0]['stops'][1]['ops'] = [EX._tier_op(['FEED'], False, 10, 4)]
        self.assertFalse(self.run_exchange(a)['accepted'])
        a = fixture(); a[1][0]['stops'] = a[1][0]['stops'][1:]
        self.assertFalse(self.run_exchange(a)['accepted'])

    def test_new_product_cannot_bypass_fixed_generic_delivery(self):
        a = fixture()
        a[1][0]['stops'].append(dict(tile=44, rel=0, turn=True,
            ops=[EX._tier_op(['DELIVER'], True, 0, 2)]))
        d = self.run_exchange(a)
        self.assertFalse(d['accepted'])
        self.assertGreater(d['rejected'].get('new_delivery_product', 0), 0)

    def test_paired_named_delivery_never_assumes_free_daytime_shed_room(self):
        a = fixture(); a[2][0]['ops'].append(EX._tier_op(['PLACE_HARVEST', 'WOOL'], False, 1, 4))
        self.assertFalse(self.run_exchange(a)['accepted'])
        a = fixture(); a[3][4][4] = deepcopy(a[3][4][6]); a[2][0]['tile'] = 44
        a[1][0]['stops'][0]['ops'] = [EX._tier_op(['FEED'], True, 100, 2)]
        a[2][0]['ops'].append(EX._tier_op(['PLACE_HARVEST', 'WOOL'], False, 1, 4))
        before = deepcopy(a[1:3])
        d = self.run_exchange(a)
        self.assertFalse(d['accepted'])
        self.assertGreater(d['rejected'].get('daytime_capacity_unverified', 0), 0)
        self.assertEqual(a[1:3], before)

    def test_existing_drop_cannot_hide_extra_daytime_shed_load(self):
        for command in (['DROP'], ['DELIVER'], ['DELIVER', 'WOOL'], ['PLACE_HARVEST', 'WOOL']):
            a = fixture()
            a[1][0]['stops'].append(dict(tile=44, rel=0, deliver=True,
                ops=[EX._tier_op(command, True, 0, 2)]))
            before = deepcopy(a[1:3])
            d = self.run_exchange(a)
            self.assertFalse(d['accepted'])
            self.assertGreater(d['rejected'].get('daytime_capacity_unverified', 0), 0)
            self.assertEqual(a[1:3], before)

    def test_delivery_removed_harvest_is_recorded_and_never_resurrected(self):
        a = fixture(); a[1][0]['stops'][2]['ops'].append(EX._tier_op(['HARVEST'], False, 120, 4))
        EX.CFG.update(sd_tier_turnaround=0, sd_tier_dump_defer=1, sd_tier_dump_defer_cap=1,
                      sd_tier_deliver_skip=0)
        EX._tier_deliver(a[0], a[1], a[3], a[4], a[5])
        self.assertIn(46, a[-1]['_harvest_exchange_blocked']['tiles'])
        self.assertEqual(ops(a)[(46, ('HARVEST',))], 0)
        self.assertFalse(self.run_exchange(a)['accepted'])


if __name__ == '__main__': unittest.main()
