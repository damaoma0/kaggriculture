"""Same per-3-day-segment profile as analyze_leader_segments.py, for our own agents.

Runs live games with the official engine so our agent's segment behaviour can be compared with
the leaders' recorded games on identical metrics. Natural engine RNG for shops and weeds.
"""
from concurrent.futures import ProcessPoolExecutor, as_completed
from hashlib import sha256
import json, time
from market_corpus import ROOT, load
from evaluate_boards import Ledger
from analyze_leader_segments import board, SEGMENT_STEPS, SEGMENTS, _ledger_totals, _delta, _digest

OUT = ROOT / 'results/fresh/leader_segments/ours'
PATHS = {
    'bench': ROOT / 'agents/benchmark_frozen_56280048.py',     # frozen benchmark = submission 56280048
    'upload': ROOT / 'agents/v45_event_candidate.py',          # submission 56280048
    'ours_base': ROOT / 'agents/v45_event_opening_fixed.py',   # retained local baseline
    'v45': ROOT / 'data/router_refresh_20260916/v45/main.py',  # stock public V45
    'twocoins': ROOT / 'data/router_refresh_20260916/twocoins/main.py',
}


def run(job):
    seed, seat, policy, opponent = job
    from collections import Counter
    from copy import deepcopy
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E

    # Kaggle's own loader: in the uploaded file the last callable is not the module's `agent`, so
    # importing the module and calling .agent would run a different wrapper than the ladder does.
    from kaggle_environments.agent import get_last_callable

    class _Entry:
        def __init__(self, path):
            self.agent = get_last_callable(path.read_text(encoding='utf-8'), path=str(path))
    own = _Entry(PATHS[policy])
    rival = _Entry(PATHS[opponent])
    env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': seed})
    unit = E._apply_unit_action
    interpreter = env.interpreter
    active = [False]
    seats = {}
    step = [0]
    physical = [[Counter() for _ in range(SEGMENTS)] for _ in range(2)]
    requests = [[Counter() for _ in range(SEGMENTS)] for _ in range(2)]
    boards = [{}, {}]
    cash = [{}, {}]
    shops_at = {}
    marks = [[], []]
    digests = [{k: [] for k in ('own_tiles', 'own_farm', 'opp_farm', 'market', 'shops', 'private', 'action')}
               for _ in range(2)]

    def real(state, environment):
        active[0] = True
        step[0] = int(state[0].observation.step)
        seats.clear()
        seats.update({id(f): i for i, f in enumerate(state[0].observation.farms)})
        try:
            return interpreter(state, environment)
        finally:
            active[0] = False

    def work(farm, private, idx, action, *args, **kwargs):
        if not active[0] or id(farm) not in seats:
            return unit(farm, private, idx, action, *args, **kwargs)
        i = seats[id(farm)]
        row = physical[i][min(SEGMENTS - 1, step[0] // SEGMENT_STEPS)]
        if idx >= len(private['inventories']):
            row['missing_worker_commands'] += 1
            return unit(farm, private, idx, action, *args, **kwargs)
        if not isinstance(action, list) or not action or not isinstance(action[0], str):
            return unit(farm, private, idx, action, *args, **kwargs)
        op = action[0]
        row['commands'] += 1
        row['op:' + op] += 1
        if op in E.FARMER_MOVES:
            row['moves'] += 1
        before = deepcopy(private['inventories'][idx])
        seeds0 = dict(private['seeds'])
        pos = E._farmer_position(farm, idx)
        tile0 = deepcopy(farm['tiles'][pos[1]][pos[0]]) if pos else None
        value = unit(farm, private, idx, action, *args, **kwargs)
        after = private['inventories'][idx]
        if op in ('HARVEST', 'COLLECT_FERTILIZER'):
            for item in E.PRODUCTS:
                gained = after.get(item, 0) - before.get(item, 0)
                if gained > 0:
                    row['produced:' + item] += gained
        if op == 'FEED':
            row['wheat_fed'] += before.get('WHEAT', 0) - after.get('WHEAT', 0)
        if op == 'FERTILIZE':
            row['fertilizer_applied'] += before.get('FERTILIZER', 0) - after.get('FERTILIZER', 0)
        if op == 'PLANT':
            for crop in E.CROPS:
                if seeds0.get(crop, 0) - private['seeds'].get(crop, 0) > 0:
                    row['planted:' + crop] += 1
        if op in ('PLANT', 'HARVEST', 'WATER', 'CARE', 'FEED', 'FERTILIZE', 'COLLECT_FERTILIZER', 'DIG'):
            tile1 = farm['tiles'][pos[1]][pos[0]] if pos else None
            if before == after and tile0 == tile1 and seeds0 == private['seeds']:
                row['no_effect:' + op] += 1
        return value

    E._apply_unit_action = work
    env.interpreter = real
    times = [[], []]
    with Ledger(E) as ledger:
        def player(i, module):
            def act(obs):
                t = int(obs['step'])
                segment = t // SEGMENT_STEPS
                if t % SEGMENT_STEPS == 0 and segment < SEGMENTS:
                    boards[i][segment] = board(obs['farms'][i])
                    cash[i][segment] = obs['farms'][i]['money']
                    marks[i].append(_ledger_totals(ledger.data[i]))
                    if i == 0:
                        shops_at[segment] = list(obs['town']['unlocked_shops'])
                farm_me, farm_op = obs['farms'][i], obs['farms'][1 - i]
                digests[i]['own_tiles'].append(_digest([farm_me['tiles'], farm_me['farmer'], farm_me['hands'],
                                                        farm_me['unlocked_quadrants'], farm_me['hires_today']]))
                digests[i]['own_farm'].append(_digest(farm_me))
                digests[i]['opp_farm'].append(_digest(farm_op))
                digests[i]['market'].append(_digest(obs['market']))
                digests[i]['shops'].append(_digest(sorted(obs['town']['unlocked_shops'])))
                digests[i]['private'].append(_digest(obs['private']))
                start = time.perf_counter()
                action = module.agent(obs)
                times[i].append(time.perf_counter() - start)
                digests[i]['action'].append(_digest(action))
                row = requests[i][min(SEGMENTS - 1, segment)]
                for order in (action or {}).get('market') or []:
                    if not isinstance(order, (list, tuple)) or not order or not isinstance(order[0], str):
                        row['req:MALFORMED'] += 1
                        continue
                    op = order[0]
                    item = order[1] if len(order) > 1 and isinstance(order[1], str) else ''
                    units = int(order[2]) if len(order) > 2 else 1
                    row['req:' + op + (':' + item if item else '')] += 1
                    row['units:' + op + (':' + item if item else '')] += units
                return action
            return act
        players = [None, None]
        players[seat] = player(seat, own)
        players[1 - seat] = player(1 - seat, rival)
        try:
            env.run(players)
        finally:
            E._apply_unit_action = unit
            env.interpreter = interpreter
        assert len(env.steps) == 720 and all(s.status == 'DONE' for s in env.state), job
        for i in (0, 1):
            assert 3000 + sum(ledger.data[i]['revenue'].values()) - sum(ledger.data[i]['spend'].values()) == env.state[i].reward, job
            marks[i].append(_ledger_totals(ledger.data[i]))
            boards[i][SEGMENTS] = board(env.state[0].observation.farms[i])
            cash[i][SEGMENTS] = env.state[i].reward

    names = [None, None]
    names[seat] = policy
    names[1 - seat] = opponent
    seat_rows = []
    for i in (0, 1):
        segs = [dict(segment=s, days=[s * 3, s * 3 + 2], shops_at_start=shops_at.get(s, []),
                     cash_start=cash[i].get(s), cash_end=cash[i].get(s + 1),
                     board_start=boards[i].get(s), board_end=boards[i].get(s + 1),
                     physical=dict(physical[i][s]), requests=dict(requests[i][s]),
                     ledger=_delta(marks[i][s + 1], marks[i][s])) for s in range(SEGMENTS)]
        seat_rows.append(dict(seat=i, team=names[i], reward=env.state[i].reward, segments=segs,
                              ledger_total=_ledger_totals(ledger.data[i])))
    tag = f'{policy}-vs-{opponent}-{seed}-{seat}'
    result = dict(tag=tag, seed=seed, seat=seat, policy=policy, opponent=opponent,
                  teams=names, rewards=[s.reward for s in env.state], shops_by_segment=shops_at,
                  max_seconds=[max(x) for x in times], seats=seat_rows)
    (OUT / f'segments-{tag}.json').write_text(json.dumps(result, indent=1), encoding='utf-8')
    (OUT / f'digests-{tag}.json').write_text(json.dumps(
        dict(tag=tag, teams=names, shops_by_segment=shops_at,
             seats=[{k: ''.join(v) for k, v in d.items()} for d in digests]), indent=1), encoding='utf-8')
    return tag


def jobs():
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'bench':
        # self-play is symmetric, so one seat per seed; against Two Coins both seats
        out = [(seed, 0, 'bench', 'bench') for seed in range(172000, 172016)]
        out += [(seed, seat, 'bench', 'twocoins') for seed in range(172000, 172016) for seat in (0, 1)]
        return out
    return [(seed, seat, 'upload', 'v45') for seed in range(161000, 161004) for seat in (0, 1)]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    todo = jobs()
    (OUT / 'manifest.json').write_text(json.dumps(dict(
        retrieved_at=time.strftime('%Y-%m-%d %H:%M:%S'), jobs=todo,
        purpose='Segment profile of our uploaded agent for comparison with leader replays. '
                'Natural engine RNG; no policy tuning or promotion.',
        sources={str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in sorted(set(PATHS.values()))},
    ), indent=1), encoding='utf-8')
    print('games', len(todo), flush=True)
    with ProcessPoolExecutor(max_workers=4, max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run, j) for j in todo]):
            print('completed', f.result(), flush=True)


if __name__ == '__main__':
    main()
