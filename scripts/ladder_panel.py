"""LADDER PANEL: our builds in the worlds we actually met on the ladder.

For every compact ladder game (scripts/ladder_panel_fetch.py): same seed, the recorded shops forced, the OPPONENT's
recorded actions replayed, our build live through Kaggle's loader. With the submitted build the recorded result must
come back to the dollar (that is the validity check of the harness). The opponent cannot react, which is the same
for every build compared; a game is flagged when the opponent's tape stops working against a build (its commands
without effect rise by more than 40 over its recorded game).

usage: ladder_panel.py run <agent>[,<agent>...] [submission=56368334] [episodes=all|e1,e2,...]
       ladder_panel.py report <agent>[,<agent>...] [reference=mgt_t10] [submission=56368334]
Results: results/fresh/ladder_panel/<agent>/<episode>.json   (MGT_FORCE=1 re-runs)
"""
import gzip
import json
import os
import random
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
OUT = ROOT / 'results/fresh/ladder_panel'
PASS = {'farmer': ['PASS'], 'hands': [], 'market': []}


def run(job):
    name, path = job
    import tape_vs_bench as TV
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    g = json.load(gzip.open(path, 'rt', encoding='utf-8'))
    seat, rec = g['seat'], g['opp_actions']
    ap = ROOT / 'agents' / f'{name}.py'
    entry = get_last_callable(ap.read_text(encoding='utf-8'), path=str(ap))
    hires = {'asked': 0, 'got': 0, 'short_days': []}
    last = {}

    def ours(obs, t):
        farm = obs['farms'][seat]
        if last.get('asked') and t % 24:                                # did last step's HIREs arrive?
            got = len(farm['hands']) - last['hands']
            hires['asked'] += last['asked']
            hires['got'] += max(0, got)
            if got < last['asked']:
                hires['short_days'].append([(t - 1) // 24, last['asked'], max(0, got)])
        a = entry(obs)
        n = sum(1 for o in ((a or {}).get('market') or [])[:10] if o and o[0] == 'HIRE')
        last.update(asked=n, hands=len(farm['hands']))
        return a

    players = [None, None]
    players[seat] = ours
    players[1 - seat] = lambda obs, t: (rec[t] if t < len(rec) and isinstance(rec[t], dict) and rec[t] else dict(PASS))
    env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': g['seed']})
    res = TV._play(E, env, players, seat, g['shops'], None, None, seat)
    d, o = res['daily'][seat][-1], res['daily'][1 - seat][-1]
    G = entry.__globals__
    hist = [list(h) for h in (G.get('_MGT_HISTORY') or [])]
    out = dict(agent=name, episode=g['episode'], seat=seat, final=res['final'][seat], rival=res['final'][1 - seat],
               margin=res['final'][seat] - res['final'][1 - seat], recorded=[g['rewards'][seat], g['rewards'][1 - seat]],
               dead=d['physical'].get('no_effect', 0), missing=d['physical'].get('missing_worker_commands', 0),
               opp_dead=o['physical'].get('no_effect', 0) + o['physical'].get('missing_worker_commands', 0),
               revenue=d['revenue'], spend=d['spend'], sold=d['sold_units'], hires=hires,
               overlay={k: v for k, v in (G.get('_SHP_REPORT') or {}).items() if isinstance(v, (int, float))},
               router={k: v for k, v in (G.get('_MGT_REPORT') or {}).items() if isinstance(v, (int, float))},
               switches=[h for i, h in enumerate(hist) if i == 0 or h[1] != hist[i - 1][1]],
               opponent=(g.get('opponent') or {}).get('team'))
    (OUT / name).mkdir(parents=True, exist_ok=True)
    (OUT / name / f'{g["episode"]}.json').write_text(json.dumps(out), encoding='utf-8')
    return out


def ci(xs, n=10000, seed=7):
    rng = random.Random(seed)
    k = len(xs)
    m = sorted(sum(rng.choices(xs, k=k)) / k for _ in range(n))
    return m[int(0.025 * n)], m[int(0.975 * n)]


def load(agent, sub):
    rows = {}
    for p in [q for x in str(sub).split(',') for q in (ROOT / f'data/ladder_panel/{x}').glob('*.json.gz')]:
        f = OUT / agent / f'{p.name.split(".")[0]}.json'
        if f.exists():
            r = json.loads(f.read_text(encoding='utf-8'))
            rows[r['episode']] = r
    return rows


def report(agents, ref, sub):
    R = {a: load(a, sub) for a in set(agents) | {ref}}
    base = R[ref]
    own = {int(p.name.split('.')[0]) for p in (ROOT / 'data/ladder_panel/56368334').glob('*.json.gz')}
    chk = R.get('mgt_t10') or {}
    if chk:
        mine = [r for e, r in chk.items() if e in own]
        off = [r['episode'] for r in mine if round(r['final']) != round(r['recorded'][0]) or round(r['rival']) != round(r['recorded'][1])]
        print(f'harness check: {len(mine) - len(off)} of {len(mine)} of the ladder results of mgt_t10 reproduced to the dollar' + (f'; NOT: {off[:8]}' if off else ''))
    expansion = {e for a in R for e, r in R[a].items() if r['overlay'].get('commitments')}
    print(f'games where a compared build commits to the sheep expansion: {len(expansion)}')
    print(f'\n{"build":<12} {"n":>4} {"W-L":>9} {"mean margin (95% CI)":>32} | {"paired vs " + ref + " (95% CI)":>34} {"better/worse/same":>18} | {"expansion games":>22} | {"hire-short games":>16} {"opp tape broken":>15}')
    for a in agents:
        rows = R[a]
        eps = sorted(set(rows) & set(base))
        if not eps:
            continue
        broken = {e for e in eps if rows[e]['opp_dead'] - base[e]['opp_dead'] > 40}
        ok = [e for e in eps if e not in broken]
        m = [rows[e]['margin'] for e in ok]
        lo, hi = ci(m)
        d = [rows[e]['margin'] - base[e]['margin'] for e in ok]
        dlo, dhi = ci(d) if any(d) else (0, 0)
        ex = [e for e in ok if e in expansion]
        dex = [rows[e]['margin'] - base[e]['margin'] for e in ex]
        short = sum(1 for e in ok if rows[e]['hires']['short_days'])
        print(f'{a:<12} {len(ok):>4} {sum(x > 0 for x in m):>4}-{sum(x < 0 for x in m):<4} {sum(m) / len(m):>+10,.0f} ({lo:>+7,.0f} to {hi:>+7,.0f}) | '
              f'{sum(d) / len(d):>+10,.0f} ({dlo:>+7,.0f} to {dhi:>+7,.0f}) {sum(x > 0 for x in d):>6}/{sum(x < 0 for x in d)}/{sum(x == 0 for x in d):<5} | '
              f'n={len(ex):>2} {sum(dex) / max(1, len(dex)):>+8,.0f} W-L {sum(rows[e]["margin"] > 0 for e in ex)}-{sum(rows[e]["margin"] < 0 for e in ex)} | {short:>16} {len(broken):>15}')


def main():
    mode = sys.argv[1]
    agents = sys.argv[2].split(',')
    if mode == 'report':
        ref = sys.argv[3] if len(sys.argv) > 3 else 'mgt_t10'
        sub = sys.argv[4] if len(sys.argv) > 4 else '56368334'
        return report(agents, ref, sub)
    sub = sys.argv[3] if len(sys.argv) > 3 else '56368334'
    only = None if len(sys.argv) <= 4 or sys.argv[4] == 'all' else set(sys.argv[4].split(','))
    paths = sorted(q for x in str(sub).split(',') for q in (ROOT / f'data/ladder_panel/{x}').glob('*.json.gz'))
    if only:
        paths = [p for p in paths if p.name.split('.')[0] in only]
    jobs = [(a, str(p)) for p in paths for a in agents
            if os.environ.get('MGT_FORCE') or not (OUT / a / f'{p.name.split(".")[0]}.json').exists()]
    print(f'{len(jobs)} games', flush=True)
    with ProcessPoolExecutor(max_workers=4, max_tasks_per_child=1) as pool:
        futures = {pool.submit(run, j): j for j in jobs}
        for f in as_completed(futures):
            try:
                r = f.result()
                print(f'{r["agent"]:<10} {r["episode"]} margin {r["margin"]:>+9,.0f} (recorded {r["recorded"][0] - r["recorded"][1]:>+9,.0f})', flush=True)
            except Exception as exc:
                print('FAILED', futures[f], type(exc).__name__, exc, flush=True)


if __name__ == '__main__':
    main()
