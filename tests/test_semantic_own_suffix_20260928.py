import copy
from collections import Counter
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import semantic_strategy_policy_20260928 as P
from semantic_strategy_own_suffix_20260928 import own_suffix_calendar


def state(day=6):
    return dict(day=day,own_crop_cohorts=[],own_animal_cohorts=[],own_structures={},
                owned_quadrants=4,stock={})


def run(s,rows):
    return own_suffix_calendar(s,rows,P.DEFAULT_CONFIG,P.CROPS,P.ANIMALS,P.output_calendar)


class OwnSuffixTests(unittest.TestCase):
    def test_forecast_includes_today_and_rejects_repeated_days(self):
        for rows in ([],[dict(day=7)],[dict(day=6),dict(day=6)]):
            with self.assertRaises(ValueError):run(state(),rows)

    def test_initial_deferred_receipt_preserved_once_with_replacement(self):
        s=state(3);s['own_crop_cohorts']=[dict(crop='WHEAT',birth=0,count=2,
                                             observation_day=3,ready_count=1)]
        s['own_fertilizer_crop_details']=[dict(crop='WHEAT',birth=0,observation_day=3,
            yield_units=y,fertilized_until_day=-1,watered_today=False,count=1) for y in (4,3)]
        out=run(s,[dict(day=3,plant_counts={'WHEAT':1})]);daily=out['daily']
        self.assertEqual(daily[3]['gross_output']['WHEAT'],5)
        self.assertEqual(daily[4]['gross_output']['WHEAT'],6)
        self.assertEqual(daily[6]['gross_output']['WHEAT'],5)
        self.assertEqual(sum(d['gross_output'].get('WHEAT',0) for d in daily.values()),16)
        self.assertEqual(daily[3]['crop_end_counts']['WHEAT'],2)
        self.assertEqual(daily[4]['crop_end_counts']['WHEAT'],1)
        self.assertEqual(daily[3]['internal_use']['FERTILIZER'],1)
        self.assertEqual(daily[5]['internal_use']['FERTILIZER'],1)
        flag=next(w for w in out['warnings'] if w['kind'].startswith('origin_dated_receipt'))
        self.assertEqual((flag['preserved_units'],flag['legacy_recomputed_units']),(6,0))

    def test_planned_replacement_cannot_use_predecessor_effect(self):
        s=state(3);s['own_crop_cohorts']=[dict(crop='WHEAT',birth=0,count=1,observation_day=3,ready_count=1)]
        s['own_fertilizer_crop_details']=[dict(crop='WHEAT',birth=0,observation_day=3,
            yield_units=5,fertilized_until_day=5,watered_today=False)]
        out=run(s,[dict(day=3,plant_counts={'WHEAT':1})])
        self.assertEqual(out['daily'][3]['internal_use']['FERTILIZER'],0)
        self.assertEqual(out['daily'][5]['internal_use']['FERTILIZER'],1)

    def test_ongoing_final_yield_precedes_replacement_without_duplication(self):
        s=state(10);s['own_crop_cohorts']=[dict(crop='TOMATO',birth=0,count=1)]
        out=run(s,[dict(day=10),dict(day=12,plant_counts={'TOMATO':1})]);daily=out['daily']
        self.assertAlmostEqual(daily[11]['gross_output']['TOMATO'],1.65)
        self.assertEqual(daily[12]['gross_output'].get('TOMATO',0),0)
        self.assertEqual(daily[12]['crop_release_counts']['TOMATO'],1)
        self.assertEqual(daily[12]['crop_end_counts']['TOMATO'],1)
        self.assertAlmostEqual(sum(d['gross_output'].get('TOMATO',0) for d in daily.values()),9.9)
        self.assertAlmostEqual(sum(d['internal_use']['FERTILIZER'] for d in daily.values()),1.95)

    def test_retirement_keeps_occupied_pen_two_nights_and_new_animal_feeds_today(self):
        s=state();s['own_animal_cohorts']=[dict(species='COW',birth=-2,count=1)]
        s['own_structures']={'PASTURE':2}
        out=run(s,[dict(day=6,animal_retire_counts={'COW':1},animal_add_counts={'COW':1})]);daily=out['daily']
        self.assertEqual(daily[6]['gross_output']['MILK'],6)
        self.assertEqual(daily[6]['animal_occupied_counts']['COW'],2)
        self.assertEqual(daily[7]['animal_occupied_counts']['COW'],2)
        self.assertEqual(daily[8]['animal_occupied_counts']['COW'],1)
        self.assertEqual(daily[6]['internal_use']['WHEAT'],1)
        self.assertTrue(any(w['kind']=='legacy_fertilizer_after_retirement_intent' for w in out['warnings']))

    def test_repeated_retirement_splits_only_remaining_active_count(self):
        s=state();s['own_animal_cohorts']=[dict(species='SHEEP',birth=0,count=3)]
        out=run(s,[dict(day=6,animal_retire_counts={'SHEEP':1}),dict(day=7,animal_retire_counts={'SHEEP':2})])
        self.assertEqual(sum(n['count'] for n in out['animal_cohorts']),3)
        self.assertEqual(out['daily'][8]['animal_occupied_counts']['SHEEP'],2)
        self.assertEqual(out['daily'][9]['animal_occupied_counts'].get('SHEEP',0),0)
        with self.assertRaisesRegex(ValueError,'exceeds_active'):
            run(s,[dict(day=6,animal_retire_counts={'SHEEP':2}),dict(day=7,animal_retire_counts={'SHEEP':2})])

    def test_existing_commitment_is_not_reissued_or_inferred_from_hunger(self):
        s=state();s['own_animal_cohorts']=[dict(species='COW',birth=0,count=2,consecutive_unfed=1)]
        ordinary=run(s,[dict(day=6)])
        self.assertEqual(ordinary['daily'][6]['internal_use']['WHEAT'],2)
        s['committed_retirement_counts']={'COW':1}
        out=run(s,[dict(day=6),dict(day=7,animal_retire_counts={'COW':1})])
        self.assertEqual(out['daily'][6]['internal_use']['WHEAT'],1)
        self.assertEqual(out['daily'][7]['retiring_occupied_counts']['COW'],2)
        self.assertEqual(out['daily'][9]['animal_occupied_counts'].get('COW',0),0)

    def test_initial_stock_credited_once_for_own_inputs_only(self):
        s=state();s['own_animal_cohorts']=[dict(species='GOOSE',birth=0,count=2)]
        s['stock']={'WHEAT':2,'FERTILIZER':1}
        out=run(s,[dict(day=6,plant_counts={'WHEAT':1})]);daily=out['daily']
        self.assertEqual(daily[6]['signed_net_flow']['WHEAT'],0)
        self.assertEqual(daily[7]['signed_net_flow']['WHEAT'],-2)
        self.assertEqual(daily[8]['initial_stock_credit']['FERTILIZER'],1)
        for p in ('WHEAT','FERTILIZER'):
            self.assertEqual(sum(d['initial_stock_credit'][p] for d in daily.values()),s['stock'][p])
            for d in daily.values():
                self.assertAlmostEqual(d['signed_net_flow'][p],d['gross_output'].get(p,0)
                    -d['internal_use'][p]+d['initial_stock_credit'][p])

    def test_outputs_are_sum_of_unique_cohort_calendars(self):
        s=state();s['own_crop_cohorts']=[dict(crop='CARROT',birth=4,count=2)]
        s['own_animal_cohorts']=[dict(species='GOOSE',birth=0,count=3)]
        out=run(s,[dict(day=6),dict(day=7,plant_counts={'CARROT':2},animal_retire_counts={'GOOSE':1}),
                   dict(day=10,plant_counts={'CARROT':2})])
        for d,row in out['daily'].items():
            total=Counter()
            for node in out['crop_cohorts']+out['animal_cohorts']:total.update(node['output'].get(d,{}))
            self.assertEqual(dict(total),row['gross_output'])
            inputs=sum(n['fertilizer_inputs'].get(d,0) for n in out['crop_cohorts'])
            self.assertEqual(inputs,row['internal_use']['FERTILIZER'])

    def test_retirement_does_not_release_a_pen_before_exit_or_remove_structure(self):
        s=state();s.update(owned_quadrants=1,own_structures={'PASTURE':1},
            own_crop_cohorts=[dict(crop='STRAWBERRY',birth=0,count=24)],
            own_animal_cohorts=[dict(species='COW',birth=0,count=1)])
        out=run(s,[dict(day=6,animal_retire_counts={'COW':1}),
            dict(day=8,remove_structure_counts={'PASTURE':1},plant_counts={'WHEAT':1})])
        self.assertEqual(out['daily'][7]['structures']['PASTURE'],1)
        self.assertEqual(out['daily'][7]['retiring_occupied_counts']['COW'],1)
        self.assertEqual(out['daily'][8]['crop_end_counts']['WHEAT'],1)
        self.assertFalse(any(w['kind'] in ('modeled_end_occupancy_exceeds_land','modeled_animals_exceed_structures') for w in out['warnings']))

    def test_no_inputs_mutated_or_rival_future_fields_read(self):
        s=state();rows=[dict(day=6,plant_counts={'CARROT':1},future_shops=['POISON'])]
        before=copy.deepcopy((s,rows));expected=run(s,rows)
        s.update(rival_crop_cohorts=[{'bad':'private'}],rival_private={'FERTILIZER':999},
                 future_observations=[{'prices':999}],episode=123,future_shops=['SECRET'])
        self.assertEqual(run(s,rows),expected)
        self.assertEqual(rows,before[1])
        for key,value in before[0].items():self.assertEqual(s[key],value)

    def test_overdue_crop_and_final_day_feed_keep_legacy_assumptions(self):
        s=state(29);s['own_crop_cohorts']=[dict(crop='WHEAT',birth=20,count=1)]
        s['own_animal_cohorts']=[dict(species='GOOSE',birth=20,count=1)]
        out=run(s,[dict(day=29)])
        self.assertEqual(out['daily'][29]['gross_output'].get('WHEAT',0),0)
        self.assertEqual(out['daily'][29]['internal_use']['WHEAT'],0)
        self.assertTrue(any(w['kind'].startswith('overdue_observed_crop') for w in out['warnings']))

    def test_sparse_plan_does_not_reset_new_land_or_repeat_jobs(self):
        s=state();s['owned_quadrants']=1
        out=run(s,[dict(day=6,target_land_count=2,plant_counts={'WHEAT':1}),dict(day=9)])
        self.assertEqual(out['daily'][9]['land'],2)
        self.assertEqual(len(out['crop_cohorts']),1)

    def test_ambiguous_initial_cohorts_and_explicit_removals_rejected(self):
        s=state();s['own_crop_cohorts']=[dict(crop='WHEAT',birth=5,count=1)]*2
        with self.assertRaisesRegex(ValueError,'duplicate_initial'):run(s,[dict(day=6)])
        with self.assertRaisesRegex(ValueError,'crop_removal'):run(state(),[dict(day=6,crop_remove_counts={'WHEAT':1})])


if __name__=='__main__':unittest.main()
