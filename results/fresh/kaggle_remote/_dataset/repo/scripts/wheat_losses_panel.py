"""KW thread: aggregate midnight-dump deletions (scripts/season_losses.py's run()) across the panel13 worlds, for
one or more of our arms' saved streams vs the leader tape. Read-only, reuses season_losses.run() directly (no
subprocess per world).

usage: wheat_losses_panel.py arm1,arm2,... [dump.json]
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import season_losses as SL  # noqa: E402
import upkeep_engine as UE  # noqa: E402
from run_arms import PANEL13  # noqa: E402


def total_lost(lost):
    return sum(sum(v.values()) for v in lost.values())


def wheat_lost(lost):
    return sum(v.get('WHEAT', 0) for v in lost.values())


def main():
    arms = sys.argv[1].split(',')
    dump = sys.argv[2] if len(sys.argv) > 2 else None
    rows = {a: [] for a in ['leader'] + arms}
    for game in PANEL13:
        team, ep = game.split(':')
        tape = UE.load_tape(team, int(ep))
        r = SL.run(tape, None)
        rows['leader'].append((total_lost(r['lost']), wheat_lost(r['lost'])))
        for arm in arms:
            f = ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json'
            if not f.exists():
                rows[arm].append(None)
                continue
            st = json.loads(f.read_text())
            r = SL.run(tape, st['actions'])
            rows[arm].append((total_lost(r['lost']), wheat_lost(r['lost'])))
    print(f'{"arm":8s} {"total_del":>10s} {"wheat_del":>10s}')
    for a in ['leader'] + arms:
        vals = [x for x in rows[a] if x is not None]
        tot = sum(x[0] for x in vals)
        wh = sum(x[1] for x in vals)
        print(f'{a:8s} {tot:10d} {wh:10d}')
    print()
    for arm in arms:
        print(f'--- {arm} per-world (total_del, wheat_del) vs leader ---')
        for game, lw, aw in zip(PANEL13, rows['leader'], rows[arm]):
            ep = game.split(':')[1]
            if aw is None:
                print(f'  {ep}: missing stream')
                continue
            print(f'  {ep}: leader total {lw[0]:3d} wheat {lw[1]:3d} | {arm} total {aw[0]:3d} wheat {aw[1]:3d}')
    if dump:
        Path(dump).write_text(json.dumps({'rows': rows, 'episodes': [g.split(":")[1] for g in PANEL13]}), encoding='utf-8')
        print('wrote', dump)


if __name__ == '__main__':
    main()
