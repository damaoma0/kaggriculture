"""KWE thread: planned vs executed on sample days (code check before any verdict). For the chosen tiles (default: our
live geese), the tier plan's stops of the day (unit, ops, mandatory flag, value) against what the engine executed there
(hour, unit, op, success), plus the goose's day-end state (fed / cared / bank / eggs added).
usage: wheategg_verify.py <team:ep> <ARM> <day,day,...> [--tiles 31,32]"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import wheategg_diag as D  # noqa: E402
import upkeep_engine as UE  # noqa: E402


def main():
    g, arm, days = sys.argv[1], sys.argv[2], [int(x) for x in sys.argv[3].split(',')]
    team, ep = g.split(':')
    tape = UE.load_tape(int(team), int(ep))
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))
    res = json.loads((ROOT / 'results/fresh/sector_20260925/multi' / arm / f'{ep}.json').read_text(encoding='utf-8'))
    L = D.run(tape, s['actions'])
    geese = sorted(set(e[2] * 10 + e[1] for e in L['goose_log']))
    tiles = [int(x) for x in sys.argv[sys.argv.index('--tiles') + 1].split(',')] if '--tiles' in sys.argv else geese
    for day in days:
        td = res['tier_days'].get(str(day), {})
        print(f'=== {arm} day {day}')
        for b in tiles:
            plan = []
            for u in td.get('units', []):
                for tile, ops in u.get('stops_v', []):
                    if tile == b:
                        plan.append(f"u{u['u']}:" + ','.join(f"{o[0]}{'(M)' if o[1] else ''}{int(o[3])}" for o in ops))
            exe = [f"h{t % 24}:u{idx}:{op}{'' if ok else '(no-op)'}" for t, idx, op, ok, tile in L['goose_steps']
                   if t // 24 == day and tile == b]
            st = [e for e in L['goose_log'] if e[0] == day and e[2] * 10 + e[1] == b]
            st = st[0] if st else None
            end = (f"fed={st[3]} cared={st[4]} bank_in={st[5]} held={st[6]} +eggs={st[7]}" if st else '-')
            print(f"  tile {b}: PLANNED {' | '.join(plan) or '-'}\n           EXECUTED {' '.join(exe) or '-'}\n           END {end}")


if __name__ == '__main__':
    main()
