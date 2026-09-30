"""Critical boundaries for the research tape-value planner."""
from copy import deepcopy
import unittest

import research_labour_profit as R
import value_tape_search as V
from value_tape_policies import cohort_policy


class ValueTapeSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sim=R.Simulator(dict(seed=73013,seat=0,episode=0,shops=[[] for _ in range(31)]))
        cls.state,cls.env=sim.initial,sim.env

    def test_independent_official_engine_matches_full_day(self):
        live=deepcopy(self.state)
        isolated=deepcopy(self.state)
        agent=V.fresh_agent()
        for t in range(24):
            for states in (live,isolated):
                for seat in range(2):
                    states[seat].observation.step=t
            action=agent(deepcopy(live[0].observation))
            for states in (live,isolated):
                states[0].action=deepcopy(action)
                states[1].action=deepcopy(R.PASS)
            R.engine().interpreter(live,deepcopy(self.env))
            V.isolated_engine().interpreter(isolated,deepcopy(self.env))
            self.assertEqual(live,isolated,t)

    def test_memory_clone_reproduces_actions_across_day_boundary(self):
        live=deepcopy(self.state)
        parent=V.fresh_agent()
        for t in range(25):
            for seat in range(2):
                live[seat].observation.step=t
            obs=deepcopy(live[0].observation)
            clone=V.fresh_agent(V.memory_of(parent)) if t in (0,12,23,24) else None
            left=parent(deepcopy(obs))
            if clone is not None:
                right=clone(deepcopy(obs))
                self.assertEqual(left,right,t)
            live[0].action=left
            live[1].action=deepcopy(R.PASS)
            R.engine().interpreter(live,deepcopy(self.env))

    def test_scenario_future_preserves_revealed_prefix_and_uses_replacement(self):
        obs=deepcopy(self.state[0].observation)
        obs.day=12
        obs.step=288
        obs.town.unlocked_shops=['YARN_STORE']*4
        first=V.future_shops(obs,0)
        self.assertEqual(first[12],['YARN_STORE']*4)
        self.assertEqual(first[14],first[12])
        self.assertEqual(len(first[15]),5)
        self.assertEqual(len(first[24]),8)
        self.assertEqual(first[29],first[24])
        self.assertEqual(first,V.future_shops(deepcopy(obs),0))
        self.assertEqual(obs.town.unlocked_shops,['YARN_STORE']*4)

    def test_asset_identity_includes_birth_day(self):
        farm={'tiles':[[{'kind':'PLANT','crop':'STRAWBERRY','planted_day':3},
                        {'kind':'PASTURE','animal':'SHEEP','placed_day':6}]]}
        changed=deepcopy(farm)
        changed['tiles'][0][0]['planted_day']=12
        self.assertNotEqual(V.asset_keys(farm),V.asset_keys(changed))

    def test_cohort_policy_values_feed_changes_but_rejects_asset_loss(self):
        base=dict(route=None,episode=1,minimum_margin=0,cash_deltas=[0],risk_score=0,protection_failures=[])
        candidate=dict(route=0,episode=2,minimum_margin=800,cash_deltas=[1000],risk_score=900,
                       protection_failures=[{'lost_feed_actions':1}])
        decision=dict(selected=None,candidates=[base,candidate])
        self.assertEqual(cohort_policy(decision)[0],0)
        self.assertIsNone(decision['selected'])
        candidate['protection_failures'].append({'assets':[[0,0,'SHEEP',6]]})
        self.assertIsNone(cohort_policy(decision)[0])


if __name__=='__main__':
    unittest.main()
