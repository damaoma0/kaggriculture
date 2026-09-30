"""Leader upkeep skips (thread upkeep, 2026-09-25; stored data only, no games).

Every leader game is replayed EXACTLY through the official engine (scripts/upkeep_engine.py: recorded seed, forced
shops, both seats' recorded actions; the final cash of both seats is asserted). Per leader asset-day (a live crop /
animal on the leader's farm at hour 0 of day d) we record
  * the tile's engine state at hour 0 (age, held yield, dryness / hunger, fertilized-until, care bank, fertilizer ready),
    the product price at hour 0, the shed distance, the productions still possible;
  * what OUR maintenance module (scripts/fragments/sem_maintenance.py, called exactly as agents/mgt_lead.py calls it:
    prices = hour-0 market, fertilize 'auto', include_optional, collect=True) requires that day: cmd, value (coins lost
    if skipped today, net of inputs), units lost, kind, deadline;
  * every effective leader op on that tile that day (cmd, hour, unit) and the units it harvested there;
  * the tile's full-production potential V (engine-exact day model of the module, inputs free, actions at hour 0 every
    day, no new fertilizer: V0; with free fertilizer: VF) at hour 0 of day d and at hour 0 of day d+1 (the asset's
    next-morning state), so the output lost on day d is V0(d) - harvested(d) - V0(d+1) (telescopes to the life total).
Per day: units, hires (hour), effective ops by type, moves, no-effect commands, PASS, per hour.

usage: upkeep_skips.py run [teams=16732748,16770421,16730612|all] [--limit N]
Writes results/fresh/upkeep_20260925/skips/<team>_<ep>.json.gz (one per game, written as it finishes).
"""
import copy
import gzip
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import upkeep_engine as UE  # noqa: E402

OUT = ROOT / 'results/fresh/upkeep_20260925/skips'
G1_TEAMS = ['16732748', '16770421', '16730612']
MOVES = {'NORTH', 'SOUTH', 'EAST', 'WEST'}
TILE_OPS = {'WATER', 'FEED', 'CARE', 'FERTILIZE', 'HARVEST', 'COLLECT_FERTILIZER', 'PLANT', 'DIG', 'BUILD_COOP',
            'BUILD_PASTURE'}


def load_sm():
    ns = {}
    src = (ROOT / 'scripts/fragments/sem_maintenance.py').read_text(encoding='utf-8')
    exec(compile(src, 'sem_maintenance', 'exec'), ns)
    return ns


SM = load_sm()


def asset_of(t):
    if not isinstance(t, dict):
        return None
    if t.get('kind') == 'PLANT' and t.get('crop') in SM['SM_CROPS']:
        return t['crop'], int(t['planted_day'])
    if t.get('animal') in SM['SM_ANIMALS']:
        return t['animal'], int(t['placed_day'])
    return None


def potential(kind, st, day, fert_ok):
    """max product units from hour 0 of `day` on (inputs free, actions at hour 0 every day)."""
    if st is None or day > SM['SM_LAST_DAY']:
        return 0
    S = SM['_sm_solver'](kind, bool(fert_ok), 0, 0, 0)
    r = S.value(st, day)
    return int(r[0][1]) if r and r[1] is not None else 0


def prods_left(kind, st, day):
    """production refreshes still possible from day `day` (end-of-day refreshes on days day..28)."""
    if kind in SM['SM_CROPS']:
        cd = SM['SM_CROPS'][kind]
        if not cd['ongoing']:
            return 1
        n = 0
        for dd in range(day, SM['SM_LAST_REFRESH_DAY'] + 1):
            dsf = dd + 1 - st[0] - cd['first_yield_day']
            if dsf >= 0 and dsf % cd['interval'] == 0 and dsf // cd['interval'] + 1 <= cd['max_yield']:
                n += 1
        return n
    a = SM['SM_ANIMALS'][kind]
    return sum(1 for dd in range(day, SM['SM_LAST_REFRESH_DAY'] + 1)
               if dd + 1 - st[0] - a['first_yield_day'] >= 0 and (dd + 1 - st[0] - a['first_yield_day']) % a['interval'] == 0)


def play(team, ep):
    SM['_SM_SOLVERS'].clear()          # per-game caches: memo growth across games only costs GC time
    SM['_SM_PLAN_CACHE'].clear()
    E = UE.engine()
    tape = UE.load_tape(team, ep)
    seat = tape['seat']
    w = UE.World(tape['seed'], tape['shops'])
    me = w.farms[seat]
    rec_ops = []            # (t, unit, op, tile_idx, effective, harvested units, product, asset-before)
    hires = []
    orig_apply, orig_hire = E._apply_unit_action, E._do_hire

    def apply_hook(farm, private, idx, action, board_size, day, tpd, shed_capacity=100):
        if farm is not me:
            return orig_apply(farm, private, idx, action, board_size, day, tpd, shed_capacity)
        op = action[0] if isinstance(action, list) and action else None
        p0 = E._farmer_position(farm, idx)
        if p0 is None or op is None:
            return orig_apply(farm, private, idx, action, board_size, day, tpd, shed_capacity)
        p0 = (int(p0[0]), int(p0[1]))
        t0 = farm['tiles'][p0[1]][p0[0]]
        t0c = dict(t0) if isinstance(t0, dict) else t0
        inv = private['inventories'][idx] if idx < len(private['inventories']) else {}
        inv0 = dict(inv)
        shed0 = dict(private['shed'])
        r = orig_apply(farm, private, idx, action, board_size, day, tpd, shed_capacity)
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
        a0 = asset_of(t0c)
        rec_ops.append((w.t, idx, op, p0[1] * 10 + p0[0], int(eff), hv, prod, a0))
        return r

    def hire_hook(farm, private, board_size, mult=1):
        n0 = len(farm['hands'])
        orig_hire(farm, private, board_size, mult)
        if farm is me and len(farm['hands']) > n0:
            hires.append(w.t)

    E._apply_unit_action, E._do_hire = apply_hook, hire_hook
    days_out, assets_out = [], []
    prev = {}             # (idx, kind, start) -> index into assets_out for the previous day's record
    try:
        for d in range(30):
            # ---- hour 0 of day d
            obs = w.obs(seat)
            tiles = me['tiles']
            prices = dict(w.market['prices'])
            try:
                jl = SM['maintenance_jobs'](obs, seat, prices=None, fertilize='auto', include_optional=True,
                                            collect=True, log=[])
            except Exception as exc:     # never expected; recorded
                jl = []
                print('mj error', team, ep, d, exc)
            jobs_by = defaultdict(list)
            for j in jl:
                jobs_by[j['tile'][1] * 10 + j['tile'][0]].append(j)
            live = {}
            for y in range(10):
                for x in range(10):
                    a = asset_of(tiles[y][x])
                    if a:
                        live[y * 10 + x] = (a, SM['_sm_state'](a[0], tiles[y][x]), dict(tiles[y][x]))
            # close yesterday's records with this morning's state
            for key, ai in list(prev.items()):
                idx, kind, start = key
                cur = live.get(idx)
                rr = assets_out[ai]
                if cur and cur[0] == (kind, start):
                    rr['alive1'] = 1
                    rr['V0_1'] = potential(kind, cur[1], d, False)
                    rr['VF_1'] = potential(kind, cur[1], d, True)
                else:
                    rr['alive1'] = 0
                    rr['V0_1'] = rr['VF_1'] = 0
            prev = {}
            cash0 = float(me['money'])
            for idx, ((kind, start), st, raw) in sorted(live.items()):
                product = SM['_sm_product'](kind)
                x, y = idx % 10, idx // 10
                mj = [[j['cmd'], j['value'], j['units'], j['kind'], j['deadline'], int(bool(j.get('optional'))),
                       j.get('held', 0)] for j in jobs_by.get(idx, []) if j.get('asset') == kind]
                rr = dict(d=d, i=idx, k=kind, s=start, st=list(st), p=prices.get(product), dist=SM['_sm_shed_dist'](x, y),
                          pl=prods_left(kind, st, d), V0=potential(kind, st, d, False), VF=potential(kind, st, d, True),
                          mj=mj, ops=[], hv=0, fa=int(bool(raw.get('fertilizer_available'))))
                prev[(idx, kind, start)] = len(assets_out)
                assets_out.append(rr)
            # ---- play the day
            n0 = len(rec_ops)
            h0 = len(hires)
            for h in range(24):
                t = w.t
                if t >= 719:
                    break
                acts = [None, None]
                acts[seat] = UE.tape_action(tape['actions'], t)
                acts[1 - seat] = UE.tape_action(tape['opp_actions'], t)
                w.step(acts)
            dops = rec_ops[n0:]
            # attribute ops to asset records
            by_key = {k: assets_out[v] for k, v in prev.items()}
            ops_by_type, noeff, passes, moves = Counter(), Counter(), 0, 0
            per_hour = [Counter() for _ in range(24)]
            unit_steps = Counter()
            planted, dug_live, harv_units = Counter(), Counter(), Counter()
            for (t, u, op, idx, eff, hv, prod, a0) in dops:
                h = t % 24
                unit_steps[u] += 1
                if op == 'PASS':
                    passes += 1
                    per_hour[h]['PASS'] += 1
                    continue
                if op in MOVES:
                    if eff:
                        moves += 1
                        per_hour[h]['MOVE'] += 1
                    else:
                        noeff['MOVE'] += 1
                        per_hour[h]['NOEFF'] += 1
                    continue
                if not eff:
                    noeff[op] += 1
                    per_hour[h]['NOEFF'] += 1
                    continue
                ops_by_type[op] += 1
                per_hour[h][op] += 1
                if op == 'PLANT':
                    t_after = me['tiles'][idx // 10][idx % 10]
                    planted['n'] += 1
                if op == 'HARVEST' and prod:
                    harv_units[prod] += hv
                if op == 'DIG' and a0:
                    dug_live[a0[0]] += 1
                if a0 is not None:
                    r_ = by_key.get((idx, a0[0], a0[1]))
                    if r_ is not None:
                        r_['ops'].append([op, h, u])
                        if op == 'HARVEST':
                            r_['hv'] += hv
            hh = [t % 24 for t in hires[h0:]]
            days_out.append(dict(d=d, cash0=cash0, prices=prices, units=1 + len(hh), hire_hours=hh,
                                 ops=dict(ops_by_type), noeff=dict(noeff), passes=passes, moves=moves,
                                 per_hour=[dict(c) for c in per_hour], unit_steps=dict(unit_steps),
                                 planted=planted.get('n', 0), dug_live=dict(dug_live), harv_units=dict(harv_units),
                                 n_jobs=len(jl)))
        for key, ai in prev.items():
            assets_out[ai]['alive1'] = 1
            assets_out[ai]['V0_1'] = assets_out[ai]['VF_1'] = 0
    finally:
        E._apply_unit_action, E._do_hire = orig_apply, orig_hire
    final = [float(w.farms[i]['money']) for i in range(2)]
    ok = [round(x) for x in final] == [round(float(x)) for x in tape['rewards']]
    return dict(game=f'{team}:{ep}', team=team, episode=int(ep), seat=seat, final=final, rewards=tape['rewards'],
                cash_match=ok, days=days_out, assets=assets_out)


def main():
    args = sys.argv[1:]
    if not args or args[0] != 'run':
        print(__doc__)
        return
    teams = G1_TEAMS
    limit = None
    for a in args[1:]:
        if a.startswith('teams='):
            v = a.split('=', 1)[1]
            teams = sorted(p.name for p in UE.SEM.iterdir() if p.is_dir()) if v == 'all' else v.split(',')
    if '--limit' in args:
        limit = int(args[args.index('--limit') + 1])
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    n = bad = 0
    for team in teams:
        eps = sorted(int(p.name.split('.')[0]) for p in (UE.SEM / team).glob('*.json.gz'))
        for ep in eps[:limit] if limit else eps:
            f = OUT / f'{team}_{ep}.json.gz'
            if f.exists():
                continue
            try:
                r = play(team, ep)
            except IndexError:
                print('no tape', team, ep)
                continue
            n += 1
            if not r['cash_match']:
                bad += 1
                print('CASH MISMATCH', team, ep, r['final'], r['rewards'])
            with gzip.open(f, 'wt', encoding='utf-8') as fh:
                json.dump(r, fh, separators=(',', ':'))
            print(f'{n} games, {bad} mismatches, {time.time() - t0:.0f}s  {team}:{ep}', flush=True)
    print(f'done: {n} games, {bad} cash mismatches, {time.time() - t0:.0f}s')


if __name__ == '__main__':
    main()
