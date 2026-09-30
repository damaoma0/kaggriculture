"""Information boundaries and engine equivalence of the follow-up planner."""
from collections import Counter
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

import audit_value_forecast_components as A
import rival_trajectory_model as M2
import rival_trajectory_model_v3 as M3
import value_tape_search as V
import value_tape_search_v2 as V2
import value_tape_search_v3 as V3
import value_tape_search_v4 as V4


class FollowupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        context=A.context('wool')
        cls.obs,cls.memory=context['observation'],context['memory']

    def test_no_target_or_test_episode_in_model(self):
        old=json.loads((M2.LIBRARY/'manifest.json').read_text(encoding='utf-8'))
        modern=json.loads((M3.MODERN/'manifest.json').read_text(encoding='utf-8'))
        prohibited={r['episode'] for m in (old,modern) for r in m['games'] if r['split']=='test'}|set(modern['excluded'])
        used={r['episode'] for r in M3.training_library()}
        self.assertEqual(len(used),115)
        self.assertFalse(used & prohibited)

    def test_rival_forecast_uses_public_inputs_and_does_not_mutate_them(self):
        obs=deepcopy(self.obs);before=deepcopy(obs)
        first=M3.world(obs,3)
        self.assertEqual(obs,before)
        # Rival predictions must not depend on our private resources or on
        # accidentally added episode/future labels in an offline harness.
        obs['private']={'shed':{'STRAWBERRY':1000000},'seeds':{},'inventories':[]}
        obs['seed']=981212;obs['future_shops']=['YARN_STORE']*8
        self.assertEqual(first,M3.world(obs,3))

    def test_stratified_shops_have_correct_marginals_and_known_prefix(self):
        obs=deepcopy(self.obs);scenarios=[M2.scenario_shops(obs,i) for i in range(8)]
        known=list(obs['town']['unlocked_shops'])
        for world in scenarios:
            for d,shops in world.items():self.assertEqual(shops[:len(known)],known)
        for day in (18,21,24):
            self.assertEqual(Counter(w[day][-1] for w in scenarios),Counter(M2.DEMAND.keys()))

    def test_hourly_rollout_reproduces_v1_when_given_v1_world(self):
        obs,memory=self.obs,self.memory;scenario=V.SCENARIOS[1]
        daily=V.rival_schedule(obs,scenario[1]);rival=obs['farms'][1-int(obs['player'])]
        world=dict(shops=V.future_shops(obs,scenario[0]),
            hourly={24*d+1:flows for d,flows in daily.items()},
            farms={d:deepcopy(rival) for d in range(int(obs['day']),30)})
        old=V.rollout(obs,memory,0,scenario);new=V2.rollout(obs,memory,0,world)
        for key in ('cash_gain','rival_gain','margin_gain','output','failures','survives','feeds','revenue'):
            self.assertEqual(old[key],new[key],key)

    def test_cash_veto_waits_for_balanced_worlds_on_recorded_forecast_fixture(self):
        fixture=json.loads((A.OUT/'v4_historical/111262874-12.json').read_text(encoding='utf-8'))['decision']
        by_route={r['route']:r for r in fixture['candidates']}
        candidates=[{k:by_route[r][k] for k in ('route','episode','hamming','distance','name')} for r in (None,184)]
        obs=dict(day=12,step=288,player=0,farms=[{'tiles':[]},{'tiles':[]}],town={'unlocked_shops':[]})
        def world(obs,index):return dict(index=index,shops={29:[]},donor={})
        def forecast(obs,memory,route,world):return deepcopy(by_route[route]['predictions'][world['index']])
        # Use the real saved public forecasts, with negative first-four own
        # cash but positive full-eight cash; no actual outcome enters choice.
        with patch.object(V,'shortlist',return_value=candidates),patch.object(M3,'world',side_effect=world),patch.object(V2,'rollout',side_effect=forecast):
            self.assertIsNone(V3.choose(deepcopy(obs),{})[0])
            selected,decision=V4.choose(deepcopy(obs),{})
        self.assertEqual(selected,184)
        self.assertEqual(len(decision['candidates'][1]['predictions']),8)


if __name__=='__main__':unittest.main()
