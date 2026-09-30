"""Hourly market and stock series from Mother-Goose's 72 raw replays, for the shed-as-cache and shop-opening studies.

Output: results/fresh/mg_watch/hourly.json
  products            list of 9 product names (index used everywhere below)
  games[]             id, era ('old' | 'new'), opp, reward [hers, opponent], shops (8, in reveal order: shop i opens
                      at hour 0 of day 3*(i+1)), and hourly arrays of length 720 (index = step = day*24 + hour,
                      values are the observation BEFORE that step's actions):
      price[p][t]     market price
      glut[p][t]      market inventory - 10000 (positive = oversupplied)
      shed[p][t]      units of p in HER shed              rshed[p][t]   the opponent's
      carried[p][t]   units of p her units carry          rcarried[p][t]
      shed_total[t]   all non-seed items in her shed (cap 100)          rshed_total[t]
      sells / rsells  filled lots [step, product index, units, price before the lot, engine average over the lot]
                      (same-step deliveries counted: unit DROP/PLACE runs before the market phase)
"""
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from mg_watch_extract import PRODUCTS, sells  # noqa: E402


def series(steps, seat):
    n = len(steps)
    shed = [[0] * n for _ in PRODUCTS]
    carried = [[0] * n for _ in PRODUCTS]
    total = [0] * n
    for t in range(n):
        private = steps[t][seat]['observation'].get('private') or {}
        sh = private.get('shed') or {}
        total[t] = sum(int(v or 0) for v in sh.values())
        for i, p in enumerate(PRODUCTS):
            shed[i][t] = int(sh.get(p, 0) or 0)
            carried[i][t] = sum(int((inv or {}).get(p, 0) or 0) for inv in (private.get('inventories') or []))
    return shed, carried, total


def main():
    games = []
    for d, era in (('data/leaders_20260917', 'old'), ('data/leaders_20260919', 'new')):
        for path in sorted(glob.glob(str(ROOT / d / '*.json'))):
            r = json.load(open(path))
            names = r['info'].get('TeamNames') or []
            if not any('Mother' in (x or '') for x in names):
                continue
            seat = next(i for i, x in enumerate(names) if 'Mother' in (x or ''))
            steps = r['steps']
            mk = [s[0]['observation']['market'] for s in steps]
            shed, carried, total = series(steps, seat)
            rshed, rcarried, rtotal = series(steps, 1 - seat)
            games.append(dict(
                id=int(r['info']['EpisodeId']), era=era, opp=names[1 - seat], reward=[r['rewards'][seat], r['rewards'][1 - seat]],
                shops=list(steps[-1][0]['observation']['town']['unlocked_shops']),
                price=[[m['prices'][p] for m in mk] for p in PRODUCTS],
                glut=[[m['inventory'][p] - 10000 for m in mk] for p in PRODUCTS],
                shed=shed, carried=carried, shed_total=total, rshed=rshed, rcarried=rcarried, rshed_total=rtotal,
                sells=sells(steps, seat), rsells=sells(steps, 1 - seat)))
            print(games[-1]['id'], era, flush=True)
    out = ROOT / 'results/fresh/mg_watch/hourly.json'
    out.write_text(json.dumps(dict(products=PRODUCTS, games=games), separators=(',', ':')), encoding='utf-8')
    print('games', len(games), 'MB', round(out.stat().st_size / 1e6, 1))


if __name__ == '__main__':
    main()
