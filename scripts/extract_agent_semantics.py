"""AGENT variant of extract_leader_semantics.py: the leader's seat is played LIVE by one of our agents (same world:
seed, forced shops, the opponent's recorded actions), and the game is extracted in the leader corpus's format, so our
agent's semantics compare like for like with the leader's. usage: extract_agent_semantics.py <agent.py> <out_dir> <tape.json.gz>...
"""
"""Semantic extraction for leader tapes (2026-09-24 harvest task, Part 2).

For each compact leader tape (scripts/harvest_leader_tapes.py output), replay BOTH
seats' recorded actions through the OFFICIAL kaggriculture engine with the recorded
seed and a forced shop-reveal schedule (reconstructed from the tape's flat
reveal-order list under the default 3-day/8-instance shop-unlock rule; see
docs/environment.md), exactly the way scripts/ladder_panel.py::run forces shops via
scripts/tape_vs_bench.py::_play (E._end_of_day is replaced to overwrite
unlocked_shops right after the real day-end runs, so the day-boundary RNG draws stay
in lockstep with the recorded episode). To see which commands took effect and on
which tile, this hooks E._commit_unit / E._apply_unit_action / E._do_hire the way
scripts/value_tape_search.py::rollout does (wrap, call the original, diff
before/after, restore in `finally`).

Verifies both players' final cash equals the recorded rewards; a mismatch sets
meta.cash_match=False but the game's data is still written (not dropped).

Output: one gzip json per game, LEADER's seat only:
  data/leader_semantics/<team_id>/<episode>.json.gz
Schema: data/leader_semantics/README.md

usage: extract_leader_semantics.py <team_id>:<dirname>[,<team_id>:<dirname>...] [--limit N] [--workers N]
  e.g. extract_leader_semantics.py 16915014:16915014_56484772 --limit 40
"""
import gzip
import json
import sys
import traceback
from collections import Counter
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAPES = ROOT / 'data/leader_tapes'
OUT = ROOT / 'data/leader_semantics'

BOARD = 10
CROP_LABEL = {'WHEAT': 'WH', 'CARROT': 'CA', 'TOMATO': 'TO', 'STRAWBERRY': 'ST', 'MELON': 'ME'}
LABEL_CROP = {v: k for k, v in CROP_LABEL.items()}
ANIMAL_LABEL = {'SHEEP': 'sh', 'COW': 'co', 'GOOSE': 'go'}
LABEL_ANIMAL = {v: k for k, v in ANIMAL_LABEL.items()}
MAINT_OPS = ('WATER', 'FEED', 'CARE', 'FERTILIZE')
MOVE_OPS = ('NORTH', 'SOUTH', 'EAST', 'WEST')


def label(tile):
    if tile == 'LOCKED':
        return ' L'
    if tile is None:
        return ' .'
    kind = tile.get('kind')
    if kind == 'PLANT':
        return str(tile.get('crop'))[:2]
    if kind == 'WEED':
        return ' .'
    if tile.get('animal'):
        return str(tile['animal'])[:2].lower()
    return str(kind)[:2].lower()


def board_labels(farm):
    return [label(t) for row in farm['tiles'] for t in row]


def shops_by_day_from_flat(shops):
    """Reconstruct the per-day-start unlocked_shops snapshot (length 31, index = day)
    from the tape's flat reveal-order list, using the default rule (docs/environment.md):
    townShopUnlockInterval=3, MAX_SHOP_INSTANCES=8 -> floor(day/3) shops visible at the
    start of `day` (capped at len(shops))."""
    return [list(shops[:min(8, d // 3)]) for d in range(31)]


def new_day():
    return dict(
        board=None, board_counts=None,
        planted={}, harvested={'units': {}, 'tiles': []},
        animals=dict(bought={}, placed=[], sold={}, culled=[]),
        built={}, dug=[],
        maintenance={op: [] for op in MAINT_OPS},
        eligible={'crops': {}, 'animals': {}},
        labour=dict(hires_asked=0, hires_arrived=0, hands_present=0,
                    command_counts={}, no_effect_commands=0),
        cash_start=None,
        market=dict(sold_units={}, sold_revenue={}, bought_units={}, bought_spend={}),
    )


def replay_one(path, team, agent_path=None):
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E

    g = json.loads(gzip.open(path, 'rt', encoding='utf-8').read())
    episode, seat, seed = g['episode'], g['seat'], g['seed']
    shops_flat = g['shops']
    shops_by_day = shops_by_day_from_flat(shops_flat)
    actions = [None, None]
    actions[seat] = g['actions']
    actions[1 - seat] = g['opp_actions']

    days = [new_day() for _ in range(30)]
    current_farms = []
    day_now = [0]

    old_apply, old_commit, old_hire, old_end = E._apply_unit_action, E._commit_unit, E._do_hire, E._end_of_day

    def pid_of(farm):
        # current_farms is refreshed at the top of every interpreter call (see `real` below), so this
        # never relies on a farm dict's id() staying stable across steps (it does in the current engine,
        # but a per-call refresh costs nothing and removes the assumption).
        for i, f in enumerate(current_farms):
            if farm is f:
                return i
        return None

    def apply_hook(farm, private, idx, action, board_size, day, turns_per_day, shed_capacity=100):
        pid = pid_of(farm)
        op = action[0] if isinstance(action, list) and action else None
        pos_before = E._farmer_position(farm, idx)
        tile_before, tidx = None, None
        if pos_before is not None:
            fx, fy = pos_before
            tidx = fy * board_size + fx
            t = farm['tiles'][fy][fx]
            tile_before = dict(t) if isinstance(t, dict) else t
        inv_before = dict(private['inventories'][idx]) if idx < len(private['inventories']) else {}
        result = old_apply(farm, private, idx, action, board_size, day, turns_per_day, shed_capacity)
        if pid != seat or op is None:
            return result
        d = days[day]
        bucket = 'MOVE' if op in MOVE_OPS else op
        d['labour']['command_counts'][bucket] = d['labour']['command_counts'].get(bucket, 0) + 1
        pos_after = E._farmer_position(farm, idx)
        tile_after = None
        if pos_after is not None:
            fx2, fy2 = pos_after
            t2 = farm['tiles'][fy2][fx2]
            tile_after = dict(t2) if isinstance(t2, dict) else t2
        inv_after = dict(private['inventories'][idx]) if idx < len(private['inventories']) else {}
        no_effect = op != 'PASS' and pos_before == pos_after and tile_before == tile_after and inv_before == inv_after
        if no_effect:
            d['labour']['no_effect_commands'] += 1
        if op == 'PLANT' and tile_before is None and isinstance(tile_after, dict) and tile_after.get('kind') == 'PLANT':
            d['planted'].setdefault(tile_after['crop'], []).append(tidx)
        elif op == 'HARVEST':
            gained = {k: inv_after.get(k, 0) - inv_before.get(k, 0) for k in inv_after if inv_after.get(k, 0) > inv_before.get(k, 0)}
            if gained:
                for prod, n in gained.items():
                    d['harvested']['units'][prod] = d['harvested']['units'].get(prod, 0) + n
                d['harvested']['tiles'].append(tidx)
        elif op == 'PLACE' and len(action) > 1:
            item = action[1]
            if isinstance(tile_before, dict) and 'animal' not in tile_before and isinstance(tile_after, dict) and tile_after.get('animal') == item:
                d['animals']['placed'].append(tidx)
        elif op in ('BUILD_COOP', 'BUILD_PASTURE'):
            if tile_before is None and isinstance(tile_after, dict):
                d['built'].setdefault(op, []).append(tidx)
        elif op == 'DIG':
            if tile_before is not None and tile_after is None:
                d['dug'].append(tidx)
        elif op in MAINT_OPS:
            if isinstance(tile_before, dict) and isinstance(tile_after, dict):
                changed = False
                if op == 'WATER' and not tile_before.get('watered_today') and tile_after.get('watered_today'):
                    changed = True
                if op == 'FEED' and not tile_before.get('fed_today') and tile_after.get('fed_today'):
                    changed = True
                if op == 'CARE' and not tile_before.get('cared_today') and tile_after.get('cared_today'):
                    changed = True
                if op == 'FERTILIZE' and tile_before.get('fertilized_until_day') != tile_after.get('fertilized_until_day'):
                    changed = True
                if changed:
                    d['maintenance'][op].append(tidx)
        return result

    def commit_hook(op, item, price, farm, private, market, shed_capacity=100):
        pid = pid_of(farm)
        result = old_commit(op, item, price, farm, private, market, shed_capacity)
        if pid == seat and result:
            d = days[day_now[0]]
            if op == 'SELL':
                d['market']['sold_units'][item] = d['market']['sold_units'].get(item, 0) + 1
                d['market']['sold_revenue'][item] = d['market']['sold_revenue'].get(item, 0) + price
                if item in ANIMAL_LABEL:
                    d['animals']['sold'][item] = d['animals']['sold'].get(item, 0) + 1
            elif op in ('BUY_PRODUCT', 'BUY_SEED', 'BUY_ANIMAL'):
                d['market']['bought_units'][item] = d['market']['bought_units'].get(item, 0) + 1
                d['market']['bought_spend'][item] = d['market']['bought_spend'].get(item, 0) + price
                if op == 'BUY_ANIMAL':
                    d['animals']['bought'][item] = d['animals']['bought'].get(item, 0) + 1
        return result

    def hire_hook(farm, private, board_size, mult=1):
        pid = pid_of(farm)
        before = len(farm['hands'])
        old_hire(farm, private, board_size, mult)
        if pid == seat and len(farm['hands']) > before:
            days[day_now[0]]['labour']['hires_arrived'] += 1

    def end_hook(state, environment, day):
        day_now[0] = day
        farm = state[0].observation.farms[seat]
        days[day]['labour']['hands_present'] = len(farm['hands'])
        old_end(state, environment, day)
        state[0].observation.town.unlocked_shops[:] = shops_by_day[min(len(shops_by_day) - 1, day + 1)]

    interpreter_box = {}

    def real(state, environment):
        farms = getattr(state[0].observation, 'farms', None)
        if farms:
            current_farms[:] = farms
        return interpreter_box['orig'](state, environment)

    E._apply_unit_action, E._commit_unit, E._do_hire, E._end_of_day = apply_hook, commit_hook, hire_hook, end_hook
    try:
        env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': seed})
        interpreter_box['orig'] = env.interpreter
        env.interpreter = real

        live = None
        if agent_path is not None:                     # our agent plays the leader's seat, live
            from kaggle_environments.agent import get_last_callable
            live = get_last_callable(Path(agent_path).read_text(encoding='utf-8'), path=str(agent_path))

        def player(i):
            def act(obs):
                t = int(obs['step'])
                d, h = divmod(t, 24)
                if i == seat and live is not None:
                    a = live(obs) or {}
                else:
                    a = actions[i][t] if t < len(actions[i]) else {}
                if i == seat:
                    if h == 0:
                        dd = days[d]
                        dd['board'] = board_labels(obs['farms'][seat])
                        dd['board_counts'] = dict(Counter(dd['board']))
                        dd['cash_start'] = obs['farms'][seat]['money']
                        dd['eligible']['crops'] = {LABEL_CROP[l]: c for l, c in dd['board_counts'].items() if l in LABEL_CROP}
                        dd['eligible']['animals'] = {LABEL_ANIMAL[l]: c for l, c in dd['board_counts'].items() if l in LABEL_ANIMAL}
                    n = sum(1 for o in (a.get('market') or [])[:10] if o and isinstance(o, (list, tuple)) and o and o[0] == 'HIRE')
                    days[d]['labour']['hires_asked'] += n
                return deepcopy(a) if a else {'farmer': ['PASS'], 'hands': [], 'market': []}
            return act

        env.run([player(0), player(1)])
        final = [float(s.reward) for s in env.state]
    finally:
        E._apply_unit_action, E._commit_unit, E._do_hire, E._end_of_day = old_apply, old_commit, old_hire, old_end

    cash_match = bool(round(final[0]) == round(g['rewards'][0]) and round(final[1]) == round(g['rewards'][1]))

    # Culled = an animal-letter tile at day d's start is gone (not via PLACE) by day d+1's start.
    for d in range(29):
        b0, b1 = days[d]['board'], days[d + 1]['board']
        if b0 is None or b1 is None:
            continue
        placed_next = set(days[d + 1]['animals']['placed'])
        for idx in range(100):
            if b0[idx] in LABEL_ANIMAL and b1[idx] not in LABEL_ANIMAL and idx not in placed_next:
                days[d]['animals']['culled'].append(idx)

    opponent = next((n for i, n in enumerate(g.get('names') or []) if i != seat), None)
    return dict(
        meta=dict(episode=episode, team=team, seat=seat, seed=seed, rewards=g['rewards'],
                  final_cash=final, opponent=opponent, cash_match=cash_match),
        shops=[dict(shop=s, reveal_day=3 * (i + 1)) for i, s in enumerate(shops_flat)],
        days=days,
    )


def job(args):
    path, team, team_id = args
    episode = path.name.split('.')[0]
    outp = OUT / str(team_id) / f'{episode}.json.gz'
    if outp.exists():
        return ('skip', episode, None)
    try:
        result = replay_one(path, team)
        outp.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(outp, 'wt', encoding='utf-8') as f:
            json.dump(result, f, separators=(',', ':'))
        return ('ok' if result['meta']['cash_match'] else 'mismatch', episode, None)
    except Exception as exc:
        return ('FAILED', episode, f'{type(exc).__name__}: {exc}\n{traceback.format_exc()[-1500:]}')


def main():
    argv = sys.argv[1:]
    limit = None
    workers = 2
    specs = []
    i = 0
    while i < len(argv):
        if argv[i] == '--limit':
            limit = int(argv[i + 1]); i += 2
        elif argv[i] == '--workers':
            workers = int(argv[i + 1]); i += 2
        else:
            specs.append(argv[i]); i += 1
    if not specs:
        print(__doc__); return
    jobs = []
    for spec in specs[0].split(','):
        team_id_s, dirname = spec.split(':')
        team_id = int(team_id_s)
        tdir = TAPES / dirname
        idx = json.loads((tdir / 'index.json').read_text(encoding='utf-8'))
        team = idx.get('team', str(team_id))
        paths = sorted(tdir.glob('*.json.gz'))
        if limit:
            paths = paths[:limit]
        jobs += [(p, team, team_id) for p in paths]
    print(f'{len(jobs)} games to extract, {workers} worker(s)', flush=True)
    from concurrent.futures import ProcessPoolExecutor, as_completed
    counts = Counter()
    fails = []
    if workers <= 1:
        results = (job(j) for j in jobs)
        for st, ep, err in results:
            counts[st] += 1
            print(f'{st:8s} {ep}' + (f'  {err.splitlines()[0]}' if err else ''), flush=True)
            if err:
                fails.append((ep, err))
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for st, ep, err in pool.map(job, jobs):
                counts[st] += 1
                print(f'{st:8s} {ep}' + (f'  {err.splitlines()[0]}' if err else ''), flush=True)
                if err:
                    fails.append((ep, err))
    print('summary:', dict(counts), flush=True)
    if fails:
        print(f'{len(fails)} failures, first one:', flush=True)
        print(fails[0][1], flush=True)


def agent_main():
    agent, out = sys.argv[1], Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    for p in sys.argv[3:]:
        p = Path(p)
        r = replay_one(p, 'agent', agent_path=agent)
        with gzip.open(out / p.name, 'wt', encoding='utf-8') as f:
            json.dump(r, f, separators=(',', ':'))
        print(p.name, 'final', r['meta']['final_cash'], 'recorded', r['meta']['rewards'], flush=True)


if __name__ == '__main__':
    agent_main()
