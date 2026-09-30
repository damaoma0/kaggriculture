"""Mechanical paired audit for the frozen v9-lite release panel.

Run only after the qualification harness has completed all 384 expected games:
    python scripts/analyze_tape_lite_release_20260924.py
Uses the standard library only; writes summary.json and paired.json beside design.json.
"""
from __future__ import annotations

import json
import math
import re
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / 'results/fresh/coherent_switch_20260924_01a0/release_lite_qualification'
ARMS = ('baseline', 'y3', 'v9lite')
CONTRASTS = (('v9lite', 'baseline'), ('v9lite', 'y3'), ('y3', 'baseline'))
BOOTSTRAP_REPLICATES = 10_000
BOOTSTRAP_SEED = 20260924
INITIAL_CASH = 3_000


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def pct(sorted_values, q):
    """Linearly interpolated quantile, q in [0,1]."""
    if not sorted_values:
        raise ValueError('empty percentile input')
    pos = (len(sorted_values) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_values[lo]
    return sorted_values[lo] * (hi - pos) + sorted_values[hi] * (pos - lo)


def validated_load():
    design_path = PANEL / 'design.json'
    games_dir = PANEL / 'games'
    if not design_path.is_file() or not games_dir.is_dir():
        raise SystemExit(f'Expected release panel not found: {PANEL}')
    design = load_json(design_path)
    assert tuple(design['arms']) == ARMS, design.get('arms')
    specs = design['specs']
    assert len(specs) == 128, f'expected 128 specs, found {len(specs)}'
    expected_specs = {s['id']: s for s in specs}
    assert len(expected_specs) == len(specs), 'duplicate spec IDs in design'
    expected_names = {f'{s["id"]}-{arm}.json' for s in specs for arm in ARMS}
    actual_names = {p.name for p in games_dir.glob('*.json')}
    missing = sorted(expected_names - actual_names)
    extra = sorted(actual_names - expected_names)
    if missing or extra or len(actual_names) != 384:
        raise SystemExit(f'panel incomplete/mismatched: expected 384 records; found {len(actual_names)}, missing={len(missing)}, extra={len(extra)}')

    games = {}
    # Check every record's completed marker and identity before analyzing metrics.
    for name in sorted(expected_names):
        row = load_json(games_dir / name)
        spec_id, arm = name[:-5].rsplit('-', 1)
        if row.get('completed') is not True:
            raise SystemExit(f'incomplete game: {name}')
        if row.get('arm') != arm or row.get('spec', {}).get('id') != spec_id:
            raise SystemExit(f'filename/record mismatch: {name}')
        expected = expected_specs[spec_id]
        got = row['spec']
        if got != expected:
            raise SystemExit(f'design/record spec mismatch: {name}')
        key = (spec_id, arm)
        if key in games:
            raise SystemExit(f'duplicate record: {name}')
        games[key] = row
    assert len(games) == 384

    # Global data-integrity gates. Do not write reports until all gates pass.
    for (spec_id, arm), row in games.items():
        cash = row['cash']
        ledgers = row['ledgers']
        if len(cash) != 2 or len(ledgers) != 2:
            raise SystemExit(f'invalid two-seat cash/ledger data: {spec_id}/{arm}')
        if row.get('ledger_verified') != [True, True]:
            raise SystemExit(f'ledger verification flag failed: {spec_id}/{arm}')
        for hash_field in ('action_sha256', 'prefix_sha256'):
            digest = row.get(hash_field)
            if not isinstance(digest, str) or re.fullmatch(r'[0-9a-fA-F]{64}', digest) is None:
                raise SystemExit(f'missing or invalid {hash_field}: {spec_id}/{arm}')
        for numeric_field in ('seconds', 'load_seconds', 'bank_remaining', 'max_action_seconds'):
            value = row.get(numeric_field)
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise SystemExit(f'missing/non-finite {numeric_field}: {spec_id}/{arm}: {value!r}')
        if row['bank_remaining'] <= 0:
            raise SystemExit(f'bank is not positive: {spec_id}/{arm}: {row["bank_remaining"]}')
        timings = row.get('timings')
        if not isinstance(timings, list) or len(timings) != 719 or any(
                not isinstance(t, (int, float)) or not math.isfinite(t) or t < 0 for t in timings):
            raise SystemExit(f'missing/non-finite per-call timings: {spec_id}/{arm}')
        expected_bank = 60.0 - sum(max(0.0, float(t) - 1.0) for t in timings)
        if not math.isclose(float(row['bank_remaining']), expected_bank, rel_tol=0, abs_tol=1e-7):
            raise SystemExit(f'bank does not reconcile to per-call timings: {spec_id}/{arm}')
        if not math.isclose(float(row['seconds']), sum(timings), rel_tol=1e-10, abs_tol=1e-7):
            raise SystemExit(f'game runtime does not reconcile to per-call timings: {spec_id}/{arm}')
        if not math.isclose(float(row['max_action_seconds']), max(timings), rel_tol=1e-10, abs_tol=1e-7):
            raise SystemExit(f'max action time does not reconcile to per-call timings: {spec_id}/{arm}')
        for seat in (0, 1):
            ledger = ledgers[seat]
            reconciled = INITIAL_CASH + sum(ledger['revenue'].values()) - sum(ledger['spend'].values())
            if reconciled != cash[seat]:
                raise SystemExit(f'ledger arithmetic mismatch: {spec_id}/{arm}/seat{seat}: {reconciled} != {cash[seat]}')
        if arm == 'v9lite':
            report = row.get('report')
            required_report_keys = {'decisions', 'switches', 'seconds', 'budgets', 'errors', 'warm'}
            if not isinstance(report, dict) or not required_report_keys.issubset(report):
                raise SystemExit(f'missing/malformed candidate report: {spec_id}: {report!r}')
            if not isinstance(report['decisions'], list) or not isinstance(report['seconds'], list) or not isinstance(report['budgets'], list) or not isinstance(report['warm'], list):
                raise SystemExit(f'malformed candidate report arrays: {spec_id}')
            if (not isinstance(report['switches'], int) or report['switches'] < 0 or
                    not isinstance(report['errors'], int) or report['errors'] < 0):
                raise SystemExit(f'malformed candidate report counters: {spec_id}')
            if any(not isinstance(t, (int, float)) or not math.isfinite(t) or t < 0 for t in report['seconds']):
                raise SystemExit(f'missing/non-finite candidate search timings: {spec_id}')
            if any(not isinstance(b, (int, float)) or not math.isfinite(b) for b in report['budgets']):
                raise SystemExit(f'missing/non-finite candidate search budgets: {spec_id}')
            errors = report.get('errors', 0)
            if errors != 0:
                raise SystemExit(f'candidate search error count is not zero: {spec_id}: {errors}')
        if row.get('error'):
            raise SystemExit(f'game reported an error: {spec_id}/{arm}: {row["error"]}')

    # Candidate must preserve Y3's exact pre-reveal action stream.
    prefix_checks = []
    no_switch_checks = []
    for spec in specs:
        v9 = games[(spec['id'], 'v9lite')]
        y3 = games[(spec['id'], 'y3')]
        prefix_equal = v9.get('prefix_sha256') == y3.get('prefix_sha256')
        if not prefix_equal:
            raise SystemExit(f'pre-288 action prefix differs from Y3: {spec["id"]}')
        prefix_checks.append(spec['id'])
        report = v9.get('report') or {}
        switches = report.get('switches', 0)
        if switches == 0:
            exact = v9.get('action_sha256') == y3.get('action_sha256') and v9['cash'] == y3['cash']
            if not exact:
                raise SystemExit(f'no-switch candidate does not match Y3 actions/cash: {spec["id"]}')
            no_switch_checks.append(spec['id'])
    return design, specs, games, prefix_checks, no_switch_checks


def values(row):
    own = int(row['cash'][int(row['spec']['seat'])])
    rival = int(row['cash'][1 - int(row['spec']['seat'])])
    return {'own_cash': own, 'competitive_margin': own - rival}


def own_ledger(row):
    return row['ledgers'][int(row['spec']['seat'])]


def actual_failed_hires(row):
    seat = int(row['spec']['seat'])
    events = row.get('failed_hires', [])
    if not isinstance(events, list):
        raise SystemExit(f'malformed failed_hires records: {row["spec"]["id"]}')
    return sum(1 for event in events if isinstance(event, (list, tuple)) and len(event) >= 2 and event[1] == seat)


def game_summaries(specs, games):
    arm_rows = defaultdict(list)
    for spec in specs:
        for arm in ARMS:
            row = games[(spec['id'], arm)]
            vm = values(row)
            vm.update({'spec_id': spec['id'], 'world_id': spec['world']['id'],
                       'opponent': spec['opponent'], 'seat': int(spec['seat'])})
            arm_rows[arm].append((row, vm))
    result = {}
    for arm, rows in arm_rows.items():
        v = [x[1] for x in rows]
        timing = [float(x[0]['seconds']) for x in rows if x[0].get('seconds') is not None]
        max_action = [float(x[0]['max_action_seconds']) for x in rows if x[0].get('max_action_seconds') is not None]
        banks = [float(x[0]['bank_remaining']) for x in rows if x[0].get('bank_remaining') is not None]
        max_action_worst_row = max(rows, key=lambda x: float(x[0]['max_action_seconds']))
        tightest_bank_row = min(rows, key=lambda x: float(x[0]['bank_remaining']))
        reports = [x[0].get('report') or {} for x in rows]
        searches = [r.get('seconds', []) for r in reports]
        search_seconds = [float(s) for one in searches for s in one]
        budgets = [float(b) for r in reports for b in r.get('budgets', [])]
        warms = [item for r in reports for item in r.get('warm', [])]
        result[arm] = {
            'games': len(rows),
            'mean_own_cash': statistics.mean(x['own_cash'] for x in v),
            'mean_competitive_margin': statistics.mean(x['competitive_margin'] for x in v),
            'mean_game_runtime_seconds': statistics.mean(timing) if timing else None,
            'max_game_runtime_seconds': max(timing) if timing else None,
            'mean_max_action_seconds': statistics.mean(max_action) if max_action else None,
            'worst_max_action_seconds': max(max_action) if max_action else None,
            'largest_own_call_time_game_id': max_action_worst_row[1]['spec_id'],
            'mean_remaining_bank_seconds': statistics.mean(banks) if banks else None,
            'minimum_remaining_bank_seconds': min(banks) if banks else None,
            'tightest_bank_game_id': tightest_bank_row[1]['spec_id'],
            'candidate_search': {
                'report_errors': sum(int(r.get('errors', 0)) for r in reports),
                'search_decisions': sum(len(r.get('decisions', [])) for r in reports),
                'reported_switches': sum(int(r.get('switches', 0)) for r in reports),
                'search_seconds_total': sum(search_seconds) if search_seconds else 0.0,
                'search_seconds_max': max(search_seconds) if search_seconds else None,
                'mean_search_budget_seconds': statistics.mean(budgets) if budgets else None,
                'warm_events': dict(Counter(str(x[0]) for x in warms if x)),
                'warm_errors': sum(bool(x and str(x[0]).endswith('_error')) for x in warms),
            } if arm == 'v9lite' else None,
        }
    return result


def game_outcomes(specs, games):
    """Actual cash wins/losses/ties, counting a tie as half a win."""
    out = {}
    for arm in ARMS:
        groups = {'pooled': list(specs)}
        for opponent in ('mgt_m1', 'v56'):
            groups[opponent] = [s for s in specs if s['opponent'] == opponent]
        out[arm] = {}
        for group, members in groups.items():
            wins = ties = losses = 0
            for spec in members:
                v = values(games[(spec['id'], arm)])
                if v['competitive_margin'] > 0:
                    wins += 1
                elif v['competitive_margin'] == 0:
                    ties += 1
                else:
                    losses += 1
            n = len(members)
            out[arm][group] = {'n': n, 'wins': wins, 'ties': ties, 'losses': losses,
                               'win_rate_ties_half': (wins + .5 * ties) / n}
    return out


def paired_analysis(specs, games):
    world_ids = sorted({s['world']['id'] for s in specs})
    worlds = defaultdict(list)
    for s in specs:
        worlds[s['world']['id']].append(s)
    if len(world_ids) != 64 or any(len(v) != 2 for v in worlds.values()):
        raise SystemExit('design must contain 64 world clusters, each with both opponents')
    for wid, ws in worlds.items():
        if {s['opponent'] for s in ws} != {'mgt_m1', 'v56'}:
            raise SystemExit(f'incomplete opponent pairing for world {wid}')

    out = {'bootstrap': {'method': 'world-cluster percentile bootstrap; resample 64 worlds with replacement, average both opponent deltas within each sampled world before the mean', 'replicates': BOOTSTRAP_REPLICATES, 'seed': BOOTSTRAP_SEED, 'confidence_level': 0.95}, 'contrasts': {}}
    rng = random.Random(BOOTSTRAP_SEED)
    for first, second in CONTRASTS:
        section = {'first_minus_second': [first, second], 'metrics': {}, 'pooled_and_by_opponent': {}, 'paired_game_deltas': []}
        case_ledger_deltas = {}
        for spec in specs:
            ga, gb = games[(spec['id'], first)], games[(spec['id'], second)]
            va, vb = values(ga), values(gb)
            la, lb = own_ledger(ga), own_ledger(gb)
            revenue_delta = {k: la['revenue'].get(k, 0) - lb['revenue'].get(k, 0)
                             for k in set(la['revenue']) | set(lb['revenue'])}
            spending_delta = {k: la['spend'].get(k, 0) - lb['spend'].get(k, 0)
                              for k in set(la['spend']) | set(lb['spend'])}
            revenue_total_delta = sum(revenue_delta.values())
            spending_total_delta = sum(spending_delta.values())
            own_cash_delta = va['own_cash'] - vb['own_cash']
            own_residual = own_cash_delta - (revenue_total_delta - spending_total_delta)
            if own_residual != 0:
                raise SystemExit(f'paired ledger delta does not reconcile: {spec["id"]}/{first}-{second}: {own_residual}')
            rival_cash_delta = int(ga['cash'][1 - int(spec['seat'])]) - int(gb['cash'][1 - int(spec['seat'])])
            margin_delta = va['competitive_margin'] - vb['competitive_margin']
            if margin_delta != own_cash_delta - rival_cash_delta:
                raise SystemExit(f'competitive-margin delta does not decompose: {spec["id"]}/{first}-{second}')
            fail_a, fail_b = actual_failed_hires(ga), actual_failed_hires(gb)
            delta = {'spec_id': spec['id'], 'world_id': spec['world']['id'], 'opponent': spec['opponent'],
                'own_cash_delta': own_cash_delta, 'rival_cash_delta': rival_cash_delta,
                'competitive_margin_delta': margin_delta,
                'own_ledger_revenue_total_delta': revenue_total_delta,
                'own_ledger_spending_total_delta': spending_total_delta,
                'own_ledger_reconciliation_residual': own_residual,
                'failed_hires_first_arm': fail_a, 'failed_hires_second_arm': fail_b,
                'extra_actual_failed_hires': fail_a - fail_b}
            section['paired_game_deltas'].append(delta)
            case_ledger_deltas[spec['id']] = {
                'revenue_by_key': dict(sorted(revenue_delta.items())),
                'spending_by_key': dict(sorted(spending_delta.items())),
                'revenue_total_delta': revenue_total_delta,
                'spending_total_delta': spending_total_delta,
                'reconciliation_residual': own_residual,
                'rival_cash_delta': rival_cash_delta,
                'margin_decomposition_residual': margin_delta - (own_cash_delta - rival_cash_delta),
                'failed_hires_first_arm': fail_a,
                'failed_hires_second_arm': fail_b,
                'extra_actual_failed_hires': fail_a - fail_b,
            }
        # Item-wise average across all paired specs, with absent items treated as zero.
        revenue_keys = sorted({k for d in case_ledger_deltas.values() for k in d['revenue_by_key']})
        spending_keys = sorted({k for d in case_ledger_deltas.values() for k in d['spending_by_key']})
        mean_revenue_by_key = {k: statistics.mean(d['revenue_by_key'].get(k, 0) for d in case_ledger_deltas.values()) for k in revenue_keys}
        mean_spending_by_key = {k: statistics.mean(d['spending_by_key'].get(k, 0) for d in case_ledger_deltas.values()) for k in spending_keys}
        mean_own_cash = statistics.mean(d['own_cash_delta'] for d in section['paired_game_deltas'])
        mean_rival_cash = statistics.mean(d['rival_cash_delta'] for d in section['paired_game_deltas'])
        mean_margin = statistics.mean(d['competitive_margin_delta'] for d in section['paired_game_deltas'])
        mean_revenue_total = statistics.mean(d['revenue_total_delta'] for d in case_ledger_deltas.values())
        mean_spending_total = statistics.mean(d['spending_total_delta'] for d in case_ledger_deltas.values())
        if abs(sum(mean_revenue_by_key.values()) - mean_revenue_total) > 1e-7:
            raise SystemExit(f'mean revenue item totals do not reconcile for {first}-{second}')
        if abs(sum(mean_spending_by_key.values()) - mean_spending_total) > 1e-7:
            raise SystemExit(f'mean spending item totals do not reconcile for {first}-{second}')
        ledger_mean_residual = mean_own_cash - (mean_revenue_total - mean_spending_total)
        margin_mean_residual = mean_margin - (mean_own_cash - mean_rival_cash)
        if abs(ledger_mean_residual) > 1e-7 or abs(margin_mean_residual) > 1e-7:
            raise SystemExit(f'mean paired ledger/margin reconciliation failed for {first}-{second}: {ledger_mean_residual}, {margin_mean_residual}')
        section['mean_own_ledger_differences'] = {
            'revenue_delta_by_key': mean_revenue_by_key,
            'spending_delta_by_key': mean_spending_by_key,
            'mean_revenue_total_delta': mean_revenue_total,
            'mean_spending_total_delta': mean_spending_total,
            'mean_own_cash_delta': mean_own_cash,
            'own_cash_reconciliation_residual': ledger_mean_residual,
            'mean_rival_cash_delta': mean_rival_cash,
            'mean_competitive_margin_delta': mean_margin,
            'margin_decomposition_residual': margin_mean_residual,
        }
        fail_deltas = [d['extra_actual_failed_hires'] for d in section['paired_game_deltas']]
        section['actual_failed_hire_differences'] = {
            'extra_failed_hires_positive_pair_count': sum(x > 0 for x in fail_deltas),
            'fewer_failed_hires_pair_count': sum(x < 0 for x in fail_deltas),
            'equal_failed_hires_pair_count': sum(x == 0 for x in fail_deltas),
            'positive_extra_failed_hires_total': sum(max(0, x) for x in fail_deltas),
            'net_failed_hire_delta': sum(fail_deltas),
            'by_opponent': {
                opp: {'positive_extra_failed_hires_total': sum(max(0, d['extra_actual_failed_hires']) for d in section['paired_game_deltas'] if d['opponent'] == opp),
                      'net_failed_hire_delta': sum(d['extra_actual_failed_hires'] for d in section['paired_game_deltas'] if d['opponent'] == opp)}
                for opp in ('mgt_m1', 'v56')
            },
        }
        for metric, key in (('own_cash', 'own_cash_delta'), ('competitive_margin', 'competitive_margin_delta')):
            by_world = {}
            for wid in world_ids:
                deltas = [r[key] for r in section['paired_game_deltas'] if r['world_id'] == wid]
                assert len(deltas) == 2
                by_world[wid] = statistics.mean(deltas)
            estimate = statistics.mean(by_world.values())
            boot = []
            for _ in range(BOOTSTRAP_REPLICATES):
                sample = [by_world[world_ids[rng.randrange(len(world_ids))]] for _ in world_ids]
                boot.append(statistics.mean(sample))
            boot.sort()
            section['metrics'][metric] = {'mean_paired_delta': estimate, 'world_clustered_95pct_ci': [pct(boot, .025), pct(boot, .975)], 'world_mean_deltas': by_world}
            groups = {'pooled': section['paired_game_deltas']}
            for opponent in ('mgt_m1', 'v56'):
                groups[opponent] = [r for r in section['paired_game_deltas'] if r['opponent'] == opponent]
            counts = {}
            for group, rr in groups.items():
                vals = [r[key] for r in rr]
                counts[group] = {'n': len(vals), 'better': sum(x > 0 for x in vals), 'ties': sum(x == 0 for x in vals), 'worse': sum(x < 0 for x in vals), 'mean_delta': statistics.mean(vals)}
            section['pooled_and_by_opponent'][metric] = counts
            sorted_rows = sorted(section['paired_game_deltas'], key=lambda r: r[key])
            def detailed_case(row):
                return {**{k: row[k] for k in ('spec_id', 'world_id', 'opponent', key,
                    'own_cash_delta', 'rival_cash_delta', 'competitive_margin_delta',
                    'failed_hires_first_arm', 'failed_hires_second_arm', 'extra_actual_failed_hires')},
                    'own_ledger_revenue_delta_by_key': case_ledger_deltas[row['spec_id']]['revenue_by_key'],
                    'own_ledger_spending_delta_by_key': case_ledger_deltas[row['spec_id']]['spending_by_key'],
                    'own_ledger_revenue_total_delta': case_ledger_deltas[row['spec_id']]['revenue_total_delta'],
                    'own_ledger_spending_total_delta': case_ledger_deltas[row['spec_id']]['spending_total_delta'],
                    'own_ledger_reconciliation_residual': case_ledger_deltas[row['spec_id']]['reconciliation_residual'],
                    'margin_decomposition_residual': case_ledger_deltas[row['spec_id']]['margin_decomposition_residual']}
            section.setdefault('worst_cases', {})[metric] = {
                'lowest_5_deltas': [detailed_case(r) for r in sorted_rows[:5]],
                'highest_5_deltas': [detailed_case(r) for r in sorted_rows[-5:][::-1]],
            }
        out['contrasts'][f'{first}_minus_{second}'] = section
    return out


def main():
    design, specs, games, prefix_checks, no_switch_checks = validated_load()
    summary = {
        'panel': 'v9-lite fresh release qualification',
        'design_file': str((PANEL / 'design.json').relative_to(ROOT)),
        'expected_games': 384,
        'completed_games': len(games),
        'world_count': len({s['world']['id'] for s in specs}),
        'opponents': sorted({s['opponent'] for s in specs}),
        'arms': list(ARMS),
        'all_game_ledgers_reconcile_exactly': True,
        'candidate_search_error_count': 0,
        'all_candidate_remaining_banks_positive': True,
        'candidate_y3_pre288_prefix_parity': {'checked_specs': len(prefix_checks), 'all_equal': True},
        'candidate_no_switch_full_action_and_cash_parity_with_y3': {'checked_specs': len(no_switch_checks), 'all_equal': True, 'spec_ids': no_switch_checks},
        'actual_game_outcomes_by_arm': game_outcomes(specs, games),
        'arm_summaries': game_summaries(specs, games),
        'notes': ['Own cash is the final cash of spec.seat.', 'Competitive margin is own final cash minus rival final cash; game wins/ties/losses compare this margin with zero, with a tie counting as half a win.', 'Paired better/tie/worse counts in paired.json classify signed arm-to-arm deltas, not game outcomes.'],
    }
    paired = paired_analysis(specs, games)
    # Atomic writes happen only after every completion, identity, ledger, bank,
    # report-error, prefix, and no-switch parity assertion has passed.
    for name, obj in (('summary.json', summary), ('paired.json', paired)):
        temp = PANEL / (name + '.tmp')
        temp.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        temp.replace(PANEL / name)
    print(json.dumps({'summary': str(PANEL / 'summary.json'), 'paired': str(PANEL / 'paired.json'),
                      'games': len(games), 'worlds': summary['world_count'], 'no_switch_specs': len(no_switch_checks)}, indent=2))


if __name__ == '__main__':
    main()
