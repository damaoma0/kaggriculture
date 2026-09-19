"""Routing loss of a Mother-Goose tape-router agent, measured in her own recorded worlds against a live rival.

For a sample of her recorded games (compact tapes in data/mg_tapes), the world is recreated (same seed, her
shops forced, natural weeds) and played in her seat in three arms:
  native_raw      her own tape, equilibrium opening, no layers (the policy's true value in that world)
  native_chassis  the agent restricted to that one tape (MGT_ONLY): what the chassis layers cost or add
  loo             the agent with that tape removed from its library (MGT_EXCLUDE): the pure routing loss
Output: results/fresh/mg_tape/loo/<agent>-<arm>-<episode>.json
Usage:  python mgt_loo.py <agent> [rival=v50_public] [n_worlds=40] [arms=native_raw,native_chassis,loo]
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
    if arm == 'native_raw':
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
    players = [None, None]
    players[seat] = ours
    players[1 - seat] = lambda obs, t: opp(obs)
    env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': tape['seed']})
    res = TV._play(E, env, players, seat, tape['shops'], None, None, seat)
    d = res['daily'][seat][-1]
    out = dict(agent=name, rival=rival, arm=arm, episode=ep, seat=seat, shops=tape['shops'][30],
               final=res['final'][seat], rival_final=res['final'][1 - seat], margin=res['final'][seat] - res['final'][1 - seat],
               revenue=d['revenue'], spend=d['spend'], sold=d['sold_units'], rival_revenue=res['daily'][1 - seat][-1]['revenue'],
               no_effect=d['physical'].get('no_effect', 0), missing=d['physical'].get('missing_worker_commands', 0),
               cash_daily=[x['money'] for x in res['daily'][seat]], history=list(history) if history is not None else None,
               sheep=json.loads(json.dumps(sheep, default=list)) if sheep else None)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f'{name}-{arm}-{ep}.json').write_text(json.dumps(out), encoding='utf-8')
    return out


def main():
    name = sys.argv[1]
    rival = sys.argv[2] if len(sys.argv) > 2 else 'v50_public'
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 40
    arms = (sys.argv[4] if len(sys.argv) > 4 else 'native_raw,native_chassis,loo').split(',')
    files = sorted(p for s in ('56266758', '56266899') for p in (ROOT / 'data/mg_tapes' / s).glob('*.json.gz'))
    random.Random(20260920).shuffle(files)
    jobs = []
    for p in files[:n]:
        ep = p.name.split('.')[0]
        for arm in arms:
            key = 'any' if arm == 'native_raw' else name
            if not (OUT / f'{key if arm == "native_raw" else name}-{arm}-{ep}.json').exists():
                jobs.append((name if arm != 'native_raw' else 'any', rival, arm, str(p)))
    print(f'{len(jobs)} games', flush=True)
    with ProcessPoolExecutor(max_workers=4, max_tasks_per_child=1) as pool:
        futures = {pool.submit(run, j): j for j in jobs}
        for f in as_completed(futures):
            try:
                r = f.result()
                print(f"{r['arm']:15s} {r['episode']}: margin {r['margin']:+9,.0f} final {r['final']:9,.0f}", flush=True)
            except Exception as exc:
                print(f'FAILED {futures[f][2]} {futures[f][3][-20:]}: {type(exc).__name__}: {exc}', flush=True)


if __name__ == '__main__':
    main()
