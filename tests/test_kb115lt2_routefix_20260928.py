"""Pure dispatcher invariants; these tests do not import or run the engine."""
import ast
from collections import Counter
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_SHA = '527d4c48b5d6bbef7854d430797e8691858724242d50eeec1e1636665ee124e7'


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'agents' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = load('mgt_lead_kb115lt2')
FIX = load('mgt_lead_kb115lt2_routefix')
CFG = dict(FIX.CFG)


def fixture(hour=2, quantity=4, received=2):
    tiles = [[None] * 10 for _ in range(10)]
    items = [dict(kind='pick', item='WHEAT', n=quantity)]
    for b in (44, 45, 46, 47):
        tiles[b // 10][b % 10] = dict(kind='PASTURE', animal='SHEEP', placed_day=6,
                                     fed_today=False, cared_today=False)
        items.append(dict(kind='stop', tile=b, ops=[['FEED'], ['CARE']], rel=0))
    route = dict(items=items, k=0, sub=0, waited=0, wait={}, done=[])
    tp = dict(day=7, routes={0: route}, cnt=Counter(), log=[], summary={})
    return dict(tp=tp, route=route, tiles=tiles, hour=hour, step=7*24+hour,
                inv={}, shed={'WHEAT': received}, pos=(4, 4), seeds={})


def call(mod, f, **kw):
    d = dict(TP=f['tp'], R=f['route'], u=0, p=f['pos'], inv=f['inv'], tiles=f['tiles'],
             day=7, hour=f['hour'], step=f['step'], seeds_left=f['seeds'], shed_left=f['shed'])
    d.update(kw)
    return mod._tier_cmd(**d)


def next_hour(f, stock=2, inventory=2):
    f['hour'] += 1
    f['step'] += 1
    f['shed'] = {'WHEAT': stock}
    f['inv'] = {'WHEAT': inventory}


class RouteFixTests(unittest.TestCase):
    def setUp(self):
        FIX.CFG.clear(); FIX.CFG.update(CFG)
        FIX.CFG.update(sd_tier_wheat_retry=1, sd_tier_wheat=1, sd_wheat_pick_now=1,
                       sd_tier_fert_opp=0, sd_tier_spawn_remap=0, sd_plan_log=0)

    def test_original_hash_and_unchanged_policy_functions(self):
        path = ROOT / 'agents/mgt_lead_kb115lt2.py'
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), ORIGINAL_SHA)
        trees = [ast.parse((ROOT/'agents'/p).read_text()) for p in
                 ('mgt_lead_kb115lt2.py', 'mgt_lead_kb115lt2_routefix.py')]
        maps = [{n.name: ast.dump(n, include_attributes=False) for n in tree.body
                 if isinstance(n, (ast.FunctionDef, ast.ClassDef))} for tree in trees]
        changed = {name for name in maps[0] if maps[0][name] != maps[1][name]}
        self.assertEqual(changed, {'_tier_cmd', '_tier_override'})
        self.assertEqual(CFG['sd_tier_wheat_retry'], 0)

    def test_off_dispatch_state_is_exactly_original(self):
        FIX.CFG['sd_tier_wheat_retry'] = 0
        BASE.CFG.update({k: v for k, v in FIX.CFG.items() if k in BASE.CFG})
        for stock in (0, 1, 2, 4, 20):
            a = fixture(received=stock); b = deepcopy(a)
            for hour in range(2, 8):
                a['hour'] = b['hour'] = hour; a['step'] = b['step'] = 168+hour
                self.assertEqual(call(BASE, a), call(FIX, b))
                self.assertEqual(a, b)

    def test_partial_retries_residual_once_without_cursor_edit(self):
        f = fixture()
        self.assertEqual(call(FIX, f), ['PICKUP', 'WHEAT', 2])
        self.assertEqual(f['route']['k'], 1)
        next_hour(f)
        items = deepcopy(f['route']['items']); wait = deepcopy(f['route']['wait'])
        self.assertEqual(call(FIX, f), ['PICKUP', 'WHEAT', 2])
        self.assertEqual((f['route']['k'], f['route']['sub']), (1, 0))
        self.assertEqual(f['route']['items'], items)
        self.assertEqual(f['route']['wait'], wait)
        self.assertEqual(f['shed']['WHEAT'], 0)
        self.assertEqual(len(f['route']['done']), 2)
        self.assertNotIn('_wheat_retry_pending', f['route'])
        next_hour(f, stock=20, inventory=4)
        self.assertEqual(call(FIX, f), ['FEED'])
        self.assertEqual(len(f['tp']['_wheat_retry_audit']), 1)

    def test_other_routes_reserve_stock_including_later_unit(self):
        f = fixture(); call(FIX, f); next_hour(f, stock=7)
        other = dict(items=[dict(kind='pick', item='WHEAT', n=6)], k=0, sub=0,
                     waited=0, wait={}, done=[])
        f['tp']['routes'][9] = other
        saved = deepcopy(other)
        self.assertEqual(call(FIX, f), ['PICKUP', 'WHEAT', 1])
        self.assertEqual(other, saved)
        self.assertEqual(f['shed']['WHEAT'], 6)
        self.assertEqual(f['tp']['_wheat_retry_audit'][0]['other_normal_claims'], 6)

    def test_no_same_hour_buy_credit_or_retry_wait(self):
        f = fixture(); call(FIX, f); next_hour(f, stock=0)
        self.assertEqual(call(FIX, f), ['FEED'])
        self.assertEqual(f['tp']['_wheat_retry_audit'][0]['reason'], 'reserved_stock')
        self.assertNotIn('_wheat_retry_pending', f['route'])
        next_hour(f, stock=20, inventory=1)
        self.assertEqual(call(FIX, f), ['CARE'])

    def test_fed_gone_replaced_and_retired_targets_reduce_need(self):
        for mode in ('fed', 'gone', 'replaced', 'retired_false'):
            f = fixture(); call(FIX, f); next_hour(f)
            if mode == 'fed': f['tiles'][4][7]['fed_today'] = True
            if mode == 'gone': f['tiles'][4][7] = None
            if mode == 'replaced': f['tiles'][4][7]['placed_day'] = 7
            if mode == 'retired_false': f['tp']['_wheat_retry_retired'] = {47}
            self.assertEqual(call(FIX, f), ['PICKUP', 'WHEAT', 1], mode)
        f = fixture(); call(FIX, f); next_hour(f)
        f['tp']['_wheat_retry_retired'] = {44, 45, 46, 47}
        FIX._tier_wheat_retry(f['tp'], f['route'], 0, f['pos'], f['inv'], f['tiles'],
                             7, f['hour'], f['step'], f['shed'])
        self.assertEqual(f['tp']['_wheat_retry_audit'][0]['reason'], 'no_demand')

    def test_rejects_unconfirmed_or_changed_checkpoint(self):
        for mode in ('inventory', 'position', 'unit', 'cursor', 'sub', 'day', 'late', 'items', 'route'):
            f = fixture(); call(FIX, f); next_hour(f)
            kw = {}
            if mode == 'inventory': f['inv']['WHEAT'] = 1
            if mode == 'position': f['pos'] = (5, 4)
            if mode == 'unit': kw['u'] = 1
            if mode == 'cursor': f['route']['k'] += 1
            if mode == 'sub': f['route']['sub'] += 1
            if mode == 'day': kw['day'] = 8
            if mode == 'late': f['step'] += 1
            if mode == 'items': f['route']['items'] = deepcopy(f['route']['items'])
            if mode == 'route':
                f['route'] = deepcopy(f['route']); f['tp']['routes'][0] = f['route']
            action = call(FIX, f, **kw)
            self.assertNotEqual(action, ['PICKUP', 'WHEAT', 2], mode)
            self.assertNotIn('_wheat_retry_pending', f['route'])
            self.assertIn(f['tp']['_wheat_retry_audit'][0]['reason'], ('changed', 'unconfirmed'))

    def test_zero_and_full_pickups_never_create_checkpoint(self):
        for stock in (0, 4):
            f = fixture(received=stock)
            if stock == 0: f['route']['waited'] = 2
            call(FIX, f)
            self.assertNotIn('_wheat_retry_pending', f['route'])

    def test_hard_scope_and_required_accounting(self):
        for day in (5, 11, 29):
            f = fixture(); call(FIX, f, day=day)
            self.assertNotIn('_wheat_retry_pending', f['route'])
        for flag in ('sd_wheat_pick_now', 'sd_tier_fert_opp'):
            f = fixture(); call(FIX, f); next_hour(f)
            FIX.CFG[flag] = 0 if flag == 'sd_wheat_pick_now' else 1
            call(FIX, f)
            self.assertEqual(f['tp']['_wheat_retry_audit'][0]['reason'], 'scope')
            FIX.CFG[flag] = 1 if flag == 'sd_wheat_pick_now' else 0

    def test_ambiguous_wheat_harvest_and_drop_do_not_retry(self):
        for command in (['DROP'], ['DELIVER'], ['PLACE_HARVEST', 'WHEAT'], ['HARVEST']):
            f = fixture()
            f['route']['items'].insert(2, dict(kind='stop', tile=34, ops=[command]))
            f['tiles'][3][4] = dict(kind='PLANT', crop='WHEAT', planted_day=4, yield_units=6)
            call(FIX, f)
            self.assertNotIn('_wheat_retry_pending', f['route'])

    def test_next_normal_wheat_pickup_caps_segment_demand(self):
        f = fixture()
        f['route']['items'].insert(3, dict(kind='pick', item='WHEAT', n=2))
        call(FIX, f); next_hour(f, stock=20)
        call(FIX, f)
        self.assertEqual(f['tp']['_wheat_retry_audit'][0]['reason'], 'no_demand')

    def test_time_guard_counts_restored_feeds_and_terminal_work(self):
        f = fixture(hour=12); call(FIX, f); next_hour(f)
        # 1 pickup + 8 operations + 3 moves from H13 needs 12 slots: reject.
        call(FIX, f)
        self.assertEqual(f['tp']['_wheat_retry_audit'][0]['reason'], 'no_time')
        f = fixture(hour=11); call(FIX, f); next_hour(f)
        self.assertEqual(call(FIX, f), ['PICKUP', 'WHEAT', 2])
        self.assertEqual(f['tp']['_wheat_retry_audit'][0]['finish_hour_exclusive'], 24)
        f = fixture(hour=11)
        f['route']['items'].append(dict(kind='stop', tile=47, ops=[['WATER']]))
        call(FIX, f); next_hour(f); call(FIX, f)
        self.assertEqual(f['tp']['_wheat_retry_audit'][0]['reason'], 'no_time')

    def test_full_override_retirement_and_market_debit(self):
        f = fixture(quantity=3, received=1)
        f['route']['items'] = f['route']['items'][:4]
        state = dict(tier=f['tp'], _xretire={47: False})
        old = FIX._sd_state
        FIX._sd_state = lambda state: {'st': {}}
        try:
            def override():
                actions = [['PASS'], ['PASS']]
                FIX._tier_override(state, {}, f['step'], 7, f['hour'], f['tiles'],
                    [(4, 4), (5, 4)], [f['inv'], {}], actions, {}, f['shed'])
                return actions
            override()
            next_hour(f, stock=10, inventory=1)
            f['tp']['routes'][1] = dict(items=[dict(kind='pick', item='WHEAT', n=8)],
                                        k=0, sub=0, waited=0, wait={}, done=[])
            actions = override()
            self.assertEqual(actions, [['PICKUP', 'WHEAT', 2], ['PICKUP', 'WHEAT', 8]])
            self.assertEqual(f['tp']['_picked_now'], (f['step'], {'WHEAT': 10}))
            self.assertEqual(f['tp']['_wheat_retry_retired'], {47})
        finally:
            FIX._sd_state = old

    def check_saved_checkpoint(self, case):
        saved = json.loads((ROOT/f'tests/fixtures/kb115lt2_routefix_{case}.json').read_text())
        routes = {int(u): r for u, r in saved['routes'].items()}
        for route in routes.values():
            route['wait'] = {ast.literal_eval(k): v for k, v in route['wait'].items()}
        route = routes[saved['unit']]
        pending = route['_wheat_retry_pending']
        pending['route_id'] = id(route); pending['items_id'] = id(route['items'])
        pending['position'] = tuple(pending['position'])
        pending['targets'] = {int(b): tuple(v) for b, v in pending['targets'].items()}
        tp = dict(routes=routes, cnt=Counter(), log=[], _wheat_retry_retired=saved['retirements'])
        out = FIX._tier_wheat_retry(tp, route, saved['unit'], tuple(saved['position']),
            saved['inventory'], saved['tiles'], saved['day'], saved['hour'], saved['step'], saved['shed'])
        expected = (['PICKUP', 'WHEAT', saved['expected']['quantity']]
                    if saved['expected']['reason'] == 'picked' else None)
        self.assertEqual(out, expected)
        self.assertEqual(tp['_wheat_retry_audit'][0], saved['expected'])

    def test_saved_live07_actual_checkpoint_remains_eligible(self):
        self.check_saved_checkpoint('live07')

    def test_saved_live04_actual_checkpoint_protects_terminal_water(self):
        self.check_saved_checkpoint('live04')

    def test_saved_live06_actual_checkpoint_protects_sheep_placement(self):
        self.check_saved_checkpoint('live06')


if __name__ == '__main__':
    unittest.main()
