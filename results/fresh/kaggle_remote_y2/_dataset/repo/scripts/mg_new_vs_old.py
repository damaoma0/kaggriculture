"""Compare Mother-Goose's NEW submissions (56331731, 56331777; 42 games, data/leaders_20260919)
against her OLD submission (56266758; 30 games, data/leaders_20260917) to find behavioural
differences. ANALYSIS ONLY: reads replays, never simulates.

OLD side reuses the pre-extracted per-step events in results/fresh/mg_policy/events-<id>.json
(small files, ~234KB each -- these are NOT the 30MB raw replays, so loading all 30 at once is
fine). NEW side has no pre-extraction, so this script loads each of the 42 raw replays ONE AT A
TIME, extracts a compact per-episode summary (same event grammar as scripts/extract_mg_events.py,
plus tile yield/fertilize deltas, market prices at order time, and the opponent's own market
orders), and discards the raw replay before moving to the next one.

Output: results/fresh/mg_new/behaviour.json
"""
import gc
import json
from collections import Counter, defaultdict
from pathlib import Path

from market_corpus import ROOT
from tape_vs_bench import mg_games

NEW_DIR = ROOT / 'data/leaders_20260919'
SAMPLE = ROOT / 'results/fresh/leader_segments/sample_20260919.json'
OLD_EVENTS = ROOT / 'results/fresh/mg_policy'
OUT_DIR = ROOT / 'results/fresh/mg_new'
MG_TEAM = 16730612
BOARD_OPS = ('PLANT', 'BUILD_COOP', 'BUILD_PASTURE', 'PLACE', 'DIG', 'HARVEST', 'FERTILIZE')
SALE_ITEMS = ('STRAWBERRY', 'TOMATO', 'MILK', 'WOOL', 'EGG', 'WHEAT')


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


def quadrant_of(x, y):
    return ('S' if y >= 5 else 'N') + ('E' if x >= 5 else 'W')


# --------------------------------------------------------------------------------------
# NEW side: full extraction from raw replays, one at a time
# --------------------------------------------------------------------------------------

def analyze_new_episode(path, her_seat, opp_seat, meta):
    replay = json.loads(path.read_text(encoding='utf-8'))
    steps = replay['steps']
    her_events = []
    opp_open = []   # opponent market orders on steps 0-1 (any op)
    opp_sales = []  # opponent SELL orders, all game
    days = []
    hands_by_day = {}       # hands roster size at start of day (always 0: hands are day contracts)
    hands_actual_by_day = {}  # hands roster size at the LAST hour of the day (actual hires that landed)
    stream = []  # per-step (her unit-ops tuple, her market-ops tuple), for conditioning checks

    for t in range(719):
        obs0 = steps[t][0]['observation']
        her_farm = obs0['farms'][her_seat]
        opp_farm = obs0['farms'][opp_seat]
        if t % 24 == 0:
            day = t // 24
            hands_by_day[day] = len(her_farm['hands'])
            days.append(dict(day=day, money=her_farm['money'], shops=list(obs0['town']['unlocked_shops']),
                              prices=dict(obs0['market']['prices']), quadrants=list(her_farm['unlocked_quadrants']),
                              board=[[tile_label(x) for x in row] for row in her_farm['tiles']]))
        if (t + 1) % 24 == 0:  # last hour of the day: hands is a per-day contract, reset at midnight
            hands_actual_by_day[t // 24] = len(her_farm['hands'])

        her_action = steps[t + 1][her_seat]['action'] or {}
        opp_action = steps[t + 1][opp_seat]['action'] or {}

        units = [('farmer', her_action.get('farmer'))] + \
                [(f'hand{i + 1}', a) for i, a in enumerate(her_action.get('hands') or [])]
        positions = [her_farm['farmer']] + list(her_farm['hands'])
        unit_ops = []
        for idx, (who, unit) in enumerate(units):
            if not isinstance(unit, list) or not unit or unit[0] not in BOARD_OPS:
                continue
            if idx >= len(positions):
                continue
            x, y = positions[idx]
            tile_before = her_farm['tiles'][y][x]
            rec = dict(step=t, day=t // 24, hour=t % 24, unit=who, op=unit[0],
                       arg=unit[1:] or None, tile=[x, y], before=tile_label(tile_before))
            if unit[0] in ('HARVEST', 'FERTILIZE') and isinstance(tile_before, dict):
                rec['crop'] = tile_before.get('crop')
                rec['planted_day'] = tile_before.get('planted_day')
                rec['yield_before'] = tile_before.get('yield_units')
                rec['fert_until_before'] = tile_before.get('fertilized_until_day')
            her_events.append(rec)
            unit_ops.append((who, unit[0], tuple(unit[1:]), x, y))

        # SELL "qty" in the action is a REQUEST, not a confirmed fill -- she frequently requests
        # selling items she has zero of in the shed (verified against private.shed below). Track
        # shed depletion sequentially within the hour to recover the actually-fulfilled quantity.
        shed_remaining = dict(steps[t][her_seat]['observation']['private']['shed'])
        mkt_ops = []
        for order in her_action.get('market') or []:
            if isinstance(order, list) and order and isinstance(order[0], str):
                item = order[1] if len(order) > 1 and isinstance(order[1], str) else None
                qty = int(order[2]) if len(order) > 2 else 1
                price = obs0['market']['prices'].get(item) if item else None
                filled = qty
                if order[0] == 'SELL' and item is not None:
                    available = shed_remaining.get(item, 0)
                    filled = max(0, min(qty, available))
                    shed_remaining[item] = available - filled
                her_events.append(dict(step=t, day=t // 24, hour=t % 24, kind='market', op=order[0],
                                        item=item, qty=qty, filled=filled, money=her_farm['money'], price=price))
                mkt_ops.append((order[0], item, qty))
        stream.append((tuple(unit_ops), tuple(mkt_ops)))

        for order in opp_action.get('market') or []:
            if isinstance(order, list) and order and isinstance(order[0], str):
                item = order[1] if len(order) > 1 and isinstance(order[1], str) else None
                qty = int(order[2]) if len(order) > 2 else 1
                price = obs0['market']['prices'].get(item) if item else None
                rec = dict(step=t, day=t // 24, hour=t % 24, op=order[0], item=item, qty=qty, price=price)
                if t <= 1:
                    opp_open.append(rec)
                if order[0] == 'SELL':
                    opp_sales.append(rec)

    final_her = steps[719][0]['observation']['farms'][her_seat]
    summary = summarize_new(meta, her_events, opp_open, opp_sales, days, hands_by_day, hands_actual_by_day, final_her)
    summary['_stream'] = stream  # kept in-memory only; stripped before writing full JSON
    del replay
    gc.collect()
    return summary


def bucket_plant_days(events):
    plants = [e for e in events if e.get('kind') != 'market' and e['op'] == 'PLANT']
    counts = Counter()
    first_day = {}
    by_day_crop = Counter()
    tiles_by_crop = defaultdict(list)
    for p in plants:
        crop = p['arg'][0] if p.get('arg') else None
        counts[crop] += 1
        d = p['day']
        first_day[crop] = min(first_day.get(crop, 999), d)
        by_day_crop[(crop, d)] += 1
        tiles_by_crop[crop].append(tuple(p['tile']))
    return counts, first_day, by_day_crop, tiles_by_crop


def summarize_new(meta, events, opp_open, opp_sales, days, hands_by_day, hands_actual_by_day, final_her):
    mkt = [e for e in events if e.get('kind') == 'market']
    units = [e for e in events if e.get('kind') != 'market']

    turn = {t: [(e['op'], e['item'], e['qty']) for e in mkt if e['step'] == t] for t in (0, 1, 2)}
    day_money = {d['day']: d['money'] for d in days}
    final_shops = days[-1]['shops'] if days else []

    hires_per_day = Counter(e['day'] for e in mkt if e['op'] == 'HIRE')
    land_days_requested = sorted(e['day'] for e in mkt if e['op'] == 'BUY_LAND')
    # BUY_LAND requests can fail (like HIRE) -- the actual unlock sequence is read off the
    # unlocked_quadrants snapshots, which take effect the day after a successful purchase.
    quad_by_day = {d['day']: tuple(d['quadrants']) for d in days}
    quad_days = sorted(quad_by_day)
    land_days = []
    prev_n = None
    for dd in quad_days:
        n = len(quad_by_day[dd])
        if prev_n is not None and n > prev_n:
            land_days.append(dd)
        prev_n = n
    final_quadrants = quad_by_day[quad_days[-1]] if quad_days else ()
    animal_purchases = [dict(day=e['day'], step=e['step'], item=e['item'], qty=e['qty'])
                         for e in mkt if e['op'] == 'BUY_ANIMAL']

    plant_counts, first_plant_day, by_day_crop, tiles_by_crop = bucket_plant_days(units)

    tomato_quads = Counter(quadrant_of(x, y) for x, y in tiles_by_crop.get('TOMATO', []))

    # day 11-13 reallocation onto freed melon land: was this tile MELON within the 3 days
    # before it was replanted to strawberry/tomato? (melon self-clears on harvest, no DIG needed,
    # so this is checked against the day-boundary board snapshots rather than DIG events)
    board_by_day = {d['day']: d['board'] for d in days if 'board' in d}
    realloc_1113 = [e for e in units if e['op'] == 'PLANT' and e.get('arg') in (['STRAWBERRY'], ['TOMATO'])
                     and e['day'] in (11, 12, 13)]
    def cell(dd, x, y):
        b = board_by_day.get(dd)
        if not b or y >= len(b) or x >= len(b[y]):
            return None
        return b[y][x]

    realloc_on_melon = 0
    for e in realloc_1113:
        x, y = e['tile']
        d = e['day']
        if any(cell(dd, x, y) == 'ME' for dd in range(max(0, d - 3), d + 1)):
            realloc_on_melon += 1

    # yields: sum of yield_before at each HARVEST event, per crop (each harvest collects the
    # accumulated yield_units and resets it, so summing across a tile's harvests gives total units).
    # Grouped by (tile, planted_day) rather than tile alone, since wheat/melon/carrot tiles are dug
    # and replanted repeatedly through the season -- tile alone would conflate separate plantings.
    harvests = [e for e in units if e['op'] == 'HARVEST']
    yield_by_crop = defaultdict(list)
    for h in harvests:
        if h.get('crop') and h.get('yield_before') is not None:
            yield_by_crop[h['crop']].append(h['yield_before'])
    plant_instances = defaultdict(set)
    for h in harvests:
        if h.get('crop'):
            plant_instances[h['crop']].add((tuple(h['tile']), h.get('planted_day')))
    units_per_plant = {}
    for crop, instances in plant_instances.items():
        total = sum(yield_by_crop.get(crop, []))
        units_per_plant[crop] = total / len(instances) if instances else None

    # fertilize ages
    ferts = [e for e in units if e['op'] == 'FERTILIZE']
    fert_ages = defaultdict(list)
    for f in ferts:
        if f.get('crop') is not None and f.get('planted_day') is not None:
            fert_ages[f['crop']].append(f['day'] - f['planted_day'])
    fert_bought = sum(e['qty'] for e in mkt if e['op'] == 'BUY_PRODUCT' and e['item'] == 'FERTILIZER')
    fert_sold = sum(e['qty'] for e in mkt if e['op'] == 'SELL' and e['item'] == 'FERTILIZER')
    fert_applied = len(ferts)

    # sales -- 'filled' is the actually-fulfilled quantity (capped at that hour's shed stock);
    # 'qty' is what she requested, kept separately to quantify over-requesting.
    sales = {}
    for item in SALE_ITEMS:
        rows = [e for e in mkt if e['op'] == 'SELL' and e['item'] == item]
        units_requested = sum(r['qty'] for r in rows)
        units_sold = sum(r['filled'] for r in rows)
        revenue = sum((r['price'] or 0) * r['filled'] for r in rows)
        late = sum(r['filled'] for r in rows if r['day'] >= 27)
        hour_hist = Counter()
        for r in rows:
            if r['filled']:
                hour_hist[r['hour']] += r['filled']
        sales[item] = dict(units=units_sold, units_requested=units_requested, revenue=revenue,
                            avg_price=(revenue / units_sold) if units_sold else None,
                            late_share=(late / units_sold) if units_sold else None,
                            hour_hist=dict(hour_hist.most_common(6)))

    opp_sale_hours = defaultdict(Counter)
    for r in opp_sales:
        if r['item']:
            opp_sale_hours[r['item']][r['hour']] += 1
    opp_sale_hours = {k: dict(v.most_common(6)) for k, v in opp_sale_hours.items()}

    opp_wheat_open = [r for r in opp_open if r['item'] == 'WHEAT']

    return dict(
        episode=meta['id'], her_sub=meta['her_sub'], her_seat=meta['her_seat'], opp_seat=meta['opp_seat'],
        her_team=meta['her_team'], opp_team=meta['opp_team'], opp_sub=meta['opp_sub'],
        her_rating_initial=meta['her_rating_initial'], her_rating_updated=meta['her_rating_updated'],
        opp_rating_initial=meta['opp_rating_initial'],
        her_reward=meta['her_reward'], opp_reward=meta['opp_reward'],
        turn0=turn[0], turn1=turn[1], turn2=turn[2],
        day0_end_cash=day_money.get(1), day1_end_cash=day_money.get(2),
        hands_actual_day0=hands_actual_by_day.get(0), hands_actual_day1=hands_actual_by_day.get(1),
        hires_day0=hires_per_day.get(0, 0), hires_day1=hires_per_day.get(1, 0),
        opp_wheat_open=opp_wheat_open,
        hires_per_day=dict(sorted(hires_per_day.items())),
        hands_actual_per_day=dict(sorted(hands_actual_by_day.items())),
        land_days=land_days, land_days_requested=land_days_requested,
        final_quadrants=list(final_quadrants), n_quadrants=len(final_quadrants),
        animal_purchases=animal_purchases,
        plant_counts=dict(plant_counts), first_plant_day=first_plant_day,
        tomato_quadrants=dict(tomato_quads),
        realloc_1113_count=len(realloc_1113), realloc_on_melon_land=realloc_on_melon,
        units_per_plant=units_per_plant,
        fert_ages={k: (sum(v) / len(v), len(v)) for k, v in fert_ages.items()},
        fert_applied=fert_applied, fert_bought=fert_bought, fert_sold=fert_sold,
        sales=sales, opp_sale_hours=opp_sale_hours,
        final_shops=final_shops, first2_shops=final_shops[:2], first4_shops=final_shops[:4],
        final_money=final_her.get('money'),
    )


# --------------------------------------------------------------------------------------
# OLD side: from pre-extracted events-<id>.json (30 small files, loaded together is fine)
# --------------------------------------------------------------------------------------

def corrected_old_extra(path, eid, seat):
    """Re-derive OLD sale fulfilment, per-plant yield and fertilize ages straight from the raw
    replay: the pre-extracted events-*.json has 'before' as a 2-char tile label and money only at
    day boundaries, not the raw tile dict (yield_units, planted_day, fertilized_until_day) or
    per-step shed, so both corrections used for NEW (see analyze_new_episode) are redone here."""
    replay = json.loads(path.read_text(encoding='utf-8'))
    steps = replay['steps']
    sale_rows = {item: [] for item in SALE_ITEMS}
    harvests, ferts = [], []
    for t in range(719):
        her_farm = steps[t][0]['observation']['farms'][seat]
        her_action = steps[t + 1][seat]['action'] or {}
        units = [('farmer', her_action.get('farmer'))] + \
                [(f'hand{i + 1}', a) for i, a in enumerate(her_action.get('hands') or [])]
        positions = [her_farm['farmer']] + list(her_farm['hands'])
        for idx, (who, unit) in enumerate(units):
            if not isinstance(unit, list) or not unit or unit[0] not in ('HARVEST', 'FERTILIZE'):
                continue
            if idx >= len(positions):
                continue
            x, y = positions[idx]
            tile_before = her_farm['tiles'][y][x]
            if not isinstance(tile_before, dict):
                continue
            rec = dict(day=t // 24, tile=(x, y), crop=tile_before.get('crop'),
                       planted_day=tile_before.get('planted_day'), yield_before=tile_before.get('yield_units'))
            (harvests if unit[0] == 'HARVEST' else ferts).append(rec)

        orders = her_action.get('market') or []
        if orders:
            shed_remaining = dict(steps[t][seat]['observation']['private']['shed'])
            prices = steps[t][0]['observation']['market']['prices']
            for order in orders:
                if isinstance(order, list) and order and order[0] == 'SELL' and len(order) > 1 and order[1] in SALE_ITEMS:
                    item = order[1]
                    qty = int(order[2]) if len(order) > 2 else 1
                    available = shed_remaining.get(item, 0)
                    filled = max(0, min(qty, available))
                    shed_remaining[item] = available - filled
                    sale_rows[item].append(dict(day=t // 24, hour=t % 24, filled=filled, requested=qty,
                                                 price=prices.get(item)))
    sales = {}
    for item in SALE_ITEMS:
        rows = sale_rows[item]
        units_sold = sum(r['filled'] for r in rows)
        units_requested = sum(r['requested'] for r in rows)
        revenue = sum((r['price'] or 0) * r['filled'] for r in rows)
        late = sum(r['filled'] for r in rows if r['day'] >= 27)
        hour_hist = Counter()
        for r in rows:
            if r['filled']:
                hour_hist[r['hour']] += r['filled']
        sales[item] = dict(units=units_sold, units_requested=units_requested, revenue=revenue,
                            avg_price=(revenue / units_sold) if units_sold else None,
                            late_share=(late / units_sold) if units_sold else None,
                            hour_hist=dict(hour_hist.most_common(6)))

    yield_by_crop = defaultdict(list)
    for h in harvests:
        if h['crop'] and h['yield_before'] is not None:
            yield_by_crop[h['crop']].append(h['yield_before'])
    plant_instances = defaultdict(set)
    for h in harvests:
        if h['crop']:
            plant_instances[h['crop']].add((h['tile'], h['planted_day']))
    units_per_plant = {crop: (sum(yield_by_crop.get(crop, [])) / len(instances) if instances else None)
                        for crop, instances in plant_instances.items()}

    fert_ages = defaultdict(list)
    for f in ferts:
        if f['crop'] is not None and f['planted_day'] is not None:
            fert_ages[f['crop']].append(f['day'] - f['planted_day'])
    fert_ages = {k: (sum(v) / len(v), len(v)) for k, v in fert_ages.items()}

    del replay
    gc.collect()
    return dict(sales=sales, units_per_plant=units_per_plant, fert_ages=fert_ages, fert_applied=len(ferts))


def summarize_old(ev):
    mkt = [e for e in ev['events'] if e['kind'] == 'market']
    units = [e for e in ev['events'] if e['kind'] == 'unit']
    turn = {t: [(e['op'], e['item'], e['qty']) for e in mkt if e['step'] == t] for t in (0, 1, 2)}
    day_money = {d['day']: d['money'] for d in ev['days']}
    hires_per_day = Counter(e['step'] // 24 for e in mkt if e['op'] == 'HIRE')
    land_days_requested = sorted(e['step'] // 24 for e in mkt if e['op'] == 'BUY_LAND')
    quad_by_day = {d['day']: tuple(d['quadrants']) for d in ev['days']}
    quad_days = sorted(quad_by_day)
    land_days = []
    prev_n = None
    for dd in quad_days:
        n = len(quad_by_day[dd])
        if prev_n is not None and n > prev_n:
            land_days.append(dd)
        prev_n = n
    final_quadrants = quad_by_day[quad_days[-1]] if quad_days else ()
    animal_purchases = [dict(day=e['step'] // 24, step=e['step'], item=e['item'], qty=e['qty'])
                         for e in mkt if e['op'] == 'BUY_ANIMAL']
    plant_counts, first_plant_day, by_day_crop, tiles_by_crop = bucket_plant_days(
        [dict(e, day=e['step'] // 24) for e in units])
    tomato_quads = Counter(quadrant_of(x, y) for x, y in tiles_by_crop.get('TOMATO', []))
    board_by_day = {d['day']: d['board'] for d in ev['days']}

    def cell(dd, x, y):
        b = board_by_day.get(dd)
        if not b or y >= len(b) or x >= len(b[y]):
            return None
        return b[y][x]

    realloc = [dict(e, day=e['step'] // 24) for e in units if e['op'] == 'PLANT'
               and e.get('arg') in (['STRAWBERRY'], ['TOMATO']) and e['step'] // 24 in (11, 12, 13)]
    realloc_on_melon = 0
    for e in realloc:
        x, y = e['tile']
        d = e['day']
        if any(cell(dd, x, y) == 'ME' for dd in range(max(0, d - 3), d + 1)):
            realloc_on_melon += 1
    fert_bought = sum(e['qty'] for e in mkt if e['op'] == 'BUY_PRODUCT' and e['item'] == 'FERTILIZER')
    fert_sold = sum(e['qty'] for e in mkt if e['op'] == 'SELL' and e['item'] == 'FERTILIZER')
    fert_applied = sum(1 for e in units if e['op'] == 'FERTILIZE')
    sales = {}
    for item in SALE_ITEMS:
        rows = [e for e in mkt if e['op'] == 'SELL' and e['item'] == item]
        units_sold = sum(r['qty'] for r in rows)
        late = sum(r['qty'] for r in rows if r['step'] // 24 >= 27)
        hour_hist = Counter(r['step'] % 24 for r in rows)
        sales[item] = dict(units=units_sold, late_share=(late / units_sold) if units_sold else None,
                            hour_hist=dict(hour_hist.most_common(6)))
    return dict(
        episode=ev['episode'], teams=ev['teams'], seat=ev['seat'], rewards=ev['rewards'],
        turn0=turn[0], turn1=turn[1], turn2=turn[2],
        day0_end_cash=day_money.get(1), day1_end_cash=day_money.get(2),
        hires_per_day=dict(sorted(hires_per_day.items())),
        land_days=land_days, land_days_requested=land_days_requested,
        final_quadrants=list(final_quadrants), n_quadrants=len(final_quadrants),
        animal_purchases=animal_purchases,
        plant_counts=dict(plant_counts), first_plant_day=first_plant_day,
        tomato_quadrants=dict(tomato_quads),
        realloc_1113_count=len(realloc), realloc_on_melon_land=realloc_on_melon,
        fert_applied=fert_applied, fert_bought=fert_bought, fert_sold=fert_sold,
        sales=sales,
    )


# --------------------------------------------------------------------------------------
# Conditioning check: pairs of NEW games sharing first4 shops, different opponents
# --------------------------------------------------------------------------------------

def first_divergence(stream_a, stream_b):
    n = min(len(stream_a), len(stream_b))
    for t in range(n):
        if stream_a[t] != stream_b[t]:
            return t, stream_a[t], stream_b[t]
    return n, None, None


def conditioning_pairs(new_summaries, streams, key):
    groups = defaultdict(list)
    for s in new_summaries:
        groups[tuple(s[key])].append(s['episode'])
    pairs = []
    for shops, eids in groups.items():
        if len(eids) < 2:
            continue
        for i in range(len(eids)):
            for j in range(i + 1, len(eids)):
                a, b = eids[i], eids[j]
                sa = next(s for s in new_summaries if s['episode'] == a)
                sb = next(s for s in new_summaries if s['episode'] == b)
                step, act_a, act_b = first_divergence(streams[a], streams[b])
                pairs.append(dict(shops=list(shops), episode_a=a, episode_b=b,
                                   sub_a=sa['her_sub'], sub_b=sb['her_sub'],
                                   opp_a=sa['opp_team'], opp_b=sb['opp_team'],
                                   same_opponent=sa['opp_team'] == sb['opp_team'],
                                   divergence_step=step, divergence_day=step // 24,
                                   action_a=act_a, action_b=act_b))
    return pairs


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # OLD: base summary from the pre-extracted events-*.json, then overwrite 'sales' with a
    # corrected pass over the raw replay (needed for per-order shed-fulfilment tracking; see
    # corrected_old_sales).
    old_summaries = []
    for path in sorted(OLD_EVENTS.glob('events-*.json')):
        ev = json.loads(path.read_text(encoding='utf-8'))
        old_summaries.append(summarize_old(ev))
    print('old episodes (base):', len(old_summaries), flush=True)

    for i, (rpath, eid, seat) in enumerate(mg_games()):
        s = next((x for x in old_summaries if x['episode'] == eid), None)
        if s is None:
            continue
        extra = corrected_old_extra(Path(rpath), eid, seat)
        s['sales'] = extra['sales']
        s['units_per_plant'] = extra['units_per_plant']
        s['fert_ages'] = extra['fert_ages']
        s['fert_applied'] = extra['fert_applied']
        print(f'old sales/yield {i + 1}/30 episode {eid}', flush=True)

    # NEW
    sample = json.loads(SAMPLE.read_text(encoding='utf-8'))
    jobs = []
    for e in sample['sample']:
        agents = e['agents']
        her_idx = next((i for i, a in enumerate(agents) if a['team'] == MG_TEAM), None)
        if her_idx is None:
            continue
        opp_idx = 1 - her_idx
        meta = dict(id=e['id'], her_seat=her_idx, opp_seat=opp_idx,
                    her_sub=agents[her_idx]['sub'], her_team=agents[her_idx]['team'],
                    opp_sub=agents[opp_idx]['sub'], opp_team=agents[opp_idx]['team'],
                    her_rating_initial=agents[her_idx]['initial'], her_rating_updated=agents[her_idx]['updated'],
                    opp_rating_initial=agents[opp_idx]['initial'],
                    her_reward=agents[her_idx]['reward'], opp_reward=agents[opp_idx]['reward'])
        path = NEW_DIR / f'episode-{e["id"]}-replay.json'
        if not path.exists():
            print('MISSING replay for', e['id'], flush=True)
            continue
        jobs.append((path, meta))

    new_summaries = []
    streams = {}
    for i, (path, meta) in enumerate(jobs):
        s = analyze_new_episode(path, meta['her_seat'], meta['opp_seat'], meta)
        streams[s['episode']] = s.pop('_stream')
        new_summaries.append(s)
        print(f'new {i + 1}/{len(jobs)} episode {s["episode"]} sub {s["her_sub"]} '
              f'reward {s["her_reward"]} vs {s["opp_reward"]}', flush=True)

    pairs4 = conditioning_pairs(new_summaries, streams, 'first4_shops')
    pairs2 = conditioning_pairs(new_summaries, streams, 'first2_shops')
    print('conditioning pairs (first4):', len(pairs4), '(first2):', len(pairs2), flush=True)

    result = dict(old=old_summaries, new=new_summaries,
                   conditioning_pairs_first4=pairs4, conditioning_pairs_first2=pairs2)
    (OUT_DIR / 'behaviour.json').write_text(json.dumps(result, default=str), encoding='utf-8')
    print('wrote', OUT_DIR / 'behaviour.json', flush=True)


if __name__ == '__main__':
    main()
