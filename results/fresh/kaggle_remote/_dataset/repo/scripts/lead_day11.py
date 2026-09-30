"""Day-11 clean-slate trace: the leader's recorded actions through day 10, then agents/mgt_lead.py (T) from day 11 hour 0
in the same world (recorded seed, forced shops, recorded opponent); per-step trace of day 11 for T and for the leader's
own replay of that day.

usage: lead_day11.py run <team:ep,...> [--cfg 'k=v;...'] [--tag NAME] [--workers 4]
       lead_day11.py report [--tag NAME]
Writes results/fresh/lead_day11/<tag>/<side>_<ep>.json: per step of day 11 every unit's position, command and whether it
changed the engine state; the market orders returned and the ones that went through (per step); T's hour-0..23 plan
jobs (what _plan returned), T's log and the idle tracer (CFG idle_trace) for T; next-morning cash.
"""
import gzip
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

OUT = ROOT / 'results/fresh/lead_day11'
DAY = 11
H0 = DAY * 24
MOVES = {'NORTH', 'SOUTH', 'EAST', 'WEST'}


def play(game, side, cfg, tag):
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    team_id, ep = game.split(':')
    sem = json.load(gzip.open(lead_g1.SEM / team_id / f'{ep}.json.gz', 'rt', encoding='utf-8'))
    tape = json.load(gzip.open(next(p for p in sorted(lead_g1.TAPES.glob(f'{team_id}_*/{ep}.json.gz'))), 'rt', encoding='utf-8'))
    seat, seed = tape['seat'], tape['seed']
    shops_by_day = [list(tape['shops'][:min(8, d // 3)]) for d in range(31)]
    opp, mine = tape['opp_actions'], tape['actions']
    mod = None
    plans = {}
    if side == 'T':
        mod = lead_g1._load_agent({})
        c = dict(cfg)
        c['idle_trace'] = str(OUT / tag / f'idle_{ep}')
        mod.configure(sem, **c)
        orig_plan = mod._plan

        def cap_plan(obs, S, tiles, day):
            r = orig_plan(obs, S, tiles, day)
            h = int(obs['step']) % 24
            if int(obs['step']) // 24 == DAY:
                plans[h] = {str(k): list(v) if isinstance(v, tuple) else v for k, v in r[0].items()}
            return r
        mod._plan = cap_plan
    steps = defaultdict(list)          # step -> [(unit, pos, command, effective)]
    orders = {}                        # step -> market orders returned
    trades = defaultdict(list)         # step -> [(op, item, price, ok)]
    farms_box, step_box = [], [0]
    old_apply, old_commit = E._apply_unit_action, E._commit_unit
    cash = {}

    def is_me(farm):
        return bool(farms_box) and farm is farms_box[0][seat]

    def apply_hook(farm, private, idx, action, board_size, day, tpd, shed_capacity=100):
        if not is_me(farm) or step_box[0] // 24 != DAY:
            return old_apply(farm, private, idx, action, board_size, day, tpd, shed_capacity)
        p0 = E._farmer_position(farm, idx)
        p0 = tuple(p0) if p0 is not None else None
        t = farm['tiles'][p0[1]][p0[0]] if p0 is not None else None
        t0 = json.dumps(t, sort_keys=True, default=str)
        inv0 = dict(private['inventories'][idx]) if idx < len(private['inventories']) else {}
        shed0 = dict(private['shed'])
        r = old_apply(farm, private, idx, action, board_size, day, tpd, shed_capacity)
        p1 = E._farmer_position(farm, idx)
        p1 = tuple(p1) if p1 is not None else None
        t = farm['tiles'][p1[1]][p1[0]] if p1 is not None else None
        eff = not (p0 == p1 and t0 == json.dumps(t, sort_keys=True, default=str)
                   and inv0 == (dict(private['inventories'][idx]) if idx < len(private['inventories']) else {})
                   and shed0 == private['shed'])
        tile_kind = (t0[:60] if t0 != 'null' else 'EMPTY')
        steps[step_box[0]].append([idx, list(p0) if p0 else None, action, bool(eff), tile_kind, dict(inv0)])
        return r

    def commit_hook(op, item, price, farm, private, market, shed_capacity=100):
        r = old_commit(op, item, price, farm, private, market, shed_capacity)
        if is_me(farm) and step_box[0] // 24 == DAY:
            trades[step_box[0]].append([op, item, price, bool(r)])
        return r

    box = {}

    def real(state, environment):
        farms = getattr(state[0].observation, 'farms', None)
        if farms:
            farms_box[:] = [farms]
        step_box[0] = int(getattr(state[0].observation, 'step', 0) or 0)
        return box['orig'](state, environment)

    def me_agent(obs):
        t = int(obs['step'])
        if t % 24 == 0:
            cash[t // 24] = obs['farms'][seat]['money']
        if side == 'leader' or t < H0:
            a = mine[t] if t < len(mine) else {}
            a = deepcopy(a) if a else {'farmer': ['PASS'], 'hands': [], 'market': []}
        else:
            a = mod.agent(obs)
        if t // 24 == DAY:
            orders[t] = (a or {}).get('market') or []
        return a

    def opp_agent(obs):
        t = int(obs['step'])
        a = opp[t] if t < len(opp) else {}
        return deepcopy(a) if a else {'farmer': ['PASS'], 'hands': [], 'market': []}

    def end_hook_factory(old_end):
        def end_hook(state, environment, day):
            old_end(state, environment, day)
            state[0].observation.town.unlocked_shops[:] = shops_by_day[min(30, day + 1)]
        return end_hook
    old_end = E._end_of_day
    E._apply_unit_action, E._commit_unit, E._end_of_day = apply_hook, commit_hook, end_hook_factory(old_end)
    try:
        env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': seed})
        box['orig'] = env.interpreter
        env.interpreter = real
        agents = [None, None]
        agents[seat] = me_agent
        agents[1 - seat] = opp_agent
        env.run(agents)
        final = float(env.state[seat].reward)
    finally:
        E._apply_unit_action, E._commit_unit, E._end_of_day = old_apply, old_commit, old_end
    out = dict(game=game, side=side, cfg=cfg, final=final, cash={str(k): v for k, v in cash.items()},
               steps={str(k): v for k, v in steps.items()}, orders={str(k): v for k, v in orders.items()},
               trades={str(k): v for k, v in trades.items()}, plans={str(k): v for k, v in plans.items()},
               log=(dict(getattr(mod, '_S', {}).get('log', {})) if mod is not None and getattr(mod, '_S', None) else {}))
    (OUT / tag).mkdir(parents=True, exist_ok=True)
    (OUT / tag / f'{side}_{ep}.json').write_text(json.dumps(out, default=str), encoding='utf-8')
    return game, side, final


def job(args):
    try:
        return play(*args)
    except Exception as exc:
        return args[0], args[1], f'FAILED {type(exc).__name__}: {exc} {traceback.format_exc()[-800:]}'


def main():
    argv = sys.argv[1:]
    if argv[0] == 'run':
        games = argv[1].split(',')
        cfg, tag, workers = {}, 'day11', 4
        i = 2
        while i < len(argv):
            if argv[i] == '--cfg':
                for kv in argv[i + 1].split(';'):
                    k, v = kv.split('=', 1)
                    try:
                        v = json.loads(v)
                    except Exception:
                        pass
                    cfg[k] = v
                i += 2
            elif argv[i] == '--tag':
                tag = argv[i + 1]; i += 2
            elif argv[i] == '--workers':
                workers = int(argv[i + 1]); i += 2
            else:
                i += 1
        jobs = [(g, s, cfg, tag) for g in games for s in ('leader', 'T')]
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for r in pool.map(job, jobs):
                print(r, flush=True)


if __name__ == '__main__':
    main()
