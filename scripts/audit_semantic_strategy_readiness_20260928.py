"""Read-only frozen V5 dawn compiler audit; no engine or agent calls."""
from collections import Counter
from copy import deepcopy
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/fresh/semantic_strategy_20260928'
CANDIDATE = BASE / 'candidates/strategy_v5_blocks100_finance'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_exit(cell, day, ages):
    crop, birth = cell['crop'], cell['planted_day']
    end = max(day, birth+ages[crop])
    projected = cell.get('yield_units', 0)
    if day-birth == ages[crop] and day < 29:
        max_age = {'WHEAT': 4, 'CARROT': 3, 'MELON': 12}[crop]
        if not cell.get('watered_today') and (max_age+1)//2 <= day-birth <= max_age:
            projected += 1+int(cell.get('fertilized_until_day', -1) >= day)
        if projected < {'WHEAT': 5, 'CARROT': 4, 'MELON': 6}[crop]:
            end = day+1
    return min(end, 29), projected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--current', action='store_true', help='Audit the editable corrected adapter/compiler against the same public observations.')
    args = parser.parse_args()
    project = CANDIDATE / 'project'
    manifest = json.loads((CANDIDATE / 'manifest.json').read_text())
    for path, digest in manifest['files'].items():
        assert sha(project / path) == digest
    source_root = ROOT if args.current else project
    sys.path.insert(0, str(source_root / 'scripts'))
    spec = importlib.util.spec_from_file_location('readiness_adapter', source_root / 'scripts/semantic_strategy_tiles_20260928.py')
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)
    config = json.loads((project / 'results/fresh/semantic_strategy_20260928/candidate_config.json').read_text())
    ages = dict(adapter.RELEASE_AGE, **config.get('tiles', {}).get('release_age', {}))
    all_days, sources = [], {}
    for path in sorted((BASE / 'runs/strategy_v5_blocks100_finance/development/live').glob('live-*.json')):
        if path.name.endswith('.actions.json'):
            continue
        source = json.loads(path.read_text())
        if not source['completed'] or not source['eligible']:
            continue
        sources[path.name] = sha(path)
        seat = source['case']['seat']
        memory = {}
        snapshots = source['diagnostics'][seat]
        for snap in snapshots:
            view = snap['current_observation']
            obs = dict(view, farms=[view['own_farm'] if index == seat else {} for index in (0, 1)])
            adapter.observe_own(obs, memory)
            day = snap['day']
            if day < 6:
                continue
            original = next(row for row in snap['diagnostics'] if row['day'] == day)
            if original.get('phase') != 'semantic':
                continue
            plan, memory, audit = adapter.build_plan(obs, dict(today=original['proposal'], forecast=[]), memory, config.get('tiles'))
            parity = audit['today']['end_board'] == original['end_board']
            mismatches = []
            for y, row in enumerate(view['own_farm']['tiles']):
                for x, cell in enumerate(row):
                    if not isinstance(cell, dict) or cell.get('crop') not in ('WHEAT', 'CARROT', 'MELON'):
                        continue
                    tile = y*10+x
                    end, projected = expected_exit(cell, day, ages)
                    assigned = tile in plan['harv_tiles'][day]
                    if assigned == (end == day):
                        continue
                    after = snapshots[day+1]['current_observation']['own_farm']['tiles'][y][x] if day < 29 else None
                    mismatches.append(dict(tile=tile, crop=cell['crop'], birth=cell['planted_day'],
                        current_yield=cell.get('yield_units', 0), projected_yield=projected,
                        public_state_exit_day=end, compiler_harvest_today=assigned,
                        replacement=plan['plant'][day].get(str(tile)), next_morning_cell=after))
            all_days.append(dict(case=source['case']['id'], day=day, saved_end_board_parity=parity,
                original_realized_plan=original['realized_plan'], replanned_realized_plan=audit['semantic_today'],
                readiness_mismatches=mismatches))
    accepted = [row for row in all_days if row['saved_end_board_parity']]
    bad = [row for row in accepted if row['readiness_mismatches']]
    types = Counter(c['crop'] for row in bad for c in row['readiness_mismatches'])
    result = dict(scope='V5_CURRENT_PUBLIC_DAWN_STATE_COMPILER_AUDIT', games_executed=0, current_fix=args.current,
        candidate_manifest_sha256=sha(CANDIDATE / 'manifest.json'), source_files_sha256=sources,
        script_sha256=sha(Path(__file__)),
        adapter_sha256=sha(source_root / 'scripts/semantic_strategy_tiles_20260928.py'),
        compiler_sha256=sha(source_root / 'scripts/semantic_tile_planner_20260928.py'),
        method='Rebuild each current-day proposal using frozen V5 modules and observed morning prefix. Future forecasts are empty because this check concerns current initial crop lifetimes. Accept a diagnosis only when the resulting current end-board exactly equals the saved one. Original artifacts remain untouched.',
        summary=dict(worlds=len(sources), dawns=len(all_days), matching_saved_end_boards=len(accepted),
            affected_matching_dawns=len(bad), swapped_initial_cells=sum(len(row['readiness_mismatches']) for row in bad),
            crop_mismatch_counts=dict(types),
            all_dawn_readiness_mismatches=sum(len(row['readiness_mismatches']) for row in all_days),
            realized_daily_counts_preserved=sum(row['original_realized_plan']==row['replanned_realized_plan'] for row in all_days)), days=all_days)
    target = BASE / ('v5_initial_readiness_fixed_audit.json' if args.current else 'v5_initial_readiness_audit.json')
    target.write_text(json.dumps(result, indent=2, sort_keys=True), encoding='utf-8')
    print(json.dumps(dict(summary=result['summary'], sha256=sha(target))))


if __name__ == '__main__':
    main()
