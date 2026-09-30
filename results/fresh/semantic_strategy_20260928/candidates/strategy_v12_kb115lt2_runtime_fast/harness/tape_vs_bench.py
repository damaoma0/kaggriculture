"""Mother-Goose's recorded move sequence, replayed against our frozen benchmark playing live.

Mother-Goose (56266758) is deterministic and its early actions are byte-identical across opponents,
so a recorded game is a genuine artefact of its policy. This replays each of its 30 recorded
sequences in its original seat against agents/benchmark_frozen_56280048.py (Kaggle loader).

WHAT IS HELD FIXED, AND WHY
  * the seed and the recorded shop sequence: its decisions were made given those shops;
  * its recorded weed spawns (logged by re-running the original game exactly): weeds are exogenous
    noise, and the shared weed RNG would otherwise drift with the benchmark's board and break the tape
    for reasons unrelated to either policy. The benchmark's weeds stay random.

THE CONFOUND, EXPOSED RATHER THAN HIDDEN
  The tape cannot react: its orders were chosen against different prices and a different opponent.
  Two instruments bound that:
  1. Validity. Every step the tape seat's own board (tiles, positions, hands, quadrants, hires) is
     compared with the board its actions were chosen for. Per day it counts commands that failed
     (no effect, or aimed at a hand that was never hired) and the share of requested sale units that
     actually sold, against the same share in the original game. The first day either breaks is the
     end of the valid window; results after it are unreliable and reported separately.
  2. Calibration arm. Our OWN benchmark is recorded against Two Coins on the same seed, seat and shops,
     and that frozen tape is replayed against the live benchmark exactly as Mother-Goose's is. Its
     result is the cost of merely being a frozen tape for a policy equal to the benchmark, so Mother-
     Goose's result is read against it rather than against zero.

Usage: python tape_vs_bench.py [mg|calib|both]
"""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
import json, sys
from market_corpus import ROOT
from evaluate_boards import Ledger
from analyze_efficiency import board_hours, instrument

OUT = ROOT / 'results/fresh/tape_vs_bench'
REPLAYS = ROOT / 'data/leaders_20260917'
BENCH = ROOT / 'agents/benchmark_frozen_56280048.py'
TWOCOINS = ROOT / 'data/router_refresh_20260916/twocoins/main.py'
MG = ('Unknown Mother-Goose', 56266758)
FAIL_MIN, FAIL_SHARE, SELL_FLOOR = 5, 0.02, 0.5


def farm_key(farm):
    return json.dumps([farm['tiles'], farm['farmer'], farm['hands'], farm['unlocked_quadrants'],
                       farm['hires_today']], sort_keys=True)


def mg_games():
    sample = json.loads((ROOT / 'results/fresh/leader_segments/sample.json').read_text(encoding='utf-8'))
    subs = {e['id']: [a['sub'] for a in e['agents']] for e in sample['sample']}
    out = []
    for path in sorted(REPLAYS.glob('episode-*-replay.json')):
        eid = int(path.name.split('-')[1])
        for seat, sub in enumerate(subs[eid]):
            if sub == MG[1]:
                out.append((str(path), eid, seat))
    return out


def _play(E, env, players, seat, shops_by_day, spawns, spawn_seat, record_seat, cushion=0):
    """Run one game with forced shops and (optionally) forced weed spawns for one farm. Records,
    per seat and per day, cumulative ledgers, labour counters, tile-hours and money, plus the
    recorded seat's actions and board keys, and the sale-order fulfilment of every seat."""
    physical = [Counter(), Counter()]
    hours = [Counter(), Counter()]
    seats, active, step = {}, [False], [0]
    interpreter = env.interpreter
    unit, work = instrument(E, physical, seats, active, step)
    end, spawn = E._end_of_day, E._spawn_weeds
    logged = [dict(), dict()]
    daily = [[], []]
    sell_req = [Counter(), Counter()]
    actions, keys = [], []
    day_now = [0]

    def spawn_wrap(farm, board_size, weed_chance, rng):
        i = seats.get(id(farm))
        if spawns is not None and i == spawn_seat:
            for x, y in spawns.get(str(day_now[0]), []):
                if farm['tiles'][y][x] is None:
                    farm['tiles'][y][x] = {'kind': 'WEED'}
            return
        before = [[t is None for t in row] for row in farm['tiles']]
        spawn(farm, board_size, weed_chance, rng)
        if i is not None:
            logged[i][str(day_now[0])] = [(x, y) for y in range(board_size) for x in range(board_size)
                                          if before[y][x] and farm['tiles'][y][x] is not None]

    def locked(state, environment, day):
        day_now[0] = day
        end(state, environment, day)
        if shops_by_day is not None:
            state[0].observation.town.unlocked_shops[:] = shops_by_day[min(len(shops_by_day) - 1, day + 1)]

    started = [False]

    def real(state, environment):
        active[0] = True
        seats.clear()
        seats.update({id(f): i for i, f in enumerate(state[0].observation.farms)})
        farms = getattr(state[0].observation, 'farms', None) or []
        if cushion and not started[0] and len(farms) > record_seat:
            # sensitivity test only: absorb the opening price drift that breaks a budget-exact tape;
            # the same amount is subtracted from the tape's final cash before any comparison. The
            # first interpreter call only initialises the farms, so wait until they exist.
            farms[record_seat]['money'] += cushion
            started[0] = True
        try:
            return interpreter(state, environment)
        finally:
            active[0] = False

    with Ledger(E) as ledger:
        def snap(obs):
            for i in (0, 1):
                daily[i].append(dict(
                    money=obs['farms'][i]['money'], physical=dict(physical[i]), tile_hours=dict(hours[i]),
                    revenue=dict(ledger.data[i]['revenue']), sold_units=dict(ledger.data[i]['sold_units']),
                    spend=dict(ledger.data[i]['spend']), sell_requested=dict(sell_req[i])))

        def wrap(i, fn):
            def act(obs):
                t = int(obs['step'])
                if i == 0 and t % 24 == 0:
                    snap(obs)
                hours[i].update(board_hours(obs['farms'][i]))
                if i == record_seat:
                    keys.append(farm_key(obs['farms'][i]))
                action = fn(obs, t)
                if i == record_seat:
                    actions.append(deepcopy(action))
                for order in (action or {}).get('market') or []:
                    if isinstance(order, (list, tuple)) and len(order) > 1 and order[0] == 'SELL':
                        sell_req[i][order[1]] += int(order[2]) if len(order) > 2 else 1
                return action
            return act

        E._apply_unit_action, E._end_of_day, E._spawn_weeds = work, locked, spawn_wrap
        env.interpreter = real
        try:
            env.run([wrap(0, players[0]), wrap(1, players[1])])
        finally:
            E._apply_unit_action, E._end_of_day, E._spawn_weeds = unit, end, spawn
            env.interpreter = interpreter
        assert len(env.steps) == 720 and all(s.status == 'DONE' for s in env.state)
        for i in (0, 1):
            extra = cushion if i == record_seat else 0
            assert 3000 + extra + sum(ledger.data[i]['revenue'].values()) - sum(ledger.data[i]['spend'].values()) \
                == env.state[i].reward
        # the cushion is a sensitivity device, never a score: take it back out of the tape's cash
        final = [s.reward - (cushion if i == record_seat else 0) for i, s in enumerate(env.state)]
        for i in (0, 1):
            daily[i].append(dict(money=final[i], physical=dict(physical[i]), tile_hours=dict(hours[i]),
                                 revenue=dict(ledger.data[i]['revenue']), sold_units=dict(ledger.data[i]['sold_units']),
                                 spend=dict(ledger.data[i]['spend']), sell_requested=dict(sell_req[i])))
    return dict(final=final, daily=daily, logged_spawns=logged, actions=actions, keys=keys)


def _daily_diffs(series):
    """Per-day increments of failures, commands, sold and requested sale units."""
    out = []
    for d in range(1, len(series)):
        a, b = series[d - 1], series[d]
        pa, pb = a['physical'], b['physical']
        fails = sum(pb.get(k, 0) - pa.get(k, 0) for k in ('no_effect', 'missing_worker_commands', 'malformed_commands'))
        cmds = pb.get('commands', 0) - pa.get('commands', 0) + pb.get('missing_worker_commands', 0) - pa.get('missing_worker_commands', 0)
        sold = sum(b['sold_units'].values()) - sum(a['sold_units'].values())
        req = sum(b['sell_requested'].values()) - sum(a['sell_requested'].values())
        out.append(dict(fails=fails, commands=cmds, sold=sold, requested=req))
    return out


def validity(tape_run, original_daily, original_keys, seat):
    """First step the board diverges, first failed command, and the day the tape breaks."""
    t_exact = next((t for t, (a, b) in enumerate(zip(tape_run['keys'], original_keys)) if a != b), None)
    tape_days = _daily_diffs(tape_run['daily'][seat])
    orig_days = _daily_diffs(original_daily)
    first_fail_day = next((d for d, x in enumerate(tape_days) if x['fails'] > 0), None)
    break_day, cause = None, None
    for d, (x, o) in enumerate(zip(tape_days, orig_days)):
        if x['fails'] >= max(FAIL_MIN, FAIL_SHARE * max(1, x['commands'])):
            break_day, cause = d, f"{x['fails']} failed commands of {x['commands']}"
            break
        if o['sold'] >= 5 and o['requested'] > 0 and x['requested'] > 0:
            ratio_o = o['sold'] / o['requested']
            ratio_x = x['sold'] / x['requested']
            if ratio_x < SELL_FLOOR * ratio_o:
                break_day, cause = d, f"sold {x['sold']}/{x['requested']} requested units vs original {o['sold']}/{o['requested']}"
                break
    return dict(t_exact=t_exact, first_fail_day=first_fail_day, break_day=break_day, cause=cause,
                failures_by_day=[x['fails'] for x in tape_days])


def run(job):
    arm, path, eid, seat = job[:4]
    cushion = job[4] if len(job) > 4 else 0
    live = job[5] if len(job) > 5 else None  # another agents/<name>.py playing live instead of the benchmark
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    replay = json.loads(open(path, encoding='utf-8').read())
    config, seed = replay['configuration'], replay['info']['seed']
    shops_by_day = [replay['steps'][min(719, d * 24)][0]['observation']['town']['unlocked_shops'] for d in range(31)]
    live_path = (ROOT / 'agents' / f'{live}.py') if live else BENCH
    bench = get_last_callable(live_path.read_text(encoding='utf-8'), path=str(live_path))

    if arm == 'mg':
        # 1. exact replay of the original game, logging the weed spawns and board keys it saw; it does
        #    not depend on our side, so it is cached once per game
        cache = OUT / 'cache' / f'orig-{eid}-{seat}.json'
        if cache.exists():
            original = json.loads(cache.read_text(encoding='utf-8'))
        else:
            recorded = lambda i: (lambda obs, t: deepcopy(replay['steps'][t + 1][i]['action']))
            env = make('kaggriculture', configuration=config, info={'seed': seed})
            original = _play(E, env, [recorded(0), recorded(1)], seat, None, None, None, seat)
            assert original['final'] == replay['rewards'], (eid, 'original replay did not reproduce')
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(original), encoding='utf-8')
        tape_actions, tape_spawns = original['actions'], original['logged_spawns'][seat]
        original_daily, original_keys = original['daily'][seat], original['keys']
        original_cash = original['final']
    else:
        # 1. our benchmark recorded against Two Coins on the same seed, seat and shops
        rival = get_last_callable(TWOCOINS.read_text(encoding='utf-8'), path=str(TWOCOINS))
        players = [None, None]
        players[seat] = lambda obs, t: bench(obs)
        players[1 - seat] = lambda obs, t: rival(obs)
        env = make('kaggriculture', configuration=config, info={'seed': seed})
        original = _play(E, env, players, seat, shops_by_day, None, None, seat)
        tape_actions, tape_spawns = original['actions'], original['logged_spawns'][seat]
        original_daily, original_keys = original['daily'][seat], original['keys']
        original_cash = original['final']
        bench = get_last_callable(live_path.read_text(encoding='utf-8'), path=str(live_path))  # fresh state

    # 2. the frozen tape in its seat against the live benchmark
    players = [None, None]
    players[seat] = lambda obs, t: deepcopy(tape_actions[t])
    players[1 - seat] = lambda obs, t: bench(obs)
    env = make('kaggriculture', configuration=config, info={'seed': seed})
    tape = _play(E, env, players, seat, shops_by_day, tape_spawns, seat, seat, cushion)
    valid = validity(tape, original_daily, original_keys, seat)
    arm = f'{arm}{cushion}' if cushion else arm
    result = dict(arm=arm, cushion=cushion, live=live or 'benchmark_frozen_56280048', episode=eid, seat=seat,
                  seed=seed, original_cash=original_cash,
                  final_cash=tape['final'], tape_cash=tape['final'][seat], bench_cash=tape['final'][1 - seat],
                  margin=tape['final'][seat] - tape['final'][1 - seat], validity=valid,
                  tape_daily=tape['daily'][seat], bench_daily=tape['daily'][1 - seat],
                  original_daily=original_daily)
    if live:
        (OUT / 'flip').mkdir(parents=True, exist_ok=True)
        (OUT / 'flip' / f'{live}-c{cushion}-{eid}-{seat}.json').write_text(json.dumps(result), encoding='utf-8')
    else:
        (OUT / f'{arm}-{eid}-{seat}.json').write_text(json.dumps(result), encoding='utf-8')
    return arm, eid, seat, result['margin'], valid['break_day']


def main():
    arm = sys.argv[1] if len(sys.argv) > 1 else 'both'
    if arm == 'live':
        # python tape_vs_bench.py live <agent>[,<agent>...] <cushion>[,<cushion>...]
        lives = sys.argv[2].split(',')
        cushions = [int(c) for c in sys.argv[3].split(',')] if len(sys.argv) > 3 else [0]
        OUT.mkdir(parents=True, exist_ok=True)
        jobs = [('mg', p, e, s, c, lv) for lv in lives for c in cushions for p, e, s in mg_games()]
        print(f'{len(jobs)} runs', flush=True)
        with ProcessPoolExecutor(max_workers=4, max_tasks_per_child=1) as pool:
            futures = {pool.submit(run, j): j for j in jobs}
            for f in as_completed(futures):
                try:
                    a, e, s, m, b = f.result()
                    print(f'{futures[f][5]} c{futures[f][4]} {e} seat{s}: margin {m:+.0f}, break {b}', flush=True)
                except Exception as exc:
                    print(f'FAILED {futures[f]}: {type(exc).__name__}: {exc}', flush=True)
        return
    cushions = [int(c) for c in sys.argv[2:]] or [0]
    OUT.mkdir(parents=True, exist_ok=True)
    arms = ('mg', 'calib') if arm == 'both' else (arm,)
    jobs = [(a, p, e, s, c) for a in arms for c in cushions for p, e, s in mg_games()]
    print(f'{len(jobs)} runs', flush=True)
    with ProcessPoolExecutor(max_workers=4, max_tasks_per_child=1) as pool:
        futures = {pool.submit(run, j): j for j in jobs}
        for f in as_completed(futures):
            try:
                a, e, s, m, b = f.result()
                print(f'{a} {e} seat{s}: margin {m:+.0f}, valid through day {b}', flush=True)
            except Exception as exc:
                print(f'FAILED {futures[f][0]} {futures[f][2]}: {type(exc).__name__}: {exc}', flush=True)


if __name__ == '__main__':
    main()
