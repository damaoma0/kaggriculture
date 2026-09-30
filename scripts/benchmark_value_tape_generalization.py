"""Frozen, paired multi-opponent and repeated-reveal V5 development panel.

The first four shop worlds are IID uniform draws; the final two are declared
stress cases. Each is crossed with three live opponents and alternates seats.
No seed, shop suffix, opponent identity, or control outcome reaches choose().
"""
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from hashlib import sha256
import argparse
import importlib.util
import json
import os
from pathlib import Path
import random
import secrets
import statistics
import sys
import time
import traceback

import research_labour_profit as R
import rival_trajectory_model_v3 as M
import value_tape_search as V
import value_tape_search_v5 as F

OUT = V.ROOT / 'results/fresh/value_tape_speed_20260923/generalization'
OPPONENTS = {
    'v56': V.ROOT / 'data/router_refresh_20260922/v56/main.py',
    'sixday': V.ROOT / 'data/public_candidates/thomastschinkel/extracted/main.py',
    'pasture': V.ROOT / 'data/public_candidates/indarkarhana/extracted/agents/e776a_engine_exact_latent_pasture.py',
}
SOURCES = ['value_tape_search.py', 'value_tape_search_v2.py', 'value_tape_search_v3.py',
    'value_tape_search_v5.py', 'rival_trajectory_model.py', 'rival_trajectory_model_v3.py',
    'research_labour_profit.py', 'test_labour_selfplay.py', 'cumulative_engine_profiles.py',
    'benchmark_value_tape_generalization.py']


def source_paths():
    paths = [V.ROOT / 'scripts' / name for name in SOURCES]
    paths += [V.SOURCE_PATH, *OPPONENTS.values()]
    # The modular pasture opponent includes a small local package and data.
    parent = OPPONENTS['pasture'].parents[1]
    paths += [p for p in parent.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    paths += [M.M.LIBRARY / 'manifest.json', M.MODERN / 'manifest.json']
    return sorted(set(paths))


def hashes():
    return {str(p.relative_to(V.ROOT)): sha256(p.read_bytes()).hexdigest() for p in source_paths()}


def load_opponent(name):
    path = OPPONENTS[name]
    spec = importlib.util.spec_from_file_location('v5_live_opponent', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    # Public modules expose agent explicitly; do not mistake an imported helper
    # for the entry point of a modular local opponent.
    return module.agent


def game(spec, search, folder):
    E = R.engine()
    seat = spec['seat']
    ours = V.fresh_agent()
    rival = load_opponent(spec['opponent'])
    chassis = ours.__globals__['_MGT_IMPL'].chassis
    native_router = chassis.router
    shops = spec['shops']
    world = dict(seed=spec['seed'], seat=seat, episode=0,
        shops=[shops[:min(8, d//3)] for d in range(31)])
    decisions, prefix, actions, max_action = [], [], sha256(), [0.0, 0.0]
    with R.Simulator(world) as sim:
        state = deepcopy(sim.initial)
        for t in range(719):
            sim.t = t
            sim.seats = {id(f): s for s, f in enumerate(state[0].observation.farms)}
            for s in state:
                s.observation.step = t
            if t % 24 == 0:
                state[0].observation.town['unlocked_shops'][:] = world['shops'][t//24]
            if t in (288, 360, 432) and search:
                selected, decision = F.choose(deepcopy(state[seat].observation), V.memory_of(ours))
                decisions.append(decision)
                (folder / f"{spec['id']}-day{t//24}.decision.json").write_text(
                    json.dumps(decision, indent=2), encoding='utf-8')
                chassis.router = native_router
                if selected is not None:
                    def committed(obs, step, memory, route=selected, until=decision['until']):
                        if step < until:
                            memory['route'] = route
                            return route
                        return native_router(obs, step, memory)
                    chassis.router = committed
            for index, entry in ((seat, ours), (1-seat, rival)):
                started = time.perf_counter()
                state[index].action = entry(deepcopy(state[index].observation))
                max_action[index] = max(max_action[index], time.perf_counter()-started)
            pair = [s.action for s in state]
            actions.update(json.dumps(pair, sort_keys=True).encode())
            if t < 288:
                prefix.append(deepcopy(pair))
            E.interpreter(state, sim.env)
        cash = [s.reward for s in state]
        economics = [R.economic(sim.events, s) for s in range(2)]
        for s in range(2):
            assert 3000 + sum(economics[s]['revenue'].values()) - sum(economics[s]['spend'].values()) == cash[s]
        assert all(s.status == 'DONE' for s in state)
    return dict(cash=cash[seat], rival_cash=cash[1-seat], margin=cash[seat]-cash[1-seat],
        decisions=decisions, ledger_verified=True, completed=True, economics=economics,
        prefix_sha256=sha256(json.dumps(prefix, sort_keys=True).encode()).hexdigest(),
        actions_sha256=actions.hexdigest(), maximum_native_action_seconds=max_action)


def worker(spec):
    target = OUT / f"{spec['id']}.json"
    if target.exists():
        row = json.loads(target.read_text(encoding='utf-8'))
    else:
        started = time.perf_counter()
        with target.with_suffix('.log').open('w', encoding='utf-8') as log:
            saved = [os.dup(1), os.dup(2)]
            try:
                os.dup2(log.fileno(), 1)
                os.dup2(log.fileno(), 2)
                candidate = game(spec, True, OUT)
                # Freeze all decisions before evaluating the paired control.
                baseline = game(spec, False, OUT)
                assert candidate['prefix_sha256'] == baseline['prefix_sha256']
                selected = [d['selected'] for d in candidate['decisions']]
                if not any(r is not None for r in selected):
                    assert candidate['actions_sha256'] == baseline['actions_sha256']
                    assert candidate['cash'] == baseline['cash'] and candidate['rival_cash'] == baseline['rival_cash']
                row = dict(spec=spec, completed=True, selected=selected, changed=any(r is not None for r in selected),
                    baseline=baseline, candidate=candidate,
                    margin_delta=candidate['margin']-baseline['margin'],
                    cash_delta=candidate['cash']-baseline['cash'],
                    rival_delta=candidate['rival_cash']-baseline['rival_cash'])
            except Exception:
                row = dict(spec=spec, completed=False, error=traceback.format_exc())
            finally:
                os.dup2(saved[0], 1)
                os.dup2(saved[1], 2)
                for fd in saved:
                    os.close(fd)
        row['seconds'] = time.perf_counter()-started
        target.write_text(json.dumps(row, indent=2), encoding='utf-8')
    return {k: row.get(k) for k in ('spec', 'completed', 'selected', 'changed', 'margin_delta',
        'cash_delta', 'rival_delta', 'seconds', 'error')}


def freeze_design():
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / 'design.json'
    if path.exists():
        design = json.loads(path.read_text(encoding='utf-8'))
        assert design['hashes'] == hashes(), 'Frozen source changed'
        return design
    master = secrets.randbits(128)
    rng = random.Random(master)
    seeds = rng.sample(range(1_000_000_000, 4_000_000_000), 6)
    shop_worlds = [[rng.choice(sorted(M.M.DEMAND)) for _ in range(8)] for _ in range(4)]
    shop_worlds += [
        ['PIZZA_SHOP', 'BAKERY', 'PET_CAFE', 'YARN_STORE', 'SMOOTHIE_SHOP', 'FARMERS_MARKET', 'ICE_CREAM_SHOP', 'SMOOTHIE_SHOP'],
        ['PIZZA_SHOP', 'ICE_CREAM_SHOP', 'SMOOTHIE_SHOP', 'BAKERY', 'YARN_STORE', 'YARN_STORE', 'PET_CAFE', 'PIZZA_SHOP'],
    ]
    specs = [dict(id=f'{i}-{opponent}', seed=seed, seat=i % 2, opponent=opponent,
        shops=shop_worlds[i], group='iid' if i < 4 else ('late_berries' if i == 4 else 'late_yarn'))
        for opponent in OPPONENTS for i, seed in enumerate(seeds)]
    design = dict(master_seed=master, specs=specs, hashes=hashes(), decisions=[12, 15, 18],
        training='Unchanged 115 trajectory training library; no new training on this panel.',
        protocol='18 independent live paired games: six shared shop worlds crossed with three responsive opponents; four IID worlds and two declared stresses, seats alternate. Replan at D12/D15/D18 from the actually reached observation, commit only three days. Both seats complete under official engine; fixed shops within each pair. No outcome filtering or parameter tuning. Sources and worlds frozen before execution. Timing recorded without enforcing the competition timeout.')
    path.write_text(json.dumps(design, indent=2), encoding='utf-8')
    for source in source_paths():
        target = OUT / 'sources' / source.relative_to(V.ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    return design


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--freeze-only', action='store_true')
    args = parser.parse_args()
    design = freeze_design()
    if args.freeze_only:
        print(json.dumps(dict(frozen=True, games=len(design['specs']))), flush=True)
        return
    rows = []
    with ProcessPoolExecutor(max_workers=args.workers, max_tasks_per_child=1) as pool:
        for future in as_completed([pool.submit(worker, s) for s in design['specs']]):
            row = future.result()
            rows.append(row)
            print(json.dumps(row), flush=True)
    summary = dict(games=len(rows), completed=sum(r['completed'] for r in rows), rows=rows)
    for label, subset in [('all', rows), *[(name, [r for r in rows if r['spec']['opponent'] == name])
            for name in OPPONENTS], ('iid', [r for r in rows if r['spec']['group'] == 'iid']),
            ('stress', [r for r in rows if r['spec']['group'] != 'iid'])]:
        valid = [r for r in subset if r['completed']]
        values = [r['margin_delta'] for r in valid]
        summary[label] = dict(n=len(valid), changed=sum(r['changed'] for r in valid),
            mean=statistics.mean(values) if values else None, total=sum(values),
            minimum=min(values, default=None), maximum=max(values, default=None),
            positive=sum(v > 0 for v in values), negative=sum(v < 0 for v in values))
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k != 'rows'}), flush=True)


if __name__ == '__main__':
    main()
