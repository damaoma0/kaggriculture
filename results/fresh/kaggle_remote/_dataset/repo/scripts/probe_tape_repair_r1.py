"""Recorded-prefix checkpoints for transition repair development."""
from copy import deepcopy
import argparse
import gzip
import json
from pathlib import Path
import time

import value_tape_repair_r1 as N

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / 'results/fresh/value_tape_wide_20260923_01a0'
OUT = ROOT / 'results/fresh/tape_repair_20260924_01a0/probes'


def checkpoint(episode, day):
    game = json.loads(gzip.decompress((OLD / f'recordings/{episode}.json.gz').read_bytes()))
    seat = 1 - game['opponent_seat']
    entry = N.V.fresh_agent()
    R = N.V.R
    with R.Simulator(dict(game, seat=seat)) as sim:
        state = deepcopy(sim.initial)
        for t in range(day * 24):
            sim.t = t
            sim.seats = {id(f): s for s, f in enumerate(state[0].observation.farms)}
            for s in state:
                s.observation.step = t
            if t % 24 == 0:
                state[0].observation.town['unlocked_shops'][:] = game['shops'][t // 24]
            our = entry(deepcopy(state[seat].observation))
            assert our == game['actions'][seat][t], ('prefix action', t)
            state[seat].action = our
            state[1 - seat].action = game['actions'][1 - seat][t]
            R.engine().interpreter(state, sim.env)
        obs = deepcopy(state[seat].observation)
        obs.step = day * 24
        obs.town['unlocked_shops'][:] = game['shops'][day]
        expected = next(c['seats'][seat] for c in game['observations'] if c['step'] == day * 24)
        clean = lambda x: {k: v for k, v in x.items() if k not in ('step', 'remainingOverageTime')}
        assert clean(obs) == clean(expected)
        return obs, N.V.memory_of(entry)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--episode', type=int, default=112109339)
    ap.add_argument('--day', type=int, default=15)
    ap.add_argument('--no-repairs', action='store_true')
    args = ap.parse_args()
    obs, memory = checkpoint(args.episode, args.day)
    print('CHECKPOINT', args.episode, args.day, flush=True)
    selection, decision = N.choose(obs, memory, max_repairs=0 if args.no_repairs else 2)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f'{args.episode}-d{args.day}-{"control" if args.no_repairs else "r1"}.json'
    path.write_text(json.dumps(decision, indent=2), encoding='utf-8')
    print('SELECTED', selection, 'seconds', decision['seconds'], flush=True)
    for row in decision['candidates']:
        print(json.dumps({k: row.get(k) for k in ('route', 'mean_margin', 'risk_score',
            'cash_deltas', 'protection_failures', 'admitted', 'fully_evaluated')}), flush=True)
        if row.get('repair_assets'):
            print('REPAIR_STATS', [p.get('repair_stats') for p in row['predictions']], flush=True)


if __name__ == '__main__':
    main()
