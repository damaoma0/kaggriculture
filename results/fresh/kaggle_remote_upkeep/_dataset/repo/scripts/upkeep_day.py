"""Single-day upkeep scenarios (thread upkeep, 2026-09-25; one local process, no full games).

A real farm state at hour 0 of day d (days 12-23) is taken from an exact replay (scripts/upkeep_engine.py): the leader's
own game (its tape) or, when a T tape exists (results/fresh/upkeep_20260925/ttape/<ep>.json.gz, recorded on Kaggle),
T's game in the same world. That ONE day is then played by our executor (T = the xopen T source
results/fresh/xopen_20260925/src/mgt_lead_8d578ef8099b.py with p1_min_value 30, release_stale_d, fert_hold 1; the
xopen/xfix handoff: fresh executor state, sold = the recording's cumulative sold units through day d-1) in the
official engine against the recorded opponent, under alternative MAINTENANCE JOB SELECTIONS (a filter on the job list
of scripts/fragments/sem_maintenance.py that the executor dispatches; plan jobs, hires, market unchanged):
  A0   status quo T (jobs worth <= 30 deferred after 15h)
  A    all module jobs, no deferral (p1_min_value 0)
  Cm   module jobs the leader also did on that tile that day (leader-state days only)
  C    Cm + the leader's other maintenance ops that day as jobs (the leader's full selection)
  Dv   module jobs worth >= v coins (v in D_VALUES; fertilizer collection always kept), no deferral
  R*   rule selections (step 2 of the thread; see RULES)
  LEADER  the leader's own recorded day (its own dispatch; reference)
End-of-day score (all at hour 0 of day d+1): cash + shed stock at that hour's prices + the future value of every live
asset (the module's day DP from its next-morning state: units x that hour's price, net of wheat / fertilizer at market
price; FV0 = no labour charge, FVc = VISIT_COST coins per tile visit), plus the day's ops, units, jobs done by value.

usage: upkeep_day.py run <team:ep,...|g1> [--days 12-23] [--sel A0,A,...] [--src leader|t] [--tag NAME]
       upkeep_day.py report [--tag NAME]
"""
import copy
import gzip
import importlib.util
import json
import statistics as stt
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import upkeep_engine as UE  # noqa: E402

OUT = ROOT / 'results/fresh/upkeep_20260925/day'
TTAPE = ROOT / 'results/fresh/upkeep_20260925/ttape'
T_SRC = ROOT / 'results/fresh/xopen_20260925/src/mgt_lead_8d578ef8099b.py'
T_CFG = {'p1_min_value': 30, 'release_stale_d': True, 'fert_hold': 1}
G1 = ['16732748:112655730', '16732748:112661570', '16732748:112667461', '16732748:112673479',
      '16770421:112708229', '16770421:112714050', '16770421:112715010', '16770421:112721923',
      '16730612:112444381', '16730612:112445586', '16730612:112447950', '16730612:112449129']
D_VALUES = (10, 20, 30, 50, 80, 120)
VISIT_COST = 15.0
MOVES = {'NORTH', 'SOUTH', 'EAST', 'WEST'}
MAINT = ('WATER', 'FEED', 'CARE', 'FERTILIZE', 'HARVEST', 'COLLECT_FERTILIZER')
ORDER = {'FERTILIZE': 0, 'WATER': 1, 'FEED': 0, 'CARE': 1, 'HARVEST': 2, 'COLLECT_FERTILIZER': 3}
RULES = {}          # name -> function(job, ctx) -> keep (filled in by step 2 of the thread)


def load_sm():
    ns = {}
    exec(compile((ROOT / 'scripts/fragments/sem_maintenance.py').read_text(encoding='utf-8'), 'sem_maintenance', 'exec'), ns)
    return ns


SMV = load_sm()          # valuation namespace (independent of the executor's)
_TMOD = None


def tmod():
    global _TMOD
    if _TMOD is None:
        spec = importlib.util.spec_from_file_location('upkeep_T', str(T_SRC))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        m._PRISTINE = copy.deepcopy(m.CFG)
        _TMOD = m
    return _TMOD


def asset_of(t):
    if not isinstance(t, dict):
        return None
    if t.get('kind') == 'PLANT' and t.get('crop') in SMV['SM_CROPS']:
        return t['crop'], int(t['planted_day'])
    if t.get('animal') in SMV['SM_ANIMALS']:
        return t['animal'], int(t['placed_day'])
    return None


# ------------------------------------------------------------------ recording hooks
class Rec:
    def __init__(self, w, seat, lo, hi):
        self.w, self.seat, self.lo, self.hi = w, seat, lo, hi
        self.ops = []          # (t, unit, op, tile, eff, hv, prod, asset)
        self.hires = []        # (t, cost)
        self.trades = []       # (t, op, item, price, ok)
        E = w.E
        self.E = E
        self.orig = (E._apply_unit_action, E._do_hire, E._commit_unit)

    def __enter__(self):
        E, w, me = self.E, self.w, self.w.farms[self.seat]
        oa, oh, oc = self.orig
        rec = self

        def apply_hook(farm, private, idx, action, board_size, day, tpd, shed_capacity=100):
            t = w.t
            if farm is not me or not (rec.lo <= t < rec.hi):
                return oa(farm, private, idx, action, board_size, day, tpd, shed_capacity)
            op = action[0] if isinstance(action, list) and action else None
            p0 = E._farmer_position(farm, idx)
            if p0 is None or op is None:
                return oa(farm, private, idx, action, board_size, day, tpd, shed_capacity)
            p0 = (int(p0[0]), int(p0[1]))
            t0 = farm['tiles'][p0[1]][p0[0]]
            t0c = dict(t0) if isinstance(t0, dict) else t0
            inv0 = dict(private['inventories'][idx]) if idx < len(private['inventories']) else {}
            shed0 = dict(private['shed'])
            r = oa(farm, private, idx, action, board_size, day, tpd, shed_capacity)
            p1 = E._farmer_position(farm, idx)
            p1 = (int(p1[0]), int(p1[1]))
            t1 = farm['tiles'][p0[1]][p0[0]]
            inv1 = private['inventories'][idx] if idx < len(private['inventories']) else {}
            eff = not (p0 == p1 and t0c == (dict(t1) if isinstance(t1, dict) else t1) and inv0 == dict(inv1)
                       and shed0 == private['shed'])
            hv, prod = 0, None
            if op == 'HARVEST' and eff:
                for k, v in inv1.items():
                    if v > inv0.get(k, 0):
                        hv, prod = v - inv0.get(k, 0), k
            rec.ops.append((t, idx, op, p0[1] * 10 + p0[0], int(eff), hv, prod, asset_of(t0c)))
            return r

        def hire_hook(farm, private, board_size, mult=1):
            m0, n0 = farm['money'], len(farm['hands'])
            oh(farm, private, board_size, mult)
            if farm is me and len(farm['hands']) > n0 and rec.lo <= w.t < rec.hi:
                rec.hires.append((w.t, m0 - farm['money']))

        def commit_hook(op, item, price, farm, private, market, shed_capacity=100):
            ok = oc(op, item, price, farm, private, market, shed_capacity)
            if farm is me and rec.lo <= w.t < rec.hi:
                rec.trades.append((w.t, op, item, price, bool(ok)))
            return ok
        E._apply_unit_action, E._do_hire, E._commit_unit = apply_hook, hire_hook, commit_hook
        return self

    def __exit__(self, *a):
        self.E._apply_unit_action, self.E._do_hire, self.E._commit_unit = self.orig
        return False


# ------------------------------------------------------------------ worlds
def world_source(game, src):
    team, ep = game.split(':')
    tape = UE.load_tape(team, ep)
    sem = UE.load_sem(team, ep)
    if src == 't':
        tt = json.load(gzip.open(TTAPE / f'{ep}.json.gz', 'rt', encoding='utf-8'))
        mine = tt['actions']
    else:
        mine = tape['actions']
    return tape, sem, mine


def snapshots(tape, mine, days):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    out = {}
    last = max(days)
    while w.t < (last + 1) * 24:
        t = w.t
        if t % 24 == 0 and t // 24 in days:
            out[t // 24] = w.snapshot()
        acts = [None, None]
        acts[seat] = UE.tape_action(mine, t)
        acts[1 - seat] = UE.tape_action(tape['opp_actions'], t)
        w.step(acts)
    return out


# ------------------------------------------------------------------ valuation
def fv_farm(tiles, day, prices, visit_cost):
    """sum over live assets of the module DP's optimal plan value from hour 0 of `day` (coins at `prices`)."""
    tot = units = 0.0
    fert_p, wheat_p = float(prices.get('FERTILIZER', 100)), float(prices.get('WHEAT', 25))
    for y in range(10):
        for x in range(10):
            t = tiles[y][x]
            a = asset_of(t)
            if not a:
                continue
            kind = a[0]
            prod = SMV['_sm_product'](kind)
            p = float(prices.get(prod, SMV['SM_BASE_PRICE'][prod]))
            st = SMV['_sm_state'](kind, t)
            crop = kind in SMV['SM_CROPS']
            if day > SMV['SM_LAST_DAY']:
                continue
            if crop:
                r = SMV['sm_tile_plan'](kind, st, day, 0, p, fert_p, True, 8, visit_cost)
            else:           # animals: the daily fertilizer valued at its market price, as the executor's solve does
                r = SMV['sm_tile_plan'](kind, st, day, 0, p, wheat_p, False, 8, visit_cost, collect_price=fert_p,
                                        avail=bool(t.get('fertilizer_available')))
            tot += r.get('econ_q', 0) * p / SMV['SM_Q']
            units += r.get('units', 0) * p
    return tot, units


def farm_state(w, seat):
    f = w.farms[seat]
    pv = w.private(seat)
    prices = dict(w.market['prices'])
    shed = {k: int(v) for k, v in pv['shed'].items() if v}
    stock = sum(v * float(prices.get(k, 0)) for k, v in shed.items() if k in prices)
    live = Counter()
    bank = 0
    for row in f['tiles']:
        for t in row:
            a = asset_of(t)
            if a:
                live[a[0]] += 1
                if t.get('animal'):
                    bank += int(t.get('pending_care_bonus', 0) or 0)
    return dict(money=float(f['money']), stock=stock, shed=shed, live=dict(live), bank=bank, prices=prices)


def summarize(rec, w, seat, d, snap_state, mj0):
    """metrics of the recorded day + the next-morning valuation."""
    ops = Counter()
    hv = Counter()
    maint_val = 0.0
    maint_n = Counter()
    steps = Counter()
    moves = passes = noeff = 0
    plant = 0
    done = set()
    for (t, u, op, idx, eff, h, prod, a) in rec.ops:
        steps[u] += 1
        if op == 'PASS':
            passes += 1
            continue
        if op in MOVES:
            if eff:
                moves += 1
            else:
                noeff += 1
            continue
        if not eff:
            noeff += 1
            continue
        ops[op] += 1
        if op == 'HARVEST' and prod:
            hv[prod] += h
        if op == 'PLANT':
            plant += 1
        if op in MAINT and a is not None:
            done.add((idx, op))
    for (idx, cmd), j in mj0.items():
        if (idx, cmd) in done and not j.get('optional'):
            maint_val += max(0.0, j['value'])
            maint_n[j['kind']] += 1
    wages = sum(c for _, c in rec.hires)
    sold = sum(p for (_, op, it, p, ok) in rec.trades if ok and op == 'SELL')
    spent = sum(p for (_, op, it, p, ok) in rec.trades if ok and op != 'SELL')
    end = farm_state(w, seat)
    pr0 = snap_state['prices']
    # every selection is valued at the SAME prices (hour 0 of day d): our own sales that day move the market
    stock0 = sum(v * float(pr0.get(k, 0)) for k, v in end['shed'].items() if k in pr0)
    fv0, fvu = fv_farm(w.farms[seat]['tiles'], d + 1, pr0, 0.0)
    fvc, _ = fv_farm(w.farms[seat]['tiles'], d + 1, pr0, VISIT_COST)
    return dict(ops=dict(ops), hv=dict(hv), hv_value=sum(v * float(pr0.get(k, 0)) for k, v in hv.items()),
                maint_value_done=round(maint_val, 1), maint_done=dict(maint_n), units=len(steps),
                unit_steps=sum(steps.values()), moves=moves, passes=passes, noeff=noeff, plant=plant,
                wages=wages, sold=sold, spent=spent, money=end['money'], stock=end['stock'], live=end['live'],
                bank=end['bank'], FV0=round(fv0, 1), FVc=round(fvc, 1), FVunits=round(fvu, 1),
                stock0=round(stock0, 1), shed=end['shed'],
                score0=round(end['money'] + stock0 + fv0, 1), scorec=round(end['money'] + stock0 + fvc, 1))


# ------------------------------------------------------------------ the day under a selection
def leader_day(snap, tape, mine, d):
    w = UE.World.restore(snap)
    seat = tape['seat']
    lo, hi = d * 24, d * 24 + 24
    with Rec(w, seat, lo, hi) as rec:
        while w.t < hi and w.t < 719:
            t = w.t
            acts = [None, None]
            acts[seat] = UE.tape_action(mine, t)
            acts[1 - seat] = UE.tape_action(tape['opp_actions'], t)
            w.step(acts)
    lops = defaultdict(set)
    for (t, u, op, idx, eff, h, prod, a) in rec.ops:
        if eff and op in MAINT and a is not None:
            lops[idx].add(op)
    return w, rec, lops


def make_filter(sel, lops, tiles0):
    """job-list filter for a selection (called on every maintenance_jobs result of the day)."""
    if sel in ('A0', 'A'):
        return None
    if sel.startswith('D'):
        v = float(sel[1:])
        return lambda jl, obs: [j for j in jl if j.get('optional') or j['cmd'] == 'COLLECT_FERTILIZER'
                                or j.get('value', 0) >= v]
    if sel in ('Cm', 'C'):
        def f(jl, obs):
            out = [j for j in jl if j['cmd'] in lops.get(j['tile'][1] * 10 + j['tile'][0], ())]
            if sel == 'C':
                have = {(j['tile'][1] * 10 + j['tile'][0], j['cmd']) for j in out}
                tiles = obs['farms'][int(obs['player'])]['tiles']
                for idx, cmds in lops.items():
                    t = tiles[idx // 10][idx % 10]
                    a = asset_of(t)
                    if not a:
                        continue
                    for cmd in cmds:
                        if (idx, cmd) in have:
                            continue
                        crop = a[0] in SMV['SM_CROPS']
                        if crop and cmd not in ('WATER', 'FERTILIZE', 'HARVEST'):
                            continue
                        if (not crop) and cmd not in ('FEED', 'CARE', 'HARVEST', 'COLLECT_FERTILIZER'):
                            continue
                        needs = {'WHEAT': 1} if cmd == 'FEED' else {'FERTILIZER': 1} if cmd == 'FERTILIZE' else {}
                        out.append({'tile': (idx % 10, idx // 10), 'cmd': cmd, 'value': 1.0, 'deadline': 23,
                                    'needs': needs, 'reason': 'leader extra', 'kind': 'production',
                                    'order': ORDER[cmd], 'units': 0, 'product': SMV['_sm_product'](a[0]),
                                    'price': 0.0, 'asset': a[0]})
            return out
        return f
    if sel in RULES:
        rule = RULES[sel]
        return lambda jl, obs: [j for j in jl if rule(j, obs)]
    raise KeyError(sel)


def t_day(snap, tape, sem, d, sel, lops, mj_log=None):
    m = tmod()
    w = UE.World.restore(snap)
    seat = tape['seat']
    lo, hi = d * 24, d * 24 + 24
    cfg = dict(T_CFG)
    if sel != 'A0':
        cfg['p1_min_value'] = 0.0
    m.CFG.clear()
    m.CFG.update(copy.deepcopy(m._PRISTINE))
    m.configure(sem, **cfg)
    S = m._new_state()
    S['last_step'] = lo - 1
    S['sold'] = Counter({k: int(v) for k, v in m._T.cum_sold[d - 1].items()})
    m._S = S
    m._SMNS = None
    ns = m._sm()
    orig_mj = ns['maintenance_jobs']
    filt = make_filter(sel, lops, None)

    def mj(obs, player, **kw):
        jl = orig_mj(obs, player, **kw)
        if mj_log is not None and not mj_log:
            mj_log.extend(jl)
        return filt(jl, obs) if filt else jl
    ns['maintenance_jobs'] = mj
    tmax = 0.0
    with Rec(w, seat, lo, hi) as rec:
        while w.t < hi and w.t < 719:
            t = w.t
            obs = w.obs(seat)
            t0 = time.time()
            a = m.agent(obs)
            tmax = max(tmax, time.time() - t0)
            acts = [None, None]
            acts[seat] = a
            acts[1 - seat] = UE.tape_action(tape['opp_actions'], t)
            w.step(acts)
    ns['maintenance_jobs'] = orig_mj
    return w, rec, dict(m._S.get('log', {})), tmax


def run_world(game, days, sels, src, tag):
    team, ep = game.split(':')
    tape, sem, mine = world_source(game, src)
    seat = tape['seat']
    snaps = snapshots(tape, mine, days)
    out_dir = OUT / tag
    out_dir.mkdir(parents=True, exist_ok=True)
    for d in days:
        f = out_dir / f'{ep}_{d:02d}.json'
        if f.exists():
            continue
        snap = snaps[d]
        w0 = UE.World.restore(snap)
        st0 = farm_state(w0, seat)
        obs0 = w0.obs(seat)
        jl0 = SMV['maintenance_jobs'](obs0, seat, prices=None, fertilize='auto', include_optional=True, collect=True, log=[])
        mj0 = {}
        for j in jl0:
            mj0[(j['tile'][1] * 10 + j['tile'][0], j['cmd'])] = j
        fv0, _ = fv_farm(w0.farms[seat]['tiles'], d, st0['prices'], 0.0)
        res = dict(game=game, episode=int(ep), day=d, src=src, seat=seat, start=dict(money=st0['money'], stock=st0['stock'],
                   FV0=round(fv0, 1), live=st0['live'], n_jobs=len(jl0),
                   jobs_rp=sum(1 for j in jl0 if not j.get('optional') and j['units'] > 0 and j['cmd'] != 'COLLECT_FERTILIZER'),
                   jobs_value=round(sum(max(0, j['value']) for j in jl0 if not j.get('optional')), 1)), sel={})
        lw, lrec, lops = leader_day(snap, tape, mine, d)
        res['sel']['LEADER'] = summarize(lrec, lw, seat, d, st0, mj0)
        for sel in sels:
            if sel in ('C', 'Cm') and src != 'leader':
                continue
            t0 = time.time()
            w, rec, log, tmax = t_day(snap, tape, sem, d, sel, lops)
            r = summarize(rec, w, seat, d, st0, mj0)
            r['secs'] = round(time.time() - t0, 2)
            r['tmax'] = round(tmax, 3)
            r['log'] = {k: v for k, v in log.items() if k.startswith(('die_', 'unfed', 'surv', 'skipped', 'dying'))}
            res['sel'][sel] = r
        f.write_text(json.dumps(res, separators=(',', ':')), encoding='utf-8')
        a0 = res['sel'].get('A0', {}).get('score0')
        print(game, d, ' '.join(f"{k}:{v['score0'] - a0:+.0f}" for k, v in res['sel'].items() if a0 is not None),
              flush=True)


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    opt = {}
    i = 1
    pos = []
    while i < len(args):
        if args[i].startswith('--'):
            opt[args[i][2:]] = args[i + 1]
            i += 2
        else:
            pos.append(args[i])
            i += 1
    if args[0] == 'run':
        games = G1 if pos[0] == 'g1' else pos[0].split(',')
        a, b = (opt.get('days', '12-23')).split('-')
        days = list(range(int(a), int(b) + 1))
        sels = opt.get('sel', 'A0,A,Cm,C,' + ','.join(f'D{v}' for v in D_VALUES)).split(',')
        src = opt.get('src', 'leader')
        tag = opt.get('tag', src)
        for g in games:
            t0 = time.time()
            run_world(g, days, sels, src, tag)
            print('world done', g, f'{time.time() - t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
