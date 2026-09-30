"""Recover public decision inputs by replaying frozen, already-evaluated games.

No new forecasts or decisions are made here. All previous actions/cash are
checked before a checkpoint is admitted to the dataset. Labels stay separate
from inputs, and all observations from one seed share a validation group.
"""
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from hashlib import sha256
import argparse
import gzip
import json
import os
from pathlib import Path
import pickle
import time
import traceback

import benchmark_value_tape_generalization_v2 as G
import probe_value_tape_search as P
import research_labour_profit as R
import value_tape_search as V
from value_tape_search_v5 import observation_copy, semantic_memory

OUT = V.ROOT / 'results/fresh/value_tape_ranker_20260923'


def sources():
    jobs = []
    for panel, folder in (
        ('generalization', V.ROOT / 'results/fresh/value_tape_speed_20260923/generalization_corrected'),
        ('v3', V.ROOT / 'results/fresh/value_tape_followup_20260923/v3_live'),
        ('v4', V.ROOT / 'results/fresh/value_tape_followup_20260923/v4_live'),
    ):
        design = json.loads((folder / 'design.json').read_text(encoding='utf-8'))
        for spec in design['specs']:
            stem = spec.get('id') or f"{spec['seed']}-{spec['seat']}"
            jobs.append(dict(id=f'{panel}-{stem}', source=str(folder / f'{stem}.json'),
                panel=panel, kind='live'))
    for episode, day in ((111262874, 12), (111269605, 15), (111287532, 12)):
        path = V.ROOT / f'results/fresh/value_tape_followup_20260923/v4_historical/{episode}-{day}.json'
        jobs.append(dict(id=f'historical-{episode}-{day}', source=str(path),
            panel='historical', kind='historical'))
    return jobs


def checkpoint(obs, entry, decision, identity, group, source):
    return dict(id=identity, group=group, obs=observation_copy(obs),
        memory=semantic_memory(V.memory_of(entry)), decision=decision,
        source=source, source_sha256=sha256(Path(source).read_bytes()).hexdigest())


def replay(job, saved):
    spec = saved['spec']
    seat = spec['seat']
    ours = V.fresh_agent()
    rival = G.load_opponent(spec.get('opponent', 'v56'))
    chassis = ours.__globals__['_MGT_IMPL'].chassis
    native = chassis.router
    decisions = saved['candidate'].get('decisions') or [saved['decision']]
    by_day = {d['day']: d for d in decisions}
    shops = spec['shops']
    world = dict(seed=spec['seed'], seat=seat, episode=0,
        shops=[shops[:min(8, d//3)] for d in range(31)])
    snapshots, prefix, actions = [], [], sha256()
    first = min(by_day) * 24
    E = R.engine()
    with R.Simulator(world) as sim:
        state = deepcopy(sim.initial)
        for t in range(719):
            sim.t = t
            sim.seats = {id(f): s for s, f in enumerate(state[0].observation.farms)}
            for s in state:
                s.observation.step = t
            if t % 24 == 0:
                state[0].observation.town['unlocked_shops'][:] = world['shops'][t//24]
            if t % 24 == 0 and t//24 in by_day:
                decision = by_day[t//24]
                point = checkpoint(state[seat].observation, ours, decision,
                    f"{job['id']}-day{t//24}", f"seed-{spec['seed']}", job['source'])
                point['panel'] = job['panel']
                point['opponent'] = spec.get('opponent', 'v56')
                snapshots.append(point)
                # Reapply the frozen decision, without calling any search.
                chassis.router = native
                if decision['selected'] is not None:
                    def committed(obs, step, memory, route=decision['selected'], until=decision['until']):
                        if step < until:
                            memory['route'] = route
                            return route
                        return native(obs, step, memory)
                    chassis.router = committed
            for index, entry in ((seat, ours), (1-seat, rival)):
                state[index].action = entry(deepcopy(state[index].observation))
            pair = [s.action for s in state]
            actions.update(json.dumps(pair, sort_keys=True).encode())
            if t < first:
                prefix.append(deepcopy(pair))
            E.interpreter(state, sim.env)
        cash = [s.reward for s in state]
        assert all(s.status == 'DONE' for s in state)
        for s in range(2):
            econ = R.economic(sim.events, s)
            assert 3000 + sum(econ['revenue'].values()) - sum(econ['spend'].values()) == cash[s]
    old = saved['candidate']
    assert cash[seat] == old['cash'] and cash[1-seat] == old['rival_cash'], (job['id'], cash)
    assert sha256(json.dumps(prefix, sort_keys=True).encode()).hexdigest() == old['prefix_sha256']
    if 'actions_sha256' in old:
        assert actions.hexdigest() == old['actions_sha256'], job['id']
    return snapshots, dict(cash_verified=True, ledger_verified=True, prefix_verified=True,
        all_actions_verified='actions_sha256' in old, actions_sha256=actions.hexdigest())


def worker(job):
    target = OUT / 'checkpoints' / f"{job['id']}.pkl.gz"
    audit = target.with_suffix('.audit.json')
    if target.exists() and audit.exists():
        row = json.loads(audit.read_text(encoding='utf-8'))
        assert row['source_sha256'] == sha256(Path(job['source']).read_bytes()).hexdigest()
        return row
    started = time.perf_counter()
    with target.with_suffix('.log').open('w', encoding='utf-8') as log:
        descriptors = [os.dup(1), os.dup(2)]
        try:
            os.dup2(log.fileno(), 1)
            os.dup2(log.fileno(), 2)
            saved = json.loads(Path(job['source']).read_text(encoding='utf-8'))
            assert saved['completed']
            if job['kind'] == 'live':
                points, checks = replay(job, saved)
            else:
                spec = saved.get('spec', saved)
                game, pair = P.load(spec['episode'])
                state, memory = P.checkpoint(game, pair, spec['day'])
                points = [dict(id=job['id'], group=f"episode-{spec['episode']}",
                    obs=observation_copy(state[game['seat']].observation),
                    memory=semantic_memory(memory), decision=saved['decision'],
                    source=job['source'], source_sha256=sha256(Path(job['source']).read_bytes()).hexdigest(),
                    panel='historical', opponent='recorded')]
                checks = dict(native_prefix_actions_verified=True, reserved_regression=True)
            with gzip.open(target, 'wb') as f:
                pickle.dump(points, f, protocol=5)
            row = dict(id=job['id'], completed=True, checkpoints=len(points),
                source=job['source'], source_sha256=sha256(Path(job['source']).read_bytes()).hexdigest(),
                artifact_sha256=sha256(target.read_bytes()).hexdigest(), checks=checks)
        except Exception:
            row = dict(id=job['id'], completed=False, error=traceback.format_exc())
        finally:
            os.dup2(descriptors[0], 1)
            os.dup2(descriptors[1], 2)
            for fd in descriptors:
                os.close(fd)
    row['seconds'] = time.perf_counter()-started
    audit.write_text(json.dumps(row, indent=2), encoding='utf-8')
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()
    (OUT / 'checkpoints').mkdir(parents=True, exist_ok=True)
    jobs, rows = sources(), []
    with ProcessPoolExecutor(max_workers=args.workers, max_tasks_per_child=1) as pool:
        for future in as_completed([pool.submit(worker, job) for job in jobs]):
            row = future.result()
            rows.append(row)
            print(json.dumps(row), flush=True)
    result = dict(jobs=len(rows), completed=sum(r['completed'] for r in rows),
        checkpoints=sum(r.get('checkpoints', 0) for r in rows), rows=rows,
        builder_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        protocol='Frozen-action replay only; whole seed groups for validation; historical named recoveries reserved for regression. Input/label records separate from source outcomes.')
    (OUT / 'dataset_audit.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}), flush=True)
    assert all(r['completed'] for r in rows)


if __name__ == '__main__':
    main()
