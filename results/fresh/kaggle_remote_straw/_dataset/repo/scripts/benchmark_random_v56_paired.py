"""Live V56 comparison for the y3 fix review (CLAUDE.md task C.1, 2026-09-23): several of OUR agents
(default mgt_m1, mgt_y2, mgt_y3), each against the active frozen V56, on the SAME fresh natural-RNG
seeds, both seats -- paired the same way scripts/benchmark_random_v56.py's 128-seed panel is (that
panel is mgt_m1-only and its seeds are reused here as the exclusion set, so these are NEW seeds).

V56 REACTS (unlike the recorded-tape ladder panels), so this is the only comparison in this review
where the opponent can answer our extra sheep-servicing. No forced shops, no early stopping.

Usage: .venv/Scripts/python.exe scripts/benchmark_random_v56_paired.py [--agents mgt_m1,mgt_y2,mgt_y3]
                                                                        [--n-seeds 20] [--workers N]
Memory-aware worker cap (shared machine): workers <= min(--workers, 2, floor((free_gb-2.0)/0.92)).
Results: results/fresh/newphase_20260923/y3/v56_paired/games/<agent>-<seed>-<seat>.json
Report:  .venv/Scripts/python.exe scripts/benchmark_random_v56_paired.py --report [--agents ...]
"""
import argparse
import json
import random
import secrets
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/newphase_20260923/y3/v56_paired'
OLD_MANIFEST = ROOT / 'results/fresh/v56_random_20260922/manifest.json'
V56 = ROOT / 'data/router_refresh_20260922/v56/main.py'
RESERVED = set(range(93021000, 93024000))


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2, default=str), encoding='utf-8')
    tmp.replace(path)


def prepare(agents, n_seeds):
    (OUT / 'frozen').mkdir(parents=True, exist_ok=True)
    (OUT / 'games').mkdir(parents=True, exist_ok=True)
    (OUT / 'logs').mkdir(parents=True, exist_ok=True)
    manifest_path = OUT / 'manifest.json'
    frozen_hashes = {}
    for name, path in [('v56', V56)] + [(a, ROOT / f'agents/{a}.py') for a in agents]:
        frozen = OUT / 'frozen' / f'{name}.py'
        if not frozen.exists() or digest(frozen) != digest(path):
            frozen.write_bytes(path.read_bytes())
        frozen_hashes[name] = digest(frozen)
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        changed = False
        for a in agents:
            if a not in manifest['hashes']:
                manifest['hashes'][a] = frozen_hashes[a]
                changed = True
        if changed:
            write_json(manifest_path, manifest)
        return manifest
    old_seeds = set()
    if OLD_MANIFEST.exists():
        old_seeds = set(json.loads(OLD_MANIFEST.read_text(encoding='utf-8'))['seeds'])
    master = secrets.randbits(128)
    rng = random.Random(master)
    seeds = []
    while len(seeds) < n_seeds:
        seed = rng.randrange(1, 2 ** 31)
        if seed not in RESERVED and seed not in old_seeds and seed not in seeds:
            seeds.append(seed)
    manifest = dict(created_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                     design='Natural engine RNG; several of our agents (paired on the same seeds), each vs '
                            'active frozen V56. Fresh seeds, excluded from the 128-seed mgt_m1 panel and the '
                            'reserved block. No forced shops or early stopping.',
                     opponent='v56', hashes=frozen_hashes, master_seed=master, seeds=seeds, seats=[0, 1],
                     excluded_old_seeds=len(old_seeds))
    write_json(manifest_path, manifest)
    return manifest


def worker(job):
    agent, seed, seat, manifest = job
    destination = OUT / 'games' / f'{agent}-{seed}-{seat}.json'
    started = time.perf_counter()
    row = dict(agent=agent, seed=seed, seat=seat, opponent='v56', completed=False, errors=[])
    with (OUT / 'logs' / f'{agent}-{seed}-{seat}.log').open('w', encoding='utf-8') as log:
        import contextlib
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            try:
                from kaggle_environments import make
                from kaggle_environments.agent import get_last_callable
                from kaggle_environments.envs.kaggriculture import kaggriculture as E
                import tape_vs_bench as TV
                paths = {agent: OUT / 'frozen' / f'{agent}.py', 'v56': OUT / 'frozen/v56.py'}
                functions = {name: get_last_callable(p.read_text(encoding='utf-8'), path=str(p))
                             for name, p in paths.items()}
                elapsed = {agent: [], 'v56': []}

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
                players[seat] = timed(agent)
                players[1 - seat] = timed('v56')
                env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': seed})
                result = TV._play(E, env, players, seat, None, None, None, seat)
                final = result['final']
                row.update(cash=final[seat], opponent_cash=final[1 - seat], margin=final[seat] - final[1 - seat],
                           shops=list(env.state[0].observation.town.unlocked_shops),
                           statuses=[s.status for s in env.state], daily=result['daily'],
                           overlay={k: v for k, v in (functions[agent].__globals__.get('_SHP_REPORT') or {}).items()
                                    if isinstance(v, (int, float))},
                           completed=True)
                assert not row['errors']
            except Exception:
                row['completed'] = False
                row['error'] = traceback.format_exc()
            finally:
                row['wall_seconds'] = time.perf_counter() - started
                write_json(destination, row)
    return {k: row.get(k) for k in ('agent', 'seed', 'seat', 'completed', 'cash', 'opponent_cash', 'margin', 'error')}


def free_gb():
    import psutil
    return psutil.virtual_memory().available / 1e9


def run(agents, n_seeds, workers_cap):
    manifest = prepare(agents, n_seeds)
    jobs = []
    for a in agents:
        for seed in manifest['seeds']:
            for seat in manifest['seats']:
                path = OUT / 'games' / f'{a}-{seed}-{seat}.json'
                if path.exists():
                    continue
                jobs.append((a, seed, seat, manifest))
    avail = free_gb()
    workers = max(0, min(workers_cap, 2, int((avail - 2.0) / 0.92)))
    print(f'{len(jobs)} games pending, {workers} workers ({avail:.1f} GB free)', flush=True)
    if not jobs:
        return
    if not workers:
        raise SystemExit('not enough free memory for one game worker; aborting (retry later)')
    with ProcessPoolExecutor(max_workers=workers, max_tasks_per_child=1) as pool:
        futures = {pool.submit(worker, j): j for j in jobs}
        for f in as_completed(futures):
            try:
                r = f.result()
                print(json.dumps(r), flush=True)
            except Exception:
                a, seed, seat, _ = futures[f]
                print(json.dumps(dict(agent=a, seed=seed, seat=seat, completed=False, error=traceback.format_exc())), flush=True)


def ci(xs, n=10000, seed=7):
    if not xs:
        return (0.0, 0.0)
    rng = random.Random(seed)
    k = len(xs)
    m = sorted(sum(rng.choices(xs, k=k)) / k for _ in range(n))
    return m[int(0.025 * n)], m[int(0.975 * n)]


def report(agents, ref='mgt_m1'):
    rows = {}
    for a in set(agents) | {ref}:
        rows[a] = {}
        for p in (OUT / 'games').glob(f'{a}-*.json'):
            g = json.loads(p.read_text(encoding='utf-8'))
            if g.get('completed'):
                rows[a][(g['seed'], g['seat'])] = g
    print(f'{"agent":<14}{"n":>5}{"W-L":>9}{"mean margin (95% CI)":>32}{"paired vs " + ref + " (95% CI)":>34}  b/w/s')
    base = rows[ref]
    for a in agents:
        keys = sorted(set(rows[a]) & set(base)) if a != ref else sorted(rows[a])
        if not keys:
            print(f'{a:<14} no completed games')
            continue
        m = [rows[a][k]['margin'] for k in keys]
        lo, hi = ci(m)
        if a == ref:
            print(f'{a:<14}{len(keys):>5}{sum(x>0 for x in m):>4}-{sum(x<0 for x in m):<4}{sum(m)/len(m):>+15,.0f} ({lo:>+7,.0f}..{hi:>+7,.0f})')
            continue
        d = [rows[a][k]['margin'] - base[k]['margin'] for k in keys]
        dlo, dhi = ci(d)
        print(f'{a:<14}{len(keys):>5}{sum(x>0 for x in m):>4}-{sum(x<0 for x in m):<4}{sum(m)/len(m):>+15,.0f} ({lo:>+7,.0f}..{hi:>+7,.0f})'
              f'{sum(d)/len(d):>+15,.0f} ({dlo:>+7,.0f}..{dhi:>+7,.0f})  {sum(x>0 for x in d)}/{sum(x<0 for x in d)}/{sum(x==0 for x in d)}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--agents', default='mgt_m1,mgt_y2,mgt_y3')
    ap.add_argument('--n-seeds', type=int, default=20)
    ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--ref', default='mgt_m1')
    args = ap.parse_args()
    agents = args.agents.split(',')
    if args.report:
        report(agents, args.ref)
    else:
        run(agents, args.n_seeds, args.workers)


if __name__ == '__main__':
    main()
