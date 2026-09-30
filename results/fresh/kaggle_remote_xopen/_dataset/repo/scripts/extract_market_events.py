"""Market EVENT log for a leader world (2026-09-24 market-mechanism thread; copy/variant of extract_agent_semantics.py).

Replays a leader tape (LEADER) or puts one of our agents in the leader's seat (same seed, forced shops, the opponent
replaying its recorded actions) and logs EVERY successful market transaction of BOTH players, with the exact position
inside the step. E._process_market is replaced by a logging copy of the engine function (identical logic, same helper
functions; the engine file is byte-identical to data/kaggriculture.py), E._town_consume and E._apply_unit_action are
wrapped. All hooks are restored in `finally`. For LEADER the final cash of both players is checked against the tape.

usage: extract_market_events.py <agent.py|LEADER>[,<agent.py|LEADER>...] <out_dir> <tape.json.gz>...
       (with several agents each writes to <out_dir>/<LEADER|agent file stem>/)

Output <out_dir>/<episode>.json.gz:
  meta: episode, seat (the leader's seat = the seat our agent plays), seed, rewards (recorded), final_cash (this run),
        cash_match (final == recorded, both players), agent, shops (flat reveal order)
  products: PRODUCTS order used by every per-product list below
  tx:   [step, order_idx, lock_iter, player, op, item, price, inv_before]  every SUCCESSFUL SELL / BUY_PRODUCT /
        BUY_SEED / BUY_ANIMAL unit. lock_iter = the per-unit lockstep iteration inside that order index (both players'
        units with the same (step, order_idx, lock_iter) were quoted from the same inventory; player 0 commits first).
        inv_before = market inventory of `item` just before this unit (SELL/BUY_PRODUCT only, else null).
  orders: [step, player, order_idx, op, item, n]  every SELL / BUY_PRODUCT order as submitted (after the 10-order cap)
  steps: per step t (0..719):
        inv_pre:  market inventory (PRODUCTS order) when the market phase starts (after unit actions)
        inv_post: market inventory after this step's town consumption (= what the next observation prices from)
        shed:     [p0, p1] shed stock per product at market start (private; after this step's unit actions)
        tile:     [p0, p1] harvestable yield on the board per product at market start (PUBLIC: plant/animal yield_units)
  harvest: [step, player, product, units]  successful HARVEST gains (unit inventory diff)
"""
import gzip
import json
import sys
import time
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def shops_by_day_from_flat(shops):
    return [list(shops[:min(8, d // 3)]) for d in range(31)]


def wait_for_memory(min_gb=3.0):
    try:
        import psutil
    except ImportError:
        return
    # free memory the machine would have without this (already running) process
    own = psutil.Process().memory_info().rss
    while (psutil.virtual_memory().available + own) / 1e9 < min_gb:
        print(f'  waiting: free memory {psutil.virtual_memory().available / 1e9:.2f} GB (+own {own / 1e9:.2f}) < {min_gb}',
              flush=True)
        time.sleep(30)
        own = psutil.Process().memory_info().rss


def replay_events(path, agent_path=None):
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E

    g = json.loads(gzip.open(path, 'rt', encoding='utf-8').read())
    episode, seat, seed = g['episode'], g['seat'], g['seed']
    shops_by_day = shops_by_day_from_flat(g['shops'])
    actions = [None, None]
    actions[seat] = g['actions']
    actions[1 - seat] = g['opp_actions']
    P = list(E.PRODUCTS)
    PIDX = {p: i for i, p in enumerate(P)}

    tx, orders, steps, harvest = [], [], [], []
    current_farms = []
    old_pm, old_tc, old_apply, old_end = E._process_market, E._town_consume, E._apply_unit_action, E._end_of_day

    def pid_of(farm):
        for i, f in enumerate(current_farms):
            if farm is f:
                return i
        return None

    def tile_yield(farm):
        out = [0] * len(P)
        for row in farm['tiles']:
            for t in row:
                if not isinstance(t, dict):
                    continue
                y = int(t.get('yield_units') or 0)
                if y <= 0:
                    continue
                if t.get('kind') == 'PLANT' and t.get('crop') in PIDX:
                    out[PIDX[t['crop']]] += y
                elif t.get('animal') in E.ANIMALS:
                    out[PIDX[E.ANIMALS[t['animal']]['product']]] += y
        return out

    def process_market_logged(state, env):
        """Copy of E._process_market with logging; logic unchanged."""
        get = E.get
        obs0 = state[0].observation
        market = obs0.market
        farms = obs0.farms
        privates = [s.observation.private for s in state]
        step = int(get(obs0, 'step', 0))
        board_size = int(get(env.configuration, 'boardSize', 10))
        max_orders = max(1, int(get(env.configuration, 'maxMarketOrdersPerTurn', 10)))
        hire_mult = int(get(env.configuration, 'farmHandCostMult', E.FARM_HAND_COST_MULT))
        shed_capacity = int(get(env.configuration, 'shedCapacity', 100))

        steps.append(dict(
            t=step,
            inv_pre=[int(market['inventory'][p]) for p in P],
            shed=[[int(privates[i]['shed'].get(p, 0)) for p in P] for i in range(2)],
            tile=[tile_yield(farms[i]) for i in range(2)],
        ))

        queues = []
        for s in state:
            action = s.action if isinstance(s.action, dict) else {}
            m = action.get('market', []) if isinstance(action, dict) else []
            q = list(m) if isinstance(m, list) else []
            queues.append(q[:max_orders])
        for pid, q in enumerate(queues):
            for oi, o in enumerate(q):
                if isinstance(o, list) and o and o[0] in ('SELL', 'BUY_PRODUCT') and len(o) >= 3:
                    orders.append([step, pid, oi, o[0], o[1], o[2]])

        max_len = max((len(q) for q in queues), default=0)
        for i in range(max_len):
            order_states = []
            for player_id, q in enumerate(queues):
                ostate = None
                if i < len(q):
                    ostate = E._parse_order(q[i])
                order_states.append(ostate)

            for player_id, ostate in enumerate(order_states):
                if ostate is None:
                    continue
                op = ostate['type']
                if op == 'HIRE':
                    E._do_hire(farms[player_id], privates[player_id], board_size, hire_mult)
                    order_states[player_id] = None
                elif op == 'BUY_LAND':
                    E._do_buy_land(farms[player_id], board_size)
                    order_states[player_id] = None

            idx_esc = 0
            lock_iter = 0
            while True:
                idx_esc += 1
                if idx_esc >= 100_000:
                    print('WARNING: kaggriculture market loop exceeded 100k iterations; aborting')
                    break
                quoted = [None, None]
                for player_id, ostate in enumerate(order_states):
                    if ostate is None or ostate['remaining'] <= 0:
                        continue
                    op = ostate['type']
                    item = ostate['item']
                    if op == 'SELL' and item in E.PRODUCTS:
                        quoted[player_id] = ('SELL', item, E.market_price(item, market['inventory'][item], market.get('params')), ostate)
                    elif op == 'BUY_PRODUCT' and item in ('WHEAT', 'FERTILIZER'):
                        quoted[player_id] = ('BUY_PRODUCT', item, E.market_price(item, market['inventory'][item] - 1, market.get('params')), ostate)
                    elif op == 'BUY_SEED' and item in E.CROPS:
                        quoted[player_id] = ('BUY_SEED', item, E.CROPS[item]['seed'], ostate)
                    elif op == 'BUY_ANIMAL' and item in E.ANIMALS:
                        quoted[player_id] = ('BUY_ANIMAL', item, E.ANIMALS[item]['cost'], ostate)
                    else:
                        order_states[player_id] = None

                if all(q is None for q in quoted):
                    break

                committed_any = False
                for player_id, q in enumerate(quoted):
                    if q is None:
                        continue
                    op, item, price, ostate = q
                    inv_b = int(market['inventory'][item]) if op in ('SELL', 'BUY_PRODUCT') else None
                    ok = E._commit_unit(op, item, price, farms[player_id], privates[player_id], market, shed_capacity)
                    if ok:
                        ostate['remaining'] -= 1
                        committed_any = True
                        tx.append([step, i, lock_iter, player_id, op, item, price, inv_b])
                    else:
                        order_states[player_id] = None
                lock_iter += 1
                if not committed_any:
                    break

            E._refresh_prices(market)

    def town_consume_hook(env, state, step):
        old_tc(env, state, step)
        if steps and steps[-1]['t'] == step:
            steps[-1]['inv_post'] = [int(state[0].observation.market['inventory'][p]) for p in P]

    def apply_hook(farm, private, idx, action, board_size, day, turns_per_day, shed_capacity=100):
        if isinstance(action, list) and action and action[0] == 'HARVEST' and idx < len(private['inventories']):
            before = dict(private['inventories'][idx])
            r = old_apply(farm, private, idx, action, board_size, day, turns_per_day, shed_capacity)
            after = private['inventories'][idx]
            pid = pid_of(farm)
            for k, v in after.items():
                if v > before.get(k, 0):
                    harvest.append([len(steps), pid, k, v - before.get(k, 0)])   # len(steps) == current step
            return r
        return old_apply(farm, private, idx, action, board_size, day, turns_per_day, shed_capacity)

    def end_hook(state, environment, day):
        old_end(state, environment, day)
        state[0].observation.town.unlocked_shops[:] = shops_by_day[min(len(shops_by_day) - 1, day + 1)]

    box = {}

    def real(state, environment):
        farms = getattr(state[0].observation, 'farms', None)
        if farms:
            current_farms[:] = farms
        return box['orig'](state, environment)

    E._process_market, E._town_consume, E._apply_unit_action, E._end_of_day = process_market_logged, town_consume_hook, apply_hook, end_hook
    try:
        env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': seed})
        box['orig'] = env.interpreter
        env.interpreter = real
        live = None
        if agent_path is not None:
            from kaggle_environments.agent import get_last_callable
            live = get_last_callable(Path(agent_path).read_text(encoding='utf-8'), path=str(agent_path))

        def player(i):
            def act(obs):
                t = int(obs['step'])
                if i == seat and live is not None:
                    a = live(obs) or {}
                else:
                    a = actions[i][t] if t < len(actions[i]) else {}
                return deepcopy(a) if a else {'farmer': ['PASS'], 'hands': [], 'market': []}
            return act

        env.run([player(0), player(1)])
        final = [float(s.reward) for s in env.state]
    finally:
        E._process_market, E._town_consume, E._apply_unit_action, E._end_of_day = old_pm, old_tc, old_apply, old_end

    # harvest step index: apply_hook runs before the market phase appends that step, so len(steps) is the step
    cash_match = bool(round(final[0]) == round(g['rewards'][0]) and round(final[1]) == round(g['rewards'][1]))
    return dict(
        meta=dict(episode=episode, seat=seat, seed=seed, rewards=g['rewards'], final_cash=final, cash_match=cash_match,
                  agent='LEADER' if agent_path is None else str(agent_path), shops=g['shops'],
                  names=g.get('names')),
        products=P, tx=tx, orders=orders, steps=steps, harvest=harvest,
    )


def main():
    # several agents (comma-separated) share one process; each writes to <out_dir>/<LEADER|agent stem>/
    agents, out = sys.argv[1].split(','), Path(sys.argv[2])
    for p in sys.argv[3:]:
      for agent in agents:
        p = Path(p)
        o = out / (agent if agent == 'LEADER' else Path(agent).stem) if len(agents) > 1 else out
        o.mkdir(parents=True, exist_ok=True)
        dest = o / p.name
        if dest.exists():
            print(p.name, agent, 'exists, skipped', flush=True)
            continue
        wait_for_memory()
        t0 = time.time()
        r = replay_events(p, agent_path=None if agent == 'LEADER' else agent)
        with gzip.open(dest, 'wt', encoding='utf-8') as f:
            json.dump(r, f, separators=(',', ':'))
        print(p.name, agent, 'final', r['meta']['final_cash'], 'recorded', r['meta']['rewards'], 'match', r['meta']['cash_match'],
              f'{time.time() - t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
