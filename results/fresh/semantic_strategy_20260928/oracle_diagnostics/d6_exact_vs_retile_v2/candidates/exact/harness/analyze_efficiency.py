"""Labour and land efficiency, measured identically for the leaders and for our frozen benchmark.

Question under test (from the user): is Mother-Goose's advantage mostly layout efficiency and labour
saving, rather than crop-portfolio choice?

Per game and per seat this records:
  * land: tile-hours of every unlocked tile by state (each crop, each animal, empty structure, empty
    ground, weed), sampled at every one of the 720 steps, so fallow and weed time are exact;
  * labour: every executed unit command by type, travel moves, PASS, commands that changed nothing,
    hands hired and hire spend;
  * output: units produced by harvest/collection, units sold and revenue per product, all spend.

Modes
  replays : the 52 exactly replayed leader episodes (data/leaders_20260917), BOTH seats, so each
            leader can also be compared with its own opponents in the same market.
  ours    : live games of agents/benchmark_frozen_56280048.py, loaded with Kaggle's last-callable
            loader, against an opponent given on the command line (default: itself).

Usage: python analyze_efficiency.py replays
       python analyze_efficiency.py ours [opponent] [seed_base] [n_seeds]
"""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
import json, sys
from market_corpus import ROOT
from evaluate_boards import Ledger

OUT = ROOT / 'results/fresh/efficiency'
REPLAYS = ROOT / 'data/leaders_20260917'
BENCH = ROOT / 'agents/benchmark_frozen_56280048.py'
OPPONENTS = {'self': BENCH, 'twocoins': ROOT / 'data/router_refresh_20260916/twocoins/main.py',
             'v44': ROOT / 'data/router_refresh_20260916/v44/main.py'}


def tile_state(tile):
    if tile == 'LOCKED':
        return None
    if tile is None:
        return 'empty'
    if tile.get('kind') == 'PLANT':
        return 'crop:' + tile['crop']
    if tile.get('kind') == 'WEED':
        return 'weed'
    if tile.get('animal'):
        return 'animal:' + tile['animal']
    return 'structure_empty'


def board_hours(farm):
    counts = Counter()
    for row in farm['tiles']:
        for tile in row:
            state = tile_state(tile)
            if state:
                counts[state] += 1
    return counts


def instrument(E, physical, seats, active, step):
    unit = E._apply_unit_action

    def work(farm, private, idx, action, *args, **kwargs):
        if not active[0] or id(farm) not in seats:
            return unit(farm, private, idx, action, *args, **kwargs)
        row = physical[seats[id(farm)]]
        if idx >= len(private['inventories']):
            row['missing_worker_commands'] += 1
            return unit(farm, private, idx, action, *args, **kwargs)
        if not isinstance(action, list) or not action or not isinstance(action[0], str):
            row['malformed_commands'] += 1
            return unit(farm, private, idx, action, *args, **kwargs)
        op = action[0]
        row['commands'] += 1
        row['commands_hand' if idx > 0 else 'commands_farmer'] += 1
        row['op:' + op] += 1
        before = deepcopy(private['inventories'][idx])
        seeds0 = dict(private['seeds'])
        pos = E._farmer_position(farm, idx)
        tile0 = deepcopy(farm['tiles'][pos[1]][pos[0]]) if pos else None
        pos0 = list(pos) if pos else None
        value = unit(farm, private, idx, action, *args, **kwargs)
        after = private['inventories'][idx]
        if op in E.FARMER_MOVES:
            row['moves'] += 1
            if pos0 == list(E._farmer_position(farm, idx) or []):
                row['moves_blocked'] += 1
        elif op == 'PASS':
            pass
        else:
            tile1 = farm['tiles'][pos[1]][pos[0]] if pos else None
            if before == after and tile0 == tile1 and seeds0 == private['seeds'] \
                    and op not in ('DROP', 'PLACE', 'PICKUP'):
                row['no_effect'] += 1
                row['no_effect:' + op] += 1
            elif op in ('DROP', 'PLACE', 'PICKUP') and before == after:
                row['no_effect'] += 1
                row['no_effect:' + op] += 1
            else:
                row['effective'] += 1
        if op in ('HARVEST', 'COLLECT_FERTILIZER'):
            for item in E.PRODUCTS:
                gained = after.get(item, 0) - before.get(item, 0)
                if gained > 0:
                    row['produced:' + item] += gained
        return value
    return unit, work


def finish(physical, hours, ledgers, rewards, hires, extra):
    out = []
    for i in (0, 1):
        out.append(dict(physical=dict(physical[i]), tile_hours=dict(hours[i]),
                        revenue=dict(ledgers[i]['revenue']), sold_units=dict(ledgers[i]['sold_units']),
                        spend=dict(ledgers[i]['spend']), cash=rewards[i], hires_requested=hires[i], **extra[i]))
    return out


def run_replay(path):
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    replay = json.loads(path.read_text(encoding='utf-8'))
    eid = replay['info']['EpisodeId']
    env = make('kaggriculture', configuration=replay['configuration'], info={'seed': replay['info']['seed']})
    physical = [Counter(), Counter()]
    hours = [Counter(), Counter()]
    hires = [0, 0]
    seats, active, step = {}, [False], [0]
    interpreter = env.interpreter
    unit, work = instrument(E, physical, seats, active, step)

    def real(state, environment):
        active[0] = True
        seats.clear()
        seats.update({id(f): i for i, f in enumerate(state[0].observation.farms)})
        try:
            return interpreter(state, environment)
        finally:
            active[0] = False

    def player(i):
        def act(obs):
            t = int(obs['step'])
            hours[i].update(board_hours(obs['farms'][i]))
            action = deepcopy(replay['steps'][t + 1][i]['action'])
            for order in (action or {}).get('market') or []:
                if isinstance(order, (list, tuple)) and order and order[0] == 'HIRE':
                    hires[i] += 1
            return action
        return act

    E._apply_unit_action = work
    env.interpreter = real
    try:
        with Ledger(E) as ledger:
            env.run([player(0), player(1)])
            for i in (0, 1):
                assert 3000 + sum(ledger.data[i]['revenue'].values()) - sum(ledger.data[i]['spend'].values()) \
                    == env.state[i].reward, eid
            ledgers = [ledger.data[0], ledger.data[1]]
    finally:
        E._apply_unit_action = unit
        env.interpreter = interpreter
    for t, states in enumerate(env.steps):
        for i in (0, 1):
            assert states[i].observation['farms'] == replay['steps'][t][i]['observation']['farms'], (eid, t, i)
    rows = finish(physical, hours, ledgers, [s.reward for s in env.state], hires,
                  [dict(team=replay['info']['TeamNames'][i]) for i in (0, 1)])
    result = dict(kind='replay', episode=eid, teams=replay['info']['TeamNames'], seats=rows)
    (OUT / 'replays' / f'eff-{eid}.json').write_text(json.dumps(result), encoding='utf-8')
    return eid


def run_ours(job):
    seed, seat, opponent = job
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    own = get_last_callable(BENCH.read_text(encoding='utf-8'), path=str(BENCH))
    rival_path = OPPONENTS[opponent]
    rival = get_last_callable(rival_path.read_text(encoding='utf-8'), path=str(rival_path))
    env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': seed})
    physical = [Counter(), Counter()]
    hours = [Counter(), Counter()]
    hires = [0, 0]
    seats, active, step = {}, [False], [0]
    interpreter = env.interpreter
    unit, work = instrument(E, physical, seats, active, step)

    def real(state, environment):
        active[0] = True
        seats.clear()
        seats.update({id(f): i for i, f in enumerate(state[0].observation.farms)})
        try:
            return interpreter(state, environment)
        finally:
            active[0] = False

    def player(i, fn):
        def act(obs):
            hours[i].update(board_hours(obs['farms'][i]))
            action = fn(obs)
            for order in (action or {}).get('market') or []:
                if isinstance(order, (list, tuple)) and order and order[0] == 'HIRE':
                    hires[i] += 1
            return action
        return act

    players = [None, None]
    players[seat] = player(seat, own)
    players[1 - seat] = player(1 - seat, rival)
    E._apply_unit_action = work
    env.interpreter = real
    try:
        with Ledger(E) as ledger:
            env.run(players)
            assert len(env.steps) == 720 and all(s.status == 'DONE' for s in env.state), job
            for i in (0, 1):
                assert 3000 + sum(ledger.data[i]['revenue'].values()) - sum(ledger.data[i]['spend'].values()) \
                    == env.state[i].reward, job
            ledgers = [ledger.data[0], ledger.data[1]]
    finally:
        E._apply_unit_action = unit
        env.interpreter = interpreter
    names = ['benchmark' if i == seat else opponent for i in (0, 1)]
    rows = finish(physical, hours, ledgers, [s.reward for s in env.state], hires,
                  [dict(team=names[i]) for i in (0, 1)])
    tag = f'bench-vs-{opponent}-{seed}-{seat}'
    (OUT / 'ours' / f'eff-{tag}.json').write_text(json.dumps(dict(kind='ours', tag=tag, seed=seed, seat=seat,
                                                                  opponent=opponent, seats=rows)), encoding='utf-8')
    return tag


def run_replace(path):
    """Our frozen benchmark in Mother-Goose's seat of a recorded game: same seed, the recorded shop
    sequence forced, the opponent's recorded actions. A diagnostic, not a match: the recorded
    opponent cannot react to the changed market, as docs/leader_opening.md notes for the same
    control on Majkel1337."""
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    replay = json.loads(path.read_text(encoding='utf-8'))
    eid = replay['info']['EpisodeId']
    teams = replay['info']['TeamNames']
    if 'Unknown Mother-Goose' not in teams:
        return None
    seat = teams.index('Unknown Mother-Goose')
    own = get_last_callable(BENCH.read_text(encoding='utf-8'), path=str(BENCH))
    env = make('kaggriculture', configuration=replay['configuration'], info={'seed': replay['info']['seed']})
    physical = [Counter(), Counter()]
    hours = [Counter(), Counter()]
    hires = [0, 0]
    seats, active, step = {}, [False], [0]
    interpreter = env.interpreter
    unit, work = instrument(E, physical, seats, active, step)
    end = E._end_of_day

    def locked(state, environment, day):
        end(state, environment, day)
        state[0].observation.town.unlocked_shops[:] =             replay['steps'][min(719, (day + 1) * 24)][0]['observation']['town']['unlocked_shops']

    def real(state, environment):
        active[0] = True
        seats.clear()
        seats.update({id(f): i for i, f in enumerate(state[0].observation.farms)})
        try:
            return interpreter(state, environment)
        finally:
            active[0] = False

    def player(i):
        def act(obs):
            t = int(obs['step'])
            hours[i].update(board_hours(obs['farms'][i]))
            action = own(obs) if i == seat else deepcopy(replay['steps'][t + 1][i]['action'])
            for order in (action or {}).get('market') or []:
                if isinstance(order, (list, tuple)) and order and order[0] == 'HIRE':
                    hires[i] += 1
            return action
        return act

    E._apply_unit_action, E._end_of_day = work, locked
    env.interpreter = real
    try:
        with Ledger(E) as ledger:
            env.run([player(0), player(1)])
            assert len(env.steps) == 720 and all(s.status == 'DONE' for s in env.state), eid
            for i in (0, 1):
                assert 3000 + sum(ledger.data[i]['revenue'].values()) - sum(ledger.data[i]['spend'].values())                     == env.state[i].reward, eid
            ledgers = [ledger.data[0], ledger.data[1]]
    finally:
        E._apply_unit_action, E._end_of_day = unit, end
        env.interpreter = interpreter
    names = ['benchmark' if i == seat else teams[i] for i in (0, 1)]
    rows = finish(physical, hours, ledgers, [s.reward for s in env.state], hires,
                  [dict(team=names[i]) for i in (0, 1)])
    (OUT / 'replace' / f'eff-replace-{eid}.json').write_text(json.dumps(dict(
        kind='replace', episode=eid, seat=seat, teams=names, original_rewards=replay['rewards'],
        seats=rows)), encoding='utf-8')
    return eid


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'replays'
    (OUT / 'replays').mkdir(parents=True, exist_ok=True)
    (OUT / 'ours').mkdir(parents=True, exist_ok=True)
    (OUT / 'replace').mkdir(parents=True, exist_ok=True)
    if mode == 'replace':
        paths = sorted(REPLAYS.glob('episode-*-replay.json'))
        with ProcessPoolExecutor(max_workers=4, max_tasks_per_child=1) as pool:
            for f in as_completed([pool.submit(run_replace, p) for p in paths]):
                if f.result():
                    print('replace', f.result(), flush=True)
        return
    if mode == 'replays':
        paths = sorted(REPLAYS.glob('episode-*-replay.json'))
        todo = [p for p in paths if not (OUT / 'replays' / f'eff-{p.name.split("-")[1]}.json').exists()]
        with ProcessPoolExecutor(max_workers=4, max_tasks_per_child=1) as pool:
            for f in as_completed([pool.submit(run_replay, p) for p in todo]):
                print('replay', f.result(), flush=True)
    else:
        opponent = sys.argv[2] if len(sys.argv) > 2 else 'self'
        base = int(sys.argv[3]) if len(sys.argv) > 3 else 172000
        n = int(sys.argv[4]) if len(sys.argv) > 4 else 16
        # In self-play both seats are the same deterministic policy and play identically, so one seat
        # per seed is one independent sample; against another opponent both seats are informative.
        seats = (0,) if opponent == 'self' else (0, 1)
        jobs = [(s, seat, opponent) for s in range(base, base + n) for seat in seats]
        with ProcessPoolExecutor(max_workers=4, max_tasks_per_child=1) as pool:
            for f in as_completed([pool.submit(run_ours, j) for j in jobs]):
                print('ours', f.result(), flush=True)


if __name__ == '__main__':
    main()
