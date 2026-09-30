"""Is our strawberry shortfall a volume (glut) problem or a sale-timing problem?

Runs one self-play game (frozen benchmark both seats) and records, per step, the market inventory
and quoted price of each product plus every successful sale, so the realised price can be attributed
to the inventory level at the moment of sale. I0 = 10000 is the neutral inventory; above it prices
fall, below it they rise.
"""
import json, sys
from collections import Counter
from market_corpus import ROOT

OUT = ROOT / 'results/fresh/selfplay'
BENCH = ROOT / 'agents/benchmark_frozen_56280048.py'
ITEMS = ['STRAWBERRY', 'WHEAT', 'CARROT', 'TOMATO', 'MILK', 'WOOL', 'EGG', 'MELON', 'FERTILIZER']


def main(seed=171000):
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.envs.kaggriculture import kaggriculture as E

    fn = get_last_callable(BENCH.read_text(encoding='utf-8'), path=str(BENCH))
    env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': seed})
    sales = []
    step = [0]
    seats = {}
    commit = E._commit_unit
    process = E._process_market

    def market(state, env_):
        seats.clear()
        seats.update({id(f): i for i, f in enumerate(state[0].observation.farms)})
        step[0] = int(state[0].observation.step)
        return process(state, env_)

    def wrapped(op, item, price, farm, private, mkt, shed_capacity=100):
        before = mkt['inventory'].get(item)
        ok = commit(op, item, price, farm, private, mkt, shed_capacity)
        if ok and op == 'SELL':
            sales.append(dict(step=step[0], seat=seats.get(id(farm)), item=item, price=price, inventory=before))
        return ok

    E._commit_unit, E._process_market = wrapped, market
    try:
        env.run([fn, get_last_callable(BENCH.read_text(encoding='utf-8'), path=str(BENCH))])
    finally:
        E._commit_unit, E._process_market = commit, process
    inv = [{item: s[0].observation.market.inventory[item] for item in ITEMS} for s in env.steps]
    prices = [{item: s[0].observation.market.prices[item] for item in ITEMS} for s in env.steps]
    print(f'seed {seed}: cash {[s.reward for s in env.state]}')
    print('\nmarket inventory relative to the neutral 10000 (negative = scarce = high price)')
    print('day  | ' + ' | '.join(f'{i[:5]:>6s}' for i in ITEMS))
    for day in range(0, 30, 3):
        row = inv[day * 24]
        print(f'{day:4d} | ' + ' | '.join(f'{row[i]-10000:+6d}' for i in ITEMS))
    print('\nquoted price at the same checkpoints')
    print('day  | ' + ' | '.join(f'{i[:5]:>6s}' for i in ITEMS))
    for day in range(0, 30, 3):
        row = prices[day * 24]
        print(f'{day:4d} | ' + ' | '.join(f'{row[i]:6.0f}' for i in ITEMS))
    print('\nsales attribution, seat 0 (both seats are the same policy)')
    print('item        | units | revenue | mean price | mean inventory at sale | units sold above neutral')
    for item in ITEMS:
        rows = [s for s in sales if s['item'] == item and s['seat'] == 0]
        if not rows:
            continue
        units = len(rows)
        revenue = sum(r['price'] for r in rows)
        above = sum(1 for r in rows if r['inventory'] > 10000)
        print(f'{item:11s} | {units:5d} | {revenue:7.0f} | {revenue/units:10.1f} | '
              f'{sum(r["inventory"] for r in rows)/units-10000:+22.0f} | {above:5d} ({100*above/units:.0f}%)')
    print('\nstrawberry sale schedule, seat 0: units sold per day and the inventory they hit')
    by_day = {}
    for s in sales:
        if s['item'] == 'STRAWBERRY' and s['seat'] == 0:
            by_day.setdefault(s['step'] // 24, []).append(s)
    for day in sorted(by_day):
        rows = by_day[day]
        print(f'  day {day:2d}: {len(rows):3d} units, price {rows[0]["price"]:.0f} -> {rows[-1]["price"]:.0f}, '
              f'inventory {rows[0]["inventory"]-10000:+d} -> {rows[-1]["inventory"]-10000:+d}')
    both = Counter()
    for s in sales:
        if s['item'] == 'STRAWBERRY':
            both[s['step'] // 24] += 1
    print('\nstrawberry units sold per day, both seats combined:',
          ' '.join(f'd{d}={n}' for d, n in sorted(both.items())))
    (OUT / f'strawberry-diagnosis-{seed}.json').write_text(json.dumps(
        dict(seed=seed, cash=[s.reward for s in env.state], sales=sales,
             inventory_by_day={str(d): inv[d * 24] for d in range(30)},
             prices_by_day={str(d): prices[d * 24] for d in range(30)}), indent=1), encoding='utf-8')


if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 171000)
