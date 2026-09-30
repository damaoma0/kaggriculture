"""Build a provenance-checked semantic study from existing verified traces.

Only exact submissions rated >=3000 in the saved leaderboard snapshot qualify.
Every p2750 benchmark episode is excluded in full from the study corpus. The
snapshot is timestamped, not silently treated as a live rating. No downloads,
credentials, submissions, replay selection by profit or future-shop features.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/semantic_architecture_20260924'
REVIEW = ROOT / 'results/fresh/leader_opening_review_20260924_01a0'
TRACES = ROOT / 'results/fresh/coherent_opening_20260924_01a0'


def read(path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8') as handle:
        return json.load(handle)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(tile):
    if not isinstance(tile, dict):
        return None
    if tile.get('crop'):
        return tile['crop'], tile['planted_day']
    if tile.get('animal'):
        return tile['animal'], tile['placed_day']
    return None


def cohort_counts(farm):
    return dict(Counter(f'{key[0]}:{key[1]}' for row in farm['tiles']
                        for tile in row if (key := identity(tile))))


def study_trace(trace, rules):
    from semantic_strategy import maintenance
    by_day = defaultdict(list)
    for job in trace['jobs']:
        by_day[int(job['day'])].append(job)
    daily = []
    services = []
    for snapshot in trace['daily']:
        day = int(snapshot['day'])
        if day > 29:
            continue
        jobs = by_day[day]
        shop_counts = Counter(snapshot['shops'])
        demand = Counter(p for shop in snapshot['shops'] for p in rules.SHOPS[shop])
        planted, placed = Counter(), Counter()
        done = set()
        retired = set()
        for job in jobs:
            op = job['command'][0]
            before, after = identity(job['before']), identity(job['after'])
            if op == 'PLANT' and after:
                planted[after[0]] += 1
            if op == 'PLACE' and after and after != before:
                placed[after[0]] += 1
            if before:
                done.add((tuple(job['tile']), before, op))
                if before != after:
                    retired.add((tuple(job['tile']), before))
        daily.append(dict(episode=trace['episode'], seat=trace['seat'], day=day,
            features=dict(shop_prefix=list(snapshot['shops']), shop_counts=dict(shop_counts),
                demand_shop_counts=dict(demand), cohorts=cohort_counts(snapshot['farm']),
                cash=snapshot['cash'], seeds=snapshot['private']['seeds'],
                shed=snapshot['private']['shed']),
            labels=dict(successful_plants=dict(planted), successful_placements=dict(placed)),
            label_window='this day only; no future shops in features'))
        # Start-of-day assets have an unambiguous maintenance denominator. New
        # intraday cohorts are represented by planting labels, not guessed ages.
        for y, row in enumerate(snapshot['farm']['tiles']):
            for x, tile in enumerate(row):
                key = identity(tile)
                if not key:
                    continue
                product = rules.ANIMALS[key[0]]['product'] if key[0] in rules.ANIMALS else key[0]
                default, omissions = maintenance(tile, day, rules)
                for cmd in default:
                    if cmd[0] not in ('WATER', 'FERTILIZE', 'FEED', 'CARE'):
                        continue
                    observed = ((x, y), key, cmd[0]) in done
                    services.append(dict(episode=trace['episode'], seat=trace['seat'],
                        day=day, tile=[x, y], species=key[0], planted_or_placed_day=key[1],
                        op=cmd[0], demand_shops=demand[product], observed=observed,
                        classification=('observed' if observed else
                            'asset_removed_same_day' if ((x, y), key) in retired else
                            'not_observed_intent_unknown')))
    return daily, services


def main():
    from cumulative_engine_profiles import ENGINE as rules, ENGINE_SHA256
    from semantic_strategy import maintenance_skip_effect
    snapshot_path = REVIEW / 'snapshot.json'
    snapshot = read(snapshot_path)
    eligible = {int(sub['id']): dict(team=team['team'], team_id=team['team_id'],
                  score=float(sub['score'])) for team in snapshot['inventory']
                for sub in team['selected'] if float(sub['score']) >= 3000}
    exact = {}
    for team in snapshot['inventory']:
        for sub, episodes in team['episodes'].items():
            for episode in episodes:
                for agent in episode['agents']:
                    if agent.get('submission_id') is not None:
                        key = (int(episode['id']), int(agent['seat']))
                        value = int(agent['submission_id'])
                        if key in exact and exact[key] != value:
                            raise ValueError('conflicting_submission_provenance')
                        exact[key] = value
    benchmark_path = ROOT / 'data/ladder_panel/p2750/index.json'
    benchmark = read(benchmark_path)
    games = benchmark['games']
    benchmark_episodes = {int(e) for e in games}
    registry = []
    for folder in (TRACES / 'extraction/full', TRACES / 'new_sources/traces',
                   OUT / 'leader_families'):
        if not (folder / 'index.json').exists():
            continue
        for meta in read(folder / 'index.json'):
            registry.append((folder / (meta.get('path') or meta['trace']), meta))
    decisions, service_rows, donors, exclusions = [], [], [], Counter()
    seen = set()
    for path, meta in registry:
        episode, seat = int(meta['episode']), int(meta['seat'])
        if (episode, seat) in seen:
            exclusions['duplicate_seat'] += 1
            continue
        if episode in benchmark_episodes:
            exclusions['benchmark_episode_overlap'] += 1
            continue
        submission = meta.get('submission') or exact.get((episode, seat))
        if submission not in eligible:
            exclusions['no_qualifying_exact_submission_rating'] += 1
            continue
        sha = digest(path)
        if meta.get('trace_sha256') and sha != meta['trace_sha256']:
            raise ValueError(f'trace_hash_mismatch: {path}')
        if meta.get('transitions') != 719:
            raise ValueError(f'incomplete_trace: {path}')
        trace = read(path)
        if (int(trace['episode']), int(trace['seat'])) != (episode, seat):
            raise ValueError('trace_identity_mismatch')
        if trace['source_sha256'] != meta['source_sha256']:
            raise ValueError('trace_source_hash_mismatch')
        seen.add((episode, seat))
        rows, service = study_trace(trace, rules)
        decisions.extend(dict(submission=submission, **row) for row in rows)
        service_rows.extend(service)
        donors.append(dict(episode=episode, seat=seat, submission=submission,
                           path=str(path.relative_to(ROOT)), sha256=sha, **eligible[submission]))
    service_summary = defaultdict(lambda: Counter())
    for row in service_rows:
        # Association only: day, phase, stock and layout still confound shop groups.
        key = f"{row['species']}:{row['op']}:shops={'0' if row['demand_shops']==0 else '1+'}"
        service_summary[key]['opportunities'] += 1
        service_summary[key][row['classification']] += 1
    blocks = defaultdict(Counter)
    block_features = {}
    for row in decisions:
        key = (row['episode'], row['seat'], row['day']//3*3)
        block_features.setdefault(key, row['features'])
        blocks[key].update(row['labels']['successful_plants'])
        blocks[key].update(row['labels']['successful_placements'])
    quantities = defaultdict(list)
    for key, counts in blocks.items():
        for species in (*rules.CROPS, *rules.ANIMALS):
            product = rules.ANIMALS[species]['product'] if species in rules.ANIMALS else species
            demand = block_features[key]['demand_shop_counts'].get(product, 0)
            quantities[f'day{key[2]}:{species}:demand_shops={demand}'].append(counts[species])
    quantity_summary = {key:dict(games=len(v), mean=sum(v)/len(v), minimum=min(v), maximum=max(v))
                        for key,v in sorted(quantities.items())}
    cow = rules._new_animal('COW', 0)
    wheat = rules._new_plant('WHEAT', 0, 24)
    # State actually attainable after watering on planting day.
    wheat.update(consecutive_unwatered=0, watered_today=False)
    skip_examples = [maintenance_skip_effect(cow,0,'CARE',rules),
                     maintenance_skip_effect(wheat,1,'WATER',rules),
                     maintenance_skip_effect(rules._new_plant('WHEAT',0,24),0,'WATER',rules)]
    profiles = read(REVIEW / 'profiles.json')
    opening_rows = []
    for episode, profile in profiles.items():
        if int(episode) in benchmark_episodes:
            continue
        for seat, values in profile['per_seat'].items():
            sub = exact.get((int(episode), int(seat)))
            if sub in eligible:
                day6 = next((d for d in values['daily'] if d['day'] == 6), None)
                if day6:
                    opening_rows.append(dict(episode=int(episode), seat=int(seat),
                        submission=sub, **eligible[sub], counts=day6['counts'],
                        cohorts=day6['cohorts'], source='verified opening profiles'))
    # The inherited panel uses team rating, not necessarily that recorded
    # submission's own rating. Preserve this distinction explicitly.
    benchmark_summary = dict(games=len(games), distinct_teams=len({r['band_team_id'] for r in games.values()}),
        source_counts=dict(Counter(r['source'] for r in games.values())),
        min_team_rating=min(r['band_score'] for r in games.values()),
        max_team_rating=max(r['band_score'] for r in games.values()),
        exact_submission_rating_verified=False, index_sha256=digest(benchmark_path),
        meta=benchmark['meta'], evaluation_type='fixed recorded opponent; development regression panel')
    payload = dict(schema_version=1, engine_sha256=ENGINE_SHA256,
        rating_snapshot_utc=snapshot['captured_utc'],
        snapshot_sha256=digest(snapshot_path), eligible_submissions=eligible,
        source_hashes={name:digest(ROOT / name) for name in (
            'scripts/semantic_strategy.py', 'scripts/build_semantic_strategy_study.py',
            'scripts/fragments/continuation_executor.py',
            'scripts/fragments/continuation_projection.py',
            'scripts/fragments/segment_job_executor_v3.py')},
        donors=donors, excluded=dict(exclusions), benchmark=benchmark_summary,
        opening_rows=opening_rows,
        study=dict(traces=len(donors), distinct_episodes=len({d['episode'] for d in donors}),
                   daily_decisions=len(decisions), maintenance_opportunities=len(service_rows),
                   service_by_product_and_demand=dict(service_summary),
                   three_day_quantity_groups=quantity_summary),
        skip_examples=skip_examples,
        limitations=['Missing expert service does not identify an intentional skip.',
            'Counts are observational and clustered by episode; no causal shop response is estimated.',
            'Unequal source-family sample sizes require family-stratified validation.',
            'The 185-game panel was used previously; it is not untouched qualification.',
            'No complete new policy, benchmark uplift or Elo claim is established.'])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'study.json').write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    with gzip.open(OUT / 'decisions.json.gz', 'wt', encoding='utf-8') as handle:
        json.dump(dict(decisions=decisions, maintenance=service_rows), handle, separators=(',', ':'))
    print(json.dumps({k: payload[k] for k in ('rating_snapshot_utc', 'excluded', 'benchmark')}))
    print(json.dumps(dict(study={k:v for k,v in payload['study'].items()
                                  if k not in ('service_by_product_and_demand','three_day_quantity_groups')},
                          submissions=sorted({d['submission'] for d in donors}),
                          opening_rows=len(opening_rows))))


if __name__ == '__main__':
    main()
