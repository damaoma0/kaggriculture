"""xfix: T's defects when it plays from the leader's EXACT morning state (thread xfix, 2026-09-25).

Worlds: results/fresh/xfix_20260925/worlds42.json = the 42 leader worlds where the xopen Xdyn arm handed off at day 11
(T plays day 11 from the leader's exact morning state; results/fresh/xopen_20260925/g1). Every game uses the recording's
world: its seed, the forced shop schedule, the recorded opponent (scripts/lead_ledger.py's setup).

Modes
  trace <arms> [--games ep,...]   day-11 per-step, per-unit trace. Engine hooks on our seat: pre-command position,
        command, effect, tile signature before / after, inventory before / after; market events per step; hires; the
        midnight shed. For a T-like arm also T's internals per step (plan jobs, tile tasks, tile values, assignment after
        the step, action, market orders, demand, idle-pass reasons). LEADER replays its tape; a T-like arm replays the
        tape for days 0..10 and plays from hour 0 of day 11 (xopen design D.2: fresh state, sold = the recording's
        cumulative sold units through day 10). Every arm stops after day 11 (PASS) and the next morning is recorded.
        -> results/fresh/xfix_20260925/trace/<arm>/<ep>.json
  day11 <arms> [--games ...]      the same single-day game through lead_ledger.play (unchanged; its per-day ledger:
        day 11 ops, cash next morning = days[12].cash). -> day11/<arm>/<ep>.json
  full  <arms> [--worlds g1|sem4|all] [--games ...]   full games, T from step 0, through lead_ledger.play. -> full/<arm>/<ep>.json
Arms: ARMS below (agent file + T options; BASE = the xopen T settings p1_min_value 30, release_stale_d, fert_hold 1).

usage: xfix_run.py <mode> <arm,arm,...> [--games ep,...] [--worlds ...] [--workers 4]
"""
import copy
import gzip
import importlib.util
import json
import os
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
OUT = ROOT / 'results/fresh/xfix_20260925'
PASS = {'farmer': ['PASS'], 'hands': [], 'market': []}
BASE = {'p1_min_value': 30, 'release_stale_d': True, 'fert_hold': 1}
T_SRC = 'results/fresh/xopen_20260925/src/mgt_lead_8d578ef8099b.py'     # the T of the xopen runs (E1)
D = 11

ARMS = {
    'T': (T_SRC, {}),                                  # = the xopen X11 / Xdyn arms' T
    'Tc': ('agents/mgt_lead.py', {}),                  # current mgt_lead.py, new options off (must equal T)
    'F0': ('agents/mgt_lead_fix.py', {}),              # the fix copy, every fix off (must equal Tc)
}
try:                                                    # fix arms (scripts/xfix_arms.json: {name: [path, cfg]})
    for k_, v_ in json.loads((ROOT / 'scripts/xfix_arms.json').read_text(encoding='utf-8')).items():
        ARMS[k_] = (v_[0], v_[1])
except FileNotFoundError:
    pass


def load_worlds():
    return json.loads((OUT / 'worlds42.json').read_text(encoding='utf-8'))


def tape_of(game):
    import lead_g1
    team_id, ep = game.split(':')
    p = next(p for p in sorted(lead_g1.TAPES.glob(f'{team_id}_*/{ep}.json.gz')))      # lead_g1 / lead_ledger's choice
    return json.load(gzip.open(p, 'rt', encoding='utf-8'))


def load_module(path, tag):
    spec = importlib.util.spec_from_file_location(tag, str(ROOT / path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Handoff:
    """module-like agent for lead_ledger.play: the tape until day hand (if any), then the T-like module; PASS from
    step stop (if any). configure / agent / _S like agents/mgt_lead.py."""

    def __init__(self, mod, cfg, tape, hand=None, stop=None, on_step=None):
        self.mod, self.cfg, self.tape, self.hand, self.stop, self.on_step = mod, cfg, tape, hand, stop, on_step

    def configure(self, sem, **kw):
        self.mod.configure(sem, **dict(self.cfg, **kw))

    @property
    def _S(self):
        return self.mod._S

    def agent(self, obs, config=None):
        t = int(obs['step'])
        if self.hand is not None and t < self.hand * 24:
            a = self.tape['actions'][t] if t < len(self.tape['actions']) and isinstance(self.tape['actions'][t], dict) else {}
            return copy.deepcopy(a) if a else dict(PASS)
        if self.stop is not None and t >= self.stop:
            return dict(PASS)
        m = self.mod
        if self.hand is not None and t == self.hand * 24:
            S = m._new_state()
            S['last_step'] = t - 1
            S['sold'] = Counter({k: int(v) for k, v in m._T.cum_sold[self.hand - 1].items()})
            m._S = S
        a = m.agent(obs, config)
        if self.on_step is not None:
            self.on_step(t, obs, a)
        if getattr(self, 'record', None) is not None:
            self.record[t] = copy.deepcopy(a)
        return a


def _sig(t):
    if t == 'LOCKED':
        return 'L'
    if t is None:
        return '.'
    if not isinstance(t, dict):
        return str(t)
    k = t.get('kind')
    if k == 'PLANT':
        return '%s@%s y%s w%d c%s f%s' % (t['crop'][:2], t.get('planted_day'), t.get('yield_units'), int(bool(t.get('watered_today'))),
                                         t.get('consecutive_unwatered'), t.get('fertilized_until_day'))
    if k == 'WEED':
        return 'WEED'
    if t.get('animal'):
        return '%s@%s y%s fed%d care%d fa%d b%s u%s' % (t['animal'][:2].lower(), t.get('placed_day'), t.get('yield_units'),
                                                       int(bool(t.get('fed_today'))), int(bool(t.get('cared_today'))),
                                                       int(bool(t.get('fertilizer_available'))), t.get('pending_care_bonus', 0),
                                                       t.get('consecutive_unfed'))
    return str(k)[:2].lower()


def instrument(mod, TR, box):
    """record T's internals per step (only while box['on']): plan jobs, tile tasks, market orders."""
    op, ot, om = mod._plan, mod._tile_ops, mod._market

    def plan(obs, S, tiles, day):
        jobs, fert = op(obs, S, tiles, day)
        if box.get('on'):
            r = TR.setdefault(box['t'], {})
            r['jobs'] = {str(k): list(v) for k, v in jobs.items()}
            r['fert'] = sorted(fert)
        return jobs, fert

    def tile_ops(idx, t, job, fert, day, last_day, seeds):
        res = ot(idx, t, job, fert, day, last_day, seeds)
        if box.get('on') and res[0]:
            TR.setdefault(box['t'], {}).setdefault('tasks', {})[str(idx)] = [res[0], dict(res[1]), res[2]]
        return res

    def market(S, obs, day, hour, money, shed, seeds, carried, invs, tasks, jobs, demand, prices, unlocked, farm, pos, last_day):
        o = om(S, obs, day, hour, money, shed, seeds, carried, invs, tasks, jobs, demand, prices, unlocked, farm, pos, last_day)
        if box.get('on'):
            r = TR.setdefault(box['t'], {})
            r['orders'] = copy.deepcopy(o)
            r['demand'] = dict(demand)
            r['carried'] = dict(carried)
            r['short'] = bool(S.get('short'))
        return o
    mod._plan, mod._tile_ops, mod._market = plan, tile_ops, market


def trace_play(game, arm, light=False):
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    import lead_g1
    team_id, ep = game.split(':')
    sem = json.load(gzip.open(lead_g1.SEM / team_id / f'{ep}.json.gz', 'rt', encoding='utf-8'))
    tape = tape_of(game)
    seat, seed = tape['seat'], tape['seed']
    shops_by_day = [list(tape['shops'][:min(8, d // 3)]) for d in range(31)]
    opp, mine = tape['opp_actions'], tape['actions']
    lo, hi = D * 24, D * 24 + 24
    rec = dict(game=game, episode=int(ep), arm=arm, seat=seat, units={}, market={}, hires={}, land={}, obs={}, tinfo={})
    TR, box = {}, {}
    wrap = None
    if arm != 'LEADER':
        path, cfg = ARMS[arm]
        mod = load_module(path, 'xfix_' + arm)
        idle_dir = OUT / 'trace' / 'idle' / arm / str(ep)
        idle_dir.mkdir(parents=True, exist_ok=True)
        for f in idle_dir.glob('*.jsonl'):
            f.unlink()
        if not light:
            instrument(mod, TR, box)

        def on_step(t, obs, a):
            if light:
                return
            if lo <= t < hi:
                S = mod._S
                r = TR.setdefault(t, {})
                r['assign'] = {str(u): (v if not isinstance(v, tuple) else list(v)) for u, v in (S.get('assign') or {}).items()}
                r['tval'] = {str(i): [round(float(v[0]), 1), v[1]] for i, v in (S.get('tval') or {}).items()}
                r['action'] = copy.deepcopy(a)
                buf = S.get('itr_buf') or []
                r['idle'] = [b for b in buf if b.get('h') == t % 24]
        wrap = Handoff(mod, dict(BASE, **cfg, **({} if light else {'idle_trace': str(idle_dir)})), tape, hand=D, stop=hi,
                       on_step=on_step)
        wrap.configure(sem)
    farms_box, step_box = [], [0]
    old = dict(apply=E._apply_unit_action, commit=E._commit_unit, hire=E._do_hire, land=E._do_buy_land, end=E._end_of_day)

    def is_me(farm):
        return bool(farms_box) and farm is farms_box[0][seat]

    def apply_hook(farm, private, idx, action, board_size, day, tpd, shed_capacity=100):
        t = step_box[0]
        if light or not is_me(farm) or not (lo <= t < hi):
            return old['apply'](farm, private, idx, action, board_size, day, tpd, shed_capacity)
        p0 = E._farmer_position(farm, idx)
        p0 = tuple(p0) if p0 is not None else None
        tile0 = farm['tiles'][p0[1]][p0[0]] if p0 is not None else None
        s0 = _sig(tile0)
        inv0 = dict(private['inventories'][idx]) if idx < len(private['inventories']) else {}
        shed0, seeds0 = dict(private['shed']), dict(private['seeds'])
        r = old['apply'](farm, private, idx, action, board_size, day, tpd, shed_capacity)
        p1 = E._farmer_position(farm, idx)
        p1 = tuple(p1) if p1 is not None else None
        s1 = _sig(farm['tiles'][p0[1]][p0[0]]) if p0 is not None else None
        inv1 = dict(private['inventories'][idx]) if idx < len(private['inventories']) else {}
        eff = int(not (p0 == p1 and s0 == s1 and inv0 == inv1 and shed0 == private['shed'] and seeds0 == private['seeds']))
        rec['units'].setdefault(str(t), []).append([idx, list(p0) if p0 else None, action, eff, s0, s1,
                                                    {k: v for k, v in inv0.items() if v}, {k: v for k, v in inv1.items() if v}])
        return r

    def commit_hook(op, item, price, farm, private, market, shed_capacity=100):
        r = old['commit'](op, item, price, farm, private, market, shed_capacity)
        t = step_box[0]
        if is_me(farm) and lo <= t < hi and not light:
            rec['market'].setdefault(str(t), []).append([op, item, float(price), bool(r)])
        if r and op == 'SELL' and lo <= t < hi and farms_box and farm is farms_box[0][1 - seat]:
            rs = rec.setdefault('rival_sales', {})
            u, v = rs.get(item, (0, 0.0))
            rs[item] = (u + 1, v + float(price))
        return r

    def hire_hook(farm, private, board_size, mult=1):
        n0, m0 = len(farm['hands']), farm['money']
        old['hire'](farm, private, board_size, mult)
        t = step_box[0]
        if is_me(farm) and lo <= t < hi:
            rec['hires'].setdefault(str(t), []).append([len(farm['hands']) > n0, m0 - farm['money'],
                                                        list(farm['hands'][-1]) if len(farm['hands']) > n0 else None])

    def land_hook(farm, board_size):
        n0, m0 = len(farm['unlocked_quadrants']), farm['money']
        old['land'](farm, board_size)
        t = step_box[0]
        if is_me(farm) and lo <= t < hi:
            rec['land'].setdefault(str(t), []).append([len(farm['unlocked_quadrants']) > n0, m0 - farm['money']])

    def end_hook(state, environment, day):
        if day == D:
            f = state[0].observation.farms[seat]
            priv = state[seat].observation.private
            rec['midnight'] = dict(shed={k: int(v) for k, v in dict(priv['shed']).items() if v},
                                   carried=[{k: int(v) for k, v in dict(i).items() if v} for i in priv['inventories']],
                                   money=f['money'])
        old['end'](state, environment, day)
        if day == D:
            priv = state[seat].observation.private
            rec['midnight']['shed_after'] = {k: int(v) for k, v in dict(priv['shed']).items() if v}
        state[0].observation.town.unlocked_shops[:] = shops_by_day[min(30, day + 1)]

    box2 = {}

    def real(state, environment):
        farms = getattr(state[0].observation, 'farms', None)
        if farms:
            farms_box[:] = [farms]
        step_box[0] = int(getattr(state[0].observation, 'step', 0) or 0)
        return box2['orig'](state, environment)

    def me_agent(obs):
        t = int(obs['step'])
        if t in (lo, hi):
            rec.setdefault('opp_cash', {})[str(t)] = obs['farms'][1 - seat]['money']
        if (lo <= t <= hi) and (not light or t in (lo, hi)):
            f = obs['farms'][seat]
            pv = obs['private']
            rec['obs'][str(t)] = dict(money=f['money'], pos=[list(f['farmer'])] + [list(h) for h in f['hands']],
                                      shed={k: int(v) for k, v in dict(pv['shed']).items() if v},
                                      seeds={k: int(v) for k, v in dict(pv['seeds']).items() if v},
                                      invs=[{k: int(v) for k, v in dict(i).items() if v} for i in pv['inventories']],
                                      hires_today=f.get('hires_today'), prices=dict(obs['market']['prices']))
            if t in (lo, hi):
                rec['obs'][str(t)]['tiles'] = [_sig(x) for row in f['tiles'] for x in row]
        if t >= hi:
            return dict(PASS)
        if arm == 'LEADER':
            a = mine[t] if t < len(mine) and isinstance(mine[t], dict) else {}
            a = copy.deepcopy(a) if a else dict(PASS)
            if lo <= t < hi:
                rec.setdefault('actions', {})[str(t)] = copy.deepcopy(a)
            return a
        box['on'] = lo <= t < hi
        box['t'] = t
        a = wrap.agent(obs)
        box['on'] = False
        if lo <= t < hi:
            rec.setdefault('actions', {})[str(t)] = copy.deepcopy(a)
        return a

    def opp_agent(obs):
        t = int(obs['step'])
        if t > hi:
            return dict(PASS)
        a = opp[t] if t < len(opp) else {}
        return copy.deepcopy(a) if a else dict(PASS)

    E._apply_unit_action, E._commit_unit, E._do_hire, E._do_buy_land, E._end_of_day = (apply_hook, commit_hook, hire_hook,
                                                                                         land_hook, end_hook)
    try:
        env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': seed})
        box2['orig'] = env.interpreter
        env.interpreter = real
        agents = [None, None]
        agents[seat] = me_agent
        agents[1 - seat] = opp_agent
        env.run(agents)
    finally:
        E._apply_unit_action, E._commit_unit, E._do_hire, E._do_buy_land, E._end_of_day = (old['apply'], old['commit'],
                                                                                             old['hire'], old['land'], old['end'])
    rec['tinfo'] = {str(k): v for k, v in TR.items()}
    if arm != 'LEADER':
        rec['t_log'] = dict((wrap.mod._S or {}).get('log', {}))
        idle = []
        for f in sorted((OUT / 'trace' / 'idle' / arm / str(ep)).glob('*.jsonl')):
            idle += [json.loads(l) for l in f.read_text(encoding='utf-8').splitlines() if l.strip()]
        rec['idle_day'] = [r for r in idle if r.get('day') == D]
    rec['cash_next_morning'] = rec['obs'].get(str(hi), {}).get('money')
    return rec


def ledger_play(game, arm, mode):
    import lead_g1
    import lead_ledger
    tape = tape_of(game)
    if arm == 'LEADER':
        r = lead_ledger.play(game, 'leader')
    else:
        path, cfg = ARMS[arm]
        box = {}
        hand = D if mode in ('day11', 'stream') else None
        stop = (D + 1) * 24 if mode == 'day11' else (D + 2) * 24 if mode == 'stream' else None

        def loader(_cfg):
            mod = load_module(path, 'xfix_' + arm)
            cfg_ = {k: v for k, v in cfg.items() if k != '_nobase'} if cfg.get('_nobase') else dict(BASE, **cfg)
            h = Handoff(mod, cfg_, tape, hand=hand, stop=stop)
            if mode == 'stream':
                h.record = {}
            box['h'] = h
            return h
        lead_g1._load_agent = loader
        r = lead_ledger.play(game, 'ours')
        r['cfg'] = dict(BASE, **cfg)
        r['agent_path'] = path
        S_ = box['h'].mod._S or {}
        if S_.get('pf'):
            r['pf'] = {'%d:%d' % k: v for k, v in S_['pf'].items()}
        if mode == 'stream':
            acts = [copy.deepcopy(a) if isinstance(a, dict) and a else {} for a in tape['actions']]
            for t_, a_ in box['h'].record.items():
                if D * 24 <= t_ < (D + 2) * 24:
                    acts[t_] = a_
            for t_ in range((D + 2) * 24, len(acts)):
                acts[t_] = {}
            r = dict(game=game, episode=r['episode'], seat=tape['seat'], seed=tape['seed'], arm=arm, cfg=dict(BASE, **cfg),
                     agent_path=path, first_step=D * 24, last_step=(D + 2) * 24 - 1, actions=acts,
                     note='actions[t] = the leader tape for t < 264 (the exact replay), T (fixes off) for 264..311, {} after; '
                          'same format as data/leader_tapes actions', cash=[d['cash'] for d in r['days'][:D + 3]])
    r['arm'] = arm
    r['mode'] = mode
    if mode == 'day11':
        r['days'] = r['days'][:D + 2]           # day 11 and the next morning are what the single-day test reads
    return r


def state_play(game, arm):
    """the day-12 morning state after the arm plays day 11 from the leader's exact morning state (LEADER: the tape)."""
    rec = trace_play(game, arm, light=True)
    return dict(game=game, episode=rec['episode'], arm=arm, cash_next_morning=rec['cash_next_morning'],
                state=rec['obs'].get(str(D * 24 + 24)), midnight=rec.get('midnight'), opp_cash=rec.get('opp_cash'),
                rival_sales=rec.get('rival_sales'), cash_morning=rec['obs'].get(str(D * 24), {}).get('money'))


def job(args):
    mode, game, arm = args
    try:
        t0 = time.time()
        r = (trace_play(game, arm) if mode == 'trace' else state_play(game, arm) if mode == 'state11'
             else ledger_play(game, arm, mode))
        r['wall'] = time.time() - t0
        ep = game.split(':')[1]
        d = (ROOT / 'results/fresh/day12_viz/xdyn_streams') if mode == 'stream' else (OUT / mode / arm)
        d.mkdir(parents=True, exist_ok=True)
        (d / f'{ep}.json').write_text(json.dumps(r, default=str), encoding='utf-8')
        fin = r.get('final') if mode not in ('trace', 'state11', 'stream') else r.get('cash_next_morning', (r.get('cash') or [None])[-1])
        if mode == 'day11':
            fin = r['days'][D + 1]['cash']
        return mode, game, arm, fin, None
    except Exception as exc:
        return mode, game, arm, None, f'{type(exc).__name__}: {exc}\n{traceback.format_exc()[-2500:]}'


def main():
    argv = sys.argv[1:]
    mode, arms = argv[0], argv[1].split(',')
    sel, spec, workers = None, None, int(os.environ.get('LP_WORKERS', 4))
    i = 2
    while i < len(argv):
        if argv[i] == '--games':
            sel = argv[i + 1].split(','); i += 2
        elif argv[i] == '--worlds':
            spec = argv[i + 1]; i += 2
        elif argv[i] == '--workers':
            workers = int(argv[i + 1]); i += 2
        else:
            i += 1
    import lead_g1
    if mode in ('full', 'stream'):
        spec = spec or 'g1'
        games = list(lead_g1.GAMES) if spec in ('g1', 'all') else []
        if spec in ('sem4', 'all'):
            w = json.loads((ROOT / 'results/fresh/lead_sem4_20260925/worlds.json').read_text(encoding='utf-8'))['worlds']
            games += [x['game'] for x in w if x['game'] not in games]
    else:
        W = load_worlds()
        games = [w['game'] for w in W['worlds']]
        if mode == 'trace' and not sel:
            games = [g for g in games if int(g.split(':')[1]) in W['trace8']]
    if sel:
        games = [g for g in games if g.split(':')[1] in sel]
    jobs = [(mode, g, a) for a in arms for g in games]
    print(len(jobs), 'jobs', flush=True)
    t0 = time.time()
    from concurrent.futures import ProcessPoolExecutor, as_completed
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for f in as_completed([pool.submit(job, j) for j in jobs]):
            m, g, a, fin, err = f.result()
            print(time.strftime('%H:%M:%S'), m, a, g, ('ERROR ' + err) if err else f'{fin}', flush=True)
    print(f'completed {len(jobs)} jobs in {time.time() - t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
