"""Strawberry delivery hands, the leader vs arms over the 40-world panel (days 11-28): a hand-day that puts strawberries
into the shed mid-day (DROP / PLACE on an access tile at hours 2-21, the hand's strawberry stock falls) and works again
afterwards. Per such hand-day: strawberries delivered, strawberry harvests before the drop, OTHER work before the drop
(the outbound leg's extra work) and after it (the second leg), by op type; hours walking; the drop hour; compared with
the arm's average working hand-day.
usage: panel_straw_delivery.py <ARM>[,<ARM>...] [--workers 4]"""
import json
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]
MOVES = ('NORTH', 'SOUTH', 'EAST', 'WEST')


def dsh(p):
    return min(abs(p[0] - a) + abs(p[1] - b) for a, b in SHED)


def job(args):
    g, arm = args
    team, ep = g.split(':')
    ep = ep.strip()
    tape = UE.load_tape(int(team), int(ep))
    s = None if arm == 'DSM' else json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    log = defaultdict(list)                              # (day, unit) -> [(hour, kind, op label, strawberries dropped)]
    while w.t < 696:
        t = w.t
        dd, h = t // 24, t % 24
        own = UE.tape_action(tape['actions'], t) if (s is None or t < 264) else (s[t] if isinstance(s[t], dict) and s[t] else dict(UE.PASS))
        rec = []
        if t >= 264:
            farm = w.farms[seat]
            units = [tuple(farm['farmer'])] + [tuple(q) for q in farm['hands']]
            cmds = [own.get('farmer')] + list(own.get('hands') or [])
            invs = w.private(seat)['inventories']
            for u, p in enumerate(units):
                cm = cmds[u] if u < len(cmds) else None
                op = cm[0] if isinstance(cm, list) and cm else 'PASS'
                if op in MOVES:
                    k, lab = 'move', op
                elif op == 'PASS':
                    k, lab = 'pass', op
                elif op in ('DROP', 'PICKUP') or (op == 'PLACE' and dsh(p) == 0 and len(cm) > 1 and cm[1] not in ('COW', 'SHEEP', 'GOOSE')):
                    k, lab = 'shed', op
                else:
                    tl = farm['tiles'][p[1]][p[0]]
                    what = (tl.get('animal') or tl.get('crop') or tl.get('kind')) if isinstance(tl, dict) else '-'
                    k, lab = 'work', op + ':' + str(what)
                s0 = int((invs[u] if u < len(invs) else {}).get('STRAWBERRY', 0) or 0)
                rec.append((u, h, k, lab, s0))
        a2 = [None, None]
        a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
        if rec:
            invs = w.private(seat)['inventories']
            for u, h, k, lab, s0 in rec:
                s1 = int((invs[u] if u < len(invs) else {}).get('STRAWBERRY', 0) or 0)
                log[(dd, u)].append((h, k, lab, max(0, s0 - s1) if k == 'shed' else 0))
    c = Counter()
    for (dd, u), ev in log.items():
        nwork = sum(1 for x in ev if x[1] == 'work')
        if nwork == 0:
            continue
        c['hand_days'] += 1
        c['all_work'] += nwork
        c['all_move'] += sum(1 for x in ev if x[1] == 'move')
        di = next((i for i, x in enumerate(ev) if x[3] > 0 and 2 <= x[0] <= 21), None)
        if di is None or not any(x[1] == 'work' for x in ev[di + 1:]):
            continue
        c['dh'] += 1
        c['delivered'] += sum(x[3] for x in ev if 2 <= x[0] <= 21)
        c['drop_hour'] += ev[di][0]
        before, after = ev[:di], ev[di + 1:]
        for lab_, part in (('b', before), ('a', after)):
            for x in part:
                if x[1] == 'work':
                    if x[2] == 'HARVEST:STRAWBERRY':
                        c[lab_ + '_sharv'] += 1
                    else:
                        c[lab_ + '_extra'] += 1
                        c[lab_ + '|' + x[2]] += 1
                elif x[1] == 'move':
                    c[lab_ + '_move'] += 1
                elif x[1] == 'shed':
                    c[lab_ + '_shed'] += 1
                elif x[1] == 'pass':
                    c[lab_ + '_pass'] += 1
        c['shed_at_drop'] += sum(1 for x in after[:3] if x[1] == 'shed') + 1
    return arm, dict(c)


if __name__ == '__main__':
    arms = sys.argv[1].split(',')
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
    tot = {a: Counter() for a in arms}
    with Pool(nw) as pool:
        for arm, c in pool.imap_unordered(job, [(g, a) for a in arms for g in games]):
            tot[arm].update(c)
    n = len(games)
    for a in arms:
        c = tot[a]
        m = max(1, c['dh'])
        print(f'\n{a}: strawberry delivery hand-days {c["dh"] / n:.1f} a world, {c["delivered"] / m:.1f} strawberries each, drop at hour {c["drop_hour"] / m:.1f} '
              f'| average working hand-day: {c["all_work"] / max(1, c["hand_days"]):.1f} work ops, {c["all_move"] / max(1, c["hand_days"]):.1f} moves')
        for lab_, name in (('b', 'before the drop'), ('a', 'after the drop ')):
            print(f'   {name}: strawberry harvests {c[lab_ + "_sharv"] / m:.1f}, OTHER work {c[lab_ + "_extra"] / m:.1f}, moves {c[lab_ + "_move"] / m:.1f}, '
                  f'shed actions {c[lab_ + "_shed"] / m:.1f}, idle {c[lab_ + "_pass"] / m:.1f}')
            print('      other work: ' + ', '.join(f'{k[2:]} {v / m:.1f}' for k, v in sorted(c.items(), key=lambda kv: -kv[1]) if k.startswith(lab_ + '|'))[:400])
        tw = (c['b_sharv'] + c['b_extra'] + c['a_sharv'] + c['a_extra']) / m
        print(f'   whole day: {tw:.1f} work ops ({(c["b_extra"] + c["a_extra"]) / m:.1f} besides strawberry harvests) vs {c["all_work"] / max(1, c["hand_days"]):.1f} for an average hand')
