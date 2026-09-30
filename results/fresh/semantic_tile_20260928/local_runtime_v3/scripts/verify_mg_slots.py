"""Verify the MG slot layer in isolation: are swapped crops fully serviced by the tape's own visits, and is
everything else on the farm left alone?

Each variant plays Mother-Goose's seat of her 30 recorded worlds (her shops forced) against the live
frozen benchmark. A tile tracker wraps the engine and records, for the variant's seat, every effective
PLANT, every harvested unit by tile and crop, every plant lost to drought (two dry days), and every unit
lost to decay. The null variant (layer active, no swaps) is the control on the same world and seat.

Output: results/fresh/mg_slots/<variant>-<eid>-<seat>.json
Usage:  python verify_mg_slots.py mgs_null,mgs_t11,...
"""
import json, sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from market_corpus import ROOT
import tape_vs_bench as TV

OUT = ROOT / 'results/fresh/mg_slots'


def tracker(E, env, seat):
    rec = dict(plants=[], harvest=defaultdict(Counter), dry=[], decay=Counter(), decay_deaths=[])
    unit, refresh, decay = E._apply_unit_action, E._daily_refresh_plants, E._decay_plants

    def seat_of(farm):
        farms = env.state[0].observation.farms if env.state else []
        for i, f in enumerate(farms or []):
            if f is farm:
                return i
        return None

    def step_now():
        return int(env.state[0].observation.get('step', 0)) if env.state else 0

    def work(farm, private, idx, action, *a, **k):
        if seat_of(farm) != seat or not isinstance(action, list) or not action:
            return unit(farm, private, idx, action, *a, **k)
        pos = E._farmer_position(farm, idx)
        before_tile = dict(farm['tiles'][pos[1]][pos[0]]) if pos and isinstance(farm['tiles'][pos[1]][pos[0]], dict) else farm['tiles'][pos[1]][pos[0]] if pos else None
        inv0 = dict(private['inventories'][idx]) if idx < len(private['inventories']) else {}
        out = unit(farm, private, idx, action, *a, **k)
        if not pos or idx >= len(private['inventories']):
            return out
        x, y = pos
        after_tile = farm['tiles'][y][x]
        if action[0] == 'PLANT' and before_tile is None and isinstance(after_tile, dict) and after_tile.get('kind') == 'PLANT':
            rec['plants'].append((step_now(), x, y, after_tile['crop']))
        if action[0] == 'HARVEST':
            inv1 = private['inventories'][idx]
            for item in set(inv0) | set(inv1):
                g = inv1.get(item, 0) - inv0.get(item, 0)
                if g > 0:
                    rec['harvest'][f'{x},{y}'][item] += g
        return out

    def refresh_wrap(farm, current_day, turns_per_day):
        if seat_of(farm) != seat:
            return refresh(farm, current_day, turns_per_day)
        before = [[(t.get('crop') if isinstance(t, dict) and t.get('kind') == 'PLANT' else None) for t in row] for row in farm['tiles']]
        out = refresh(farm, current_day, turns_per_day)
        for y, row in enumerate(farm['tiles']):
            for x, t in enumerate(row):
                if before[y][x] and isinstance(t, dict) and t.get('kind') == 'WEED':
                    rec['dry'].append((current_day, x, y, before[y][x]))
        return out

    def decay_wrap(farm, step):
        if seat_of(farm) != seat:
            return decay(farm, step)
        before = [[(t.get('crop'), t.get('yield_units', 0)) if isinstance(t, dict) and t.get('kind') == 'PLANT' else None for t in row] for row in farm['tiles']]
        out = decay(farm, step)
        for y, row in enumerate(farm['tiles']):
            for x, t in enumerate(row):
                b = before[y][x]
                if not b:
                    continue
                crop, y0 = b
                y1 = t.get('yield_units', 0) if isinstance(t, dict) and t.get('kind') == 'PLANT' else 0
                if y0 > 0 and y1 < y0:
                    rec['decay'][crop] += y0 - y1
                if isinstance(t, dict) and t.get('kind') == 'WEED':
                    rec['decay_deaths'].append((step, x, y, crop, y0))
        return out

    return rec, (work, refresh_wrap, decay_wrap), (unit, refresh, decay)


def run(job):
    variant, path, eid, seat = job
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    replay = json.loads(open(path, encoding='utf-8').read())
    config, seed = replay['configuration'], replay['info']['seed']
    shops = [replay['steps'][min(719, d * 24)][0]['observation']['town']['unlocked_shops'] for d in range(31)]
    bench = get_last_callable(TV.BENCH.read_text(encoding='utf-8'), path=str(TV.BENCH))
    cpath = ROOT / 'agents' / f'{variant}.py'
    cand = get_last_callable(cpath.read_text(encoding='utf-8'), path=str(cpath))
    players = [None, None]
    players[seat] = lambda obs, t: cand(obs)
    players[1 - seat] = lambda obs, t: bench(obs)
    env = make('kaggriculture', configuration=config, info={'seed': seed})
    rec, wrapped, originals = tracker(E, env, seat)
    E._apply_unit_action, E._daily_refresh_plants, E._decay_plants = wrapped
    try:
        res = TV._play(E, env, players, seat, shops, None, None, seat)
    finally:
        E._apply_unit_action, E._daily_refresh_plants, E._decay_plants = originals
    final_obs = env.state[seat].observation
    out = dict(variant=variant, episode=eid, seat=seat, final=res['final'][seat], bench_final=res['final'][1 - seat],
               margin=res['final'][seat] - res['final'][1 - seat],
               telemetry=dict(getattr(cand, 'mgs_telemetry', {}) or {}),
               physical=res['daily'][seat][-1]['physical'], revenue=res['daily'][seat][-1]['revenue'],
               spend=res['daily'][seat][-1]['spend'], sold=res['daily'][seat][-1]['sold_units'],
               bench_revenue=res['daily'][1 - seat][-1]['revenue'],
               seeds_left=dict(final_obs['private']['seeds']),
               plants=rec['plants'], harvest={k: dict(v) for k, v in rec['harvest'].items()},
               dry=rec['dry'], decay=dict(rec['decay']), decay_deaths=rec['decay_deaths'],
               cash_daily=[d['money'] for d in res['daily'][seat]])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f'{variant}-{eid}-{seat}.json').write_text(json.dumps(out), encoding='utf-8')
    return out


def main():
    variants = sys.argv[1].split(',')
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    games = TV.mg_games()[:n]
    jobs = [(v, p, e, s) for v in variants for p, e, s in games
            if not (OUT / f'{v}-{e}-{s}.json').exists()]
    print(f'{len(jobs)} games', flush=True)
    with ProcessPoolExecutor(max_workers=4, max_tasks_per_child=1) as pool:
        futures = {pool.submit(run, j): j for j in jobs}
        for f in as_completed(futures):
            try:
                r = f.result()
                t = r['telemetry']
                print(f"{r['variant']:14s} {r['episode']}: margin {r['margin']:+8.0f} swaps {t.get('swaps_committed', 0)} "
                      f"harvest {t.get('harvest_issued_units', 0)} lost {t.get('lost_plants', 0)} errors {t.get('errors', 0)}", flush=True)
            except Exception as exc:
                print(f'FAILED {futures[f][0]} {futures[f][2]}: {type(exc).__name__}: {exc}', flush=True)


if __name__ == '__main__':
    main()
