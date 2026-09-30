"""Cheapest-insertion helper for hand plans: tile op groups not in any route are inserted, one tile at a time (mandatory
first, then optional by value), at the route and position that add the fewest hours while the route still ends by 24,
feeds keep wheat and fertilizes keep a fertilizer (a route may take one more shed fertilizer if it declares fpick).
usage: manual_day_insert.py <catalogue.json> <plan.json> <out.json>"""
import json
import sys

ACCESS = {(4, 4), (5, 4), (4, 5), (5, 5)}
LOG = ('DROP', 'DELIVER', 'PLACE_HARVEST', 'PICKUP')
ORDER = {'DIG': 0, 'COLLECT_FERTILIZER': 1, 'FEED': 2, 'CARE': 3, 'FERTILIZE': 4, 'WATER': 5, 'HARVEST': 6, 'PLANT': 7}


def sim(R):
    x, y = R['start']
    t = int(R['t0'])
    f = int(R.get('fpick', 0))
    ff = next((k for k, s in enumerate(R['stops']) if 'FEED' in s[2]), None)
    fp = next((k for k, s in enumerate(R['stops']) if 'PICKUP' in s[2]), None)
    wheat = False
    if (ff is not None and (fp is None or fp > ff)) or f:
        t += 1
        wheat = True
    bad = 0
    for sx, sy, ops in R['stops']:
        t += abs(sx - x) + abs(sy - y)
        x, y = sx, sy
        for op in ops:
            if op == 'PICKUP':
                wheat = True
            if op == 'COLLECT_FERTILIZER':
                f += 1
            if op == 'FERTILIZE':
                if f <= 0:
                    bad += 1
                else:
                    f -= 1
            if op == 'FEED' and not wheat:
                bad += 1
            t += 1
    return t, bad


def main():
    cat = json.load(open(sys.argv[1]))
    plan = json.load(open(sys.argv[2]))
    routes = plan['routes']
    have = set()
    for R in routes:
        for sx, sy, ops in R['stops']:
            for op in ops:
                have.add((sy * 10 + sx, op))
    groups = []
    for tile, d in cat['tiles'].items():
        t = int(tile)
        ops = [(op, m, v) for op, m, v, _ in d['ops'] if op not in LOG and (t, op) not in have]
        seen, uniq = set(), []
        for o in ops:
            if o[0] not in seen or o[0] == 'WATER':
                uniq.append(o)
                seen.add(o[0])
        if uniq:
            mand = any(m for _, m, _ in uniq)
            groups.append((0 if mand else 1, -sum(v for _, m, v in uniq if not m), t, uniq))
    groups.sort()
    left = []
    for _, _, t, ops in groups:
        opl = sorted([o[0] for o in ops], key=lambda c: ORDER.get(c, 5))
        best = None
        for ri, R in enumerate(routes):
            base, bad0 = sim(R)
            for k in range(len(R['stops']) + 1):
                for fpadd in (0, 1):
                    if fpadd and 'FERTILIZE' not in opl:
                        continue
                    R2 = dict(R, stops=R['stops'][:k] + [[t % 10, t // 10, opl]] + R['stops'][k:],
                              fpick=int(R.get('fpick', 0)) + fpadd)
                    end, bad = sim(R2)
                    if end <= 24 and bad <= bad0:
                        cost = end - base + 3 * fpadd
                        if best is None or cost < best[0]:
                            best = (cost, ri, R2)
        if best is None and any(m for _, m, _ in ops):    # a mandatory tile: make room by dropping cheap optional ops
            vals = {}
            for tile, d in cat['tiles'].items():
                for op, m, v, _ in d['ops']:
                    if not m:
                        vals[(int(tile), op)] = v
            for ri, R in enumerate(routes):
                for k in range(len(R['stops']) + 1):
                    R2 = dict(R, stops=[list(x) for x in R['stops'][:k]] + [[t % 10, t // 10, opl]] + [list(x) for x in R['stops'][k:]])
                    lost = 0.0
                    while sim(R2)[0] > 24:
                        cands = [(vals.get((sy * 10 + sx, op), 1e9), j, op) for j, (sx, sy, sops) in enumerate(R2['stops'])
                                 if j != k for op in sops if (sy * 10 + sx, op) in vals and op not in ('COLLECT_FERTILIZER',)]
                        if not cands:
                            break
                        v, j, op = min(cands)
                        R2['stops'][j] = [R2['stops'][j][0], R2['stops'][j][1], [o for o in R2['stops'][j][2] if o != op]]
                        R2['stops'] = [x for x in R2['stops'] if x[2]]
                        lost += v
                        if j < k:
                            k -= 1
                    end, bad = sim(R2)
                    if end <= 24 and bad <= sim(R)[1] and (best is None or lost < best[0]):
                        best = (lost, ri, R2)
            if best is not None:
                print('made room for', (t % 10, t // 10, opl), 'dropping optional value', round(best[0]))
        if best is None:
            left.append((t % 10, t // 10, opl))
            continue
        routes[best[1]] = best[2]
    json.dump({'routes': routes}, open(sys.argv[3], 'w'), indent=1)
    print('not insertable:', left)


if __name__ == '__main__':
    main()
