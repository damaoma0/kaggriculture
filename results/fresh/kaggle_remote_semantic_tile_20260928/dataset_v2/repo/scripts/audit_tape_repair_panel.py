"""Audit frozen repair qualification and summarize paired, world-clustered results."""
import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import random
import statistics

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / 'results/fresh/tape_repair_20260924_01a0'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def percentile(values, q):
    values = sorted(values)
    i = (len(values) - 1) * q
    low = int(i)
    return values[low] + (values[min(low + 1, len(values) - 1)] - values[low]) * (i - low)


def distribution(values):
    if not values:
        return None
    return dict(n=len(values), mean=statistics.mean(values), median=statistics.median(values),
                p95=percentile(values, .95), minimum=min(values), maximum=max(values))


def comparison(rows, reference):
    deltas = [r[f'delta_{reference}'] for r in rows]
    clustered = defaultdict(list)
    for r in rows:
        clustered[r['world']].append(r[f'delta_{reference}'])
    means = [statistics.mean(v) for v in clustered.values()]
    rng = random.Random(72416093)
    bootstrap = [statistics.mean(rng.choices(means, k=len(means))) for _ in range(10000)]
    deficit_before = sum(max(0, -r[reference]) for r in rows)
    deficit_after = sum(max(0, -r['candidate']) for r in rows)
    return dict(matchups=len(rows), independent_worlds=len(means), better=sum(d > 0 for d in deltas),
                equal=sum(d == 0 for d in deltas), worse=sum(d < 0 for d in deltas),
                margin_gain=distribution(deltas), world_cluster_bootstrap_95=[percentile(bootstrap, .025), percentile(bootstrap, .975)],
                own_cash_gain=distribution([r[f'own_cash_delta_{reference}'] for r in rows]),
                rival_cash_gain=distribution([r[f'rival_cash_delta_{reference}'] for r in rows]),
                reference_wins=sum(r[reference] > 0 for r in rows), candidate_wins=sum(r['candidate'] > 0 for r in rows),
                reference_ties=sum(r[reference] == 0 for r in rows), candidate_ties=sum(r['candidate'] == 0 for r in rows),
                wins_gained=sum(r[reference] <= 0 < r['candidate'] for r in rows),
                wins_lost=sum(r['candidate'] <= 0 < r[reference] for r in rows),
                deficit_before=deficit_before, deficit_after=deficit_after,
                deficit_recovery_fraction=(deficit_before-deficit_after)/deficit_before if deficit_before else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--version', default='r3holdout24')
    ap.add_argument('--partial', action='store_true')
    args = ap.parse_args()
    folder = STUDY / args.version
    design = read(folder / 'design.json')
    manifest = read(folder / 'source_manifest.json')
    for name, expected in manifest['sha256'].items():
        assert sha256((folder / 'payload' / name).read_bytes()).hexdigest() == expected, name
    assert sha256((folder / 'run_panel.py').read_bytes()).hexdigest() == design['harness_sha256']
    assert manifest['sha256']['scripts/value_tape_repair_r3.py'] == design['policy_sha256']
    rows, checks, timings, banks, memory, durations = [], Counter(), defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(list)
    funnel, cases, decision_timings = Counter(), [], defaultdict(list)
    full_cases = [s for s in design['specs'] if all((folder/'arms'/f'{s["id"]}-{a}.json').exists() for a in design['arms'])]
    if not args.partial:
        assert len(full_cases) == len(design['specs']), (len(full_cases), len(design['specs']))
    for spec in full_cases:
        case = spec['id']
        arms = {a: read(folder/'arms'/f'{case}-{a}.json') for a in design['arms']}
        actions = {}
        for arm, row in arms.items():
            assert row['completed'] and row['ledger_verified'] and row['spec'] == spec
            assert not row['measured_bank_exhausted']
            assert row['cash'] - row['rival_cash'] == row['margin']
            for s, econ in enumerate(row['economics']):
                assert 3000 + sum(econ['revenue'].values()) - sum(econ['spend'].values()) == row['cash_by_seat'][s]
            assert not any(('error' in k.lower() or 'exception' in k.lower()) and v for k,v in row['native_telemetry'].items()), row['native_telemetry']
            actions[arm] = read(folder/'actions'/f'{case}-{arm}.json')
            assert all(len(a) == 719 for a in actions[arm])
            assert digest(actions[arm]) == row['actions_sha256']
            assert digest([[actions[arm][s][t] for s in range(2)] for t in range(288)]) == row['prefix_sha256']
            assert len(row['timings']) == 719
            expected_bank = 60 - sum(max(0, t['seconds'] - 1) for t in row['timings'])
            assert abs(expected_bank-row['remaining_overage_seconds']) < 1e-8
            checks['full_games'] += 1
            banks[arm].append(row['remaining_overage_seconds'])
            memory[arm].append(row['peak_rss_gib'])
            durations[arm].append(row['seconds'])
            timings[arm].extend(t['seconds'] for t in row['timings'] if t['searched'])
            if arm != 'baseline':
                decisions = [read(folder/'decisions'/f'{case}-{arm}-d{day}.json') for day in design['decisions']]
                assert [d['selected'] for d in decisions] == row['selected']
                assert all(d['planner_sha256'] == manifest['sha256']['scripts/'+('value_tape_repair_r3.py' if arm=='candidate' else 'value_tape_search_v9.py')] for d in decisions)
                for d in decisions:
                    checks['decisions'] += 1
                    decision_timings[arm].append(d['seconds'])
                    if arm != 'candidate':
                        continue
                    funnel['decisions'] += 1
                    funnel['timeouts'] += bool(d['timed_out'])
                    funnel['selected'] += d['selected'] is not None
                    alternatives = d['candidates'][1:]
                    funnel['original_candidates'] += sum(not c.get('repair_assets') for c in alternatives)
                    funnel['original_cohort_rejections'] += sum(bool(c.get('early_rejection')) for c in alternatives if not c.get('repair_assets'))
                    repairs = [c for c in alternatives if c.get('repair_assets')]
                    funnel['repair_candidates'] += len(repairs)
                    funnel['repair_scout_survived'] += sum(bool(c['predictions']) for c in repairs)
                    funnel['repair_fully_evaluated_eight'] += sum(c['fully_evaluated'] for c in repairs)
                    validation = d.get('repair_validation')
                    if validation:
                        funnel['robustness_validations'] += 1
                        funnel['robustness_admitted'] += validation['admitted']
                        funnel['robustness_vetoed'] += not validation['admitted']
                    if isinstance(d['selected'], list):
                        assert validation and validation['admitted'] and validation['fully_evaluated'] and not validation['timed_out']
                        assert len(validation['predictions']) == 16 and len(validation['stress']) == 16
                        assert not validation['protection_failures'] and not validation['missing_cohorts']
                        assert validation['stress_minimum_margin'] >= -validation['loss_budget']
                        funnel['repair_selected'] += 1
                    if d['selected'] is not None:
                        chosen = next(c for c in d['candidates'] if c['route'] == d['selected'])
                        assert chosen['admitted'] and chosen['fully_evaluated'] and not chosen['protection_failures']
                if all(s is None for s in row['selected']):
                    assert actions[arm] == actions['baseline'], (case, arm, 'unintervened actions changed')
                    checks['native_no_intervention_exact'] += 1
        assert len({r['prefix_sha256'] for r in arms.values()}) == 1, case
        checks['three_arm_prefixes_exact'] += 1
        if actions['candidate'] == actions['v9']:
            checks['candidate_v9_full_action_streams_exact'] += 1
        result = dict(id=case, world=spec['world'], opponent=spec['opponent'], seed=spec['seed'], shops=spec['shops'],
                      **{arm: row['margin'] for arm, row in arms.items()},
                      delta_v9=arms['candidate']['margin']-arms['v9']['margin'],
                      delta_baseline=arms['candidate']['margin']-arms['baseline']['margin'],
                      own_cash_delta_v9=arms['candidate']['cash']-arms['v9']['cash'],
                      rival_cash_delta_v9=arms['candidate']['rival_cash']-arms['v9']['rival_cash'],
                      own_cash_delta_baseline=arms['candidate']['cash']-arms['baseline']['cash'],
                      rival_cash_delta_baseline=arms['candidate']['rival_cash']-arms['baseline']['rival_cash'],
                      selected=arms['candidate']['selected'], v9_selected=arms['v9']['selected'],
                      repair_execution=arms['candidate']['repair_execution'])
        rows.append(result)
        if result['delta_v9'] != 0 or any(isinstance(s,list) for s in result['selected']):
            cases.append(result)
    if not rows:
        print('No completed three-arm matchups yet.');return
    grouped = {op: [r for r in rows if r['opponent']==op] for op in ('v56','original_m1')}
    summary = dict(complete=len(full_cases)==len(design['specs']), planned_matchups=len(design['specs']),
                   policy_sha256=design['policy_sha256'], harness_sha256=design['harness_sha256'],
                   frozen_files_verified=len(manifest['sha256']), checks=dict(checks), funnel=dict(funnel),
                   comparisons={ref:{'all':comparison(rows,ref), **{op:comparison(rr,ref) for op,rr in grouped.items() if rr}} for ref in ('v9','baseline')},
                   timing={a:dict(turn_including_search=distribution(timings[a]), planner=distribution(decision_timings[a]),
                                  remaining_bank=distribution(banks[a]), game_seconds=distribution(durations[a]),
                                  rss_gib=distribution(memory[a])) for a in design['arms']},
                   changed_cases=cases, rows=rows,
                   uncertainty_note='Resample whole shop worlds, keeping both opponents together. Percentile bootstrap is descriptive, particularly with rare interventions; this is not an Elo estimate.',
                   timing_note='Local synchronous engine timings, including import and initialization; at most two game workers on the shared laptop, gated by available memory. Competition sandbox not certified.')
    destination = folder / ('audit_partial.json' if args.partial else 'audit.json')
    destination.write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('rows','timing')},indent=2))


if __name__ == '__main__':
    main()
