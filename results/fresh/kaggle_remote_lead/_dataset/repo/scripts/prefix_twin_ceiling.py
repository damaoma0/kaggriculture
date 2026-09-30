"""Direction 3 ceiling: what is PERFECT COVERAGE of the known shops worth when the rest are still unknown?

In Mother-Goose's recorded worlds W (the 128 held-out h2h worlds, where arm A = ladder case and arm B = her own tape
for W are already measured for mgt_m1), our agent is forced (MGT_ONLY) onto a DIFFERENT recorded tape T - a "twin"
whose shop history agrees with W's for the first k reveals and then goes its own way. Her recorded moves play her
seat, as in scripts/mgt_loo.py (frozen opponent: cannot react).
  twin k (ordered):  T's first k shops are W's first k shops, in order; reveal k+1 differs.
  twin k (demand):   T's weighted demand vector equals W's at every router checkpoint <= k (used only when no ordered
                     twin exists; this is what the router itself treats as a perfect match).
k = 8 is arm B (her own tape). The curve margin(k) is the value of covering the first k shops exactly, with
reveals k+1..8 random relative to the world - the ceiling a library can reach without foresight.

usage: prefix_twin_ceiling.py plan            (write the job list, no games)
       prefix_twin_ceiling.py run [agent=mgt_m1]
       prefix_twin_ceiling.py report [agent=mgt_m1]
"""
import gzip, json, os, random, sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
OUT = ROOT / 'results/fresh/newphase_20260923/prefix_twins'
LOO = ROOT / 'results/fresh/mg_tape/loo'
W8 = {'STRAWBERRY': 3.0, 'TOMATO': 2.0, 'WOOL': 2.0, 'CARROT': 1.5, 'MILK': 1.5, 'EGG': 1.0, 'WHEAT': 0.5}
DEM = {'BAKERY': {'EGG': 1, 'WHEAT': 1}, 'PIZZA_SHOP': {'MILK': 1, 'TOMATO': 1, 'WHEAT': 1},
       'BRUNCH_SPOT': {'EGG': 1, 'WHEAT': 1, 'STRAWBERRY': 1}, 'YARN_STORE': {'WOOL': 2},
       'ICE_CREAM_SHOP': {'STRAWBERRY': 1, 'MILK': 1, 'WHEAT': 1}, 'PET_CAFE': {'CARROT': 2},
       'SMOOTHIE_SHOP': {'STRAWBERRY': 1, 'MILK': 1},
       'FARMERS_MARKET': {'WHEAT': 1, 'CARROT': 1, 'TOMATO': 1, 'STRAWBERRY': 1}}
CHECK = (2, 4, 5, 6, 8)


def seq(sh):
    out, seen = [], 0
    for cur in sh:
        while len(cur) > seen:
            out.append(cur[seen]); seen += 1
    return out[:8]


def dvec(s, k):
    v = {p: 0 for p in W8}
    for x in s[:k]:
        for p, c in DEM[x].items():
            v[p] += c
    return tuple(v[p] for p in W8)


def demand_equal(a, b, k):
    return all(dvec(a, j) == dvec(b, j) for j in CHECK if j <= k) and dvec(a, k) == dvec(b, k)


def library():
    tapes = {}
    for p in sorted((ROOT / 'data/mg_tapes').rglob('*.json.gz')):
        g = json.load(gzip.open(p, 'rt', encoding='utf-8'))
        tapes[str(g['episode'])] = dict(path=str(p), shops=seq(g['shops']))
    return tapes


def plan():
    tapes = library()
    lib_eps = set(json.loads((ROOT / 'results/fresh/newphase_20260923/library_episode_ids.json').read_text()))
    worlds = sorted(f.name.split('-')[-1].split('.')[0] for f in LOO.glob('mgtape_vs_mgt_m1-mg_vs_only-*.json'))
    rng = random.Random(923)
    jobs, avail = [], {}
    for w in worlds:
        sw = tapes[w]['shops']
        for k in (1, 2, 3, 4, 5, 6):
            cand = [t for t, x in tapes.items() if t != w and int(t) in lib_eps
                    and x['shops'][:k] == sw[:k] and x['shops'][k] != sw[k]]
            kind = 'ordered'
            if not cand and k >= 4:
                cand = [t for t, x in tapes.items() if t != w and int(t) in lib_eps and demand_equal(x['shops'], sw, k)
                        and not demand_equal(x['shops'], sw, min(8, k + 1))]
                kind = 'demand'
            if not cand:
                continue
            avail.setdefault(k, {}).setdefault(kind, 0)
            avail[k][kind] += 1
            if k == 1 and sum(1 for j in jobs if j['k'] == 1) >= 64:
                continue
            jobs.append(dict(world=w, twin=rng.choice(sorted(cand)), k=k, kind=kind, n_cand=len(cand)))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'plan.json').write_text(json.dumps(dict(worlds=len(worlds), availability=avail, jobs=jobs), indent=1))
    print(f'{len(worlds)} worlds; twins available per k: {avail}; {len(jobs)} games planned')


def run_one(job):
    agent, j = job
    os.environ['MGT_ONLY'] = j['twin']
    import tape_vs_bench as TV
    from build_mg_tape_agent import fix_opening
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    tape = json.load(gzip.open(library()[j['world']]['path'], 'rt', encoding='utf-8'))
    seat = tape['seat']
    actions = [a if isinstance(a, dict) else {} for a in tape['actions']]
    fix_opening(actions)
    her = lambda obs, t: deepcopy(actions[t]) if t < len(actions) else {'farmer': ['PASS'], 'hands': [], 'market': []}
    ap = ROOT / 'agents' / f'{agent}.py'
    entry = get_last_callable(ap.read_text(encoding='utf-8'), path=str(ap))
    lib = entry.__globals__['_MGT_TAPES']
    assert len(lib) == 1 and str(lib[0]['ep']) == j['twin'], (len(lib), j['twin'])
    players = [None, None]
    players[seat] = her                                   # her recorded tape in HER seat
    players[1 - seat] = lambda obs, t: entry(obs)         # our agent in the other seat, restricted to the twin
    env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': tape['seed']})
    res = TV._play(E, env, players, seat, tape['shops'], None, None, seat)
    ours, hers = res['final'][1 - seat], res['final'][seat]
    out = dict(j, agent=agent, ours=ours, hers=hers, margin=ours - hers,
               no_effect=res['daily'][1 - seat][-1]['physical'].get('no_effect', 0))
    (OUT / agent).mkdir(parents=True, exist_ok=True)
    (OUT / agent / f"{j['world']}-k{j['k']}.json").write_text(json.dumps(out), encoding='utf-8')
    return out


def run(agent):
    """Memory-adaptive: the machine is shared. A new game (~0.92 GB) starts only while at most 4 are in flight AND
    free memory stays above 2 GB + one worker; otherwise wait for a game to finish or memory to free up.
    The decisive cells run first (k=4, then 5, 6, 3, 2, 1) so a partial run is still usable."""
    import time
    import psutil
    from concurrent.futures import FIRST_COMPLETED, wait
    order = {4: 0, 5: 1, 6: 2, 3: 3, 2: 4, 1: 5}
    jobs = sorted((j for j in json.loads((OUT / 'plan.json').read_text())['jobs']
                   if not (OUT / agent / f"{j['world']}-k{j['k']}.json").exists()), key=lambda j: order.get(j['k'], 9))
    print(f'{len(jobs)} games, up to 4 workers, free {psutil.virtual_memory().available / 1e9:.1f} GB', flush=True)
    live = {}
    with ProcessPoolExecutor(max_workers=4, max_tasks_per_child=1) as pool:
        while jobs or live:
            free = psutil.virtual_memory().available / 1e9
            if jobs and len(live) < 4 and free > 2.0 + 0.92:
                j = jobs.pop(0)
                live[pool.submit(run_one, (agent, j))] = j
                time.sleep(8)                                  # let the new worker reach its footprint before re-checking
                continue
            if not live:
                time.sleep(15)
                continue
            done, _ = wait(list(live), timeout=15, return_when=FIRST_COMPLETED)
            for f in done:
                j = live.pop(f)
                try:
                    r = f.result()
                    print(f"k={r['k']} {r['kind']:7s} {r['world']} twin {r['twin']}: margin {r['margin']:+9,.0f} "
                          f"(free {psutil.virtual_memory().available / 1e9:.1f} GB, {len(live)} running)", flush=True)
                except Exception as exc:
                    print('FAILED', j, type(exc).__name__, exc, flush=True)


def ci(xs, n=10000):
    rng = random.Random(7)
    m = sorted(sum(rng.choices(xs, k=len(xs))) / len(xs) for _ in range(n))
    return m[int(.025 * n)], m[int(.975 * n)]


def report(agent):
    # mgt_loo stores the margin from HER seat (her final - ours); flip it to OUR perspective like the twin rows
    def load(arm):
        out = {}
        for f in LOO.glob(f'mgtape_vs_{agent}-{arm}-*.json'):
            r = json.loads(f.read_text())
            r['margin'] = -r['margin']
            out[f.name.split('-')[-1][:-5]] = r
        return out
    A, B = load('mg_vs'), load('mg_vs_only')
    rows = [json.loads(f.read_text()) for f in (OUT / agent).glob('*.json')]
    res = {}
    for k in sorted({r['k'] for r in rows}):
        rs = [r for r in rows if r['k'] == k and r['world'] in A and r['world'] in B]
        if not rs:
            continue
        m = [r['margin'] for r in rs]
        dA = [r['margin'] - A[r['world']]['margin'] for r in rs]
        dB = [r['margin'] - B[r['world']]['margin'] for r in rs]
        res[k] = dict(n=len(rs), ordered=sum(r['kind'] == 'ordered' for r in rs), wins=sum(x > 0 for x in m),
                      mean=sum(m) / len(m), ci=ci(m), vsA=sum(dA) / len(dA), vsA_ci=ci(dA), vsB=sum(dB) / len(dB),
                      vsB_ci=ci(dB), A_same=sum(A[r['world']]['margin'] for r in rs) / len(rs),
                      B_same=sum(B[r['world']]['margin'] for r in rs) / len(rs),
                      no_effect=sum(r['no_effect'] for r in rs) / len(rs))
        r = res[k]
        print(f"twin k={k} ({r['ordered']}/{r['n']} ordered) n={r['n']:3d} W-L {r['wins']}-{r['n'] - r['wins']}  mean {r['mean']:+8,.0f} "
              f"({r['ci'][0]:+,.0f}..{r['ci'][1]:+,.0f}) | vs A {r['vsA']:+7,.0f} ({r['vsA_ci'][0]:+,.0f}..{r['vsA_ci'][1]:+,.0f}) | "
              f"vs B {r['vsB']:+7,.0f} ({r['vsB_ci'][0]:+,.0f}..{r['vsB_ci'][1]:+,.0f}) | A {r['A_same']:+,.0f} B {r['B_same']:+,.0f} on same worlds")
    a = [A[w]['margin'] for w in B if w in A]
    b = [B[w]['margin'] for w in B if w in A]
    print(f"arm A (router, her tape removed) n={len(a)} mean {sum(a) / len(a):+,.0f}; arm B (her own tape, k=8) mean {sum(b) / len(b):+,.0f}")
    (OUT / f'report_{agent}.json').write_text(json.dumps(res, indent=1))


if __name__ == '__main__':
    mode = sys.argv[1]
    agent = sys.argv[2] if len(sys.argv) > 2 else 'mgt_m1'
    {'plan': plan, 'run': lambda: run(agent), 'report': lambda: report(agent)}[mode]()
