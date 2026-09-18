"""Per-3-day-segment behaviour and adaptation tests for the top two leaderboard teams.

Consumes the artifacts written by analyze_leader_segments.py (52 exactly replayed public episodes)
and segment_profile_ours.py (8 live games of our uploaded agent), and regenerates every number
quoted in docs/leader_segments.md.

Segments are the engine's shop cadence: 3 days = 72 steps; a shop unlocks at the start of days
3,6,...,24 (8 instances), so segment 0 opens with no shop and segment 9 gets no new shop.

Tests
  A  decision level: crop/animal quantity vs the shop demand present at a checkpoint (Spearman,
     permutation p). Cross-game, so shop-vs-price mediation is NOT separated.
  B  first-action-divergence between same-seat games of one submission. With a deterministic
     policy, an action difference must be caused by an observation difference; the components
     that differ identify what information was available. Also tests whether pairs sharing the
     first two shops stay identical longer (the V45-style day-6 route switch).
  C  opponent conditioning: partial (shop-controlled) rank correlation of own later planting with
     the opponent's visible board, plus the direct negative test of Test B pairs.
  D  within-game event study: does a NEWLY revealed shop change planting in the next two segments,
     after removing the segment-index (calendar) mean? Permutation test within segment index.
"""
from collections import Counter
import json, itertools, random, statistics as st
from market_corpus import ROOT

OUT = ROOT / 'results/fresh/leader_segments'
SEGMENTS = 10
W = 10  # digest width written by analyze_leader_segments.py
RNG_SEED = 20260917
GROUPS = {
    'Majkel1337/56216119': ('Majkel1337', 56216119),
    'MotherGoose/56266758': ('Unknown Mother-Goose', 56266758),
    'Majkel1337/56156662': ('Majkel1337', 56156662),
    'M&M&P&Q/56254996': ('M & M & P & Q', 56254996),
}
PRIMARY = ('Majkel1337/56216119', 'MotherGoose/56266758')
ITEMS = ['WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON', 'EGG', 'MILK', 'WOOL', 'FERTILIZER']
CROPS = ['WHEAT', 'STRAWBERRY', 'MELON', 'TOMATO', 'CARROT']
SHOP_DEMAND = {  # product -> shops that consume it; single-product shops consume 2x
    'WHEAT': {'BAKERY': 1, 'PIZZA_SHOP': 1, 'BRUNCH_SPOT': 1, 'ICE_CREAM_SHOP': 1, 'FARMERS_MARKET': 1},
    'EGG': {'BAKERY': 1, 'BRUNCH_SPOT': 1},
    'MILK': {'PIZZA_SHOP': 1, 'ICE_CREAM_SHOP': 1, 'SMOOTHIE_SHOP': 1},
    'WOOL': {'YARN_STORE': 2},
    'CARROT': {'PET_CAFE': 2, 'FARMERS_MARKET': 1},
    'TOMATO': {'PIZZA_SHOP': 1, 'FARMERS_MARKET': 1},
    'STRAWBERRY': {'BRUNCH_SPOT': 1, 'ICE_CREAM_SHOP': 1, 'SMOOTHIE_SHOP': 1, 'FARMERS_MARKET': 1},
}


# --------------------------------------------------------------------------- loading
def load_leaders():
    sample = json.loads((OUT / 'sample.json').read_text(encoding='utf-8'))
    subs = {e['id']: [a['sub'] for a in e['agents']] for e in sample['sample']}
    tags = {e['id']: e['tags'] for e in sample['sample']}
    scores = {v[1]: float(v[0]) for v in sample['scores'].values() if v[0]}
    games, digests = {}, {}
    for path in sorted(OUT.glob('segments-*.json')):
        game = json.loads(path.read_text(encoding='utf-8'))
        eid = game['episode']
        dig = json.loads((OUT / 'digests' / f'digests-{eid}.json').read_text(encoding='utf-8'))
        for seat_row in game['seats']:
            seat = seat_row['seat']
            key = (seat_row['team'], subs[eid][seat])
            row = dict(episode=eid, seat=seat, reward=seat_row['reward'], rewards=game['rewards'],
                       opp=game['teams'][1 - seat], opp_sub=subs[eid][1 - seat], tags=tags[eid],
                       shops=game['shops_by_segment'], segments=seat_row['segments'],
                       opp_segments=game['seats'][1 - seat]['segments'])
            games.setdefault(key, []).append(row)
            digests.setdefault(key, []).append(dict(
                episode=eid, seat=seat, opp=row['opp'], opp_sub=row['opp_sub'], shops=row['shops'],
                arr={k: [v[i * W:(i + 1) * W] for i in range(len(v) // W)] for k, v in dig['seats'][seat].items()}))
    return games, digests, scores


def load_ours():
    games, digests = [], []
    for path in sorted((OUT / 'ours').glob('segments-*.json')):
        game = json.loads(path.read_text(encoding='utf-8'))
        own = game['seats'][game['seat']]
        games.append(dict(episode=game['tag'], seat=game['seat'], reward=own['reward'], rewards=game['rewards'],
                          opp=game['opponent'], opp_sub=0, tags=['ours'], shops=game['shops_by_segment'],
                          segments=own['segments'], opp_segments=game['seats'][1 - game['seat']]['segments']))
    for path in sorted((OUT / 'ours').glob('digests-*.json')):
        dig = json.loads(path.read_text(encoding='utf-8'))
        seat = int(dig['tag'].split('-')[-1])
        digests.append(dict(episode=dig['tag'], seat=seat, opp='v45', opp_sub=0, shops=dig['shops_by_segment'],
                            arr={k: [v[i * W:(i + 1) * W] for i in range(len(v) // W)] for k, v in dig['seats'][seat].items()}))
    return games, digests


# --------------------------------------------------------------------------- helpers
def planted(game, crop, segs):
    return sum(game['segments'][s]['physical'].get('planted:' + crop, 0) for s in segs if s < SEGMENTS)


def units(game, key, segs=range(SEGMENTS)):
    return sum(game['segments'][s]['requests'].get('units:' + key, 0) for s in segs)


def ledger(game, field, item, segs=range(SEGMENTS)):
    return sum(game['segments'][s]['ledger'][field].get(item, 0) for s in segs)


def physical(game, key, segs=range(SEGMENTS)):
    return sum(game['segments'][s]['physical'].get(key, 0) for s in segs)


def demand(shops, product):
    weights = SHOP_DEMAND[product]
    return sum(weights.get(s, 0) for s in shops)


def shops_at(game, segment):
    return game['shops'].get(str(segment), [])


def new_shop(game, segment):
    prev, cur = shops_at(game, segment - 1), shops_at(game, segment)
    return cur[len(prev):][0] if len(cur) > len(prev) else None


def ranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return out


def spearman(x, y, rounds=4000, rng=None):
    rng = rng or random.Random(RNG_SEED)
    rx, ry = ranks(x), ranks(y)
    mx, my = st.mean(rx), st.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    rho = num / den if den else 0.0
    hits = 0
    for _ in range(rounds):
        shuffled = ry[:]
        rng.shuffle(shuffled)
        alt = sum((a - mx) * (b - my) for a, b in zip(rx, shuffled))
        if abs(alt) >= abs(num) - 1e-12:
            hits += 1
    return rho, (hits + 1) / (rounds + 1), len(x)


def residualise(x, z):
    """Rank-residualise x on z with a linear fit on ranks."""
    rx, rz = ranks(x), ranks(z)
    mx, mz = st.mean(rx), st.mean(rz)
    den = sum((a - mz) ** 2 for a in rz)
    slope = sum((a - mz) * (b - mx) for a, b in zip(rz, rx)) / den if den else 0.0
    return [b - mx - slope * (a - mz) for a, b in zip(rz, rx)]


def first_diff(a, b, key):
    x, y = a['arr'][key], b['arr'][key]
    for t in range(min(len(x), len(y))):
        if x[t] != y[t]:
            return t
    return None


def pairs(digests):
    return [(a, b) for a, b in itertools.combinations(digests, 2) if a['seat'] == b['seat']]


def stat(values):
    values = list(values)
    if not values:
        return None
    return dict(n=len(values), mean=round(st.mean(values), 2), median=st.median(values),
                lo=min(values), hi=max(values), constant=len(set(values)) == 1)


def cell(value):
    if value is None:
        return '-'
    if value['constant']:
        return f"{value['mean']:g}"
    return f"{value['mean']:g} [{value['lo']:g}-{value['hi']:g}]"


# --------------------------------------------------------------------------- sections
def segment_tables(name, games, out):
    print(f'\n## {name}: per-segment behaviour (n={len(games)} games)')
    blocks = [
        ('board at segment end', lambda g, s, k: (g['segments'][s]['board_end'] or {}).get(k, 0),
         ['WHEAT', 'STRAWBERRY', 'MELON', 'TOMATO', 'CARROT', 'COW', 'SHEEP', 'GOOSE', 'WEED', 'EMPTY', 'LOCKED']),
        ('planted during segment', lambda g, s, k: g['segments'][s]['physical'].get('planted:' + k, 0), CROPS),
        ('purchased units', lambda g, s, k: g['segments'][s]['requests'].get('units:' + k, 0),
         ['BUY_ANIMAL:COW', 'BUY_ANIMAL:SHEEP', 'BUY_ANIMAL:GOOSE', 'HIRE', 'BUY_PRODUCT:WHEAT',
          'BUY_PRODUCT:FERTILIZER', 'BUY_SEED:TOMATO', 'BUY_SEED:CARROT']),
        ('land spend', lambda g, s, k: g['segments'][s]['ledger']['spend'].get(k, 0), ['BUY_LAND', 'HIRE']),
        ('units sold', lambda g, s, k: g['segments'][s]['ledger']['sold_units'].get(k, 0), ITEMS),
        ('revenue', lambda g, s, k: g['segments'][s]['ledger']['revenue'].get(k, 0), ITEMS),
        ('work', lambda g, s, k: g['segments'][s]['physical'].get(k, 0),
         ['commands', 'moves', 'op:WATER', 'op:HARVEST', 'op:FERTILIZE', 'op:COLLECT_FERTILIZER', 'op:PASS', 'op:DIG']),
    ]
    rows = {}
    for title, fn, keys in blocks:
        print(f'\n### {title}')
        print('days  | ' + ' | '.join(keys))
        for s in range(SEGMENTS):
            values = {k: stat(fn(g, s, k) for g in games) for k in keys}
            rows.setdefault(str(s), {})[title] = values
            print(f'{s*3:2d}-{s*3+2:2d} | ' + ' | '.join(cell(values[k]) for k in keys))
    cash = [stat((g['segments'][s]['cash_end'] or 0) for g in games) for s in range(SEGMENTS)]
    print('\ncash at segment end: ' + ' | '.join(f"{c['mean']:.0f}" for c in cash))
    out[name] = dict(n_games=len(games), segments=rows, cash_end=[c['mean'] for c in cash],
                     final_cash_mean=round(st.mean(g['reward'] for g in games)),
                     wins=sum(1 for g in games if g['reward'] > g['rewards'][1 - g['seat']]))


def totals_table(sets, out):
    print('\n## Per-game totals (means)')
    print(f"{'set':24s} | " + ' | '.join(f'{i[:5]:>6s}' for i in ITEMS) + ' |   total')
    for name, games in sets.items():
        vals = [st.mean(ledger(g, 'revenue', i) for g in games) for i in ITEMS]
        print(f'{name:24s} | ' + ' | '.join(f'{v:6.0f}' for v in vals) + f' | {sum(vals):8.0f}')
        out.setdefault(name, {})['revenue'] = dict(zip(ITEMS, [round(v) for v in vals]))
    print('\nrealised price per sold unit (pooled revenue / pooled units)')
    print(f"{'set':24s} | " + ' | '.join(f'{i[:5]:>6s}' for i in ITEMS))
    for name, games in sets.items():
        row = []
        for i in ITEMS:
            rev = sum(ledger(g, 'revenue', i) for g in games)
            sold = sum(ledger(g, 'sold_units', i) for g in games)
            row.append(rev / sold if sold else float('nan'))
        print(f'{name:24s} | ' + ' | '.join(f'{v:6.0f}' for v in row))
        out[name]['price_per_unit'] = dict(zip(ITEMS, [round(v, 1) for v in row]))
    print('\nspending, work and outcome')
    keys = ['BUY_SEED:WHEAT', 'BUY_SEED:CARROT', 'BUY_SEED:TOMATO', 'BUY_SEED:STRAWBERRY', 'BUY_SEED:MELON',
            'BUY_PRODUCT:WHEAT', 'BUY_PRODUCT:FERTILIZER', 'BUY_ANIMAL:COW', 'BUY_ANIMAL:SHEEP',
            'BUY_ANIMAL:GOOSE', 'HIRE', 'BUY_LAND']
    work = ['commands', 'moves', 'op:WATER', 'op:PASS', 'op:HARVEST', 'fertilizer_applied',
            'produced:FERTILIZER', 'wheat_fed', 'produced:WHEAT']
    for name, games in sets.items():
        spend = {k: round(st.mean(ledger(g, 'spend', k) for g in games)) for k in keys}
        phys = {k: round(st.mean(physical(g, k) for g in games), 1) for k in work}
        extra = dict(hires=round(st.mean(units(g, 'HIRE') for g in games), 1),
                     fertilizer_sold=round(st.mean(ledger(g, 'sold_units', 'FERTILIZER') for g in games), 1),
                     final_cash=round(st.mean(g['reward'] for g in games)),
                     strawberries_planted=round(st.mean(planted(g, 'STRAWBERRY', range(SEGMENTS)) for g in games), 1),
                     strawberries_planted_day12plus=round(st.mean(planted(g, 'STRAWBERRY', range(4, SEGMENTS)) for g in games), 1),
                     tomatoes_planted=round(st.mean(planted(g, 'TOMATO', range(SEGMENTS)) for g in games), 1),
                     carrots_planted=round(st.mean(planted(g, 'CARROT', range(SEGMENTS)) for g in games), 1))
        out[name].update(spend=spend, work=phys, **extra)
        print(f'-- {name} (n={len(games)})  final cash {extra["final_cash"]}')
        print('     spend  ' + ' '.join(f'{k.split(":")[-1][:5]}={v}' for k, v in spend.items()))
        print('     work   ' + ' '.join(f'{k.split(":")[-1][:9]}={v}' for k, v in phys.items()))
        print('     other  ' + ' '.join(f'{k}={v}' for k, v in extra.items() if k != 'final_cash'))
    print('\nshare of season revenue realised per segment')
    print(f"{'set':24s} | " + ' | '.join(f'{s*3:2d}-{s*3+2:2d}' for s in range(SEGMENTS)))
    for name, games in sets.items():
        total = st.mean(sum(sum(g['segments'][s]['ledger']['revenue'].values()) for s in range(SEGMENTS)) for g in games)
        shares = [st.mean(sum(g['segments'][s]['ledger']['revenue'].values()) for g in games) / total for s in range(SEGMENTS)]
        out[name]['revenue_share_by_segment'] = [round(v, 4) for v in shares]
        print(f'{name:24s} | ' + ' | '.join(f'{v*100:4.1f}%' for v in shares))


def test_a(sets, out):
    print('\n## Test A: decision-level shop conditioning (Spearman rho, permutation p)')
    checks = [('tomatoes planted', lambda g: planted(g, 'TOMATO', range(SEGMENTS)), 'TOMATO', 4),
              ('carrots planted', lambda g: planted(g, 'CARROT', range(SEGMENTS)), 'CARROT', 4),
              ('carrots planted day 9+', lambda g: planted(g, 'CARROT', range(3, SEGMENTS)), 'CARROT', 3),
              ('strawberries planted', lambda g: planted(g, 'STRAWBERRY', range(SEGMENTS)), 'STRAWBERRY', 4),
              ('sheep bought', lambda g: units(g, 'BUY_ANIMAL:SHEEP'), 'WOOL', 4),
              ('cows bought', lambda g: units(g, 'BUY_ANIMAL:COW'), 'MILK', 4),
              ('geese bought', lambda g: units(g, 'BUY_ANIMAL:GOOSE'), 'EGG', 4),
              ('land spend', lambda g: ledger(g, 'spend', 'BUY_LAND'), 'TOMATO', 4)]
    for name, games in sets.items():
        print(f'-- {name} (n={len(games)})')
        rows = {}
        for label, fn, product, seg in checks:
            xs = [demand(shops_at(g, seg), product) for g in games]
            ys = [fn(g) for g in games]
            rho, p, n = spearman(xs, ys)
            rows[label] = dict(product=product, checkpoint_day=seg * 3, rho=round(rho, 3), p=round(p, 4), n=n,
                               y_min=min(ys), y_max=max(ys), x_min=min(xs), x_max=max(xs))
            print(f'     {label:24s} vs {product:10s} demand @day{seg*3:2d}: rho={rho:+.2f} p={p:.3f} '
                  f'(outcome {min(ys):g}-{max(ys):g}, demand {min(xs)}-{max(xs)})')
        out.setdefault(name, {})['test_a'] = rows


def test_b(digest_sets, out):
    print('\n## Test B: first action divergence between same-seat games of one submission')
    comps = ('own_tiles', 'private', 'shops', 'opp_farm', 'market', 'own_farm')
    for name, digests in digest_sets.items():
        pr = pairs(digests)
        if not pr:
            continue
        info = Counter()
        nondet = []
        ts = []
        for a, b in pr:
            t_act = first_diff(a, b, 'action')
            firsts = {c: first_diff(a, b, c) for c in comps}
            available = tuple(sorted(c for c, t in firsts.items()
                                     if t is not None and (t_act is None or t <= t_act)))
            ts.append(719 if t_act is None else t_act)
            if t_act is not None and not available:
                nondet.append((a['episode'], b['episode'], t_act))
            info[available or ('none',)] += 1
        agree = []
        for s in range(SEGMENTS):
            vals = []
            for t in range(s * 72, min((s + 1) * 72, 719)):
                same = tot = 0
                for a, b in pr:
                    if t < len(a['arr']['action']) and t < len(b['arr']['action']):
                        tot += 1
                        same += a['arr']['action'][t] == b['arr']['action'][t]
                if tot:
                    vals.append(same / tot)
            agree.append(round(st.mean(vals), 3) if vals else None)
        same_shops = [719 if first_diff(a, b, 'action') is None else first_diff(a, b, 'action')
                      for a, b in pr if tuple(a['shops'].get('2', [])[:2]) == tuple(b['shops'].get('2', [])[:2])]
        diff_shops = [719 if first_diff(a, b, 'action') is None else first_diff(a, b, 'action')
                      for a, b in pr if tuple(a['shops'].get('2', [])[:2]) != tuple(b['shops'].get('2', [])[:2])]
        print(f'-- {name}: {len(digests)} games, {len(pr)} same-seat pairs')
        print(f'     action-divergence step: min={min(ts)} median={int(st.median(ts))} max={max(ts)}')
        print(f'     pairs whose actions differ with NO observation difference (nondeterminism): {len(nondet)}')
        for x in nondet[:4]:
            print(f'        {x[0]} vs {x[1]} at step {x[2]} (day {x[2]//24} hour {x[2]%24})')
        print('     pairwise action agreement by segment: ' + ' '.join(f'{v:.2f}' if v is not None else '-' for v in agree))
        if same_shops:
            print(f'     pairs sharing first two shops: n={len(same_shops)} median t={int(st.median(same_shops))}; '
                  f'differing: n={len(diff_shops)} median t={int(st.median(diff_shops))}')
            print(f'     divergence inside the day-6 segment [144,168): '
                  f'same-shops {sum(1 for t in same_shops if 144 <= t < 168)}/{len(same_shops)}, '
                  f'diff-shops {sum(1 for t in diff_shops if 144 <= t < 168)}/{len(diff_shops)}')
        out.setdefault(name, {})['test_b'] = dict(
            n_games=len(digests), n_pairs=len(pr), t_min=min(ts), t_median=st.median(ts), t_max=max(ts),
            nondeterministic_pairs=len(nondet), nondeterministic_examples=nondet[:6],
            agreement_by_segment=agree,
            same_first_two_shops=dict(n=len(same_shops), median=st.median(same_shops) if same_shops else None,
                                      in_day6_segment=sum(1 for t in same_shops if 144 <= t < 168)),
            diff_first_two_shops=dict(n=len(diff_shops), median=st.median(diff_shops) if diff_shops else None,
                                      in_day6_segment=sum(1 for t in diff_shops if 144 <= t < 168)),
            info_available=[[list(k), v] for k, v in info.most_common()])


def test_b3(digest_sets, out, rounds=2000):
    print('\n## Test B3: permutation test of the day-6 first-two-shops switch')
    rng = random.Random(RNG_SEED)
    for name, digests in digest_sets.items():
        pr = pairs(digests)
        if len(digests) < 6:
            continue
        idx = {g['episode']: i for i, g in enumerate(digests)}
        cache = {}
        for a, b in pr:
            t = first_diff(a, b, 'action')
            cache[(idx[a['episode']], idx[b['episode']])] = 719 if t is None else t
        labels = [tuple(g['shops'].get('2', [])[:2]) for g in digests]
        seats = [g['seat'] for g in digests]

        def gap(assign):
            same = [t for (i, j), t in cache.items() if assign[i] == assign[j]]
            diff = [t for (i, j), t in cache.items() if assign[i] != assign[j]]
            if not same or not diff:
                return None
            return st.mean(same) - st.mean(diff), len(same), len(diff)
        observed = gap(labels)
        if observed is None:
            print(f'-- {name}: no pair shares the first two shops; test not applicable')
            out.setdefault(name, {})['test_b3'] = dict(applicable=False)
            continue
        hits = 0
        for _ in range(rounds):
            perm = labels[:]
            rng.shuffle(perm)
            alt = gap(perm)
            if alt and alt[0] >= observed[0]:
                hits += 1
        p = (hits + 1) / (rounds + 1)
        print(f'-- {name}: same-shop pairs diverge {observed[0]:+.0f} steps later '
              f'(n_same={observed[1]}, n_diff={observed[2]}), permutation p={p:.4f}')
        out.setdefault(name, {})['test_b3'] = dict(applicable=True, gap_steps=round(observed[0], 1),
                                                   n_same=observed[1], n_diff=observed[2], p=round(p, 4),
                                                   note='pairs share games, so the permutation shuffles shop labels over games')
        # the direct negative opponent test: pairs that share shops but face different opponents
        rows = []
        for a, b in pr:
            if tuple(a['shops'].get('2', [])[:2]) != tuple(b['shops'].get('2', [])[:2]):
                continue
            if a['opp_sub'] == b['opp_sub']:
                continue
            t = first_diff(a, b, 'action')
            rows.append(dict(pair=[a['episode'], b['episode']], seat=a['seat'], opponents=[a['opp'], b['opp']],
                             opp_first_diff=first_diff(a, b, 'opp_farm'), market_first_diff=first_diff(a, b, 'market'),
                             own_tiles_first_diff=first_diff(a, b, 'own_tiles'), shops_first_diff=first_diff(a, b, 'shops'),
                             action_first_diff=t))
        if rows:
            print(f'   same shops, different opponents: {len(rows)} pairs')
            for r in rows:
                print(f'      {r["pair"]} seat{r["seat"]} {r["opponents"]}: opponent farm differs from step '
                      f'{r["opp_first_diff"]}, market from {r["market_first_diff"]}, but actions identical '
                      f'until step {r["action_first_diff"]} (day {r["action_first_diff"]//24})')
        out[name]['same_shops_diff_opponent'] = rows


def test_c(sets, scores, out):
    print('\n## Test C: opponent conditioning (raw and shop-controlled rank correlation)')
    for name, games in sets.items():
        print(f'-- {name} (n={len(games)})')
        rows = {}
        for crop, seg in (('STRAWBERRY', 4), ('TOMATO', 4), ('CARROT', 4), ('TOMATO', 5), ('CARROT', 6)):
            own = [planted(g, crop, range(seg, SEGMENTS)) for g in games]
            opp = [(g['opp_segments'][seg]['board_start'] or {}).get(crop, 0) for g in games]
            shopd = [demand(shops_at(g, seg), crop) for g in games]
            raw, p_raw, _ = spearman(opp, own)
            part, p_part, n = spearman(residualise(opp, shopd), residualise(own, shopd))
            rows[f'{crop}@day{seg*3}'] = dict(raw_rho=round(raw, 3), raw_p=round(p_raw, 4),
                                              partial_rho=round(part, 3), partial_p=round(p_part, 4), n=n)
            print(f'     own {crop:10s} planted day{seg*3:2d}+ vs opponent {crop:10s} at day{seg*3:2d}: '
                  f'raw rho={raw:+.2f} (p={p_raw:.3f}) | shop-controlled rho={part:+.2f} (p={p_part:.3f})')
        strength = [(i, scores.get(g['opp'])) for i, g in enumerate(games) if scores.get(g['opp'])]
        if len(strength) >= 8:
            for label, fn in (('total plantings', lambda g: sum(planted(g, c, range(SEGMENTS)) for c in CROPS)),
                              ('hires', lambda g: units(g, 'HIRE')),
                              ('final cash', lambda g: g['reward'])):
                xs = [s for _, s in strength]
                ys = [fn(games[i]) for i, _ in strength]
                rho, p, n = spearman(xs, ys)
                rows[label + ' vs opponent rating'] = dict(rho=round(rho, 3), p=round(p, 4), n=n)
                print(f'     {label:24s} vs opponent leaderboard score: rho={rho:+.2f} p={p:.3f} n={n}')
        out.setdefault(name, {})['test_c'] = rows


def test_d(sets, out, horizon=2, rounds=4000):
    print(f'\n## Test D: within-game event study — a newly revealed shop and planting over the next '
          f'{horizon} segments (segment-index mean removed)')
    rng = random.Random(RNG_SEED)
    for crop in ('CARROT', 'TOMATO', 'STRAWBERRY', 'WHEAT'):
        print(f'-- crop {crop}')
        for name, games in sets.items():
            obs = []
            for g in games:
                for s in range(1, 9):
                    shop = new_shop(g, s)
                    if shop is None:
                        continue
                    obs.append((s, SHOP_DEMAND[crop].get(shop, 0) > 0, planted(g, crop, range(s, s + horizon))))
            if not obs:
                continue
            seg_mean = {s: st.mean([o[2] for o in obs if o[0] == s]) for s in {o[0] for o in obs}}
            resid = [(o[0], o[1], o[2] - seg_mean[o[0]]) for o in obs]
            treated = [r[2] for r in resid if r[1]]
            control = [r[2] for r in resid if not r[1]]
            if not treated or not control:
                print(f'     {name:24s} no variation')
                continue
            diff = st.mean(treated) - st.mean(control)
            by_seg = {}
            for r in resid:
                by_seg.setdefault(r[0], []).append(r)
            hits = 0
            for _ in range(rounds):
                tt, cc = [], []
                for rows in by_seg.values():
                    labels = [r[1] for r in rows]
                    rng.shuffle(labels)
                    for r, lab in zip(rows, labels):
                        (tt if lab else cc).append(r[2])
                alt = (st.mean(tt) - st.mean(cc)) if tt and cc else 0.0
                if abs(alt) >= abs(diff) - 1e-9:
                    hits += 1
            p = (hits + 1) / (rounds + 1)
            print(f'     {name:24s} treated n={len(treated):3d} resid={st.mean(treated):+6.2f} | '
                  f'control n={len(control):3d} resid={st.mean(control):+6.2f} | diff={diff:+6.2f} plants p={p:.4f}')
            out.setdefault(name, {}).setdefault('test_d', {})[crop] = dict(
                diff_plants=round(diff, 3), p=round(p, 4), n_treated=len(treated), n_control=len(control),
                horizon_segments=horizon)


def main():
    games, digests, scores = load_leaders()
    our_games, our_digests = load_ours()
    summary = {}
    primary = {name: games[GROUPS[name]] for name in PRIMARY}
    for name, rows in primary.items():
        segment_tables(name, rows, summary)
    segment_tables('OURS upload 56280048 (vs public V45)', our_games, summary)
    sets = dict(primary)
    sets['M&M&P&Q/56254996'] = games[GROUPS['M&M&P&Q/56254996']]
    sets['Majkel1337/56156662'] = games[GROUPS['Majkel1337/56156662']]
    sets['OURS upload (vs V45)'] = our_games
    totals_table(sets, summary)
    test_a(dict(list(sets.items())[:2] + [('OURS upload (vs V45)', our_games)]), summary)
    dsets = {name: digests[GROUPS[name]] for name in GROUPS}
    dsets['OURS upload (vs V45)'] = our_digests
    test_b(dsets, summary)
    test_b3(dsets, summary)
    test_c(dict(list(primary.items()) + [('OURS upload (vs V45)', our_games)]), scores, summary)
    test_d(dict(list(primary.items()) + [('OURS upload (vs V45)', our_games)]), summary)
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=1, default=str), encoding='utf-8')
    print('\nwrote', OUT / 'summary.json')


if __name__ == '__main__':
    main()
