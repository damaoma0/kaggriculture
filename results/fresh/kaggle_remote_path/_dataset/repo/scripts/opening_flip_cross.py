"""Opening x wheat-flip cross-test: is the MG-style opening affordable only at a lower flip quantity?

User hypothesis: the 70-unit flip raises the wheat price for both sides, so while it breaks Mother-Goose's
budget-exact opening it may also stop US from running that opening. The flip and the opening would then
be coupled and must be evaluated together.

Rows (our side, in Mother-Goose's seat of each of her 30 recorded worlds; recorded shops forced):
  current opening   our V45 chassis, live, with the turn-0 flip set to 70 (= frozen benchmark), 5, 0, or
                    the certified Nash opening (buy 5 on turn 0, keep them)
  MG-style opening  Mother-Goose's own recorded plan (her deferred-commitment opening and everything after),
                    with ONLY her turn-0 wheat orders replaced by the same choices; her own 13/5/13 is kept
                    as a fifth cell. Her recorded weed spawns are replayed; no cash cushion.
Opponent: the frozen benchmark, live (it flips 70). Reported per cell: own cash at the end of engine day 0
(step 24), end of engine day 1 (step 48) and start of day 12 (step 288), hire failures on day 1, whether the
plan stays coherent, and the final margin against the benchmark.
"""
import json, sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from market_corpus import ROOT
import tape_vs_bench as TV

OUT = ROOT / 'results/fresh/opening_flip_cross'
FLIPS = {'flip70': [['BUY_PRODUCT', 'WHEAT', 70], ['SELL', 'WHEAT', 70]],
         'flip5': [['BUY_PRODUCT', 'WHEAT', 5], ['SELL', 'WHEAT', 5]],
         'flip0': [],
         'nash5': [['BUY_PRODUCT', 'WHEAT', 5]]}
OURS = {'flip70': 'sp_flip70', 'flip5': 'sp_flip5', 'flip0': 'sp_flip0', 'nash5': 'sp_nash5'}


def run(job):
    row, flip, path, eid, seat = job
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    replay = json.loads(open(path, encoding='utf-8').read())
    config, seed = replay['configuration'], replay['info']['seed']
    shops = [replay['steps'][min(719, d * 24)][0]['observation']['town']['unlocked_shops'] for d in range(31)]
    bench = get_last_callable(TV.BENCH.read_text(encoding='utf-8'), path=str(TV.BENCH))
    players = [None, None]
    players[1 - seat] = lambda obs, t: bench(obs)
    spawns = None
    original_keys = None
    if row == 'ours':
        path_c = ROOT / 'agents' / f'{OURS[flip]}.py'
        cand = get_last_callable(path_c.read_text(encoding='utf-8'), path=str(path_c))
        players[seat] = lambda obs, t: cand(obs)
    else:
        cache = json.loads((TV.OUT / 'cache' / f'orig-{eid}-{seat}.json').read_text(encoding='utf-8'))
        tape = deepcopy(cache['actions'])
        if flip != 'own':
            tape[0] = dict(tape[0], market=deepcopy(FLIPS[flip]))
            if flip == 'nash5':
                m1 = tape[1].get('market') or []
                if m1[:2] == [['SELL', 'WHEAT', 5], ['BUY_PRODUCT', 'WHEAT', 5]]:
                    tape[1] = dict(tape[1], market=m1[2:])
        players[seat] = lambda obs, t: deepcopy(tape[t])
        spawns = cache['logged_spawns'][seat]
        original_keys = cache['keys']
    env = make('kaggriculture', configuration=config, info={'seed': seed})
    res = TV._play(E, env, players, seat, shops, spawns, seat, seat)
    d = res['daily'][seat]
    b = res['daily'][1 - seat]
    exact = None
    if original_keys is not None:
        exact = next((t for t, (a, o) in enumerate(zip(res['keys'], original_keys)) if a != o), None)
    out = dict(row=row, flip=flip, episode=eid, seat=seat,
               cash_d0=d[1]['money'], cash_d1=d[2]['money'], cash_d12=d[12]['money'],
               bench_d1=b[2]['money'], bench_d12=b[12]['money'],
               hire_fail_d1=d[2]['physical'].get('missing_worker_commands', 0) > 0,
               failed_commands=d[-1]['physical'].get('no_effect', 0) + d[-1]['physical'].get('missing_worker_commands', 0),
               board_exact_until=exact, final=res['final'][seat], bench_final=res['final'][1 - seat],
               margin=res['final'][seat] - res['final'][1 - seat])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f'{row}-{flip}-{eid}-{seat}.json').write_text(json.dumps(out), encoding='utf-8')
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    games = TV.mg_games()
    jobs = [('ours', f, p, e, s) for f in ('flip70', 'flip5', 'flip0', 'nash5') for p, e, s in games]
    jobs += [('mg', f, p, e, s) for f in ('own', 'flip70', 'flip5', 'flip0', 'nash5') for p, e, s in games]
    jobs = [j for j in jobs if not (OUT / f'{j[0]}-{j[1]}-{j[3]}-{j[4]}.json').exists()]
    print(f'{len(jobs)} games', flush=True)
    with ProcessPoolExecutor(max_workers=4, max_tasks_per_child=1) as pool:
        futures = {pool.submit(run, j): j for j in jobs}
        for f in as_completed(futures):
            try:
                r = f.result()
                print(f"{r['row']:4s} {r['flip']:6s} {r['episode']}: d1 {r['cash_d1']:.0f} margin {r['margin']:+.0f}", flush=True)
            except Exception as exc:
                print(f'FAILED {futures[f][:2]} {futures[f][3]}: {type(exc).__name__}: {exc}', flush=True)


if __name__ == '__main__':
    main()
