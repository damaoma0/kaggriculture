"""Audit intended daily quantities against observed execution, without games.

Boundaries identify lasting changes, not unsuccessful action requests. The final
day has no following morning in this harness and is explicitly censored. Later
matching plants are descriptive: the next day's replanning may change intent.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / 'results/fresh/semantic_strategy_20260928'
CROPS = {'WHEAT', 'CARROT', 'MELON', 'STRAWBERRY', 'TOMATO'}
ANIMALS = {'COW', 'SHEEP', 'GOOSE'}
CROP_LABEL = {'WHEAT': 'WH', 'CARROT': 'CA', 'MELON': 'ME', 'STRAWBERRY': 'ST', 'TOMATO': 'TO'}
LABEL_CROP = {v: k for k, v in CROP_LABEL.items()}
LABEL_ANIMAL = {'co': 'COW', 'sh': 'SHEEP', 'go': 'GOOSE'}


def clean(counter):
    return dict(sorted((k, v) for k, v in counter.items() if v))


def diff(after, before):
    return clean(Counter({k: v - before.get(k, 0) for k, v in after.items()}))


def identity(tile):
    if not isinstance(tile, dict):
        return None
    if tile.get('kind') == 'PLANT':
        return 'crop', tile['crop'], int(tile['planted_day'])
    if tile.get('animal'):
        return 'animal', tile['animal'], int(tile['placed_day'])
    return None


def label(tile):
    if tile == 'LOCKED':
        return ' L'
    if not isinstance(tile, dict) or tile.get('kind') == 'WEED':
        return ' .'
    if tile.get('crop'):
        return CROP_LABEL[tile['crop']]
    if tile.get('animal'):
        return tile['animal'][:2].lower()
    return tile.get('kind', '')[:2].lower()


def flat(farm):
    return [tile for row in farm['tiles'] for tile in row]


def quadrant(tile):
    x, y = tile % 10, tile // 10
    return ('N' if y < 5 else 'S') + ('W' if x < 5 else 'E')


def counts(cells, kind):
    return clean(Counter(i[1] for t in cells if (i := identity(t)) and i[0] == kind))


def births(before, after, day):
    out = {'crop': [], 'animal': []}
    for tile, value in enumerate(after):
        new = identity(value)
        if new is not None and new != identity(before[tile]):
            assert new[2] == day, (day, tile, new)
            out[new[0]].append(dict(tile=tile, species=new[1], birth=new[2]))
    return out


def exits(before, after):
    out = {'crop': [], 'animal': []}
    for tile, value in enumerate(before):
        old = identity(value)
        if old is not None and old != identity(after[tile]):
            out[old[0]].append(dict(tile=tile, species=old[1], birth=old[2]))
    return out


def record_counts(records):
    return clean(Counter(r['species'] for r in records))


def fraction(expected, actual):
    e = sum(expected.values())
    achieved = sum(min(n, actual.get(k, 0)) for k, n in expected.items())
    return dict(requested=e, actual=sum(actual.values()), matched=achieved,
        fraction=(achieved / e if e else None), missing=clean(Counter({k: max(0, n - actual.get(k, 0)) for k, n in expected.items()})))


def audit_world(path):
    world = json.loads(path.read_text(encoding='utf-8'))
    seat = world['case']['seat']
    assert world['completed'] and world['ledger_verified']
    assert world['engine_audit']['steps'] == 720
    log = world['diagnostics'][seat]
    morning = {r['day']: r['current_observation']['own_farm'] for r in log}
    plans = {}
    for snapshot in log:
        for entry in snapshot.get('diagnostics') or []:
            if entry.get('phase') == 'semantic':
                plans[entry['day']] = entry
    actions_path = path.with_name(path.stem + '.actions.json')
    actions = json.loads(actions_path.read_text())[seat]
    days, actual_exits, intentions = [], [], []
    cumulative = world['daily'][seat]
    for day in range(6, 30):
        entry, plan = plans[day], plans[day]['realized_plan']
        before = flat(morning[day])
        physical = diff(cumulative[day + 1]['physical'], cumulative[day]['physical'])
        for intent in entry.get('retirements') or []:
            tile = int(intent['tile'])
            cohort = identity(before[tile])
            intentions.append(dict(intent, birth=cohort[2] if cohort and cohort[0] == 'animal' else None))
        row = dict(day=day, proposal=entry['proposal'], compiled=plan,
            capacity_adjustments=entry['capacity_adjustments'], warnings=entry['warnings'],
            physical=physical, revenue=diff(cumulative[day + 1]['revenue'], cumulative[day]['revenue']),
            sold_units=diff(cumulative[day + 1]['sold_units'], cumulative[day]['sold_units']),
            spend=diff(cumulative[day + 1]['spend'], cumulative[day]['spend']),
            start_cash=cumulative[day]['money'], end_cash=cumulative[day + 1]['money'],
            land_request_hours=[step % 24 for step in range(day * 24, min(719, (day + 1) * 24))
                if any(o and o[0] == 'BUY_LAND' for o in actions[step].get('market', []))],
            boundary_observed=day + 1 in morning,
            lower_errors_logged=entry.get('executor_errors_cumulative'),
            lower_last_error=entry.get('executor_last_error'))
        row['attempted_work'] = physical.get('commands', 0) - physical.get('moves', 0) - physical.get('op:PASS', 0)
        row['no_effect_rate'] = physical.get('no_effect', 0) / max(1, row['attempted_work'])
        row['proposal_to_compiled_crops'] = fraction(entry['proposal'].get('plant_counts', {}), plan['plant_counts'])
        row['proposal_to_compiled_animals'] = fraction(entry['proposal'].get('animal_add_counts', {}), plan['animal_add_counts'])
        if not row['boundary_observed']:
            row['actual'] = None
            days.append(row)
            continue
        after = flat(morning[day + 1])
        added, removed = births(before, after, day), exits(before, after)
        for exit_ in removed['animal']:
            actual_exits.append(dict(exit_, exit_day=day))
        structures = Counter(t['kind'] for i, t in enumerate(after) if isinstance(t, dict)
            and t.get('kind') in ('COOP', 'PASTURE')
            and (not isinstance(before[i], dict) or before[i].get('kind') != t['kind']))
        new_land = sorted(set(morning[day + 1]['unlocked_quadrants']) - set(morning[day]['unlocked_quadrants']))
        crop_added, animal_added = record_counts(added['crop']), record_counts(added['animal'])
        old_exits = record_counts(removed['crop'])
        planned_exits = Counter(plan['crop_end_counts']) + Counter(plan['crop_remove_counts']) + Counter(plan['crop_disappear_counts'] or {})
        row['actual'] = dict(plant_counts=crop_added, animal_add_counts=animal_added,
            build_counts=clean(structures), crop_exit_counts=old_exits,
            animal_exit_counts=record_counts(removed['animal']), new_quadrants=new_land,
            end_crop_counts=counts(after, 'crop'), end_animal_counts=counts(after, 'animal'),
            new_crop_cohorts=added['crop'], new_animal_cohorts=added['animal'],
            exited_crop_cohorts=removed['crop'], exited_animal_cohorts=removed['animal'])
        row['crop_execution'] = fraction(plan['plant_counts'], crop_added)
        row['animal_execution'] = fraction(plan['animal_add_counts'], animal_added)
        row['structure_execution'] = fraction(plan['build_counts'], clean(structures))
        row['crop_exit_timing'] = dict(planned=clean(planned_exits), actual=old_exits,
            excess_over_planned_count=clean(Counter({k: max(0, n-planned_exits[k]) for k, n in old_exits.items()})))
        expected_board = entry['end_board']
        row['ending_label_mismatches'] = [i for i, t in enumerate(after) if label(t) != expected_board[i]]
        row['new_land_empty_tiles'] = sum(quadrant(i) in new_land and label(t) == ' .' for i, t in enumerate(after))
        row['new_land_planned_asset_tiles'] = sum(quadrant(i) in new_land and x not in (' .', ' L') for i, x in enumerate(expected_board))
        row['new_land_actual_asset_tiles'] = sum(quadrant(i) in new_land and label(t) not in (' .', ' L') for i, t in enumerate(after))
        row['planned_unbought_quadrants'] = max(0, int(plan['land_add_count']) - len(new_land))
        # New crop labels on previously different tiles are unambiguous spatial
        # planting intentions. Same-crop rotations cannot be identified from the
        # logged labels alone and are left to count-level comparisons above.
        matched_later = []
        for tile, wanted in enumerate(expected_board):
            if wanted not in LABEL_CROP or label(before[tile]) == wanted:
                continue
            species = LABEL_CROP[wanted]
            observed = identity(after[tile])
            if observed and observed[:2] == ('crop', species) and observed[2] == day:
                status, lag = 'on_time', 0
            else:
                lag = None
                for later in range(day + 2, min(day + 7, 30)):
                    found = identity(flat(morning[later])[tile])
                    if found and found[:2] == ('crop', species) and day < found[2] < later:
                        lag = found[2] - day
                        break
                status = 'later_matching_plant' if lag is not None else 'no_matching_plant_in_followup'
            matched_later.append(dict(tile=tile, crop=species, status=status, lag_days=lag))
        row['unambiguous_new_crop_sites'] = matched_later
        days.append(row)
    # Match physical exits only to the same actual starting cohort. Intent is
    # allowed to be deliberate; unmatched deaths are not automatically bad.
    for exit_ in actual_exits:
        matching = [r for r in intentions if (int(r['tile']), r['animal'], r['birth']) ==
            (exit_['tile'], exit_['species'], exit_['birth']) and r['first_unfed_day'] <= exit_['exit_day']]
        if matching:
            intent = min(matching, key=lambda r: r['first_unfed_day'])
            exit_['intent_first_unfed_day'] = intent['first_unfed_day']
            delta = exit_['exit_day'] - intent['expected_exit_day']
            exit_['timing_delta_days'] = delta
            exit_['classification'] = 'planned_on_time' if delta == 0 else 'planned_late' if delta > 0 else 'planned_early'
        else:
            exit_['classification'] = 'no_matching_recorded_retirement'
    for intent in intentions:
        matching = [r for r in actual_exits if (r['tile'], r['species'], r['birth']) ==
            (int(intent['tile']), intent['animal'], intent['birth']) and r['exit_day'] >= intent['first_unfed_day']]
        intent['observed_exit_day'] = matching[0]['exit_day'] if matching else None
        intent['status'] = ('exit_observed' if matching else 'endpoint_censored' if intent['expected_exit_day'] >= 29
            else 'no_exit_observed_by_day29_morning')
    return dict(case=world['case'], cash=world['cash'], opponent_cash=world['opponent_cash'], margin=world['margin'],
        top_level_errors=world['errors'], measured_runtime_valid=world['measured_runtime_valid'],
        source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), days=days,
        retirements=intentions, animal_exits=actual_exits)


def aggregate(games):
    by_day, by_asset = {}, defaultdict(Counter)
    for day in range(6, 30):
        rows = [r for game in games for r in game['days'] if r['day'] == day]
        metrics = Counter()
        for row in rows:
            metrics.update(passes=row['physical'].get('op:PASS', 0), moves=row['physical'].get('moves', 0),
                attempted_work=row['attempted_work'], no_effect=row['physical'].get('no_effect', 0))
            if not row['boundary_observed']:
                continue
            metrics.update(new_quadrants=len(row['actual']['new_quadrants']),
                new_land_empty_tiles=row['new_land_empty_tiles'],
                new_land_planned_assets=row['new_land_planned_asset_tiles'],
                new_land_actual_assets=row['new_land_actual_asset_tiles'])
            for kind, target, actual in [('crop', row['compiled']['plant_counts'], row['actual']['plant_counts']),
                ('animal', row['compiled']['animal_add_counts'], row['actual']['animal_add_counts']),
                ('structure', row['compiled']['build_counts'], row['actual']['build_counts'])]:
                f = fraction(target, actual)
                metrics.update({kind + '_' + k: f[k] for k in ('requested', 'actual', 'matched')})
                for asset in set(target) | set(actual):
                    by_asset[kind + ':' + asset].update(requested=target.get(asset, 0), actual=actual.get(asset, 0),
                        matched=min(target.get(asset, 0), actual.get(asset, 0)))
        by_day[str(day)] = dict(metrics, no_effect_rate=metrics['no_effect']/max(1, metrics['attempted_work']),
            boundary_observed=all(r['boundary_observed'] for r in rows))
    total = Counter()
    for values in by_asset.values():
        total.update(values)
    lower = [r['lower_errors_logged'] for game in games for r in game['days']]
    return dict(worlds=len(games), wins=sum(g['margin'] > 0 for g in games), mean_margin=sum(g['margin'] for g in games)/len(games),
        by_day=by_day, by_asset={k: dict(v, fraction=v['matched']/v['requested'] if v['requested'] else None) for k, v in sorted(by_asset.items())},
        animal_exits=clean(Counter(x['classification'] for g in games for x in g['animal_exits'])),
        retirement_outcomes=clean(Counter(x['status'] for g in games for x in g['retirements'])),
        crop_site_outcomes=clean(Counter(x['status'] for g in games for r in g['days'] for x in r.get('unambiguous_new_crop_sites', []))),
        no_effect_by_op=clean(Counter({op: sum(r['physical'].get(op, 0) for g in games for r in g['days'])
            for op in {k for g in games for r in g['days'] for k in r['physical'] if k.startswith('no_effect:')}})),
        lower_error_coverage=sum(x is not None for x in lower), daily_plans=len(lower))


def markdown(report):
    a = report['aggregate']
    lines = ['# Semantic strategy execution audit', '',
        f"{a['worlds']} completed games; {a['wins']} wins; mean margin {a['mean_margin']:+,.0f}. These are development outcomes.", '',
        '## Daily execution', '',
        'Counts show matched actual additions / compiled requested additions. Matching is by type and day; extra additions cannot compensate for a different missing type.', '',
        '| Day | Crops | Animals | Structures | PASS | No-effect / work | New land: actual / planned asset tiles |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for d, row in a['by_day'].items():
        if not row['boundary_observed']:
            continue
        lines.append(f"| {d} | {row.get('crop_matched',0)}/{row.get('crop_requested',0)} | {row.get('animal_matched',0)}/{row.get('animal_requested',0)} | {row.get('structure_matched',0)}/{row.get('structure_requested',0)} | {row['passes']} | {row['no_effect']}/{row['attempted_work']} | {row.get('new_land_actual_assets',0)}/{row.get('new_land_planned_assets',0)} |")
    lines += ['', '## Addition coverage by type (D6–28)', '', '| Asset | Matched | Requested | Fraction |', '|---|---:|---:|---:|']
    for asset, row in a['by_asset'].items():
        pct = f"{row['fraction']:.1%}" if row['fraction'] is not None else 'n/a'
        lines.append(f"| {asset} | {row['matched']} | {row['requested']} | {pct} |")
    lines += ['', '## Retirement and errors', '',
        'Observed animal exit classifications: ' + json.dumps(a['animal_exits'], sort_keys=True) + '.', '',
        'Recorded retirement outcomes: ' + json.dumps(a['retirement_outcomes'], sort_keys=True) + '.', '',
        'Unambiguous new crop site outcomes: ' + json.dumps(a['crop_site_outcomes'], sort_keys=True) + '.', '',
        'No-effect commands by operation: ' + json.dumps(a['no_effect_by_op'], sort_keys=True) + '.', '',
        f"Lower-layer exception counters were logged for {a['lower_error_coverage']}/{a['daily_plans']} daily plans. Empty top-level error lists do not establish that caught dispatcher exceptions were absent.", '',
        '## Limits', '', *['- ' + text for text in report['limitations']], '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', type=Path, default=STUDY / 'runs/smoke_v1/development/live')
    parser.add_argument('--out', type=Path, default=STUDY / 'smoke_v1_execution_audit.json')
    args = parser.parse_args()
    paths = [p for p in sorted(args.runs.glob('live-*.json')) if not p.name.endswith('.actions.json')]
    games = [audit_world(p) for p in paths]
    assert games
    report = dict(schema_version=1, games_executed=0, runs=str(args.runs), games=games, aggregate=aggregate(games),
        limitations=['No following morning is saved for D29; boundary additions/exits are censored, while its action/financial ledger is still included.',
            'Boundary changes omit construction or placement that was undone within the same day.',
            'Counts match by type/day; same-crop rotations cannot be located from end labels alone.',
            'Later matching plants are not proof of a delayed original command: daily replanning can replace the old intention.',
            'An exit without a recorded retirement is described neutrally; these observations do not prove whether a death was economically harmful.',
            'No-effect commands measure unsuccessful physical work, not caught lower-layer software exceptions.'])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding='utf-8')
    args.out.with_suffix('.md').write_text(markdown(report), encoding='utf-8')
    print(json.dumps(report['aggregate'], indent=2))


if __name__ == '__main__':
    main()
