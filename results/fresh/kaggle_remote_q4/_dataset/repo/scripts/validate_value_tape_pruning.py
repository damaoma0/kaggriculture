"""Verify the logically exact cohort cutoff against frozen V4/V5 forecasts."""
from copy import deepcopy
import json
import time

import audit_value_forecast_components as A
import probe_value_tape_search as P
import value_tape_search_v7 as G

OUT = G.V.ROOT / 'results/fresh/value_tape_speed_20260923'


def equivalent(decision, reference):
    assert decision['selected'] == reference['selected']
    assert decision['strict_selected'] == reference['strict_selected']
    assert decision['worlds'] == reference['worlds']
    assert [c['route'] for c in decision['candidates']] == [c['route'] for c in reference['candidates']]
    for actual, old in zip(decision['candidates'], reference['candidates']):
        assert actual['admitted'] == old['admitted']
        assert actual['strict_admitted'] == old['strict_admitted']
        if actual.get('early_rejection'):
            witness = actual['protection_failures'][0]
            assert any(f['scenario']==witness['scenario'] and f.get('assets')==witness['assets']
                for f in old['protection_failures'])
        else:
            assert json.loads(json.dumps(actual['predictions'])) == old['predictions']


def main():
    cases = []
    c = A.context('wool')
    cases.append(('wool', c['observation'], c['memory'], 'wool_v4_reference.json'))
    for episode, day in ((111262874,12),(111287532,12)):
        game, pair = P.load(episode)
        state, memory = P.checkpoint(game,pair,day)
        cases.append((str(episode),deepcopy(state[game['seat']].observation),memory,f'{episode}-{day}-v5.json'))
    rows=[]
    for name, obs, memory, path in cases:
        wall, cpu = time.perf_counter(), time.process_time()
        _, decision = G.choose(obs,memory)
        reference=json.loads((OUT/path).read_text(encoding='utf-8'))
        equivalent(json.loads(json.dumps(decision)),reference)
        row=dict(case=name,selected=decision['selected'],seconds=time.perf_counter()-wall,
            cpu_seconds=time.process_time()-cpu,rollouts=decision['rollouts'],pruned_rollouts=decision['pruned_rollouts'],
            simulated_turns=decision['simulated_turns'],reference_turns=sum(len(c['predictions']) for c in reference['candidates'])*(719-int(obs['step'])))
        rows.append(row)
        (OUT/f'{name}-v7.json').write_text(json.dumps(decision,indent=2),encoding='utf-8')
        print(json.dumps(row),flush=True)
    (OUT/'pruning_equivalence.json').write_text(json.dumps(dict(rows=rows,planner_sha256=G.PLANNER_SHA256),indent=2),encoding='utf-8')


if __name__=='__main__':
    main()
