"""Differential tests against the untouched KB115LT2 route evaluator."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import random
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build_kb115lt2_eval_fast_20260928 import transform


class EvalFastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / 'agents/mgt_lead_kb115lt2_routefix_fast.py'
        spec = importlib.util.spec_from_file_location('_eval_fast_test', path)
        cls.kb = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.kb
        exec(compile(transform(path.read_text(encoding='utf-8')), str(path), 'exec'), cls.kb.__dict__)
        cls.kb._TIER_D = [[abs(i//10-j//10)+abs(i%10-j%10) for j in range(100)] for i in range(100)]
        cls.kb._TIER_SHED_I = {44, 45, 54, 55}

    def test_varied_routes_equal_with_and_without_hours(self):
        kb = self.kb
        rng = random.Random(280926)
        commands = [['FEED'], ['CARE'], ['HARVEST'], ['PLACE_HARVEST'],
                    ['FERTILIZE'], ['WATER'], ['COLLECT_FERTILIZER'],
                    ['PLACE','COW'], ['PLACE','SHEEP'], ['PLACE','GOOSE'],
                    ['PLACE','WOOL',0], ['PLANT','WHEAT']]
        for trial in range(2500):
            kb.CFG['sd_tier_eval_fast'] = 1
            kb.CFG['sd_wheat_fert_mand'] = trial % 2
            kb._TIER_WY = {i:rng.randrange(1,7) for i in rng.sample(range(100), 20)} if trial%3 else {}
            n = rng.randrange(9)
            dawn = rng.randrange(n+1)
            stops = [dict(tile=rng.randrange(100), rel=rng.randrange(30), dawn=i<dawn,
                          ops=[dict(c=deepcopy(rng.choice(commands)), m=bool(rng.randrange(2)))
                               for _ in range(rng.randrange(6))]) for i in range(n)]
            seg = dict(p0=rng.randrange(100), t0=rng.randrange(5), stops=stops,
                       hold0=bool(trial%2), fpick=rng.randrange(4), goose_ready=rng.randrange(6))
            before = deepcopy(seg)
            expected = kb._tier_eval_reference(seg)
            self.assertEqual(expected, kb._tier_eval(seg), trial)
            self.assertEqual(expected, kb._tier_eval(seg, stops), trial)
            self.assertEqual(kb._tier_eval_reference(seg, want_hours=True),
                             kb._tier_eval(seg, want_hours=True), trial)
            self.assertEqual(before, seg)

    def test_disabled_reference_and_changed_globals_are_respected(self):
        kb = self.kb
        seg = dict(p0=44,t0=0,hold0=True,stops=[dict(tile=34,rel=0,ops=[
            dict(c=['HARVEST'],m=True),dict(c=['FEED'],m=True),dict(c=['FERTILIZE'],m=True)])])
        for fast in (0,1):
            kb.CFG['sd_tier_eval_fast'] = fast
            for mandatory in (0,1):
                kb.CFG['sd_wheat_fert_mand'] = mandatory
                for wheat in ({}, {34:6}):
                    kb._TIER_WY = wheat
                    self.assertEqual(kb._tier_eval_reference(seg), kb._tier_eval(seg))


if __name__ == '__main__':
    unittest.main()
