"""Read verified DSM recordings; audit openings and emit causal daily count rows.

No environment transitions are executed. Features are day-start public own-farm
state, own private inputs and already revealed shops. Source identity and label
suffixes never enter features. Death labels identify observed retirement, not a
judgment that losing an animal was economically wrong.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/fresh/coherent_opening_20260924_01a0'
OUT = ROOT / 'results/fresh/semantic_strategy_20260928'
ANIMALS = {'COW', 'SHEEP', 'GOOSE'}
ONGOING = {'STRAWBERRY', 'TOMATO'}


def read(path):
    with gzip.open(path, 'rt', encoding='utf-8') if str(path).endswith('.gz') else open(path, encoding='utf-8') as f:
        return json.load(f)


def compact(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def clean(counter):
    return dict(sorted((k, v) for k, v in counter.items() if v))


def tiles(farm):
    return {y * 10 + x: t for y, row in enumerate(farm['tiles']) for x, t in enumerate(row) if isinstance(t, dict)}


def species(tile):
    return tile.get('animal') if isinstance(tile, dict) else None


def crop(tile):
    return tile.get('crop') if isinstance(tile, dict) and tile.get('kind') == 'PLANT' else None


def cohorts(farm):
    crops, animals, structures = Counter(), Counter(), Counter()
    for tile in tiles(farm).values():
        if crop(tile):
            crops[crop(tile), int(tile['planted_day'])] += 1
        if species(tile):
            animals[species(tile), int(tile['placed_day'])] += 1
        if tile.get('kind') in ('PASTURE', 'COOP'):
            structures[tile['kind']] += 1
    return {
        'own_crop_cohorts': [dict(crop=c, birth=b, count=n) for (c, b), n in sorted(crops.items())],
        'own_animal_cohorts': [dict(species=c, birth=b, count=n) for (c, b), n in sorted(animals.items())],
        'own_structures': clean(structures),
        'cash': farm['money'], 'owned_quadrants': list(farm['unlocked_quadrants']),
        'hands': len(farm['hands']),
    }


def trace_rows(trace, metadata):
    daily = trace['daily']
    jobs = defaultdict(list)
    for job in trace['jobs']:
        jobs[int(job['day'])].append(job)
    result = []
    retire = defaultdict(Counter)
    for day in range(29):
        before, after = tiles(daily[day]['farm']), tiles(daily[day + 1]['farm'])
        for tile, value in before.items():
            if species(value) and species(after.get(tile)) != species(value):
                # Two unfed nights remove a physically present animal. This
                # supervision label starts on the first night, one day earlier.
                retire[max(0, day - 1)][species(value)] += 1
    for day in range(30):
        start, end = daily[day], daily[day + 1]
        before, after = tiles(start['farm']), tiles(end['farm'])
        target = {key: Counter() for key in ('plant_counts', 'build_counts', 'remove_structure_counts',
            'animal_add_counts', 'animal_exit_counts', 'crop_end_counts', 'crop_remove_counts')}
        for job in jobs[day]:
            old, new = job.get('before'), job.get('after')
            if job['job'] == 'unit_plant':
                target['plant_counts'][crop(new)] += 1
            elif job['job'] == 'unit_harvest' and crop(old) and not crop(new):
                target['crop_end_counts'][crop(old)] += 1
            elif job['job'] == 'unit_dig' and crop(old):
                target['crop_remove_counts'][crop(old)] += 1
            if species(new) and species(new) != species(old):
                target['animal_add_counts'][species(new)] += 1
        for tile, value in after.items():
            kind = value.get('kind')
            if kind in ('COOP', 'PASTURE') and before.get(tile, {}).get('kind') != kind:
                target['build_counts'][kind] += 1
        for tile, value in before.items():
            kind = value.get('kind')
            if kind in ('COOP', 'PASTURE') and after.get(tile, {}).get('kind') != kind:
                target['remove_structure_counts'][kind] += 1
            if species(value) and species(after.get(tile)) != species(value):
                target['animal_exit_counts'][species(value)] += 1
        end_crops = Counter(crop(t) for t in after.values() if crop(t))
        disappear = Counter(crop(t) for t in before.values() if crop(t))
        disappear.update(target['plant_counts'])
        disappear.subtract(target['crop_end_counts'])
        disappear.subtract(target['crop_remove_counts'])
        disappear.subtract(end_crops)
        assert min(disappear.values(), default=0) >= 0, (metadata, day, disappear)
        target = {k: clean(v) for k, v in target.items()}
        target.update(crop_disappear_counts=clean(disappear), animal_retire_counts=clean(retire[day]),
            hands=sum(o == ['HIRE'] for orders in trace['market_success_by_order'][day * 24:min(719, (day + 1) * 24)] for o in orders),
            land_add_count=len(end['farm']['unlocked_quadrants']) - len(start['farm']['unlocked_quadrants']),
            owned_quadrants=list(end['farm']['unlocked_quadrants']), end_crop_counts=clean(end_crops),
            end_animal_counts=clean(Counter(species(t) for t in after.values() if species(t))))
        features = cohorts(start['farm'])
        features.update(shops_prefix=list(start['shops']), seeds=dict(start['private']['seeds']),
            shed=dict(start['private']['shed']), inventories=[dict(x) for x in start['private']['inventories']],
            prices=None, opponent_crop_cohorts=None, opponent_animal_cohorts=None)
        result.append(dict(meta=dict(metadata), day=day, features=features, target=target))
    return result


def modal(values):
    histogram = Counter(compact(v) for v in values)
    return {'unique': len(histogram), 'modal_count': max(histogram.values(), default=0), 'n': len(values)}


def audit_group(records):
    output = []
    for day in range(13):
        rows = [r['rows'][day] for r in records]
        board_stat = modal([r['boards'][day] for r in records])
        by_shops = defaultdict(list)
        for row in rows:
            by_shops[tuple(row['features']['shops_prefix'])].append(row['target'])
        cash = [r['features']['cash'] for r in rows]
        asked = [sum(bool(o) and o[0] == 'HIRE' for a in r['actions'][day * 24:(day + 1) * 24] for o in a.get('market', [])[:10]) for r in records]
        output.append(dict(day=day, board=board_stat, semantic=modal([r['target'] for r in rows]),
            raw_actions=modal([r['actions'][day * 24:(day + 1) * 24] for r in records]),
            cash=dict(min=min(cash), median=statistics.median(cash), max=max(cash)),
            requested_hires=sum(asked), successful_hires=sum(r['target']['hands'] for r in rows),
            shop_conditional_modal_count=sum(modal(v)['modal_count'] for v in by_shops.values()),
            shop_prefix_groups=len(by_shops)))
    first_difference = next((step for step in range(719) if len({compact(r['actions'][step]) for r in records}) > 1), None)
    return dict(games=len(records), all_identical_raw_prefix_steps=first_difference, days=output)


def current_records():
    """Current 100-game compact corpus, for descriptive audit only."""
    from semantic_tile_inputs_20260928 import load_executor, extract_game, strict_input
    executor = load_executor()
    records = []
    for path in sorted((ROOT / 'data/leader_semantics/16732748').glob('*.json.gz')):
        sem = read(path)
        tape_path = ROOT / 'data/leader_tapes/16732748_56498734' / path.name
        if not tape_path.exists():
            continue
        tape = read(tape_path)
        exact = executor.TilePlanView(executor.Target(sem)).to_dict()
        extracted = strict_input(extract_game(sem, exact)[0])
        rows = [dict(features=dict(cash=s['cash_start'], shops_prefix=tape['shops'][:min(8, day // 3)]),
                     target=extracted['days'][day]) for day, s in enumerate(sem['days'])]
        records.append(dict(rows=rows, boards=[s['board'] for s in sem['days']], actions=tape['actions'],
            meta=dict(episode=sem['meta']['episode'], seat=sem['meta']['seat'])))
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=OUT)
    parser.add_argument('--audit-only', action='store_true', help='Preserve the frozen training file exactly.')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    excluded = {int(x.split(':')[-1]) for x in (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().strip().split(',')}
    protocol_path = OUT / 'protocol.json'
    protocol = read(protocol_path) if protocol_path.exists() else None
    reserved = [] if protocol is None else (protocol['development']['recorded']
        + protocol['qualification']['recorded'] + protocol['recorded_reserve'])
    reserved_ids = {int(row['episode']) for row in reserved}
    excluded.update(reserved_ids)
    records, seen, provenance = [], set(), []
    for folder in (BASE / 'extraction/full', BASE / 'new_sources/traces'):
        for info in read(folder / 'index.json'):
            if info.get('team') != 'DSM':
                continue
            path = folder / (info.get('path') or info['trace'])
            trace = read(path)
            key = (trace['episode'], trace['seat'])
            assert key == (info['episode'], info['seat'])
            if key in seen:
                continue
            seen.add(key)
            metadata = dict(episode=key[0], seat=key[1], submission=trace.get('submission', info.get('submission')),
                family='DSM', source=str(path.relative_to(ROOT)).replace('\\', '/'))
            rows = trace_rows(trace, metadata)
            boards = [[(t.get('kind'), t.get('crop'), t.get('animal')) if isinstance(t, dict) and t.get('kind') != 'WEED' else (None if isinstance(t, dict) else t)
                for line in day['farm']['tiles'] for t in line] for day in trace['daily']]
            records.append(dict(rows=rows, boards=boards, actions=trace['actions'], meta=metadata))
            provenance.append(dict(path=metadata['source'], sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    training = [row for r in records if r['meta']['episode'] not in excluded for row in r['rows'] if row['day'] >= 6]
    for i, row in enumerate(training):
        row['row_id'] = i
    dataset = dict(schema_version=1, feature_time='start of day before any current-day action',
        label_time='successful current-day changes; observed two-night retirement labelled at first unfed day',
        feature_limitations=['Prices and opponent public farms are absent in these trace archives; represented by null.',
            'Day 29 ending state is the final executed transition, not an unexecuted midnight.',
            'Source IDs are offline metadata; not model features. Future shop suffixes and coordinates are absent.'],
        excluded_episodes=sorted(excluded), training_games=len({r['meta']['episode'] for r in training}),
        training_seats=len({(r['meta']['episode'], r['meta']['seat']) for r in training}), rows=training, sources=provenance,
        holdout_audit=dict(protocol_sha256=hashlib.sha256(protocol_path.read_bytes()).hexdigest() if protocol else None,
            reserved_recorded_episodes=len(reserved_ids), shared_source_alias_rule='episode identity excludes both self-play seats; filename/index/trace identities agree',
            matching_reserved_source_episodes=sorted(reserved_ids & {r['meta']['episode'] for r in records}),
            training_reserved_overlap=sorted(reserved_ids & {r['meta']['episode'] for r in training})))
    if not args.audit_only:
        (args.out / 'causal_daily_rows.json').write_text(json.dumps(dataset, separators=(',', ':')), encoding='utf-8')
    audit = dict(schema_version=1, rich_corpus=audit_group(records), training_rows=len(training),
        current_100_corpus=audit_group(current_records()),
        board_definition='Type occupancy with weeds treated as empty; no ages/yields/care bits',
        training_seats=dataset['training_seats'], excluded_episode_count=len(excluded), sources=provenance)
    (args.out / 'opening_audit.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
    print(json.dumps({k: audit[k] for k in ('training_rows', 'training_seats', 'excluded_episode_count')}))


if __name__ == '__main__':
    main()
