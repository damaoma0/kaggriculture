"""Validate the tape-calendar simulator against recorded benchmark games (scripts/labour_idle.py output).

For each recorded game: reconstruct the route the benchmark used (its own router on the recorded shops),
simulate the native crew from step 0 with the tape only, and compare every tape unit's simulated position
and command with the recorded position and command, step by step.
"""
import glob, json, sys
from collections import Counter
from market_corpus import ROOT

FRAG = (ROOT / 'scripts/fragments/tape_calendar.py').read_text(encoding='utf-8')


def load_bench():
    ns = {'__name__': 'bench'}
    exec(compile((ROOT / 'agents/benchmark_frozen_56280048.py').read_text(encoding='utf-8'), 'bench', 'exec'), ns)
    return ns


def main():
    ns = load_bench()
    exec(FRAG, ns)
    routes = ns['_IMPL'].chassis.routes
    files = sorted(glob.glob(str(ROOT / 'results/fresh/labour_idle/*.json')))
    for p in files:
        g = json.loads(open(p, encoding='utf-8').read())
        eid = g['episode']
        ev = json.loads((ROOT / f'results/fresh/mg_policy/events-{eid}.json').read_text(encoding='utf-8'))
        shops = ev['days'][6]['shops']
        state = {}
        route_at = {}
        for t in range(719):
            obs = {'town': {'unlocked_shops': ev['days'][min(t // 24, len(ev['days']) - 1)]['shops']}}
            route_at[t] = ns['_router'](obs, t, state)
        tape_at = lambda t: routes[route_at[t]][t] if t < len(routes[route_at[t]]) else {}
        sim = ns['_tc_simulate'](tape_at, 0, 718, [(4, 4)])
        U = g['units']
        pos_bad, cmd_bad, total = Counter(), Counter(), Counter()
        first_bad = None
        for t in range(719):
            for u, (x, y, c) in enumerate(sim[t]):
                if u >= len(U[t]):
                    continue
                rx, ry, rop = U[t][u]
                d = t // 24
                total[d] += 1
                if (rx, ry) != (x, y):
                    pos_bad[d] += 1
                    if first_bad is None:
                        first_bad = (t, u, (x, y), (rx, ry))
                elif rop != (c[0] if c else 'PASS'):
                    cmd_bad[d] += 1
        extra = sum(max(0, len(U[t]) - len(sim[t])) for t in range(719))
        print(f'{eid}: routes {sorted(set(route_at.values()))}; unit-steps {sum(total.values())}; '
              f'position mismatches {sum(pos_bad.values())}; command changed by layers {sum(cmd_bad.values())}; '
              f'extra (non-tape) unit-steps {extra}; first position mismatch {first_bad}')
        if '-v' in sys.argv:
            print('   by day: ' + ' '.join(f'{d}:{pos_bad[d]}/{cmd_bad[d]}' for d in range(30) if pos_bad[d] or cmd_bad[d]))


if __name__ == '__main__':
    main()
