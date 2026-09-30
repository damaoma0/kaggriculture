"""Check the narrow revision's isolation, reset and scenario boundaries."""
from copy import deepcopy
import gzip
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[1]


class TapeVariantTests(unittest.TestCase):
    def setUp(self):
        self.spec=json.loads((ROOT/'data/tape_variants/109740300-milk-care-to-wool-v1.json').read_text(encoding='utf8'))
        p=next((ROOT/'data/mg_tapes').glob('*/109740300.json.gz'))
        with gzip.open(p,'rt',encoding='utf8') as f:
            self.original=json.load(f)['actions']
        # Deliberately shared action dictionaries, just like the compressed
        # production library. One tape's revision must not corrupt another.
        routes={0:list(self.original),1:list(self.original)}
        chassis=SimpleNamespace(routes={k:list(v) for k,v in routes.items()},router=lambda obs,t,s:s.get('route',0))
        self.ns={'_MGT_IMPL':SimpleNamespace(chassis=chassis),'_MGT_ROUTES':routes,
                 '_MGT_TAPES':[{'ep':109740300},{'ep':123456789}]}
        source=(ROOT/'scripts/fragments/tape_variant_care.py').read_text(encoding='utf8')
        exec(compile(source.replace('__TAPE_VARIANT_SPEC__',repr(self.spec)),str(p),'exec'),self.ns)
        tiles=[[None for _ in range(10)] for _ in range(10)]
        tiles[4][4]={'animal':'COW','placed_day':0}
        tiles[4][3]={'animal':'SHEEP','placed_day':0,'pending_care_bonus':0}
        self.obs={'player':0,'farms':[{'tiles':tiles}],
                  'market':{'prices':{'MILK':9,'WOOL':37}},'town':{'unlocked_shops':['YARN_STORE']}}

    def call(self,day=17,route=0):
        return self.ns['_tv_router'](self.obs,day*24,{'route':route})

    def test_copy_on_write_keeps_all_other_tapes_and_source_actions_unchanged(self):
        pristine=deepcopy(self.original)
        self.assertEqual(self.call(),0)
        self.assertEqual(self.ns['_TV_REPORT']['decisions'][-1]['reason'],'applied')
        revised=self.ns['_MGT_ROUTES'][0]
        self.assertEqual([i for i,(a,b) in enumerate(zip(pristine,revised)) if a!=b],
                         [17*24+h for h in (1,2,3,4)])
        self.assertEqual(self.ns['_MGT_ROUTES'][1],pristine)
        self.assertEqual(self.original,pristine)
        self.assertIs(revised,self.ns['_MGT_IMPL'].chassis.routes[0])

    def test_reset_restores_original_before_a_second_game(self):
        self.call()
        self.ns['_tv_router'](self.obs,0,{})
        self.assertEqual(self.ns['_MGT_ROUTES'][0],self.original)
        self.assertEqual(self.ns['_TV_REPORT']['decisions'],[])

    def test_other_donor_never_receives_revision(self):
        self.call(route=1)
        self.assertEqual(self.ns['_MGT_ROUTES'][0],self.original)
        self.assertEqual(self.ns['_TV_REPORT']['decisions'],[])

    def test_original_no_yarn_scenario_is_unchanged(self):
        self.obs['town']['unlocked_shops']=[]
        self.call()
        self.assertEqual(self.ns['_MGT_ROUTES'][0],self.original)
        self.assertEqual(self.ns['_TV_REPORT']['decisions'][-1]['reason'],'no_revealed_yarn_store')

    def test_high_milk_price_keeps_cow_care(self):
        self.obs['market']['prices']={'MILK':100,'WOOL':200}
        self.call()
        self.assertEqual(self.ns['_MGT_ROUTES'][0],self.original)
        self.assertEqual(self.ns['_TV_REPORT']['decisions'][-1]['reason'],'price_condition')

    def test_replaced_sheep_cohort_is_not_mistaken_for_original(self):
        self.obs['farms'][0]['tiles'][4][3]['placed_day']=8
        self.call()
        self.assertEqual(self.ns['_MGT_ROUTES'][0],self.original)

    def test_retirement_rejects_late_care_even_when_wool_is_expensive(self):
        self.obs['market']['prices']={'MILK':1,'WOOL':240}
        self.call(day=23)
        self.assertEqual(self.ns['_MGT_ROUTES'][0],self.original)
        self.assertEqual(self.ns['_TV_REPORT']['decisions'][-1]['reason'],'retirement_before_harvest')


if __name__=='__main__':
    unittest.main()
