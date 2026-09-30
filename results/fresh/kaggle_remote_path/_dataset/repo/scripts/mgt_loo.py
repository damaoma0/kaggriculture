"""Routing loss of a Mother-Goose tape-router agent, measured in her own recorded worlds against a live rival.

For a sample of her recorded games (compact tapes in data/mg_tapes), the world is recreated (same seed, her
shops forced, natural weeds) and played in her seat in three arms:
  native_raw      her own tape, equilibrium opening, no layers (the policy's true value in that world)
  native_chassis  the agent restricted to that one tape (MGT_ONLY): what the chassis layers cost or add
  loo             the agent with that tape removed from its library (MGT_EXCLUDE): the pure routing loss
Output: results/fresh/mg_tape/loo/<agent>-<arm>-<episode>.json
  mg_vs / mg_vs_only   HER recorded tape in her seat against live <rival> (tape excluded / rival restricted to it)
Usage:  python mgt_loo.py <agent> [rival=v50_public] [n_worlds=40] [arms=native_raw,native_chassis,loo] [offset=0]
"""
import gzip, json, os, random, sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from market_corpus import ROOT
import tape_vs_bench as TV
from build_mg_tape_agent import fix_opening

OUT = ROOT / 'results/fresh/mg_tape/loo'


def run(job):
    name, rival, arm, path = job
    tape = json.load(gzip.open(path, 'rt', encoding='utf-8'))
    ep, seat = tape['episode'], tape['seat']
    if arm == 'native_chassis':
        os.environ['MGT_ONLY'] = str(ep)
    elif arm == 'loo':
        os.environ['MGT_EXCLUDE'] = str(ep)
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    rp = ROOT / 'agents' / f'{rival}.py'
    opp = get_last_callable(rp.read_text(encoding='utf-8'), path=str(rp))
    history = None
    sheep = None
    if arm.startswith(('mg_late', 'mg_sell', 'mg_oracle')):
        # hindsight ceilings (research hooks of the router template): mg_late<D> = her tape for this world hidden
        # until day D, then forced; mg_sell<D> = a neighbour's crew and purchases with HER sell orders from day D;
        # mg_oracle = her tape removed, the router ranks against the world's full shop list from day 3
        for k in ('MGT_EXCLUDE', 'MGT_ONLY', 'MGT_LATE_ONLY', 'MGT_SELL_FROM', 'MGT_ORACLE_SHOPS'):
            os.environ.pop(k, None)
        if arm.startswith('mg_late'):
            os.environ['MGT_LATE_ONLY'] = f'{ep}:{int(arm[7:])}'
        elif arm.startswith('mg_sell'):
            os.environ['MGT_SELL_FROM'] = f'{ep}:{int(arm[7:])}'
        else:
            os.environ['MGT_EXCLUDE'] = str(ep)
            os.environ['MGT_ORACLE_SHOPS'] = ','.join(tape['shops'][30])
        rp = ROOT / 'agents' / f'{rival}.py'
        opp = get_last_callable(rp.read_text(encoding='utf-8'), path=str(rp))
    if arm in ('mg_vs', 'mg_vs_only'):
        # head to head: HER recorded moves in her own world against the live rival. mg_vs: the rival's tape library
        # must not contain this world (MGT_EXCLUDE, read when the file is loaded below) - the ladder situation.
        # mg_vs_only: the rival is restricted to this very tape (MGT_ONLY) - same plan on both sides, so the margin
        # is what the chassis repairs and the overlay add to or take from her original.
        os.environ['MGT_EXCLUDE' if arm == 'mg_vs' else 'MGT_ONLY'] = str(ep)
        rp = ROOT / 'agents' / f'{rival}.py'
        opp = get_last_callable(rp.read_text(encoding='utf-8'), path=str(rp))
    if arm == 'native_raw' or arm.startswith('mg_'):
        actions = [a if isinstance(a, dict) else {} for a in tape['actions']]
        fix_opening(actions)
        ours = lambda obs, t: deepcopy(actions[t]) if t < len(actions) else {'farmer': ['PASS'], 'hands': [], 'market': []}
    else:
        ns = {'__name__': 'mgt'}
        exec(compile((ROOT / 'agents' / f'{name}.py').read_text(encoding='utf-8'), name, 'exec'), ns)
        agent = ns['agent']
        ours = lambda obs, t: agent(obs)
        history = ns['_MGT_HISTORY']
        sheep = ns.get('_SHP_REPORT')
    _items = ('WOOL', 'MILK', 'MELON', 'STRAWBERRY', 'TOMATO', 'EGG')
    trace = dict(price={k: [] for k in _items}, ours={k: {} for k in _items}, rival={k: {} for k in _items},
                 melon_ready=[[], []], melon_index=[{}, {}], index={'ours': {k: {} for k in _items}, 'rival': {k: {} for k in _items}},
                 orders={'ours': {}, 'rival': {}}, service=[[], []])

    def logged(fn, who):
        def call(obs, t):
            a = fn(obs, t)
            if who == 'ours':
                for k in trace['price']:
                    trace['price'][k].append(obs['market']['prices'].get(k))
                day = t // 24
                if t % 24 == 23:                       # servicing snapshot (hour-23 actions are not in it)
                    for side, farm in ((0, obs['farms'][seat]), (1, obs['farms'][1 - seat])):
                        snap = {}
                        for row in farm['tiles']:
                            for c in row:
                                if isinstance(c, dict) and c.get('animal'):
                                    v = snap.setdefault(c['animal'], [0, 0, 0, 0, 0])
                                    v[0] += 1
                                    v[1] += bool(c.get('fed_today'))
                                    v[2] += bool(c.get('cared_today'))
                                    v[3] += int(c.get('pending_care_bonus', 0) or 0)
                                    v[4] += int(c.get('yield_units', 0) or 0)
                        trace['service'][side].append(snap)
                for side, farm in ((0, obs['farms'][seat]), (1, obs['farms'][1 - seat])):
                    trace['melon_ready'][side].append(sum(
                        1 for row in farm['tiles'] for c in row
                        if isinstance(c, dict) and c.get('kind') == 'PLANT' and c.get('crop') == 'MELON'
                        and day - int(c.get('planted_day', day)) >= 10))
            for j, o in enumerate((a.get('market') or []) if isinstance(a, dict) else []):
                if o and o[0] == 'SELL' and len(o) >= 3 and o[1] == 'MELON' and int(o[2]) > 0:
                    trace['melon_index'][0 if who == 'ours' else 1][t] = j      # position of the melon SELL in the order list
                if o and o[0] == 'SELL' and len(o) >= 3 and o[1] in trace['index'][who] and int(o[2]) > 0:
                    trace['index'][who][o[1]].setdefault(t, j)                  # first position of that product's SELL
            if isinstance(a, dict) and a.get('market'):
                trace['orders'][who][t] = len(a['market'])
            for o in (a.get('market') or []) if isinstance(a, dict) else []:
                if o and o[0] == 'SELL' and len(o) >= 3 and o[1] in trace[who] and int(o[2]) > 0:
                    trace[who][o[1]][t] = trace[who][o[1]].get(t, 0) + int(o[2])
            return a
        return call

    players = [None, None]
    players[seat] = logged(ours, 'ours')
    players[1 - seat] = logged(lambda obs, t: opp(obs), 'rival')
    env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': tape['seed']})
    res = TV._play(E, env, players, seat, tape['shops'], None, None, seat)
    d = res['daily'][seat][-1]
    out = dict(agent=name, rival=rival, arm=arm, episode=ep, seat=seat, shops=tape['shops'][30],
               final=res['final'][seat], rival_final=res['final'][1 - seat], margin=res['final'][seat] - res['final'][1 - seat],
               revenue=d['revenue'], spend=d['spend'], sold=d['sold_units'], rival_revenue=res['daily'][1 - seat][-1]['revenue'],
               rival_spend=res['daily'][1 - seat][-1]['spend'], rival_sold=res['daily'][1 - seat][-1]['sold_units'],
               rival_revenue_daily=[{k: round(v) for k, v in x['revenue'].items()} for x in res['daily'][1 - seat]],
               rival_history=[list(h) for h in (getattr(opp, '__globals__', {}).get('_MGT_HISTORY') or [])],
               rival_sheep=json.loads(json.dumps(getattr(opp, '__globals__', {}).get('_SHP_REPORT') or {}, default=list)),
               rival_report=json.loads(json.dumps(getattr(opp, '__globals__', {}).get('_MGT_REPORT') or {}, default=str)),
               no_effect=d['physical'].get('no_effect', 0), missing=d['physical'].get('missing_worker_commands', 0),
               cash_daily=[x['money'] for x in res['daily'][seat]], history=list(history) if history is not None else None,
               revenue_daily=[{k: round(v) for k, v in x['revenue'].items()} for x in res['daily'][seat]],
               units_daily=[dict(x['sold_units']) for x in res['daily'][seat]],
               rival_units_daily=[dict(x['sold_units']) for x in res['daily'][1 - seat]],
               sheep=json.loads(json.dumps(sheep, default=list)) if sheep else None, trace=trace)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f'{name}-{arm}-{ep}.json').write_text(json.dumps(out), encoding='utf-8')
    return out


def main():
    name = sys.argv[1]
    rival = sys.argv[2] if len(sys.argv) > 2 else 'v50_public'
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 40
    arms = (sys.argv[4] if len(sys.argv) > 4 else 'native_raw,native_chassis,loo').split(',')
    off = int(sys.argv[5]) if len(sys.argv) > 5 else 0          # worlds [off, off + n) of the fixed shuffle
    files = sorted(p for s in ('56266758', '56266899') for p in (ROOT / 'data/mg_tapes' / s).glob('*.json.gz'))
    random.Random(20260920).shuffle(files)
    jobs = []
    for p in files[off:off + n]:
        ep = p.name.split('.')[0]
        for arm in arms:
            key = 'any' if arm == 'native_raw' else (f'mgtape_vs_{rival}' if arm.startswith('mg_') else name)
            if os.environ.get('MGT_FORCE') or not (OUT / f'{key}-{arm}-{ep}.json').exists():
                jobs.append((key, rival, arm, str(p)))
    # memory guard (shared machine): ~0.92 GB a worker, keep 2 GB free, never more than 4 (LP_WORKERS caps lower)
    import psutil
    avail = psutil.virtual_memory().available / 1e9
    workers = max(0, min(4, int(os.environ.get('LP_WORKERS', 4)), int((avail - 2.0) / 0.92)))
    print(f'{len(jobs)} games, {workers} workers ({avail:.1f} GB free)', flush=True)
    if not workers:
        raise SystemExit('not enough free memory for one game worker; aborting')
    with ProcessPoolExecutor(max_workers=workers, max_tasks_per_child=1) as pool:
        futures = {pool.submit(run, j): j for j in jobs}
        for f in as_completed(futures):
            try:
                r = f.result()
                print(f"{r['arm']:15s} {r['episode']}: margin {r['margin']:+9,.0f} final {r['final']:9,.0f}", flush=True)
            except Exception as exc:
                print(f'FAILED {futures[f][2]} {futures[f][3][-20:]}: {type(exc).__name__}: {exc}', flush=True)


if __name__ == '__main__':
    main()
