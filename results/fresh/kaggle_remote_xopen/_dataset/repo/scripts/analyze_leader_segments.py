"""Per-3-day-segment behaviour and per-step digests for top-two leader replays.

Exactly replays each downloaded public episode with the official engine, validating every
state, and records for BOTH seats: successful transactions per segment (Ledger), physical
command counts, board composition at segment boundaries, market requests, and per-step
observation/action digests used by the adaptation tests in report_leader_segments.py.

Segments are the engine's shop cadence: 3 days = 72 steps. A shop unlocks at the start of
days 3..24 (townShopUnlockInterval 3, MAX_SHOP_INSTANCES 8), so segment 0 has no shop and
segment 9 gets no new shop.
"""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from hashlib import sha256, sha1
import json, time
from market_corpus import ROOT
from evaluate_boards import Ledger

REPLAYS = ROOT / 'data/leaders_20260917'
OUT = ROOT / 'results/fresh/leader_segments'
SEGMENT_STEPS = 72
SEGMENTS = 10


def _digest(value):
    return sha1(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()[:10]


def board(farm):
    counts = Counter()
    for row in farm['tiles']:
        for tile in row:
            if tile is None:
                counts['EMPTY'] += 1
            elif tile == 'LOCKED':
                counts['LOCKED'] += 1
            elif tile.get('kind') == 'PLANT':
                counts[tile['crop']] += 1
            elif tile.get('kind') == 'WEED':
                counts['WEED'] += 1
            elif tile.get('animal'):
                counts[tile['animal']] += 1
            else:
                counts['EMPTY_' + tile['kind']] += 1
    return dict(counts)


def _ledger_totals(row):
    return dict(revenue=dict(row['revenue']), sold_units=dict(row['sold_units']), spend=dict(row['spend']))


def _delta(now, before):
    out = {}
    for field in ('revenue', 'sold_units', 'spend'):
        diff = {k: now[field][k] - before[field].get(k, 0) for k in now[field]}
        out[field] = {k: v for k, v in diff.items() if v}
    return out


def run(path):
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E

    replay = json.loads(path.read_text(encoding='utf-8'))
    eid = replay['info']['EpisodeId']
    teams = replay['info']['TeamNames']
    env = make('kaggriculture', configuration=replay['configuration'], info={'seed': replay['info']['seed']})
    unit = E._apply_unit_action
    interpreter = env.interpreter
    active = [False]
    seats = {}
    step = [0]
    physical = [[Counter() for _ in range(SEGMENTS)] for _ in range(2)]
    requests = [[Counter() for _ in range(SEGMENTS)] for _ in range(2)]
    hires = [Counter(), Counter()]
    boards = [{}, {}]
    cash = [{}, {}]
    shops_at = {}
    digests = [{k: [] for k in ('own_tiles', 'own_farm', 'opp_farm', 'market', 'shops', 'private', 'action')}
               for _ in range(2)]
    actions = [[], []]

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
        seat = seats[id(farm)]
        row = physical[seat][min(SEGMENTS - 1, step[0] // SEGMENT_STEPS)]
        if idx >= len(private['inventories']):
            row['missing_worker_commands'] += 1
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
    with Ledger(E) as ledger:
        marks = [[], []]

        def player(i):
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
                action = deepcopy(replay['steps'][t + 1][i]['action'])
                digests[i]['action'].append(_digest(action))
                actions[i].append(action)
                row = requests[i][min(SEGMENTS - 1, segment)]
                for order in action.get('market') or []:
                    # Agents emit malformed/empty orders; the engine ignores them, so must we.
                    if not isinstance(order, (list, tuple)) or not order or not isinstance(order[0], str):
                        row['req:MALFORMED'] += 1
                        continue
                    op = order[0]
                    item = order[1] if len(order) > 1 and isinstance(order[1], str) else ''
                    units = int(order[2]) if len(order) > 2 else 1
                    row['req:' + op + (':' + item if item else '')] += 1
                    row['units:' + op + (':' + item if item else '')] += units
                    if op == 'HIRE':
                        hires[i][t // 24] += 1
                return action
            return act

        try:
            env.run([player(0), player(1)])
        finally:
            E._apply_unit_action = unit
            env.interpreter = interpreter
        assert len(env.steps) == 720 and all(s.status == 'DONE' for s in env.state), eid
        for t, states in enumerate(env.steps):
            for i in (0, 1):
                for field in ('farms', 'market', 'town', 'private'):
                    assert states[i].observation[field] == replay['steps'][t][i]['observation'][field], (eid, t, i, field)
        for i in (0, 1):
            assert 3000 + sum(ledger.data[i]['revenue'].values()) - sum(ledger.data[i]['spend'].values()) == env.state[i].reward, eid
            marks[i].append(_ledger_totals(ledger.data[i]))
            boards[i][SEGMENTS] = board(env.state[0].observation.farms[i])
            cash[i][SEGMENTS] = env.state[i].reward

    seat_rows = []
    for i in (0, 1):
        segs = []
        for s in range(SEGMENTS):
            segs.append(dict(segment=s, days=[s * 3, s * 3 + 2], shops_at_start=shops_at.get(s, []),
                             cash_start=cash[i].get(s), cash_end=cash[i].get(s + 1),
                             board_start=boards[i].get(s), board_end=boards[i].get(s + 1),
                             physical=dict(physical[i][s]), requests=dict(requests[i][s]),
                             ledger=_delta(marks[i][s + 1], marks[i][s])))
        seat_rows.append(dict(seat=i, team=teams[i], reward=replay['rewards'][i], segments=segs,
                              hires_by_day={str(k): v for k, v in sorted(hires[i].items())},
                              ledger_total=_ledger_totals(ledger.data[i])))
    result = dict(episode=eid, teams=teams, seed=replay['info']['seed'], rewards=replay['rewards'],
                  configuration=replay['configuration'], shops_by_segment=shops_at,
                  replay_sha256=sha256(path.read_bytes()).hexdigest(), seats=seat_rows)
    (OUT / f'segments-{eid}.json').write_text(json.dumps(result, indent=1), encoding='utf-8')
    (OUT / 'digests' / f'digests-{eid}.json').write_text(json.dumps(
        dict(episode=eid, teams=teams, shops_by_segment=shops_at,
             seats=[{k: ''.join(v) for k, v in d.items()} for d in digests]), indent=1), encoding='utf-8')
    (OUT / 'actions' / f'actions-{eid}.json').write_text(json.dumps(
        dict(episode=eid, teams=teams, actions=actions)), encoding='utf-8')
    return eid


def main():
    for sub in ('digests', 'actions'):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    paths = sorted(REPLAYS.glob('episode-*-replay.json'))
    manifest = dict(retrieved_at=time.strftime('%Y-%m-%d %H:%M:%S'),
                    teams={'16718819': 'Majkel1337 (rank 1, best submission 56216119)',
                           '16730612': 'Unknown Mother-Goose (rank 2, best submission 56266758)'},
                    segment_steps=SEGMENT_STEPS, segments=SEGMENTS,
                    design='52 public episodes: 8 head-to-head, 8 per leader against one repeated opponent '
                           'submission, 14 per leader against distinct high-scoring opponents. Exact replay only; '
                           'no substitute agents. Both seats recorded in every game.',
                    episodes=[p.name for p in paths],
                    replays={p.name: sha256(p.read_bytes()).hexdigest() for p in paths})
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=1), encoding='utf-8')
    todo = [p for p in paths if not (OUT / f'segments-{p.name.split("-")[1]}.json').exists()]
    print('episodes', len(paths), 'to process', len(todo), flush=True)
    with ProcessPoolExecutor(max_workers=4, max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run, p) for p in todo]):
            print('completed', f.result(), flush=True)


if __name__ == '__main__':
    main()
