"""Season (multi-day) runs of arms defined in a JSON spec, without editing scripts/sector_run.py.

spec (JSON): {"ARM": {"agent": "agents/<copy>.py", "base": "K5b", "cfg": {"flag": value, ...}, "label": "..."}, ...}
  agent  the agent file to load (default: the base arm's agent)
  base   an arm of scripts/sector_run.py whose config is the starting point (default K5b)
  cfg    overrides on top of the base config

usage: run_arms.py --spec spec.json --arms A,B --games panel13|team:ep,... [--days 19] [--workers 1]
Results: results/fresh/sector_20260925/multi/<ARM>/<ep>.json and results/fresh/day12_viz/<arm>_streams/<ep>.json
(the same files sector_run's multi jobs write). Each worker is one game process: keep --workers small on the shared laptop.
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import sector_run as SR  # noqa: E402

PANEL13 = ['16730612:112444381'] + ['16732748:' + e for e in (
    '112655730', '112661570', '112667461', '112673479', '112562136', '112563376', '112563785', '112564633', '112565927',
    '112567021', '112568233', '112569426')]


def register(spec):
    for arm, d in spec.items():
        base = d.get('base', 'K5b')
        bpath, bcfg = SR.ARMS[base]
        path = str(ROOT / d['agent']) if d.get('agent') else bpath
        SR.ARMS[arm] = (path, dict(bcfg, **(d.get('cfg') or {})))
        SR.LABEL[arm] = d.get('label', arm)
        SR.X.ARMS[arm] = SR.ARMS[arm]


def init(spec):
    SR.setup()
    register(spec)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--spec', required=True)
    ap.add_argument('--arms', required=True)
    ap.add_argument('--games', default='panel13')
    ap.add_argument('--days', type=int, default=19)
    ap.add_argument('--workers', type=int, default=1)
    a = ap.parse_args()
    spec = json.loads(Path(a.spec).read_text(encoding='utf-8'))
    arms = a.arms.split(',')
    games = PANEL13 if a.games == 'panel13' else a.games.split(',')
    init(spec)
    for arm in arms:
        path, cfg = SR.ARMS[arm]
        print('ARM', arm, 'agent', path, 'cfg', json.dumps(cfg, sort_keys=True, default=str), flush=True)
    t0 = time.time()
    jobs = [('multi', g, arm, a.days) for arm in arms for g in games]
    if a.workers <= 1:
        for j in jobs:
            m, g, arm, fin, err = SR.run_one(j)
            print(time.strftime('%H:%M:%S'), arm, g, ('FAILED ' + err[-1500:]) if err else f'final money {fin}', flush=True)
    else:
        from concurrent.futures import ProcessPoolExecutor, as_completed
        with ProcessPoolExecutor(max_workers=a.workers, initializer=init, initargs=(spec,)) as pool:
            for f in as_completed([pool.submit(SR.run_one, j) for j in jobs]):
                m, g, arm, fin, err = f.result()
                print(time.strftime('%H:%M:%S'), arm, g, ('FAILED ' + err[-1500:]) if err else f'final money {fin}', flush=True)
    print(f'done in {time.time() - t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
