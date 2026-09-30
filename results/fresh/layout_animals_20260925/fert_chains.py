"""Fertilizer chains of DSM's hands, from stored Kaggle replays only (no engine runs).

usage: .venv/Scripts/python.exe results/fresh/layout_animals_20260925/fert_chains.py [max_games]

For each replay in data/dsm_replays/ (one file at a time), for each DSM seat, replays the fertilizer bookkeeping of
every unit step by step from the recorded pre-state observation + recorded action, using the engine's rules
(data/kaggriculture.py::_apply_unit_action): PICKUP/DROP/PLACE only on shed-access tiles, FERTILIZE needs a PLANT
tile and a fertilizer in the unit's own inventory, COLLECT_FERTILIZER needs an animal tile with
fertilizer_available (first unit in farmer-then-hand order takes it), inventories auto-dump to the shed at day end.
The simulated per-unit fertilizer count is checked against the recorded post-step inventory on every non-boundary
step (verification counts are printed). Fertilizer tokens are tracked per unit (LIFO consumption; FIFO recorded
too) so each FERTILIZE is attributed to an in-field COLLECT or a shed PICKUP, with positions and walked moves.
Writes events.jsonl.gz (one record per game-seat) and summary.json; report.py turns them into chains.txt.
"""
import gc
import glob
import gzip
import json
import os
import sys
import time

import psutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]
SHEDSET = set(SHED)
MOVES = {'NORTH': (0, -1), 'SOUTH': (0, 1), 'EAST': (1, 0), 'WEST': (-1, 0)}
WORK = {'WATER', 'HARVEST', 'FERTILIZE', 'FEED', 'CARE', 'COLLECT_FERTILIZER', 'PLANT', 'DIG', 'BUILD_COOP',
        'BUILD_PASTURE', 'PICKUP', 'DROP', 'PLACE'}
LEADER = 'DSM'
MIN_AVAIL = 1024 ** 3


def dshed(p):
    return min(abs(p[0] - sx) + abs(p[1] - sy) for sx, sy in SHED)


def man(p, q):
    return abs(p[0] - q[0]) + abs(p[1] - q[1])


def via_shed(p, q):
    return min(abs(p[0] - sx) + abs(p[1] - sy) + abs(q[0] - sx) + abs(q[1] - sy) for sx, sy in SHED)


def tile_at(farm, pos):
    return farm['tiles'][pos[1]][pos[0]]


def kind(t):
    if t is None:
        return 'EMPTY'
    if t == 'LOCKED':
        return 'LOCKED'
    if not isinstance(t, dict):
        return str(t)
    if t.get('kind') == 'PLANT':
        return t.get('crop')
    if 'animal' in t:
        return t['animal']
    return str(t.get('kind'))


def unit_pos(farm, u):
    if u == 0:
        return tuple(farm['farmer'])
    return tuple(farm['hands'][u - 1]) if u - 1 < len(farm['hands']) else None


def analyse_seat(steps, seat):
    """Returns dict with event lists for one seat of one game."""
    ev_fert, ev_collect, ev_pick, ev_dep, fates = [], [], [], [], []
    verify = {'ok': 0, 'bad': 0, 'pos_ok': 0, 'pos_bad': 0}
    unit_days = {}          # (day,u) -> dict(moves, steps, fert, chained)
    layout = []             # per day start: list of (kind, x, y)
    shed_stock = {}         # t -> shed FERTILIZER before action t
    market_fert = {'sell_req': 0, 'buy_req': 0, 'net_resid': 0}
    st = {}                 # unit state within the day

    def new_unit(t, pos):
        return {'stack': [], 'cm': 0, 'last_shed_t': t if pos in SHEDSET else -1,
                'last_shed_cm': 0, 'last_eff': None, 'trip': 0}

    for t in range(1, len(steps)):
        day, hour = (t - 1) // 24, (t - 1) % 24
        pre_o = steps[t - 1][0]['observation']
        pre_farm = pre_o['farms'][seat]
        pre_priv = steps[t - 1][seat]['observation']['private']
        post_farm = steps[t][0]['observation']['farms'][seat]
        post_priv = steps[t][seat]['observation']['private']
        act = steps[t][seat].get('action') or {}
        if not isinstance(act, dict):
            act = {}
        boundary = (t % 24 == 0)
        if hour == 0:
            st = {}
            lay = []
            for y in range(10):
                for x in range(10):
                    k = kind(pre_farm['tiles'][y][x])
                    if k not in ('EMPTY', 'LOCKED'):
                        lay.append((k, x, y))
            layout.append(lay)
        shed_f = int(pre_priv['shed'].get('FERTILIZER', 0))
        shed_stock[t] = shed_f
        for o in act.get('market') or []:
            if isinstance(o, list) and len(o) >= 2 and o[1] == 'FERTILIZER':
                if o[0] == 'SELL':
                    market_fert['sell_req'] += int(o[2]) if len(o) >= 3 else 1
                elif o[0] == 'BUY_PRODUCT':
                    market_fert['buy_req'] += int(o[2]) if len(o) >= 3 else 1
        acts = [act.get('farmer') or ['PASS']] + list(act.get('hands') or [])
        n_units = 1 + len(pre_farm['hands'])
        tile_fa = {}
        shed_delta_units = 0     # fertilizer into shed by units (deposits - pickups), this step
        for u in range(n_units):
            pos = unit_pos(pre_farm, u)
            if pos is None:
                continue
            if u not in st:
                st[u] = new_unit(t, pos)
            S = st[u]
            a = acts[u] if u < len(acts) else ['PASS']
            if not isinstance(a, list) or not a:
                a = ['PASS']
            op = a[0]
            inv_pre = pre_priv['inventories'][u] if u < len(pre_priv['inventories']) else {}
            fert_pre = int(inv_pre.get('FERTILIZER', 0))
            assert fert_pre == len(S['stack']), (t, u, fert_pre, len(S['stack']))
            ud = unit_days.setdefault((day, u), {'moves': 0, 'steps': 0, 'fert': 0, 'chain_out': 0,
                                                 'chain_any': 0, 'collect': 0})
            ud['steps'] += 1
            if pos in SHEDSET:
                if S['last_shed_t'] < t - 1:
                    S['trip'] += 1
                S['last_shed_t'] = t
                S['last_shed_cm'] = S['cm']
            tile = tile_at(pre_farm, pos)
            delta = 0
            new_pos = pos
            eff = False
            if op in MOVES:
                dx, dy = MOVES[op]
                nx, ny = pos[0] + dx, pos[1] + dy
                if 0 <= nx < 10 and 0 <= ny < 10:
                    new_pos = (nx, ny)
                    S['cm'] += 1
                    ud['moves'] += 1
            elif op == 'PICKUP' and pos in SHEDSET and len(a) >= 2:
                n = int(a[2]) if len(a) >= 3 else 1
                if a[1] == 'FERTILIZER' and n > 0:
                    take = min(n, shed_f)
                    shed_f -= take
                    delta = take
                    shed_delta_units -= take
                    for _ in range(take):
                        S['stack'].append({'src': 'shed', 't': t, 'pos': pos, 'cm': S['cm'], 'trip': S['trip'],
                                           'shed_cm': S['cm'], 'shed_t': t})
                    if take:
                        ev_pick.append({'t': t, 'u': u, 'n': take, 'hour': hour})
                        eff = True
                # other pickups (wheat etc.): effectivity checked below via inventory
            elif op == 'DROP' and pos in SHEDSET:
                if S['stack']:
                    for tok in S['stack']:
                        fates.append({'src': tok['src'], 'fate': 'drop', 'same_trip': None, 'dt': t - tok['t']})
                    ev_dep.append({'t': t, 'u': u, 'n': len(S['stack']), 'how': 'DROP',
                                   'field': sum(1 for k in S['stack'] if k['src'] == 'field')})
                    delta = -len(S['stack'])
                    shed_delta_units += len(S['stack'])
                    S['stack'] = []
                    eff = True
            elif op == 'PLACE' and len(a) >= 2 and a[1] == 'FERTILIZER' and pos in SHEDSET:
                n = int(a[2]) if len(a) >= 3 else 1
                k = min(n, len(S['stack'])) if n > 0 else 0
                if k:
                    popped = [S['stack'].pop() for _ in range(k)]
                    for tok in popped:
                        fates.append({'src': tok['src'], 'fate': 'place', 'same_trip': None, 'dt': t - tok['t']})
                    ev_dep.append({'t': t, 'u': u, 'n': k, 'how': 'PLACE',
                                   'field': sum(1 for x in popped if x['src'] == 'field')})
                    delta = -k
                    shed_delta_units += k
                    eff = True
            elif op == 'FERTILIZE':
                if isinstance(tile, dict) and tile.get('kind') == 'PLANT' and S['stack']:
                    nf = sum(1 for k in S['stack'] if k['src'] == 'field')
                    ns = len(S['stack']) - nf
                    fifo_src = S['stack'][0]['src']
                    tok = S['stack'].pop()
                    delta = -1
                    eff = True
                    shed_between = S['last_shed_t'] > tok['t']
                    prev = S['last_eff']
                    rec = {'t': t, 'day': day, 'hour': hour, 'u': u, 'crop': tile.get('crop'), 'C': pos,
                           'src': tok['src'], 'fifo_src': fifo_src, 'held_field': nf, 'held_shed': ns,
                           'A': tok['pos'], 'tA': tok['t'], 'walk_AC': S['cm'] - tok['cm'],
                           'walk_shedC': S['cm'] - tok['shed_cm'] if not shed_between else None,
                           'shed_between': shed_between, 'trip': S['trip'], 'tok_trip': tok['trip'],
                           'prev': prev[1] if prev else None, 'prev_t': prev[0] if prev else None,
                           'walk_prevC': S['cm'] - prev[2] if prev else None,
                           'last_shed_t': S['last_shed_t'],
                           'shed_stock_trip_start': shed_stock.get(tok.get('shed_t', -1))}
                    ev_fert.append(rec)
                    fates.append({'src': tok['src'], 'fate': 'applied', 'same_trip': not shed_between,
                                  'dt': t - tok['t']})
                    ud['fert'] += 1
                    if tok['src'] == 'field':
                        ud['chain_any'] += 1
                        if not shed_between:
                            ud['chain_out'] += 1
            elif op == 'COLLECT_FERTILIZER':
                if isinstance(tile, dict) and 'animal' in tile:
                    avail = tile_fa.get(pos, tile.get('fertilizer_available'))
                    if avail:
                        tile_fa[pos] = False
                        delta = 1
                        eff = True
                        S['stack'].append({'src': 'field', 't': t, 'pos': pos, 'cm': S['cm'], 'trip': S['trip'],
                                           'shed_cm': S['last_shed_cm'], 'shed_t': S['last_shed_t'],
                                           'animal': tile['animal']})
                        ev_collect.append({'t': t, 'u': u, 'A': pos, 'animal': tile['animal'], 'hour': hour,
                                           'since_shed': S['cm'] - S['last_shed_cm'],
                                           'shed_stock_at_last_shed': shed_stock.get(S['last_shed_t'])})
                        ud['collect'] += 1
            # generic effectivity for other work ops (prev-position bookkeeping only)
            if op in WORK and not eff and not boundary:
                inv_post = post_priv['inventories'][u] if u < len(post_priv['inventories']) else {}
                if inv_post != inv_pre or tile_at(post_farm, pos) != tile:
                    eff = True
            elif op in WORK and not eff and boundary and op in ('WATER', 'HARVEST', 'FEED', 'CARE', 'PLANT'):
                eff = True  # cannot check at the day boundary; assume effective (only used for 'prev')
            if eff and op not in MOVES:
                S['last_eff'] = (t, pos, S['cm'])
            # verification against the recorded post-step inventory / position
            if not boundary:
                inv_post = post_priv['inventories'][u] if u < len(post_priv['inventories']) else {}
                if int(inv_post.get('FERTILIZER', 0)) == fert_pre + delta:
                    verify['ok'] += 1
                else:
                    verify['bad'] += 1
                    # resync to recorded truth (should not happen)
                    truth = int(inv_post.get('FERTILIZER', 0))
                    while len(S['stack']) > truth:
                        S['stack'].pop()
                    while len(S['stack']) < truth:
                        S['stack'].append({'src': 'unknown', 't': t, 'pos': pos, 'cm': S['cm'], 'trip': S['trip'],
                                           'shed_cm': S['last_shed_cm']})
                if unit_pos(post_farm, u) == new_pos:
                    verify['pos_ok'] += 1
                else:
                    verify['pos_bad'] += 1
        if not boundary:
            resid = int(post_priv['shed'].get('FERTILIZER', 0)) - int(pre_priv['shed'].get('FERTILIZER', 0)) \
                - shed_delta_units
            market_fert['net_resid'] += resid
        else:
            carried = 0
            for u, S in st.items():
                for tok in S['stack']:
                    fates.append({'src': tok['src'], 'fate': 'autodump', 'same_trip': None, 'dt': t - tok['t']})
                    carried += 1
                S['stack'] = []
            resid = int(post_priv['shed'].get('FERTILIZER', 0)) - int(pre_priv['shed'].get('FERTILIZER', 0)) \
                - shed_delta_units - carried
            market_fert['net_resid'] += resid   # includes overflow loss if the shed was full
    uds = [{'day': k[0], 'u': k[1], **v} for k, v in unit_days.items()]
    return {'fert': ev_fert, 'collect': ev_collect, 'pick': ev_pick, 'dep': ev_dep, 'fates': fates,
            'verify': verify, 'unit_days': uds, 'layout': layout, 'market': market_fert,
            'final': steps[-1][seat].get('reward')}


def main():
    max_games = int(sys.argv[1]) if len(sys.argv) > 1 else 10 ** 9
    files = sorted(glob.glob(os.path.join(ROOT, 'data', 'dsm_replays', 'episode-*-replay.json')))
    out_path = os.path.join(HERE, 'events.jsonl.gz')
    done = set()
    if os.path.exists(out_path):
        with gzip.open(out_path, 'rt', encoding='utf-8') as f:
            for line in f:
                r = json.loads(line)
                done.add((r['episode'], r['seat']))
    n = 0
    t0 = time.time()
    with gzip.open(out_path, 'at', encoding='utf-8') as out:
        for fp in files:
            if n >= max_games:
                break
            ep = int(os.path.basename(fp).split('-')[1])
            avail = psutil.virtual_memory().available
            if avail < MIN_AVAIL:
                print(f'STOP: available memory {avail // 2**20} MB < 1024 MB before {ep}', flush=True)
                break
            with open(fp, encoding='utf-8') as f:
                d = json.load(f)
            avail = psutil.virtual_memory().available
            if avail < MIN_AVAIL:
                print(f'STOP: available memory {avail // 2**20} MB < 1024 MB after loading {ep}', flush=True)
                del d
                break
            teams = d['info']['TeamNames']
            steps = d['steps']
            seats = [i for i, nm in enumerate(teams) if nm == LEADER]
            for seat in seats:
                if (ep, seat) in done:
                    continue
                r = analyse_seat(steps, seat)
                r.update({'episode': ep, 'seat': seat, 'teams': teams, 'rewards': d.get('rewards')})
                out.write(json.dumps(r, separators=(',', ':')) + '\n')
                out.flush()
                v = r['verify']
                print(f'{ep} seat{seat} {teams} fert={len(r["fert"])} collect={len(r["collect"])} '
                      f'verify inv {v["ok"]}/{v["ok"] + v["bad"]} pos {v["pos_ok"]}/{v["pos_ok"] + v["pos_bad"]} '
                      f'{time.time() - t0:.0f}s rss={psutil.Process().memory_info().rss // 2**20}MB', flush=True)
            del d, steps
            gc.collect()
            n += 1


if __name__ == '__main__':
    main()
