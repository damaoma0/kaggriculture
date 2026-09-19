"""Diagnose one game of a Mother-Goose tape-router agent against a live rival on a natural seed.

Prints the route history (day, tape, demand distance, board Hamming distance), the shops, our cash by day next to
the cash the chosen tape had on that day in its own game, dead commands by day, and the final ledger.
Usage: python mgt_diag.py <agent> <rival> <seed> [seat=0]
"""
import json, sys
from collections import Counter
from market_corpus import ROOT
import tape_vs_bench as TV


def main():
    name, rival, seed = sys.argv[1], sys.argv[2], int(sys.argv[3])
    seat = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    ns = {'__name__': 'mgt'}
    exec(compile((ROOT / 'agents' / f'{name}.py').read_text(encoding='utf-8'), name, 'exec'), ns)
    ours = ns['agent']
    rp = ROOT / 'agents' / f'{rival}.py'
    opp = get_last_callable(rp.read_text(encoding='utf-8'), path=str(rp))
    players = [None, None]
    players[seat] = lambda obs, t: ours(obs)
    players[1 - seat] = lambda obs, t: opp(obs)
    env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': seed})
    res = TV._play(E, env, players, seat, None, None, None, seat)
    st = ns['_MGT_IMPL'].chassis.players[seat]['router_state']
    tapes = ns['_MGT_TAPES']
    shops = env.state[0].observation.town['unlocked_shops']
    print(f'{name} vs {rival}, seed {seed}, seat {seat}: {res["final"][seat]:,.0f} vs {res["final"][1 - seat]:,.0f} (margin {res["final"][seat] - res["final"][1 - seat]:+,.0f})')
    print('shops:', shops)
    print('route history (day, tape, distance, hamming):', st.get('history'))
    final_route = st.get('route')
    print('final tape', final_route, 'episode', tapes[final_route]['ep'], 'its shops:', tapes[final_route]['shops'])
    print('telemetry:', ns['_MGT_REPORT'], 'chassis diagnostics:', ns['_MGT_IMPL'].chassis.diagnostics)
    daily = res['daily'][seat]
    prev = Counter()
    print('day: cash | no-effect cmds | missing-hand cmds | effective')
    for d in range(1, len(daily)):
        ph = daily[d]['physical']
        print(f"  {d - 1:2d}: {daily[d]['money']:9,.0f} | {ph.get('no_effect', 0) - prev['n']:4d} | {ph.get('missing_worker_commands', 0) - prev['m']:4d} | {ph.get('effective', 0) - prev['e']:4d}")
        prev = Counter(n=ph.get('no_effect', 0), m=ph.get('missing_worker_commands', 0), e=ph.get('effective', 0))
    print('revenue:', {k: round(v) for k, v in daily[-1]['revenue'].items()})
    print('spend:', {k: round(v) for k, v in daily[-1]['spend'].items()})
    print('rival revenue:', {k: round(v) for k, v in res['daily'][1 - seat][-1]['revenue'].items()})


if __name__ == '__main__':
    main()
