from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import semantic_strategy_policy_20260928 as P
from semantic_strategy_blocks_20260928 import SemanticBlockPolicy
from semantic_strategy_blocks_reveal_20260928 import SemanticRevealBlockPolicy,reveal_features
from test_semantic_strategy_blocks_20260928 import model,obs


def bundle():
    base=model();rev=deepcopy(base)
    for b in rev['blocks'].values():
        b['mean'] += [0.]*len(P.SHOPS);b['scale'] += [1.]*len(P.SHOPS)
        b['coef'] += [[0.]*len(base['outputs']) for _ in P.SHOPS]
    # Makes the semantic distinction visible without relying on fit noise.
    target=rev['outputs'].index('SHEEP')
    rev['blocks']['9']['coef'][15+list(P.SHOPS).index('YARN_STORE')][target]=3
    return dict(reveal_shop_types=list(P.SHOPS),baseline_model=base,reveal_model=rev)


def observed(day,animals=()):
    value=obs(day,animals=animals)
    shops=['BAKERY','PIZZA_SHOP','YARN_STORE','PET_CAFE','BRUNCH_SPOT','BAKERY','SMOOTHIE_SHOP','YARN_STORE']
    value['town']['unlocked_shops']=shops[:min(8,day//3)]
    return value


class RevealFeatureTests(unittest.TestCase):
    def test_off_is_full_proposal_equivalent(self):
        m=bundle();old=SemanticBlockPolicy(m['baseline_model']);new=SemanticRevealBlockPolicy(m)
        for day in (6,9,12,21,27):
            self.assertEqual(old.propose(observed(day)),new.propose(observed(day)))

    def test_known_reveal_is_order_sensitive_and_future_is_expectation(self):
        shops=list(P.SHOPS)
        a=reveal_features(9,['YARN_STORE','BAKERY','PIZZA_SHOP'],shops)
        b=reveal_features(9,['PIZZA_SHOP','BAKERY','YARN_STORE'],shops)
        self.assertNotEqual(a,b);self.assertEqual(sum(a),1)
        self.assertEqual(reveal_features(12,['PIZZA_SHOP','BAKERY','YARN_STORE'],shops,True),[1/8]*8)
        self.assertEqual(reveal_features(27,['YARN_STORE']*8,shops,True),[0.]*8)
        self.assertEqual(a,reveal_features(9,['YARN_STORE','BAKERY','PIZZA_SHOP','YARN_STORE'],shops))
        with self.assertRaises(ValueError):reveal_features(12,['BAKERY']*3,shops)

    def test_d6_nearest_and_actual_block_unchanged(self):
        m=bundle();old=SemanticBlockPolicy(m['baseline_model']);new=SemanticRevealBlockPolicy(m,{'reveal_features':True})
        a=old.propose(observed(6));b=new.propose(observed(6))
        self.assertEqual(a['today'],b['today']);self.assertEqual(a['memory'],b['memory'])
        self.assertEqual(a['forecast'][:3],b['forecast'][:3])

    def test_identity_private_oracle_and_future_suffix_ignored(self):
        policy=SemanticRevealBlockPolicy(bundle(),{'reveal_features':True})
        o=observed(9);original=deepcopy(o);a=policy.propose(o)
        self.assertEqual(o,original)
        o.update(episode=123,seed=999,reward=999999,actual_future_shops=['YARN_STORE']*8)
        o['private']['opponent_private_inventory']={'WOOL':999999}
        o['private']['actual_future_shops']=['PET_CAFE']*8
        o['town']['future_shops']=['SMOOTHIE_SHOP']*8
        self.assertEqual(a,policy.propose(o))

    def test_held_animals_survive_zero_prediction_without_repurchase(self):
        policy=SemanticRevealBlockPolicy(bundle(),{'reveal_features':True,'forecast':False})
        o=observed(12);o['private']['inventories']=[{'SHEEP':2}]
        result=policy.propose(o)
        self.assertEqual(result['today']['animal_add_counts'],{'SHEEP':2})
        self.assertEqual(result['today']['estimated_capital_cost'],0)

    def test_block_persistence_success_and_idempotence(self):
        policy=SemanticRevealBlockPolicy(bundle(),{'reveal_features':True,'forecast':False})
        a=policy.propose(observed(9));self.assertEqual(a['diagnostics']['totals']['SHEEP'],3)
        self.assertEqual(a,policy.propose(observed(9),a['memory']))
        b=policy.propose(observed(10,animals=[('SHEEP',9,1)]),a['memory'])
        self.assertEqual(b['diagnostics']['totals'],a['diagnostics']['totals'])
        self.assertEqual(b['today']['animal_add_counts'],{'SHEEP':1})
        c=policy.propose(observed(11,animals=[('SHEEP',9,1),('SHEEP',10,1)]),b['memory'])
        self.assertEqual(c['today']['animal_add_counts'],{'SHEEP':1})

    def test_real_model_keeps_every_other_coefficient_and_metadata(self):
        path=ROOT/'results/fresh/semantic_strategy_20260928/block_model_reveal_modern100.json'
        m=json.loads(path.read_text());base=m['baseline_model'];rev=m['reveal_model']
        for key,old in base['blocks'].items():
            new=rev['blocks'][key];n=len(old['coef'])
            for j,species in enumerate(base['outputs']):
                if species in m['selected_outputs']:continue
                self.assertEqual([row[j] for row in old['coef']],[row[j] for row in new['coef'][:n]])
                self.assertTrue(all(row[j]==0 for row in new['coef'][n:]))
            for field in ('shares','max_counts','hands','land','opening_examples'):
                self.assertEqual(old[field],new[field])
        self.assertNotIn('episode',json.dumps(m['reveal_model']))


if __name__=='__main__':unittest.main()
