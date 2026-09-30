"""Work / output / cash ledger of a G1 game, for the leader's OWN recorded actions and for our leader-plan agent,
through the same engine hooks in the same world (recorded seed, forced shops, opponent = recorded opp_actions).

usage: lead_ledger.py run [--workers 4] [--sides leader,ours] [--games ep,...]
       lead_ledger.py report
Writes results/fresh/lead_ledger/<side>_<ep>.json. Side 'leader' replays tape['actions'] (must reproduce the leader's
recorded cash; asserted in the report). Side 'ours' = agents/mgt_lead.py with its current defaults (the Gcut cell).
Per day: unit-steps, moves, actions by type split effective / no-effect (engine state unchanged), PASS, shed arrivals
and items per effective PICKUP, per-unit worked tiles, hires by hour and wages, trades, land, harvests by product,
plantings, deaths, day-start board counts (tile-days per crop / animal).
"""
import gzip
import os
import json
import sys
import time
import traceback
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import lead_g1  # noqa: E402

OUT = ROOT / 'results/fresh/lead_ledger'
MOVES = {'NORTH', 'SOUTH', 'EAST', 'WEST'}
SHED = {(4, 4), (5, 4), (4, 5), (5, 5)}
WINDOWS = [(0, 5), (6, 11), (12, 17), (18, 23), (24, 29)]
ASSETS = {'WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON', 'COW', 'SHEEP', 'GOOSE'}


def _kind(t):
    if t == 'LOCKED':
        return 'LOCKED'
    if t is None:
        return 'EMPTY'
    if not isinstance(t, dict):
        return str(t)
    if t.get('kind') == 'PLANT':
        return t.get('crop')
    if t.get('kind') == 'WEED':
        return 'WEED'
    if t.get('animal'):
        return t['animal']
    return 'S_' + str(t.get('kind'))


def play(game, side):
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    team_id, ep = game.split(':')
    sem = json.load(gzip.open(lead_g1.SEM / team_id / f'{ep}.json.gz', 'rt', encoding='utf-8'))
    tape_path = next(p for p in sorted(lead_g1.TAPES.glob(f'{team_id}_*/{ep}.json.gz')))
    tape = json.load(gzip.open(tape_path, 'rt', encoding='utf-8'))
    seat, seed = tape['seat'], tape['seed']
    shops_by_day = [list(tape['shops'][:min(8, d // 3)]) for d in range(31)]
    opp, mine = tape['opp_actions'], tape['actions']
    mod = None
    if side == 'ours':
        mod = lead_g1._load_agent({})
        mod.configure(sem)
    elif side == 'deploy':
        import lead_ablation
        mod = lead_ablation._DeployAdapter('full', ep, None, 'agents/mgt_lead_deploy.py')
        mod.configure(sem)

    def newday():
        return dict(unit_steps=0, units_max=0, move=0, move_noeff=0, passes=0, eff=Counter(), noeff=Counter(),
                    opk=Counter(), pick_items=0, pick_n=0, shed_arr=0, hires=[], wages=0.0, land=0.0,
                    sold=Counter(), rev=Counter(), bought=Counter(), spend=Counter(), failed=Counter(),
                    harv=Counter(), plant=Counter(), died=Counter(), board=Counter(), cash=None,
                    tiles_by_unit=defaultdict(set), plants=[], board_list=None, consec_d=0, consec_n=0,
                    opshed_d=0, opshed_n=0, last={}, picked=Counter(), deposited=Counter(), deposit_n=0,
                    fed_from=Counter(), fert_from=Counter(), shed_mid=None, carried_mid=None, shed_after=None,
                    overflow=Counter())
    days = [newday() for _ in range(30)]
    farms_box, step_box = [], [0]
    old_apply, old_commit, old_hire, old_end, old_land = (E._apply_unit_action, E._commit_unit, E._do_hire,
                                                          E._end_of_day, E._do_buy_land)

    def is_me(farm):
        return bool(farms_box) and farm is farms_box[0][seat]

    def apply_hook(farm, private, idx, action, board_size, day, tpd, shed_capacity=100):
        if not is_me(farm):
            return old_apply(farm, private, idx, action, board_size, day, tpd, shed_capacity)
        op = action[0] if isinstance(action, list) and action else None
        p0 = E._farmer_position(farm, idx)
        p0 = tuple(p0) if p0 is not None else None
        t = farm['tiles'][p0[1]][p0[0]] if p0 is not None else None
        t0 = dict(t) if isinstance(t, dict) else t
        inv0 = dict(private['inventories'][idx]) if idx < len(private['inventories']) else {}
        shed0 = dict(private['shed'])
        r = old_apply(farm, private, idx, action, board_size, day, tpd, shed_capacity)
        d = days[min(29, day)]
        if op is None or op == 'PASS':
            d['passes'] += 1
            return r
        p1 = E._farmer_position(farm, idx)
        p1 = tuple(p1) if p1 is not None else None
        t = farm['tiles'][p1[1]][p1[0]] if p1 is not None else None
        t1 = dict(t) if isinstance(t, dict) else t
        inv1 = dict(private['inventories'][idx]) if idx < len(private['inventories']) else {}
        eff = not (p0 == p1 and t0 == t1 and inv0 == inv1 and shed0 == private['shed'])
        if op in MOVES:
            d['move'] += 1
            if not eff:
                d['move_noeff'] += 1
            if p1 in SHED and p0 not in SHED:
                d['shed_arr'] += 1
            return r
        (d['eff'] if eff else d['noeff'])[op] += 1
        if not eff:
            return r
        k0 = _kind(t0)
        if p0 is not None and p0 not in SHED and op not in ('PICKUP', 'DROP'):
            lp = d['last'].get(idx)
            if lp is not None:
                d['consec_d'] += abs(lp[0] - p0[0]) + abs(lp[1] - p0[1])
                d['consec_n'] += 1
            d['last'][idx] = p0
            d['opshed_d'] += min(abs(p0[0] - sx) + abs(p0[1] - sy) for sx, sy in SHED)
            d['opshed_n'] += 1
        if op in ('WATER', 'FERTILIZE', 'HARVEST', 'FEED', 'CARE', 'COLLECT_FERTILIZER', 'DIG'):
            d['opk'][f'{op}:{k0}'] += 1
            d['tiles_by_unit'][idx].add(p0)
        if op == 'PICKUP':
            d['pick_n'] += 1
            d['pick_items'] += sum(inv1.values()) - sum(inv0.values())
            for k, v in inv1.items():
                if v > inv0.get(k, 0):
                    d['picked'][k] += v - inv0.get(k, 0)
        if op in ('PLACE', 'DROP') and p0 in SHED:
            dep = {k: v - inv1.get(k, 0) for k, v in inv0.items() if v > inv1.get(k, 0)}
            if dep:
                d['deposit_n'] += 1
                for k, v in dep.items():
                    d['deposited'][k] += v
        if op == 'HARVEST':
            for k, v in inv1.items():
                if v > inv0.get(k, 0):
                    d['harv'][k] += v - inv0.get(k, 0)
        if op == 'PLANT' and len(action) > 1:
            d['plant'][str(action[1])] += 1
            d['plants'].append([p0[1] * 10 + p0[0], str(action[1])])
            d['tiles_by_unit'][idx].add(p0)
        return r

    def commit_hook(op, item, price, farm, private, market, shed_capacity=100):
        r = old_commit(op, item, price, farm, private, market, shed_capacity)
        if is_me(farm):
            dd = days[min(29, step_box[0] // 24)]
            if not r and op != 'SELL':
                dd['failed'][f'{op}:{item}'] += 1
            elif r and op == 'SELL':
                dd['sold'][item] += 1
                dd['rev'][item] += price
            elif r:
                dd['bought'][f'{op}:{item}'] += 1
                dd['spend'][f'{op}:{item}'] += price
        return r

    def hire_hook(farm, private, board_size, mult=1):
        m0, n0 = farm['money'], len(farm['hands'])
        old_hire(farm, private, board_size, mult)
        if is_me(farm) and len(farm['hands']) > n0:
            dd = days[min(29, step_box[0] // 24)]
            dd['hires'].append(step_box[0] % 24)
            dd['wages'] += m0 - farm['money']

    def land_hook(*a, **k):
        farm = a[0] if a else k.get('farm')
        m0 = farm['money'] if isinstance(farm, dict) else None
        r = old_land(*a, **k)
        if isinstance(farm, dict) and is_me(farm):
            days[min(29, step_box[0] // 24)]['land'] += m0 - farm['money']
        return r

    def end_hook(state, environment, day):
        f = state[0].observation.farms[seat]
        before = [[dict(t) if isinstance(t, dict) else t for t in row] for row in f['tiles']]
        priv = state[seat].observation.private
        shed0 = Counter({k: int(v) for k, v in dict(priv['shed']).items() if v})
        carried = Counter()
        for inv in priv['inventories']:
            for k, v in dict(inv).items():
                if v:
                    carried[k] += int(v)
        old_end(state, environment, day)
        shed1 = Counter({k: int(v) for k, v in dict(state[seat].observation.private['shed']).items() if v})
        dd0 = days[min(29, day)]
        dd0['shed_mid'], dd0['carried_mid'], dd0['shed_after'] = dict(shed0), dict(carried), dict(shed1)
        for k in set(shed0) | set(carried):
            lost = shed0.get(k, 0) + carried.get(k, 0) - shed1.get(k, 0)
            if lost > 0:
                dd0['overflow'][k] += lost
        for y in range(10):
            for x in range(10):
                a, b = before[y][x], f['tiles'][y][x]
                if isinstance(a, dict) and a.get('kind') == 'PLANT' and not (isinstance(b, dict) and b.get('kind') == 'PLANT'):
                    days[day]['died']['plant_' + a['crop']] += 1
                if isinstance(a, dict) and a.get('animal') and not (isinstance(b, dict) and b.get('animal')):
                    days[day]['died']['animal_' + a['animal']] += 1
        state[0].observation.town.unlocked_shops[:] = shops_by_day[min(30, day + 1)]

    box = {}

    def real(state, environment):
        farms = getattr(state[0].observation, 'farms', None)
        if farms:
            farms_box[:] = [farms]
        step_box[0] = int(getattr(state[0].observation, 'step', 0) or 0)
        return box['orig'](state, environment)

    def me_agent(obs):
        t = int(obs['step'])
        d, h = divmod(t, 24)
        f = obs['farms'][seat]
        if d < 30:
            n = 1 + len(f['hands'])
            days[d]['unit_steps'] += n
            days[d]['units_max'] = max(days[d]['units_max'], n)
            if h == 0:
                days[d]['cash'] = f['money']
                days[d]['board'] = Counter(_kind(x) for row in f['tiles'] for x in row)
                days[d]['board_list'] = [_kind(x) for row in f['tiles'] for x in row]
        if side == 'leader':
            a = mine[t] if t < len(mine) else {}
            return deepcopy(a) if a else {'farmer': ['PASS'], 'hands': [], 'market': []}
        return mod.agent(obs)

    def opp_agent(obs):
        t = int(obs['step'])
        a = opp[t] if t < len(opp) else {}
        return deepcopy(a) if a else {'farmer': ['PASS'], 'hands': [], 'market': []}

    E._apply_unit_action, E._commit_unit, E._do_hire, E._end_of_day, E._do_buy_land = (
        apply_hook, commit_hook, hire_hook, end_hook, land_hook)
    try:
        cfg_env = {'episodeSteps': 720}
        if os.environ.get('KAGG_NO_TIMEOUT') == '1':    # research: no agent timeout (planner quality without a time limit)
            cfg_env['actTimeout'] = 100000
        if os.environ.get('SHED_CAP'):                  # what-if research: another shed capacity (default 100)
            cfg_env['shedCapacity'] = int(os.environ['SHED_CAP'])
        env = make('kaggriculture', configuration=cfg_env, info={'seed': seed})
        box['orig'] = env.interpreter
        env.interpreter = real
        agents = [None, None]
        agents[seat] = me_agent
        agents[1 - seat] = opp_agent
        env.run(agents)
        final = [float(s.reward) for s in env.state]
    finally:
        E._apply_unit_action, E._commit_unit, E._do_hire, E._end_of_day, E._do_buy_land = (
            old_apply, old_commit, old_hire, old_end, old_land)
    out_days = []
    for d in days:
        tb = d.pop('tiles_by_unit')
        d.pop('last', None)
        spans = []
        for u, ts in tb.items():
            if len(ts) >= 2:
                xs, ys = [p[0] for p in ts], [p[1] for p in ts]
                spans.append([len(ts), (max(xs) - min(xs) + 1) * (max(ys) - min(ys) + 1)])
        dd = {k: (dict(v) if isinstance(v, Counter) else v) for k, v in d.items()}
        dd['unit_spans'] = spans
        out_days.append(dd)
    extra = {}
    if mod is not None and getattr(mod, '_S', None):
        extra = dict(agent_pmap=len(mod._S.get('pmap', {})), agent_smap=len(mod._S.get('smap', {})),
                     agent_log=dict(mod._S.get('log', {})))
    return dict(extra, game=game, episode=int(ep), side=side, seat=seat, final=final[seat], opp_final=final[1 - seat],
                target=sem['meta']['rewards'][seat], target_opp=sem['meta']['rewards'][1 - seat], days=out_days)


def job(args):
    game, side = args
    try:
        t0 = time.time()
        r = play(game, side)
        r['wall'] = time.time() - t0
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / f"{side}_{game.split(':')[1]}.json").write_text(json.dumps(r, default=str), encoding='utf-8')
        return (game, side, r['final'] / r['target'], None)
    except Exception as exc:
        return (game, side, None, f'{type(exc).__name__}: {exc}\n{traceback.format_exc()[-2000:]}')


def _win(d):
    for i, (a, b) in enumerate(WINDOWS):
        if a <= d <= b:
            return i


def report():
    rows = {}
    for f in sorted(OUT.glob('*_1*.json')):
        r = json.load(open(f))
        rows[(r['side'], r['episode'])] = r
    eps = sorted({e for s, e in rows if ('leader', e) in rows and ('ours', e) in rows})
    print(f'{len(eps)} games with both sides')
    bad = [(e, rows[('leader', e)]['final'], rows[('leader', e)]['target']) for e in eps
           if abs(rows[('leader', e)]['final'] - rows[('leader', e)]['target']) > 0.5]
    print('leader replay reproduces recorded cash:', len(eps) - len(bad), '/', len(eps), bad[:3])
    ratios = [rows[('ours', e)]['final'] / rows[('ours', e)]['target'] for e in eps]
    print('ours / leader cash: mean %.3f' % (sum(ratios) / len(ratios)))
    g = len(eps)
    W = {s: [defaultdict(float) for _ in WINDOWS] for s in ('leader', 'ours')}
    for s in ('leader', 'ours'):
        for e in eps:
            for di, d in enumerate(rows[(s, e)]['days']):
                w = W[s][_win(di)]
                effops = sum(v for k, v in d['eff'].items())
                maint = sum(v for k, v in d['eff'].items() if k in ('WATER', 'FEED', 'CARE', 'HARVEST', 'FERTILIZE', 'COLLECT_FERTILIZER'))
                w['unit-steps'] += d['unit_steps']
                w['moves'] += d['move']
                w['moves no-effect'] += d['move_noeff']
                w['effective actions'] += effops
                w['maintenance ops (eff)'] += maint
                for k, v in d['eff'].items():
                    w['eff ' + k] += v
                w['no-effect actions'] += sum(d['noeff'].values())
                w['pass'] += d['passes']
                w['idle (unit-steps - acted)'] += d['unit_steps'] - d['move'] - effops - sum(d['noeff'].values())
                w['shed arrivals'] += d['shed_arr']
                w['pickups'] += d['pick_n']
                w['items picked'] += d['pick_items']
                w['hires'] += len(d['hires'])
                w['hires after hour 0'] += sum(1 for h in d['hires'] if h > 0)
                w['hire hour sum'] += sum(d['hires'])
                w['units (max) day-sum'] += d['units_max']
                w['wages'] += d['wages']
                w['land'] += d['land']
                for k, v in d['board'].items():
                    w['td ' + k] += v
                for k, v in d['opk'].items():
                    w['opk ' + k] += v
                for k, v in d['harv'].items():
                    w['harv ' + k] += v
                for k, v in d['plant'].items():
                    w['plant ' + k] += v
                for k, v in d['died'].items():
                    w['died ' + k] += v
                for k, v in d['spend'].items():
                    w['spend ' + k] += v
                for k, v in d['rev'].items():
                    w['rev ' + k] += v
                for k, v in d['sold'].items():
                    w['sold ' + k] += v
                w['consec_d'] += d.get('consec_d', 0)
                w['consec_n'] += d.get('consec_n', 0)
                w['opshed_d'] += d.get('opshed_d', 0)
                w['opshed_n'] += d.get('opshed_n', 0)
                bl = d.get('board_list') or []
                lb = (rows[('leader', e)]['days'][di].get('board_list') or []) if s == 'ours' else bl
                for ti, k in enumerate(bl):
                    if k in ASSETS:
                        w['occ_n'] += 1
                        w['occ_d'] += min(abs(ti % 10 - sx) + abs(ti // 10 - sy) for sx, sy in SHED)
                        if lb and lb[ti] == k:
                            w['occ_same'] += 1
                if s == 'ours':
                    lp = set()
                    for dj in range(max(0, di - 3), di + 1):
                        lp |= {(t_, c_) for t_, c_ in rows[('leader', e)]['days'][dj].get('plants', [])}
                    for t_, c_ in d.get('plants', []):
                        w['plant_n'] += 1
                        w['plant_same'] += 1 if (t_, c_) in lp else 0
                for sp in d['unit_spans']:
                    w['worked tiles per unit-day'] += sp[0]
                    w['work bbox per unit-day'] += sp[1]
                    w['unit-days working >=2 tiles'] += 1
    keys = ['unit-steps', 'units (max) day-sum', 'moves', 'moves no-effect', 'effective actions', 'maintenance ops (eff)',
            'no-effect actions', 'pass', 'idle (unit-steps - acted)', 'shed arrivals', 'pickups', 'items picked',
            'hires', 'hires after hour 0', 'wages']
    opt = sorted({k for s in W for w in W[s] for k in w if k.startswith('eff ')})
    hdr = '| per game | ' + ' | '.join(f'd{a}-{b} lead / ours' for a, b in WINDOWS) + ' | all lead / ours |'
    print(hdr)
    print('|---|' + '---|' * (len(WINDOWS) + 1))

    def cell(k, s, i=None):
        if i is None:
            return sum(W[s][j].get(k, 0) for j in range(len(WINDOWS))) / g
        return W[s][i].get(k, 0) / g

    def line(label, f):
        vals = [f(i) for i in range(len(WINDOWS))] + [f(None)]
        print(f'| {label} | ' + ' | '.join(vals) + ' |')
    for k in keys + opt:
        line(k, lambda i, k=k: f"{cell(k, 'leader', i):,.0f} / {cell(k, 'ours', i):,.0f}")
    line('moves per maintenance op', lambda i: '%.2f / %.2f' % tuple(
        cell('moves', s, i) / max(1e-9, cell('maintenance ops (eff)', s, i)) for s in ('leader', 'ours')))
    line('moves per effective action', lambda i: '%.2f / %.2f' % tuple(
        cell('moves', s, i) / max(1e-9, cell('effective actions', s, i)) for s in ('leader', 'ours')))
    line('items per pickup', lambda i: '%.2f / %.2f' % tuple(
        cell('items picked', s, i) / max(1e-9, cell('pickups', s, i)) for s in ('leader', 'ours')))
    line('shed arrivals per unit-day', lambda i: '%.2f / %.2f' % tuple(
        cell('shed arrivals', s, i) / max(1e-9, cell('units (max) day-sum', s, i)) for s in ('leader', 'ours')))
    line('share moves / eff actions / idle+noeff %', lambda i: ' / '.join(
        '%.0f-%.0f-%.0f' % (100 * cell('moves', s, i) / cell('unit-steps', s, i),
                            100 * cell('effective actions', s, i) / cell('unit-steps', s, i),
                            100 * (cell('idle (unit-steps - acted)', s, i) + cell('no-effect actions', s, i)) / cell('unit-steps', s, i))
        for s in ('leader', 'ours')))
    line('mean distance between consecutive ops per unit', lambda i: '%.2f / %.2f' % tuple(
        cell('consec_d', s, i) / max(1e-9, cell('consec_n', s, i)) for s in ('leader', 'ours')))
    line('mean shed distance of op tiles', lambda i: '%.2f / %.2f' % tuple(
        cell('opshed_d', s, i) / max(1e-9, cell('opshed_n', s, i)) for s in ('leader', 'ours')))
    line('mean shed distance of occupied tiles (tile-days)', lambda i: '%.2f / %.2f' % tuple(
        cell('occ_d', s, i) / max(1e-9, cell('occ_n', s, i)) for s in ('leader', 'ours')))
    line('our occupied tile-days on a tile the leader holds with the same asset that day', lambda i: '%.1f%%' % (
        100 * cell('occ_same', 'ours', i) / max(1e-9, cell('occ_n', 'ours', i))))
    line('our plantings on a tile where the leader planted that crop (<= 3 days earlier)', lambda i: '%.1f%%' % (
        100 * cell('plant_same', 'ours', i) / max(1e-9, cell('plant_n', 'ours', i))))
    line('mean hire hour', lambda i: '%.1f / %.1f' % tuple(
        cell('hire hour sum', s, i) / max(1e-9, cell('hires', s, i)) for s in ('leader', 'ours')))
    line('worked tiles / bbox per unit-day', lambda i: ' / '.join(
        '%.1f-%.0f' % (cell('worked tiles per unit-day', s, i) / max(1e-9, cell('unit-days working >=2 tiles', s, i)),
                       cell('work bbox per unit-day', s, i) / max(1e-9, cell('unit-days working >=2 tiles', s, i)))
        for s in ('leader', 'ours')))
    # ops per tile-day of the relevant asset
    print('\nops per tile-day (effective), leader / ours:')
    for asset, cmds in (('WHEAT', ('WATER', 'FERTILIZE', 'HARVEST')), ('CARROT', ('WATER', 'FERTILIZE', 'HARVEST')),
                        ('TOMATO', ('WATER', 'FERTILIZE', 'HARVEST')), ('STRAWBERRY', ('WATER', 'FERTILIZE', 'HARVEST')),
                        ('MELON', ('WATER', 'FERTILIZE', 'HARVEST')), ('COW', ('FEED', 'CARE', 'HARVEST', 'COLLECT_FERTILIZER')),
                        ('SHEEP', ('FEED', 'CARE', 'HARVEST', 'COLLECT_FERTILIZER')),
                        ('GOOSE', ('FEED', 'CARE', 'HARVEST', 'COLLECT_FERTILIZER'))):
        parts = []
        for i in list(range(len(WINDOWS))) + [None]:
            tdl, tdo = cell('td ' + asset, 'leader', i), cell('td ' + asset, 'ours', i)
            if tdl + tdo < 1:
                parts.append('-')
                continue
            parts.append(' '.join('%s %.2f/%.2f' % (c[:4], cell(f'opk {c}:{asset}', 'leader', i) / max(1e-9, tdl),
                                                   cell(f'opk {c}:{asset}', 'ours', i) / max(1e-9, tdo)) for c in cmds)
                         + ' (td %.0f/%.0f)' % (tdl, tdo))
        print(f'  {asset:10s} ' + ' | '.join(parts))
    # output and cash decomposition
    print('\nper game, leader / ours: harvested units, plantings, deaths by kind')
    for pre in ('harv ', 'plant ', 'died '):
        ks = sorted({k for s in W for w in W[s] for k in w if k.startswith(pre)})
        print('  ' + ', '.join('%s %.1f/%.1f' % (k[len(pre):], cell(k, 'leader'), cell(k, 'ours')) for k in ks))
    print('items picked up at the shed per game, leader / ours: ' + ', '.join('%s %.0f/%.0f' % (k, sum(sum(d.get('picked', {}).get(k, 0) for d in rows[('leader', e)]['days']) for e in eps) / g, sum(sum(d.get('picked', {}).get(k, 0) for d in rows[('ours', e)]['days']) for e in eps) / g) for k in sorted({k for e in eps for s_ in ('leader', 'ours') for d in rows[(s_, e)]['days'] for k in d.get('picked', {})})))
    print('items deposited at the shed (PLACE/DROP) per game, leader / ours: ' + ', '.join('%s %.0f/%.0f' % (k, sum(sum(d.get('deposited', {}).get(k, 0) for d in rows[('leader', e)]['days']) for e in eps) / g, sum(sum(d.get('deposited', {}).get(k, 0) for d in rows[('ours', e)]['days']) for e in eps) / g) for k in sorted({k for e in eps for s_ in ('leader', 'ours') for d in rows[(s_, e)]['days'] for k in d.get('deposited', {})})))
    print('deposit visits per game, leader / ours: %.0f / %.0f' % tuple(sum(sum(d.get('deposit_n', 0) for d in rows[(s_, e)]['days']) for e in eps) / g for s_ in ('leader', 'ours')))
    for s_ in ('leader', 'ours', 'deploy'):
        es = [e for e in eps if (s_, e) in rows]
        if not es:
            continue
        ov = Counter(); sm = [0.0] * 30; ca = [0.0] * 30; sa = [0.0] * 30; so = [0.0] * 30
        for e in es:
            for di, d in enumerate(rows[(s_, e)]['days']):
                for k, v in (d.get('overflow') or {}).items():
                    ov[k] += v / len(es)
                sm[di] += sum((d.get('shed_mid') or {}).values()) / len(es)
                ca[di] += sum((d.get('carried_mid') or {}).values()) / len(es)
                sa[di] += sum((d.get('shed_after') or {}).values()) / len(es)
                so[di] += sum(d.get('sold', {}).values()) / len(es)
        print('%-7s items discarded by the shed cap at midnight per game: %.1f %s' % (s_, sum(ov.values()), {k: round(v, 1) for k, v in ov.most_common()}))
        print('        shed before dump / carried / shed after / units sold that day, days 12-28 means: %.0f / %.0f / %.0f / %.0f'
              % tuple(sum(x[12:29]) / 17 for x in (sm, ca, sa, so)))
        print('        per day (shed before+carried -> after): ' + ' '.join('%d:%.0f+%.0f>%.0f' % (di, sm[di], ca[di], sa[di]) for di in range(6, 29, 2)))
    print('\ncash decomposition, leader minus ours, per game:')
    fin_l = sum(rows[('leader', e)]['final'] for e in eps) / g
    fin_o = sum(rows[('ours', e)]['final'] for e in eps) / g
    print('  final cash: leader %.0f, ours %.0f, gap %.0f' % (fin_l, fin_o, fin_l - fin_o))
    prods = sorted({k[4:] for s in W for w in W[s] for k in w if k.startswith('rev ')})
    tot_rev = 0.0
    for p in prods:
        rl, ro = cell('rev ' + p, 'leader'), cell('rev ' + p, 'ours')
        ul, uo = cell('sold ' + p, 'leader'), cell('sold ' + p, 'ours')
        pl = rl / ul if ul else 0.0
        po = ro / uo if uo else 0.0
        vol = (ul - uo) * pl
        prc = uo * (pl - po)
        tot_rev += rl - ro
        print(f'  revenue {p:11s} {rl - ro:+8,.0f}  (units {ul:6.1f} vs {uo:6.1f}: volume {vol:+8,.0f}, price {pl:6.1f} vs {po:6.1f}: {prc:+8,.0f})')
    print(f'  revenue total        {tot_rev:+8,.0f}')
    cats = sorted({k[6:] for s in W for w in W[s] for k in w if k.startswith('spend ')})
    tot_sp = 0.0
    for c in cats:
        sl, so = cell('spend ' + c, 'leader'), cell('spend ' + c, 'ours')
        tot_sp += so - sl
        if abs(sl - so) >= 20:
            print(f'  spend {c:24s} ours {so:8,.0f} leader {sl:8,.0f}: {so - sl:+8,.0f} against us')
    wl, wo = cell('wages', 'leader'), cell('wages', 'ours')
    ll, lo = cell('land', 'leader'), cell('land', 'ours')
    print(f'  spend total (trades) {tot_sp:+8,.0f}; wages ours {wo:,.0f} leader {wl:,.0f}: {wo - wl:+,.0f}; land {lo - ll:+,.0f}')
    print(f'  explained {tot_rev + tot_sp + (wo - wl) + (lo - ll):+,.0f} of the gap {fin_l - fin_o:+,.0f} (rest: end inventory / rounding)')
    pm = [rows[('ours', e)].get('agent_pmap') for e in eps]
    print('agent pmap entries (plant events remapped by the planner) per game: %s' % (sum(x or 0 for x in pm) / g))
    print('\nper game gap (leader - ours) and ratio:')
    for e in eps:
        rl, ro = rows[('leader', e)], rows[('ours', e)]
        print(f"  {e} {rl['final'] - ro['final']:+9,.0f}  ratio {ro['final'] / rl['final']:.3f}")


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] == 'report':
        return report()
    workers, sides, sel = 4, ['leader', 'ours', 'deploy'], None
    i = 1
    while i < len(argv):
        if argv[i] == '--workers':
            workers = int(argv[i + 1]); i += 2
        elif argv[i] == '--sides':
            sides = argv[i + 1].split(','); i += 2
        elif argv[i] == '--games':
            sel = argv[i + 1].split(','); i += 2
        else:
            i += 1
    games = [g for g in lead_g1.GAMES if sel is None or g.split(':')[1] in sel]
    jobs = [(g, s) for g in games for s in sides]
    from concurrent.futures import ProcessPoolExecutor, as_completed
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for f in as_completed([pool.submit(job, j) for j in jobs]):
            g, s, ratio, err = f.result()
            print(g, s, ratio if err is None else err, flush=True)


if __name__ == '__main__':
    main()
