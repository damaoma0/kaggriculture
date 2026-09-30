"""Paired trace of two builds in one ladder-panel world (same harness as scripts/ladder_panel.py run: seed, forced
shops, the opponent's recorded actions, our build through Kaggle's loader), with engine hooks on our seat.

usage: lead_world_trace.py run <agentA,agentB> <ep[,ep]> [submission=p2750]
       lead_world_trace.py compare <agentA> <agentB> <ep>
Per day: harvested units, our sales (units / revenue by product and hour), the rival's sales, failed buys (with hour),
the shed and the units' carried inventory at midnight and the shed overflow the end-of-day dump discards, cash at
hour 0; per step: our action dict (first divergence). Results: results/fresh/lead_world_trace/<agent>_<ep>.json
"""
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
OUT = ROOT / 'results/fresh/lead_world_trace'
PASS = {'farmer': ['PASS'], 'hands': [], 'market': []}


def run_one(name, path):
    import tape_vs_bench as TV
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    g = json.load(gzip.open(path, 'rt', encoding='utf-8'))
    seat, rec = g['seat'], g['opp_actions']
    ap = ROOT / 'agents' / f'{name}.py'
    entry = get_last_callable(ap.read_text(encoding='utf-8'), path=str(ap))
    days = [dict(harv=Counter(), sold=Counter(), rev=Counter(), sold_h=Counter(), rsold=Counter(), rrev=Counter(),
                 failed=Counter(), bought=Counter(), spend=Counter(), cash0=None, shed_mid=None, carried_mid=None,
                 overflow=Counter()) for _ in range(30)]
    acts = []
    farms_box, step_box = [], [0]
    old_apply, old_commit, old_end = E._apply_unit_action, E._commit_unit, E._end_of_day

    def is_me(farm):
        return bool(farms_box) and farm is farms_box[0][seat]

    def is_rival(farm):
        return bool(farms_box) and farm is farms_box[0][1 - seat]

    def apply_hook(farm, private, idx, action, board_size, day, tpd, shed_capacity=100):
        if not is_me(farm):
            return old_apply(farm, private, idx, action, board_size, day, tpd, shed_capacity)
        inv0 = dict(private['inventories'][idx]) if idx < len(private['inventories']) else {}
        r = old_apply(farm, private, idx, action, board_size, day, tpd, shed_capacity)
        if isinstance(action, list) and action and action[0] == 'HARVEST':
            inv1 = private['inventories'][idx] if idx < len(private['inventories']) else {}
            for k, v in inv1.items():
                if v > inv0.get(k, 0):
                    days[min(29, day)]['harv'][k] += v - inv0.get(k, 0)
        return r

    def commit_hook(op, item, price, farm, private, market, shed_capacity=100):
        r = old_commit(op, item, price, farm, private, market, shed_capacity)
        t = step_box[0]
        dd = days[min(29, t // 24)]
        if is_me(farm):
            if not r and op != 'SELL':
                dd['failed'][f'{op}:{item}@{t % 24}'] += 1
            elif r and op == 'SELL':
                dd['sold'][item] += 1
                dd['rev'][item] += price
                dd['sold_h'][f'{item}@{t % 24}'] += 1
            elif r:
                dd['bought'][f'{op}:{item}'] += 1
                dd['spend'][f'{op}:{item}'] += price
        elif is_rival(farm) and r and op == 'SELL':
            dd['rsold'][item] += 1
            dd['rrev'][item] += price
        return r

    def end_hook(state, environment, day):
        f = state[0].observation.farms[seat]
        # private state of our seat: the shed and the units' inventories before the end-of-day dump
        priv = None
        try:
            priv = state[seat].observation.private
        except Exception:
            priv = None
        shed0 = Counter({k: int(v) for k, v in dict(getattr(priv, 'shed', None) or (priv or {}).get('shed', {}) or {}).items() if v}) if priv is not None else Counter()
        invs = (getattr(priv, 'inventories', None) or (priv or {}).get('inventories', [])) if priv is not None else []
        carried = Counter()
        for inv in invs or []:
            for k, v in dict(inv).items():
                if v:
                    carried[k] += int(v)
        old_end(state, environment, day)
        try:
            priv2 = state[seat].observation.private
            shed1 = Counter({k: int(v) for k, v in dict(getattr(priv2, 'shed', None) or priv2.get('shed', {}) or {}).items() if v})
        except Exception:
            shed1 = Counter()
        dd = days[min(29, day)]
        dd['shed_mid'] = dict(shed0)
        dd['carried_mid'] = dict(carried)
        for k in set(shed0) | set(carried):
            lost = shed0.get(k, 0) + carried.get(k, 0) - shed1.get(k, 0)
            if lost > 0:
                dd['overflow'][k] += lost

    def real_wrap(interp):
        def real(state, environment):
            farms = getattr(state[0].observation, 'farms', None)
            if farms:
                farms_box[:] = [farms]
            step_box[0] = int(getattr(state[0].observation, 'step', 0) or 0)
            return interp(state, environment)
        return real

    def ours(obs, t):
        d, h = divmod(t, 24)
        if h == 0 and d < 30:
            days[d]['cash0'] = obs['farms'][seat]['money']
        a = entry(obs)
        acts.append(json.dumps(a, sort_keys=True))
        return a

    players = [None, None]
    players[seat] = ours
    players[1 - seat] = lambda obs, t: (rec[t] if t < len(rec) and isinstance(rec[t], dict) and rec[t] else dict(PASS))
    E._apply_unit_action, E._commit_unit, E._end_of_day = apply_hook, commit_hook, end_hook
    try:
        env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': g['seed']})
        env.interpreter = real_wrap(env.interpreter)
        res = TV._play(E, env, players, seat, g['shops'], None, None, seat)
    finally:
        E._apply_unit_action, E._commit_unit, E._end_of_day = old_apply, old_commit, old_end
    out = dict(agent=name, episode=g['episode'], seat=seat, final=res['final'][seat], rival=res['final'][1 - seat],
               margin=res['final'][seat] - res['final'][1 - seat], actions=acts,
               days=[{k: (dict(v) if isinstance(v, Counter) else v) for k, v in d.items()} for d in days])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f'{name}_{g["episode"]}.json').write_text(json.dumps(out), encoding='utf-8')
    return name, g['episode'], out['final'], out['rival']


def compare(a, b, ep):
    A = json.load(open(OUT / f'{a}_{ep}.json'))
    B = json.load(open(OUT / f'{b}_{ep}.json'))
    print(f'{ep}: {a} own {A["final"]:.0f} rival {A["rival"]:.0f} margin {A["margin"]:.0f} | {b} own {B["final"]:.0f} '
          f'rival {B["rival"]:.0f} margin {B["margin"]:.0f} | diff own {B["final"] - A["final"]:+.0f} rival '
          f'{B["rival"] - A["rival"]:+.0f} margin {B["margin"] - A["margin"]:+.0f}')
    fd = next((t for t, (x, y) in enumerate(zip(A['actions'], B['actions'])) if x != y), None)
    if fd is not None:
        print(f'first divergence: step {fd} (day {fd // 24} hour {fd % 24})')
        print('  ' + a + ': ' + A['actions'][fd][:400])
        print('  ' + b + ': ' + B['actions'][fd][:400])
    tot = {s: Counter() for s in ('A', 'B')}
    print('day | our revenue A / B | rival revenue A / B | harvested A / B | sold units A / B | overflow A / B | '
          'carried at midnight A / B | failed buys A / B')
    for d in range(30):
        da, db = A['days'][d], B['days'][d]
        ra, rb = sum(da['rev'].values()), sum(db['rev'].values())
        qa, qb = sum(da['rrev'].values()), sum(db['rrev'].values())
        for k, s, dd in (('rev', 'A', da), ('rev', 'B', db)):
            tot[s]['rev'] += sum(dd['rev'].values())
            tot[s]['rrev'] += sum(dd['rrev'].values())
            tot[s]['overflow'] += sum(dd['overflow'].values())
            tot[s]['failed'] += sum(dd['failed'].values())
            for p, v in dd['overflow'].items():
                tot[s]['ovf_' + p] += v
        print(f"{d:2d} | {ra:7.0f} / {rb:7.0f} | {qa:7.0f} / {qb:7.0f} | {sum(da['harv'].values()):4d} / "
              f"{sum(db['harv'].values()):4d} | {sum(da['sold'].values()):4d} / {sum(db['sold'].values()):4d} | "
              f"{dict(da['overflow']) or '-'} / {dict(db['overflow']) or '-'} | {sum((da['carried_mid'] or {}).values())} / "
              f"{sum((db['carried_mid'] or {}).values())} | {sum(da['failed'].values())} / {sum(db['failed'].values())}")
    print('totals A:', dict(tot['A']))
    print('totals B:', dict(tot['B']))
    # by product: our units / revenue / price, rival units / revenue / price
    prods = sorted({p for s in (A, B) for d in s['days'] for p in list(d['rev']) + list(d['rrev'])})
    print('product | ours A units rev price | ours B units rev price | rival A units rev price | rival B units rev price')
    for p in prods:
        vals = []
        for S, key_u, key_r in ((A, 'sold', 'rev'), (B, 'sold', 'rev'), (A, 'rsold', 'rrev'), (B, 'rsold', 'rrev')):
            u = sum(d[key_u].get(p, 0) for d in S['days'])
            r = sum(d[key_r].get(p, 0) for d in S['days'])
            vals.append(f'{u:4d} {r:7.0f} {r / u if u else 0:6.1f}')
        print(f'{p:11s} | ' + ' | '.join(vals))
    fa = Counter(); fb = Counter()
    for d in range(30):
        for k, v in A['days'][d]['failed'].items():
            fa[k.split('@')[0]] += v
        for k, v in B['days'][d]['failed'].items():
            fb[k.split('@')[0]] += v
    print('failed buys A:', dict(fa)); print('failed buys B:', dict(fb))


def main():
    if sys.argv[1] == 'compare':
        return compare(sys.argv[2], sys.argv[3], sys.argv[4])
    agents, eps = sys.argv[2].split(','), sys.argv[3].split(',')
    sub = sys.argv[4] if len(sys.argv) > 4 else 'p2750'
    jobs = [(a, str(ROOT / f'data/ladder_panel/{sub}/{e}.json.gz')) for e in eps for a in agents]
    from concurrent.futures import ProcessPoolExecutor, as_completed
    with ProcessPoolExecutor(max_workers=min(4, len(jobs)), max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run_one, *j) for j in jobs]):
            print(f.result(), flush=True)


if __name__ == '__main__':
    main()
