"""Classify the tape commands that do nothing when a tape-router build plays a leave-one-out world.

usage: mgt_dead.py <agent> <episode|seed:<seed>:<seat>>[,...] [rival=v50_public]
For every step and unit the command is checked against the observation (before the step): FEED without wheat,
PICKUP of more than the shed holds, PLANT without a seed, FERTILIZE without fertilizer, PLACE without the animal,
HARVEST of nothing, ... The counts say which "tape repairs" are worth building. One game per episode, run
sequentially (keeps to the one-evaluation rule).
"""
import gzip
import json
import os
import sys
from collections import Counter

from market_corpus import ROOT
import tape_vs_bench as TV


def classify(cmd, pos, tile, inv, shed, seeds):
    op = cmd[0]
    animal = isinstance(tile, dict) and tile.get('animal')
    plant = isinstance(tile, dict) and tile.get('kind') == 'PLANT'
    if op == 'FEED':
        if not animal:
            return 'FEED:no_animal'
        if tile.get('fed_today'):
            return 'FEED:already'
        if int(inv.get('WHEAT', 0) or 0) < 1:
            return 'FEED:no_wheat'
    elif op == 'CARE':
        if not animal:
            return 'CARE:no_animal'
        if tile.get('cared_today'):
            return 'CARE:already'
    elif op == 'PICKUP' and len(cmd) > 2:
        have = int(shed.get(cmd[1], 0) or 0)
        if have < int(cmd[2]):
            return f'PICKUP:short:{cmd[1]}'
    elif op == 'PLANT':
        if tile is not None:
            return 'PLANT:occupied:' + (str(tile.get('kind')) if isinstance(tile, dict) else str(tile))
        if int(seeds.get(cmd[1], 0) or 0) < 1:
            return f'PLANT:no_seed:{cmd[1]}'
    elif op == 'WATER':
        if not plant:
            return 'WATER:no_plant'
    elif op == 'FERTILIZE':
        if not plant:
            return 'FERTILIZE:no_plant'
        if int(inv.get('FERTILIZER', 0) or 0) < 1:
            return 'FERTILIZE:no_fertilizer'
    elif op == 'HARVEST':
        if not (isinstance(tile, dict) and int(tile.get('yield_units', 0) or 0) > 0):
            return 'HARVEST:nothing' + (':animal' if animal else ':plant' if plant else ':empty')
    elif op == 'PLACE' and len(cmd) > 1:
        if int(inv.get(cmd[1], 0) or 0) < 1:
            return f'PLACE:no_item:{cmd[1]}'
        if not (isinstance(tile, dict) and tile.get('kind') in ('PASTURE', 'COOP') and not tile.get('animal')):
            return 'PLACE:no_structure'
    elif op in ('BUILD_PASTURE', 'BUILD_COOP'):
        if tile is not None:
            return op + ':occupied'
    elif op == 'COLLECT_FERTILIZER':
        if not (animal and tile.get('fertilizer_available')):
            return 'COLLECT:nothing'
    return None


def run(name, ep, rival):
    if str(ep).startswith('seed:'):                       # natural world: seed:<seed>:<seat>
        _, seed, seat0 = str(ep).split(':')
        tape = dict(seat=int(seat0), seed=int(seed), shops=None)
    else:
        path = next(p for s in ('56266758', '56266899') for p in (ROOT / 'data/mg_tapes' / s).glob(f'{ep}.json.gz'))
        tape = json.load(gzip.open(path, 'rt', encoding='utf-8'))
        os.environ['MGT_EXCLUDE'] = str(ep)
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    rp = ROOT / 'agents' / f'{rival}.py'
    opp = get_last_callable(rp.read_text(encoding='utf-8'), path=str(rp))
    ns = {'__name__': 'mgt'}
    exec(compile((ROOT / 'agents' / f'{name}.py').read_text(encoding='utf-8'), name, 'exec'), ns)
    agent, seat = ns['agent'], tape['seat']
    counts, lost = Counter(), []
    prev = {}

    def ours(obs, t):
        a = agent(obs)
        farm = obs['farms'][seat]
        shed = dict(obs['private'].get('shed') or {})
        seeds = obs['private'].get('seeds') or {}
        invs = obs['private'].get('inventories') or []
        own = (ns.get('_SHP_STATES') or {}).get(seat, {}).get('own', set())
        units = [farm['farmer']] + list(farm['hands'])
        cmds = [a.get('farmer')] + list(a.get('hands') or [])
        for i, (u, c) in enumerate(zip(units, cmds)):
            if not c or i in own:
                continue
            tile = farm['tiles'][u[1]][u[0]]
            k = classify(c, tuple(u), tile, invs[i] if i < len(invs) else {}, shed, seeds)
            if k:
                counts[k] += 1
            if c[0] == 'PICKUP' and len(c) > 2:
                shed[c[1]] = max(0, int(shed.get(c[1], 0) or 0) - int(c[2]))
        animals = {(x, y): c['animal'] for y, row in enumerate(farm['tiles']) for x, c in enumerate(row)
                   if isinstance(c, dict) and c.get('animal')}
        for p, s in prev.items():
            if p not in animals:
                lost.append((t // 24, s))
        prev.clear()
        prev.update(animals)
        return a

    players = [None, None]
    players[seat] = ours
    players[1 - seat] = lambda obs, t: opp(obs)
    env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': tape['seed']})
    res = TV._play(E, env, players, seat, tape['shops'], None, None, seat)
    hist = ns.get('_MGT_HISTORY') or []
    routes = []
    for h in hist:
        if not routes or routes[-1][1] != h[1]:
            routes.append((h[0], h[1], h[3]))
    print('   shops', [s[:6] for s in (env.state[0].observation.town.unlocked_shops or [])], 'routes (day, tape, hamming)', routes,
          'overlay', {k: v for k, v in (ns.get('_SHP_REPORT') or {}).items() if k != 'decisions'})
    return res['final'][seat] - res['final'][1 - seat], counts, lost


def main():
    name = sys.argv[1]
    eps = [x if x.startswith('seed:') else int(x) for x in sys.argv[2].split(',')]
    rival = sys.argv[3] if len(sys.argv) > 3 else 'v50_public'
    total = Counter()
    for ep in eps:
        margin, counts, lost = run(name, ep, rival)
        total.update(counts)
        print(f'{ep}: margin {margin:+.0f}; animals lost {Counter(s for _, s in lost)} on days {sorted({d for d, _ in lost})}')
        print('   ' + ', '.join(f'{k} {v}' for k, v in counts.most_common(14)))
    if len(eps) > 1:
        print('TOTAL ' + ', '.join(f'{k} {v}' for k, v in total.most_common(20)))


if __name__ == '__main__':
    main()
