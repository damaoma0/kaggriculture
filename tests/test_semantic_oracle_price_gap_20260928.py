"""Check the accounting audit's engine-timing and attribution identities."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from audit_semantic_oracle_price_gap_20260928 import attribution, potential_night


class PriceGapAuditTest(unittest.TestCase):
    def test_same_quantities_have_only_realized_price_component(self):
        row = attribution(5, 100, 5, 150)
        self.assertEqual(row['matched_daily_average_price_component'], 50)
        self.assertEqual(row['matched_daily_volume_component'], 0)
        self.assertEqual(row['unmatched_sale_day_revenue'], 0)

    def test_absent_sale_price_is_not_invented(self):
        row = attribution(0, 0, 5, 150)
        self.assertIsNone(row['native_average_price'])
        self.assertEqual(row['matched_daily_average_price_component'], 0)
        self.assertEqual(row['unmatched_sale_day_revenue'], 150)

    def test_strawberry_has_four_productions_two_days_apart(self):
        plant = dict(crop='STRAWBERRY', planted_day=2, consecutive_unwatered=0, fertilized_until_day=30)
        nights = [d for d in range(11, 22) if potential_night([plant], [plant], d)[(0, 'crop', 'STRAWBERRY', 2)]['production']]
        self.assertEqual(nights, [11, 13, 15, 17])

    def test_cow_uses_prior_bank_only_when_fed_at_production(self):
        before = dict(animal='COW', placed_day=2, pending_care_bonus=5, consecutive_unfed=0)
        after = dict(before, pending_care_bonus=1)
        fed = potential_night([before], [after], 9)[(0, 'animal', 'COW', 2)]
        self.assertEqual(fed['total'], 6)
        after.update(consecutive_unfed=1, pending_care_bonus=0)
        unfed = potential_night([before], [after], 9)[(0, 'animal', 'COW', 2)]
        self.assertEqual(unfed['total'], 1)
        self.assertEqual(unfed['unfed_production_lost_bank'], 5)


if __name__ == '__main__':
    unittest.main()
