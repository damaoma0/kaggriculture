"""Can DSM's recorded games be replayed as tapes once the hire over-requests are removed?

DSM is closed-loop, but its boards are shop-driven (70-100% of count variance by day 9) and its opening is identical
across games. The earlier 108-tape DSM library lost 9.9k with ~396 extra failed commands a game; the O1 work found why
a recorded DSM stream breaks: it asks for far more hires than it can afford (8+8 on day 1, 3+1 arrive), so a few coins
of price drift lose a hand and every later hand index shifts.

For tapes X and worlds Y (our recorded ladder games: seed, weeds, opponent's recorded moves), X is replayed with X's own
shops forced, so only replay fidelity is tested (not shop fit). Variants: raw; exact = in each step's order list the
HIREs are cut to the number that actually arrived at that step in DSM's own game (order kept). Score: board distance
(router labels, weeds as empty) from X's own recorded board on days 6/9/12/18/24, and final cash vs X's final cash.
usage: dsm_tape_fidelity_probe.py [n_tapes=12] [worlds_per_tape=3] [variants=raw,exact]
"""
import gzip, json, random, sys, time
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from opening_replay_probe import label

PASS = {'farmer': ['PASS'], 'hands': [], 'market': []}
DAYS = (6, 9, 12, 18, 24)


def exact_hires(tape):
    acts = [deepcopy(a) if isinstance(a, dict) else {} for a in tape['actions']]
    h = tape['hands_by_step']
    for t, a in enumerate(acts):
        arrived = max(0, h[t + 1] - h[t]) if (t + 1) % 24 else 0
        out, kept = [], 0
        for o in a.get('market') or []:
            if o and o[0] == 'HIRE':
                if kept < arrived:
                    out.append(o); kept += 1
                continue
            out.append(o)
        a['market'] = out
    return acts


def board_labels(rows):
    s = ''.join(rows)
    return [' .' if s[i:i + 2] in (' w', ' .') else s[i:i + 2] for i in range(0, len(s), 2)]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    import psutil
    import tape_vs_bench as TV
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    n_t = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    per = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    names = (sys.argv[3] if len(sys.argv) > 3 else 'raw,exact').split(',')
    tapes = sorted((ROOT / 'data/dsm_tapes/56444344').glob('*.json.gz'))
    worlds = sorted((ROOT / 'data/ladder_panel/56368334').glob('*.json.gz'))
    rng = random.Random(11)
    rng.shuffle(tapes); rng.shuffle(worlds)
    rows = []
    wi = 0
    for tp in tapes[:n_t]:
        X = json.load(gzip.open(tp, 'rt', encoding='utf-8'))
        ref = {d: board_labels(X['boards'][d]) for d in DAYS}
        for _ in range(per):
            wp = worlds[wi % len(worlds)]; wi += 1
            Y = json.load(gzip.open(wp, 'rt', encoding='utf-8'))
            seat, rec = Y['seat'], Y['opp_actions']
            for v in names:
                while psutil.virtual_memory().available / 1e9 < 2.5:
                    time.sleep(20)
                acts = X['actions'] if v == 'raw' else exact_hires(X)
                snap = {}

                def ours(obs, t):
                    if t % 24 == 0 and t // 24 in DAYS:
                        snap[t // 24] = [(' .' if label(x) == ' .' else label(x)) for row in obs['farms'][seat]['tiles'] for x in row]
                    a = acts[t] if t < len(acts) else PASS
                    return deepcopy(a) if isinstance(a, dict) and a else dict(PASS)
                players = [None, None]
                players[seat] = ours
                players[1 - seat] = lambda obs, t: (rec[t] if t < len(rec) and isinstance(rec[t], dict) and rec[t] else dict(PASS))
                env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': Y['seed']})
                res = TV._play(E, env, players, seat, X['shops'], None, None, seat)
                ham = {d: sum(1 for x, y in zip(snap[d], ref[d]) if x != y) for d in DAYS}
                rows.append(dict(tape=tp.name, world=Y['episode'], variant=v, ham=ham, final=res['final'][seat],
                                 x_final=X['rewards'][X['seat']], dead=res['daily'][seat][-1]['physical'].get('no_effect', 0)))
            print(tp.name[:14], Y['episode'], {r['variant']: (list(r['ham'].values()), round(r['final'])) for r in rows[-len(names):]},
                  'DSM own final', round(X['rewards'][X['seat']]), flush=True)
    print('\nboard distance from the tape\'s own recorded board, median by day (and share within 8 tiles):')
    for v in names:
        rs = [r for r in rows if r['variant'] == v]
        line = '  '.join(f"d{d} {sorted(r['ham'][d] for r in rs)[len(rs) // 2]:2d} ({100 * sum(r['ham'][d] <= 8 for r in rs) / len(rs):3.0f}%)" for d in DAYS)
        print(f"  {v:6s} n={len(rs)}  {line}  final cash median {sorted(r['final'] for r in rs)[len(rs) // 2]:,.0f} "
              f"(DSM own median {sorted(r['x_final'] for r in rs)[len(rs) // 2]:,.0f}); no-effect median {sorted(r['dead'] for r in rs)[len(rs) // 2]}")
    (ROOT / 'results/fresh/newphase_20260923/opening/dsm_fidelity.json').write_text(json.dumps(rows), encoding='utf-8')


if __name__ == '__main__':
    main()
