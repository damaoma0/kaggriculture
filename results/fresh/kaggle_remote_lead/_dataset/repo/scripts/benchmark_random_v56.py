"""Frozen, resumable natural-RNG survey: current m1 vs V56, 128 seeds x 2 seats.

Every game uses fresh agent globals and a fresh spawned process. No forced shops,
outcome selection, or early stopping. Failure records remain in the final panel.
"""
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import redirect_stdout, redirect_stderr
from hashlib import sha256
import argparse
import json
from pathlib import Path
import random
import secrets
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/v56_random_20260922'
SOURCES = {'mgt_m1': ROOT / 'agents/mgt_m1.py',
           'v56': ROOT / 'data/router_refresh_20260922/v56/main.py'}


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2, default=str), encoding='utf-8')
    temporary.replace(path)


def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ('frozen', 'games', 'logs'):
        (OUT / name).mkdir(exist_ok=True)
    manifest_path = OUT / 'manifest.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        for name, relative in manifest['source_paths'].items():
            assert digest(ROOT / relative) == manifest['hashes'][name], name
        for relative, expected in manifest['harness_hashes'].items():
            assert digest(ROOT / relative) == expected, 'Harness changed: ' + relative
        return manifest
    master = secrets.randbits(128)
    rng = random.Random(master)
    excluded = set(range(93021000, 93024000))
    seeds = []
    while len(seeds) < 128:
        seed = rng.randrange(1, 2**31)
        if seed not in excluded and seed not in seeds:
            seeds.append(seed)
    paths, hashes = {}, {}
    for name, path in SOURCES.items():
        frozen = OUT / 'frozen' / (name + '.py')
        frozen.write_bytes(path.read_bytes())
        paths[name] = str(frozen.relative_to(ROOT))
        hashes[name] = digest(frozen)
    harness_files = ['scripts/benchmark_random_v56.py', 'scripts/tape_vs_bench.py',
                     'scripts/analyze_efficiency.py', 'scripts/evaluate_boards.py']
    manifest = dict(created_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        design='Natural engine RNG, current deployed mgt_m1 versus active frozen V56; fixed 128 random seeds, both seats. No forced shops or weeds.',
        agent='mgt_m1', opponent='v56', source_paths=paths, hashes=hashes,
        random_generator='Python random.Random(master_seed), unique uniform integers [1,2**31); exclude reserved seed block 93021000..93023999',
        master_seed=master, seeds=seeds, seats=[0, 1], expected_games=256,
        stopping_rule='Complete all 256 games; no outcome-based early stopping or policy changes.',
        qualifies_new_continuation=False,
        scope='Current-baseline random-world statistics only; new production-plan continuation is not integrated.',
        harness_hashes={p: digest(ROOT / p) for p in harness_files})
    write_json(manifest_path, manifest)
    return manifest


def worker(job):
    seed, seat, manifest = job
    destination = OUT / 'games' / f'{seed}-{seat}.json'
    started = time.perf_counter()
    row = dict(seed=seed, seat=seat, agent='mgt_m1', opponent='v56',
               own_sha256=manifest['hashes']['mgt_m1'], opponent_sha256=manifest['hashes']['v56'],
               completed=False, errors=[])
    with (OUT / 'logs' / f'{seed}-{seat}.log').open('w', encoding='utf-8') as log:
        with redirect_stdout(log), redirect_stderr(log):
            try:
                from kaggle_environments import make
                from kaggle_environments.agent import get_last_callable
                from kaggle_environments.envs.kaggriculture import kaggriculture as E
                from importlib.metadata import version
                import tape_vs_bench as TV
                functions = {}
                loading = {}
                for name, relative in manifest['source_paths'].items():
                    path = ROOT / relative
                    assert digest(path) == manifest['hashes'][name]
                    tick = time.perf_counter()
                    functions[name] = get_last_callable(path.read_text(encoding='utf-8'), path=str(path))
                    loading[name] = time.perf_counter() - tick
                elapsed = {'mgt_m1': [], 'v56': []}
                def timed(name):
                    def act(obs, step):
                        before = time.perf_counter()
                        try:
                            return functions[name](obs)
                        except Exception:
                            row['errors'].append(dict(policy=name, step=step, trace=traceback.format_exc()))
                            raise
                        finally:
                            elapsed[name].append(time.perf_counter() - before)
                    return act
                players = [None, None]
                players[seat] = timed('mgt_m1')
                players[1-seat] = timed('v56')
                env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': seed})
                result = TV._play(E, env, players, seat, None, None, None, seat)
                final = result['final']
                row.update(cash=final[seat], opponent_cash=final[1-seat], margin=final[seat]-final[1-seat],
                    shops=list(env.state[0].observation.town.unlocked_shops),
                    statuses=[s.status for s in env.state], states=len(env.steps), actions=len(result['actions']),
                    ledger_verified=True, daily=result['daily'],
                    action_sha256=sha256(json.dumps(result['actions'], sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                    configuration=dict(env.configuration), engine_version=version('kaggle-environments'),
                    native_telemetry={k:v for k,v in functions['mgt_m1'].__globals__.get('_SHP_REPORT', {}).items()
                                      if isinstance(v, (int, float))},
                    loading_seconds=loading, completed=True)
                assert not row['errors']
                assert all(len(t) == 719 for t in elapsed.values())
            except Exception:
                row['completed'] = False
                row['error'] = traceback.format_exc()
                if 'env' in locals():
                    row['statuses'] = [s.status for s in env.state]
                    row['states'] = len(env.steps)
            finally:
                if 'elapsed' in locals():
                    row['timing'] = {name: dict(calls=len(times), max_seconds=max(times, default=0),
                        total_seconds=sum(times), over_1s=sum(t > 1 for t in times)) for name,times in elapsed.items()}
                row['wall_seconds'] = time.perf_counter() - started
                write_json(destination, row)
    return {k: row.get(k) for k in ('seed', 'seat', 'completed', 'cash', 'opponent_cash', 'margin', 'wall_seconds', 'error')}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    manifest = prepare()
    if args.prepare_only:
        print(json.dumps(manifest, indent=2))
        return
    jobs = []
    for seed in manifest['seeds']:
        for seat in manifest['seats']:
            path = OUT / 'games' / f'{seed}-{seat}.json'
            if path.exists():
                row = json.loads(path.read_text())
                assert row['own_sha256'] == manifest['hashes']['mgt_m1']
                assert row['opponent_sha256'] == manifest['hashes']['v56']
                continue  # failures remain failures; never silently rerun an outcome
            jobs.append((seed, seat, manifest))
    print(json.dumps(dict(expected=256, pending=len(jobs), workers=args.workers)), flush=True)
    with ProcessPoolExecutor(max_workers=args.workers, max_tasks_per_child=1) as pool:
        futures = {pool.submit(worker, job): job for job in jobs}
        for future in as_completed(futures):
            try:
                result = future.result()
            except Exception:
                seed, seat, _ = futures[future]
                result = dict(seed=seed, seat=seat, completed=False, error=traceback.format_exc(),
                    own_sha256=manifest['hashes']['mgt_m1'], opponent_sha256=manifest['hashes']['v56'])
                write_json(OUT / 'games' / f'{seed}-{seat}.json', result)
            print(json.dumps(result), flush=True)
    print('Panel finished. Report failures and all completed results; do not change the panel.', flush=True)


if __name__ == '__main__':
    main()
