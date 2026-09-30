"""Replay V9-lite parameter variants offline from logged full-V9 decisions (no new rollouts).

Input: v9lite_decisions.jsonl lines written by agents/mgt_v9lite.py with V9LITE_SHADOW=1 (V9's per-candidate,
per-world margin/cash deltas and protection failures at the same checkpoint). A lite variant whose rollouts are a
subset of V9's (shortlist prefix, keep <= 2, worlds <= 4 for V9-expanded candidates, <= 8 for V9 finalists) is
decided exactly; otherwise the decision is marked 'unknown'. Cost = simulated turns (full rollout 719-step,
cohort-rejected rollout until-step), the unit that V9's own simulated_turns counts.

usage: v9lite_offline.py <jsonl> [<jsonl> ...]
"""
import itertools
import json
import statistics
import sys


def native_route(rec):
    """The router's own route at this reveal: logged by lite, else the V9 row matching the native row's tape."""
    if rec.get('lite') and rec['lite'].get('native_route') is not None:
        return rec['lite']['native_route']
    c = rec['v9']['candidates']
    for x in c[1:]:
        if (x['episode'], x['hamming'], x['distance']) == (c[0]['episode'], c[0]['hamming'], c[0]['distance']):
            return x['route']
    return None


def variant(rec, count, skip_native, scout_min, keep, W, final_min, max_h=99, lazy=False):
    v9 = rec['v9']
    step = rec['step']
    until = v9['until']
    full, cut = 719 - step, until - step
    native = native_route(rec)
    cands = v9['candidates']
    alts = [c for c in cands[1:count] if not (skip_native and c['route'] == native) and c['hamming'] <= max_h]
    turns = 0

    def rejected_at(c):
        for f in c['failures']:
            if 'boundary_step' in f:
                return f['scenario']
        return None

    def fails_in(c, i):
        return any(f.get('scenario') == i for f in c['failures'])

    if not alts:
        return None, 0, 'ok'
    turns += full                                       # native world 0
    scout = []
    for c in alts:
        r = rejected_at(c)
        if r == 0:
            turns += cut
            continue
        if not c['deltas']:
            return 'unknown', turns, 'not scouted by V9'
        turns += full
        if fails_in(c, 0):
            continue
        scout.append((c['deltas'][0], c))
    scout.sort(key=lambda x: -x[0])
    expanded = [c for d, c in scout if d > scout_min][:keep]
    if not expanded or W == 1:
        pass
    else:
        turns += (W - 1) * full                          # native worlds 1..W-1
    admitted = []
    for c in expanded:
        if lazy and admitted:                           # lazy keep: the runner-up is expanded only if the top fails
            break
        n = len(c['deltas'])
        r = rejected_at(c)
        ok = True
        for i in range(1, W):
            if r == i:
                turns += cut
                ok = False
                break
            if i >= n:
                return 'unknown', turns, 'candidate world %d not run by V9' % i
            turns += full
        if not ok:
            continue
        if any(fails_in(c, i) for i in range(W)):
            continue
        d, cash = c['deltas'][:W], c['cash'][:W]
        mean = statistics.mean(d)
        risk = mean - .5 * statistics.pstdev(d)
        if risk > final_min and min(d) >= -max(500, .25 * max(0, mean)) and statistics.mean(cash) > 0:
            admitted.append((risk, c))
    if not admitted:
        return None, turns, 'ok'
    return max(admitted, key=lambda x: x[0])[1]['route'], turns, 'ok'


def main(paths):
    recs = [json.loads(l) for p in paths for l in open(p, encoding='utf-8') if l.strip()]
    recs = list({(r['tag'], r['step']): r for r in recs if 'v9' in r}.values())   # last line per checkpoint
    print(len(recs), 'checkpoints;', sum(r['v9']['selected'] is not None for r in recs), 'V9 switches')
    v9_turns = sum(r['v9']['simulated_turns'] for r in recs)
    for r in recs:
        c = r['v9']['candidates']
        sel = r['v9']['selected']
        row = next((x for x in c if x['route'] == sel), None) if sel is not None else None
        pos = [x['route'] for x in c].index(sel) if row else None
        print(f"{r['tag']} d{r['step']//24} v9={sel} pos={pos} v9 {r['v9_seconds']:.1f}s "
              f"turns {r['v9']['simulated_turns']} "
              f"native={native_route(r)} cands={[x['route'] for x in c]} "
              f"d0={[None if not x['deltas'] else round(x['deltas'][0]) for x in c]}"
              + (f" sel_deltas={[round(v) for v in row['deltas']]}" if row else ''))
    grid = itertools.product([5, 6, 7], [False, True], [350], [1, 2], [3, 4, 8], [350], [8, 12, 99])
    out = []
    for count, lazy, smin, keep, W, fmin, max_h in grid:
        skip = True
        agree = same_switch = missed = extra = unknown = 0
        turns = 0
        for r in recs:
            sel, t, why = variant(r, count, skip, smin, keep, W, fmin, max_h, lazy)
            turns += t
            if sel == 'unknown':
                unknown += 1
                continue
            v = r['v9']['selected']
            agree += sel == v
            same_switch += (sel == v and v is not None)
            missed += (v is not None and sel != v)
            extra += (sel is not None and sel != v)
        out.append((count, max_h, int(lazy), keep, W, fmin, agree, same_switch, missed, extra, unknown,
                    round(turns / max(1, v9_turns), 3)))
    print('count max_h lazy keep W final agree same_switch missed extra unknown cost_ratio')
    for o in sorted(out, key=lambda o: (o[10] > 0, -o[7], o[9], o[11])):
        print(*o)


if __name__ == '__main__':
    main(sys.argv[1:])
