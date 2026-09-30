"""Her animal servicing as a function of the demand that is OPEN that day (offline, 584 tapes).

For every tape and day: species on each tile from the recorded board of that day, FEED / CARE commands on the tile
from the tape calendar, and the shops open that day. Rates are per animal-day. Shows how fast she reacts when a
consuming shop opens late. Output: results/fresh/mg_tape/service_dynamics.json
"""
import glob
import gzip
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ns = {}
exec(compile((ROOT / 'scripts/fragments/tape_calendar.py').read_text(encoding='utf-8'), 'tape_calendar', 'exec'), ns)
simulate = ns['_tc_simulate']
SPECIES = {'sh': 'SHEEP', 'co': 'COW', 'go': 'GOOSE'}
BUYERS = {'SHEEP': {'YARN_STORE': 12}, 'COW': {'PIZZA_SHOP': 6, 'ICE_CREAM_SHOP': 6, 'SMOOTHIE_SHOP': 6},
          'GOOSE': {'BAKERY': 6, 'BRUNCH_SPOT': 6}}


def main():
    paths = sorted(glob.glob(str(ROOT / 'data/mg_tapes/*/*.json.gz')))
    by_cap = defaultdict(lambda: [0, 0, 0])              # (species, phase, capacity bucket) -> animal-days, fed, cared
    by_since = defaultdict(lambda: [0, 0, 0])            # (species, days since first buyer opened) -> ...
    herd = defaultdict(list)
    for p in paths:
        t = json.load(gzip.open(p, 'rt', encoding='utf-8'))
        acts = [a if isinstance(a, dict) else {} for a in t['actions']]
        sim = simulate(lambda s: acts[s] if s < len(acts) else {}, 0, 718, [(4, 4)])
        for day in range(6, 29):
            board = t['boards'][day]
            animals = {}
            for y, row in enumerate(board):
                for x in range(10):
                    sp = SPECIES.get(row[2 * x:2 * x + 2])
                    if sp:
                        animals[(x, y)] = sp
            fed, cared = set(), set()
            for s in range(day * 24, day * 24 + 24):
                for x, y, c in sim.get(s, []):
                    if c and c[0] == 'FEED':
                        fed.add((x, y))
                    elif c and c[0] == 'CARE':
                        cared.add((x, y))
            shops = t['shops'][day]
            for sp in BUYERS:
                capd = sum(BUYERS[sp].get(s, 0) for s in shops)
                tiles = [k for k, v in animals.items() if v == sp]
                if not tiles:
                    continue
                ph = '12-17' if day < 18 else '18-23' if day < 24 else '24-28'
                if day >= 12:
                    b = by_cap[(sp, ph, min(capd, 24) // 6 * 6)]
                    b[0] += len(tiles)
                    b[1] += sum(1 for k in tiles if k in fed)
                    b[2] += sum(1 for k in tiles if k in cared)
                first = next((d for d in range(31) if any(s in BUYERS[sp] for s in t['shops'][d])), None)
                if first is not None and first >= 15 and day >= 12:
                    b = by_since[(sp, max(-3, min(6, day - first)))]
                    b[0] += len(tiles)
                    b[1] += sum(1 for k in tiles if k in fed)
                    b[2] += sum(1 for k in tiles if k in cared)
                if day == 24:
                    herd[(sp, min(sum(BUYERS[sp].get(s, 0) for s in t['shops'][30]), 24) // 6 * 6)].append(len(tiles))
    out = {}
    for sp in BUYERS:
        print(f'\n{sp}: fed / cared share of animal-days, by daily shop capacity for its product OPEN that day')
        print('   capacity/day    days 12-17          days 18-23          days 24-28')
        for capd in (0, 6, 12, 18, 24):
            cells = []
            for ph in ('12-17', '18-23', '24-28'):
                n, f, c = by_cap.get((sp, ph, capd), [0, 0, 0])
                cells.append(f'{f / n:4.0%} / {c / n:4.0%} (n={n:>5})' if n else f'{"-":>20}')
                out[f'{sp}|{ph}|{capd}'] = [n, f, c]
            print(f'   {capd:>3}{"+" if capd == 24 else " "}          ' + '   '.join(cells))
        print('   first buyer opens on day >= 15: days relative to that opening -> fed / cared')
        print('   ' + '  '.join(f'{d:+d}: {by_since[(sp, d)][1] / max(1, by_since[(sp, d)][0]):.0%}/{by_since[(sp, d)][2] / max(1, by_since[(sp, d)][0]):.0%}'
                                for d in range(-3, 7) if by_since[(sp, d)][0]))
        print('   herd on day 24 by FINAL capacity: ' + '  '.join(f'{capd}: {sum(v) / len(v):.1f} (n={len(v)})' for (s2, capd), v in sorted(herd.items()) if s2 == sp))
    (ROOT / 'results/fresh/mg_tape/service_dynamics.json').write_text(json.dumps(out), encoding='utf-8')


if __name__ == '__main__':
    main()
