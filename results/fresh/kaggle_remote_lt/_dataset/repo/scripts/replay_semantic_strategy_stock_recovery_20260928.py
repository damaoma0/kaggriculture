"""One-day component continuation after a recorded wheat pickup shortfall.

Both saved action streams reproduce the prefix. The frozen candidate runs in
shadow until the trigger, then its existing rolling dispatcher controls only
the rest of that day. Opponent actions stay recorded; no live opponent is run.
This fixture refuses any retirement intent, so it cannot blanket-feed retirees.
"""
from collections import Counter
from copy import deepcopy
import argparse
import gzip
import json
import os
from pathlib import Path
import sys
import time

from replay_semantic_strategy_service_shadow_20260928 import ROOT, STUDY, load, safe, sha, route_snapshot


def recover(state):
    kb, S = state['kb'], state['kb']._S
    assert not S.get('_xretire'), 'This isolated fixture refuses a day with retirement intent.'
    kb.CFG.update(sd_tier=0, sd_budget0=.7, sd_budget=.35, sd_step_cap=.8, sd_plan_once=0)
    old_tier = S.pop('tier', None)
    for field in ('assign', 'walk'):
        S.get(field, {}).clear()
    lower = kb._sd_state(S)
    lower['routes'].clear()
    lower['walk'].clear()
    lower['lastP'] = None
    lower['first_of_day'] = True
    return old_tier


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', default='live-04')
    parser.add_argument('--day', type=int, default=7)
    parser.add_argument('--tiles', default='25,46')
    parser.add_argument('--external-workers', type=int, required=True)
    args = parser.parse_args()
    import psutil
    available = psutil.virtual_memory().available/2**30
    if args.external_workers >= 4 or available < 2.5:
        raise RuntimeError(f'Insufficient allocated slot/memory: freeGiB={available:.3f}')
    candidate = STUDY/'candidates/strategy_v2_unlock'
    source = STUDY/'fixed_experiments/nearest_shops_v2/runs/strategy_v2_unlock'/f'{args.case}.json'
    original = json.loads(source.read_text())
    action_path = source.with_suffix('.actions.json')
    recorded = json.loads(action_path.read_text())
    manifest = json.loads((candidate/'manifest.json').read_text())
    assert original['candidate_manifest_sha256'] == sha(candidate/'manifest.json')
    for relative, digest in manifest['files'].items():
        assert sha(candidate/'project'/relative) == digest
    for relative, digest in manifest['harness_files'].items():
        assert sha(candidate/'harness'/relative) == digest
    experiment = json.loads((STUDY/'fixed_experiments/nearest_shops_v2/manifest.json').read_text())
    shops = next(row['shops'] for row in experiment['cases'] if row['case']['id'] == args.case)
    project, harness = candidate/'project', candidate/'harness'
    sys.path[:0] = [str(harness), str(project/'scripts')]
    gate = load(harness/'semantic_strategy_gate_20260928.py', 'frozen_stock_gate')
    import kaggle_environments
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    import tape_vs_bench as TV
    assert kaggle_environments.__version__ == '1.32.7'
    os.chdir(project)
    fn, accepts_config, loading = gate.load_entry(project/manifest['entry'], project)
    env = make('kaggriculture', configuration={'episodeSteps':720,'actTimeout':1}, info={'seed':original['case']['seed']})
    seat = original['case']['seat']
    watch = set(map(int,args.tiles.split(',')))
    physical = [Counter(), Counter()]
    seats, active, step_box = {}, [False], [0]
    interpreter = env.interpreter
    old_unit, work = TV.instrument(E, physical, seats, active, step_box)
    old_end = E._end_of_day

    def real(state, environment):
        active[0] = True
        seats.clear()
        seats.update({id(f): i for i,f in enumerate(state[0].observation.farms)})
        try:
            return interpreter(state, environment)
        finally:
            active[0] = False

    def fixed_end(state, environment, day):
        result = old_end(state, environment, day)
        state[0].observation.town.unlocked_shops[:] = shops[min(30,day+1)]
        return result

    snapshots, prefix_parity, trigger = [], [], None
    started = time.perf_counter()
    E._apply_unit_action, E._end_of_day, env.interpreter = work, fixed_end, real
    try:
        with TV.Ledger(E) as ledger:
            env.reset(2)
            stop = (args.day+1)*24
            for step in range(stop):
                step_box[0] = step
                obs = env._Environment__get_shared_state(seat).observation
                assert int(obs['step']) == step
                day, hour = divmod(step,24)
                state = fn.__globals__.get('_STATE')
                if day == args.day and trigger is None and state and state['kb']._S:
                    tier = state['kb']._S.get('tier') or {}
                    events = [event for event in tier.get('log',[]) if event[0] == step-1
                        and event[2] in ('pick_short','pick_none') and str(event[4]).startswith('WHEAT')]
                    if events:
                        trigger = dict(step=step, reason='previous-step observed tier wheat pickup shortfall',
                            events=deepcopy(events), old_tier=safe(recover(state)))
                shadow = fn(deepcopy(obs),env.configuration) if accepts_config else fn(deepcopy(obs))
                if trigger is None:
                    assert shadow == recorded[seat][step], ('Shadow prefix diverged',step)
                    prefix_parity.append(step)
                else:
                    assert not state['kb']._S.get('_xretire'), 'Retirement appeared: fixture does not alter its servicing.'
                chosen = deepcopy(shadow if trigger is not None else recorded[seat][step])
                if day == args.day:
                    farm = obs['farms'][seat]
                    snapshots.append(dict(step=step, hour=hour, cash=farm['money'],
                        private=deepcopy(obs['private']),
                        tiles={str(t):deepcopy(farm['tiles'][t//10][t%10]) for t in watch},
                        executed_action=chosen, recorded_action=recorded[seat][step],
                        state=route_snapshot(fn,day,hour,watch)))
                actions = [deepcopy(recorded[i][step]) for i in range(2)]
                actions[seat] = chosen
                env.step(actions)
            final = env._Environment__get_shared_state(seat).observation
            original_next = original['diagnostics'][seat][args.day+1]['current_observation']
            own_farm = final['farms'][seat]
            current_ledgers = [dict(money=final['farms'][i]['money'],physical=dict(physical[i]),
                revenue=dict(ledger.data[i]['revenue']),sold_units=dict(ledger.data[i]['sold_units']),
                spend=dict(ledger.data[i]['spend'])) for i in range(2)]
            before = original['daily'][seat][args.day]
            baseline = original['daily'][seat][args.day+1]
            differences = {}
            for key in ('physical','revenue','sold_units','spend'):
                ours = current_ledgers[seat][key]
                differences[key] = {k:ours.get(k,0)-baseline[key].get(k,0) for k in set(ours)|set(baseline[key])
                    if ours.get(k,0)!=baseline[key].get(k,0)}
            payload = dict(scope='ONE_DAY_COMPONENT_CONTINUATION_RECORDED_OPPONENT', case=original['case'],
                source_sha256=sha(source),actions_sha256=sha(action_path),candidate_manifest_sha256=sha(candidate/'manifest.json'),
                script_sha256=sha(Path(__file__)),day=args.day,stop_step=stop,live_opponent_calls=0,
                trigger=trigger,exact_shadow_prefix_calls=len(prefix_parity),
                watched_tiles=sorted(watch),snapshots=snapshots,
                baseline_end_tiles={str(t):original_next['own_farm']['tiles'][t//10][t%10] for t in watch},
                recovery_end_tiles={str(t):own_farm['tiles'][t//10][t%10] for t in watch},
                baseline_end_cash=[original['daily'][i][args.day+1]['money'] for i in range(2)],
                recovery_end_cash=[r['money'] for r in current_ledgers],own_ledger_delta=differences,
                ending_private=deepcopy(final['private']),current_ledgers=current_ledgers,
                elapsed_seconds=time.perf_counter()-started,loading_seconds=loading,
                memory_available_before_GiB=available,
                limitation='No full-season profit or responsive-opponent claim. Isolated fixture refuses retirement days; production wrapper must preserve explicit retirees.')
    finally:
        E._apply_unit_action, E._end_of_day, env.interpreter = old_unit, old_end, interpreter
    assert trigger is not None
    out = STUDY/'service_shadows'/f'{args.case}-d{args.day}-stock-recovery.json.gz'
    with gzip.open(out,'wt',encoding='utf-8') as f:
        json.dump(safe(payload),f,separators=(',',':'))
    print(json.dumps({k:payload[k] for k in ('case','stop_step','exact_shadow_prefix_calls','baseline_end_tiles','recovery_end_tiles','baseline_end_cash','recovery_end_cash','elapsed_seconds')}))
    print(str(out))


if __name__ == '__main__':
    main()
