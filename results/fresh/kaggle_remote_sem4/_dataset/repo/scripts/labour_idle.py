"""How much idle labour does the benchmark's crew have, and what does its board look like tile by tile?

Runs the frozen benchmark in Mother-Goose's seat of her recorded worlds (her shops forced, benchmark
live on both seats) and records, for that seat, every unit's position and action at every step, plus
the board at every day start. Output: results/fresh/labour_idle/<eid>-<seat>.json
  units[t] = [[x, y, op], ...]   (farmer first, then hands in index order; op is the action's verb)
  boards[d] = [[label, ...], ...] (crop / animal / structure per tile at day start)
"""
import json, sys
from concurrent.futures import ProcessPoolExecutor
from market_corpus import ROOT
import tape_vs_bench as TV
from extract_mg_events import tile_label

OUT = ROOT / 'results/fresh/labour_idle'


def run(job):
    path, eid, seat = job
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    replay = json.loads(open(path, encoding='utf-8').read())
    config, seed = replay['configuration'], replay['info']['seed']
    shops = [replay['steps'][min(719, d * 24)][0]['observation']['town']['unlocked_shops'] for d in range(31)]
    agents = [get_last_callable(TV.BENCH.read_text(encoding='utf-8'), path=str(TV.BENCH)) for _ in (0, 1)]
    units, boards = [], []

    def rec(i):
        def act(obs, t):
            a = agents[i](obs)
            if i == seat:
                farm = obs['farms'][seat]
                pos = [farm['farmer']] + list(farm['hands'])
                cmds = [a.get('farmer')] + list(a.get('hands') or [])
                row = []
                for k, p in enumerate(pos):
                    c = cmds[k] if k < len(cmds) else None
                    row.append([p[0], p[1], (c[0] if isinstance(c, list) and c else 'NONE')])
                units.append(row)
                if t % 24 == 0:
                    boards.append([[tile_label(x) for x in r] for r in farm['tiles']])
            return a
        return act

    env = make('kaggriculture', configuration=config, info={'seed': seed})
    res = TV._play(E, env, [rec(0), rec(1)], seat, shops, None, None, seat)
    OUT.mkdir(parents=True, exist_ok=True)
    out = dict(episode=eid, seat=seat, units=units, boards=boards, final=res['final'][seat])
    (OUT / f'{eid}-{seat}.json').write_text(json.dumps(out), encoding='utf-8')
    return eid, len(units)


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    games = TV.mg_games()[:n]
    with ProcessPoolExecutor(max_workers=4, max_tasks_per_child=1) as pool:
        for eid, k in pool.map(run, games):
            print('done', eid, k, flush=True)


if __name__ == '__main__':
    main()
