"""Skeptic check 5: where do the actual steps beyond the model go (ours vs leader), and are there same-day constraints
the model does not carry? Own code, all 12 games per side, stored streams only.

  walking beyond Manhattan, split into: before the first work stay (from the spawn tile), between consecutive work
  stays with / without a shed command in between (the executor's shed detours), after the last work stay
  repeat PICKUPs of an item type already picked up that unit-day (the model allows one per item type)
  BUY_PRODUCT WHEAT / FERTILIZER by hour (a mid-day purchase can make a morning pickup impossible)
  same-hour jobs of two units on one tile (no order constraint in the model)
usage: verify_overhead.py
"""
from collections import Counter

import verify_common as V

BUCKETS = ((0, 2), (3, 11), (12, 17), (18, 23), (24, 29))


def unit_day(seq):
    c = Counter()
    stays, cur = [], None          # (tile, first index, last index)
    for k, (h, p, op, cmd) in enumerate(seq):
        if V.is_work(p, op):
            if cur is not None and cur[0] == p:
                cur[2] = k
            else:
                cur = [p, k, k]
                stays.append(cur)
        else:
            cur = None
    if not stays:
        return c
    moves = [1 if op in V.MV else 0 for h, p, op, cmd in seq]
    shed = [1 if (op in ('PICKUP', 'DROP') or (op == 'PLACE' and p in V.SHEDSET)) else 0 for h, p, op, cmd in seq]
    first = stays[0]
    c['pre_moves'] += sum(moves[:first[1]])
    c['pre_dist'] += V.dist(seq[0][1], first[0])
    for a, b in zip(stays, stays[1:]):
        mv = sum(moves[a[2] + 1:b[1]])
        dd = V.dist(a[0], b[0])
        if any(shed[a[2] + 1:b[1]]):
            c['via_shed_pairs'] += 1
            c['via_shed_moves'] += mv
            c['via_shed_dist'] += dd
        else:
            c['direct_pairs'] += 1
            c['direct_moves'] += mv
            c['direct_dist'] += dd
    last = stays[-1]
    w = [k for k, (h, p, op, cmd) in enumerate(seq) if op != 'PASS']
    post = seq[last[2] + 1:w[-1] + 1]
    pm = sum(moves[last[2] + 1:w[-1] + 1])
    c['post_moves'] += pm
    if pm:
        c['post_units'] += 1
        if any(op in ('DROP', 'PICKUP') or (op == 'PLACE' and p in V.SHEDSET) for h, p, op, cmd in post):
            c['post_moves_with_shed_cmd'] += pm
            c['post_shed_legs'] += V.dist(last[0], V.near_shed(last[0]))
        else:
            c['post_moves_no_cmd'] += pm
            if w[-1] >= len(seq) - 1 or seq[-1][0] == 23:
                c['post_moves_no_cmd_to_h23'] += pm if w[-1] == len(seq) - 1 else 0
    items = Counter()
    for h, p, op, cmd in seq:
        if op == 'PICKUP' and len(cmd) > 1:
            items[cmd[1]] += 1
            c['pk_' + cmd[1]] += 1
    c['pickups'] += sum(items.values())
    c['repeat_pickups'] += sum(v - 1 for v in items.values())
    return c


def main():
    L = ['VERIFY 5: actual walking beyond the model and same-day constraints (own code, 12 games per side, per game)']
    for side in ('ours', 'leader'):
        games = [V.load_ours(ep) for ep in V.OURS] if side == 'ours' else [V.load_leader(t, ep) for t, ep in V.LEADER]
        tot = Counter()
        byb = {b: Counter() for b in BUCKETS}
        buy_h = Counter()
        same_hour = 0
        for g in games:
            days, _ = V.rebuild(g['actions'])
            for d in range(30):
                bk = next(b for b in BUCKETS if b[0] <= d <= b[1])
                tiles = {}
                units, routes, busy, info = V.instance(days[d])
                for u, seq in days[d].items():
                    c = unit_day(seq)
                    r = routes[u]
                    f, tr_, cm_, pk_, dr_, wt_ = V.breakdown(units[u], r)
                    c['m_travel'] += tr_
                    c['m_pk'] += pk_
                    c['m_drops'] += dr_
                    c['m_wait'] += wt_
                    c['m_busy'] += V.cost(units[u], r)
                    c['a_busy'] += busy[u]
                    wl = [k for k, (h, p, op, cmd) in enumerate(seq) if op != 'PASS']
                    if wl:
                        pre = seq[:wl[-1] + 1]
                        c['a_moves'] += sum(1 for h, p, op, cmd in pre if op in V.MV)
                        c['a_shed'] += sum(1 for h, p, op, cmd in pre if op in ('PICKUP', 'DROP') or (op == 'PLACE' and p in V.SHEDSET))
                        c['a_pass'] += sum(1 for h, p, op, cmd in pre if op == 'PASS')
                    lt = max((k for k, j in enumerate(r) if j.today), default=-1)
                    if lt >= 0:
                        c['m_droplegs'] += V.dist(r[lt].tile, V.near_shed(r[lt].tile))
                    tot.update(c)
                    byb[bk].update(c)
                    for h, p, op, cmd in seq:
                        if V.is_work(p, op):
                            tiles.setdefault((p, h), set()).add(u)
                same_hour += sum(1 for k, us in tiles.items() if len(us) > 1)
            for t, a in enumerate(g['actions'][:719]):
                for o in a.get('market') or []:
                    if o and o[0] == 'BUY_PRODUCT' and len(o) > 2:
                        buy_h[(o[1], 'h0' if t % 24 == 0 else 'h1-11' if t % 24 < 12 else 'h12-23')] += int(o[2])
        n = 12

        def line(c, div, lab):
            return (f"    {lab}: actual busy {c['a_busy'] / div:.1f} - model {c['m_busy'] / div:.1f} = {(c['a_busy'] - c['m_busy']) / div:+.1f} = "
                    f"moves-travel {(c['a_moves'] - c['m_travel']) / div:+.1f} [via-shed detours {(c['via_shed_moves'] - c['via_shed_dist']) / div:+.1f}, "
                    f"after-last-stay moves minus model drop legs {(c['post_moves'] - c['m_droplegs']) / div:+.1f}, other {(c['a_moves'] - c['m_travel'] - (c['via_shed_moves'] - c['via_shed_dist']) - (c['post_moves'] - c['m_droplegs'])) / div:+.1f}] "
                    f"+ shed cmds-(pickups+drops) {(c['a_shed'] - c['m_pk'] - c['m_drops']) / div:+.1f} + PASS-wait {(c['a_pass'] - c['m_wait']) / div:+.1f}\n"
                    f"      before first stay moves {c['pre_moves'] / div:.1f} vs Manhattan {c['pre_dist'] / div:.1f}; "
                    f"between stays direct {c['direct_pairs'] / div:.0f} pairs, moves {c['direct_moves'] / div:.0f} vs Manhattan {c['direct_dist'] / div:.0f} "
                    f"(+{(c['direct_moves'] - c['direct_dist']) / div:.0f}); via a shed stop {c['via_shed_pairs'] / div:.0f} pairs, moves {c['via_shed_moves'] / div:.0f} "
                    f"vs Manhattan {c['via_shed_dist'] / div:.0f} (+{(c['via_shed_moves'] - c['via_shed_dist']) / div:.0f}); after last stay {c['post_moves'] / div:.1f}; "
                    f"PICKUPs {c['pickups'] / div:.1f} of which repeats of an item type {c['repeat_pickups'] / div:.1f}\n"
                    f"      after-last-stay moves: ending in a shed command {c['post_moves_with_shed_cmd'] / div:.1f} (Manhattan leg to the shed {c['post_shed_legs'] / div:.1f}), "
                    f"with no command at the end (walking, last move = last non-PASS) {c['post_moves_no_cmd'] / div:.1f} (of which the walk runs to the unit's last step {c['post_moves_no_cmd_to_h23'] / div:.1f}); "
                    f"model travel {c['m_travel'] / div:.0f}, model drop legs {c['m_droplegs'] / div:.1f}; "
                    f"PICKUP items {', '.join(f'{k[3:]} {v / div:.1f}' for k, v in sorted(c.items()) if k.startswith('pk_'))}")
        L.append(f"  {side}:")
        L.append(line(tot, n, 'all days, per game'))
        for b in BUCKETS:
            L.append(line(byb[b], n * (b[1] - b[0] + 1), f"days {b[0]}-{b[1]}, per day"))
        L.append(f"    BUY_PRODUCT units per game by hour: " + ', '.join(f"{k[0]} {k[1]} {v / n:.0f}" for k, v in sorted(buy_h.items())))
        L.append(f"    same tile, same hour, two units (no order constraint in the model): {same_hour / n:.1f} per game")
    txt = '\n'.join(L) + '\n'
    (V.HERE / 'verify_overhead.txt').write_text(txt, encoding='utf-8')
    print(txt)


if __name__ == '__main__':
    main()
