"""Season panel report: each arm vs the leader (the recorded episode) and vs a base arm, per world and on average.

usage: season_report.py <arm,...> [--base K5b] [--games panel13|team:ep,...]
Reads results/fresh/sector_20260925/multi/<ARM>/<ep>.json (sector_run / run_arms multi jobs) and .../LEADER/<ep>.json.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from run_arms import PANEL13  # noqa: E402

M = ROOT / 'results/fresh/sector_20260925/multi'


def load(arm, ep):
    f = M / arm / f'{ep}.json'
    return json.loads(f.read_text()) if f.exists() else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('arms')
    ap.add_argument('--base', default='K5b')
    ap.add_argument('--games', default='panel13')
    a = ap.parse_args()
    games = PANEL13 if a.games == 'panel13' else a.games.split(',')
    eps = [g.split(':')[1] for g in games]
    for arm in a.arms.split(','):
        rows = []
        print(f'\n=== {arm}  (own / margin gap vs leader; delta vs {a.base})')
        for ep in eps:
            L, R, B = load('LEADER', ep), load(arm, ep), load(a.base, ep)
            if not (L and R):
                print(f'  {ep}: missing')
                continue
            lo, lr = L['money']['30']
            ro, rr = R['money']['30']
            og, mg = ro - lo, (ro - rr) - (lo - lr)
            bo = bm = None
            if B:
                bo_, br_ = B['money']['30']
                bo, bm = og - (bo_ - lo), mg - ((bo_ - br_) - (lo - lr))
            err = (R.get('tier_err') or {}).get('errors')
            td = R.get('tier_days') or {}
            rows.append((og, mg, bo, bm, ro > rr))
            print('  %s own %+8.0f  margin %+8.0f | vs %s own %s margin %s | %s | tier days %s err %s' % (
                ep, og, mg, a.base, '%+7.0f' % bo if bo is not None else '     -', '%+7.0f' % bm if bm is not None else '     -',
                'win ' if ro > rr else 'loss', '%s-%s' % (min(map(int, td)), max(map(int, td))) if td else '-', err))
        if rows:
            n = len(rows)
            nb = [r for r in rows if r[2] is not None]
            print('  MEAN own %+.0f margin %+.0f | vs %s own %s margin %s | wins %d/%d' % (
                sum(r[0] for r in rows) / n, sum(r[1] for r in rows) / n, a.base,
                '%+.0f' % (sum(r[2] for r in nb) / len(nb)) if nb else '-', '%+.0f' % (sum(r[3] for r in nb) / len(nb)) if nb else '-',
                sum(r[4] for r in rows), n))


if __name__ == '__main__':
    main()
