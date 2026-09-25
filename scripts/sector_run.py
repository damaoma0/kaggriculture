"""Planner-on-day-11 and sector tests in the day-11 exact-start worlds (thread "search dispatch", 2026-09-25).

Uses scripts/xfix_run.py READ-ONLY (the day-11 agent owns it): its trace / full modes are called with this module's arms
injected into xfix_run.ARMS in memory and its output directory redirected to results/fresh/sector_20260925 (the 42-world
list is still read from results/fresh/xfix_20260925/worlds42.json).

  trace  day 11 from the leader's exact morning state (leader actions through step 263, then the arm), per-unit per-step
         records + opponent cash at the day-11 / day-12 mornings -> OUT/trace/<arm>/<ep>.json (42 worlds)
  full   full games, the arm from step 0, --worlds g1 | sem4 | all (all = the 52 G1 + sem4 worlds) -> OUT/full/<arm>/<ep>.json

Arms (agents/mgt_lead_search2.py = mgt_lead.py at git f8b48ef, the current T, + the planner block; agents/mgt_lead_sector.py
= the same + the sector term):
  N0    planner off (= the current T)
  N11   planner days 11-23, the shipping settings (v1 + survival fallback, deterministic budgets)
  N12   planner days 12-23, the shipping settings (= the deploy candidate's window)
  S0 / S11  the sector copy with the sector term off (must equal N0 / N11)
  S11w / S11h / S11wh / S11WH  day-11 planner + sectors (sd_sector_w 40) / contiguity (sd_hop_w 20) / both / both x2
Offline measurement: the wall-clock caps are raised (2 / 1 / 3 s) so the deterministic evaluation budgets decide even
under the harness's instrumentation (on Kaggle's runner the shipping caps 0.75 / 0.6 / 0.8 s essentially never fire).

usage: sector_run.py trace|full <arm,...> [--worlds all] [--games ep,...] [--workers 4]
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import xfix_run as X  # noqa: E402

OUT = ROOT / 'results/fresh/sector_20260925'
SHIP = dict(sd_surv_fb=20, sd_evals0=24000, sd_evals=8000, sd_budget0=2.0, sd_budget=1.0, sd_step_cap=3.0)
S2, SEC = 'agents/mgt_lead_search2.py', 'agents/mgt_lead_sector.py'
ARMS = {
    'N0': (S2, dict(dispatch_search='off')),
    'N11': (S2, dict(dispatch_search='active', sd_days=[11, 23], **SHIP)),
    'N12': (S2, dict(dispatch_search='active', sd_days=[12, 23], **SHIP)),
    'S0': (SEC, dict(dispatch_search='off')),                                        # must equal N0
    'S11': (SEC, dict(dispatch_search='active', sd_days=[11, 23], **SHIP)),          # must equal N11 (sector off)
    'S11w': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_sector_w=40.0, **SHIP)),       # sectors only
    'S11h': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_hop_w=20.0, **SHIP)),          # contiguity only
    'S11wh': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_sector_w=40.0, sd_hop_w=20.0, **SHIP)),
    'S11WH': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_sector_w=80.0, sd_hop_w=40.0, **SHIP)),
}


def setup():
    X.OUT = OUT
    wl = json.loads((ROOT / 'results/fresh/xfix_20260925/worlds42.json').read_text(encoding='utf-8'))
    X.load_worlds = lambda: wl
    X.ARMS.update(ARMS)


def main():
    argv = sys.argv[1:]
    mode, arms = argv[0], argv[1].split(',')
    sel, spec, workers = None, 'all', int(os.environ.get('LP_WORKERS', 4))
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
    setup()
    import lead_g1
    if mode == 'full':
        games = list(lead_g1.GAMES) if spec in ('g1', 'all') else []
        if spec in ('sem4', 'all'):
            w = json.loads((ROOT / 'results/fresh/lead_sem4_20260925/worlds.json').read_text(encoding='utf-8'))['worlds']
            games += [x['game'] for x in w if x['game'] not in games]
    else:
        games = [w['game'] for w in X.load_worlds()['worlds']]
    if sel:
        games = [g for g in games if g.split(':')[1] in sel]
    jobs = [(mode, g, a) for a in arms for g in games]
    print(len(jobs), 'jobs', flush=True)
    t0 = time.time()
    errs = 0
    from concurrent.futures import ProcessPoolExecutor, as_completed
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for f in as_completed([pool.submit(X.job, j) for j in jobs]):
            m, g, a, fin, err = f.result()
            errs += bool(err)
            print(time.strftime('%H:%M:%S'), m, a, g, ('FAILED ' + err) if err else f'{fin}', flush=True)
    print(f'completed {len(jobs)} games in {time.time() - t0:.0f}s, errors (FAILED) {errs}', flush=True)


if __name__ == '__main__':
    main()
