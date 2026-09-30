"""Replay cached forecast labels without inventing censored world outcomes."""
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import patch

import train_tape_semantic_ranker as T
import value_tape_search_v7 as Exact
import value_tape_search_v8 as Scout


class MissingForecast(Exception):
    pass


class FixtureRuntime:
    busy = False

    def __init__(self, point):
        self.point = point
        self.reference = point['decision']
        self.by_route = {c['route']: c for c in self.reference['candidates']}
        self.rollout_impl = SimpleNamespace(__globals__={})

    def prepare(self, obs):
        self.rollouts = self.pruned_rollouts = self.simulated_turns = 0

    def shortlist(self, obs, memory, count):
        return [{k: c[k] for k in ('route', 'episode', 'hamming', 'distance', 'name')}
            for c in self.reference['candidates']]

    def rollout(self, obs, memory, route, world, until=None, protected=None):
        index = world['index']
        available = self.by_route[route]['predictions']
        if index >= len(available):
            raise MissingForecast((route, index))
        self.rollouts += 1
        result = deepcopy(available[index])
        missing = (protected or set()) - set(map(tuple, result['survives']))
        if missing:
            self.pruned_rollouts += 1
            self.simulated_turns += 72
            return dict(early_rejection=True, missing=sorted(missing),
                survives=result['survives'], boundary_step=(self.reference['day']+3)*24)
        self.simulated_turns += 719-self.reference['day']*24
        return result


def replay(point, planner):
    runner = FixtureRuntime(point)
    def world(obs, index):
        w = point['decision']['worlds'][index]
        return dict(index=index, shops={29:w['shops']}, donor=w['donor'])
    with patch.object(planner, 'runtime', return_value=runner), patch.object(planner.M, 'world', side_effect=world):
        _, decision = planner.choose(point['obs'], point['memory'])
    return decision


def main():
    rows = []
    for point in T.load_points():
        row = dict(id=point['id'], group=point['group'], reference=point['decision']['selected'])
        # V3's old cash screen can differ from the corrected exact policy.
        try:
            exact = replay(point, Exact)
            row.update(exact=exact['selected'], exact_turns=exact['simulated_turns'])
            scout = replay(point, Scout)
            row.update(scout=scout['selected'], scout_turns=scout['simulated_turns'],
                selected_equal=scout['selected'] == exact['selected'], completed=True)
        except MissingForecast as error:
            row.update(completed=False, censored_forecast=str(error))
        rows.append(row)
    resolved = [r for r in rows if r['completed']]
    old = sum(r['exact_turns'] for r in resolved)
    new = sum(r['scout_turns'] for r in resolved)
    report = dict(checkpoints=len(rows), resolved=len(resolved), censored=len(rows)-len(resolved),
        equal=sum(r['selected_equal'] for r in resolved), exact_turns=old, scout_turns=new,
        turn_reduction=1-new/old, rows=rows,
        caution='Saved forecast fixtures only. Missing eight-world labels remain unresolved, not treated as bad outcomes. Runtime and new policy outcomes need live-engine evaluation.')
    (T.OUT / 'scout_fixtures.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k != 'rows'}, indent=2))
    print(json.dumps([r for r in rows if not r['completed'] or not r['selected_equal']], indent=2))


if __name__ == '__main__':
    main()
