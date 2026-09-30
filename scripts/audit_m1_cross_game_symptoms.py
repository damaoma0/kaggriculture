"""Exact recorded-action screen for recurring mgt_m1 crop-service symptoms.

Both winning and losing games are included. Output gaps are descriptive and
must not be read as the value of a production change at fixed prices.
"""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import gzip
from hashlib import sha256
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.venv/Lib/site-packages'))
sys.path.insert(0, str(ROOT / 'scripts'))
from research_labour_profit import Simulator, engine

SOURCE = ROOT / 'submissions/2026-09-20-mgt_m1/main.py'
OUT = ROOT / 'results/fresh/m1_cross_game_symptoms'
EPISODES = OUT / 'episodes'
VERSION = 2
BERRY_SHOPS = {'FARMERS_MARKET', 'BRUNCH_SPOT', 'ICE_CREAM_SHOP', 'SMOOTHIE_SHOP'}


def audit_one(path):
    ep = int(path.name.split('.')[0])
    target = EPISODES / f'{ep}.json'
    if target.exists():
        cached = json.loads(target.read_text(encoding='utf8'))
        if cached.get('version') == VERSION:
            return cached
    with gzip.open(path, 'rt', encoding='utf8') as f:
        game = json.load(f)
    seat = game['seat']
    actions = [None, None]
    actions[seat], actions[1-seat] = game['our_actions'], game['opp_actions']
    E = engine()
    fert = [Counter(), Counter()]
    planted = [Counter(), Counter()]
    harvested = [Counter(), Counter()]
    checkpoints = {}
    with Simulator(game) as sim:
        old = E._apply_unit_action
        old_interpreter = E.interpreter

        def interpreter(state, env):
            day = sim.t // 24
            if sim.t % 24 == 0 and day in (9, 11, 12, 15, 18, 21, 24):
                obs = state[seat].observation
                farms = obs.farms
                checkpoints[str(day)] = dict(
                    cash=[farms[side]['money'] for side in (seat, 1-seat)],
                    berry_quote=obs.market['prices']['STRAWBERRY'],
                    berry_plots=[sum(isinstance(tile, dict) and tile.get('crop') == 'STRAWBERRY'
                                     for row in farms[side]['tiles'] for tile in row)
                                 for side in (seat, 1-seat)],
                    free_unlocked=[sum(tile is None for row in farms[side]['tiles'] for tile in row)
                                   for side in (seat, 1-seat)],
                    locked=[sum(tile == 'LOCKED' for row in farms[side]['tiles'] for tile in row)
                            for side in (seat, 1-seat)])
            return old_interpreter(state, env)

        def unit(farm, private, idx, action, *args, **kwargs):
            if idx >= len(private['inventories']) or not action:
                return old(farm, private, idx, action, *args, **kwargs)
            op = action[0]
            if op not in ('FERTILIZE', 'PLANT', 'HARVEST'):
                return old(farm, private, idx, action, *args, **kwargs)
            side = sim.seats[id(farm)]
            pos = E._farmer_position(farm, idx)
            if pos is None:
                return old(farm, private, idx, action, *args, **kwargs)
            tile = farm['tiles'][pos[1]][pos[0]]
            crop = tile.get('crop') if isinstance(tile, dict) else None
            before_fert = private['inventories'][idx].get('FERTILIZER', 0)
            before_inv = private['inventories'][idx].get(crop, 0) if op == 'HARVEST' and crop else 0
            seed = action[1] if op == 'PLANT' and len(action) > 1 else None
            before_seed = private['seeds'].get(seed, 0) if seed else 0
            result = old(farm, private, idx, action, *args, **kwargs)
            if op == 'FERTILIZE' and crop:
                fert[side][crop] += before_fert - private['inventories'][idx].get('FERTILIZER', 0)
            elif op == 'PLANT' and seed:
                planted[side][seed] += before_seed - private['seeds'].get(seed, 0)
            elif op == 'HARVEST' and crop:
                harvested[side][crop] += private['inventories'][idx].get(crop, 0) - before_inv
            return result

        E._apply_unit_action = unit
        E.interpreter = interpreter
        try:
            result = sim.run(sim.initial, 0, 719, actions)
        finally:
            E._apply_unit_action = old
            E.interpreter = old_interpreter
    assert result['money'] == game['rewards'], ep
    sales = [Counter(), Counter()]
    revenue = [Counter(), Counter()]
    spend = [Counter(), Counter()]
    for _, side, op, item, price in result['events']:
        if op == 'SELL':
            sales[side][item] += 1
            revenue[side][item] += price
        else:
            spend[side][f'{op}:{item}' if item else op] += price
    summary = dict(version=VERSION, episode=ep, seat=seat, margin=result['money'][seat]-result['money'][1-seat],
                   rewards=result['money'], shops=game['shops'][29],
                   berry_shops=sum(x in BERRY_SHOPS for x in game['shops'][29]), checkpoints=checkpoints,
                   berry_shops_by_day={str(day):sum(x in BERRY_SHOPS for x in game['shops'][day]) for day in (9,12,15,18,24)},
                   sides=[])
    for side in (seat, 1-seat):
        summary['sides'].append(dict(fertilize=dict(fert[side]), planted=dict(planted[side]),
                                     harvested=dict(harvested[side]), sales=dict(sales[side]),
                                     revenue=dict(revenue[side]), spend=dict(spend[side])))
    EPISODES.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary), encoding='utf8')
    return summary


def median(values):
    return statistics.median(values) if values else None


def summarize(rows):
    def v(r, side, section, product):
        return r['sides'][side][section].get(product, 0)
    return dict(
        games=len(rows),
        berry_shop_2plus=sum(r['berry_shops'] >= 2 for r in rows),
        berry_shop_3plus=sum(r['berry_shops'] >= 3 for r in rows),
        planted_less_strawberry=sum(v(r,0,'planted','STRAWBERRY') < v(r,1,'planted','STRAWBERRY') for r in rows),
        harvested_less_strawberry=sum(v(r,0,'harvested','STRAWBERRY') < v(r,1,'harvested','STRAWBERRY') for r in rows),
        fert_less_strawberry=sum(v(r,0,'fertilize','STRAWBERRY') < v(r,1,'fertilize','STRAWBERRY') for r in rows),
        planted_and_fert_less_strawberry=sum(v(r,0,'planted','STRAWBERRY') < v(r,1,'planted','STRAWBERRY') and
                                          v(r,0,'fertilize','STRAWBERRY') < v(r,1,'fertilize','STRAWBERRY') for r in rows),
        total_fert_more_but_berry_fert_less=sum(sum(r['sides'][0]['fertilize'].values()) >
                                            sum(r['sides'][1]['fertilize'].values()) and
                                            v(r,0,'fertilize','STRAWBERRY') < v(r,1,'fertilize','STRAWBERRY') for r in rows),
        berry_revenue_gap_sum=sum(v(r,0,'revenue','STRAWBERRY')-v(r,1,'revenue','STRAWBERRY') for r in rows),
        berry_revenue_gap_negative=sum(v(r,0,'revenue','STRAWBERRY') < v(r,1,'revenue','STRAWBERRY') for r in rows),
        berry_revenue_gap_below_minus_5000=sum(v(r,0,'revenue','STRAWBERRY')-v(r,1,'revenue','STRAWBERRY') < -5000 for r in rows),
        berry_unit_gap_sum=sum(v(r,0,'harvested','STRAWBERRY')-v(r,1,'harvested','STRAWBERRY') for r in rows),
        median_berry_unit_gap=median([v(r,0,'harvested','STRAWBERRY')-v(r,1,'harvested','STRAWBERRY') for r in rows]),
        mean_berry_yield_per_plot=[sum(v(r,s,'harvested','STRAWBERRY') for r in rows) /
                                   sum(v(r,s,'planted','STRAWBERRY') for r in rows) if rows else None for s in (0,1)],
        total_strawberry_fertilize=[sum(v(r,s,'fertilize','STRAWBERRY') for r in rows) for s in (0,1)],
        total_fertilize=[sum(sum(r['sides'][s]['fertilize'].values()) for r in rows) for s in (0,1)],
        total_strawberry_planted=[sum(v(r,s,'planted','STRAWBERRY') for r in rows) for s in (0,1)],
        total_strawberry_harvested=[sum(v(r,s,'harvested','STRAWBERRY') for r in rows) for s in (0,1)],
        own_yield_below_7_rival_at_least_7_4=sum(
            v(r,0,'harvested','STRAWBERRY') / max(1, v(r,0,'planted','STRAWBERRY')) < 7 and
            v(r,1,'harvested','STRAWBERRY') / max(1, v(r,1,'planted','STRAWBERRY')) >= 7.4
            for r in rows),
    )


def loss_route_diagnostics(rows):
    from audit_production_plan_fit import load_library
    _, library = load_library()
    tape_shops = {int(t['ep']):t['shops'] for t in library['tapes']}
    by_ep = {r['episode']:r for r in rows}
    plans = [json.loads(p.read_text(encoding='utf8')) for p in
             (ROOT / 'results/fresh/all_umg_m1/plans').glob('*.json')]
    assert len(plans) == len(rows) == 89
    gaps = []
    no_switch_after_12 = 0
    for plan in plans:
        history = plan['history']
        changes = [x[0] for i,x in enumerate(history) if i and x[1] != history[i-1][1]]
        no_switch_after_12 += not changes or max(changes) <= 12
        donor = tape_shops[next(x[1] for x in history if x[0] == 12)][:4]
        actual = plan['actualShops'][:4]
        berry_demand_gap = sum(x in BERRY_SHOPS for x in actual) - sum(x in BERRY_SHOPS for x in donor)
        row = by_ep[plan['episode']]
        berry_revenue_gap = row['sides'][0]['revenue'].get('STRAWBERRY',0) - row['sides'][1]['revenue'].get('STRAWBERRY',0)
        gaps.append((berry_demand_gap, berry_revenue_gap))
    positive = [r for r in gaps if r[0] > 0]
    return dict(losses=len(plans), no_switch_after_day12=no_switch_after_12,
                day12_berry_demand_positive=sum(x[0]>0 for x in gaps),
                day12_berry_demand_zero=sum(x[0]==0 for x in gaps),
                day12_berry_demand_negative=sum(x[0]<0 for x in gaps),
                median_berry_revenue_gap_when_day12_positive=median([x[1] for x in positive]))


def main():
    paths = sorted((ROOT / 'data/ladder_panel/56395605').glob('*.json.gz'))
    assert len(paths) == 198
    EPISODES.mkdir(parents=True, exist_ok=True)
    rows = []
    with ProcessPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(audit_one, p):p for p in paths}
        for n, future in enumerate(as_completed(futures), 1):
            rows.append(future.result())
            if n % 20 == 0 or n == len(futures):
                print(n, '/', len(futures), flush=True)
    assert len(rows) == len({x['episode'] for x in rows}) == 198
    rows.sort(key=lambda x:x['episode'])
    losses = [r for r in rows if r['margin'] < 0]
    wins = [r for r in rows if r['margin'] > 0]
    assert len(losses) == 89 and len(wins) == 109
    result = dict(version=VERSION, source_hash=sha256(SOURCE.read_bytes()).hexdigest(),
                  protocol='198 exact recorded-action engine replays; no agent decisions changed. Sides are [mgt_m1, opponent].',
                  groups=dict(all=summarize(rows), losses=summarize(losses), wins=summarize(wins),
                              loss_berry_shops_2plus=summarize([r for r in losses if r['berry_shops']>=2]),
                              win_berry_shops_2plus=summarize([r for r in wins if r['berry_shops']>=2])),
                  loss_route=loss_route_diagnostics(losses),
                  episodes=rows)
    (OUT / 'summary.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps(result['groups'], indent=2), flush=True)
    print(json.dumps(result['loss_route'], indent=2), flush=True)


if __name__ == '__main__':
    main()
