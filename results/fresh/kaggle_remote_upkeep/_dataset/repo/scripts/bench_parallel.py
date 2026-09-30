"""How far does local parallelism go? Run the same kind of game the panels run (tape router vs live V50, Kaggle loader)
with W worker processes and report wall time, throughput, where a game's time goes, and memory per worker.

usage: bench_parallel.py <workers> <games> [candidate=mgt_t10] [rival=v50_public]
"""
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

from market_corpus import ROOT


def run(job):
    cand, rival, seed, seat = job
    import psutil
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    proc = psutil.Process()
    t0 = time.perf_counter()
    agents = []
    for name in (cand, rival):
        p = ROOT / 'agents' / f'{name}.py'
        agents.append(get_last_callable(p.read_text(encoding='utf-8'), path=str(p)))
    load = time.perf_counter() - t0
    spent = [0.0, 0.0]

    def timed(i, fn):
        def call(obs, cfg=None):
            s = time.perf_counter()
            try:
                return fn(obs, cfg)
            finally:
                spent[i] += time.perf_counter() - s
        return call

    order = [timed(0, agents[0]), timed(1, agents[1])]
    if seat == 1:
        order.reverse()
    env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': seed})
    t1 = time.perf_counter()
    env.run(order)
    total = time.perf_counter() - t1
    mem = proc.memory_info()
    return dict(seed=seed, seat=seat, load=load, game=total, ours=spent[0], rival=spent[1], engine=total - spent[0] - spent[1],
                rss=mem.rss / 1e6, peak=getattr(mem, 'peak_wset', mem.rss) / 1e6, cpu=sum(proc.cpu_times()[:2]))


def main():
    workers, games = int(sys.argv[1]), int(sys.argv[2])
    cand = sys.argv[3] if len(sys.argv) > 3 else 'mgt_t10'
    rival = sys.argv[4] if len(sys.argv) > 4 else 'v50_public'
    jobs = [(cand, rival, 175000 + i // 2, i % 2) for i in range(games)]
    import psutil
    before = psutil.virtual_memory()
    t0 = time.perf_counter()
    low = [before.available]
    with ProcessPoolExecutor(max_workers=workers, max_tasks_per_child=1) as pool:
        futures = [pool.submit(run, j) for j in jobs]
        while not all(f.done() for f in futures):
            time.sleep(2)
            low.append(psutil.virtual_memory().available)
        rows = [f.result() for f in futures]
    wall = time.perf_counter() - t0
    n = len(rows)
    avg = lambda k: sum(r[k] for r in rows) / n
    print(f'workers {workers}, games {n}: wall {wall:.0f} s -> {3600 * n / wall:.0f} games/hour; a 64-game panel would take {64 * wall / n / 60:.1f} min')
    print(f'  per game: {avg("game"):.0f} s in the run ({avg("ours"):.0f} s our agent, {avg("rival"):.0f} s {rival}, {avg("engine"):.0f} s engine + framework), '
          f'{avg("load"):.1f} s loading both agent files, CPU {avg("cpu"):.0f} s')
    print(f'  memory per worker: mean peak {avg("peak"):.0f} MB (max {max(r["peak"] for r in rows):.0f} MB); '
          f'system available {before.available / 1e9:.1f} GB before, lowest {min(low) / 1e9:.1f} GB during')


if __name__ == '__main__':
    main()
