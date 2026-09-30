"""Authorized V5 idle diagnostic: replay saved streams and shadow frozen agent.

Shadow decisions never control the world. A whole-game dollar/ledger match and
action parity up to each inspected route are reported separately. This is not a
new policy matchup. Run only within the shared worker/memory allocation.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / 'results/fresh/semantic_strategy_20260928'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe(value, depth=0):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if depth > 12:
        return repr(value)[:500]
    if isinstance(value, dict):
        return {str(k): safe(v, depth+1) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [safe(v, depth+1) for v in value]
    return repr(value)[:500]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def route_snapshot(fn, day, hour, watch):
    state = fn.__globals__.get('_STATE')
    if not state:
        return None
    kb = state['kb']
    S = kb._S
    if S is None:
        return None
    tier = S.get('tier') or {}
    routes = {}
    for unit, route in tier.get('routes', {}).items():
        items = route.get('items', [])
        selected = [i for i, item in enumerate(items) if item.get('tile') in watch]
        routes[str(unit)] = dict(cursor=route.get('k'), sub=route.get('sub'),
            current_items=items[route.get('k', 0):route.get('k', 0)+2],
            watched_items=[dict(item_index=i, item=items[i]) for i in selected],
            done=route.get('done'), plan_hours=route.get('plan_hours'))
    lower = kb._sd_state(S)
    problem = lower.get('lastP')
    problem_fields = ('key', 'jb', 'ops', 'where', 'routes', 'hard', 'vraw', 'real',
                      'up', 'ut', 'rsc', 'cropi', 'seeds', 'keep', 'J', 'U')
    return safe(dict(day=day, hour=hour, sd_tier=kb.CFG['sd_tier'],
        xretire=S.get('_xretire'), xfeed=S.get('_xfeed'), smap=S.get('smap'),
        committed_retirements=state['tile_memory'].get('retirements'),
        animal_lookahead=kb._T.animals_by_day[day:min(day+4, 30)],
        tier_counts=tier.get('cnt'), tier_log=tier.get('log'), tier_summary=tier.get('summary') if hour in (0, 23) else None,
        routes=routes, lower_stats=lower['st'], lower_routes=lower.get('routes'),
        lower_problem={key: getattr(problem, key) for key in problem_fields if hasattr(problem, key)},
        current_context=getattr(kb, '_audit_context', None),
        plan_plant=kb._T.plant[day], plan_harvest=kb._T.harv_tiles[day],
        assignments=S.get('assign'), walk=S.get('walk'), melon=S.get('melon'),
        S_keys=sorted(S), daily_diagnostic=state.get('daily_diagnostic')))


def attach_context_hook(fn):
    state = fn.__globals__.get('_STATE')
    if not state:
        return
    kb = state['kb']
    if getattr(kb, '_audit_hook_installed', False):
        return
    original = kb._sd_pre
    names = original.__code__.co_varnames[:original.__code__.co_argcount]
    def wrapped(*args, **kwargs):
        inputs = dict(zip(names, args), **kwargs)
        result = original(*args, **kwargs)
        kb._audit_context = {key: inputs[key] for key in ('step', 'day', 'hour', 'pos', 'invs', 'tasks', 'jobs',
            'shed', 'seeds', 'assign', 'taken', 'surv_route', 'deliv_u', 'demand')}
        return result
    kb._sd_pre = wrapped
    kb._audit_hook_installed = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', required=True)
    parser.add_argument('--start-day', type=int, required=True)
    parser.add_argument('--end-day', type=int, required=True)
    parser.add_argument('--tiles', required=True)
    parser.add_argument('--external-workers', type=int, required=True)
    parser.add_argument('--out', type=Path, default=STUDY / 'idle_shadows_v5')
    args = parser.parse_args()
    args.out = args.out.resolve()
    import psutil
    available = psutil.virtual_memory().available / 2**30
    if args.external_workers > 1 or available < 2.5:
        raise RuntimeError(f'No authorized diagnostic slot/headroom: external={args.external_workers}, freeGiB={available:.2f}')
    candidate = STUDY / 'candidates/strategy_v5_blocks100_finance'
    source = STUDY / 'runs/strategy_v5_blocks100_finance/development/live' / f'{args.case}.json'
    actions_path = source.with_suffix('.actions.json')
    original = json.loads(source.read_text())
    actions = json.loads(actions_path.read_text())
    manifest = json.loads((candidate/'manifest.json').read_text())
    assert original['candidate_manifest_sha256'] == sha(candidate/'manifest.json')
    for rel, digest in manifest['files'].items():
        assert sha(candidate/'project'/rel) == digest, rel
    for rel, digest in manifest['harness_files'].items():
        assert sha(candidate/'harness'/rel) == digest, rel
    shops = [original['shops'][:min(8, day//3)] for day in range(31)]
    watch = set(map(int, args.tiles.split(',')))
    project, harness = candidate/'project', candidate/'harness'
    sys.path[:0] = [str(harness), str(project/'scripts')]
    gate = load(harness/'semantic_strategy_gate_20260928.py', 'frozen_shadow_gate')
    import kaggle_environments
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    import tape_vs_bench as TV
    assert kaggle_environments.__version__ == '1.32.7'
    os.chdir(project)
    fn, accepts_config, loading = gate.load_entry(project/manifest['entry'], project)
    env = make('kaggriculture', configuration={'episodeSteps': 720, 'actTimeout': 1}, info={'seed': original['case']['seed']})
    seat = original['case']['seat']
    snapshots, mismatches, dawn_checks = [], [], []
    shadow_calls, shadow_max = 0, 0.0
    original_dawn = {row['day']: row['current_observation'] for row in original['diagnostics'][seat]}

    def actor(index):
        def act(obs, step):
            nonlocal shadow_calls, shadow_max
            recorded = deepcopy(actions[index][step])
            if index == seat:
                day, hour = divmod(step, 24)
                if hour == 0:
                    expected = original_dawn[day]
                    dawn_checks.append(dict(day=day,
                        own_farm_equal=obs['farms'][seat] == expected['own_farm'],
                        private_equal=obs['private'] == expected.get('private'),
                        market_equal=obs['market'] == expected['market'],
                        shops_equal=obs['town']['unlocked_shops'] == expected['town']['unlocked_shops']))
                shadow = None
                if day <= args.end_day:
                    if day >= args.start_day:
                        attach_context_hook(fn)
                    tick = time.perf_counter()
                    shadow = fn(deepcopy(obs), env.configuration) if accepts_config else fn(deepcopy(obs))
                    shadow_max = max(shadow_max, time.perf_counter()-tick)
                    shadow_calls += 1
                    if shadow != recorded:
                        mismatches.append(dict(step=step, shadow=safe(shadow), recorded=recorded))
                if args.start_day <= day <= args.end_day or (day == args.end_day+1 and hour == 0):
                    farm = obs['farms'][seat]
                    snapshots.append(dict(step=step, day=day, hour=hour, cash=farm['money'],
                        private=deepcopy(obs['private']), market=deepcopy(obs['market']),
                        positions=dict(farmer=deepcopy(farm['farmer']), hands=deepcopy(farm['hands'])),
                        tiles={str(t): deepcopy(farm['tiles'][t//10][t%10]) for t in watch},
                        all_tiles=deepcopy(farm['tiles']),
                        recorded_action=recorded, shadow_action=safe(shadow),
                        shadow_action_equal=(shadow == recorded) if shadow is not None else None,
                        shadow_prefix_equal=not mismatches,
                        state=route_snapshot(fn, day, hour, watch) if shadow is not None else None))
            return recorded
        return act

    started = time.perf_counter()
    result = TV._play(E, env, [actor(0), actor(1)], seat, shops, None, None, seat)
    cash_equal = result['final'] == original['cash_by_seat']
    ledger_equal = result['daily'] == original['daily']
    assert cash_equal and ledger_equal, 'Both-stream replay must reproduce original cash and complete ledgers.'
    assert all(all(row[key] for key in ('own_farm_equal', 'private_equal', 'market_equal', 'shops_equal')) for row in dawn_checks)
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    payload = dict(scope='RECORDED_ACTION_REPLAY_WITH_NONCONTROLLING_SHADOW', case=original['case'],
        source_sha256=sha(source), actions_sha256=sha(actions_path), candidate_manifest_sha256=sha(candidate/'manifest.json'),
        script_sha256=sha(Path(__file__)), source=source.relative_to(ROOT).as_posix(),
        watched_tiles=sorted(watch), start_day=args.start_day, end_day=args.end_day,
        recorded_actions_executed=True, live_opponent_calls=0, shadow_actions_executed=False,
        replay_cash=result['final'], replay_cash_equal=cash_equal, replay_ledger_equal=ledger_equal,
        dawn_checks=dawn_checks, shadow_calls=shadow_calls, shadow_mismatches=mismatches,
        first_shadow_mismatch=mismatches[0]['step'] if mismatches else None,
        shadow_max_call_seconds=shadow_max, loading_seconds=loading,
        elapsed_seconds=time.perf_counter()-started, memory_available_before_GiB=available,
        snapshots=snapshots)
    target = args.out/f'{args.case}-d{args.start_day}-{args.end_day}.json.gz'
    with gzip.open(target, 'wt', encoding='utf-8') as f:
        json.dump(payload, f, separators=(',', ':'))
    print(json.dumps({k: payload[k] for k in ('case', 'replay_cash_equal', 'replay_ledger_equal', 'shadow_calls', 'first_shadow_mismatch', 'elapsed_seconds')}))
    print(str(target))


if __name__ == '__main__':
    main()
