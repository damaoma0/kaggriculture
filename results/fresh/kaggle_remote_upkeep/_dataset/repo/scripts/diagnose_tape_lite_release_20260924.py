"""Offline exact-trajectory diagnostic for a completed v9-lite release case.

This is hindsight analysis, not qualification: v9lite route choices are forced
from the completed game's saved report. It never runs the search or writes under
`games/`; it writes one replay under `diagnostics/`.

Usage after the release panel is complete:
  python scripts/diagnose_tape_lite_release_20260924.py --case r00-mgt_m1 --arm v9lite
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / 'results/fresh/coherent_switch_20260924_01a0/release_lite_qualification'
ARMS = ('baseline', 'y3', 'v9lite')


def public_hash(H, action):
    return sha256(json.dumps(H.public(action), sort_keys=True).encode()).hexdigest()


def farm_asset_counts(farm):
    counts = {}
    for row in farm.get('tiles', []):
        for tile in row:
            if not isinstance(tile, dict):
                continue
            kind = tile.get('kind')
            if kind:
                counts[kind] = counts.get(kind, 0) + 1
            crop = tile.get('crop')
            if crop:
                key = 'CROP:' + str(crop)
                counts[key] = counts.get(key, 0) + 1
            animal = tile.get('animal')
            if animal:
                key = 'ANIMAL:' + str(animal)
                counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def daily_snapshot(state, step):
    farms = state[0].observation.farms
    seats = []
    for seat in (0, 1):
        private = state[seat].observation.private
        farm = farms[seat]
        seats.append({
            'seat': seat,
            'cash': int(farm['money']),
            'hands': len(farm.get('hands', [])),
            'asset_counts': farm_asset_counts(farm),
            'tiles': deepcopy(farm.get('tiles', [])),
            'inventories': deepcopy(private.get('inventories', [])),
            'seeds': deepcopy(private.get('seeds', {})),
            'shed': deepcopy(private.get('shed', {})),
        })
    return {'step': step, 'day': step // 24, 'seats': seats,
            'revealed_shops': list(state[0].observation.town.unlocked_shops),
            'market': deepcopy(state[0].observation.market)}


def configure_v9_replay(entry, saved_record):
    """Disable warm threads and force only choices present in saved report."""
    ns = entry.__globals__
    report = saved_record.get('report')
    if not isinstance(report, dict) or not isinstance(report.get('decisions'), list):
        raise RuntimeError('v9lite record lacks report.decisions; cannot reconstruct commitments')
    choices = {}
    for record in report['decisions']:
        if not isinstance(record, list) or len(record) != 3:
            raise RuntimeError(f'malformed saved v9lite decision: {record!r}')
        day, selected, route = record
        step = int(day) * 24
        if step in choices:
            raise RuntimeError(f'duplicate saved decision at step {step}')
        choices[step] = {'selected': selected, 'route': route, 'day': int(day)}

    ns['_V9_WARM_START'] = 720
    ns['_V9_WARM_ROLLOUT'] = None
    ns['_V9_MIN'] = -1.0e30  # call the forced chooser at reveal steps even if a saved decision is absent
    ns['_V9_WARM'] = {}
    ns['_V9_SPENT'] = [0.0]
    ns['_V9_STATE'] = {}
    ns['_V9_REPORT'] = {'decisions': [], 'switches': 0, 'seconds': [], 'budgets': [], 'errors': 0, 'warm': []}
    reveal_results = []

    def forced_choose(observation, memory, budget_seconds=None, **kwargs):
        step = int(observation.get('step', 0))
        saved = choices.get(step)
        if saved is None:
            reveal_results.append({'step': step, 'saved_decision': False, 'route': None,
                                   'remaining_overage_time_reconstructed': observation.get('remainingOverageTime'),
                                   'action': 'preserve_current/native_route'})
            return None, None
        route = saved['route']
        decision = {'selected': saved['selected'], 'until': min(719, (saved['day'] + 3) * 24)}
        reveal_results.append({'step': step, 'saved_decision': True, 'route': route,
                               'selected': saved['selected'], 'until': decision['until'],
                               'remaining_overage_time_reconstructed': observation.get('remainingOverageTime'),
                               'action': 'force_saved_commitment' if route is not None else 'saved_no_switch'})
        return route, decision

    ns['_V9_L'].choose = forced_choose
    return choices, reveal_results


def run_case(case, arm):
    import run_coherent_opening_study as H
    R = H.R
    E = R.engine()
    from kaggle_environments.agent import get_last_callable

    design = json.loads((PANEL / 'design.json').read_text(encoding='utf-8'))
    spec = next((s for s in design['specs'] if s['id'] == case), None)
    if spec is None:
        raise SystemExit(f'unknown release spec: {case}')
    game_path = PANEL / 'games' / f'{case}-{arm}.json'
    if not game_path.is_file():
        raise SystemExit(f'saved source game missing: {game_path}')
    original = json.loads(game_path.read_text(encoding='utf-8'))
    if original.get('completed') is not True or original.get('arm') != arm or original.get('spec') != spec:
        raise SystemExit('saved game is incomplete or does not match the frozen design')
    if arm not in ARMS:
        raise SystemExit(f'arm must be one of {ARMS}')
    timings = original.get('timings')
    if not isinstance(timings, list) or len(timings) != 719 or any(
            not isinstance(t, (int, float)) or not math.isfinite(t) or t < 0 for t in timings):
        raise SystemExit('saved game does not contain 719 finite nonnegative call timings')

    seat = int(spec['seat'])
    shops = spec['world']['shops']
    pkg = PANEL / 'package'
    source = {'baseline': pkg / 'agents/mgt_m1.py', 'y3': pkg / 'agents/mgt_y3.py', 'v9lite': pkg / 'main.py'}[arm]
    sys.path.insert(0, str(pkg))
    entry = get_last_callable(source.read_text(encoding='utf-8'), path=str(source))
    forced_choices, reveal_events = ({}, [])
    if arm == 'v9lite':
        forced_choices, reveal_events = configure_v9_replay(entry, original)

    rival = H.load_callable(H.OPPONENTS[spec['opponent']], spec['opponent'])
    sim = R.Simulator(dict(seed=spec['world']['seed'], seat=seat, episode=0,
        shops=[shops[:min(8, d // 3)] for d in range(31)]))
    actions = sha256()
    prefix = sha256()
    own_actions = []
    daily = []
    failures = []
    bank = 60.0
    with sim:
        old_hire = E._do_hire
        def hire(farm, *args, **kwargs):
            before = farm['hires_today']
            result = old_hire(farm, *args, **kwargs)
            if before == farm['hires_today']:
                failures.append([sim.t, sim.seats.get(id(farm))])
            return result
        E._do_hire = hire
        state = deepcopy(sim.initial)
        for t in range(719):
            sim.t = t
            sim.seats = {id(f): s for s, f in enumerate(state[0].observation.farms)}
            for item in state:
                item.observation.step = t
            expected_shops = shops[:min(8, (t // 24) // 3)]
            if list(state[seat].observation.town.unlocked_shops) != expected_shops:
                raise RuntimeError(f'shop schedule mismatch at step {t}')
            if t % 24 == 0:
                daily.append(daily_snapshot(state, t))

            obs = deepcopy(state[seat].observation)
            obs['remainingOverageTime'] = bank
            action = entry(obs)
            state[seat].action = action
            state[1 - seat].action = rival(deepcopy(state[1 - seat].observation))
            encoded = json.dumps(H.public(action), sort_keys=True).encode()
            actions.update(encoded)
            if t < 288:
                prefix.update(encoded)
            own_actions.append(H.public(action))
            E.interpreter(state, sim.env)
            bank -= max(0.0, float(timings[t]) - 1.0)
            if (t + 1) % 24 == 0:
                state[0].observation.town.unlocked_shops[:] = shops[:min(8, ((t + 1) // 24) // 3)]

        if not all(s.status == 'DONE' for s in state):
            raise RuntimeError('replay did not complete all seats')
        cash = [int(state[0].observation.farms[s]['money']) for s in (0, 1)]
        ledgers = H.ledgers_from_events(sim.events)
        ledger_verified = [
            3000 + sum(ledgers[s]['revenue'].values()) - sum(ledgers[s]['spend'].values()) == cash[s]
            for s in (0, 1)
        ]

    action_sha = actions.hexdigest()
    prefix_sha = prefix.hexdigest()
    action_equal = action_sha == original.get('action_sha256')
    cash_equal = cash == original.get('cash')
    bank_match = original.get('bank_remaining') is not None and math.isclose(
        bank, float(original['bank_remaining']), rel_tol=0, abs_tol=1e-7)
    reproduced = action_equal and cash_equal and ledger_verified == [True, True] and bank_match
    output = {
        'diagnostic_only_hindsight_route_replay': True,
        'qualification_result': False,
        'case': case,
        'arm': arm,
        'spec': spec,
        'reproduced': reproduced,
        'match_checks': {
            'full_own_action_sha256_equal': action_equal,
            'reconstructed_action_sha256': action_sha,
            'recorded_action_sha256': original.get('action_sha256'),
            'pre288_prefix_sha256_equal': prefix_sha == original.get('prefix_sha256'),
            'both_end_cash_equal': cash_equal,
            'reconstructed_cash': cash,
            'recorded_cash': original.get('cash'),
            'remaining_bank_equal_within_1e-7': bank_match,
            'both_ledgers_reconcile': ledger_verified == [True, True],
            'recorded_action_sequence_available': 'actions' in original,
        },
        'reconstructed_remaining_bank': {'starting_seconds': 60.0, 'ending_seconds': bank,
            'recorded_ending_seconds': original.get('bank_remaining'),
            'matches_recorded_within_1e-7': original.get('bank_remaining') is not None and math.isclose(bank, float(original['bank_remaining']), rel_tol=0, abs_tol=1e-7)},
        'daily': daily,
        'own_actions': own_actions,
        'successful_transaction_events': [{'step': t, 'seat': s, 'op': op, 'item': item, 'amount': int(amount)}
                                          for t, s, op, item, amount in sim.events],
        'ledgers': ledgers,
        'failed_hires': failures,
        'end_cash': cash,
        'forced_saved_decisions': [forced_choices[k] | {'step': k} for k in sorted(forced_choices)],
        'reveal_actions': reveal_events,
        'source_call_timings_used_for_bank_reconstruction': len(timings),
        'runtime_measurement': None,
        'runtime_note': 'Replay uses forced saved choices and disabled background warming; its runtime is diagnostic and is not comparable to the qualification run.',
    }
    diag_dir = PANEL / 'diagnostics'
    diag_dir.mkdir(parents=True, exist_ok=True)
    target = diag_dir / f'{case}-{arm}.json'
    target.write_text(json.dumps(output, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'path': str(target), 'reproduced': reproduced, 'action_equal': action_equal,
                      'cash_equal': cash_equal, 'end_cash': cash, 'forced_decisions': len(forced_choices)}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', required=True, help='release spec ID, such as r00-mgt_m1')
    parser.add_argument('--arm', required=True, choices=ARMS)
    args = parser.parse_args()
    run_case(args.case, args.arm)


if __name__ == '__main__':
    main()
