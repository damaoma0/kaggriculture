from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import semantic_strategy_policy_20260928 as P
from semantic_strategy_blocks_20260928 import SemanticBlockPolicy
from test_semantic_strategy_policy_20260928 import observation


SPECIES=tuple(P.CROPS)+tuple(P.ANIMALS)
OUTPUTS=SPECIES+tuple('RETIRE_'+s for s in P.ANIMALS)


def model():
    zero=[0.]*len(OUTPUTS);daily=[list(zero) for _ in range(3)]
    daily[0][OUTPUTS.index('STRAWBERRY')]=2;daily[1][OUTPUTS.index('STRAWBERRY')]=1
    daily[0][OUTPUTS.index('COW')]=2
    blocks={}
    for day in range(6,30,3):
        blocks[str(day)]=dict(mean=[0.]*14,scale=[1.]*14,coef=[list(zero) for _ in range(15)],
            shares=[[1/3]*len(OUTPUTS) for _ in range(3)],max_counts=[100]*len(OUTPUTS),
            hands=[0]*3,land=[4]*3,opening_examples=[])
    blocks['6']['opening_examples']=[dict(features=dict(shops_prefix=[],own_crop_cohorts=[],own_animal_cohorts=[],owned_quadrants=4),
                                          daily=daily,hands=[0]*3,land=[4]*3)]
    return dict(species=list(SPECIES),outputs=list(OUTPUTS),demand_features=['MILK','WOOL','EGG','STRAWBERRY','TOMATO','CARROT'],blocks=blocks)


def obs(day,crops=(),animals=()):
    o=observation(day,crops,animals);o['farms'][0]['unlocked_quadrants']=['NW','NE','SW','SE'];return o


class BlockPolicyTests(unittest.TestCase):
    def policy(self,m=None,**cfg):return SemanticBlockPolicy(m or model(),dict(forecast=False,**cfg))

    def test_failed_work_carries_and_successful_births_subtract(self):
        p=self.policy();a=p.propose(obs(6));self.assertEqual(a['today']['animal_add_counts'],{'COW':2})
        next_obs=obs(7,crops=[('STRAWBERRY',6,1)],animals=[('COW',6,1)])
        next_obs['private']['shed']={'COW':1}
        b=p.propose(next_obs,a['memory'])
        self.assertEqual(b['today']['plant_counts'],{'STRAWBERRY':2})
        self.assertEqual(b['today']['animal_add_counts'],{'COW':1})
        self.assertEqual(b['today']['estimated_capital_cost'],200)
        c=p.propose(obs(8,crops=[('STRAWBERRY',6,1),('STRAWBERRY',7,2)],animals=[('COW',6,1),('COW',7,1)]),b['memory'])
        self.assertEqual(c['today']['plant_counts'],{})
        self.assertEqual(c['today']['animal_add_counts'],{})

    def test_capacity_clipping_does_not_consume_budget(self):
        p=self.policy(land_limit=1);full=obs(6,crops=[('STRAWBERRY',0,25)])
        full['farms'][0]['unlocked_quadrants']=['NW']
        a=p.propose(full);self.assertEqual(a['today']['animal_add_counts'],{})
        b=p.propose(obs(7),a['memory'])
        self.assertEqual(b['today']['animal_add_counts'],{'COW':2})
        self.assertEqual(b['today']['plant_counts'],{'STRAWBERRY':3})

    def test_repeated_observation_is_idempotent_and_no_rebuy_after_disappearance(self):
        p=self.policy();a=p.propose(obs(6))
        self.assertEqual(a,p.propose(obs(6),a['memory']))
        b=p.propose(obs(7,crops=[('STRAWBERRY',6,2)]),a['memory'])
        c=p.propose(obs(8),b['memory'])
        self.assertEqual(c['today']['plant_counts'],{'STRAWBERRY':1})
        self.assertEqual(c['diagnostics']['completed']['crop'],{'STRAWBERRY':2})

    def test_annual_replant_dates_follow_own_cohorts(self):
        p=self.policy();a=p.propose(obs(9,crops=[('WHEAT',7,4)]))
        self.assertEqual(a['today']['plant_counts'],{})
        self.assertEqual(a['diagnostics']['totals']['WHEAT'],4)
        b=p.propose(obs(10,crops=[('WHEAT',7,4)]),a['memory'])
        self.assertEqual(b['today']['plant_counts'],{'WHEAT':4})

    def test_prepaid_animals_across_reveal_are_urgent_placements_not_new_cost(self):
        p=self.policy();o=obs(9);o['private']['inventories']=[{'SHEEP':2}]
        a=p.propose(o)
        self.assertEqual(a['today']['animal_add_counts'],{'SHEEP':2})
        self.assertEqual(a['today']['estimated_capital_cost'],0)

    def test_retirement_intent_is_not_inferred_from_missed_feeding(self):
        m=model();idx=OUTPUTS.index('RETIRE_SHEEP');m['blocks']['18']['coef'][0][idx]=1
        m['blocks']['18']['shares'][0][idx]=1;m['blocks']['18']['shares'][1][idx]=0;m['blocks']['18']['shares'][2][idx]=0
        p=self.policy(m);o=obs(18,animals=[('SHEEP',0,3)])
        o['farms'][0]['tiles'][0][0]['consecutive_unfed']=1
        a=p.propose(o);self.assertEqual(a['today']['animal_retire_counts'],{'SHEEP':1})
        memory=deepcopy(a['memory']);memory['committed_retirement_counts']={'SHEEP':1}
        b=p.propose(obs(19,animals=[('SHEEP',0,3)]),memory)
        self.assertEqual(b['today']['animal_retire_counts'],{})

    def test_identity_and_actual_future_are_ignored_and_inputs_unchanged(self):
        p=self.policy();o=obs(6);before=deepcopy(o);a=p.propose(o)
        self.assertEqual(o,before)
        o.update(episode=999,seed=123,reward=999999,actual_future_shops=['YARN_STORE']*8)
        self.assertEqual(a,p.propose(o))
        altered=model();altered.update(episode=111,actual_future_shops=['PET_CAFE']*8)
        self.assertEqual(a,self.policy(altered).propose(o))

    def test_forecast_success_does_not_leak_into_actual_memory(self):
        p=self.policy();p.config['forecast']=True
        a=p.propose(obs(6));self.assertEqual(len(a['forecast']),24)
        self.assertEqual(a['memory']['block_strategy']['seen_births'],{})
        b=p.propose(obs(7),a['memory'])
        self.assertEqual(b['today']['animal_add_counts'],{'COW':2})
        self.assertEqual(b['today']['plant_counts'],{'STRAWBERRY':3})

    def test_training_manifest_excludes_new_protocol_holdouts(self):
        root=ROOT/'results/fresh/semantic_strategy_20260928'
        manifest=json.loads((root/'block_model_modern100_training_manifest.json').read_text())
        protocol=json.loads((root/'protocol.json').read_text())
        records=protocol['development']['recorded']+protocol['qualification']['recorded']+protocol['recorded_reserve']
        self.assertFalse(set(manifest['episodes']) & {int(x['episode']) for x in records})
        source=ROOT/manifest['source']
        self.assertEqual(manifest['source_sha256'],hashlib.sha256(source.read_bytes()).hexdigest())
        runtime=json.loads((root/'block_model_modern100.json').read_text())
        self.assertNotIn('episode',json.dumps(runtime))


if __name__=='__main__':unittest.main()
