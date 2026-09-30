"""How much of the benchmark tape's labour is redundant, i.e. freeable for an executor without hiring?

Plays the frozen benchmark against itself on a few seeds and classifies every effective WATER by the tile
state before it: 'yield' (adds units: one-time crop inside its watering window; ongoing crop on a production
day while fertilized), 'survival' (the plant was not watered yesterday, so skipping would risk a weed),
or 'redundant' (neither). Also counts PASS turns and blocked moves per day. Output:
results/fresh/mg_executor/tape_slack.json
"""
import json, sys
from collections import Counter
from market_corpus import ROOT

CROPS = {'WHEAT': (2, 4, 0, 6, False), 'CARROT': (2, 3, 0, 4, False), 'TOMATO': (8, 8, 1, 4, True),
         'STRAWBERRY': (10, 10, 2, 4, True), 'MELON': (10, 12, 0, 6, False)}
BENCH = ROOT / 'agents/benchmark_frozen_56280048.py'


def classify(tile, day):
    first, maxday, interval, maxy, ongoing = CROPS[tile['crop']]
    age = day - tile['planted_day']
    fert = tile.get('fertilized_until_day', -1) >= day
    if ongoing:
        # the engine produces at the END of day d when (d + 1) - planted_day reaches the schedule
        since = age + 1 - first
        production_today = since >= 0 and since % interval == 0 and since // interval + 1 <= maxy
        yield_ = production_today and fert
    else:
        ws = (maxday + 1) // 2
        yield_ = ws <= age <= maxday and tile['yield_units'] < maxy
    if yield_:
        return 'yield'
    if tile.get('consecutive_unwatered', 0) >= 1:
        return 'survival'
    return 'redundant'


def run(seed):
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    agents = [get_last_callable(BENCH.read_text(encoding='utf-8'), path=str(BENCH)) for _ in (0, 1)]
    env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': seed})
    per_day = Counter()
    by_crop = Counter()
    unit = E._apply_unit_action
    interpreter = env.interpreter
    seat0 = set()

    def real(state, environment):
        seat0.clear()
        farms = getattr(state[0].observation, 'farms', None) or []
        if farms:
            seat0.add(id(farms[0]))
        return interpreter(state, environment)

    def work(farm, private, idx, action, board, day, tpd, cap=100):
        if id(farm) in seat0 and isinstance(action, list) and action:
            pos = E._farmer_position(farm, idx)
            tile = farm['tiles'][pos[1]][pos[0]] if pos else None
            op = action[0]
            if op == 'WATER' and isinstance(tile, dict) and tile.get('kind') == 'PLANT' and not tile['watered_today']:
                c = classify(tile, day)
                per_day[(day, c)] += 1
                by_crop[(tile['crop'], c)] += 1
            elif op == 'PASS':
                per_day[(day, 'pass')] += 1
            elif op in E.FARMER_MOVES:
                per_day[(day, 'move')] += 1
            elif op == 'WATER':
                per_day[(day, 'water_noop')] += 1
            else:
                per_day[(day, 'other')] += 1
        return unit(farm, private, idx, action, board, day, tpd, cap)

    E._apply_unit_action = work
    env.interpreter = real
    try:
        env.run([lambda obs: agents[0](obs), lambda obs: agents[1](obs)])
    finally:
        E._apply_unit_action = unit
        env.interpreter = interpreter
    return per_day, by_crop


def main():
    seeds = [int(s) for s in sys.argv[1:]] or [175000, 175001, 175002, 175003]
    tot_day, tot_crop = Counter(), Counter()
    for s in seeds:
        d, c = run(s)
        tot_day.update(d)
        tot_crop.update(c)
    n = len(seeds)
    out = ROOT / 'results/fresh/mg_executor'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'tape_slack.json').write_text(json.dumps({'seeds': seeds, 'per_day': {f'{k[0]}:{k[1]}': v for k, v in tot_day.items()},
                                                    'by_crop': {f'{k[0]}:{k[1]}': v for k, v in tot_crop.items()}}), encoding='utf-8')
    print(f'per game (mean of {n}): water yield {sum(v for k, v in tot_crop.items() if k[1] == "yield") / n:.0f}, '
          f'survival {sum(v for k, v in tot_crop.items() if k[1] == "survival") / n:.0f}, '
          f'redundant {sum(v for k, v in tot_crop.items() if k[1] == "redundant") / n:.0f}')
    for crop in CROPS:
        print(f'  {crop:10s} ' + ' '.join(f'{c} {tot_crop[(crop, c)] / n:5.0f}' for c in ('yield', 'survival', 'redundant')))
    print('day: redundant waters / pass / moves (per game)')
    print(' '.join(f'{d}:{tot_day[(d, "redundant")] / n:.0f}/{tot_day[(d, "pass")] / n:.0f}/{tot_day[(d, "move")] / n:.0f}' for d in range(30)))


if __name__ == '__main__':
    main()
