"""Why hands planned to act from hour 2 start late: per unit-day, when the hand appears, where it spawns vs the plan's
predicted tile, its first commands, and the first planned op's delay. usage: late_start_diag.py <arm> <n worlds>"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

arm, nw = sys.argv[1], int(sys.argv[2])
M = ROOT / 'results/fresh/sector_20260925/multi' / arm
eps = [g for g in (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()][:nw]
C = Counter()
examples = []
for g in eps:
    team, ep = g.split(':')
    d = json.loads((M / f'{ep}.json').read_text())
    tape = UE.load_tape(int(team), int(ep))
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    appear = {}
    first_cmds = {}
    while w.t < 696:
        t = w.t
        own = UE.tape_action(tape['actions'], t) if t < 264 else (s[t] if t < len(s) and isinstance(s[t], dict) and s[t] else dict(UE.PASS))
        if t >= 264:
            day, h = divmod(t, 24)
            hands = w.farms[seat]['hands']
            for i, p in enumerate(hands):
                key = (day, i + 1)
                if key not in appear:
                    appear[key] = (h, tuple(p))
                cmds = own.get('hands') or []
                if i < len(cmds) and len(first_cmds.get(key, [])) < 3:
                    first_cmds.setdefault(key, []).append((h, tuple(p), cmds[i][0] if cmds[i] else None))
        acts = [None, None]
        acts[seat], acts[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(acts)
    for day_s, t in d['tier_days'].items():
        day = int(day_s)
        info = {U['u']: U['t0'] for U in t['units']}
        spawn = t.get('spawn') or []
        for u, t0 in info.items():
            if t0 != 2 or u == 0:
                continue
            e = (t.get('exec') or {}).get(str(u)) or {}
            plan = e.get('plan') or []
            if not plan:
                continue
            tile, cmd, hp = plan[0]
            m = next((x for x in e.get('done', []) if x[1] == tile and x[2] == cmd), None)
            late = (m[0] - hp) if m else None
            ap = appear.get((day, u))
            pl_sp = tuple(spawn[u - 1]) if u - 1 < len(spawn) else None
            C['n'] += 1
            if late is None:
                C['no_match'] += 1
                continue
            C['late'] += late > 0
            if ap is None:
                C['never_appeared'] += 1
                continue
            cause = []
            if ap[0] != 2:
                cause.append('appeared_h%d' % ap[0])
            if pl_sp and ap[1] != pl_sp:
                cause.append('spawn_tile_off')
            fc = first_cmds.get((day, u), [])
            if fc and fc[0][2] == 'PASS':
                cause.append('first_cmd_PASS')
            key = '+'.join(cause) or 'none_found'
            C[('late|' if late > 0 else 'ontime|') + key] += 1
            if late > 0 and len(examples) < 8:
                examples.append((ep, day, u, 'planned spawn', pl_sp, 'appeared', ap, 'first cmds', fc, 'late', late))
n = C['n']
print(f'{arm}, {nw} worlds: hour-2 hands {n}, first op late {C["late"]} ({100 * C["late"] / max(1, n):.0f}%)')
for k, v in sorted(C.items(), key=lambda x: -x[1] if isinstance(x[0], str) and '|' in x[0] else 0):
    if isinstance(k, str) and '|' in k:
        print('  %-40s %d' % (k, v))
for e in examples:
    print('  example', e)
