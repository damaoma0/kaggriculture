"""Engine check of candidate tomato servicing schedules: units harvested per plant for a given per-day
action list, using the engine's own tile functions on a synthetic one-tile farm (no market, no opponent).

Each schedule maps plant age (days since planting) -> list of ops applied that day in order
(WATER / FERTILIZE / HARVEST). The plant is put down on day 0 with the engine's _new_plant; end-of-day
refresh, decay and harvest use the engine code, so the numbers are exactly what a real game would give.
"""
from kaggle_environments.envs.kaggriculture import kaggriculture as E


def simulate(schedule, days=14, fertilizer=10):
    farm = E._new_farm(10, 3000)
    private = E._new_private()
    private['inventories'] = [{'FERTILIZER': fertilizer}]
    private['seeds'] = {'TOMATO': 1}
    farm['farmer'] = [0, 0]
    farm['tiles'][0][0] = None
    E._apply_unit_action(farm, private, 0, ['PLANT', 'TOMATO'], 10, 0, 24)
    harvested = 0
    actions = 0
    log = []
    for day in range(0, days):
        for op in schedule.get(day, []):
            before = private['inventories'][0].get('TOMATO', 0)
            E._apply_unit_action(farm, private, 0, [op], 10, day, 24)
            actions += 1
            got = private['inventories'][0].get('TOMATO', 0) - before
            harvested += got
            if op == 'HARVEST':
                log.append((day, 'H', got))
        # decay is checked every step; run the last step of the day then refresh
        for step in range(day * 24, day * 24 + 24):
            E._decay_plants(farm, step)
        E._daily_refresh_plants(farm, day, 24)
        t = farm['tiles'][0][0]
        if not isinstance(t, dict) or t.get('kind') != 'PLANT':
            break
    return harvested, actions, log


SCHEDULES = {
    'tape strawberry calendar (water every other day, fert+water age 9, harvest 10 and 12)':
        {0: ['WATER'], 2: ['WATER'], 3: ['WATER'], 5: ['WATER'], 7: ['WATER'], 9: ['FERTILIZE', 'WATER'], 10: ['HARVEST'],
         11: ['WATER'], 12: ['HARVEST']},
    'unfertilized, water daily, harvest 9 and 11':
        {**{d: ['WATER'] for d in range(0, 12)}, 9: ['HARVEST', 'WATER'], 11: ['HARVEST', 'WATER']},
    'fert age 7 and 10, water production days only + survival, harvest 9 and 11':
        {0: ['WATER'], 2: ['WATER'], 4: ['WATER'], 6: ['WATER'], 7: ['FERTILIZE', 'WATER'], 8: ['WATER'],
         9: ['HARVEST', 'WATER'], 10: ['FERTILIZE', 'WATER'], 11: ['HARVEST']},
    'fert age 7 only, water production days + survival, harvest 9 and 11':
        {0: ['WATER'], 2: ['WATER'], 4: ['WATER'], 6: ['WATER'], 7: ['FERTILIZE', 'WATER'], 8: ['WATER'],
         9: ['HARVEST', 'WATER'], 10: ['WATER'], 11: ['HARVEST']},
    'fert age 7 and 10, water daily, harvest daily from age 8':
        {**{d: ['WATER'] for d in range(0, 7)}, 7: ['FERTILIZE', 'WATER'], 8: ['HARVEST', 'WATER'], 9: ['HARVEST', 'WATER'],
         10: ['HARVEST', 'FERTILIZE', 'WATER'], 11: ['HARVEST', 'WATER'], 12: ['HARVEST']},
    'fert age 8 and 10 (one day late), water production days + survival, harvest 9 and 11':
        {0: ['WATER'], 2: ['WATER'], 4: ['WATER'], 6: ['WATER'], 7: ['WATER'], 8: ['FERTILIZE', 'WATER'],
         9: ['HARVEST', 'WATER'], 10: ['FERTILIZE', 'WATER'], 11: ['HARVEST']},
}

if __name__ == '__main__':
    for name, sched in SCHEDULES.items():
        units, actions, log = simulate(sched)
        print(f'{units} units, {actions} actions after planting, harvests {log}: {name}')
