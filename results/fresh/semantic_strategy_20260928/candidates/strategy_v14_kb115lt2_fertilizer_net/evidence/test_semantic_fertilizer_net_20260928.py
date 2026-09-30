import copy
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import semantic_strategy_policy_20260928 as P
import semantic_strategy_fertilizer_net_20260928 as F


def config(on=True):
    return dict(P.DEFAULT_CONFIG,forecast_fertilizer_net=on)


def calendar(sp,birth=0,day=0,details=None,**more):
    c=dict(crop=sp,birth=birth,count=1);c.update(more)
    return F.crop_input_calendar([c],day,P.DEFAULT_CONFIG['release_age'],P.CROPS,details)


def state(day=6):
    return dict(day=day,shops_prefix=[],own_crop_cohorts=[],rival_crop_cohorts=[],
        own_animal_cohorts=[],rival_animal_cohorts=[],stock={},market_params={},
        inventory={p:10000 for p in P.PRODUCTS})


class FertilizerCalendarTests(unittest.TestCase):
    def test_annual_targets_require_exact_minimum_inputs(self):
        for sp,total,date in [('WHEAT',1,2),('CARROT',1,2),('MELON',0,None)]:
            cal,audit=calendar(sp)
            self.assertEqual(sum(cal.values()),total)
            if date is not None:self.assertEqual(cal[date],1)
            self.assertEqual(sum(x.get('unachievable_units_under_current_yield',0) for x in audit),0)

    def test_ongoing_service_precedes_production_and_packs_effect(self):
        for sp,dates in [('TOMATO',[7,10]),('STRAWBERRY',[9,13])]:
            cal,_=calendar(sp)
            self.assertEqual({d:v for d,v in cal.items() if v},{d:.65 for d in dates})

    def test_fresh_yield_and_active_fertilizer_are_credited(self):
        for y,expiry in [(4,-1),(3,3),(6,-1)]:
            detail=dict(crop='WHEAT',birth=0,observation_day=3,yield_units=y,
                        fertilized_until_day=expiry,watered_today=False)
            cal,_=calendar('WHEAT',day=3,details=[detail],observation_day=3,ready_count=1)
            self.assertEqual(sum(cal.values()),0)

    def test_deferred_annual_input_can_support_next_day_target(self):
        detail=dict(crop='WHEAT',birth=0,observation_day=3,yield_units=3,
                    fertilized_until_day=-1,watered_today=False)
        cal,audit=calendar('WHEAT',day=3,details=[detail],observation_day=3,ready_count=0)
        self.assertEqual(cal[3],1);self.assertEqual(audit[0]['harvest'],4)
        self.assertEqual(audit[0]['unachievable_units_under_current_yield'],0)

    def test_ongoing_active_effect_replaces_existing_application(self):
        detail=dict(crop='STRAWBERRY',birth=0,observation_day=9,yield_units=0,
                    fertilized_until_day=11,watered_today=False)
        cal,_=calendar('STRAWBERRY',day=9,details=[detail])
        self.assertEqual({d:v for d,v in cal.items() if v},{13:.65})

    def test_no_use_after_release_or_for_future_public_detail(self):
        self.assertEqual(sum(calendar('WHEAT',day=5)[0].values()),0)
        poison=dict(crop='WHEAT',birth=0,observation_day=1,yield_units=999,fertilized_until_day=99)
        self.assertEqual(calendar('WHEAT')[0],calendar('WHEAT',details=[poison])[0])
        old=dict(crop='WHEAT',birth=-5,observation_day=0,yield_units=6,fertilized_until_day=2)
        self.assertEqual(calendar('WHEAT')[0],calendar('WHEAT',details=[old])[0])

    def test_stale_yield_is_ignored_and_effect_credit_stays_with_birth(self):
        stale=dict(crop='WHEAT',birth=0,observation_day=0,yield_units=99,
                   fertilized_until_day=-1,watered_today=True)
        self.assertEqual(calendar('WHEAT',day=1)[0],calendar('WHEAT',day=1,details=[stale])[0])
        predecessor=dict(crop='WHEAT',birth=0,observation_day=3,yield_units=6,
                         fertilized_until_day=5,watered_today=True)
        # Replacement at birth3 must still buy its own fertilizer at day5.
        replacement,_=calendar('WHEAT',birth=3,day=4,details=[predecessor])
        self.assertEqual(replacement,calendar('WHEAT',birth=3,day=4)[0])
        self.assertEqual(replacement[5],1)
        surviving=dict(crop='TOMATO',birth=0,observation_day=6,yield_units=0,
                       fertilized_until_day=8,watered_today=False)
        credited,_=calendar('TOMATO',day=7,details=[surviving])
        self.assertEqual({d:n for d,n in credited.items() if n},{9:.65})

    def test_own_stock_credit_never_credits_rival_or_reuses_inventory(self):
        rows=F.market_input_debits({6:1,7:2},{6:2,7:1},2)
        self.assertEqual(rows[6]['market_debit'],2)
        self.assertEqual(rows[7]['market_debit'],2)
        self.assertEqual(rows[7]['remaining_own_stock'],0)
        self.assertEqual(sum(r['own_stock_credit'] for r in rows.values()),2)

    def test_both_farms_inventory_identity_and_other_goods_unchanged(self):
        s=state();s['own_crop_cohorts']=[dict(crop='WHEAT',birth=6,count=1)]
        s['rival_crop_cohorts']=[dict(crop='CARROT',birth=6,count=1)];s['stock']['FERTILIZER']=1
        off,_=P.forecast_market(s,config(False));on,rival=P.forecast_market(s,config())
        for d in on:
            self.assertAlmostEqual(on[d]['FERTILIZER']-off[d]['FERTILIZER'],-int(d>=8))
            for p in P.PRODUCTS:
                if p!='FERTILIZER':self.assertEqual(on[d][p],off[d][p])
        self.assertEqual(rival[8]['FERTILIZER'],-1)

    def test_harvest_blend_is_gross_and_debited_once(self):
        s=state();s['rival_crop_cohorts']=[dict(crop='WHEAT',birth=6,count=1)]
        hist=dict(rival_net_daily={'FERTILIZER':2},rival_flow_kind='harvest')
        _,rival=P.forecast_market(s,config(),hist)
        self.assertAlmostEqual(rival[8]['FERTILIZER'],.3*2-1)

    def test_signed_net_blend_does_not_double_debit_observed_fraction(self):
        s=state();s['rival_crop_cohorts']=[dict(crop='WHEAT',birth=6,count=1)]
        hist=dict(rival_net_daily={'FERTILIZER':-2},rival_flow_kind='market_net')
        _,rival=P.forecast_market(s,config(),hist)
        self.assertAlmostEqual(rival[8]['FERTILIZER'],-.3*2-.7)
        self.assertAlmostEqual(rival[7]['FERTILIZER'],-.3*2)

    def test_ambiguous_blend_is_rejected_only_when_enabled(self):
        s=state();hist=dict(rival_net_daily={'FERTILIZER':2})
        P.forecast_market(s,config(False),hist)
        with self.assertRaisesRegex(ValueError,'explicit_rival_flow_kind'):
            P.forecast_market(s,config(),hist)

    def test_scalar_marginal_cost_uses_same_calendar(self):
        s=state(0);paths,rival=P.forecast_market(s,config(False))
        for sp in P.CROPS:
            old=P.cohort_value(s,sp,paths,rival,config(False))
            new=P.cohort_value(s,sp,paths,rival,config())
            cal,_=calendar(sp);rule=P.CROPS[sp]
            actual=sum(n*P.market_price('FERTILIZER',paths[d]['FERTILIZER']) for d,n in cal.items())
            legacy=sum(.4*P.market_price('FERTILIZER',paths[d]['FERTILIZER']) for d in range(30)
                if d<=rule['last'] and rule['interval'] and d+1>=rule['first'] and (d+1-rule['first'])%rule['interval']==0)
            self.assertAlmostEqual(new-old,legacy-actual)

    def test_added_crop_changes_market_by_its_calendar(self):
        s=state(0);base,_=P.forecast_market(s,config())
        for sp in P.CROPS:
            added=copy.deepcopy(s);added['own_crop_cohorts']=[dict(crop=sp,birth=0,count=1)]
            paths,_=P.forecast_market(added,config());cal,_=calendar(sp);used=0
            for d in paths:
                used+=cal[d]
                self.assertAlmostEqual(paths[d]['FERTILIZER']-base[d]['FERTILIZER'],-used)


if __name__=='__main__':unittest.main()
