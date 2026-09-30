"""Optional correction to the daily market approximation, not a runtime policy.

Supply remains in market inventory after its sale date. Its price effect on
existing own and rival sales must be compared with the unmodified baseline on
every subsequent day, including days with no new output from the added cohort.
This module preserves the existing physical, care, delivery and cost assumptions.
It does not model responsive rival production or incremental feed price impact.
"""
from collections import Counter

import semantic_strategy_policy_20260928 as P


def receipts(paths, extra, own, rival, params=None, persistent=True):
    """Competitive receipt change under the declared daily sale approximation.

    paths contains baseline inventory after that day's forecast flows. Added
    units sell at the mean of their starting/ending quotes. Existing sales are
    repriced at the ending quote in both arms. These are daily approximations,
    not exact engine transaction prices or a guarantee of future profit.
    """
    accum = Counter()
    total = 0.
    details = []
    products = sorted({p for row in extra.values() for p, n in row.items() if n})
    for day in sorted(paths):
        added_receipts = externality = 0.
        for product in products:
            n = extra.get(day, {}).get(product, 0)
            if not n and not (persistent and accum[product]):
                continue
            baseline = P.market_price(product, paths[day][product], params)
            before = P.market_price(product, paths[day][product]+accum[product], params)
            after = P.market_price(product, paths[day][product]+accum[product]+n, params)
            added_receipts += n * (before+after)/2
            reference = baseline if persistent else before
            externality += (reference-after) * (rival.get(day, {}).get(product, 0)
                                                - own.get(day, {}).get(product, 0))
            accum[product] += n
        total += added_receipts+externality
        details.append(dict(day=day, added_receipts=added_receipts,
                            existing_sales_margin=externality))
    return total, details


def _calendars(state, species, config):
    animal = species in P.ANIMALS
    crops = [] if animal else [dict(crop=species, birth=state['day'], count=1)]
    animals = [dict(species=species, birth=state['day'], count=1)] if animal else []
    extra = P.output_calendar(crops, animals, state['day'], release_age=config['release_age'])
    own = P.output_calendar(state['own_crop_cohorts'], state['own_animal_cohorts'],
                            state['day'], release_age=config['release_age'])
    return extra, own


def cohort_value(state, species, paths, rival, config):
    extra, own = _calendars(state, species, config)
    legacy = P.cohort_value(state, species, paths, rival, config)
    old, _ = receipts(paths, extra, own, rival, state['market_params'], persistent=False)
    corrected, _ = receipts(paths, extra, own, rival, state['market_params'])
    return legacy-old+corrected


def bundle_value(state, choice, paths, rival, config, unit_values):
    crops = [dict(crop=s, birth=state['day'], count=n) for s,n in choice['plant_counts'].items()]
    animals = [dict(species=s, birth=state['day'], count=n) for s,n in choice['animal_add_counts'].items()]
    extra = P.output_calendar(crops, animals, state['day'], release_age=config['release_age'])
    own = P.output_calendar(state['own_crop_cohorts'], state['own_animal_cohorts'],
                            state['day'], release_age=config['release_age'])
    joint, _ = receipts(paths, extra, own, rival, state['market_params'])
    independent = 0.
    linear = 0.
    for field in ('plant_counts', 'animal_add_counts'):
        for species, n in choice[field].items():
            one, _ = _calendars(state, species, config)
            value, _ = receipts(paths, one, own, rival, state['market_params'])
            independent += n*value
            linear += n*unit_values[species]
    return linear+joint-independent
