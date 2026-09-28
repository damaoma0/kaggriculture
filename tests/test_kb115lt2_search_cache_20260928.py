"""Search cache must preserve routes, objective and all consumed random draws."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import random
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from build_kb115lt2_search_cache_20260928 import transform


class SearchCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT/'agents/mgt_lead_kb115lt2_eval_fast.py'
        spec = importlib.util.spec_from_file_location('_search_cache_test', path)
        cls.kb = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.kb
        exec(compile(transform(path.read_text(encoding='utf-8')), str(path), 'exec'),cls.kb.__dict__)
        cls.kb._TIER_D = [[abs(i//10-j//10)+abs(i%10-j%10) for j in range(100)] for i in range(100)]
        cls.kb._TIER_SHED_I = {44,45,54,55}
        cls.kb._TIER_ANG = [cls.kb._tier_math.atan2(i//10-4.5,i%10-4.5) for i in range(100)]

    def test_fixed_iteration_search_and_rng_parity(self):
        kb = self.kb
        for seed in range(12):
            rng = random.Random(seed)
            kb._TIER_WY = {34:3} if seed%2 else {}
            kb.CFG['sd_wheat_fert_mand'] = seed%2
            kb.CFG['sd_tier_iters'] = 400
            kb.CFG['sd_tier_rot_all'] = seed%2
            kb.CFG['sd_tier_swap_oropt'] = seed%3==0
            stops = [dict(tile=i,rel=rng.randrange(6),ops=[dict(c=[rng.choice(
                     ['FEED','WATER','HARVEST','CARE','FERTILIZE','COLLECT_FERTILIZER'])],m=True)])
                     for i in rng.sample(range(100),16)]
            segs = [dict(u=i,kind='out' if i<3 else 'post',p0=p,t0=i%3,stops=[],wu=1.,
                         anim=[34,35],fneed={34},hold0=i==0) for i,p in enumerate([44,45,54,55])]
            before = deepcopy((segs,stops))
            results = []
            for enabled in (0,1):
                kb.CFG['sd_tier_search_cache'] = enabled
                rng2 = random.Random(seed+100)
                result = kb._tier_search(segs,stops,60.,rng2)
                results.append((result,rng2.getstate()))
            self.assertEqual(results[0],results[1],seed)
            self.assertEqual(before,(segs,stops))


if __name__ == '__main__':
    unittest.main()
