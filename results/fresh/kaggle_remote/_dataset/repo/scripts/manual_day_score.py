"""Score a hand-made day plan against the day's work catalogue (scripts output results/fresh/manual_day/<ep>_d<day>_catalogue.json)
with the tier planner's time model: one hour a step (Manhattan) or an op; a route that feeds starts with one pickup hour at
its start tile (a shed access tile); FERTILIZE needs a fertilizer from a COLLECT earlier on the same route (sd_fert_sell 1:
no shed fertilizer) unless the route declares "fpick"; ops after hour 23 are late.
plan JSON: {"routes": [{"u": 0, "start": [4, 4], "t0": 1, "fpick": 0, "stops": [[x, y, ["OP", ...]], ...]}, ...]}
Also scores the planner's own routes from its log for the same day (--planner ARM ep day).
usage: manual_day_score.py <catalogue.json> <plan.json> | manual_day_score.py <catalogue.json> --planner ARM ep day"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGISTICS = ('DROP', 'DELIVER', 'PLACE_HARVEST', 'PICKUP')
ACCESS = {(4, 4), (5, 4), (4, 5), (5, 5)}


def score(cat, routes, label):
    need = {}
    val = {}
    import re
    sty = {}
    for tile, d in cat['tiles'].items():
        mm = re.match(r'STRAWBERRY .* y(\d+)', d['state'])
        if mm:
            sty[int(tile)] = int(mm.group(1))
        for op, m, v, _ in d['ops']:
            if op in LOGISTICS:
                continue
            k = (int(tile), op)
            need[k] = need.get(k, False) or m
            val[k] = max(val.get(k, 0), v if not m else 0)
    done = Counter()
    deliv = []
    tot = dict(hours=0, steps=0, ops=0, late=0, fbad=0, idle=0, walkonly=0, value=0.0)
    per = []
    for R in routes:
        x, y = R['start']
        t = int(R['t0'])
        f = int(R.get('fpick', 0))
        first_feed = next((k for k, s_ in enumerate(R['stops']) if 'FEED' in s_[2]), None)
        first_pick = next((k for k, s_ in enumerate(R['stops']) if 'PICKUP' in s_[2]), None)
        wheat = False
        if (first_feed is not None and (first_pick is None or first_pick > first_feed)) or f:
            t += 1                              # the shed pickup (wheat / fertilizer) at the start tile
            wheat = True
        carry = 0
        steps = ops = late = fbad = 0
        visited = set()
        for sx, sy, sops in R['stops']:
            d = abs(sx - x) + abs(sy - y)
            steps += d
            t += d
            x, y = sx, sy
            visited.add(sy * 10 + sx)
            for op in sops:
                if op in ('PICKUP', 'DROP'):
                    if (sx, sy) not in ACCESS:
                        tot['badlog'] = tot.get('badlog', 0) + 1
                    if op == 'PICKUP':
                        wheat = True
                    else:
                        if carry:
                            deliv.append((t, carry, R['u']))
                        carry = 0
                    t += 1
                    continue
                if op == 'FEED' and not wheat:
                    tot['wbad'] = tot.get('wbad', 0) + 1
                if op == 'HARVEST' and (sy * 10 + sx) in sty:
                    carry += sty[sy * 10 + sx]
                if op == 'COLLECT_FERTILIZER':
                    f += 1
                elif op == 'FERTILIZE':
                    if f <= 0:
                        fbad += 1
                    else:
                        f -= 1
                t += 1
                ops += 1
                if t - 1 > 23:
                    late += 1
                done[(sy * 10 + sx, op)] += 1
        end = t
        per.append((R['u'], R['t0'], end, steps, ops, late, fbad))
        tot['steps'] += steps
        tot['ops'] += ops
        tot['late'] += late
        tot['fbad'] += fbad
        tot['idle'] += max(0, 24 - end)
    miss_m = [k for k, m in need.items() if m and done[k] == 0]
    extra = [k for k in done if k not in need]
    dup = [k for k, n in done.items() if n > 1]
    got_opt = [k for k, m in need.items() if not m and done[k] > 0]
    tot['value'] = sum(val[k] for k in got_opt)
    by_op = Counter(k[1] for k in got_opt)
    left_opt = Counter(k[1] for k, m in need.items() if not m and done[k] == 0)
    left_val = sum(val[k] for k, m in need.items() if not m and done[k] == 0)
    print(f'== {label}: {len(routes)} routes | ops {tot["ops"]} steps {tot["steps"]} idle h (to 24) {tot["idle"]} | late ops '
          f'{tot["late"]} | fertilize without fertilizer {tot["fbad"]} | mandatory missing {len(miss_m)} | extra ops {len(extra)} dup {len(dup)}')
    print(f'   optional done {len(got_opt)} worth {tot["value"]:.0f}: {dict(by_op)}')
    print(f'   optional left {sum(left_opt.values())} worth {left_val:.0f}: {dict(left_opt)}')
    if deliv or tot.get('wbad') or tot.get('badlog'):
        print(f'   strawberries delivered mid-day (hour, units, unit): {sorted(deliv)} total {sum(d[1] for d in deliv)}'
              f' | FEED without wheat {tot.get("wbad", 0)} | pickup/drop off the access tiles {tot.get("badlog", 0)}')
    if miss_m:
        print('   MISSING mandatory:', [(k[0] % 10, k[0] // 10, k[1]) for k in miss_m][:20])
    for u, t0, end, steps, ops, late, fbad in per:
        print(f'   u{u:<2d} start h{t0} end {end:2d} steps {steps:2d} ops {ops:2d}' + (f' LATE {late}' if late else '') + (f' FBAD {fbad}' if fbad else ''))
    return tot


def planner_routes(arm, ep, day, keep_log=False):
    T = json.load(open(ROOT / f'results/fresh/sector_20260925/multi/{arm}/{ep}.json'))['tier_days'][str(day)]
    spawn = T.get('spawn') or []
    out = []
    for u in T['units']:
        p0 = u.get('p0')
        stops = [[t % 10, t // 10, [('DROP' if o == 'DELIVER' else o) for o in ops if not (keep_log is False and o in ('DROP', 'DELIVER', 'PLACE_HARVEST'))]]
                 for t, ops in u['stops']]
        stops = [s for s in stops if s[2]]
        start = [4, 4] if u['u'] == 0 else (spawn[u['u'] - 1] if u['u'] - 1 < len(spawn) else [4, 4])
        out.append({'u': u['u'], 'start': start, 't0': u['t0'], 'stops': stops})
    return out


def main():
    cat = json.load(open(sys.argv[1]))
    if sys.argv[2] == '--planner':
        score(cat, planner_routes(sys.argv[3], sys.argv[4], sys.argv[5]), f'planner {sys.argv[3]}')
    else:
        score(cat, json.load(open(sys.argv[2]))['routes'], Path(sys.argv[2]).stem)


if __name__ == '__main__':
    main()
