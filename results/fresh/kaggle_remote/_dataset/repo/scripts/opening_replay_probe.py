"""New-opening plan, measurement 2: is the leaders' opening REPLAYABLE as an open-loop tape in other worlds?

DSM's day-6 board is the same in every game (median 1 tile apart) although its actions differ, and it ends day 1 with
~4 coins, so a recorded opening may fail its budget-exact purchases elsewhere. Here DSM's recorded actions for days
0-5 (from a few source games, scripts/opening_handoff_probe.py) are replayed in our recorded ladder worlds
(data/ladder_panel, our seat, the opponent's recorded moves, recorded shops forced), and the board on the morning of
day 6 is compared with DSM's own day-6 board (router tile labels, weeds as empty), together with cash and hands.
One process, no agent file loaded.
usage: opening_replay_probe.py [n_worlds=24] [n_sources=3]
Writes results/fresh/newphase_20260923/opening/replay_probe.json
"""
import gzip, json, sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
OUT = ROOT / 'results/fresh/newphase_20260923/opening'
PASS = {'farmer': ['PASS'], 'hands': [], 'market': []}


def label(tile):
    if tile == 'LOCKED':
        return ' L'
    if tile is None:
        return ' .'
    kind = tile.get('kind')
    if kind == 'PLANT':
        return str(tile.get('crop'))[:2]
    if kind == 'WEED':
        return ' .'
    if tile.get('animal'):
        return str(tile['animal'])[:2].lower()
    return str(kind)[:2].lower()


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    n_worlds = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    n_src = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    import tape_vs_bench as TV
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    probe = json.loads((OUT / 'handoff_probe.json').read_text(encoding='utf-8'))
    sources = [g for g in probe['games'] if not (isinstance(g['seat'], int) and False)][:n_src]
    worlds = sorted((ROOT / 'data/ladder_panel/56368334').glob('*.json.gz'))[:n_worlds]
    rows = []
    for src in sources:
        ref6 = src['boards'][6]
        for wp in worlds:
            g = json.load(gzip.open(wp, 'rt', encoding='utf-8'))
            seat, rec = g['seat'], g['opp_actions']
            snap = {}
            acts = src['actions']

            def ours(obs, t):
                if t == 144:
                    farm = obs['farms'][seat]
                    snap.update(board=[label(x) for row in farm['tiles'] for x in row], cash=farm['money'],
                                hands=len(farm['hands']), quads=list(farm.get('unlocked_quadrants') or []))
                if t == 24:
                    snap['cash1'] = obs['farms'][seat]['money']
                return deepcopy(acts[t]) if t < 144 and t < len(acts) else dict(PASS)
            players = [None, None]
            players[seat] = ours
            players[1 - seat] = lambda obs, t: (rec[t] if t < len(rec) and isinstance(rec[t], dict) and rec[t] else dict(PASS))
            env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': g['seed']})
            TV._play(E, env, players, seat, g['shops'], None, None, seat)
            ham = sum(1 for x, y in zip(snap['board'], ref6) if x != y)
            rows.append(dict(src=src['ep'], world=g['episode'], ham6=ham, cash6=snap['cash'], cash1=snap.get('cash1'),
                             ref_cash6=src['cash'][6], ref_cash1=src['cash'][1], hands6=snap['hands']))
            print(f"source {src['ep']} world {g['episode']}: day-6 board {ham:2d} tiles from DSM's; cash day1 {snap.get('cash1')} "
                  f"(DSM {src['cash'][1]}), day6 {snap['cash']} (DSM {src['cash'][6]})", flush=True)
    hams = [r['ham6'] for r in rows]
    print(f"\n{len(rows)} replays: day-6 board identical in {sum(h == 0 for h in hams)}, within 2 tiles in {sum(h <= 2 for h in hams)}, "
          f"within 8 in {sum(h <= 8 for h in hams)}; median {sorted(hams)[len(hams) // 2]}, max {max(hams)}")
    (OUT / 'replay_probe.json').write_text(json.dumps(rows), encoding='utf-8')


if __name__ == '__main__':
    main()
