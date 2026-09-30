"""Her LATE crop decisions as a function of the demand open at the time (offline, 584 tapes): plantings and
fertilizer applications on days >= 12 by crop, against the daily shop capacity for that crop's product.
Output: printed table only."""
import glob
import gzip
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ns = {}
exec(compile((ROOT / 'scripts/fragments/tape_calendar.py').read_text(encoding='utf-8'), 'tape_calendar', 'exec'), ns)
simulate = ns['_tc_simulate']
CROP = {'ST': 'STRAWBERRY', 'TO': 'TOMATO', 'CA': 'CARROT', 'WH': 'WHEAT', 'ME': 'MELON'}
BUY = {'STRAWBERRY': {'BRUNCH_SPOT': 6, 'ICE_CREAM_SHOP': 6, 'SMOOTHIE_SHOP': 6, 'FARMERS_MARKET': 6},
       'TOMATO': {'PIZZA_SHOP': 6, 'FARMERS_MARKET': 6}, 'CARROT': {'PET_CAFE': 12, 'FARMERS_MARKET': 6},
       'WHEAT': {'BAKERY': 6, 'PIZZA_SHOP': 6, 'BRUNCH_SPOT': 6, 'ICE_CREAM_SHOP': 6, 'FARMERS_MARKET': 6}}


def main():
    paths = sorted(glob.glob(str(ROOT / 'data/mg_tapes/*/*.json.gz')))
    plant = defaultdict(lambda: defaultdict(list))      # crop -> (phase, cap bucket) -> plantings per game in that phase
    fert = defaultdict(lambda: defaultdict(list))
    tiles = defaultdict(lambda: defaultdict(list))
    for p in paths:
        t = json.load(gzip.open(p, 'rt', encoding='utf-8'))
        acts = [a if isinstance(a, dict) else {} for a in t['actions']]
        sim = simulate(lambda s: acts[s] if s < len(acts) else {}, 0, 718, [(4, 4)])
        for lo, hi in ((12, 17), (18, 23), (24, 28)):
            pl, fe = defaultdict(int), defaultdict(int)
            for s in range(lo * 24, (hi + 1) * 24):
                day = s // 24
                for x, y, c in sim.get(s, []):
                    if c and c[0] == 'PLANT' and len(c) > 1:
                        pl[str(c[1])] += 1
                    elif c and c[0] == 'FERTILIZE':
                        lab = t['boards'][min(29, day)][y][2 * x:2 * x + 2]
                        fe[CROP.get(lab, lab)] += 1
            shops = t['shops'][lo]
            board = t['boards'][hi]
            for crop in BUY:
                capd = min(24, sum(BUY[crop].get(s, 0) for s in shops)) // 6 * 6
                plant[crop][(lo, capd)].append(pl.get(crop, 0))
                fert[crop][(lo, capd)].append(fe.get(crop, 0))
                tiles[crop][(lo, capd)].append(sum(1 for row in board for x in range(10) if CROP.get(row[2 * x:2 * x + 2]) == crop))
    for crop in BUY:
        print(f'\n{crop}: per game, by daily capacity for it OPEN at the start of the phase  (plantings | fertilizer applications | tiles at phase end)')
        print('   capacity      days 12-17                 days 18-23                 days 24-28')
        for capd in (0, 6, 12, 18, 24):
            cells = []
            for lo in (12, 18, 24):
                v = plant[crop].get((lo, capd))
                if v:
                    cells.append(f'{sum(v) / len(v):5.1f} | {sum(fert[crop][(lo, capd)]) / len(v):5.1f} | {sum(tiles[crop][(lo, capd)]) / len(v):5.1f} (n={len(v):>3})')
                else:
                    cells.append(f'{"-":>27}')
            print(f'   {capd:>3}{"+" if capd == 24 else " "}     ' + '   '.join(cells))


if __name__ == '__main__':
    main()
