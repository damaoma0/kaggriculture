"""Technical progress only: deliberately does not report cash/profit outcomes."""
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / 'results/fresh/coherent_switch_20260924_01a0/release_lite_qualification'

def main():
    rows = {}
    for path in (PANEL / 'games').glob('*.json'):
        # The worker writes directly; avoid a currently open output file.
        if time.time() - path.stat().st_mtime < 3:
            continue
        row = json.loads(path.read_text())
        assert row.get('completed'), (path.name, row.get('error'))
        rows[path.stem] = row
    candidate = {name.removesuffix('-v9lite'): row for name, row in rows.items() if name.endswith('-v9lite')}
    paired, no_switch = 0, 0
    for case, row in candidate.items():
        assert row['report']['errors'] == 0
        assert row['bank_remaining'] > 0
        base = rows.get(case + '-y3')
        if base is None:
            continue
        assert row['prefix_sha256'] == base['prefix_sha256'], ('prefix_parity', case)
        paired += 1
        if row['report']['switches'] == 0:
            assert row['action_sha256'] == base['action_sha256'], ('no_switch_action_parity', case)
            assert row['cash'] == base['cash'], ('no_switch_cash_parity', case)
            no_switch += 1
    print(json.dumps(dict(completed_records=len(rows), candidate_games=len(candidate),
        candidate_minimum_bank=min((r['bank_remaining'] for r in candidate.values()), default=None),
        maximum_candidate_call=max((r['max_action_seconds'] for r in candidate.values()), default=None),
        prefix_checks_passed=paired, no_switch_parity_checks_passed=no_switch,
        candidate_search_errors=0, profit_outcomes_reported=False)))

if __name__ == '__main__':
    main()
