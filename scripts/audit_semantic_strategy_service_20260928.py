"""Read saved games to diagnose funding, committed survival and feed use.

No simulation or policy calls. Requested market commands are kept distinct from
successful daily transactions; hourly private inventories are not in these logs.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import statistics

from audit_semantic_strategy_execution_20260928 import (
    ROOT, STUDY, audit_world, aggregate, flat, identity, label, diff, clean,
)
from semantic_tile_inputs_20260928 import load_executor

ANIMAL_RULES = {'COW': (400, 8, 2), 'SHEEP': (500, 6, 3), 'GOOSE': (300, 4, 1)}
CROP_FIRST = {'WHEAT': 2, 'CARROT': 2, 'MELON': 10, 'TOMATO': 8, 'STRAWBERRY': 10}
SEED_COST = {'WHEAT': 10, 'CARROT': 20, 'MELON': 80, 'TOMATO': 50, 'STRAWBERRY': 100}
PRICE_HELPER = None


def stocks(private):
    total = Counter(private.get('shed', {}))
    for inventory in private.get('inventories', []):
        total.update(inventory)
    return total


def dawn_liquidity(snapshot, plan):
    obs = snapshot['current_observation']
    private, farm = obs.get('private'), obs['own_farm']
    if private is None:
        return None
    inventory = obs['market']['inventory']
    lots = {}
    for product, quantity in private['shed'].items():
        if product not in inventory or product in ANIMAL_RULES or quantity <= 0:
            continue
        prices = [PRICE_HELPER._mkt_price(product, int(inventory[product]) + i) for i in range(quantity)]
        allowed = [price for price in prices if price > 5]
        lots[product] = dict(held=quantity, above_floor=len(allowed), walk_proceeds=sum(allowed),
                             lowest_walk_price=min(prices))
    held = stocks(private)
    realized = plan['realized_plan']
    land_count = len(farm['unlocked_quadrants'])
    land_cost = sum((1000, 2000, 4000)[i-1] for i in range(land_count, land_count+realized['land_add_count']))
    seed_cost = sum(max(0, n-private.get('seeds', {}).get(c, 0))*SEED_COST[c]
                    for c, n in realized['plant_counts'].items())
    animal_cost = sum(max(0, n-held.get(a, 0))*ANIMAL_RULES[a][0]
                      for a, n in realized['animal_add_counts'].items())
    a, b, hire_cost = 1, 1, 0
    for _ in range(realized['hands']):
        hire_cost += a
        a, b = b, a+b
    funding_lots = {p: v for p, v in lots.items() if p in ('WOOL', 'MILK', 'EGG', 'FERTILIZER')}
    funding = sum(v['walk_proceeds'] for v in funding_lots.values())
    return dict(shed=dict(private['shed']), carried=[dict(v) for v in private.get('inventories', [])],
        wheat_held=held.get('WHEAT', 0), funding_lots=funding_lots,
        current_cash=farm['money'], funding_walk_proceeds=funding,
        current_cash_plus_funding=farm['money']+funding,
        known_land_and_hire_cost=land_cost+hire_cost,
        known_land_hire_seed_animal_cost=land_cost+hire_cost+seed_cost+animal_cost,
        land_and_hires_fundable_at_dawn=farm['money']+funding >= land_cost+hire_cost,
        admitted_inputs_fundable_excluding_feed=farm['money']+funding >= land_cost+hire_cost+seed_cost+animal_cost,
        scope='Static dawn own-shed liquidation above the exact default price-curve floor5; no rival trades, future harvests, feed costs or pacing assumptions.')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hires_from_spend(spend):
    a, b, total = 1, 1, 0
    for n in range(25):
        if total == spend:
            return n
        total += a
        a, b = b, a + b
    raise AssertionError(('Unexpected default-engine daily wage bill', spend))


def service_world(path):
    path = path.resolve()
    game = json.loads(path.read_text(encoding='utf-8'))
    seat = game['case']['seat']
    actions_path = path.with_name(path.stem + '.actions.json')
    actions = json.loads(actions_path.read_text(encoding='utf-8'))[seat]
    snapshots = {s['day']: s for s in game['diagnostics'][seat]}
    mornings = {d: flat(s['current_observation']['own_farm']) for d, s in snapshots.items()}
    plans = {d['day']: d for snapshot in snapshots.values() for d in snapshot['diagnostics'] if d.get('phase') == 'semantic'}
    audit = audit_world(path)
    ledger = game['daily'][seat]
    retired = {(int(r['tile']), r['animal'], r['birth']): r['first_unfed_day'] for r in audit['retirements']}
    exits = {(r['exit_day'], r['tile']): r for r in audit['animal_exits']}
    purchased_stock = Counter()
    finance, service, young_crop_losses = [], [], []
    for day in range(29):
        added = Counter()
        for tile, after in enumerate(mornings[day + 1]):
            cohort = identity(after)
            if cohort and cohort[0] == 'animal' and cohort != identity(mornings[day][tile]):
                added[cohort[1]] += 1
        spend = diff(ledger[day + 1]['spend'], ledger[day]['spend'])
        sold = diff(ledger[day + 1]['sold_units'], ledger[day]['sold_units'])
        bought = {a: spend.get('BUY_ANIMAL:' + a, 0) / rules[0] for a, rules in ANIMAL_RULES.items()}
        purchased_stock.update(bought)
        purchased_stock.subtract(added)
        for animal in ANIMAL_RULES:
            purchased_stock[animal] -= sold.get(animal, 0)
        assert min(purchased_stock.values(), default=0) >= 0
        if day < 6:
            continue
        plan = plans[day]
        farm = snapshots[day]['current_observation']['own_farm']
        expected = plan['end_board']
        daily_actions = actions[24 * day:24 * (day + 1)]
        market_hours = defaultdict(list)
        for hour, action in enumerate(daily_actions):
            for order in (action.get('market') or [])[:10]:
                if order:
                    key = order[0] + (':' + str(order[1]) if len(order) > 1 else '')
                    market_hours[key].append(hour)
        unlock_hour = (plan.get('observed_land_unlock') or {}).get('hour')
        remaining_commands = Counter()
        if unlock_hour is not None:
            for action in daily_actions[unlock_hour:]:
                for command in [action.get('farmer')] + (action.get('hands') or []):
                    remaining_commands[command[0] if command else 'MISSING'] += 1
        physical = diff(ledger[day + 1]['physical'], ledger[day]['physical'])
        dawn = dawn_liquidity(snapshots[day], plan)
        before_private = snapshots[day]['current_observation'].get('private')
        after_private = snapshots[day + 1]['current_observation'].get('private')
        wheat_balance = None
        if before_private is not None and after_private is not None:
            before_stock, after_stock = stocks(before_private), stocks(after_private)
            feeds = physical.get('op:FEED', 0)-physical.get('no_effect:FEED', 0)
            harvest = physical.get('produced:WHEAT', 0)
            inferred = after_stock.get('WHEAT', 0)-before_stock.get('WHEAT', 0)+feeds+sold.get('WHEAT', 0)-harvest
            exact_balance = sum(after_private['shed'].values()) < 100
            if exact_balance:
                assert inferred >= 0, (path, day, inferred)
            wheat_balance = dict(start_stock=before_stock.get('WHEAT', 0), end_stock=after_stock.get('WHEAT', 0),
                successful_feeds=feeds, harvested=harvest, purchased_minimum=max(0, inferred),
                purchased_exact=exact_balance,
                caveat='When the next shed is full, unknown midnight overflow makes this a lower bound.')
        finance.append(dict(day=day, dawn_cash=farm['money'], end_cash=ledger[day + 1]['money'],
            planned_hires=plan['realized_plan']['hands'], successful_hires=hires_from_spend(spend.get('HIRE', 0)),
            planned_land=plan['realized_plan']['land_add_count'], land_spend=spend.get('BUY_LAND', 0),
            unlock_hour=unlock_hour, planned_capital=plan['proposal'].get('estimated_capital_cost'),
            buy_animal_counts=bought, placed_counts=clean(added), purchased_unplaced_stock=clean(purchased_stock),
            wheat_buy_spend=spend.get('BUY_PRODUCT:WHEAT', 0), wheat_sold=sold.get('WHEAT', 0),
            wheat_sale_revenue=ledger[day + 1]['revenue'].get('WHEAT', 0) - ledger[day]['revenue'].get('WHEAT', 0),
            seed_spend={k: v for k, v in spend.items() if k.startswith('BUY_SEED:')},
            market_request_hours={k: sorted(set(v)) for k, v in sorted(market_hours.items())},
            post_unlock_issued_commands=clean(remaining_commands), physical=physical,
            dawn_liquidity=dawn, wheat_balance=wheat_balance,
            software_errors=plan.get('executor_errors_cumulative'),
            software_last_error=plan.get('executor_last_error')))
        before, after = mornings[day], mornings[day + 1]
        # A survived animal's next-morning hunger precisely identifies feeding
        # on this day. Banking rules identify useful fed+care days as well.
        for tile, value in enumerate(after):
            cohort = identity(value)
            if not cohort or cohort[0] != 'animal':
                continue
            species, birth = cohort[1:]
            old = before[tile] if identity(before[tile]) == cohort else {}
            retiring = retired.get((tile, species, birth), 99) <= day
            committed = expected[tile] == label(value) and not retiring
            first, interval = ANIMAL_RULES[species][1:]
            production = day + 1 - birth - first >= 0 and (day + 1 - birth - first) % interval == 0
            fed = int(value['consecutive_unfed']) == 0
            old_bonus, new_bonus = old.get('pending_care_bonus', 0), value.get('pending_care_bonus', 0)
            care_bonus = new_bonus if production else new_bonus - old_bonus
            service.append(dict(day=day, tile=tile, animal=species, birth=birth,
                age=day-birth, committed=committed, retiring=retiring, fed=fed,
                productive_care=(fed and care_bonus > 0), production=production,
                lost_banked_bonus=(old_bonus if production and not fed else 0),
                newborn=(birth == day), yielded_next_morning=value.get('yield_units', 0)))
        for tile, value in enumerate(before):
            cohort = identity(value)
            if not cohort or identity(after[tile]) == cohort:
                continue
            if cohort[0] == 'animal':
                exit_row = exits[(day, tile)]
                exit_row['morning_unfed_days'] = value.get('consecutive_unfed', 0)
                exit_row['morning_banked_bonus'] = value.get('pending_care_bonus', 0)
                exit_row['retained_in_same_day_end_board'] = expected[tile] == label(value)
                exit_row['same_day_passes'] = physical.get('op:PASS', 0)
                exit_row['same_day_wheat_buy_spend'] = spend.get('BUY_PRODUCT:WHEAT', 0)
                exit_row['dawn_wheat_held'] = dawn['wheat_held'] if dawn else None
                exit_row['age_at_exit'] = day - cohort[2]
                first, interval = ANIMAL_RULES[cohort[1]][1:]
                production_days = [d for d in range(day+1, 30) if d-cohort[2]-first >= 0 and (d-cohort[2]-first) % interval == 0]
                exit_row['remaining_possible_production_days'] = production_days
                exit_row['season_end_note'] = ('No further production before the last played day; omitted feed may be economically intentional.'
                    if not production_days else 'At least one future production date remained; counterfactual profit still unmeasured.')
            elif cohort[1] in ('TOMATO', 'STRAWBERRY') and day-cohort[2] < CROP_FIRST[cohort[1]]:
                if expected[tile] == label(value) and not plan['realized_plan']['crop_remove_counts'].get(cohort[1], 0):
                    young_crop_losses.append(dict(day=day, tile=tile, crop=cohort[1], birth=cohort[2],
                        morning_unwatered_days=value.get('consecutive_unwatered', 0),
                        planned_to_retain=True, same_day_passes=physical.get('op:PASS', 0)))
    final, start = ledger[-1], ledger[6]
    own = {field: diff(final[field], start[field]) for field in ('revenue', 'sold_units', 'spend', 'physical')}
    rival_ledger = game['daily'][1-seat]
    rival = {field: diff(rival_ledger[-1][field], rival_ledger[6][field]) for field in ('revenue', 'sold_units', 'spend', 'physical')}
    return dict(case=game['case'], margin=game['margin'], source=path.relative_to(ROOT).as_posix(),
        source_sha256=sha(path), actions_sha256=sha(actions_path),
        candidate_manifest_sha256=game['candidate_manifest_sha256'], shops=game['shops'],
        execution=audit, finance=finance, service=service, young_crop_losses=young_crop_losses,
        own=own, rival=rival, software_errors_max=max((r['software_errors'] or 0 for r in finance), default=0))


def summarize(games):
    audit = aggregate([g['execution'] for g in games])
    frows = [r for g in games for r in g['finance']]
    services = [r for g in games for r in g['service'] if r['committed']]
    deaths = [r for g in games for r in g['execution']['animal_exits']]
    expansion = [r for r in frows if r['planned_land']]
    own, rival = {}, {}
    for key in ('revenue', 'sold_units', 'spend', 'physical'):
        own[key] = clean(sum((Counter(g['own'][key]) for g in games), Counter()))
        rival[key] = clean(sum((Counter(g['rival'][key]) for g in games), Counter()))
    churn = [r for r in frows if r['wheat_buy_spend'] > 0 and r['wheat_sold'] > 0]
    exact_churn = [r for r in churn if r['wheat_balance'] and r['wheat_balance']['purchased_exact'] and r['wheat_balance']['purchased_minimum'] > 0]
    churn_proxy = sum(min(r['wheat_sold'], r['wheat_balance']['purchased_minimum'])*(
        r['wheat_buy_spend']/r['wheat_balance']['purchased_minimum'] - r['wheat_sale_revenue']/r['wheat_sold']) for r in exact_churn)
    return dict(execution=audit, own=own, rival=rival,
        committed_surviving_animal_days=len(services), committed_unfed_days=sum(not r['fed'] for r in services),
        committed_fed_care_days=sum(r['productive_care'] for r in services),
        committed_unfed_production_days=sum(r['production'] and not r['fed'] for r in services),
        committed_banked_bonus_lost=sum(r['lost_banked_bonus'] for r in services),
        newborn_committed_unfed=sum(r['newborn'] and not r['fed'] for r in services),
        unplanned_deaths=sum(r['classification'] == 'no_matching_recorded_retirement' for r in deaths),
        unplanned_deaths_committed_to_keep=sum(r['classification'] == 'no_matching_recorded_retirement' and r['retained_in_same_day_end_board'] for r in deaths),
        unplanned_deaths_with_remaining_production=sum(r['classification'] == 'no_matching_recorded_retirement' and bool(r['remaining_possible_production_days']) for r in deaths),
        unplanned_exits_after_final_production=sum(r['classification'] == 'no_matching_recorded_retirement' and not r['remaining_possible_production_days'] for r in deaths),
        unplanned_deaths_before_first_production=sum(r['classification'] == 'no_matching_recorded_retirement' and r['age_at_exit'] + 1 < ANIMAL_RULES[r['species']][1] for r in deaths),
        young_committed_crop_losses=sum(len(g['young_crop_losses']) for g in games),
        expansion_days=len(expansion), expansion_purchased=sum(r['land_spend'] > 0 for r in expansion),
        median_observed_unlock_hour=statistics.median([r['unlock_hour'] for r in expansion if r['unlock_hour'] is not None]) if any(r['unlock_hour'] is not None for r in expansion) else None,
        expansion_hire_shortfall=sum(max(0, r['planned_hires'] - r['successful_hires']) for r in expansion),
        total_hire_shortfall=sum(max(0, r['planned_hires'] - r['successful_hires']) for r in frows),
        post_unlock_issued_commands=clean(sum((Counter(r['post_unlock_issued_commands']) for r in expansion), Counter())),
        daily_wheat_buy_and_sell=len(churn), wheat_buy_spend_on_churn_days=sum(r['wheat_buy_spend'] for r in churn),
        wheat_sale_revenue_on_churn_days=sum(r['wheat_sale_revenue'] for r in churn),
        wheat_sold_on_churn_days=sum(r['wheat_sold'] for r in churn),
        exact_churn_balance_days=len(exact_churn), exact_churn_daily_average_spread_proxy=churn_proxy,
        exact_churn_matched_units=sum(min(r['wheat_sold'], r['wheat_balance']['purchased_minimum']) for r in exact_churn),
        expansion_land_and_hires_fundable_at_dawn=sum(bool(r['dawn_liquidity'] and r['dawn_liquidity']['land_and_hires_fundable_at_dawn']) for r in expansion),
        expansion_all_admitted_inputs_fundable_at_dawn_excluding_feed=sum(bool(r['dawn_liquidity'] and r['dawn_liquidity']['admitted_inputs_fundable_excluding_feed']) for r in expansion),
        software_errors_max=max(g['software_errors_max'] for g in games))


def main():
    global PRICE_HELPER
    PRICE_HELPER = load_executor()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', action='append', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=STUDY / 'service_audit_v2.json')
    args = parser.parse_args()
    groups = {}
    for folder in args.runs:
        folder = folder.resolve()
        paths = sorted(p for p in folder.glob('live-*.json') if not p.name.endswith('.actions.json'))
        paths = [p for p in paths if json.loads(p.read_text()).get('completed')]
        if paths:
            games = [service_world(path) for path in paths]
            groups[folder.relative_to(ROOT).as_posix()] = dict(games=games, summary=summarize(games))
    report = dict(schema_version=1, games_executed=0, script_sha256=sha(Path(__file__)), groups=groups,
        limitations=['Dawn private state is available in V2; hourly private state and successful market fills are not saved. Requested order hours are not purchase-success times.',
            'Dawn shed liquidation uses the exact static price curve/floor but cannot determine earliest later financing, delivery times or actual route inventory capacity.',
            'Wheat purchases are inferred exactly by stock conservation only when the following dawn shed is not full; otherwise unknown overflow gives a lower bound.',
            'Daily wheat average-price matched-volume spread is descriptive turnover, not an identified avoidable round-trip loss or causal policy value.',
            'Animal feed inferred from next-morning hunger; useful fed+care from engine banking rules. D29 is censored for boundary service.',
            'A committed survival loss contradicts the recorded same-day target but does not establish its counterfactual profit cost.'])
    args.out.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k: {s: v for s, v in row['summary'].items() if s not in ('execution', 'own', 'rival', 'post_unlock_issued_commands')} for k, row in groups.items()}, indent=2))


if __name__ == '__main__':
    main()
