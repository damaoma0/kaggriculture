"""Extract Mother-Goose's complete decision timeline from her 30 exactly replayable games.

Phase 1 of reconstructing her policy: recover rules, not actions. For every game this records, for
her seat only:
  * every unit action that changes the board: PLANT (crop, tile), BUILD_COOP/BUILD_PASTURE (tile),
    PLACE animal (tile), DIG (tile, and what was dug), with the step and the acting unit;
  * every market order as requested (BUY_SEED, BUY_ANIMAL, BUY_PRODUCT, SELL, HIRE, BUY_LAND);
  * her board (crop/animal per tile), money, shed, seeds and hands at the start of every day;
  * the shops visible at every day, and the market prices at every day start.
Positions come from the observation the action was chosen from, so a PLANT's tile is exact.

Output: results/fresh/mg_policy/events-<episode>.json
"""
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from market_corpus import ROOT

OUT = ROOT / 'results/fresh/mg_policy'
REPLAYS = ROOT / 'data/leaders_20260917'
MG = ('Unknown Mother-Goose', 56266758)
BOARD_OPS = ('PLANT', 'BUILD_COOP', 'BUILD_PASTURE', 'PLACE', 'DIG', 'HARVEST', 'FERTILIZE')


def tile_label(tile):
    if tile == 'LOCKED':
        return 'L'
    if tile is None:
        return '.'
    if tile.get('kind') == 'PLANT':
        return tile['crop'][:2]
    if tile.get('kind') == 'WEED':
        return 'w'
    if tile.get('animal'):
        return tile['animal'][:2].lower()
    return tile['kind'][:2].lower()


def run(job):
    path, eid, seat = job
    replay = json.loads(open(path, encoding='utf-8').read())
    events, days = [], []
    for t in range(719):
        obs = replay['steps'][t][seat]['observation']
        if not obs.get('farms'):
            obs = replay['steps'][t][0]['observation']
        farm = obs['farms'][seat]
        if t % 24 == 0:
            days.append(dict(
                day=t // 24, money=farm['money'], shops=list(obs['town']['unlocked_shops']),
                prices=dict(obs['market']['prices']), inventory=dict(obs['market']['inventory']),
                board=[[tile_label(x) for x in row] for row in farm['tiles']],
                shed=dict(replay['steps'][t][seat]['observation']['private']['shed']),
                seeds=dict(replay['steps'][t][seat]['observation']['private']['seeds']),
                quadrants=list(farm['unlocked_quadrants'])))
        action = replay['steps'][t + 1][seat]['action'] or {}
        units = [('farmer', action.get('farmer'))] + [(f'hand{i + 1}', a) for i, a in enumerate(action.get('hands') or [])]
        positions = [farm['farmer']] + list(farm['hands'])
        for index, (who, unit) in enumerate(units):
            if not isinstance(unit, list) or not unit or unit[0] not in BOARD_OPS:
                continue
            if index >= len(positions):
                events.append(dict(step=t, kind='unit', unit=who, op=unit[0], arg=unit[1:] or None, tile=None,
                                   note='no such hand'))
                continue
            x, y = positions[index]
            before = tile_label(farm['tiles'][y][x])
            events.append(dict(step=t, kind='unit', unit=who, op=unit[0], arg=unit[1:] or None, tile=[x, y],
                               before=before))
        for order in action.get('market') or []:
            if isinstance(order, list) and order and isinstance(order[0], str):
                events.append(dict(step=t, kind='market', op=order[0],
                                   item=order[1] if len(order) > 1 and isinstance(order[1], str) else None,
                                   qty=int(order[2]) if len(order) > 2 else 1, money=farm['money']))
    final = replay['steps'][719][seat]['observation']['farms'][seat]
    result = dict(episode=eid, seat=seat, teams=replay['info']['TeamNames'], seed=replay['info']['seed'],
                  rewards=replay['rewards'], days=days, events=events,
                  final_board=[[tile_label(x) for x in row] for row in final['tiles']])
    (OUT / f'events-{eid}.json').write_text(json.dumps(result), encoding='utf-8')
    return eid


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sample = json.loads((ROOT / 'results/fresh/leader_segments/sample.json').read_text(encoding='utf-8'))
    subs = {e['id']: [a['sub'] for a in e['agents']] for e in sample['sample']}
    jobs = []
    for path in sorted(REPLAYS.glob('episode-*-replay.json')):
        eid = int(path.name.split('-')[1])
        for seat, sub in enumerate(subs[eid]):
            if sub == MG[1]:
                jobs.append((str(path), eid, seat))
    with ProcessPoolExecutor(max_workers=4) as pool:
        for f in as_completed([pool.submit(run, j) for j in jobs]):
            print('extracted', f.result(), flush=True)


if __name__ == '__main__':
    main()
