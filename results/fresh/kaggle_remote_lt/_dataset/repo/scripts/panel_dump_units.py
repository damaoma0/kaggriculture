"""Whose goods the midnight dump deletes (arm over the 40-world panel, days 11-28): the engine drops the farmer's
inventory first, then the hands' in hire order, into the shed up to its capacity and discards the rest. This hooks the
engine's drop for our seat and records, per night, the units each inventory carried and lost, by unit class (farmer /
hour-0 hire / hour-1 hire) and product.
usage: panel_dump_units.py <ARM>[,<ARM>...] [--workers 4]"""
import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402


def job(args):
    g, arm = args
    team, ep = g.split(':')
    ep = ep.strip()
    tape = UE.load_tape(int(team), int(ep))
    s = None if arm == 'DSM' else json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    E = w.E
    c = Counter()
    first_h = {}
    state = {'day': None}
    orig = E._drop_inventories_to_shed

    def hooked(private, capacity):
        if private is w.private(seat) and state['day'] is not None and state['day'] >= 11:
            shed = private['shed']
            cur = sum(shed.values())
            c['nights'] += 1
            c['shed_before'] += cur
            for u, inv in enumerate(private['inventories']):
                cls = 'farmer' if u == 0 else ('hour1_hire' if first_h.get((state['day'], u), 1) >= 2 else 'hour0_hire')
                for item, n in inv.items():
                    if n <= 0:
                        continue
                    room = max(0, capacity - cur)
                    take = min(n, room)
                    cur += take
                    c['carried|' + cls] += n
                    if n - take:
                        c['lost|' + cls] += n - take
                        c['lostp|' + item] += n - take
                        c['lost'] += n - take
        return orig(private, capacity)
    E._drop_inventories_to_shed = hooked
    try:
        while w.t < 696:
            t = w.t
            dd, h = t // 24, t % 24
            state['day'] = dd
            own = UE.tape_action(tape['actions'], t) if (s is None or t < 264) else (s[t] if isinstance(s[t], dict) and s[t] else dict(UE.PASS))
            if t >= 264:
                farm = w.farms[seat]
                for u in range(1 + len(farm['hands'])):
                    first_h.setdefault((dd, u), h)
            a2 = [None, None]
            a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
            w.step(a2)
    finally:
        E._drop_inventories_to_shed = orig
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
        print(f'{a}: deleted at midnight {c["lost"] / n:.1f} units a world (shed before the dump {c["shed_before"] / max(1, c["nights"]):.0f} a night) | '
              + ', '.join(f'{k.split("|")[1]} carried {c["carried|" + k.split("|")[1]] / n:.0f} lost {v / n:.1f}' for k, v in sorted(c.items()) if k.startswith('lost|'))
              + ' | by product: ' + ', '.join(f'{k.split("|")[1]} {v / n:.1f}' for k, v in sorted(c.items(), key=lambda kv: -kv[1]) if k.startswith('lostp|')))
        print(f'   carried into the dump: ' + ', '.join(f'{k.split("|")[1]} {v / n:.0f}' for k, v in sorted(c.items()) if k.startswith('carried|')))
