from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from export_semantic_training_public_20260928 import features,asset_states,compare_known


class EnrichmentTests(unittest.TestCase):
    def test_asset_state_aggregation_has_no_source_coordinates(self):
        animal=dict(kind='PASTURE',animal='SHEEP',placed_day=0,yield_units=4,pending_care_bonus=2,
                    fed_today=False,x=9,y=9,source_episode=123)
        farm=dict(tiles=[[deepcopy(animal),deepcopy(animal)]])
        self.assertEqual(asset_states(farm),[dict(kind='PASTURE',animal='SHEEP',placed_day=0,yield_units=4,
            pending_care_bonus=2,fed_today=False,count=2)])

    def test_features_read_only_current_observation_and_past_three_history(self):
        state=dict(day=9,own_crop_cohorts=[],own_animal_cohorts=[],own_structures={},cash=12,
            rival_crop_cohorts=[],rival_animal_cohorts=[],rival_structures={},shops_prefix=['BAKERY']*3)
        policy=SimpleNamespace(public_state=lambda obs:deepcopy(state))
        own=dict(tiles=[[None]],unlocked_quadrants=['NW'],hands=[],money=12)
        rival=dict(tiles=[[None]],unlocked_quadrants=['NW'],hands=[],money=30)
        obs=dict(day=9,player=0,farms=[own,rival],private=dict(shed={'WHEAT':2},seeds={},inventories=[{}],
            opponent_private={'MILK':999},actual_future_shops=['YARN_STORE']),episode=999,rewards=[1,2])
        memory=dict(public_history={str(d):{'observed_ticks':24} for d in range(30)},future_donor='forbidden')
        before=deepcopy((obs,memory));out=features(obs,memory,policy)
        self.assertEqual(list(out['public_history']),['6','7','8'])
        self.assertFalse({'episode','rewards','opponent_private','actual_future_shops','future_donor'} & out.keys())
        self.assertEqual(out['shed'],{'WHEAT':2});self.assertEqual((obs,memory),before)

    def test_known_feature_comparison_allows_new_public_readiness_only(self):
        old=dict(own_crop_cohorts=[dict(crop='WHEAT',birth=3,count=2)],own_animal_cohorts=[],own_structures={},
            cash=100,owned_quadrants=['NW'],hands=0,shops_prefix=['BAKERY','YARN_STORE'])
        new=deepcopy(old);new['own_crop_cohorts'][0].update(observation_day=6,ready_count=1)
        self.assertTrue(all(compare_known(old,new).values()))
        new['own_crop_cohorts'][0]['birth']=4
        self.assertFalse(compare_known(old,new)['own_crop_cohorts'])
        new['cash']=101;self.assertFalse(compare_known(old,new)['cash'])


if __name__=='__main__':unittest.main()
