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
import base64, gzip, json, os, sys, zlib
from pathlib import Path
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
if _MGT_CFG.get('opening_route') is not None:          # locate the opening route by id (library filters shift indexes)
    _MGT_CFG['opening_route'] = next((i for i, t in enumerate(_MGT_TAPES) if t.get('ep') == 'opening'), None)
    if _MGT_CFG['opening_route'] is not None:
        _MGT_CFG['default_route'] = _MGT_CFG['opening_route']
_MGT_ROUTES = {i: [_MGT_ACTIONS[j] for j in t['ids']] for i, t in enumerate(_MGT_TAPES)}
_MGT_REPORT = {'switches': 0, 'router_errors': 0}
_MGT_HISTORY = []
_MGT_ANIMAL_LABELS = ('sh', 'co', 'go')
_MGT_IGNORE = {}                       # player -> tile indexes an overlay owns (left out of the board distance)
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


_MGT_MEAN = tuple(sum(_MGT_DEMAND[s].get(p, 0) for s in _MGT_DEMAND) / float(len(_MGT_DEMAND)) for p in _MGT_PRODUCTS)


def _mgt_distance(ours_vec, ours, t, k):
    d = 0.0
    for j in _MGT_CHECKPOINTS:
        jj = min(j, k)
        a, b = ours_vec[jj], t['vec'][jj]
        d += sum(w * abs(x - y) for w, x, y in zip(_MGT_W, a, b))
        if j >= k:
            break
    fw = _MGT_CFG.get('future_weight', 0.0)
    if fw:
        # the shops still to come are unknown: prefer a plan that was made for a TYPICAL future over one made for a
        # rare one - the tape's later demand counts against the expectation (what we have + the mean shop per draw)
        for j in _MGT_CHECKPOINTS:
            if j > k:
                exp = [x + (j - k) * m for x, m in zip(ours_vec[k], _MGT_MEAN)]
                d += fw * sum(w * abs(x - y) for w, x, y in zip(_MGT_W, exp, t['vec'][j]))
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
        # new-opening handoff (off unless --opening): the leaders' fixed opening is played as a route until
        # opening_until (the day-6 morning is the only day its board is within max_hamming of our tapes), and is
        # never ranked or kept after that
        _op = _MGT_CFG.get('opening_route')
        if _op is not None and state['route'] == _op and day < _MGT_CFG.get('opening_until', 6):
            return state['route']
        shops = list((_get(observation, 'town', {}) or {}).get('unlocked_shops', []) or [])
        # research hooks (absent on Kaggle), hindsight ceilings:
        #   MGT_ORACLE_SHOPS=a,b,..  rank tapes against the world's FULL shop list from the first routing day on
        #   MGT_LATE_ONLY=<ep>:<day> tape <ep> is hidden from the router until <day>, then forced for good
        #   MGT_SELL_FROM=<ep>:<day> tape <ep> is hidden for good (its SELL orders are blended in further down)
        if _mgt_os.environ.get('MGT_ORACLE_SHOPS'):
            shops = _mgt_os.environ['MGT_ORACLE_SHOPS'].split(',')
        _hide = None
        _spec = _mgt_os.environ.get('MGT_LATE_ONLY') or _mgt_os.environ.get('MGT_SELL_FROM')
        if _spec:
            _hide = next((i for i, t in enumerate(_MGT_TAPES) if str(t['ep']) == _spec.split(':')[0]), None)
            if _mgt_os.environ.get('MGT_LATE_ONLY') and _hide is not None and day >= int(_spec.split(':')[1]):
                if state['route'] != _hide:
                    _MGT_REPORT['switches'] += 1
                state['route'] = _hide
                _MGT_HISTORY.append([day, _MGT_TAPES[_hide]['ep'], 0.0, -1, len(shops)])
                return state['route']
        k = len(shops)
        farm = observation['farms'][_int(_get(observation, 'player', 0))]
        board = _mgt_labels(_mgt_board(farm))
        limit = _MGT_CFG.get('max_hamming', 8)
        cur = state['route']
        ours_vec = [_mgt_vec(shops, j) for j in range(9)]
        lam = _MGT_CFG.get('hamming_weight', 0.0)
        penalty = _MGT_CFG.get('incompatible_penalty', 4.0)
        best = None
        ign = _MGT_IGNORE.get(_int(_get(observation, 'player', 0))) or ()
        if ign:
            board = [None if j in ign else x for j, x in enumerate(board)]
        aw = _MGT_CFG.get('animal_weight', 1)
        # strand_penalty: a live animal of ours on a tile where the candidate tape has no animal today NOR two days
        # on is an animal nobody will feed (ladder game 110933872: sheep placed on day 8, switch on day 9, gone that
        # night, and no cash to hire a rescuer). Narrow on purpose: the blanket animal-tile weight tested -228.
        sp = _MGT_CFG.get('strand_penalty', 0.0)
        mine = [j for j, x in enumerate(board) if x in _MGT_ANIMAL_LABELS] if sp else ()
        for i, t in enumerate(_MGT_TAPES):
            if i == _hide or i == _op:
                continue
            h = _mgt_hamming(board, t['lab'][day]) if not (ign or aw != 1) else sum(
                (aw if (x in _MGT_ANIMAL_LABELS or y in _MGT_ANIMAL_LABELS) else 1)
                for x, y in zip(board, t['lab'][day]) if x is not None and x != y)
            if h > limit and i != cur:
                continue
            d = _mgt_distance(ours_vec, shops, t, k)
            if i == cur and h > limit:
                d += penalty
            if mine:
                now_lab, later_lab = t['lab'][day], t['lab'][min(29, day + 2)]
                d += sp * sum(1 for j in mine if now_lab[j] not in _MGT_ANIMAL_LABELS and later_lab[j] not in _MGT_ANIMAL_LABELS)
            key = (d + lam * h, 0 if i == cur else 1, h, i)
            if best is None or key < best[0]:
                best = (key, d, h, i)
        if best is None:
            # only reachable when the opening route is left: no tape within max_hamming, take the nearest board
            best = min(((_mgt_hamming(board, t['lab'][day]), _mgt_distance(ours_vec, shops, t, k), i)
                        for i, t in enumerate(_MGT_TAPES) if i != _op))
            best = ((best[1] + penalty, 1, best[0], best[2]), best[1] + penalty, best[0], best[2])
            _MGT_REPORT['opening_fallback'] = 1
        best = (best[1], best[2], best[3])
        # research hook (absent on Kaggle): on day MGT_FREEZE_DAY take the MGT_PICK-th best tape and stop switching
        _fd = _mgt_os.environ.get('MGT_FREEZE_DAY')
        if _fd:
            if state.get('frozen'):
                return state['route']
            if day >= int(_fd):
                ranked = sorted((((_mgt_distance(ours_vec, shops, t, k) + lam * (_mgt_hamming(board, t['lab'][day]) if not ign else 0)), i)
                                 for i, t in enumerate(_MGT_TAPES) if _mgt_hamming(board, t['lab'][day]) <= limit or i == cur))
                pick = ranked[min(int(_mgt_os.environ.get('MGT_PICK', '0')), len(ranked) - 1)]
                state['frozen'] = True
                best = (pick[0], _mgt_hamming(board, _MGT_TAPES[pick[1]]['lab'][day]), pick[1])
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
if _mgt_os.environ.get('MGT_SELL_FROM'):
    # research hook: from <day> on every route carries the SELL orders of tape <ep> instead of its own (the crew and
    # the purchases stay the route's) - the hindsight ceiling of re-deriving the sell schedule for the true world
    _sf_ep, _sf_day = _mgt_os.environ['MGT_SELL_FROM'].split(':')
    _sf_src = _MGT_ROUTES[next(i for i, t in enumerate(_MGT_TAPES) if str(t['ep']) == _sf_ep)]
    _sf_from = int(_sf_day) * 24

    class _MgtBlend(list):
        def __getitem__(self, t):
            a = list.__getitem__(self, t)
            if not isinstance(t, int) or t < _sf_from or not isinstance(a, dict):
                return a
            b = _sf_src[t] if t < len(_sf_src) and isinstance(_sf_src[t], dict) else {}
            sells = [o for o in (b.get('market') or []) if o and o[0] == 'SELL']
            return dict(a, market=sells + [o for o in (a.get('market') or []) if not (o and o[0] == 'SELL')])

    _MGT_IMPL.chassis.routes = {rid: _MgtBlend(tape) for rid, tape in _MGT_IMPL.chassis.routes.items()}


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
    sheep = None
    settings = dict(hand_align=True, weed_repair=True, sell_lead=False, front_run=False, budget_guard=True,
                    room_guard=True, clamp_sells=True, dead_stock=True, terminal_liquidation=True)
    cfg = dict(max_hamming=8, incompatible_penalty=4.0)
    opening = None
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
        elif args[i] == '--sheep':
            sheep = dict(enabled=True, max_sheep=16, max_hands=4, min_deficit=2, min_profit=3000, first_day=6,
                         last_day=19, latest_hour=8, cash_margin=2000)
            if args[i + 1] != 'default':
                for kv in args[i + 1].split(','):
                    k, v = kv.split('=')
                    if k.startswith('reveal_') and k[7:].upper() in ('WOOL', 'MILK', 'STRAWBERRY', 'EGG', 'CARROT', 'TOMATO', 'WHEAT'):
                        sheep.setdefault('reveal', {})[k[7:].upper()] = int(v)
                        continue
                    if k in ('hold_items', 'align_items', 'sell_all'):
                        sheep[k] = tuple(x for x in v.split('+') if x)
                        continue
                    sheep[k] = float(v) if '.' in v else (int(v) if v.lstrip('-').isdigit() else v)
            i += 2
        elif args[i] == '--opening':
            opening = json.loads(Path(args[i + 1]).read_text(encoding='utf-8')); i += 2
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
    if opening:
        # the leaders' fixed opening as an extra route: its recorded actions for days 0..len-1, nothing after; boards for
        # the recorded days, then an impossible board so the router can never keep it
        ids = []
        for t in range(719):
            a = opening['actions'][t] if t < len(opening['actions']) else {}
            a = {'farmer': a.get('farmer') or ['PASS'], 'hands': a.get('hands') or [], 'market': a.get('market') or []}
            k = json.dumps(a, sort_keys=True, separators=(',', ':'))
            if k not in index:
                index[k] = len(unique); unique.append(a)
            ids.append(index[k])
        boards = list(opening['boards']) + ['XX' * 100] * (30 - len(opening['boards']))
        tapes.append(dict(ids=ids, shops=list(tapes[0]['shops']), boards=boards, ep='opening', modal=False))
        cfg['opening_route'] = len(tapes) - 1
        cfg['opening_until'] = int(opening.get('until', len(opening['actions']) // 24))
        cfg['default_route'] = cfg['opening_route']
    cfg['settings'] = settings
    blob = base64.b85encode(zlib.compress(json.dumps(dict(actions=unique, tapes=tapes), separators=(',', ':')).encode('utf-8'), 9)).decode('ascii')
    assert "'" not in blob and '\\' not in blob
    body = (ROUTER.replace('__BLOB__', blob).replace('__CFG__', repr(cfg)).replace('__SUBS__', ', '.join(subs))
            .replace('__NTAPES__', str(len(tapes))))
    if sheep:
        frag = ROOT / 'scripts/fragments'
        sep = chr(10) * 2
        body += sep + (frag / 'tape_calendar.py').read_text(encoding='utf-8')
        sheep_file = Path(os.environ['MGT_SHEEP_FILE']) if os.environ.get('MGT_SHEEP_FILE') else frag / 'mgt_sheep.py'   # bisecting old overlays
        body += sep + sheep_file.read_text(encoding='utf-8').replace('__SHEEP_CFG__', repr(sheep))
    # Kaggle's loader calls the LAST NEW callable name in the file. Re-defining `agent` in a fragment keeps the
    # name's original position in the module dict, so helpers defined after the first `agent` would win. The
    # entry point is therefore a fresh name, defined last; the check below loads the file the way Kaggle does.
    entry_src = ('def mgt_kaggle_entry(observation, configuration=None):' + chr(10)
                 + '    return agent(observation, configuration)' + chr(10))
    if opening and opening.get('raw', True):
        # the leaders' opening is budget-exact and over-requests hires on purpose (DSM asks ~17 on day 1, ~6 arrive, and
        # ends day 1 with a few coins): our budget / hire guards rewrite it (first O1 panel: board 12 tiles off at the
        # handoff, hire shortfalls in every game, -66k). Replayed raw it reproduces DSM's day-6 board in 14/16 worlds
        # (scripts/opening_replay_probe.py), so the days before opening_until go out untouched and the chassis and
        # every layer start at the day-6 handoff, when all hands respawn at the shed.
        entry_src = ('def mgt_kaggle_entry(observation, configuration=None):' + chr(10)
                     + "    _op = _MGT_CFG.get('opening_route')" + chr(10)
                     + "    _t = int(_get(observation, 'step', 0) or 0)" + chr(10)
                     + "    if _op is not None and _t < _MGT_CFG.get('opening_until', 6) * 24:" + chr(10)
                     + '        _a = _MGT_ROUTES[_op][_t]' + chr(10)
                     + "        return {'farmer': list(_a.get('farmer') or ['PASS']), 'hands': [list(h) for h in (_a.get('hands') or [])],"
                     + " 'market': [list(o) for o in (_a.get('market') or [])]}" + chr(10)
                     + '    return agent(observation, configuration)' + chr(10))
    body += chr(10) * 3 + entry_src + chr(10) * 2 \
        + "mgt_kaggle_entry.sp_telemetry = agent.sp_telemetry if hasattr(agent, 'sp_telemetry') else _MGT_REPORT" + chr(10)
    out = ROOT / 'agents' / f'{name}.py'
    out.write_text(chassis + body, encoding='utf-8')
    compile(out.read_text(encoding='utf-8'), str(out), 'exec')
    from kaggle_environments.agent import get_last_callable
    entry = get_last_callable(out.read_text(encoding='utf-8'), path=str(out))
    assert getattr(entry, '__name__', '') == 'mgt_kaggle_entry', f'loader would call {entry!r}'
    print(f'built {name}: {len(tapes)} tapes, {len(unique)} unique actions, blob {len(blob) / 1e6:.2f} MB, file {out.stat().st_size / 1e6:.2f} MB, '
          f'pre-shop stream shared by {pre.most_common(1)[0][1]}/{len(tapes)} tapes, sha {sha256(out.read_bytes()).hexdigest()[:12]}')


if __name__ == '__main__':
    main()
