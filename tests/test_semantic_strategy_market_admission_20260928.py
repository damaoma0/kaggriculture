from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import semantic_strategy_policy_20260928 as P
import semantic_strategy_market_admission_20260928 as G
from semantic_strategy_blocks_20260928 import SemanticBlockPolicy
from test_semantic_strategy_blocks_20260928 import model,obs,OUTPUTS


def target(n=2):
    return dict(plant_counts={'WHEAT':3},animal_add_counts={'COW':n},
                animal_retire_counts={'SHEEP':1},end_animal_counts={'COW':4+n,'SHEEP':2})


def negative(*args,**kwargs):
    return [dict(rival_supply_scale=1.,future_demand_scale=1.,margin=-700.)]


class MarketAdmissionTests(unittest.TestCase):
    def state(self,day=15):return P.public_state(obs(day))
    def config(self,**kw):return dict(P.DEFAULT_CONFIG,animal_market_gate=True,**kw)

    def test_default_off_and_hard_time_and_unit_bounds(self):
        t=target();s=self.state(11);admitted={'animal_add_counts':{'COW':2}}
        with patch.object(G,'scenario_margins',side_effect=negative) as value:
            self.assertEqual(G.gate_unbought_animals(s,t,admitted,P.DEFAULT_CONFIG)[0],t)
            self.assertEqual(G.gate_unbought_animals(s,t,admitted,self.config(animal_market_start_day=6))[0],t)
            value.assert_not_called()
            s['day']=15
            result,diag=G.gate_unbought_animals(s,t,admitted,self.config(animal_market_max_units=99))
        self.assertEqual(result['animal_add_counts'],{'COW':1})
        self.assertEqual(diag['withheld'],{'COW':1})
        self.assertEqual(result['plant_counts'],t['plant_counts'])
        self.assertEqual(result['animal_retire_counts'],t['animal_retire_counts'])

    def test_shed_and_carried_purchases_are_protected(self):
        o=obs(15);o['private']['shed']={'COW':1};o['private']['inventories']=[{'COW':1}]
        s=P.public_state(o);t=target();before=deepcopy((s,t))
        with patch.object(G,'scenario_margins',side_effect=AssertionError('held animal valued')):
            result,diag=G.gate_unbought_animals(s,t,{'animal_add_counts':{'COW':2}},self.config())
        self.assertEqual(result,t);self.assertEqual(diag['withheld'],{})
        self.assertEqual((s,t),before)

    def test_any_optimistic_scenario_above_buffer_preserves_unit(self):
        outcomes=negative()+[dict(rival_supply_scale=.5,future_demand_scale=1.5,margin=-299.)]
        with patch.object(G,'scenario_margins',return_value=outcomes):
            result,diag=G.gate_unbought_animals(self.state(),target(),{'animal_add_counts':{'COW':2}},self.config())
        self.assertEqual(result,target());self.assertEqual(diag['withheld'],{})

    def test_withheld_work_remains_in_budget_and_only_observed_births_complete_it(self):
        m=model();idx=OUTPUTS.index('COW');b=m['blocks']['12'];b['coef'][0][idx]=3
        for i in range(3):b['shares'][i][idx]=int(i==0)
        p=SemanticBlockPolicy(m,self.config(forecast=False))
        with patch.object(G,'scenario_margins',side_effect=negative):
            a=p.propose(obs(12));b=p.propose(obs(13),a['memory'])
            c=p.propose(obs(14,animals=[('COW',12,2)]),b['memory'])
        self.assertEqual(a['today']['animal_add_counts'],{'COW':2})
        self.assertEqual(b['today']['animal_add_counts'],{'COW':2})
        self.assertEqual(a['memory']['block_strategy']['totals']['COW'],3)
        self.assertEqual(b['diagnostics']['completed']['animal'],{})
        self.assertEqual(c['diagnostics']['completed']['animal'],{'COW':2})
        self.assertEqual(c['today']['animal_add_counts'],{})
        self.assertEqual(c['diagnostics']['requested']['animal_add_counts'],{'COW':1})

    def test_public_supply_and_prices_change_scores_but_identity_future_do_not(self):
        s=self.state(15);cfg=self.config();a=G.scenario_margins(s,'COW',cfg)
        glut=deepcopy(s);glut['inventory']['MILK']+=1000
        self.assertLess(max(x['margin'] for x in G.scenario_margins(glut,'COW',cfg)),max(x['margin'] for x in a))
        rival=deepcopy(s);rival['rival_animal_cohorts']=[{'species':'COW','birth':0,'count':20}]
        self.assertNotEqual(a,G.scenario_margins(rival,'COW',cfg))
        s.update(episode=12345,actual_future_shops=['YARN_STORE']*8,rival_private={'MILK':1000})
        self.assertEqual(a,G.scenario_margins(s,'COW',cfg))

    def test_default_matches_frozen_v6(self):
        path=ROOT/'results/fresh/semantic_strategy_20260928/candidates/strategy_v6_blocks100_recovery/project/scripts/semantic_strategy_blocks_20260928.py'
        spec=importlib.util.spec_from_file_location('frozen_block_no_gate',path)
        frozen=importlib.util.module_from_spec(spec);spec.loader.exec_module(frozen)
        current=SemanticBlockPolicy(model(),{'forecast':True})
        old=frozen.SemanticBlockPolicy(model(),{'forecast':True})
        self.assertEqual(current.propose(obs(6)),old.propose(obs(6)))


if __name__=='__main__':unittest.main()
