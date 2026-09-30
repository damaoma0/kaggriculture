"""Optional, bounded veto of unbought animals with negative public-state value.

This is an admission check, not a completion event: the block budget stays intact.
Forecasts are deliberately favorable to the extra animal (full care, no marginal
labor charge) and span nine declared demand/supply assumptions. They are not an
upper bound over all possible future worlds or rival actions.
"""
from collections import Counter
from copy import deepcopy

import semantic_strategy_policy_20260928 as P


DEFAULTS = dict(animal_market_gate=False, animal_market_start_day=12,
                animal_market_max_units=1, animal_market_loss_buffer=300.)


def scenario_margins(state, species, config, history=None):
    """Competitive receipts for one unbought animal, using current state only."""
    base, rival = P.forecast_market(state, config, history)
    own = P.output_calendar(state['own_crop_cohorts'], state['own_animal_cohorts'],
                            state['day'], release_age=config['release_age'])
    prior = Counter()
    for shop in P.SHOPS.values():
        for product, n in shop.items():
            prior[product] += n / len(P.SHOPS)
    day = state['day']; animal = P.ANIMALS[species]
    extra = {d: Counter() for d in range(day, 30)}
    for d in range(day, 30):
        age = d - day
        if age >= animal['first'] and (age - animal['first']) % animal['interval'] == 0:
            care_days = animal['first'] - 1 if age == animal['first'] else animal['interval']
            extra[d][animal['product']] = min(animal['held'], 1 + care_days)
        if age > 0:
            extra[d]['FERTILIZER'] = 1
    outcomes = []
    # This varies output of the observed rival farm, not its physical herd/feed.
    for supply_scale in (.5, 1., 1.5):
        for demand_scale in (.5, 1., 1.5):
            delta = Counter(); added = Counter(); value = -float(animal['cost'])
            for d in range(day, 30):
                missing = max(0, min(8, d // 3) - len(state['shops_prefix']))
                paths = {}
                for product in P.PRODUCTS:
                    delta[product] += (supply_scale - 1) * rival[d].get(product, 0)
                    if config['prior_future_shops']:
                        delta[product] -= 6 * missing * prior[product] * (demand_scale - 1)
                    paths[product] = base[d][product] + delta[product]
                for product, n in extra[d].items():
                    before = P.market_price(product, paths[product] + added[product], state['market_params'])
                    after = P.market_price(product, paths[product] + added[product] + n, state['market_params'])
                    value += n * (before + after) / 2
                    value += (before - after) * (supply_scale * rival[d].get(product, 0) - own[d].get(product, 0))
                    added[product] += n
                if d < 29:
                    value -= P.market_price('WHEAT', paths['WHEAT'], state['market_params'])
            outcomes.append(dict(rival_supply_scale=supply_scale,
                                 future_demand_scale=demand_scale, margin=value))
    return outcomes


def gate_unbought_animals(state, target, admitted, config, history=None):
    """Return a copied internal target plus diagnostics; never mutate a budget.

    The hard bounds (D12+, at most one unit) cannot be widened with configuration.
    A larger loss buffer or later start can make the gate more conservative.
    Already bought animals in either shed or hands always bypass this check.
    """
    cfg = dict(DEFAULTS); cfg.update(config or {})
    result = deepcopy(target)
    diag = dict(enabled=bool(cfg['animal_market_gate']), withheld={}, candidates={})
    if not diag['enabled']:
        diag['reason'] = 'disabled'; return result, diag
    if state['day'] < max(12, int(cfg['animal_market_start_day'])):
        diag['reason'] = 'before_start'; return result, diag
    cap = min(1, max(0, int(cfg['animal_market_max_units'])))
    threshold = -max(300., float(cfg['animal_market_loss_buffer']))
    diag.update(threshold=threshold, daily_unit_cap=cap,
                future_assumptions='observed shops fixed; unrevealed demand .5/1/1.5 prior; rival output .5/1/1.5',
                own_assumption='full care and delivery; zero incremental labor cost')
    eligible = []
    for species in P.ANIMALS:
        n = min(int(target.get('animal_add_counts', {}).get(species, 0)),
                int(admitted.get('animal_add_counts', {}).get(species, 0)))
        held = max(0, int(state.get('stock', {}).get(species, 0)))
        if n <= held:
            continue
        margins = scenario_margins(state, species, config, history)
        upper = max(row['margin'] for row in margins)
        diag['candidates'][species] = dict(admitted=n, held=held,
            best_scenario_margin=round(upper, 3), scenarios=[dict(row, margin=round(row['margin'], 3)) for row in margins])
        if upper < threshold:
            eligible.append((upper, species))
    for _, species in sorted(eligible)[:cap]:
        result['animal_add_counts'][species] -= 1
        if not result['animal_add_counts'][species]:
            del result['animal_add_counts'][species]
        result['end_animal_counts'][species] = max(0, result['end_animal_counts'][species] - 1)
        diag['withheld'][species] = 1
    diag['reason'] = 'negative_in_all_scenarios' if diag['withheld'] else 'no_confident_negative_unbought_unit'
    return result, diag
