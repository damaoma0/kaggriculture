"""Read-only analysis (thread 20260928): does DSM (team 16732748) behave differently on days when a new
shop instance appears (REVEAL) versus days when it doesn't (NORMAL), days 11-28 of a 30-day season?

Replays the 40 recorded DSM games in results/fresh/threads_20260928/panel_dsm40b.txt through the repo's
engine harness (scripts/upkeep_engine.py -> the real kaggriculture.py, 1.32.7), hooking the same engine
functions scripts/case_world.py hooks (_commit_unit, _apply_unit_action, _drop_inventories_to_shed), plus
_do_hire, to log per in-game-day: sales (unit/price/hour/market stock), deliveries into the shed during the
day (DROP / shed-adjacent PLACE) vs the midnight dump (_drop_inventories_to_shed, called once per day end),
harvest/feed/care/water/fertilize/plant/collect-fertilizer op counts, hires, animals bought, and market
stock+price at hour 0 / hour 23 of each day.

REVEAL/NORMAL labeling and "which products" use World.shops directly (upkeep_engine.World precomputes, per
seed+recording, the exact `unlocked_shops` list the engine's end-of-day hook forces into the observation for
every day 0-30: `shops[d] = shops_flat[:min(8, d // 3)]`) rather than assuming the 3/6/9/.../24 schedule; a
day is REVEAL iff len(shops[d]) > len(shops[d-1]), and the new shop is shops[d][-1]. kaggriculture.SHOPS maps
shop name -> products it buys.

Usage: .venv/Scripts/python.exe scripts/thread_shopday_behavior.py [--workers N] [--limit N] [--out DIR]
Writes <out>/per_game/<ep>.json (one per game) and <out>/summary.json (the cross-game REVEAL vs NORMAL
aggregation) and prints a short text report.
"""
import argparse
import copy
import json
import multiprocessing as mp
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, pstdev

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

PANEL = ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt'
OUT_DEFAULT = ROOT / 'results/fresh/threads_20260928/shopdays'
DAY0, DAY1 = 11, 28  # inclusive window of interest
OPS_TRACK = ('HARVEST', 'FEED', 'CARE', 'WATER', 'FERTILIZE', 'PLANT', 'COLLECT_FERTILIZER')
SRC_OF = {'STRAWBERRY': 'STRAWBERRY', 'TOMATO': 'TOMATO', 'CARROT': 'CARROT', 'WHEAT': 'WHEAT', 'MELON': 'MELON',
          'WOOL': 'SHEEP', 'MILK': 'COW', 'EGG': 'GOOSE'}
ANIMAL_PRODUCT = {'SHEEP': 'WOOL', 'COW': 'MILK', 'GOOSE': 'EGG'}


def _hour_bucket(h):
    if h == 0:
        return 'h0'
    if h == 1:
        return 'h1'
    if h <= 11:
        return 'h2_11'
    return 'h12_23'


def analyze_game(spec):
    team_s, ep_s = spec.split(':')
    team, ep = int(team_s), int(ep_s)
    tape = UE.load_tape(team, ep)
    E = UE.engine()
    SHOPS = E.SHOPS

    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']

    reveal = {}
    for d in range(DAY0, DAY1 + 1):
        if len(w.shops[d]) > len(w.shops[d - 1]):
            shop_name = w.shops[d][-1]
            reveal[d] = {'shop': shop_name, 'products': list(SHOPS[shop_name])}

    rec = {
        'sales': defaultdict(list),                       # day -> [t, hour, side, op, item, price, inv_before]
        'ops': defaultdict(Counter),                       # day -> Counter('OP|label')
        'harv': defaultdict(Counter),                      # day -> Counter(product -> units)
        'hires': Counter(),                                # day -> n (us)
        'animals_bought': defaultdict(Counter),            # day -> Counter(animal) (us)
        'deliv_day': defaultdict(Counter),                 # day -> Counter(product -> units), DROP/PLACE (us)
        'deliv_mid': defaultdict(Counter),                 # day -> Counter(product -> units), midnight dump (us)
        'lost': defaultdict(Counter),                      # day -> Counter(product -> units discarded, cap overflow, us)
        'place_animal': defaultdict(Counter),              # day -> Counter(animal -> count placed) (us)
        'stock_h0': {}, 'stock_h23': {},                   # day -> {product: inventory}
        'price_h0': {}, 'price_h23': {},                   # day -> {product: price}
    }
    cur = {'t': 0}

    orig_commit = E._commit_unit
    orig_ua = E._apply_unit_action
    orig_hire = E._do_hire
    orig_drop_mid = E._drop_inventories_to_shed

    def commit(op, item, price, farm, private, market, shed_capacity=100):
        inv_before = market['inventory'].get(item)
        ok = orig_commit(op, item, price, farm, private, market, shed_capacity)
        if ok and op in ('SELL', 'BUY_PRODUCT', 'BUY_ANIMAL'):
            t = cur['t']
            d = t // 24
            if DAY0 <= d <= DAY1:
                side = 'us' if farm is w.farms[seat] else 'opp'
                rec['sales'][d].append([t, t % 24, side, op, item, float(price), inv_before])
                if op == 'BUY_ANIMAL' and side == 'us':
                    rec['animals_bought'][d][item] += 1
        return ok

    def ua(farm, private, idx, action, *a, **k):
        t = cur['t']
        d = t // 24
        if not (DAY0 <= d <= DAY1 and farm is w.farms[seat] and isinstance(action, list) and action):
            return orig_ua(farm, private, idx, action, *a, **k)
        op = action[0]
        if op not in OPS_TRACK and op not in ('DROP', 'PLACE'):
            return orig_ua(farm, private, idx, action, *a, **k)
        pos = E._farmer_position(farm, idx)
        if pos is None:
            return orig_ua(farm, private, idx, action, *a, **k)
        tile0 = farm['tiles'][pos[1]][pos[0]]
        label0 = (tile0.get('crop') or tile0.get('animal') or tile0.get('kind')) if isinstance(tile0, dict) else 'EMPTY'
        # WATER/CARE mutate the tile dict IN PLACE (no reassignment of the grid cell), so a plain
        # reference captured here would alias the post-mutation object; snapshot it first so the
        # before/after json comparison below is meaningful for those ops too.
        tile0_snap = copy.deepcopy(tile0) if isinstance(tile0, dict) else tile0
        inv_before = dict(E._farmer_inventory(private, idx))
        shed_before = dict(private['shed'])
        r = orig_ua(farm, private, idx, action, *a, **k)
        tile1 = farm['tiles'][pos[1]][pos[0]]
        if op in OPS_TRACK:
            inv_after = E._farmer_inventory(private, idx)
            tb = json.dumps(tile0_snap, sort_keys=True, default=str)
            ta = json.dumps(tile1, sort_keys=True, default=str)
            if ta != tb or inv_after != inv_before:
                rec['ops'][d][f'{op}|{label0}'] += 1
                if op == 'HARVEST':
                    for kk, v in inv_after.items():
                        gain = v - inv_before.get(kk, 0)
                        if gain > 0:
                            rec['harv'][d][kk] += gain
        else:  # DROP / PLACE
            newly_animal = isinstance(tile1, dict) and 'animal' in tile1 and not (isinstance(tile0_snap, dict) and 'animal' in tile0_snap)
            if newly_animal:
                rec['place_animal'][d][tile1['animal']] += 1
            else:
                shed_after = private['shed']
                for kk, v in shed_after.items():
                    gain = v - shed_before.get(kk, 0)
                    if gain > 0:
                        rec['deliv_day'][d][kk] += gain
        return r

    def hire(farm, private, *a, **k):
        before = farm['money']
        orig_hire(farm, private, *a, **k)
        t = cur['t']
        d = t // 24
        if DAY0 <= d <= DAY1 and farm is w.farms[seat] and farm['money'] != before:
            rec['hires'][d] += 1

    def drop_mid(private, capacity):
        t = cur['t']
        d = t // 24  # day that is ending (midnight dump belongs to the day that just finished)
        if not (DAY0 <= d <= DAY1 and private is w.private(seat)):
            return orig_drop_mid(private, capacity)
        carried = Counter()
        for inv in private['inventories']:
            for kk, v in inv.items():
                if v > 0:
                    carried[kk] += v
        before = dict(private['shed'])
        orig_drop_mid(private, capacity)
        after = private['shed']
        for kk, v in carried.items():
            landed = max(0, after.get(kk, 0) - before.get(kk, 0))
            if landed > 0:
                rec['deliv_mid'][d][kk] += landed
            lost = v - landed
            if lost > 0:
                rec['lost'][d][kk] += lost
        return

    E._commit_unit, E._apply_unit_action, E._do_hire, E._drop_inventories_to_shed = commit, ua, hire, drop_mid
    try:
        while w.t < 719:
            t = w.t
            cur['t'] = t
            d = t // 24
            if DAY0 <= d <= DAY1 and t % 24 == 0:
                rec['stock_h0'][d] = dict(w.market['inventory'])
                rec['price_h0'][d] = dict(w.market['prices'])
            if DAY0 <= d <= DAY1 and t % 24 == 23:
                rec['stock_h23'][d] = dict(w.market['inventory'])
                rec['price_h23'][d] = dict(w.market['prices'])
            acts = [None, None]
            acts[seat] = UE.tape_action(tape['actions'], t)
            acts[1 - seat] = UE.tape_action(tape['opp_actions'], t)
            w.step(acts)
    finally:
        E._commit_unit, E._apply_unit_action, E._do_hire, E._drop_inventories_to_shed = orig_commit, orig_ua, orig_hire, orig_drop_mid

    money_us = float(w.farms[seat]['money'])
    money_opp = float(w.farms[1 - seat]['money'])

    out = {
        'game': spec, 'team': team, 'ep': ep, 'seat': seat, 'reveal': reveal,
        'sales': {d: v for d, v in rec['sales'].items()},
        'ops': {d: dict(c) for d, c in rec['ops'].items()},
        'harv': {d: dict(c) for d, c in rec['harv'].items()},
        'hires': dict(rec['hires']),
        'animals_bought': {d: dict(c) for d, c in rec['animals_bought'].items()},
        'place_animal': {d: dict(c) for d, c in rec['place_animal'].items()},
        'deliv_day': {d: dict(c) for d, c in rec['deliv_day'].items()},
        'deliv_mid': {d: dict(c) for d, c in rec['deliv_mid'].items()},
        'lost': {d: dict(c) for d, c in rec['lost'].items()},
        'stock_h0': rec['stock_h0'], 'stock_h23': rec['stock_h23'],
        'price_h0': rec['price_h0'], 'price_h23': rec['price_h23'],
        'money_us': money_us, 'money_opp': money_opp,
    }
    return out


def _jsonify_daykeys(d):
    """json.dump turns int dict keys into strings; do it explicitly for round-trip clarity."""
    return {str(k): v for k, v in d.items()}


def dump_game(res, per_game_dir):
    per_game_dir.mkdir(parents=True, exist_ok=True)
    p = per_game_dir / f"{res['ep']}.json"
    j = dict(res)
    for k in ('sales', 'ops', 'harv', 'animals_bought', 'place_animal', 'deliv_day', 'deliv_mid', 'lost',
              'stock_h0', 'stock_h23', 'price_h0', 'price_h23'):
        j[k] = _jsonify_daykeys(j[k])
    j['reveal'] = _jsonify_daykeys(j['reveal'])
    p.write_text(json.dumps(j, indent=1), encoding='utf-8')
    return p


# ---------------------------------------------------------------------------
# Aggregation: REVEAL vs NORMAL, days 11-28, across all games.
# ---------------------------------------------------------------------------

def aggregate(all_res):
    days = list(range(DAY0, DAY1 + 1))
    reveal_days = []   # list of (game, d, new_products, shop_name)
    normal_days = []   # list of (game, d)
    for res in all_res:
        for d in days:
            if d in res['reveal']:
                reveal_days.append((res, d, res['reveal'][d]['products'], res['reveal'][d]['shop']))
            else:
                normal_days.append((res, d))

    def day_sales_units_rev(res, d, side='us', op='SELL', item=None):
        n, rev = 0, 0.0
        for t, hour, s, o, it, price, inv in res['sales'].get(d, []):
            if s == side and o == op and (item is None or it == item):
                n += 1
                rev += price
        return n, rev

    def day_sales_hourbuckets(res, d, side='us', op='SELL', item=None):
        buckets = Counter()
        for t, hour, s, o, it, price, inv in res['sales'].get(d, []):
            if s == side and o == op and (item is None or it == item):
                buckets[_hour_bucket(hour)] += 1
        return buckets

    # 1) Overall sales units/day (us), REVEAL vs NORMAL
    rev_units = [sum(day_sales_units_rev(res, d)[0] for _ in [0]) for res, d, *_ in reveal_days]
    rev_units = [day_sales_units_rev(res, d)[0] for res, d, *_ in reveal_days]
    nor_units = [day_sales_units_rev(res, d)[0] for res, d in normal_days]
    rev_rev = [day_sales_units_rev(res, d)[1] for res, d, *_ in reveal_days]
    nor_rev = [day_sales_units_rev(res, d)[1] for res, d in normal_days]
    rev_price = [r / n for n, r in zip(rev_units, rev_rev) if n]
    nor_price = [r / n for n, r in zip(nor_units, nor_rev) if n]

    # Hour buckets, all products, us side
    rev_buckets = Counter()
    nor_buckets = Counter()
    for res, d, *_ in reveal_days:
        rev_buckets.update(day_sales_hourbuckets(res, d))
    for res, d in normal_days:
        nor_buckets.update(day_sales_hourbuckets(res, d))

    # 2) Newly-revealed product(s) sales on their reveal day, vs that SAME product's
    #    sales on normal days (baseline "typical" rate for that product).
    per_product_reveal_units = defaultdict(list)   # product -> [units sold that reveal day]
    per_product_reveal_price = defaultdict(list)
    per_product_normal_units = defaultdict(list)   # product -> [units sold, one entry per normal day, any game]
    first_sale_hour = []                            # hours (int) or None
    stock_delta_reveal = defaultdict(list)          # product -> [stock_h23 - stock_h0] on its reveal day
    price_delta_reveal = defaultdict(list)          # product -> [price_h23 - price_h0] on its reveal day
    # other (non-new) products' units on the SAME reveal day, for intra-day contrast
    other_products_units_on_reveal_day = []

    for res, d, prods, shop in reveal_days:
        for p in prods:
            n, rv = day_sales_units_rev(res, d, item=p)
            per_product_reveal_units[p].append(n)
            if n:
                per_product_reveal_price[p].append(rv / n)
            sh0 = res['stock_h0'].get(d, {}).get(p)
            sh23 = res['stock_h23'].get(d, {}).get(p)
            if sh0 is not None and sh23 is not None:
                stock_delta_reveal[p].append(sh23 - sh0)
            ph0 = res['price_h0'].get(d, {}).get(p)
            ph23 = res['price_h23'].get(d, {}).get(p)
            if ph0 is not None and ph23 is not None:
                price_delta_reveal[p].append(ph23 - ph0)
            hrs = [hour for t, hour, s, o, it, price, inv in res['sales'].get(d, [])
                   if s == 'us' and o == 'SELL' and it == p]
            first_sale_hour.append(min(hrs) if hrs else None)
        all_prods = ['WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'EGG', 'MILK', 'WOOL']
        for p in all_prods:
            if p in prods:
                continue
            n, _ = day_sales_units_rev(res, d, item=p)
            other_products_units_on_reveal_day.append(n)

    for res, d in normal_days:
        for p in ('WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'EGG', 'MILK', 'WOOL'):
            n, _ = day_sales_units_rev(res, d, item=p)
            per_product_normal_units[p].append(n)

    # 3) Deliveries: during-day vs midnight dump, per product, REVEAL vs NORMAL
    def deliv_totals(day_list, key):
        tot = Counter()
        ndays = 0
        for entry in day_list:
            res, d = entry[0], entry[1]
            tot.update(res[key].get(d, {}))
            ndays += 1
        return tot, ndays

    rev_deliv_day, n_rev = deliv_totals(reveal_days, 'deliv_day')
    nor_deliv_day, n_nor = deliv_totals(normal_days, 'deliv_day')
    rev_deliv_mid, _ = deliv_totals(reveal_days, 'deliv_mid')
    nor_deliv_mid, _ = deliv_totals(normal_days, 'deliv_mid')

    # 4) Ops / hires / animals bought, REVEAL vs NORMAL (means per day)
    def ops_per_day(day_list, only_labels=None):
        rows = []
        for entry in day_list:
            res, d = entry[0], entry[1]
            c = res['ops'].get(d, {})
            if only_labels is None:
                rows.append(sum(c.values()))
            else:
                rows.append(sum(v for k, v in c.items() if any(k.startswith(l + '|') for l in only_labels)))
        return rows

    rev_ops_total = ops_per_day(reveal_days)
    nor_ops_total = ops_per_day(normal_days)
    rev_hires = [res['hires'].get(d, 0) for res, d, *_ in reveal_days]
    nor_hires = [res['hires'].get(d, 0) for res, d in normal_days]
    rev_animals = [sum(res['animals_bought'].get(d, {}).values()) for res, d, *_ in reveal_days]
    nor_animals = [sum(res['animals_bought'].get(d, {}).values()) for res, d in normal_days]

    per_op_rev = Counter()
    per_op_nor = Counter()
    for res, d, *_ in reveal_days:
        for k, v in res['ops'].get(d, {}).items():
            per_op_rev[k.split('|')[0]] += v
    for res, d in normal_days:
        for k, v in res['ops'].get(d, {}).items():
            per_op_nor[k.split('|')[0]] += v

    # 5) Post-reveal ramp: ops on the new product's source, days d, d+1, d+2 vs a
    #    per-game normal-day baseline rate for the same op-family.
    ramp_rows = []
    for res, d, prods, shop in reveal_days:
        srcs = {SRC_OF[p] for p in prods}
        normal_days_this_game = [dd for dd in days if dd not in res['reveal']]
        base_rate = 0.0
        if normal_days_this_game:
            base_total = 0
            for dd in normal_days_this_game:
                c = res['ops'].get(dd, {})
                base_total += sum(v for k, v in c.items() if k.split('|')[1] in srcs)
            base_rate = base_total / len(normal_days_this_game)
        window = [dd for dd in (d, d + 1, d + 2) if dd <= DAY1]
        win_total = 0
        for dd in window:
            c = res['ops'].get(dd, {})
            win_total += sum(v for k, v in c.items() if k.split('|')[1] in srcs)
        win_rate = win_total / len(window) if window else 0.0
        ramp_rows.append({'game': res['game'], 'day': d, 'products': prods, 'src': sorted(srcs),
                           'post_reveal_ops_per_day': win_rate, 'normal_ops_per_day_baseline': base_rate})

    # 6) Opponent sales, reveal vs normal (brief)
    opp_rev_units = [day_sales_units_rev(res, d, side='opp')[0] for res, d, *_ in reveal_days]
    opp_nor_units = [day_sales_units_rev(res, d, side='opp')[0] for res, d in normal_days]
    opp_rev_rev = [day_sales_units_rev(res, d, side='opp')[1] for res, d, *_ in reveal_days]
    opp_nor_rev = [day_sales_units_rev(res, d, side='opp')[1] for res, d in normal_days]

    def s(xs):
        xs = list(xs)
        return {'n': len(xs), 'mean': (mean(xs) if xs else None), 'sd': (pstdev(xs) if len(xs) > 1 else 0.0)}

    summary = {
        'n_games': len(all_res), 'window_days': [DAY0, DAY1],
        'n_reveal_days': len(reveal_days), 'n_normal_days': len(normal_days),
        'reveal_days_by_shop': dict(Counter(shop for *_, shop in [(r, d, p, sh) for r, d, p, sh in reveal_days])),
        'reveal_days_by_product': dict(Counter(p for _, _, prods, _ in reveal_days for p in prods)),
        'overall_sales_units_per_day_us': {'reveal': s(rev_units), 'normal': s(nor_units)},
        'overall_sales_revenue_per_day_us': {'reveal': s(rev_rev), 'normal': s(nor_rev)},
        'overall_avg_sale_price_us': {'reveal': s(rev_price), 'normal': s(nor_price)},
        'hour_bucket_share_us': {
            'reveal': {k: rev_buckets[k] for k in ('h0', 'h1', 'h2_11', 'h12_23')},
            'normal': {k: nor_buckets[k] for k in ('h0', 'h1', 'h2_11', 'h12_23')},
        },
        'new_product_sales_on_reveal_day': {
            p: {'units': s(v), 'avg_price': s(per_product_reveal_price[p]),
                'normal_day_baseline_units': s(per_product_normal_units[p]),
                'stock_delta_h0_to_h23': s(stock_delta_reveal[p]),
                'price_delta_h0_to_h23': s(price_delta_reveal[p])}
            for p, v in per_product_reveal_units.items()
        },
        'other_products_units_on_reveal_day': s(other_products_units_on_reveal_day),
        'first_sale_hour_of_new_product_on_reveal_day': {
            'n_reveal_product_slots': len(first_sale_hour),
            'n_sold_same_day': sum(1 for x in first_sale_hour if x is not None),
            'mean_hour_if_sold': (mean([x for x in first_sale_hour if x is not None])
                                  if any(x is not None for x in first_sale_hour) else None),
        },
        'deliveries_during_day_us': {'reveal': {'per_day_games': n_rev, 'totals': dict(rev_deliv_day)},
                                      'normal': {'per_day_games': n_nor, 'totals': dict(nor_deliv_day)}},
        'deliveries_midnight_dump_us': {'reveal': dict(rev_deliv_mid), 'normal': dict(nor_deliv_mid)},
        'ops_total_per_day_us': {'reveal': s(rev_ops_total), 'normal': s(nor_ops_total)},
        'ops_by_type_totals_us': {'reveal': dict(per_op_rev), 'normal': dict(per_op_nor)},
        'hires_per_day_us': {'reveal': s(rev_hires), 'normal': s(nor_hires)},
        'animals_bought_per_day_us': {'reveal': s(rev_animals), 'normal': s(nor_animals)},
        'post_reveal_ramp_rows': ramp_rows,
        'post_reveal_ramp_summary': {
            'mean_post_reveal_ops_per_day': mean(r['post_reveal_ops_per_day'] for r in ramp_rows) if ramp_rows else None,
            'mean_normal_baseline_ops_per_day': mean(r['normal_ops_per_day_baseline'] for r in ramp_rows) if ramp_rows else None,
        },
        'opponent_sales_units_per_day': {'reveal': s(opp_rev_units), 'normal': s(opp_nor_units)},
        'opponent_sales_revenue_per_day': {'reveal': s(opp_rev_rev), 'normal': s(opp_nor_rev)},
    }
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--limit', type=int, default=None)
    ap.add_argument('--out', default=str(OUT_DEFAULT))
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    per_game_dir = out_dir / 'per_game'

    specs = [g.strip() for g in PANEL.read_text(encoding='utf-8').strip().split(',') if g.strip()]
    if args.limit:
        specs = specs[:args.limit]
    print(f'{len(specs)} games to replay, workers={args.workers}')

    if args.workers <= 1:
        results = [analyze_game(spec) for spec in specs]
    else:
        with mp.Pool(args.workers) as pool:
            results = pool.map(analyze_game, specs)

    for res in results:
        dump_game(res, per_game_dir)

    summary = aggregate(results)
    (out_dir / 'summary.json').write_text(json.dumps(summary, indent=1, default=str), encoding='utf-8')
    print('wrote', out_dir / 'summary.json')
    print(json.dumps(summary, indent=1, default=str)[:4000])


if __name__ == '__main__':
    main()
