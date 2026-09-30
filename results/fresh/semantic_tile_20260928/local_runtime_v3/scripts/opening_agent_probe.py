"""O1 sanity check before a panel: play an agent that carries the opening route in recorded ladder worlds (recorded
opponent, recorded shops) and report, per world, its day-6 board distance from DSM's recorded day-6 board, cash on
day 1 / day 6, the tape the router hands off to on day 6 (and its tile Hamming), whether the fallback fired, and
the final margin. One game process at a time, memory-checked.
usage: opening_agent_probe.py <agent> [n_worlds=8]"""
import gzip, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
PASS = {'farmer': ['PASS'], 'hands': [], 'market': []}
from opening_replay_probe import label


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    import psutil
    agent = sys.argv[1]; n = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    ref = json.loads((ROOT / 'data/openings/dsm_329f3ad2.json').read_text(encoding='utf-8'))
    ref6 = [ref['boards'][6][i:i + 2] for i in range(0, 200, 2)]
    import tape_vs_bench as TV
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    rows = []
    for wp in sorted((ROOT / 'data/ladder_panel/56368334').glob('*.json.gz'))[:n]:
        while psutil.virtual_memory().available / 1e9 < 3.0:
            time.sleep(30)
        g = json.load(gzip.open(wp, 'rt', encoding='utf-8'))
        seat, rec = g['seat'], g['opp_actions']
        ap = ROOT / 'agents' / f'{agent}.py'
        entry = get_last_callable(ap.read_text(encoding='utf-8'), path=str(ap))
        snap = {}

        def ours(obs, t):
            farm = obs['farms'][seat]
            if t in (24, 144):
                snap[t] = dict(board=[label(x) for row in farm['tiles'] for x in row], cash=farm['money'])
            return entry(obs)
        players = [None, None]
        players[seat] = ours
        players[1 - seat] = lambda obs, t: (rec[t] if t < len(rec) and isinstance(rec[t], dict) and rec[t] else dict(PASS))
        env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': g['seed']})
        res = TV._play(E, env, players, seat, g['shops'], None, None, seat)
        G = entry.__globals__
        hist = G.get('_MGT_HISTORY') or []
        d6 = next((h for h in hist if h[0] == 6), None)
        ham = sum(1 for x, y in zip(snap[144]['board'], ref6) if x != y)
        rows.append(dict(world=g['episode'], ham6=ham, cash1=snap[24]['cash'], cash6=snap[144]['cash'], handoff=d6,
                         fallback=(G.get('_MGT_REPORT') or {}).get('opening_fallback', 0), margin=res['final'][seat] - res['final'][1 - seat],
                         final=res['final'][seat], switches=[h[:2] for h in hist]))
        r = rows[-1]
        print(f"world {r['world']}: day-6 board {ham:2d} tiles from DSM's, cash d1 {r['cash1']:.0f} d6 {r['cash6']:.0f}; handoff {d6}; "
              f"fallback {r['fallback']}; margin {r['margin']:+,.0f}", flush=True)
        del entry, G
    out = ROOT / f'results/fresh/newphase_20260923/opening/agent_probe_{agent}.json'
    out.write_text(json.dumps(rows), encoding='utf-8')


if __name__ == '__main__':
    main()
