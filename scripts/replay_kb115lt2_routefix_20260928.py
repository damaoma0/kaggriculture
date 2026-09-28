"""Authorized one-day route-local retry diagnostic, against recorded actions.

No live rival computation. Frozen V8 runs unchanged through the requested day;
the experimental functions are installed with their flag OFF, then enabled only
on that day. Every action must match the recording until an admitted retry.
"""
from collections import Counter
from copy import deepcopy
import argparse
import ast
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pickle
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
MAIN = Path(r'C:\Users\xyygl\Documents\kaggriculture')
STUDY = MAIN/'results/fresh/semantic_strategy_20260928'
BASE_SHA = '527d4c48b5d6bbef7854d430797e8691858724242d50eeec1e1636665ee124e7'


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def safe(value):
    if value is None or isinstance(value, (str, int, float, bool)): return value
    if isinstance(value, dict): return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)): return [safe(v) for v in value]
    return repr(value)


def install(fn, source, captures, fixtures):
    state = fn.__globals__.get('_STATE')
    if not state: return
    kb = state['kb']
    if getattr(kb, '_routefix_installed', False): return
    names = {'_tier_wheat_retry_targets', '_tier_wheat_retry_finish', '_tier_wheat_retry',
             '_tier_cmd', '_tier_override'}
    tree = ast.parse(source.read_text())
    body = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {node.name for node in body} == names
    exec(compile(ast.Module(body=body, type_ignores=[]), str(source), 'exec'), kb.__dict__)
    kb.CFG['sd_tier_wheat_retry'] = 0
    cmd = kb._tier_cmd
    def wrapped(TP, R, u, p, inv, tiles, day, hour, step, seeds_left, shed_left):
        pending = bool(R.get('_wheat_retry_pending'))
        before = None
        if kb.CFG['sd_tier_wheat_retry'] and (pending or
                (R['k'] < len(R['items']) and R['items'][R['k']].get('item') == 'WHEAT')):
            # _pol holds a closure used during planning, unnecessary for dispatch.
            before = deepcopy({k: v for k, v in TP.items() if k != '_pol'})
            fixture = dict(TP=before, R=before['routes'][u], u=u, p=tuple(p), inv=deepcopy(inv),
                tiles=deepcopy(tiles), day=day, hour=hour, step=step,
                seeds_left=deepcopy(seeds_left), shed_left=deepcopy(shed_left), CFG=dict(kb.CFG))
            if pending:
                fixture['R']['_wheat_retry_pending']['route_id'] = id(fixture['R'])
                fixture['R']['_wheat_retry_pending']['items_id'] = id(fixture['R']['items'])
        action = cmd(TP, R, u, p, inv, tiles, day, hour, step, seeds_left, shed_left)
        if before is not None and (pending or R.get('_wheat_retry_pending')):
            captures.append(dict(step=step, unit=u, pending_before=pending, action=deepcopy(action),
                route_before=safe(before['routes'][u]), all_routes_before=safe(before['routes']),
                retirements=safe(before.get('_wheat_retry_retired')),
                own_inventory=deepcopy(inv), shed_before=fixture['shed_left'],
                decisions=safe(TP.get('_wheat_retry_audit', [])), route_after=safe(R)))
            fixtures.append(fixture)
        return action
    kb._tier_cmd = wrapped
    kb._routefix_installed = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', default='live-07')
    parser.add_argument('--day', type=int, default=7)
    parser.add_argument('--external-workers', type=int, required=True)
    parser.add_argument('--out-name', default=None)
    args = parser.parse_args()
    import psutil
    available = psutil.virtual_memory().available / 2**30
    if args.external_workers > 1 or available < 2.5:
        raise RuntimeError(f'No authorized slot/headroom: external={args.external_workers}, freeGiB={available:.3f}')
    candidate = STUDY/'candidates/strategy_v8_kb115lt2_readiness'
    source = STUDY/'runs/strategy_v8_kb115lt2_readiness/development/live'/f'{args.case}.json'
    actions_path = source.with_suffix('.actions.json')
    fix = ROOT/'agents/mgt_lead_kb115lt2_routefix.py'
    out_dir = STUDY/'kb115lt2_routefix_diagnostics'
    out_name = args.out_name or f'{args.case}-d{args.day}-v1'
    out = out_dir/(out_name+'.json.gz')
    if out.exists(): raise FileExistsError(out)
    original = json.loads(source.read_text()); recorded = json.loads(actions_path.read_text())
    manifest = json.loads((candidate/'manifest.json').read_text())
    assert original['candidate_manifest_sha256'] == sha(candidate/'manifest.json')
    for rel, digest in manifest['files'].items(): assert sha(candidate/'project'/rel) == digest, rel
    for rel, digest in manifest['harness_files'].items(): assert sha(candidate/'harness'/rel) == digest, rel
    assert sha(candidate/'project/results/fresh/semantic_strategy_20260928/runtime/agents/mgt_lead_kb115lt.py') == BASE_SHA
    shops = [original['shops'][:min(8, d//3)] for d in range(31)]
    project, harness = candidate/'project', candidate/'harness'
    sys.path[:0] = [str(harness), str(project/'scripts')]
    gate = load(harness/'semantic_strategy_gate_20260928.py', 'routefix_frozen_gate')
    import kaggle_environments
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    import tape_vs_bench as TV
    assert kaggle_environments.__version__ == '1.32.7'
    os.chdir(project)
    fn, accepts_config, loading = gate.load_entry(project/manifest['entry'], project)
    env = make('kaggriculture', configuration={'episodeSteps':720,'actTimeout':1}, info={'seed':original['case']['seed']})
    seat = original['case']['seat']
    physical = [Counter(), Counter()]; seats, active, step_box = {}, [False], [0]
    interpreter = env.interpreter
    old_unit, work = TV.instrument(E, physical, seats, active, step_box)
    old_end = E._end_of_day
    def real(state, environment):
        active[0] = True; seats.clear()
        seats.update({id(f): i for i, f in enumerate(state[0].observation.farms)})
        try: return interpreter(state, environment)
        finally: active[0] = False
    def fixed_end(state, environment, day):
        result = old_end(state, environment, day)
        state[0].observation.town.unlocked_shops[:] = shops[min(30, day+1)]
        return result
    captures, fixtures, snapshots, timings, dawn_checks = [], [], [], [], []
    trigger = None; parity_calls = 0; started = time.perf_counter()
    E._apply_unit_action, E._end_of_day, env.interpreter = work, fixed_end, real
    try:
        with TV.Ledger(E) as ledger:
            env.reset(2); stop = (args.day+1)*24
            for step in range(stop):
                step_box[0] = step
                obs = env._Environment__get_shared_state(seat).observation
                assert int(obs['step']) == step
                day, hour = divmod(step, 24)
                if hour == 0 and trigger is None:
                    expected = original['diagnostics'][seat][day]['current_observation']
                    checks = dict(day=day, own=obs['farms'][seat] == expected['own_farm'],
                        market=obs['market'] == expected['market'], private=obs['private'] == expected['private'],
                        shops=obs['town']['unlocked_shops'] == expected['town']['unlocked_shops'])
                    assert all(v for k, v in checks.items() if k != 'day'), checks
                    dawn_checks.append(checks)
                install(fn, fix, captures, fixtures)
                state = fn.__globals__.get('_STATE')
                if state: state['kb'].CFG['sd_tier_wheat_retry'] = int(day == args.day)
                tick = time.perf_counter()
                chosen = fn(deepcopy(obs), env.configuration) if accepts_config else fn(deepcopy(obs))
                duration = time.perf_counter() - tick
                state = fn.__globals__.get('_STATE'); kb = state['kb']
                tier = kb._S.get('tier', {}) if kb._S else {}
                retry_events = [r for r in tier.get('_wheat_retry_audit', [])
                                if r['step'] == step and r['reason'] == 'picked']
                if trigger is None and retry_events: trigger = deepcopy(retry_events[0])
                if trigger is None:
                    assert chosen == recorded[seat][step], ('Unexpected OFF/pre-retry divergence', step)
                    parity_calls += 1
                if day == args.day:
                    snapshots.append(dict(step=step, hour=hour, own_farm=deepcopy(obs['farms'][seat]),
                        private=deepcopy(obs['private']), market=deepcopy(obs['market']),
                        chosen=deepcopy(chosen), recorded=deepcopy(recorded[seat][step]),
                        retirements=safe(kb._S.get('_xretire')),
                        tier_routes=safe(tier.get('routes')), tier_log=safe(tier.get('log')),
                        retry_audit=safe(tier.get('_wheat_retry_audit', []))))
                timings.append(dict(step=step, seconds=duration))
                actions = [deepcopy(recorded[i][step]) for i in range(2)]
                actions[seat] = chosen
                env.step(actions)
            final = env._Environment__get_shared_state(seat).observation
            expected = original['diagnostics'][seat][args.day+1]['current_observation']
            actual = [dict(money=final['farms'][i]['money'], physical=dict(physical[i]),
                revenue=dict(ledger.data[i]['revenue']), sold_units=dict(ledger.data[i]['sold_units']),
                spend=dict(ledger.data[i]['spend'])) for i in range(2)]
            differences = {}
            baseline = original['daily'][seat][args.day+1]
            for key in ('physical', 'revenue', 'sold_units', 'spend'):
                ours = actual[seat][key]
                differences[key] = {k: ours.get(k, 0)-baseline[key].get(k, 0)
                    for k in set(ours)|set(baseline[key]) if ours.get(k, 0) != baseline[key].get(k, 0)}
            payload = dict(scope='ONE_DAY_KB2_LOCAL_RETRY_RECORDED_OPPONENT', case=original['case'],
                source_sha256=sha(source), actions_sha256=sha(actions_path),
                candidate_manifest_sha256=sha(candidate/'manifest.json'),
                original_executor_sha256=BASE_SHA, experimental_executor_sha256=sha(fix),
                script_sha256=sha(Path(__file__)), engine_sha256=sha(Path(E.__file__)),
                day=args.day, stop_step=stop, live_opponent_calls=0, trigger=trigger,
                exact_action_prefix_calls=parity_calls, dawn_checks=dawn_checks, captures=captures,
                snapshots=snapshots, call_timings=timings, own_ledger_delta=differences,
                baseline_end_farm=expected['own_farm'], continuation_end_farm=deepcopy(final['farms'][seat]),
                baseline_end_private=expected['private'], continuation_end_private=deepcopy(final['private']),
                baseline_end_cash=[original['daily'][i][args.day+1]['money'] for i in range(2)],
                continuation_end_cash=[r['money'] for r in actual], current_ledgers=actual,
                elapsed_seconds=time.perf_counter()-started, loading_seconds=loading,
                memory_available_before_GiB=available,
                limitation='One-day local mechanism diagnostic. Current snapshots and own route state only; no full-season or live-rival profit claim.')
            if trigger is None:
                assert payload['baseline_end_farm'] == payload['continuation_end_farm']
                assert payload['baseline_end_private'] == payload['continuation_end_private']
                assert payload['baseline_end_cash'] == payload['continuation_end_cash']
                assert all(not delta for delta in differences.values())
    finally:
        E._apply_unit_action, E._end_of_day, env.interpreter = old_unit, old_end, interpreter
    out_dir.mkdir(parents=True, exist_ok=True)
    with gzip.open(out, 'wt', encoding='utf-8') as handle: json.dump(safe(payload), handle, separators=(',', ':'))
    fixture_path = out_dir/(out_name+'.fixtures.pkl.gz')
    with gzip.open(fixture_path, 'wb') as handle: pickle.dump(fixtures, handle)
    print(json.dumps({k: payload[k] for k in ('case', 'trigger', 'exact_action_prefix_calls',
        'baseline_end_cash', 'continuation_end_cash', 'own_ledger_delta', 'elapsed_seconds')}))
    print(str(out))


if __name__ == '__main__': main()
