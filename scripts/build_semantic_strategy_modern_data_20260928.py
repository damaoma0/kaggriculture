"""Add modern DSM count supervision using archived observations, without games.

Only prior successful plant/place/build changes, the current morning board and
cash, and already revealed shops enter features. Current-day successful changes
are supervision labels. Unknown private state and prices remain explicitly null.
The existing frozen training model is read-only; every output has a new name.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import time

from semantic_tile_inputs_20260928 import (
    LABEL_CROP, extract_game, initial_state, load_executor, strict_input,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/semantic_strategy_20260928'
NULL_FIELDS = ('seeds', 'shed', 'inventories', 'prices',
               'opponent_crop_cohorts', 'opponent_animal_cohorts')
STRUCT_LABELS = {'co', 'pa', 'sh', 'go'}


def read(path):
    with gzip.open(path, 'rt', encoding='utf-8') if str(path).endswith('.gz') else open(path, encoding='utf-8') as f:
        return json.load(f)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean(counter):
    return dict(sorted((key, value) for key, value in counter.items() if value))


def quadrant(tile):
    return ('S' if tile // 10 >= 5 else 'N') + ('E' if tile % 10 >= 5 else 'W')


def features_from_prefix(history, current_board, cash, revealed_shops):
    """This API cannot see current-day labels, future boards or shop suffixes.

    Coordinates are used only to reconstruct already observed cohort ages and
    disappear after aggregation. The compact board's 'co' label is ambiguous:
    past successful construction distinguishes an empty coop from a cow.
    """
    planted, placed, structures = {}, {}, {}
    for day, source in enumerate(history):
        for crop, tile_ids in source['planted'].items():
            for tile in tile_ids:
                planted[int(tile)] = (crop, day)
        for tile in source['animals']['placed']:
            placed[int(tile)] = day
        for op, tile_ids in source['built'].items():
            for tile in tile_ids:
                structures[int(tile)] = 'COOP' if op == 'BUILD_COOP' else 'PASTURE'
        boundary = history[day + 1]['board'] if day + 1 < len(history) else current_board
        for tile in list(structures):
            if boundary[tile] not in STRUCT_LABELS:
                del structures[tile]

    crops, animals, kinds = Counter(), Counter(), Counter()
    for tile, label in enumerate(current_board):
        if label in LABEL_CROP:
            crop = LABEL_CROP[label]
            assert tile in planted and planted[tile][0] == crop, (len(history), tile, label)
            crops[planted[tile]] += 1
        if label in STRUCT_LABELS:
            kind = structures[tile]
            kinds[kind] += 1
            species = ('GOOSE' if label == 'go' and kind == 'COOP' else
                       'SHEEP' if label == 'sh' and kind == 'PASTURE' else
                       'COW' if label == 'co' and kind == 'PASTURE' else None)
            if species:
                assert tile in placed, (len(history), tile, label)
                animals[species, placed[tile]] += 1
    owned = {quadrant(tile) for tile, label in enumerate(current_board) if label != ' L'}
    features = dict(
        own_crop_cohorts=[dict(crop=c, birth=b, count=n) for (c, b), n in sorted(crops.items())],
        own_animal_cohorts=[dict(species=c, birth=b, count=n) for (c, b), n in sorted(animals.items())],
        own_structures=clean(kinds), cash=cash,
        owned_quadrants=[q for q in ('NW', 'NE', 'SW', 'SE') if q in owned],
        hands=0, shops_prefix=list(revealed_shops),
    )
    features.update({key: None for key in NULL_FIELDS})
    return features


def exclusions(protocol, old_panel):
    reserved = protocol['development']['recorded'] + protocol['qualification']['recorded'] + protocol['recorded_reserve']
    reserved_ids = {int(row['episode']) for row in reserved}
    old_ids = {int(token.strip().split(':')[-1]) for token in old_panel.strip().split(',') if token.strip()}
    return reserved_ids, old_ids


def check_features(features, sem, exact, day):
    """Independent full extractor is an audit comparator, never a feature input."""
    state = initial_state(sem, exact, day)
    expected_crops = Counter((tile['crop'], tile['planted_day']) for tile in state['crops'].values())
    expected_animals = Counter((tile['species'], tile['placed_day']) for tile in state['animals'].values())
    assert features['own_crop_cohorts'] == [dict(crop=c, birth=b, count=n) for (c, b), n in sorted(expected_crops.items())]
    assert features['own_animal_cohorts'] == [dict(species=c, birth=b, count=n) for (c, b), n in sorted(expected_animals.items())]
    assert features['own_structures'] == clean(Counter(state['structures'].values()))
    assert features['owned_quadrants'] == state['unlocked_quadrants']
    assert all(cohort['birth'] < day for field in ('own_crop_cohorts', 'own_animal_cohorts') for cohort in features[field])


def write(path, value, *, pretty=False):
    path.write_text(json.dumps(value, indent=2 if pretty else None, separators=None if pretty else (',', ':')), encoding='utf-8')


def build(out=OUT, include_stage1_training=False):
    started = time.perf_counter()
    baseline_path = OUT / 'causal_daily_rows.json'
    baseline_sha = sha(baseline_path)
    baseline = read(baseline_path)
    protocol_path = OUT / 'protocol.json'
    panel_path = ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt'
    reserved, old_panel = exclusions(read(protocol_path), panel_path.read_text(encoding='utf-8'))
    excluded = reserved if include_stage1_training else reserved | old_panel | set(baseline['excluded_episodes'])
    executor = load_executor()
    rows, sources, records, skipped = [], [], [], []
    observed_episodes = set()
    for path in sorted((ROOT / 'data/leader_semantics/16732748').glob('*.json.gz')):
        sem = read(path)
        episode, seat = int(sem['meta']['episode']), int(sem['meta']['seat'])
        assert episode == int(path.name.split('.')[0])
        observed_episodes.add(episode)
        if episode in excluded:
            skipped.append(episode)
            continue
        tape_path = ROOT / 'data/leader_tapes/16732748_56498734' / path.name
        tape = read(tape_path)
        assert (episode, seat) == (int(tape['episode']), int(tape['seat']))
        assert sem['meta']['cash_match'] and len(sem['days']) == 30
        exact = executor.TilePlanView(executor.Target(sem)).to_dict()
        strict = strict_input(extract_game(sem, exact)[0])
        metadata = dict(episode=episode, seat=seat, submission=56498734, family='DSM',
                        source=path.relative_to(ROOT).as_posix(), source_format='compact_semantics')
        for day in range(6, 30):
            observed_shops = [shop['shop'] for shop in sem['shops'] if int(shop['reveal_day']) <= day]
            assert observed_shops == tape['shops'][:min(8, day // 3)]
            features = features_from_prefix(sem['days'][:day], sem['days'][day]['board'],
                                            sem['days'][day]['cash_start'], observed_shops)
            check_features(features, sem, exact, day)
            target = deepcopy(strict['days'][day])
            target.pop('day')
            end = target.pop('end_occupancy_counts')
            target['end_crop_counts'] = end['crops'] if end else None
            target['end_animal_counts'] = end['animals'] if end else None
            target['owned_quadrants'] = [q for q in ('NW', 'NE', 'SW', 'SE') if q == 'NW' or exact['land_day'].get(q, 99) <= day]
            rows.append(dict(meta=metadata.copy(), day=day, features=features, target=target, row_id=len(rows)))
        record_sources = [dict(path=p.relative_to(ROOT).as_posix(), sha256=sha(p)) for p in (path, tape_path)]
        sources.extend(record_sources)
        records.append(dict(episode=episode, seat=seat, sources=record_sources, cash_match=True))

    modern_ids = {r['meta']['episode'] for r in rows}
    baseline_ids = {r['meta']['episode'] for r in baseline['rows']}
    assert not (modern_ids | baseline_ids) & excluded
    assert not modern_ids & baseline_ids
    limits = [
        'Prices, private seeds/shed/unit inventories and opponent farms are absent; represented by null.',
        'Current morning hands are zero after the engine daily reset. Future hands_present is a label only.',
        'Compact market, animals.bought and hires_arrived fields are shifted by the source extractor; not used as features.',
        'Day 29 has no observed ending boundary; ending counts and crop disappearance are null, not fabricated.',
        'Supervision uses actual same-day type changes and observed retirement; future first-harvest timing is excluded.',
        'Source episode, submission and coordinates are offline provenance only, never model features.',
    ]
    holdout = dict(protocol_sha256=sha(protocol_path), stage1_panel_sha256=sha(panel_path),
        reserved_recorded_episodes=len(reserved), stage1_episodes=len(old_panel),
        shared_source_alias_rule='Exclude episode identity across both seats and every source; semantic filename, semantic metadata and tape metadata must agree.',
        modern_corpus_reserved_overlap=sorted(observed_episodes & reserved),
        training_reserved_overlap=sorted((modern_ids | baseline_ids) & reserved),
        training_stage1_overlap=sorted((modern_ids | baseline_ids) & old_panel))
    if include_stage1_training:
        holdout['stage1_reuse_authorization'] = ('Explicitly authorized for stage-2 training. Earlier DSM40 '
            'is no longer independent validation for a policy trained on this file; all new protocol183 remain excluded.')
    modern = dict(schema_version=1, feature_time='start of day before any current-day action',
        label_time='successful current-day tile changes and observed two-night retirement',
        feature_limitations=limits, excluded_episodes=sorted(excluded), training_games=len(modern_ids),
        training_seats=len(records), rows=rows, sources=sources, holdout_audit=holdout)
    combined = deepcopy(baseline)
    combined['rows'] = deepcopy(rows) + deepcopy(baseline['rows'])
    for row_id, row in enumerate(combined['rows']):
        row['row_id'] = row_id
    ordering = ('Modern submission 56498734 rows first, in ascending episode filename then day order; '
                'historical rows follow in their unchanged frozen relative order. Stable policy ties '
                'therefore prefer the modern submission family; IDs remain offline metadata only.')
    combined.update(training_games=len(baseline_ids | modern_ids), training_seats=baseline['training_seats'] + len(records),
        feature_limitations=list(baseline['feature_limitations']) + limits, excluded_episodes=sorted(excluded),
        sources=list(baseline['sources']) + sources, holdout_audit=holdout,
        extension=dict(baseline_path=baseline_path.relative_to(ROOT).as_posix(), baseline_sha256=baseline_sha,
                       baseline_rows=len(baseline['rows']), modern_rows=len(rows), modern_seats=len(records),
                       deterministic_row_order=ordering))
    out.mkdir(parents=True, exist_ok=True)
    modern_suffix = 'modern100' if include_stage1_training else 'modern60'
    combined_suffix = '244' if include_stage1_training else '204'
    modern_path, combined_path = out / f'causal_daily_rows_{modern_suffix}.json', out / f'causal_daily_rows_{combined_suffix}.json'
    write(modern_path, modern)
    write(combined_path, combined)
    old_manifest = read(OUT / 'training_episodes.json')
    write(out / f'training_episodes_{modern_suffix}.json', dict(model_sha256=sha(modern_path),
        episodes=sorted(modern_ids), records=records, source_hashes=sources,
        excluded_episodes=sorted(excluded), holdout_audit=holdout), pretty=True)
    write(out / f'training_episodes_modern{combined_suffix}.json', dict(model_sha256=sha(combined_path),
        episodes=sorted(baseline_ids | modern_ids), records=records + old_manifest['records'],
        source_hashes=combined['sources'], excluded_episodes=sorted(excluded), holdout_audit=holdout,
        deterministic_row_order=ordering), pretty=True)
    audit = dict(schema_version=1, no_environment_transitions_executed=True,
        baseline_unchanged=(baseline_sha == sha(baseline_path)), baseline_sha256=baseline_sha,
        modern_model_sha256=sha(modern_path), combined_model_sha256=sha(combined_path),
        builder_sha256=sha(__file__), strict_extractor_sha256=sha(ROOT / 'scripts/semantic_tile_inputs_20260928.py'),
        target_adapter_sha256=sha(ROOT / 'agents/mgt_lead_kb115lt.py'), protocol=holdout,
        modern_corpus_episodes=len(observed_episodes), skipped_episodes=skipped,
        modern_training_episodes=len(modern_ids), modern_training_seats=len(records), modern_rows=len(rows),
        combined_training_episodes=combined['training_games'], combined_training_seats=combined['training_seats'],
        combined_rows=len(combined['rows']), checked_prefix_states=len(rows), null_feature_fields=list(NULL_FIELDS),
        deterministic_row_order=ordering,
        elapsed_seconds=time.perf_counter() - started, sources=sources,
        feature_contract='Only history[:day], current board/cash and already revealed shops reach features_from_prefix.',
        feature_limitations=limits)
    assert audit['baseline_unchanged']
    write(out / ('modern_training_audit_modern100.json' if include_stage1_training else 'modern_training_audit.json'), audit, pretty=True)
    return {k: audit[k] for k in ('baseline_unchanged', 'modern_training_seats', 'modern_rows',
            'combined_training_seats', 'combined_rows', 'checked_prefix_states', 'elapsed_seconds')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=OUT)
    parser.add_argument('--include-stage1-training', action='store_true',
        help='Explicit stage-2 authorization: reuse earlier DSM40 as training; retain all new protocol183 holdouts. Writes separate modern100/244 files.')
    args = parser.parse_args()
    print(json.dumps(build(args.out, args.include_stage1_training)))
