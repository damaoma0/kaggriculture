"""Validate observed locks and all future placement dates without playing games."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from semantic_tile_inputs_20260928 import ROOT
from semantic_tile_planner_20260928 import compile_plan


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def quadrant(tile):
    tile = int(tile)
    return ('S' if tile // 10 >= 5 else 'N') + ('E' if tile % 10 >= 5 else 'W')


def validate(game, plan):
    initial = game['initial_state']
    assert plan['board'][6] == initial['board']
    locked = {str(t) for t, label in enumerate(initial['board']) if label == ' L'}
    assert locked == {t for t, cell in initial['tiles'].items() if cell.get('locked')}
    purchases = dict(NW=-1, **plan['land_day'])
    placements = 0
    for day in range(6, 30):
        for tile, label in enumerate(plan['board'][day]):
            is_locked = purchases.get(quadrant(tile), 99) >= day
            assert (label == ' L') == is_locked, ('morning_lock', day, tile, label)
        for field in ('plant', 'struct_by_day', 'animals_by_day'):
            for tile in plan[field][day]:
                assert purchases.get(quadrant(tile), 99) <= day, (field, day, tile)
                placements += 1
    for row in plan['planner_metadata']['daily']:
        day = row['day']
        for tile, label in enumerate(row['end_board']):
            is_locked = purchases.get(quadrant(tile), 99) > day
            assert (label == ' L') == is_locked, ('evening_lock', day, tile, label)
        expected = game['days'][day]['end_occupancy_counts']
        if expected is not None:
            assert row['end_board'].count(' L') == expected['locked']
    return dict(locked_at_handoff=len(locked), checked_placement_entries=placements,
                planned_purchase_days=plan['land_day'])


def main():
    base = ROOT / 'results/fresh/semantic_strategy_20260928'
    original = base / 'semantic_inputs_oracle_d6_40.json'
    corrected = base / 'semantic_inputs_oracle_d6_40_locked_v2.json'
    old = json.loads(original.read_text())
    new = json.loads(corrected.read_text())
    selection = base / 'oracle_diagnostics/d6_exact_vs_retile_v3/manifest.json'
    selected = [row['episode'] for row in json.loads(selection.read_text())['cases']]
    rows, failures = {}, {}
    for episode, game in new.items():
        cleaned = deepcopy(game)
        cleaned['initial_state']['tiles'] = {t: c for t, c in cleaned['initial_state']['tiles'].items() if not c.get('locked')}
        assert cleaned == old[episode], 'Change beyond observed lock restoration'
        try:
            plan = compile_plan(game)
        except ValueError as exc:
            failures[episode] = dict(error=str(exc), selected=episode in selected,
                day6_animal_add_counts=game['days'][6]['animal_add_counts'],
                day6_animal_retire_counts=game['days'][6]['animal_retire_counts'])
            continue
        rows[episode] = validate(game, plan)
    assert all(episode in rows for episode in selected), 'Selected oracle game fails lock preflight'
    audit = dict(worlds=len(new), compiled_worlds=len(rows), games_executed=0, only_change='Restore observed handoff locked cells',
                 original_input_sha256=sha(original), corrected_input_sha256=sha(corrected),
                 source_sha256={name: sha(ROOT / 'scripts' / name) for name in
                   ('semantic_tile_inputs_20260928.py', 'semantic_tile_planner_20260928.py',
                    'semantic_tile_allocator_20260928.py', 'semantic_tile_lifetimes_20260928.py', Path(__file__).name)},
                 selected_episodes=selected, selection_manifest_sha256=sha(selection),
                 selected_checks_passed=True, all_checks_passed=not failures,
                 compile_failures=failures, worlds_checked=rows)
    path = base / 'semantic_inputs_oracle_d6_40_locked_v2_compile_audit.json'
    path.write_text(json.dumps(audit, indent=2), encoding='utf-8')
    print(json.dumps(dict(worlds=len(new), compiled_worlds=len(rows), selected_checks_passed=True,
                          compile_failures=failures, audit_sha256=sha(path))))


if __name__ == '__main__':
    main()
