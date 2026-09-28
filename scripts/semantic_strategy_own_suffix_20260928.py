"""Unused own-farm suffix accounting; no policy selection or engine invocation.

The forecast includes TODAY. Output is dated by the supplied legacy model:
animal/ongoing output at dawn, annual output at its modeled harvest day.
Today's release/retirement/establishment actions then update occupancy. A new
animal feeds today; a retiring animal stays occupied through retirement+1.
This module never reads a rival farm, future observations or future prices.
"""
from collections import Counter
from copy import deepcopy

from semantic_strategy_fertilizer_net_20260928 import crop_input_calendar


def _count(value):
    if isinstance(value, bool) or int(value) != value or value < 0:
        raise ValueError('counts_must_be_nonnegative_integers')
    return int(value)


def _counts(value, allowed):
    result = {}
    for species, count in (value or {}).items():
        if species not in allowed:
            raise ValueError('unknown_species:' + str(species))
        if _count(count):
            result[species] = int(count)
    return result


def _birth(cohort):
    return int(cohort.get('birth', cohort.get('planted_day', cohort.get('placed_day', 0))))


def _retire(nodes, species, count, day, events, reason):
    """The legacy anonymous suffix assigns intent to oldest active cohorts."""
    eligible = sorted((n for n in nodes if n['species'] == species
                       and n['birth'] <= day and 'retire_day' not in n),
                      key=lambda n: (n['birth'], n['id']))
    if count > sum(n['count'] for n in eligible):
        raise ValueError('retirement_exceeds_active_animals:' + species)
    remaining = count
    for node in eligible:
        if not remaining:
            break
        take = min(remaining, node['count']); remaining -= take
        if take < node['count']:
            retained = dict(node, count=node['count'] - take, id=node['id'] + ':retained')
            nodes.append(retained)
        node['count'] = take
        node['retire_day'] = day
        events.append(dict(day=day, kind=reason, species=species, count=take,
                           birth=node['birth'], exit_dawn=day + 2))


def own_suffix_calendar(state, forecast, config, crop_rules, animal_rules, output_calendar):
    """Project admitted own counts once; return expected flows and accounting.

    ``output_calendar`` is explicitly injected so no legacy production quirks
    are silently repaired here. Fertilizer inputs use the already reviewed
    helper. The returned signed flow is a production-minus-internal-use proxy,
    not verified transactions: delivery, cap loss and $1 sales are unmodeled.
    Missing later plan days mean no additional commitments, not repeated jobs.
    Conflicting retirements or unsupported explicit crop removal fail closed.
    """
    day = int(state['day'])
    if not 0 <= day <= 29:
        raise ValueError('outside_season')
    forecast = deepcopy(list(forecast))
    if not forecast or int(forecast[0]['day']) != day:
        raise ValueError('forecast_must_include_today_first')
    dates = [int(row['day']) for row in forecast]
    if dates != sorted(set(dates)) or any(d < day or d > 29 for d in dates):
        raise ValueError('forecast_days_must_be_unique_increasing')
    plan = {}
    for row in forecast:
        if any(row.get(k) for k in ('crop_remove_counts', 'crop_end_counts', 'crop_disappear_counts')):
            raise ValueError('explicit_crop_removal_not_supported')
        projected = dict(
            plant_counts=_counts(row.get('plant_counts'), crop_rules),
            animal_add_counts=_counts(row.get('animal_add_counts'), animal_rules),
            animal_retire_counts=_counts(row.get('animal_retire_counts'), animal_rules),
            build_counts=_counts(row.get('build_counts'), ('COOP', 'PASTURE')),
            remove_structure_counts=_counts(row.get('remove_structure_counts'), ('COOP', 'PASTURE')))
        if 'target_land_count' in row:
            projected['target_land_count'] = int(row['target_land_count'])
        plan[int(row['day'])] = projected
    gross = {d: Counter() for d in range(day, 30)}
    fertilizer = {d: 0. for d in gross}
    crops = []; animals = []; events = []; warnings = []
    initial_seen = set()

    def add_crop(cohort, start, observed):
        species = cohort['crop']; birth = _birth(cohort); count = _count(cohort.get('count', 1))
        if species not in crop_rules or birth > start:
            raise ValueError('invalid_crop_cohort')
        if not count:
            return
        cohort = deepcopy(cohort)
        cohort.update(crop=species, birth=birth, count=count)
        # Planned new cohorts receive no observed predecessor metadata.
        if not observed:
            cohort = dict(crop=species, birth=birth, count=count)
        output = output_calendar([cohort], [], start, release_age=config['release_age'])
        details = state.get('own_fertilizer_crop_details') if observed else None
        inputs, audit = crop_input_calendar([cohort], start, config['release_age'], crop_rules, details)
        release = max(start, birth + config['release_age'][species])
        ready = count
        if (not crop_rules[species]['interval'] and release == start
                and birth + config['release_age'][species] == start
                and cohort.get('observation_day') == start and 'ready_count' in cohort):
            ready = min(count, _count(cohort['ready_count']))
        releases = {release: ready}
        if ready < count:
            releases[min(29, release + 1)] = releases.get(min(29, release + 1), 0) + count - ready
        releases = {d: n for d, n in releases.items() if n}
        node = dict(id='crop:' + str(len(crops)), crop=species, birth=birth, count=count,
                    start_day=start, observed=observed, releases=releases,
                    output={d: dict(v) for d, v in output.items() if any(v.values())},
                    fertilizer_inputs={d: n for d, n in inputs.items() if n}, fertilizer_audit=audit)
        crops.append(node)
        if ready < count and start < 29:
            deferred = dict(cohort, count=count - ready)
            recomputed = output_calendar([deferred], [], start + 1, release_age=config['release_age'])
            preserved = float(output.get(start + 1, {}).get(species, 0))
            legacy = float(recomputed.get(start + 1, {}).get(species, 0))
            if preserved != legacy:
                warnings.append(dict(kind='origin_dated_receipt_differs_from_legacy_next_day_recomputation',
                    cohort=node['id'], day=start + 1, preserved_units=preserved, legacy_recomputed_units=legacy))
        for d, values in output.items():
            gross[d].update(values)
            if any(values.values()) and d > max(releases):
                warnings.append(dict(kind='legacy_output_after_modeled_release', cohort=node['id'], day=d))
        for d, n in inputs.items():
            fertilizer[d] += n
            if n and d > max(releases):
                warnings.append(dict(kind='legacy_input_after_modeled_release', cohort=node['id'], day=d))
        if observed and birth + config['release_age'][species] < start:
            warnings.append(dict(kind='overdue_observed_crop_uses_legacy_output_and_release', cohort=node['id']))

    for c in state.get('own_crop_cohorts', []):
        key = (c['crop'], _birth(c))
        if key in initial_seen:
            raise ValueError('aggregate_duplicate_initial_crop_births_before_projection')
        initial_seen.add(key); add_crop(c, day, True)
    for c in state.get('own_animal_cohorts', []):
        species = c['species']; birth = _birth(c); count = _count(c.get('count', 1))
        if species not in animal_rules or birth > day:
            raise ValueError('invalid_animal_cohort')
        node = dict(id='animal:' + str(len(animals)), species=species, birth=birth,
                    count=count, start_day=day, observed=True)
        if 'retire_day' in c:
            retire = int(c['retire_day'])
            if retire > day or retire + 2 <= day:
                raise ValueError('initial_retirement_must_describe_still_occupied_observed_animal')
            node['retire_day'] = retire
        if count:
            animals.append(node)
    committed = _counts(state.get('committed_retirement_counts'), animal_rules)
    marked = Counter()
    for node in animals:
        if 'retire_day' in node:
            marked[node['species']] += node['count']
    for species, count in committed.items():
        if count > marked[species]:
            _retire(animals, species, count - marked[species], day, events, 'initial_committed_intent')
            warnings.append(dict(kind='committed_exit_delay_unknown_assumed_two_nights', species=species))
    # Build the complete own timeline before evaluating animals. This supplies
    # only modeled future retirements, never actual future exits or observations.
    for d, row in plan.items():
        for species, count in row['animal_retire_counts'].items():
            _retire(animals, species, count, d, events, 'planned_retirement')
        for species, count in row['animal_add_counts'].items():
            animals.append(dict(id='animal:' + str(len(animals)), species=species, birth=d,
                                count=count, start_day=d, observed=False))
            events.append(dict(day=d, kind='animal_establishment', species=species, count=count))
        for species, count in row['plant_counts'].items():
            add_crop(dict(crop=species, birth=d, count=count), d, False)
            events.append(dict(day=d, kind='crop_establishment', species=species, count=count))
    for node in animals:
        output = output_calendar([], [node], node['start_day'], release_age=config['release_age'])
        node['output'] = {d: dict(v) for d, v in output.items() if any(v.values())}
        for d, values in output.items():
            gross[d].update(values)
            if 'retire_day' in node and d > node['retire_day'] and values.get('FERTILIZER', 0):
                warnings.append(dict(kind='legacy_fertilizer_after_retirement_intent', cohort=node['id'], day=d))
    stock = {p: max(0., float(state.get('stock', {}).get(p, 0))) for p in ('WHEAT', 'FERTILIZER')}
    initial_stock = dict(stock)
    structures = Counter(state.get('own_structures', {})); land = int(state.get('owned_quadrants', 1))
    daily = {}
    for d in range(day, 30):
        row = plan.get(d, {})
        occupied = Counter(); retiring = Counter(); feed = 0
        for n in animals:
            if n['start_day'] <= d < n.get('retire_day', 99) + 2:
                occupied[n['species']] += n['count']
                if n.get('retire_day', 99) <= d:
                    retiring[n['species']] += n['count']
                elif d < 29:
                    feed += n['count']
        crop_dawn = Counter(); crop_end = Counter(); released = Counter()
        for n in crops:
            if n['start_day'] > d:
                continue
            before = sum(count for end, count in n['releases'].items() if end >= d)
            after = sum(count for end, count in n['releases'].items() if end > d)
            if n['observed'] or n['birth'] < d:
                crop_dawn[n['crop']] += before
            crop_end[n['crop']] += after
            released[n['crop']] += n['releases'].get(d, 0)
        structures.update(row.get('build_counts', {})); structures.subtract(row.get('remove_structure_counts', {}))
        if any(n < 0 for n in structures.values()):
            raise ValueError('negative_structure_count')
        land = int(row.get('target_land_count', land))
        use = {'WHEAT': float(feed), 'FERTILIZER': fertilizer[d]}
        credit = {}; net = Counter(gross[d])
        for p, amount in use.items():
            credit[p] = min(stock[p], amount); stock[p] -= credit[p]
            net[p] -= amount - credit[p]
        needed_pens = Counter()
        for species, count in occupied.items():
            needed_pens[animal_rules[species]['structure']] += count
        capacity = sum(crop_end.values()) + sum(structures.values())
        if capacity > 25 * land:
            warnings.append(dict(kind='modeled_end_occupancy_exceeds_land', day=d, occupied=capacity, capacity=25 * land))
        if any(needed_pens[p] > structures[p] for p in needed_pens):
            warnings.append(dict(kind='modeled_animals_exceed_structures', day=d))
        daily[d] = dict(gross_output=dict(gross[d]), internal_use=use, initial_stock_credit=credit,
                        remaining_initial_stock=dict(stock), signed_net_flow=dict(net),
                        crop_dawn_counts=dict(crop_dawn), crop_end_counts=dict(crop_end),
                        crop_release_counts=dict(released), animal_occupied_counts=dict(occupied),
                        retiring_occupied_counts=dict(retiring), structures=dict(structures), land=land)
    return dict(day=day, last_explicit_plan_day=dates[-1], daily=daily,
                crop_cohorts=crops, animal_cohorts=animals, events=events, warnings=warnings,
                initial_stock=initial_stock, scope='OWN_ONLY_MODELED_SUFFIX_UNUSED_BY_RUNTIME',
                assumptions=[
                    'Forecast includes today; additions occur during that day and new animals feed that day.',
                    'Gross output dates and amounts are exactly the supplied legacy output model.',
                    'Current-dawn animal/ongoing output and held field inventory remain legacy approximations, not received or sold goods.',
                    'Observed annual readiness may defer part of today\'s harvest/release by one day.',
                    'Origin-dated deferred receipts are preserved once; legacy daily recomputation can omit them and is flagged.',
                    'Crop releases use configured ages; ongoing final modeled yield is not discarded.',
                    'Anonymous retirement selects oldest active birth; occupied through intent+1, exit dawn intent+2.',
                    'Initial intent without an observed delay conservatively occupies two further nights.',
                    'Initial own private stock offsets internal inputs once; no rival/private stock is read.',
                    'Signed net flow is production minus internal use, not exact delivery or market transactions.',
                    'Occupancy warnings require a future caller rejection/fallback rule before treating this suffix as feasible supply.',
                    'Legacy post-intent fertilizer output and absence of D29 feed are exposed, not repaired.',
                    'Cash, wages, cap loss, labor feasibility, future observations and $1 sale inventory rules are outside scope.'])
