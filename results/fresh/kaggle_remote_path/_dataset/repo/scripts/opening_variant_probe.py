"""Make the recorded DSM opening robust to price drift, offline. The recording is budget-exact and over-requests HIREs
(DSM asks 8+8 on day 1 and gets 3+1 with ~6 coins); a few coins less against a different opponent loses a hand, and
every later hand index shifts (O1 panels: day-6 board 12-15 tiles off in 132 of 174 worlds).

Variants of the opening orders (days 0-5), replayed raw in recorded ladder worlds (our seat, recorded opponent and
shops), scored by the day-6 board distance from DSM's recorded day-6 board:
  raw      the recording as is
  exact    HIREs replaced by the number that actually ARRIVED at that step in DSM's own game
  exact4   exact + the day-0 feed-wheat buy trimmed 5 -> 4 (a ~28-coin cushion)
  exactsell exact + one extra SELL WHEAT at a morning hire step when cash is short of that step's wages
usage: opening_variant_probe.py <world-list-json> [n] [variants=raw,exact,exact4,exactsell]
"""
import gzip, json, sys, time
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from opening_replay_probe import label

PASS = {'farmer': ['PASS'], 'hands': [], 'market': []}
FIB = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377]


def variant_actions(src, name):
    acts = [deepcopy(a) for a in src['actions']]
    if name == 'raw':
        return acts
    hands = src['hands_by_step']
    for t in range(len(acts)):
        m = [o for o in (acts[t].get('market') or []) if o and o[0] != 'HIRE']
        arrived = max(0, hands[t + 1] - hands[t]) if (t + 1) % 24 else 0
        if arrived:
            m = [['HIRE'] for _ in range(arrived)] + m          # hires first, so no purchase can take their wage
        acts[t]['market'] = m
    if name == 'exact4':
        acts[0]['market'] = [(['BUY_PRODUCT', 'WHEAT', 4] if o[:2] == ['BUY_PRODUCT', 'WHEAT'] and o[2] == 5 else o) for o in acts[0]['market']]
    return acts


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    import psutil
    import tape_vs_bench as TV
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    worlds = json.loads(Path(sys.argv[1]).read_text())
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 16
    names = (sys.argv[3] if len(sys.argv) > 3 else 'raw,exact,exact4,exactsell').split(',')
    src = json.loads((ROOT / 'data/openings/dsm_329f3ad2.json').read_text(encoding='utf-8'))
    ref6 = [src['boards'][6][i:i + 2] for i in range(0, 200, 2)]
    res = {v: [] for v in names}
    for w in worlds[:n]:
        g = json.load(gzip.open(ROOT / f'data/ladder_panel/56368334/{w}.json.gz', 'rt', encoding='utf-8'))
        seat, rec = g['seat'], g['opp_actions']
        for v in names:
            while psutil.virtual_memory().available / 1e9 < 2.5:
                time.sleep(20)
            acts = variant_actions(src, 'exact' if v == 'exactsell' else v)
            snap = {}

            def ours(obs, t):
                farm = obs['farms'][seat]
                if t == 144:
                    snap['board'] = [label(x) for row in farm['tiles'] for x in row]
                    snap['cash'] = farm['money']
                if t >= 144:
                    return dict(PASS)
                a = deepcopy(acts[t])
                if v == 'exactsell':
                    hires = sum(1 for o in a['market'] if o[0] == 'HIRE')
                    if hires:
                        have = len(farm['hands'])
                        wage = sum(FIB[min(len(FIB) - 1, have + i)] for i in range(hires))
                        if farm['money'] < wage and int((obs['private'].get('shed') or {}).get('WHEAT', 0) or 0) > 0:
                            a['market'] = [['SELL', 'WHEAT', 1]] + a['market']
                return a
            players = [None, None]
            players[seat] = ours
            players[1 - seat] = lambda obs, t: (rec[t] if t < len(rec) and isinstance(rec[t], dict) and rec[t] else dict(PASS))
            env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': g['seed']})
            TV._play(E, env, players, seat, g['shops'], None, None, seat)
            res[v].append(dict(world=w, ham=sum(1 for x, y in zip(snap['board'], ref6) if x != y), cash=snap['cash']))
        print(w, {v: (res[v][-1]['ham'], res[v][-1]['cash']) for v in names}, flush=True)
    print('\nday-6 board distance from DSM (tiles):')
    for v in names:
        h = [r['ham'] for r in res[v]]
        print(f"  {v:10s} exact {sum(x == 0 for x in h):2d}/{len(h)}, <=2 {sum(x <= 2 for x in h):2d}, <=8 {sum(x <= 8 for x in h):2d}, "
              f"median {sorted(h)[len(h) // 2]}, mean cash day 6 {sum(r['cash'] for r in res[v]) / len(h):.0f}")
    (ROOT / 'results/fresh/newphase_20260923/opening/variant_probe.json').write_text(json.dumps(res), encoding='utf-8')


if __name__ == '__main__':
    main()
