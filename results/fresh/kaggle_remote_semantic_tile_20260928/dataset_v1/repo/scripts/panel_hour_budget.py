"""Hour budget per hand-day, the leader vs arms over the 40-world panel (days 11-28, hands only): hours present, work /
moves (and distinct tiles walked) / shed actions / idle, split into before the first work op, between the first and last,
and after the last. usage: panel_hour_budget.py <ARM>[,<ARM>...]"""
import json, sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE
SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]
MOVES = ('NORTH', 'SOUTH', 'EAST', 'WEST')
def dsh(p): return min(abs(p[0]-a)+abs(p[1]-b) for a, b in SHED)
def job(args):
    g, arm = args
    team, ep = g.split(':'); ep = ep.strip()
    tape = UE.load_tape(int(team), int(ep))
    s = None if arm == 'DSM' else json.loads((ROOT/'results/fresh/day12_viz'/f'{arm.lower()}_streams'/f'{ep}.json').read_text(encoding='utf-8'))['actions']
    w = UE.World(tape['seed'], tape['shops']); seat = tape['seat']
    hd = defaultdict(list)
    while w.t < 696:
        t = w.t; dd, h = t // 24, t % 24
        own = UE.tape_action(tape['actions'], t) if (s is None or t < 264) else (s[t] if isinstance(s[t], dict) and s[t] else dict(UE.PASS))
        if t >= 264:
            farm = w.farms[seat]
            units = [tuple(farm['farmer'])] + [tuple(q) for q in farm['hands']]
            cmds = [own.get('farmer')] + list(own.get('hands') or [])
            for u, p in enumerate(units):
                cm = cmds[u] if u < len(cmds) else None
                op = cm[0] if isinstance(cm, list) and cm else 'PASS'
                k = 'move' if op in MOVES else 'pass' if op == 'PASS' else 'shed' if (op in ('DROP', 'PICKUP') or (op == 'PLACE' and dsh(p) == 0 and len(cm) > 1 and cm[1] not in ('COW', 'SHEEP', 'GOOSE'))) else 'work'
                hd[(dd, u)].append((h, k, p))
        a2 = [None, None]; a2[seat], a2[1-seat] = own, UE.tape_action(tape['opp_actions'], t); w.step(a2)
    c = Counter()
    for (dd, u), ev in hd.items():
        if u == 0 or not any(k == 'work' for _, k, _ in ev): continue
        c['n'] += 1
        c['present'] += len(ev)
        c['first_h'] += ev[0][0]
        wk = [i for i, x in enumerate(ev) if x[1] == 'work']
        lw = wk[-1]; fw = wk[0]
        for i, (h, k, p) in enumerate(ev):
            seg = 'lead' if i < fw else ('tail' if i > lw else 'mid')
            c[k] += 1; c[seg + '_' + k] += 1
        c['walked_tiles'] += len(set(p for h, k, p in ev if k == 'move'))
        c['h0_' + str(ev[0][0])] += 1
    return arm, dict(c)
if __name__ == '__main__':
    games = (__import__('os').environ.get('PANEL_GAMES') or (ROOT/'results/fresh/threads_20260928/panel_dsm40b.txt').read_text()).replace(',', ' ').split()
    tot = {a: Counter() for a in sys.argv[1].split(',')}
    with Pool(4) as pool:
        for a, c in pool.imap_unordered(job, [(g, a) for a in tot for g in games]): tot[a].update(c)
    for a, c in tot.items():
        m = c['n']
        print(f'{a}: {m/40:.0f} hand-days a world | hours present {c["present"]/m:.1f} (first hour {c["first_h"]/m:.2f}; ' + ', '.join(f'h{k[3:]} {v/m:.2f}' for k, v in sorted(c.items()) if k.startswith('h0_')) + ')')
        print(f'   all day: work {c["work"]/m:.2f}, moves {c["move"]/m:.2f} (distinct tiles walked {c["walked_tiles"]/m:.1f}), shed {c["shed"]/m:.2f}, idle {c["pass"]/m:.2f}')
        for seg, lab in (('lead', 'before first work'), ('mid', 'first..last work'), ('tail', 'after last work ')):
            print(f'   {lab}: ' + ', '.join(f'{k} {c[seg + "_" + k]/m:.2f}' for k in ('work', 'move', 'shed', 'pass')))
