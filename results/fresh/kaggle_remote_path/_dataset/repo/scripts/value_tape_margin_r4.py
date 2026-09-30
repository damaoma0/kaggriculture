"""R3 challenger: admit fully evaluated ordinary routes on competitive margin.

R3 search, repaired-route validation, cohorts, downside, and risk thresholds
are retained. A newly admitted ordinary route must have no additional failed
purchases/hires in any paired forecast. No extra rollouts or future information.
"""
from hashlib import sha256
from pathlib import Path
import statistics
import time

import value_tape_repair_r3 as R3

V, F, B = R3.V, R3.F, R3.B
install, commit, unpack = R3.install, R3.commit, R3.unpack
PLANNER_SHA256 = sha256(Path(__file__).read_bytes()).hexdigest()


def select_margin(decision):
    current = next(c for c in decision['candidates'] if c['route'] == decision['selected'])
    baseline = decision['candidates'][0]
    eligible, diagnostics = [current], []
    for c in decision['candidates']:
        if not isinstance(c['route'], int):
            continue
        predictions = c.get('predictions', [])
        complete = c.get('fully_evaluated') and len(predictions) == 8 and len(baseline['predictions']) >= 8
        failures = []
        if complete:
            for i, (p, base) in enumerate(zip(predictions, baseline['predictions'])):
                for operation, count in p.get('failures', {}).items():
                    if count > base.get('failures', {}).get(operation, 0):
                        failures.append(dict(scenario=i, operation=operation,
                                             extra=count-base.get('failures', {}).get(operation, 0)))
        admitted = bool(complete and not c.get('protection_failures') and not failures
                        and c.get('risk_score', 0) > 350
                        and c['minimum_margin'] >= -c['loss_budget'])
        diagnostics.append(dict(route=c['route'], complete=bool(complete), admitted=admitted,
                                extra_failed_spending=failures,
                                mean_own_cash=statistics.mean(c['cash_deltas']) if c.get('cash_deltas') else None))
        if admitted:
            eligible.append(c)
    # Existing R3 choice wins ties, including its validated repairs.
    winner = max(eligible, key=lambda c:c.get('risk_score', 0))
    return winner, diagnostics


def choose(obs, memory, *, count=7, keep=2, max_repairs=2, budget_seconds=18.0):
    started = time.perf_counter()
    selected, decision = R3.choose(obs, memory, count=count, keep=keep,
                                  max_repairs=max_repairs, budget_seconds=budget_seconds)
    winner, diagnostics = select_margin(decision)
    decision['r3_selected'] = selected
    decision['r3_planner_sha256'] = decision['planner_sha256']
    decision['planner_sha256'] = PLANNER_SHA256
    decision['margin_admission'] = diagnostics
    decision['margin_override'] = winner['route'] != selected
    decision['selected'] = winner['route']
    decision['selected_episode'] = winner['episode']
    decision['protocol'] += ' R4: allow fully evaluated ordinary routes by margin, retaining downside/cohort gates and requiring no extra failed spending in each scenario; original R3 repairs unchanged.'
    decision['seconds'] = time.perf_counter()-started
    return winner['route'], decision
