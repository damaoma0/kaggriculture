"""DSM's strawberry daytime returns over the 40-world panel: trips a day, cluster size (tiles, units, spread), and the
returning hand's whole day - what it did before its first strawberry harvest, between that harvest and the drop, and
after the drop (successful ops by type and target, moves, idle, a second return, where it went).
usage: dsm_return_day.py"""
import json
import statistics as stt
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
MOVES = {'NORTH', 'SOUTH', 'EAST', 'WEST'}
SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]


def kind(tl):
    if not isinstance(tl, dict):
        return 'empty'
    return tl.get('animal') or tl.get('crop') or tl.get('kind', '?')


def job(g):
    team, ep = g.split(':')
    ep = ep.strip()
    tape = UE.load_tape(int(team), int(ep))
    dr = json.loads((ROOT / 'results/fresh/threads_20260928/dsm_dayret' / f'{ep}.json').read_text())['days']
    rets = {}                                          # (day, unit) -> [(drop hour, first strawberry harvest hour, tiles)]
    for d, lst in dr.items():
        for unit, dh, dt, tiles in lst:
            st = [x for x in tiles if x[1] == 'STRAWBERRY']
            if st:
                rets.setdefault((int(d), int(unit)), []).append((int(dh), min(x[2] for x in st), [x[0] for x in st]))
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    log = defaultdict(list)                            # (day, unit) -> [(hour, op, ok, target kind, pos, carried strawberries)]
    straw_units = {}
    while w.t < 696:
        t = w.t
        d, h = t // 24, t % 24
        act = UE.tape_action(tape['actions'], t)
        farm = w.farms[seat]
        units = [tuple(farm['farmer'])] + [tuple(q) for q in farm['hands']]
        cmds = [act.get('farmer')] + list(act.get('hands') or [])
        before = json.dumps([farm['tiles'], w.private(seat)['inventories']], sort_keys=True, default=str) if d >= 11 else None
        pre = []
        if d >= 11:
            for u, p in enumerate(units):
                if (d, u) in rets:
                    c = cmds[u] if u < len(cmds) else None
                    op = c[0] if isinstance(c, list) and c else 'PASS'
                    tgt = farm['tiles'][p[1]][p[0]] if 0 <= p[0] < 10 and 0 <= p[1] < 10 else None
                    inv = (w.private(seat)['inventories'][u] if u < len(w.private(seat)['inventories']) else {}) or {}
                    pre.append((u, op, kind(tgt), p, int(inv.get('STRAWBERRY', 0) or 0), dict(inv)))
        a2 = [None, None]
        a2[seat], a2[1 - seat] = act, UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
        for u, op, k, p, sb, inv0 in pre:
            inv1 = (w.private(seat)['inventories'][u] if u < len(w.private(seat)['inventories']) else {}) or {}
            ok = op in MOVES or op == 'PASS' or inv1 != inv0 or True
            log[(d, u)].append((h, op, k, p, sb))
    out = Counter()
    rows = []
    for (d, u), lst in rets.items():
        L = log.get((d, u), [])
        if not L:
            continue
        lst = sorted(lst)
        dh, fh, tl = lst[0]
        out['returns'] += len(lst)
        out['days_with'] += 1
        out['multi_return_days'] += 1 if len(lst) > 1 else 0
        for ph, lo, hi in (('before', 1, fh - 1), ('between', fh, dh), ('after', dh + 1, 23)):
            for h, op, k, p, sb in L:
                if lo <= h <= hi:
                    key = 'move' if op in MOVES else ('idle' if op == 'PASS' else op)
                    out[f'{ph}|{key}'] += 1
                    if key not in ('move', 'idle'):
                        out[f'{ph}|on|{k}'] += 1
            out[f'{ph}|hours'] += max(0, hi - lo + 1)
        # after the drop: how far from the shed it works, and where it ends the day
        aft = [(h, p) for h, op, k, p, sb in L if h > dh]
        if aft:
            out['after_maxdist'] += max(min(abs(p[0] - a) + abs(p[1] - b) for a, b in SHED) for h, p in aft)
            out['after_n'] += 1
        rows.append((dh, fh, len(tl)))
    return dict(out), rows


if __name__ == '__main__':
    games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
    tot = Counter()
    rows = []
    with Pool(4) as pool:
        for c, r in pool.imap_unordered(job, games):
            tot.update(c)
            rows += r
    n = len(games)
    print(f'DSM strawberry daytime returns: {tot["returns"] / n:.1f} a world = {tot["returns"] / n / 18:.2f} a day over days 11-28; '
          f'on {tot["days_with"] / n:.1f} hand-days a world ({tot["multi_return_days"] / n:.1f} of them with 2+ returns by the same hand)')
    print(f'   first strawberry harvest hour median {stt.median(r[1] for r in rows)}, drop hour median {stt.median(r[0] for r in rows)}, '
          f'strawberry tiles a return median {stt.median(r[2] for r in rows)}')
    for ph in ('before', 'between', 'after'):
        hrs = tot[f'{ph}|hours']
        ops = {k.split('|', 1)[1]: v for k, v in tot.items() if k.startswith(ph + '|') and k.count('|') == 1 and not k.endswith('hours')}
        on = {k.split('|', 2)[2]: v for k, v in tot.items() if k.startswith(ph + '|on|')}
        print(f'\n{ph.upper()} ({hrs / max(1, tot["days_with"]):.1f} h a returning hand-day): ' + ', '.join(
            f'{k} {100 * v / max(1, hrs):.0f}%' for k, v in sorted(ops.items(), key=lambda kv: -kv[1])))
        print('   ops on: ' + ', '.join(f'{k} {v / max(1, tot["days_with"]):.1f}' for k, v in sorted(on.items(), key=lambda kv: -kv[1])[:8]))
    print(f'\nafter the drop, farthest distance from the shed that day: mean {tot["after_maxdist"] / max(1, tot["after_n"]):.1f} steps')
