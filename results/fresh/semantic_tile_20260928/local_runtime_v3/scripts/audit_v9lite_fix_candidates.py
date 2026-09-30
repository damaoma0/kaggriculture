"""Read-only policy audit of saved V9-lite decisions; does not simulate games.

Execute only the packaged pure admission function, extracted with AST, against
saved forecast rows. Counterfactual choices are diagnostic, not strength claims.
"""
import ast
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'submissions/2026-09-24-mgt_v9lite/pkg'
OUT = ROOT / 'results/fresh/v9lite_fix_audit_20260925'


def main():
    source = (PACKAGE / 'scripts/value_tape_search_lite.py').read_bytes()
    tree = ast.parse(source)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_admit')
    namespace = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), '<packaged _admit>', 'exec'), namespace)
    admit = namespace['_admit']
    results = []
    checked = 0
    # Phase 1 used a different shortlist. Keep only default-compatible logs.
    for folder in ('phase2', 'pkg', 'iso_lite'):
        path = ROOT / f'results/fresh/v9lite_20260924/{folder}/v9lite_decisions.jsonl'
        for line_number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            entry = json.loads(line)
            decision = entry['lite']
            params = decision['params']
            eligible = []
            blocked = []
            for row in decision['candidates']:
                if row['route'] is None:
                    continue
                deltas, cash = row['deltas'], row['cash']
                restored = dict(predictions=[None] * len(deltas),
                    early_rejection=row['early'], protection_failures=row['failures'],
                    risk_score=row['risk'], minimum_margin=min(deltas, default=0),
                    mean_margin=mean(deltas) if deltas else 0, cash_deltas=cash)
                actual = admit(deepcopy(restored), params['worlds'], params['final_min'])
                assert actual['admitted'] == row['admitted'], (path, line_number, row['route'])
                checked += 1
                other_gates = (actual['fully_evaluated'] and not row['failures']
                    and row['risk'] > params['final_min']
                    and restored['minimum_margin'] >= -max(500, .25 * max(0, restored['mean_margin'])))
                if other_gates:
                    eligible.append(row)
                    if mean(cash) <= 0:
                        blocked.append(dict(route=row['route'], mean_margin=mean(deltas),
                            minimum_margin=min(deltas), mean_own_cash=mean(cash), risk=row['risk']))
            proposed = max(eligible, key=lambda r: r['risk'])['route'] if eligible else None
            if blocked:
                results.append(dict(log=str(path.relative_to(ROOT)), line=line_number,
                    tag=entry.get('tag'), pid=entry.get('pid'), step=entry['step'],
                    current=decision['selected'], diagnostic_margin_only=proposed,
                    changed=proposed != decision['selected'], blocked=blocked))
    report = dict(packaged_selector_sha256=sha256(source).hexdigest(),
        checked_candidate_rows=checked, blocked_decisions=len(results),
        changed_decisions=sum(r['changed'] for r in results), examples=results,
        limitations='Saved development/runtime logs can overlap worlds and predate the final thread-free package. '
        'Admission booleans reproduce the packaged function. No new full games or strength estimate. '
        'Removing the gate changes lazy expansion too; logged counterfactuals are not a full policy replay.')
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'admission_audit.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
