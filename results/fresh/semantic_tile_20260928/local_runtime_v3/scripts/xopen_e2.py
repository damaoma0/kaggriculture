"""xopen E2 / E3: new worlds, the deploy with the exact opening (agents/mgt_lpv_xopen*.py) vs the deploy (paired).

Every game is scripts/ladder_panel.py's own run() (seed, forced shops, the recorded opponent's actions, our build
through Kaggle's loader), unchanged; this runner only captures the loaded entry point (get_last_callable is wrapped
before the call) to store the agent's xopen report (_XO_REPORT: breakages / repairs / failsafe cuts / handoff / cash,
animals placed and plantings by day) next to the ladder-panel record. XO_EXCLUDE_EP = the world's own episode, so a
corpus game can never re-retrieve its own recording (review T6).

usage: xopen_e2.py run <agent>[,<agent>...] [smoke|p2750|ep,ep,...] [--sub p2750] [--workers 4]
Results: results/fresh/xopen_20260925/e2/<agent>/<episode>.json (the ladder-panel record + xo, router, wall)
"""
import json
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
OUT = ROOT / 'results/fresh/xopen_20260925/e2'
SMOKE = [110937191, 111374151, 111376633, 111416249, 111554912, 111577649, 111681195, 111688786, 111871547, 111902048,
         111916514, 111941962]


def run(job):
    name, ep, sub = job
    try:
        import ladder_panel as LP
        import kaggle_environments.agent as KA
        box = {}
        orig = KA.get_last_callable

        def cap(raw, fallback=None, path=None):
            f = orig(raw, fallback, path)
            box['entry'] = f
            return f
        KA.get_last_callable = cap
        os.environ['XO_EXCLUDE_EP'] = str(ep)
        t0 = time.time()
        out = LP.run((name, str(ROOT / f'data/ladder_panel/{sub}/{ep}.json.gz')))
        G = box['entry'].__globals__ if 'entry' in box else {}
        xo = json.loads(json.dumps(G.get('_XO_REPORT') or {}, default=str))
        res = dict(out, xo=xo, wall=time.time() - t0, dep_tmax=(G.get('_MGT_REPORT') or {}).get('tmax'))
        (OUT / name).mkdir(parents=True, exist_ok=True)
        (OUT / name / f'{ep}.json').write_text(json.dumps(res, default=str), encoding='utf-8')
        return name, ep, res['final'], res['rival'], None
    except Exception as exc:
        return name, ep, None, None, f'{type(exc).__name__}: {exc}\n{traceback.format_exc()[-2500:]}'


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] != 'run':
        print(__doc__)
        return
    agents = argv[1].split(',')
    sel = argv[2] if len(argv) > 2 and not argv[2].startswith('--') else 'smoke'
    sub, workers = 'p2750', int(os.environ.get('LP_WORKERS', 4))
    i = 2
    while i < len(argv):
        if argv[i] == '--sub':
            sub = argv[i + 1]; i += 2
        elif argv[i] == '--workers':
            workers = int(argv[i + 1]); i += 2
        else:
            i += 1
    if sel == 'smoke':
        eps = SMOKE
    elif sel == 'p2750':
        eps = sorted(int(p.name.split('.')[0]) for p in (ROOT / f'data/ladder_panel/{sub}').glob('*.json.gz'))
    else:
        eps = [int(x) for x in sel.split(',')]
    jobs = [(a, e, sub) for e in eps for a in agents]
    print(len(jobs), 'games', flush=True)
    t0 = time.time()
    from concurrent.futures import ProcessPoolExecutor, as_completed
    with ProcessPoolExecutor(max_workers=workers, max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run, j) for j in jobs]):
            name, ep, fin, riv, err = f.result()
            print(time.strftime('%H:%M:%S'), name, ep, ('ERROR ' + err) if err else f'own {fin:.0f} rival {riv:.0f} margin {fin - riv:.0f}',
                  flush=True)
    print(f'completed {len(jobs)} games in {time.time() - t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
