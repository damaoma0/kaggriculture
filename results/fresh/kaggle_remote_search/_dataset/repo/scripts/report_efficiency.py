"""Is the leaders' edge labour and layout efficiency, or crop portfolio? An exact decomposition.

For each product c, season revenue is an identity of five factors:

    R_c = L * u * s_c * y_c * p_c
      L   unlocked tile-days (land)
      u   productive share of those tile-days (crop or occupied animal tiles; the rest is fallow
          ground, empty structures or weeds)                                    -> layout/utilisation
      s_c share of productive tile-days given to c's source (crop tiles, or the animal that makes it;
          fertilizer uses all animal tile-days)                                  -> portfolio
      y_c units of c sold per source tile-day                                    -> husbandry/yield
      p_c realised price per unit sold                                           -> price

A Shapley split over all 120 orderings attributes each product's revenue difference to the five
factors exactly; spend differences (labour, seeds, animals, land, product purchases) are added
directly. The components therefore reconcile to the difference in mean final cash.

Mapping to the two hypotheses:
  labour/layout ("saves manpower, better layout") -> hire spend, L, u, and y
  portfolio ("redeploys into scarce goods")      -> s, and the part of p that scarcity buys
Price is confounded by the opponent pool when comparing across pools, so it is reported alone and
the within-game comparison (a leader against its own opponents, same market) is shown as a control.
"""
import itertools, json, statistics as st
from collections import Counter
from market_corpus import ROOT

EFF = ROOT / 'results/fresh/efficiency'
SAMPLE = ROOT / 'results/fresh/leader_segments/sample.json'
PRODUCTS = ['WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON', 'EGG', 'MILK', 'WOOL', 'FERTILIZER']
SOURCE = {'WHEAT': ['crop:WHEAT'], 'CARROT': ['crop:CARROT'], 'TOMATO': ['crop:TOMATO'],
          'STRAWBERRY': ['crop:STRAWBERRY'], 'MELON': ['crop:MELON'], 'EGG': ['animal:GOOSE'],
          'MILK': ['animal:COW'], 'WOOL': ['animal:SHEEP'],
          'FERTILIZER': ['animal:GOOSE', 'animal:COW', 'animal:SHEEP']}
SPEND_GROUPS = {'labour (hire spend)': lambda k: k == 'HIRE',
                'land': lambda k: k == 'BUY_LAND',
                'seeds': lambda k: k.startswith('BUY_SEED'),
                'animals': lambda k: k.startswith('BUY_ANIMAL'),
                'wheat/fertilizer purchases': lambda k: k.startswith('BUY_PRODUCT')}
FACTORS = ['land', 'utilisation', 'portfolio', 'yield', 'price']


def load_groups():
    sample = json.loads(SAMPLE.read_text(encoding='utf-8'))
    subs = {e['id']: [a['sub'] for a in e['agents']] for e in sample['sample']}
    groups = {}
    for path in sorted((EFF / 'replays').glob('eff-*.json')):
        game = json.loads(path.read_text(encoding='utf-8'))
        eid = game['episode']
        for i, row in enumerate(game['seats']):
            key = (row['team'], subs[eid][i])
            other = (game['seats'][1 - i]['team'], subs[eid][1 - i])
            if key == ('Unknown Mother-Goose', 56266758):
                groups.setdefault('Mother-Goose', []).append(row)
                groups.setdefault("Mother-Goose's opponents", []).append(game['seats'][1 - i])
            if key == ('Majkel1337', 56216119):
                groups.setdefault('Majkel1337', []).append(row)
                groups.setdefault("Majkel's opponents", []).append(game['seats'][1 - i])
    for path in sorted((EFF / 'ours').glob('eff-*.json')):
        game = json.loads(path.read_text(encoding='utf-8'))
        mine = game['seats'][game['seat']]
        name = 'Ours, self-play' if game['opponent'] == 'self' else f"Ours vs {game['opponent']}"
        groups.setdefault(name, []).append(mine)
    return groups


def aggregate(rows):
    """Group means of every quantity the decomposition needs."""
    n = float(len(rows))
    hours = Counter()
    phys = Counter()
    revenue, sold, spend = Counter(), Counter(), Counter()
    for r in rows:
        hours.update(r['tile_hours'])
        phys.update(r['physical'])
        revenue.update(r['revenue'])
        sold.update(r['sold_units'])
        spend.update(r['spend'])
    days = {k: v / 24.0 / n for k, v in hours.items()}
    land = sum(days.values())
    productive = sum(v for k, v in days.items() if k.startswith('crop:') or k.startswith('animal:'))
    out = dict(n=len(rows), land=land, productive=productive,
               fallow=days.get('empty', 0.0) + days.get('structure_empty', 0.0), weed=days.get('weed', 0.0),
               tile_days=days, phys={k: v / n for k, v in phys.items()},
               revenue={k: v / n for k, v in revenue.items()}, sold={k: v / n for k, v in sold.items()},
               spend={k: v / n for k, v in spend.items()}, cash=st.mean(r['cash'] for r in rows))
    out['factors'] = {}
    for product in PRODUCTS:
        source = sum(days.get(s, 0.0) for s in SOURCE[product])
        units = out['sold'].get(product, 0.0)
        rev = out['revenue'].get(product, 0.0)
        out['factors'][product] = dict(
            land=land, utilisation=productive / land if land else 0.0,
            portfolio=source / productive if productive else 0.0,
            yield_=(units / source) if source else None, price=(rev / units) if units else None,
            revenue=rev, source_days=source, units=units)
    return out


def shapley(base, alt):
    """Exact Shapley attribution of alt-minus-base for a product of five factors."""
    names = list(base)
    contrib = {k: 0.0 for k in names}
    perms = list(itertools.permutations(names))
    for order in perms:
        current = dict(base)
        value = _prod(current)
        for k in order:
            current[k] = alt[k]
            new = _prod(current)
            contrib[k] += new - value
            value = new
    return {k: v / len(perms) for k, v in contrib.items()}


def _prod(values):
    out = 1.0
    for v in values.values():
        out *= v
    return out


def factor_vector(f, other):
    """Five-factor vector; a factor undefined on one side (nothing grown/sold) takes the other
    side's value, so the whole difference lands on the factor that actually differs."""
    y = f['yield_'] if f['yield_'] is not None else (other['yield_'] or 0.0)
    p = f['price'] if f['price'] is not None else (other['price'] or 0.0)
    return dict(land=f['land'], utilisation=f['utilisation'], portfolio=f['portfolio'], yield_=y, price=p)


def decompose(alt, base):
    by_factor = Counter()
    by_product = {}
    for product in PRODUCTS:
        fa, fb = alt['factors'][product], base['factors'][product]
        va, vb = factor_vector(fa, fb), factor_vector(fb, fa)
        parts = shapley(vb, va)
        # guard: the Shapley parts must reproduce the revenue difference of the aggregates
        assert abs(sum(parts.values()) - (fa['revenue'] - fb['revenue'])) < 1e-6 * max(1.0, abs(fa['revenue'])) + 1e-6
        by_product[product] = parts
        for k, v in parts.items():
            by_factor[k] += v
    spend = {}
    keys = set(alt['spend']) | set(base['spend'])
    for label, pick in SPEND_GROUPS.items():
        delta = sum(alt['spend'].get(k, 0.0) - base['spend'].get(k, 0.0) for k in keys if pick(k))
        spend[label] = -delta  # lower spend is a cash gain
    total = sum(by_factor.values()) + sum(spend.values())
    return by_factor, by_product, spend, total


def labour_table(groups):
    print('\n## 1. Labour')
    head = (f"{'group':28s} {'n':>3s} {'hire $':>7s} {'hand cmds':>9s} {'effective':>9s} {'moves':>6s} "
            f"{'PASS':>5s} {'no-effect':>9s} {'eff/100$':>8s} {'$/eff':>6s} {'moves/eff':>9s} {'idle %':>6s}")
    print(head)
    rows = {}
    for name, rows_ in groups.items():
        a = aggregate(rows_)
        p = a['phys']
        hire = a['spend'].get('HIRE', 0.0)
        eff = p.get('effective', 0.0)
        idle = (p.get('op:PASS', 0.0) + p.get('no_effect', 0.0)) / max(1.0, p.get('commands', 0.0))
        rows[name] = dict(hire_spend=hire, hand_commands=p.get('commands_hand', 0.0), effective=eff,
                          moves=p.get('moves', 0.0), passes=p.get('op:PASS', 0.0), no_effect=p.get('no_effect', 0.0),
                          effective_per_100_hire=100 * eff / hire if hire else None,
                          hire_per_effective=hire / eff if eff else None,
                          moves_per_effective=p.get('moves', 0.0) / eff if eff else None, idle_share=idle)
        print(f"{name:28s} {a['n']:3d} {hire:7.0f} {p.get('commands_hand', 0):9.0f} {eff:9.0f} "
              f"{p.get('moves', 0):6.0f} {p.get('op:PASS', 0):5.0f} {p.get('no_effect', 0):9.0f} "
              f"{rows[name]['effective_per_100_hire']:8.1f} {rows[name]['hire_per_effective']:6.2f} "
              f"{rows[name]['moves_per_effective']:9.2f} {100 * idle:6.1f}")
    return rows


def land_table(groups):
    print('\n## 2. Land and layout (tile-days over the season)')
    print(f"{'group':28s} {'unlocked':>9s} {'productive':>10s} {'util %':>6s} {'fallow':>7s} {'weed':>5s} | "
          f"crop tile-days: {'wheat':>6s} {'straw':>6s} {'melon':>6s} {'tomato':>6s} {'carrot':>6s} | "
          f"animal: {'cow':>5s} {'sheep':>5s} {'goose':>5s}")
    rows = {}
    for name, rows_ in groups.items():
        a = aggregate(rows_)
        d = a['tile_days']
        rows[name] = dict(unlocked=a['land'], productive=a['productive'], utilisation=a['productive'] / a['land'],
                          fallow=a['fallow'], weed=a['weed'], tile_days=d)
        print(f"{name:28s} {a['land']:9.0f} {a['productive']:10.0f} {100 * a['productive'] / a['land']:6.1f} "
              f"{a['fallow']:7.0f} {a['weed']:5.0f} | {'':15s} {d.get('crop:WHEAT', 0):6.0f} "
              f"{d.get('crop:STRAWBERRY', 0):6.0f} {d.get('crop:MELON', 0):6.0f} {d.get('crop:TOMATO', 0):6.0f} "
              f"{d.get('crop:CARROT', 0):6.0f} | {'':7s} {d.get('animal:COW', 0):5.0f} {d.get('animal:SHEEP', 0):5.0f} "
              f"{d.get('animal:GOOSE', 0):5.0f}")
    print('\n   units sold per source tile-day (yield)')
    print(f"{'group':28s} " + ' '.join(f'{p[:6]:>7s}' for p in PRODUCTS))
    for name, rows_ in groups.items():
        a = aggregate(rows_)
        vals = [a['factors'][p]['yield_'] for p in PRODUCTS]
        print(f"{name:28s} " + ' '.join(f"{v:7.3f}" if v is not None else f"{'-':>7s}" for v in vals))
    print('\n   realised price per unit')
    print(f"{'group':28s} " + ' '.join(f'{p[:6]:>7s}' for p in PRODUCTS))
    for name, rows_ in groups.items():
        a = aggregate(rows_)
        vals = [a['factors'][p]['price'] for p in PRODUCTS]
        print(f"{name:28s} " + ' '.join(f"{v:7.1f}" if v is not None else f"{'-':>7s}" for v in vals))
    return rows


def decomposition_table(groups, pairs):
    print('\n## 3. Decomposition of the mean final-cash gap (leader minus comparison)')
    results = {}
    for alt_name, base_name in pairs:
        if alt_name not in groups or base_name not in groups:
            continue
        alt, base = aggregate(groups[alt_name]), aggregate(groups[base_name])
        by_factor, by_product, spend, total = decompose(alt, base)
        gap = alt['cash'] - base['cash']
        print(f"\n### {alt_name} (n={alt['n']}) minus {base_name} (n={base['n']}): cash gap {gap:+,.0f} "
              f"(components sum to {total:+,.0f})")
        labels = {'land': 'land (unlocked tile-days)', 'utilisation': 'utilisation (fallow/weed share)',
                  'portfolio': 'portfolio (what the land grows)', 'yield_': 'yield per source tile-day',
                  'price': 'realised price'}
        for k in ('land', 'utilisation', 'portfolio', 'yield_', 'price'):
            print(f"   revenue via {labels[k]:36s} {by_factor[k]:+10,.0f}")
        for label, v in spend.items():
            print(f"   spend: {label:40s} {v:+10,.0f}")
        user = by_factor['utilisation'] + by_factor['land'] + by_factor['yield_'] + spend['labour (hire spend)']
        mine = by_factor['portfolio']
        print(f"   -> labour + layout + yield (user's hypothesis): {user:+,.0f} | portfolio (mine): {mine:+,.0f} | "
              f"price: {by_factor['price']:+,.0f} | other spend: "
              f"{sum(v for k, v in spend.items() if k != 'labour (hire spend)'):+,.0f}")
        print('   by product (portfolio / yield / price):',
              ', '.join(f"{p[:5]} {by_product[p]['portfolio']:+.0f}/{by_product[p]['yield_']:+.0f}/{by_product[p]['price']:+.0f}"
                        for p in PRODUCTS))
        results[f'{alt_name} - {base_name}'] = dict(
            cash_gap=gap, components_total=total, revenue_by_factor=dict(by_factor), spend=spend,
            by_product=by_product, user_hypothesis=user, portfolio=mine, price=by_factor['price'])
    return results


def main():
    groups = load_groups()
    order = ['Mother-Goose', 'Majkel1337', 'Ours, self-play', 'Ours vs twocoins',
             "Mother-Goose's opponents", "Majkel's opponents"]
    groups = {k: groups[k] for k in order if k in groups}
    summary = dict(groups={k: len(v) for k, v in groups.items()})
    summary['labour'] = labour_table(groups)
    summary['land'] = land_table(groups)
    summary['decomposition'] = decomposition_table(groups, [
        ('Mother-Goose', 'Ours, self-play'), ('Mother-Goose', 'Ours vs twocoins'),
        ('Majkel1337', 'Ours, self-play'), ('Mother-Goose', "Mother-Goose's opponents")])
    (EFF / 'summary.json').write_text(json.dumps(summary, indent=1, default=str), encoding='utf-8')
    print('\nwrote', EFF / 'summary.json')


if __name__ == '__main__':
    main()
