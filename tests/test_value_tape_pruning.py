"""Real saved forecast fixtures check admission-preserving early exits."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

import value_tape_search_v7 as G
from validate_value_tape_pruning import equivalent, OUT


class PruningFixtures(unittest.TestCase):
    def test_all_54_live_decisions_keep_admission_and_selection(self):
        directory = OUT / 'generalization_corrected'
        design = json.loads((directory/'design.json').read_text(encoding='utf-8'))
        records = []
        for spec in design['specs']:
            game = json.loads((directory/f"{spec['id']}.json").read_text(encoding='utf-8'))
            for reference in game['candidate']['decisions']:
                day = reference['day']
                by_route = {r['route']:r for r in reference['candidates']}
                # The checkpoint is midnight before new actions. Starting
                # cohorts surviving the baseline have birth dates before today.
                existing = {tuple(x) for p in by_route[None]['predictions'] for x in p['survives'] if x[3] < day}
                class FixtureRuntime:
                    busy = False
                    def prepare(self, obs):
                        self.rollouts = self.pruned_rollouts = self.simulated_turns = 0
                    def shortlist(self, obs, memory, count):
                        return [{k:r[k] for k in ('route','episode','hamming','distance','name')}
                            for r in reference['candidates']]
                    def rollout(self, obs, memory, route, world, until=None, protected=None):
                        self.rollouts += 1
                        result = deepcopy(by_route[route]['predictions'][world['index']])
                        missing = (protected or set()) - set(map(tuple,result['survives']))
                        if missing:
                            self.pruned_rollouts += 1
                            self.simulated_turns += 72
                            return dict(early_rejection=True, missing=sorted(missing),
                                survives=result['survives'],boundary_step=(day+3)*24)
                        self.simulated_turns += 719-day*24
                        return result
                runner = FixtureRuntime()
                def world(obs, index):
                    w = reference['worlds'][index]
                    return dict(index=index,shops={29:w['shops']},donor=w['donor'])
                obs = dict(day=day,step=day*24,player=0,farms=[{'tiles':[]},{'tiles':[]}])
                with patch.object(G,'runtime',return_value=runner), patch.object(G.M,'world',side_effect=world), \
                        patch.object(G.V,'asset_keys',return_value=existing):
                    _, decision = G.choose(obs, {'players':{},'_SHP_STATES':{}})
                equivalent(json.loads(json.dumps(decision)),reference)
                reference_turns = sum(len(c['predictions']) for c in reference['candidates'])*(719-day*24)
                records.append(dict(id=spec['id'],day=day,selected=decision['selected'],
                    reference_turns=reference_turns,simulated_turns=runner.simulated_turns,
                    rollouts=runner.rollouts,pruned_rollouts=runner.pruned_rollouts))
        self.assertEqual(len(records),54)
        old = sum(r['reference_turns'] for r in records)
        new = sum(r['simulated_turns'] for r in records)
        result = dict(decisions=54,admission_and_selection_equal=True,reference_turns=old,
            simulated_turns=new,turn_reduction_fraction=1-new/old,
            pruned_candidates=sum(r['pruned_rollouts'] for r in records),
            evidence='Recorded full-forecast fixtures; selection equivalence and deterministic simulation work count, not new live-game or wall-clock evidence.',
            planner_sha256=G.PLANNER_SHA256,records=records)
        (OUT/'pruning_live_fixtures.json').write_text(json.dumps(result,indent=2),encoding='utf-8')


if __name__=='__main__':
    unittest.main()
