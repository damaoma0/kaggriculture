from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import semantic_strategy_policy_20260928 as P
import semantic_strategy_persistent_value_20260928 as V


class PersistentValueTests(unittest.TestCase):
    def test_price_effect_on_later_rival_sale_without_new_own_supply(self):
        paths = {d: {'MILK': 10000} for d in range(3)}
        extra = {0: {'MILK': 10}}
        rival = {2: {'MILK': 30}}
        corrected, detail = V.receipts(paths, extra, {}, rival)
        old, _ = V.receipts(paths, extra, {}, rival, persistent=False)
        expected = 30*(P.market_price('MILK', 10000)-P.market_price('MILK', 10010))
        self.assertGreater(expected, 0)
        self.assertEqual(corrected-old, expected)
        self.assertEqual(detail[2]['added_receipts'], 0)
        self.assertEqual(detail[2]['existing_sales_margin'], expected)

    def test_later_own_sale_has_opposite_effect_and_symmetric_farms_cancel(self):
        paths = {d: {'MILK': 10000} for d in range(3)}
        extra = {0: {'MILK': 10}}
        future = {2: {'MILK': 30}}
        neutral, _ = V.receipts(paths, extra, {}, {})
        rival, _ = V.receipts(paths, extra, {}, future)
        own, _ = V.receipts(paths, extra, future, {})
        symmetric, _ = V.receipts(paths, extra, future, future)
        self.assertEqual(rival-neutral, neutral-own)
        self.assertEqual(neutral, symmetric)

    def test_no_double_count_and_first_day_unchanged(self):
        paths = {d: {'MILK': 10000} for d in range(3)}
        extra = {0: {'MILK': 10}, 1: {'MILK': 10}}
        rival = {d: {'MILK': 30} for d in range(3)}
        before = deepcopy((paths, extra, rival))
        _, rows = V.receipts(paths, extra, {}, rival)
        _, old = V.receipts(paths, extra, {}, rival, persistent=False)
        self.assertEqual(rows[0], old[0])
        self.assertEqual(rows[1]['existing_sales_margin'],
                         30*(P.market_price('MILK',10000)-P.market_price('MILK',10020)))
        self.assertEqual(rows[2]['existing_sales_margin'], rows[1]['existing_sales_margin'])
        self.assertEqual(before, (paths, extra, rival))

    def test_no_sales_and_no_externality_matches_legacy_costs(self):
        state = dict(day=12, own_crop_cohorts=[], own_animal_cohorts=[], market_params={})
        cfg = deepcopy(P.DEFAULT_CONFIG)
        paths = {d: {p:10000 for p in P.PRODUCTS} for d in range(12,30)}
        rival = {d:{} for d in paths}
        for species in (*P.CROPS, *P.ANIMALS):
            self.assertAlmostEqual(V.cohort_value(state,species,paths,rival,cfg),
                                   P.cohort_value(state,species,paths,rival,cfg))

    def test_single_cohort_bundle_equals_corrected_unit(self):
        state = dict(day=12, own_crop_cohorts=[], own_animal_cohorts=[], market_params={})
        cfg = deepcopy(P.DEFAULT_CONFIG)
        paths = {d: {p:10000 for p in P.PRODUCTS} for d in range(12,30)}
        rival = {d:{'MILK':10} for d in paths}
        value = V.cohort_value(state,'COW',paths,rival,cfg)
        choice = dict(plant_counts={},animal_add_counts={'COW':1})
        self.assertAlmostEqual(V.bundle_value(state,choice,paths,rival,cfg,{'COW':value}),value)


if __name__ == '__main__':
    unittest.main()
