"""The leader's morning (hours 0..H) for days 11-29 of one recorded game, for sd_dsm_morning: at every such step the
leader's unit positions at the step start and its recorded action (farmer, hands, market); also the positions at hour H
(where the planned routes start). Written to results/fresh/threads_20260928/dsm_morning/<ep>.json.
usage: build_dsm_morning.py <team:ep>[,<team:ep>...] [--hour 8]"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

H = int(sys.argv[sys.argv.index('--hour') + 1]) if '--hour' in sys.argv else 8
OUT = ROOT / 'results/fresh/threads_20260928/dsm_morning'
OUT.mkdir(parents=True, exist_ok=True)
for g in sys.argv[1].split(','):
    team, ep = g.split(':')
    tape = UE.load_tape(int(team), int(ep))
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    steps = {}
    while w.t < 719:
        t = w.t
        own = UE.tape_action(tape['actions'], t)
        if t >= 264 and t % 24 <= H:
            f = w.farms[seat]
            steps[str(t)] = {'pos': [list(f['farmer'])] + [list(p) for p in f['hands']],
                             'act': own if t % 24 < H else None}
        acts = [None, None]
        acts[seat], acts[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(acts)
    (OUT / f'{ep}.json').write_text(json.dumps({'game': g, 'hour': H, 'steps': steps}), encoding='utf-8')
    print('written', OUT / f'{ep}.json', len(steps), 'steps')
