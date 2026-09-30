"""Can a hand be dropped? Generous feasibility bound from the tape calendar (offline).

For every day 6-28 take the hand with the least work + travel. Every other unit (farmer included) has a trailing idle
block: the steps after its last non-PASS command, starting from where it stands. Hands vanish at midnight and their
cargo is auto-dropped into the shed, so a trailing route is ONE-WAY (no return trip). Greedy nearest-neighbour: each
helper walks to the nearest unassigned work tile of the dropped hand (cost = Manhattan distance + 1 step for the
command) while its block lasts. GENEROUS: ignores inventory (seeds, wheat, fertilizer, watering order), ignores that
a dropped hire shifts later spawn tiles, and lets late work stand in for early work.

Output: results/fresh/mg_tape/slack_absorb.json
"""
import glob
import gzip
import json
import statistics as st
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ns = {}
exec(compile((ROOT / 'scripts/fragments/tape_calendar.py').read_text(encoding='utf-8'), 'tape_calendar', 'exec'), ns)
simulate = ns['_tc_simulate']
MV = ns['_TC_MOVES']
FIB = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987]
NEEDS_CARGO = {'PLANT', 'FEED', 'FERTILIZE', 'PLACE', 'DROP', 'BUILD_PASTURE', 'BUILD_COOP'}


def main():
    paths = sorted(glob.glob(str(ROOT / 'data/mg_tapes/*/*.json.gz')))[::4]
    days = Counter()
    saved = []
    saved_strict = []
    share = []
    blocks = Counter()
    for p in paths:
        t = json.load(gzip.open(p, 'rt', encoding='utf-8'))
        acts = [a if isinstance(a, dict) else {} for a in t['actions']]
        sim = simulate(lambda s: acts[s] if s < len(acts) else {}, 0, 718, [(4, 4)])
        game = game_strict = 0
        for day in range(6, 29):
            seq = {}
            for s in range(day * 24, day * 24 + 24):
                for u, (x, y, c) in enumerate(sim.get(s, [])):
                    seq.setdefault(u, []).append((s % 24, x, y, c[0] if c else 'PASS'))
            hands = {u: v for u, v in seq.items() if u > 0}
            if len(hands) < 3:
                continue
            load = {u: sum(1 for _, _, _, o in v if o != 'PASS') for u, v in hands.items()}
            drop = min(load, key=load.get)
            jobs = [(x, y, o) for _, x, y, o in hands[drop] if o != 'PASS' and o not in MV]
            helpers = []
            for u, v in seq.items():
                if u == drop:
                    continue
                busy = [k for k, (_, _, _, o) in enumerate(v) if o != 'PASS']
                last = busy[-1] if busy else -1
                free = len(v) - 1 - last
                if last >= 0:
                    _, x, y, o = v[last]
                    if o in MV:
                        x, y = max(0, min(9, x + MV[o][0])), max(0, min(9, y + MV[o][1]))
                else:
                    _, x, y, _ = v[0]
                blocks[min(free, 12)] += 1
                if free >= 2:
                    helpers.append([free, x, y])
            todo = list(jobs)
            done = done_cargo = 0
            for h in sorted(helpers, key=lambda h: -h[0]):
                while todo:
                    k = min(range(len(todo)), key=lambda i: abs(todo[i][0] - h[1]) + abs(todo[i][1] - h[2]))
                    cost = abs(todo[k][0] - h[1]) + abs(todo[k][1] - h[2]) + 1
                    if cost > h[0]:
                        break
                    h[0] -= cost
                    h[1], h[2] = todo[k][0], todo[k][1]
                    done += 1
                    done_cargo += todo[k][2] in NEEDS_CARGO
                    todo.pop(k)
            n = len(hands)
            days['all'] += 1
            share.append(done / max(1, len(jobs)))
            if not todo:
                days['absorbed'] += 1
                game += FIB[min(15, n - 1)]
                if not any(o in NEEDS_CARGO for _, _, o in jobs):
                    days['absorbed, no cargo-dependent job'] += 1
                    game_strict += FIB[min(15, n - 1)]
        saved.append(game)
        saved_strict.append(game_strict)
    tot = sum(blocks.values())
    print(f'{len(paths)} tapes, {days["all"]} days (6-28).')
    print('trailing idle block per unit-day:', '  '.join(f'{k}{"+" if k == 12 else ""}: {v / tot:.0%}' for k, v in sorted(blocks.items())))
    print(f'share of the lightest hand\'s work commands the others\' trailing blocks can reach (generous): mean {st.mean(share):.0%}')
    print(f'days where ALL of it is absorbed: {days["absorbed"] / days["all"]:.0%}  -> wage saved {st.mean(saved):,.0f} per game (generous upper bound)')
    print(f'  of which the dropped hand had no seed/feed/fertilizer/shed job: {days["absorbed, no cargo-dependent job"] / days["all"]:.0%}  -> {st.mean(saved_strict):,.0f} per game')
    (ROOT / 'results/fresh/mg_tape/slack_absorb.json').write_text(json.dumps(dict(days=dict(days), saved=st.mean(saved), saved_strict=st.mean(saved_strict))), encoding='utf-8')


if __name__ == '__main__':
    main()
