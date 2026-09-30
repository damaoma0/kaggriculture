"""Research contracts between production decisions, layout and the existing scheduler.

No donor moves, future shops, prices or opponent private state enter this module.
This is a daily compiler, not a complete policy or a packaged submission. A node
must pass exact-engine execution checks before it can be used in a live policy.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
import math


@dataclass(frozen=True)
class Cohort:
    """A quantity decision for today; service_days is a layout heuristic."""
    species: str
    quantity: int
    service_days: float


def place_cohorts(farm, cohorts):
    """Allocate only vacant, owned tiles, highest service load nearest the shed.

    Sorting solves this separable distance objective exactly; it does not solve
    worker tours. Established assets are never moved or demolished. The daily
    scheduler must still check travel, inputs, wages and capacity.
    """
    size = len(farm['tiles'])
    if size < 2 or size % 2 or any(len(row) != size for row in farm['tiles']):
        raise ValueError('expected_even_square_board')
    middle = size // 2
    shed = [(x, y) for x in (middle - 1, middle) for y in (middle - 1, middle)]
    unlocked = set(farm['unlocked_quadrants'])
    vacancies = []
    for y, row in enumerate(farm['tiles']):
        for x, tile in enumerate(row):
            quadrant = ('N' if y < middle else 'S') + ('W' if x < middle else 'E')
            if tile is None and quadrant in unlocked:
                distance = min(abs(x-a) + abs(y-b) for a, b in shed)
                vacancies.append((distance, y, x))
    assets = []
    for cohort in cohorts:
        if (not isinstance(cohort.quantity, int) or isinstance(cohort.quantity, bool)
                or cohort.quantity < 0 or not math.isfinite(cohort.service_days)
                or cohort.service_days < 0):
            raise ValueError('invalid_cohort_quantity_or_service_load')
        assets.extend([(cohort.species, cohort.service_days)] * cohort.quantity)
    if len(assets) > len(vacancies):
        raise ValueError('insufficient_vacant_owned_tiles')
    assets.sort(key=lambda a: (-a[1], a[0]))
    vacancies.sort()
    return [dict(species=s, tile=[x, y], service_days=w, shed_distance=d)
            for (s, w), (d, y, x) in zip(assets, vacancies)]


def production_days(tile, rules, last_day=29):
    """Days on which output is available, excluding the nonexistent day 30."""
    if tile.get('animal'):
        rule = rules.ANIMALS[tile['animal']]
        return list(range(tile['placed_day'] + rule['first_yield_day'],
                          last_day + 1, rule['interval']))
    rule = rules.CROPS[tile['crop']]
    if not rule['ongoing']:
        harvest = tile['planted_day'] + rule['max_yield_day']
        return [harvest] if harvest <= last_day else []
    first = tile['planted_day'] + rule['first_yield_day']
    return [d for i in range(rule['max_yield'])
            if (d := first + i * rule['interval']) <= last_day]


def maintenance(tile, day, rules, last_day=29):
    """Full useful care for one observed asset; explains mechanical omissions.

    Economic skipping is deliberately not inferred from missing expert commands.
    WATER/FEED protect every retained asset by default. Fertilizer is needed only
    on yield-relevant days and while its existing effect is inactive. Harvests
    drain available ongoing output; non-ongoing crops finish their growth first.
    Animal CARE today is useful only to a production day strictly after tomorrow:
    the engine credits it *after* processing tomorrow's production.
    """
    commands, omitted = [], []
    if not isinstance(tile, dict) or not (tile.get('crop') or tile.get('animal')):
        return commands, omitted
    days = production_days(tile, rules, last_day)
    if tile.get('animal'):
        if tile.get('yield_units', 0):
            commands.append(['HARVEST'])
        if tile.get('fertilizer_available'):
            commands.append(['COLLECT_FERTILIZER'])
        if not tile.get('fed_today'):
            if day < last_day:
                commands.append(['FEED'])
            else:
                omitted.append(dict(op='FEED', reason='no_terminal_day_refresh'))
        if not tile.get('cared_today'):
            if any(d > day + 1 for d in days):
                commands.append(['CARE'])
            else:
                omitted.append(dict(op='CARE', reason='no_later_in_season_bonus_tick'))
        return commands, omitted
    rule = rules.CROPS[tile['crop']]
    age = day - tile['planted_day']
    held = tile.get('yield_units', 0)
    harvest = held > 0 and age >= rule['first_yield_day'] and (
        rule['ongoing'] or age >= rule['max_yield_day'] or day == last_day)
    # Ongoing crops stay on the tile after harvesting; empty space is available
    # for tonight's tick. Non-ongoing harvests must follow today's yield inputs.
    if rule['ongoing'] and harvest:
        commands.append(['HARVEST'])
    yield_day = (day + 1 in days if rule['ongoing'] else
                 (rule['max_yield_day'] + 1)//2 <= age <= rule['max_yield_day']
                 and held < rule['max_yield'] and not tile.get('watered_today'))
    if yield_day and tile.get('fertilized_until_day', -1) < day:
        commands.append(['FERTILIZE'])
    else:
        omitted.append(dict(op='FERTILIZE', reason=(
            'already_active' if yield_day else 'no_bonus_window_today')))
    if not tile.get('watered_today'):
        if yield_day or (day < last_day and not (harvest and not rule['ongoing'])):
            commands.append(['WATER'])
        else:
            omitted.append(dict(op='WATER', reason='harvest_or_terminal_day_ends_obligation'))
    if not rule['ongoing'] and harvest:
        commands.append(['HARVEST'])
    return commands, omitted


def maintenance_skip_effect(tile, day, operation, rules, last_day=29):
    """Marginal physical cost of omitting ONE service under full later care.

    Executes the engine's tile operations and daily refresh, with supplied inputs
    and prompt harvests. No price, routing, cash or opponent effect is estimated.
    Two individually harmless skips need not be harmless together.
    """
    if operation not in ('WATER', 'FERTILIZE', 'FEED', 'CARE'):
        raise ValueError('not_a_maintenance_operation')
    if not 0 <= day <= last_day <= 29:
        raise ValueError('skip_horizon_outside_season')

    def run(skip):
        farm = dict(tiles=[[deepcopy(tile)]], farmer=[0, 0], hands=[])
        private = dict(inventories=[{}], shed={}, seeds={})
        output, inputs = Counter(), Counter()
        count, lost = 0, False
        for current in range(day, last_day + 1):
            live = farm['tiles'][0][0]
            commands, _ = maintenance(live, current, rules, last_day)
            hour = 0
            for command in commands:
                op = command[0]
                if skip and current == day and op == operation:
                    continue
                resource = {'FEED':'WHEAT', 'FERTILIZE':'FERTILIZER'}.get(op)
                inv = private['inventories'][0]
                if resource:
                    inv[resource] = inv.get(resource, 0) + 1
                before = Counter(inv)
                rules._apply_unit_action(farm, private, 0, command, 1, current, 24, 100)
                after = Counter(inv)
                if op in ('HARVEST', 'COLLECT_FERTILIZER'):
                    output.update(after - before)
                inputs.update(before - after)
                count += 1
                rules._decay_plants(farm, current * 24 + hour)
                hour += 1
            for rest in range(hour, 23 if current == 29 else 24):
                rules._decay_plants(farm, current * 24 + rest)
            # There is no end-of-day-29 production transition in a 719-action season.
            if current == last_day:
                break
            previous = farm['tiles'][0][0]
            rules._daily_refresh_plants(farm, current, 24)
            rules._daily_refresh_animals(farm, current)
            after = farm['tiles'][0][0]
            if isinstance(previous, dict) and (previous.get('crop') or previous.get('animal')):
                lost |= not isinstance(after, dict) or bool(after.get('kind') == 'WEED') or (
                    bool(previous.get('animal')) and not after.get('animal'))
        return dict(output=dict(output), consumed=dict(inputs), service_commands=count,
                    lost_to_lack_of_service=lost)

    full, skipped = run(False), run(True)
    return dict(operation=operation, day=day,
                applicable=[operation] in maintenance(tile, day, rules, last_day)[0],
                full=full, skipped=skipped,
                output_delta={p:skipped['output'].get(p,0)-full['output'].get(p,0)
                              for p in sorted(set(full['output']) | set(skipped['output']))},
                evidence='single_tile_counterfactual_with_full_later_care')


def observation_digest(observation):
    """Freeze execution prerequisites; never equate tile labels with full state."""
    fields = dict(day=observation['day'], hour=observation['hour'], step=observation['step'],
        player=observation['player'], farm=observation['farms'][observation['player']],
        private=observation['private'], market=observation['market'], town=observation['town'])
    return sha256(json.dumps(fields, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def compile_day(observation, cohorts, rules, *, workers, cash_reserve=0):
    """Translate today's quantities + default care to a fresh-route node.

    The caller chooses quantities and headcount. This contract deliberately has
    no sales or land orders: those require a cash/market plan beyond this pilot.
    It starts at dawn and is rebuilt from observed state each day.
    """
    if observation['hour'] != 0 or observation['step'] != 24 * observation['day']:
        raise ValueError('daily_contract_requires_dawn')
    if not 0 <= observation['day'] <= 29:
        raise ValueError('outside_season')
    if (not isinstance(workers, int) or isinstance(workers, bool) or workers < 1
            or not math.isfinite(cash_reserve) or cash_reserve < 0):
        raise ValueError('invalid_workers_or_cash_reserve')
    own, day = int(observation['player']), int(observation['day'])
    farm = observation['farms'][own]
    assignments = place_cohorts(farm, cohorts)
    jobs, omissions = [], []

    def append(pos, commands, tile):
        for sequence, command in enumerate(commands):
            effect = {}
            if command[0] == 'HARVEST':
                item = tile.get('crop') or rules.ANIMALS[tile['animal']]['product']
                # Conservative transport reservation includes possible watering
                # growth before harvesting a non-ongoing crop.
                amount = tile.get('yield_units', 0)
                if tile.get('crop') and not rules.CROPS[tile['crop']]['ongoing']:
                    amount = rules.CROPS[tile['crop']]['max_yield']
                effect[item] = amount
            jobs.append(dict(day=0, hour=sequence, tile=list(pos), cmd=command,
                             effect=effect))

    for y, row in enumerate(farm['tiles']):
        for x, tile in enumerate(row):
            commands, reasons = maintenance(tile, day, rules)
            append((x, y), commands, tile)
            omissions.extend(dict(tile=[x, y], **r) for r in reasons)
    for assignment in assignments:
        species, pos = assignment['species'], assignment['tile']
        if species in rules.CROPS:
            tile = rules._new_plant(species, day, 24)
            commands = [['PLANT', species]]
        elif species in rules.ANIMALS:
            tile = rules._new_animal(species, day)
            commands = [['BUILD_' + rules.ANIMALS[species]['structure']], ['PLACE', species, 1]]
        else:
            raise ValueError('unknown_cohort_species: ' + species)
        care, reasons = maintenance(tile, day, rules)
        append(pos, commands + care, tile)
        omissions.extend(dict(tile=pos, **r) for r in reasons)
    return dict(jobs=jobs, hire_to=workers, cash_reserve=cash_reserve,
                safety_assets=False, assignments=assignments, omissions=omissions,
                start_day=day, horizon_days=1,
                origin_sha256=observation_digest(observation),
                requested=dict(Counter(j['cmd'][0] for j in jobs)),
                status='requires_engine_validation')


def start_scheduled_day(observation, contract):
    """Use the repository's existing continuation scheduler without donor routes."""
    from fragments.continuation_executor import segment_executor_start
    if observation['day'] != contract['start_day'] or observation['hour'] != 0:
        raise ValueError('contract_start_mismatch')
    if observation_digest(observation) != contract['origin_sha256']:
        raise ValueError('contract_prerequisites_changed_recompile')
    return segment_executor_start(deepcopy(observation), deepcopy(contract))


def scheduled_action(observation, state):
    from fragments.continuation_executor import segment_executor_action
    if observation['day'] != state['start_day']:
        raise ValueError('daily_contract_expired_recompile_from_observation')
    return segment_executor_action(observation, state)


def check_scheduled_day(observation, contract, *, budget_seconds=1.0):
    """Check *all* scheduled physical jobs, including care, before activation.

    The inherited window checker checks establishment/harvesting but can miss a
    failed FEED or FERTILIZE. This adapter closes that gap for daily contracts.
    Projection uses the checked-in engine's mechanics, today's revealed shops,
    no rival trades and no new weeds. It proves only conditional feasibility.
    """
    import time
    from fragments import continuation_executor as executor
    from fragments.continuation_projection import project_step
    if not math.isfinite(budget_seconds) or budget_seconds <= 0:
        raise ValueError('invalid_planning_budget')
    previous = executor.set_deadline(time.perf_counter() + budget_seconds)
    try:
        state = start_scheduled_day(observation, contract)
        if not state['ok']:
            return dict(ok=False, failure=state['failure'])
        projected, actions, completed = deepcopy(observation), [], set()
        for _ in range(23 if observation['day'] == 29 else 24):
            executor.check_budget()
            hour = projected['hour']
            action = scheduled_action(projected, state)
            if state.get('failure'):
                return dict(ok=False, failure=state['failure'])
            scheduled = state['plans'].get(0, {}).get('scheduled', {})
            projected, report = project_step(projected, action)
            if report['failures'] or report['overflow']:
                return dict(ok=False, failure=dict(reason='projection_failed', hour=hour, **report))
            commands = [action['farmer'], *action.get('hands', [])]
            for (worker, at), job_id in scheduled.items():
                if at != hour:
                    continue
                expected = state['jobs'][job_id]['cmd']
                if (worker >= len(report['changes']) or not report['changes'][worker]
                        or worker >= len(commands) or commands[worker] != expected):
                    return dict(ok=False, failure=dict(reason='unfulfilled_job',
                        job=job_id, command=expected, worker=worker, hour=hour))
                completed.add(job_id)
            actions.append(action)
        if len(completed) != len(contract['jobs']):
            return dict(ok=False, failure=dict(reason='incomplete_contract',
                        completed=len(completed), requested=len(contract['jobs'])))
        if projected['farms'][observation['player']]['money'] < contract['cash_reserve']:
            return dict(ok=False, failure=dict(reason='cash_reserve_breached'))
        return dict(ok=True, evidence='own_farm_projection_only', actions=actions,
                    end_observation=projected, completed_jobs=len(completed))
    except executor.PlanningBudgetExceeded:
        return dict(ok=False, failure=dict(reason='planning_budget'))
    finally:
        executor.set_deadline(previous)
