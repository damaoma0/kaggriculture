"""Vital-statistics table (the path-planner thread's, 2026-09-27) from the text output of panel_path_metrics /
panel_hour_budget / panel_tile_coverage / panel_hand_time (PANEL_GAMES = the worlds, per world, days 11-28, hired
hands), one column per arm, in the order given.
usage: vitals_table.py <vitals.txt>[,<vitals.txt>...] ARM[,ARM...] [--md]"""
import re
import sys
from pathlib import Path


def parse(texts):
    V = {}

    def put(arm, k, v):
        V.setdefault(arm, {})[k] = v
    for txt in texts:
        sec, cur = None, None
        for ln in txt.splitlines():
            m = re.match(r'=== (\w+)', ln)
            if m:
                sec, cur = m.group(1), None
                continue
            if sec == 'panel_path_metrics':
                m = re.match(r'^(\w+):\s*$', ln)
                if m:
                    cur = m.group(1)
                    continue
                m = re.match(r'\s+(radial|returning)\s*:.*path steps between visits (\d+)%', ln)
                if m and cur:
                    kind = m.group(1)
                    put(cur, f'path_{kind}', int(m.group(2)))
                    continue
                m = re.match(r'\s+shape:.*jump 4\+ (\d+)%', ln)
                if m and cur:
                    put(cur, f'jump_{kind}', int(m.group(1)))
            elif sec == 'panel_hour_budget':
                m = re.match(r'^(\w+): .*hand-days a world', ln)
                if m:
                    cur = m.group(1)
                    continue
                m = re.match(r'\s+all day: work ([\d.]+), moves ([\d.]+).*shed ([\d.]+), idle ([\d.]+)', ln)
                if m and cur:
                    for k, v in zip(('work_h', 'move_h', 'shed_h', 'idle_h'), m.groups()):
                        put(cur, k, float(v))
                    continue
                m = re.match(r'\s+before first work: work [\d.]+, move ([\d.]+)', ln)
                if m and cur:
                    put(cur, 'walk_first', float(m.group(1)))
            elif sec == 'panel_tile_coverage':
                m = re.match(r'^(\w+) hands: .*tiles walked over \(not worked\) ([\d.]+) \| tiles worked ([\d.]+).*ops ([\d.]+), ops per worked tile ([\d.]+)', ln)
                if m:
                    cur = m.group(1)
                    put(cur, 'walk_only', float(m.group(2)))
                    put(cur, 'tiles_worked', float(m.group(3)))
                    put(cur, 'ops_hd', float(m.group(4)))
                    put(cur, 'ops_tile', float(m.group(5)))
                    continue
                m = re.match(r'^(\w+) farm-day: .*by 2 ([\d.]+), by 3\+ ([\d.]+)', ln)
                if m:
                    put(m.group(1), 'shared', float(m.group(2)) + float(m.group(3)))
                    continue
                m = re.match(r'\s+hand-visits a day / ops per hand-visit: (.*)', ln)
                if m and cur:
                    for kind in ('SHEEP', 'COW', 'GOOSE'):
                        mm = re.search(kind + r' [\d.]+ / ([\d.]+)', m.group(1))
                        if mm:
                            put(cur, 'pen_' + kind, float(mm.group(1)))
            elif sec == 'panel_hand_time':
                m = re.match(r'^(\w+): unit-hours a world: move (\d+), work (\d+)', ln)
                if m:
                    cur = m.group(1)
                    put(cur, 'ops_total', int(m.group(3)))
                    continue
                m = re.match(r'\s+ops: (.*)', ln)
                if m and cur:
                    for k in ('COLLECT_FERTILIZER', 'CARE', 'FERTILIZE', 'WATER', 'FEED', 'HARVEST'):
                        mm = re.search(r'(?<![A-Z_])' + k + r' (\d+)', m.group(1))
                        put(cur, 'op_' + k, int(mm.group(1)) if mm else 0)
    return V


ROWS = [('Work hours a hand-day', 'work_h', '{:.2f}'),
        ('Move / shed / idle hours', ('move_h', 'shed_h', 'idle_h'), '{:.2f}'),
        ('Walking before the first job (hours)', 'walk_first', '{:.2f}'),
        ('Tiles worked a hand-day', 'tiles_worked', '{:.1f}'),
        ('Ops per worked tile', 'ops_tile', '{:.2f}'),
        ('Tiles walked over without work', 'walk_only', '{:.1f}'),
        ('Outbound: steps that follow a path (jumps 4+)', ('path_radial', 'jump_radial'), '{}%'),
        ('Returning: steps that follow a path (jumps 4+)', ('path_returning', 'jump_returning'), '{}%'),
        ('Tiles served by 2+ hands a day', 'shared', '{:.1f}'),
        ('Ops per pen visit (sheep / cow / goose)', ('pen_SHEEP', 'pen_COW', 'pen_GOOSE'), '{:.2f}'),
        ('Total work ops', 'ops_total', '{:,}'),
        ('Collect / care / fertilize ops', ('op_COLLECT_FERTILIZER', 'op_CARE', 'op_FERTILIZE'), '{:,}')]


def cell(d, key, fmt):
    if isinstance(key, tuple):
        vals = [d.get(k) for k in key]
        if key[0].startswith('path_'):
            return '—' if vals[0] is None else (f'{vals[0]}%' if vals[1] is None else f'{vals[0]}% ({vals[1]}%)')
        return ' / '.join('—' if v is None else fmt.format(v) for v in vals)
    v = d.get(key)
    return '—' if v is None else fmt.format(v)


def main():
    texts = [Path(p).read_text(encoding='utf-8') for p in sys.argv[1].split(',')]
    arms = sys.argv[2].split(',')
    V = parse(texts)
    print('| | ' + ' | '.join(arms) + ' |')
    print('|---|' + '---:|' * len(arms))
    for lab, key, fmt in ROWS:
        print(f'| {lab} | ' + ' | '.join(cell(V.get(a, {}), key, fmt) for a in arms) + ' |')


if __name__ == '__main__':
    main()
