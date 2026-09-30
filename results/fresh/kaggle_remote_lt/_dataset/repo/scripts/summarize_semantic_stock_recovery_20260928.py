"""Summarize completed recorded-action diagnostics; does not run the engine."""
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/fresh/semantic_strategy_20260928'


def main():
    rows = []
    for case, day in [('live-04', 7), ('live-01', 8)]:
        paths = {kind: BASE / 'service_shadows' / name for kind, name in
                 [('shadow', f'{case}-d{day-1}-{day}.json.gz'),
                  ('recovery', f'{case}-d{day}-stock-recovery.json.gz')]}
        data = {kind: json.loads(gzip.decompress(path.read_bytes())) for kind, path in paths.items()}
        shadow, recovery = data['shadow'], data['recovery']
        assert shadow['replay_cash_equal'] and shadow['replay_ledger_equal']
        assert not shadow['shadow_mismatches']
        assert all(all(row[k] for k in ('own_farm_equal', 'private_equal', 'market_equal', 'shops_equal')) for row in shadow['dawn_checks'])
        assert shadow['live_opponent_calls'] == recovery['live_opponent_calls'] == 0
        assert all(not row['state']['xretire'] for row in recovery['snapshots'])
        seat = recovery['case']['seat']
        rescued = []
        for tile, cell in recovery['recovery_end_tiles'].items():
            assert not recovery['baseline_end_tiles'][tile].get('animal')
            assert cell.get('animal') and cell['consecutive_unfed'] == 0
            assert cell['pending_care_bonus'] == 1
            rescued.append(dict(tile=int(tile), species=cell['animal'], birth=cell['placed_day']))
        active = [r for r in recovery['snapshots'] if r['step'] >= recovery['trigger']['step']]
        stats = active[-1]['state']['lower_stats']
        max_step = max(r['state']['lower_stats']['step_ms'][-1] for r in active)
        row = dict(case=case, day=day, seat=seat,
            artifacts={kind: dict(path=path.relative_to(ROOT).as_posix(), sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for kind, path in paths.items()},
            candidate_manifest_sha256=shadow['candidate_manifest_sha256'],
            source_game_sha256=shadow['source_sha256'], source_actions_sha256=shadow['actions_sha256'],
            shadow_script_sha256=shadow['script_sha256'], recovery_script_sha256=recovery['script_sha256'],
            baseline_full_cash_ledger_and_dawns_exact=True, shadow_actions_equal=shadow['shadow_calls'],
            recovery_prefix_actions_equal=recovery['exact_shadow_prefix_calls'],
            trigger_step=recovery['trigger']['step'], trigger_events=recovery['trigger']['events'],
            stop_step=recovery['stop_step'], rescued_animals=rescued,
            next_morning_own_cash_delta=recovery['recovery_end_cash'][seat]-recovery['baseline_end_cash'][seat],
            next_morning_rival_cash_delta=recovery['recovery_end_cash'][1-seat]-recovery['baseline_end_cash'][1-seat],
            own_ledger_delta=recovery['own_ledger_delta'], posttrigger_reported_max_step_ms=max_step,
            reported_errors=stats['errors'], reported_steps_over_1s=stats['steps_over_1s'],
            reported_dropped_hard=stats['dropped_hard'], live_opponent_calls=0,
            diagnostic_elapsed_seconds=recovery['elapsed_seconds'])
        rows.append(row)
    result = dict(scope='TWO_DEVELOPMENT_CASES_ONE_DAY_COMPONENT_CONTINUATIONS',
        cause='Tier advances its pickup cursor after a partial wheat pickup, then skips later mandatory FEED without replenishment.',
        intervention='After preceding-step wheat pick_short, activate existing rolling dispatcher; fixtures refuse explicit retirement days.',
        limitation='Proves three next-morning rescues, not full-season profitability or responsive-opponent generalization. Switching changes other work, purchases and sales too.',
        new_games_executed_by_this_summary=0, cases=rows)
    path = BASE / 'stock_recovery_diagnostic_summary.json'
    path.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(dict(cases=len(rows), rescued_animals=sum(len(r['rescued_animals']) for r in rows), summary_sha256=hashlib.sha256(path.read_bytes()).hexdigest())))


if __name__ == '__main__':
    main()
