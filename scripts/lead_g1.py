"""G1 gate for agents/mgt_lead.py: play the target leader game's OWN world (recorded seed, forced
shop schedule, opponent = the tape's recorded opp_actions) with mgt_lead in the leader's seat,
following that game's board plan.

usage: lead_g1.py [--tag NAME] [--workers 2] [--games team:ep,...] [--cfg key=val,...]
Writes results/fresh/lead_agent_20260924/<tag>/<ep>.json and prints the G1 table.
"""
import gzip
import importlib.util
import json
import sys
import time
import traceback
from collections import Counter
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEM = ROOT / 'data/leader_semantics'
TAPES = ROOT / 'data/leader_tapes'
OUT = ROOT / 'results/fresh/lead_agent_20260924'

GAMES = [
    '16732748:112655730', '16732748:112661570', '16732748:112667461', '16732748:112673479',
    '16770421:112708229', '16770421:112714050', '16770421:112715010', '16770421:112721923',
    '16730612:112444381', '16730612:112445586', '16730612:112447950', '16730612:112449129',
]
TEAM = {'16732748': 'DSM', '16770421': 'Vadim', '16730612': 'UMG'}


def _label(tile):
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


def _load_agent(cfg):
    import os
    spec = importlib.util.spec_from_file_location('mgt_lead', os.environ.get('LEAD_AGENT_PATH') or (ROOT / 'agents/mgt_lead.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def play(game, cfg):
    team_id, ep = game.split(':')
    sem = json.load(gzip.open(SEM / team_id / f'{ep}.json.gz', 'rt', encoding='utf-8'))
    tape_path = next(p for p in sorted(TAPES.glob(f'{team_id}_*/{ep}.json.gz')))
    tape = json.load(gzip.open(tape_path, 'rt', encoding='utf-8'))
    seat, seed = tape['seat'], tape['seed']
    assert seat == sem['meta']['seat']
    shops_flat = tape['shops']
    shops_by_day = [list(shops_flat[:min(8, d // 3)]) for d in range(31)]
    opp = tape['opp_actions']

    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    mod = _load_agent(cfg)
    mod.configure(sem, **cfg)

    days = [dict(cash=None, board=None, hamming=None, noeff=Counter(), failed=Counter(), hires=0, hands=0,
                 cmds=Counter(), harv=Counter(), died=Counter(), sold=Counter(), rev=Counter(), bought=Counter(), spend=Counter()) for _ in range(30)]
    farms_box = []
    step_box = [0]
    old_apply, old_commit, old_hire, old_end = E._apply_unit_action, E._commit_unit, E._do_hire, E._end_of_day

    def is_me(farm):
        return bool(farms_box) and farm is farms_box[0][seat]

    def apply_hook(farm, private, idx, action, board_size, day, tpd, shed_capacity=100):
        if not is_me(farm):
            return old_apply(farm, private, idx, action, board_size, day, tpd, shed_capacity)
        op = action[0] if isinstance(action, list) and action else None
        p0 = E._farmer_position(farm, idx)
        t0 = None
        if p0 is not None:
            t = farm['tiles'][p0[1]][p0[0]]
            t0 = dict(t) if isinstance(t, dict) else t
        inv0 = dict(private['inventories'][idx]) if idx < len(private['inventories']) else {}
        shed0 = dict(private['shed'])
        r = old_apply(farm, private, idx, action, board_size, day, tpd, shed_capacity)
        if op is None or op == 'PASS':
            return r
        d = days[day]
        d['cmds'][op] += 1
        p1 = E._farmer_position(farm, idx)
        t1 = None
        if p1 is not None:
            t = farm['tiles'][p1[1]][p1[0]]
            t1 = dict(t) if isinstance(t, dict) else t
        inv1 = dict(private['inventories'][idx]) if idx < len(private['inventories']) else {}
        if p0 == p1 and t0 == t1 and inv0 == inv1 and shed0 == private['shed']:
            d['noeff'][op] += 1
        if op == 'HARVEST':
            for k, v in inv1.items():
                if v > inv0.get(k, 0):
                    d['harv'][k] += v - inv0.get(k, 0)
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
                dd['bought'][item] += 1
                dd['spend'][item] += price
        return r

    def hire_hook(farm, private, board_size, mult=1):
        before = len(farm['hands'])
        old_hire(farm, private, board_size, mult)
        if is_me(farm) and len(farm['hands']) > before:
            days[min(29, step_box[0] // 24)]['hires'] += 1

    def end_hook(state, environment, day):
        f = state[0].observation.farms[seat]
        days[day]['hands'] = len(f['hands'])
        before = [[dict(t) if isinstance(t, dict) else t for t in row] for row in f['tiles']]
        old_end(state, environment, day)
        for y in range(10):
            for x in range(10):
                a, b = before[y][x], f['tiles'][y][x]
                if isinstance(a, dict) and a.get('kind') == 'PLANT' and not (isinstance(b, dict) and b.get('kind') == 'PLANT'):
                    days[day]['died']['unwatered_' + a['crop']] += 1
                    days[day]['died']['age%02d' % min(20, day - a['planted_day'])] += 1
                if isinstance(a, dict) and a.get('animal') and not (isinstance(b, dict) and b.get('animal')):
                    days[day]['died']['escaped_' + a['animal']] += 1
        state[0].observation.town.unlocked_shops[:] = shops_by_day[min(30, day + 1)]

    box = {}

    def real(state, environment):
        farms = getattr(state[0].observation, 'farms', None)
        if farms:
            farms_box[:] = [farms]
        step_box[0] = int(getattr(state[0].observation, 'step', 0) or 0)
        return box['orig'](state, environment)

    times = []

    def me_agent(obs):
        t = int(obs['step'])
        d, h = divmod(t, 24)
        if h == 0 and d < 30:
            f = obs['farms'][seat]
            days[d]['cash'] = f['money']
            b = [_label(x) for row in f['tiles'] for x in row]
            days[d]['board'] = b
            days[d]['hamming'] = sum(1 for a, c in zip(b, sem['days'][d]['board']) if a != c)
        t0 = time.time()
        a = mod.agent(obs)
        times.append(time.time() - t0)
        return a

    def opp_agent(obs):
        t = int(obs['step'])
        a = opp[t] if t < len(opp) else {}
        return deepcopy(a) if a else {'farmer': ['PASS'], 'hands': [], 'market': []}

    E._apply_unit_action, E._commit_unit, E._do_hire, E._end_of_day = apply_hook, commit_hook, hire_hook, end_hook
    try:
        env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': seed})
        box['orig'] = env.interpreter
        env.interpreter = real
        agents = [None, None]
        agents[seat] = me_agent
        agents[1 - seat] = opp_agent
        env.run(agents)
        final = [float(s.reward) for s in env.state]
        statuses = [s.status for s in env.state]
        last_obs = env.state[0].observation
    finally:
        E._apply_unit_action, E._commit_unit, E._do_hire, E._end_of_day = old_apply, old_commit, old_hire, old_end

    target_cash = sem['meta']['rewards'][seat]
    tdays = sem['days']
    out = dict(
        game=game, team=TEAM.get(team_id, team_id), episode=int(ep), seat=seat, cfg=cfg,
        final=final[seat], opp_final=final[1 - seat], target=target_cash,
        target_opp=sem['meta']['rewards'][1 - seat], ratio=final[seat] / target_cash, statuses=statuses,
        tmax=max(times) if times else 0, tsum=sum(times),
        days=[dict(day=i, cash=dd['cash'], target_cash=tdays[i]['cash_start'], hamming=dd['hamming'],
                   noeff=dict(dd['noeff']), failed=dict(dd['failed']), hires=dd['hires'], hands=dd['hands'],
                   target_hands=tdays[i]['labour']['hands_present'], cmds=dict(dd['cmds']),
                   harv=dict(dd['harv']), died=dict(dd['died']), sold=dict(dd['sold']), rev=dict(dd['rev']), bought=dict(dd['bought']), spend=dict(dd['spend']),
                   board=''.join(dd['board']) if dd['board'] else None)
              for i, dd in enumerate(days)],
        agent_log=dict(getattr(mod, '_S', {}) or {}).get('log', {}),
    )
    return out


def job(args):
    game, cfg, tag = args
    try:
        t0 = time.time()
        r = play(game, cfg)
        r['wall'] = time.time() - t0
        o = OUT / tag
        o.mkdir(parents=True, exist_ok=True)
        (o / f"{game.split(':')[1]}.json").write_text(json.dumps(r, default=str), encoding='utf-8')
        return r
    except Exception as exc:
        return dict(game=game, error=f'{type(exc).__name__}: {exc}', tb=traceback.format_exc()[-3000:])


def table(rows):
    lines = ['| game | team | final | target | ratio | opp (vs target opp) | ham d6/d12/d20 | noeff | failed buys | hires (tgt) | tmax s |',
             '|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|']
    rs = []
    for r in rows:
        if 'error' in r:
            lines.append(f"| {r['game']} | ERROR {r['error']} |")
            continue
        ham = '/'.join(str(r['days'][d]['hamming']) for d in (6, 12, 20))
        ne = sum(sum(d['noeff'].values()) for d in r['days'])
        fb = sum(sum(d['failed'].values()) for d in r['days'])
        hi = sum(d['hires'] for d in r['days'])
        th = sum(d['target_hands'] for d in r['days'])
        lines.append(f"| {r['episode']} | {r['team']} | {r['final']:.0f} | {r['target']:.0f} | {r['ratio']:.3f} | "
                     f"{r['opp_final']:.0f} ({r['target_opp']:.0f}) | {ham} | {ne} | {fb} | {hi} ({th}) | {r['tmax']:.3f} |")
        rs.append(r['ratio'])
    if rs:
        lines.append(f'| **mean** | | | | **{sum(rs) / len(rs):.3f}** | | | | | | |')
    return '\n'.join(lines)


def main():
    argv = sys.argv[1:]
    tag, workers, games, cfg = 'dev', 2, GAMES, {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--tag':
            tag = argv[i + 1]; i += 2
        elif a == '--workers':
            workers = int(argv[i + 1]); i += 2
        elif a == '--games':
            sel = argv[i + 1].split(',')
            games = [g for g in GAMES if any(g.endswith(s) or g == s for s in sel)] or sel
            i += 2
        elif a == '--cfg':
            for kv in argv[i + 1].split(';'):
                k, v = kv.split('=', 1)
                try:
                    v = json.loads(v)
                except Exception:
                    pass
                cfg[k] = v
            i += 2
        else:
            i += 1
    jobs = [(g, cfg, tag) for g in games]
    t0 = time.time()
    rows = []
    if workers <= 1:
        for j in jobs:
            r = job(j)
            rows.append(r)
            print(r.get('game'), r.get('ratio', r.get('error')), flush=True)
    else:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for r in pool.map(job, jobs):
                rows.append(r)
                print(r.get('game'), r.get('ratio', r.get('error')), flush=True)
    print(table(rows))
    print(f'wall {time.time() - t0:.0f}s')
    (OUT / tag).mkdir(parents=True, exist_ok=True)
    (OUT / tag / 'table.md').write_text(table(rows), encoding='utf-8')


if __name__ == '__main__':
    main()
