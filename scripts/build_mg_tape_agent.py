"""Build a Mother-Goose tape-router agent: the public route-replay chassis core + a library of her recorded
deterministic game tapes + a shop router + first-principles adaptations. Single self-contained file.

  chassis   lines 1..CHASSIS_END of agents/benchmark_frozen_56280048.py (Apache-2.0 route-replay chassis:
            hand alignment, weed repair, budget guard, sell clamping, dead stock, terminal liquidation).
  library   data/mg_tapes/<submission>/*.json.gz (scripts/fetch_mg_tapes.py): her 719 actions, the 8 shops in
            reveal order and her board at every day start. Every tape gets the equilibrium opening: her turn-0/1
            wheat round trip is replaced by one BUY of her net feed wheat at index 0 of turn 0.
  router    her old policy is deterministic and conditioned on the shop sequence only, so two of her games with
            the same shops so far have made the same decisions so far. At every day start the router picks the
            tape whose shop history is closest to ours in DEMAND terms (cumulative count of shops demanding each
            product at the checkpoints her rules read: first 2, 4, 5, 6 and 8 shops), among tapes whose recorded
            board at that day is compatible with ours (Hamming distance over tiles, weeds ignored). Ties keep the
            current tape. Switching only at day starts is position-safe: every unit respawns at the shed.

Usage: python build_mg_tape_agent.py <name> [--subs 56266758,56266899] [--max-tapes N] [--settings k=v,...]
"""
import base64, gzip, json, sys, zlib
from hashlib import sha256
from market_corpus import ROOT

CHASSIS = ROOT / 'agents/benchmark_frozen_56280048.py'
CHASSIS_SHA = '07c313e53d390ab6e1dd563fa2059dd1ea78988af4e0df3f8bbe1c6d8085ea4f'
TAPES = ROOT / 'data/mg_tapes'

ROUTER = r'''

# --------------------------------------------------------------------------- Mother-Goose tape router
# Built by scripts/build_mg_tape_agent.py. Tapes: recorded public replays of team "Unknown Mother-Goose"
# (submissions __SUBS__), __NTAPES__ games; opening replaced by the equilibrium feed purchase.
import base64 as _mgt_b64
import json as _mgt_json
import zlib as _mgt_zlib

_MGT_LIB = _mgt_json.loads(_mgt_zlib.decompress(_mgt_b64.b85decode('__BLOB__')))
_MGT_ACTIONS = _MGT_LIB['actions']
_MGT_TAPES = _MGT_LIB['tapes']          # [{'ids': [...719], 'shops': [8], 'boards': [30 x 200-char str], 'ep': id}]
_MGT_CFG = __CFG__
# research hooks (absent on Kaggle): restrict the library to one recorded game, or leave one out
import os as _mgt_os
if _mgt_os.environ.get('MGT_ONLY'):
    _MGT_TAPES = [t for t in _MGT_TAPES if str(t['ep']) == _mgt_os.environ['MGT_ONLY']]
elif _mgt_os.environ.get('MGT_EXCLUDE'):
    _MGT_TAPES = [t for t in _MGT_TAPES if str(t['ep']) != _mgt_os.environ['MGT_EXCLUDE']]
_MGT_CFG['default_route'] = next((i for i, t in enumerate(_MGT_TAPES) if t.get('modal')), 0)
_MGT_ROUTES = {i: [_MGT_ACTIONS[j] for j in t['ids']] for i, t in enumerate(_MGT_TAPES)}
_MGT_REPORT = {'switches': 0, 'router_errors': 0}
_MGT_HISTORY = []
_MGT_DEMAND = {'BAKERY': {'EGG': 1, 'WHEAT': 1}, 'PIZZA_SHOP': {'MILK': 1, 'TOMATO': 1, 'WHEAT': 1},
               'BRUNCH_SPOT': {'EGG': 1, 'WHEAT': 1, 'STRAWBERRY': 1}, 'YARN_STORE': {'WOOL': 2},
               'ICE_CREAM_SHOP': {'STRAWBERRY': 1, 'MILK': 1, 'WHEAT': 1}, 'PET_CAFE': {'CARROT': 2},
               'SMOOTHIE_SHOP': {'STRAWBERRY': 1, 'MILK': 1},
               'FARMERS_MARKET': {'WHEAT': 1, 'CARROT': 1, 'TOMATO': 1, 'STRAWBERRY': 1}}
_MGT_WEIGHT = {'STRAWBERRY': 3.0, 'TOMATO': 2.0, 'WOOL': 2.0, 'CARROT': 1.5, 'MILK': 1.5, 'EGG': 1.0, 'WHEAT': 0.5}
_MGT_CHECKPOINTS = (2, 4, 5, 6, 8)


def _mgt_label(tile):
    if tile == 'LOCKED':
        return ' L'
    if tile is None:
        return ' .'
    kind = tile.get('kind')
    if kind == 'PLANT':
        return str(tile.get('crop'))[:2]
    if kind == 'WEED':
        return ' .'                      # weeds are random: compare as empty
    if tile.get('animal'):
        return str(tile['animal'])[:2].lower()
    return str(kind)[:2].lower()


def _mgt_board(farm):
    return ''.join(_mgt_label(t) for row in farm['tiles'] for t in row)


_MGT_PRODUCTS = ('STRAWBERRY', 'TOMATO', 'WOOL', 'CARROT', 'MILK', 'EGG', 'WHEAT')
_MGT_W = tuple(float(_MGT_CFG.get('weights', {}).get(p, _MGT_WEIGHT[p])) for p in _MGT_PRODUCTS)
_MGT_SOFT = (' .', 'WH', 'CA')          # short-lived or empty: interchangeable when 'relaxed_compat' is on


def _mgt_vec(shops, j):
    c = [0] * len(_MGT_PRODUCTS)
    for s in shops[:j]:
        for p, n in _MGT_DEMAND.get(s, {}).items():
            c[_MGT_PRODUCTS.index(p)] += n
    return tuple(c)


def _mgt_labels(board):
    out = [board[i:i + 2] for i in range(0, len(board), 2)]
    if _MGT_CFG.get('relaxed_compat'):
        out = [' .' if x in _MGT_SOFT else x for x in out]
    return [' .' if x == ' w' else x for x in out]


for _mgt_t in _MGT_TAPES:
    _mgt_t['vec'] = [_mgt_vec(_mgt_t['shops'], j) for j in range(9)]
    _mgt_t['lab'] = [_mgt_labels(b) for b in _mgt_t['boards']]


def _mgt_hamming(a, b):
    return sum(1 for x, y in zip(a, b) if x != y)


def _mgt_distance(ours_vec, ours, t, k):
    d = 0.0
    for j in _MGT_CHECKPOINTS:
        jj = min(j, k)
        a, b = ours_vec[jj], t['vec'][jj]
        d += sum(w * abs(x - y) for w, x, y in zip(_MGT_W, a, b))
        if j >= k:
            break
    same = 0
    for x, y in zip(ours, t['shops']):
        if x != y:
            break
        same += 1
    return d - 0.01 * same


def _mgt_router(observation, step, state):
    try:
        if 'route' not in state:
            state['route'] = _MGT_CFG.get('default_route', 0)
            del _MGT_HISTORY[:]
        if step % 24 != 0 or step < 72 or step >= _MGT_CFG.get('last_switch_day', 28) * 24 + 1:
            return state['route']
        day = step // 24
        shops = list((_get(observation, 'town', {}) or {}).get('unlocked_shops', []) or [])
        k = len(shops)
        farm = observation['farms'][_int(_get(observation, 'player', 0))]
        board = _mgt_labels(_mgt_board(farm))
        limit = _MGT_CFG.get('max_hamming', 8)
        cur = state['route']
        ours_vec = [_mgt_vec(shops, j) for j in range(9)]
        ranked = sorted((( _mgt_distance(ours_vec, shops, t, k), 0 if i == cur else 1, i) for i, t in enumerate(_MGT_TAPES)))
        cur_d = next(d for d, _, i in ranked if i == cur)
        cur_h = _mgt_hamming(board, _MGT_TAPES[cur]['lab'][day])
        best = (cur_d + (_MGT_CFG.get('incompatible_penalty', 4.0) if cur_h > limit else 0.0), cur_h, cur)
        margin = _MGT_CFG.get('switch_margin', 0.0)
        for d, _, i in ranked:
            if d >= best[0] - margin:
                break
            if i == cur:
                continue
            h = _mgt_hamming(board, _MGT_TAPES[i]['lab'][day])
            if h <= limit:
                best = (d, h, i)
                break
        if best[2] != cur:
            state['route'] = best[2]
            _MGT_REPORT['switches'] += 1
        chosen = _MGT_TAPES[state['route']]
        _MGT_HISTORY.append([day, chosen['ep'], round(best[0], 2), best[1], k])
        if day in (6, 12, 18, 24):
            _MGT_REPORT['dist_d%d' % day] = round(best[0], 2)
        _MGT_REPORT['hamming_max'] = max(_MGT_REPORT.get('hamming_max', 0), best[1])
        return state['route']
    except Exception:
        _MGT_REPORT['router_errors'] += 1
        return state.get('route', 0)


_MGT_IMPL = make_agent(_MGT_ROUTES, router=_mgt_router, **_MGT_CFG.get('settings', {}))


def agent(observation, configuration=None):
    try:
        return _MGT_IMPL(observation, configuration)
    except Exception:
        return {'farmer': ['PASS'], 'hands': [], 'market': []}


agent.mgt_telemetry = _MGT_REPORT
agent.sp_telemetry = _MGT_REPORT
agent.mgt_history = _MGT_HISTORY
'''


def fix_opening(actions):
    net = 0
    for t in (0, 1):
        keep = []
        for o in (actions[t].get('market') or []):
            if len(o) >= 3 and o[1] == 'WHEAT' and o[0] in ('BUY_PRODUCT', 'SELL'):
                net += int(o[2]) if o[0] == 'BUY_PRODUCT' else -int(o[2])
            else:
                keep.append(o)
        actions[t] = dict(actions[t], market=keep)
    if net > 0:
        actions[0] = dict(actions[0], market=[['BUY_PRODUCT', 'WHEAT', net]] + actions[0]['market'])


def main():
    args = sys.argv[1:]
    name = args[0]
    subs = ['56266758', '56266899']
    max_tapes = None
    settings = dict(hand_align=True, weed_repair=True, sell_lead=False, front_run=False, budget_guard=True,
                    room_guard=True, clamp_sells=True, dead_stock=True, terminal_liquidation=True)
    cfg = dict(max_hamming=8, incompatible_penalty=4.0)
    i = 1
    while i < len(args):
        if args[i] == '--subs':
            subs = args[i + 1].split(','); i += 2
        elif args[i] == '--max-tapes':
            max_tapes = int(args[i + 1]); i += 2
        elif args[i] == '--settings':
            for kv in args[i + 1].split(','):
                k, v = kv.split('=')
                settings[k] = v.lower() in ('1', 'true', 'yes')
            i += 2
        elif args[i] == '--cfg':
            for kv in args[i + 1].split(','):
                k, v = kv.split('=')
                if k.startswith('w_'):
                    cfg.setdefault('weights', {})[k[2:].upper()] = float(v)
                else:
                    cfg[k] = float(v) if '.' in v else int(v)
            i += 2
        else:
            raise SystemExit(f'unknown argument {args[i]}')
    src = CHASSIS.read_text(encoding='utf-8')
    assert sha256(CHASSIS.read_bytes()).hexdigest() == CHASSIS_SHA
    lines = src.split('\n')
    end = next(i for i, l in enumerate(lines) if l.startswith('import base64'))   # first line after make_agent
    chassis = '\n'.join(lines[:end])
    assert 'def make_agent(' in chassis and '_R108_DATA' not in chassis

    unique, index, tapes = [], {}, []
    files = sorted(p for s in subs for p in (TAPES / s).glob('*.json.gz'))
    if max_tapes:
        files = files[:max_tapes]
    for p in files:
        t = json.load(gzip.open(p, 'rt', encoding='utf-8'))
        if len(t['actions']) != 719 or len(t['shops'][30]) < 8:
            continue
        actions = [a if isinstance(a, dict) else {} for a in t['actions']]
        fix_opening(actions)
        ids = []
        for a in actions:
            a = {'farmer': a.get('farmer') or ['PASS'], 'hands': a.get('hands') or [], 'market': a.get('market') or []}
            k = json.dumps(a, sort_keys=True, separators=(',', ':'))
            if k not in index:
                index[k] = len(unique); unique.append(a)
            ids.append(index[k])
        tapes.append(dict(ids=ids, shops=list(t['shops'][30][:8]), boards=[''.join(rows) for rows in t['boards']], ep=t['episode']))
    # default route: the tape with the most common day 0-2 action stream
    from collections import Counter
    pre = Counter(tuple(t['ids'][:72]) for t in tapes)
    modal = pre.most_common(1)[0][0]
    cfg['default_route'] = next(i for i, t in enumerate(tapes) if tuple(t['ids'][:72]) == modal)
    for t in tapes:
        t['modal'] = tuple(t['ids'][:72]) == modal
    cfg['settings'] = settings
    blob = base64.b85encode(zlib.compress(json.dumps(dict(actions=unique, tapes=tapes), separators=(',', ':')).encode('utf-8'), 9)).decode('ascii')
    assert "'" not in blob and '\\' not in blob
    body = (ROUTER.replace('__BLOB__', blob).replace('__CFG__', repr(cfg)).replace('__SUBS__', ', '.join(subs))
            .replace('__NTAPES__', str(len(tapes))))
    out = ROOT / 'agents' / f'{name}.py'
    out.write_text(chassis + body, encoding='utf-8')
    compile(out.read_text(encoding='utf-8'), str(out), 'exec')
    print(f'built {name}: {len(tapes)} tapes, {len(unique)} unique actions, blob {len(blob) / 1e6:.2f} MB, file {out.stat().st_size / 1e6:.2f} MB, '
          f'pre-shop stream shared by {pre.most_common(1)[0][1]}/{len(tapes)} tapes, sha {sha256(out.read_bytes()).hexdigest()[:12]}')


if __name__ == '__main__':
    main()
