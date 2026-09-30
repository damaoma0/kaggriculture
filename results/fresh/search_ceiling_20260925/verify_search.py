"""Skeptic check 3: the search ceiling with an independent search (own ILS in verify_common.Search), and check 4:
the tracer's dropped jobs inserted into (i) our routes as scored by the model, (ii) the own search solution,
(iii) after each unit's ACTUAL last command in real timing (own append-only implementation).

Model variants:
  report : the report's model (merge revisits, first-stay purchase release, time-order constraint, one wheat pickup
           whenever a route has a FEED)
  robust : no merging of revisits + strict purchase release (the purchase op may not happen before its actual hour)
           + wheat flow (a HARVEST of wheat gives 3 wheat; wheat pickup only on a deficit) -> removes the leader's
           frozen units caused by harvest-then-feed routes the report's model cannot represent
Every solution is re-checked by verify_common.check_solution (same jobs, cap 24, releases, order pairs).
usage: verify_search.py [budget=1.0] [games_per_side=4] [every_nth_day=1] [variants=report,robust]
"""
import json
import random
import sys
import time
from collections import Counter, defaultdict

import verify_common as V

OURS_PICK = [110937191, 111554912, 111688786, 111941962]
LEAD_PICK = [('16732748', 112655730), ('16770421', 112714050), ('16730612', 112444381), ('16732748', 112667461)]
BUCKETS = ((0, 2), (3, 11), (12, 17), (18, 23), (24, 29))


def report_rows():
    out = {}
    for line in open(V.HERE / 'rows_both.jsonl', encoding='utf-8'):
        r = json.loads(line)
        out[(r['side'], r['ep'], r['day'])] = r
    return out


def tracer_for(ep, days, tracers, used):
    keys = ('WATER', 'FEED', 'CARE', 'HARVEST', 'FERTILIZE')
    best = None
    for name, rr in tracers.items():
        if name in used:
            continue
        ok = 0
        for r in rr:
            c = Counter(op for u, seq in days[r['day']].items() for h, p, op, cmd in seq if op in keys)
            ok += all(r['work'].get('op_' + k, 0) == c.get(k, 0) for k in keys)
        if best is None or ok > best[0]:
            best = (ok, name)
    used.add(best[1])
    return {r['day']: r for r in tracers[best[1]]}


def insert_by_value(S, R, extra, frozen):
    """highest value first, cheapest feasible insertion over all non-frozen routes, intra re-opt; two passes."""
    R = {u: list(r) for u, r in R.items()}
    C = {u: (V.cost(S.units[u], R[u])) for u in R}
    left = sorted(extra, key=lambda j: -j.val)
    placed = []
    for _ in range(2):
        rest = []
        for j in left:
            best = None
            for u in R:
                if u in frozen:
                    continue
                for k in range(len(R[u]) + 1):
                    c = S.c_of(u, R[u][:k] + [j] + R[u][k:])
                    if c is not None and (best is None or c - C[u] < best[0]):
                        best = (c - C[u], u, k)
            if best is None:
                rest.append(j)
                continue
            _, u, k = best
            R[u], C[u] = S.intra(u, R[u][:k] + [j] + R[u][k:])
            placed.append(j)
        left = rest
    return placed, R


def append_only(day_units, extra):
    """units continue after their actual last non-PASS command (actual hour + tile); a route of added jobs that needs
    wheat / fertilizer walks to the nearest shed tile first (+1 step per item type); cap 24."""
    st = {}
    for u, seq in day_units.items():
        w = [k for k, (h, p, op, c) in enumerate(seq) if op != 'PASS']
        if not w:
            st[u] = (seq[0][0], seq[0][1])
            continue
        h, p, op, c = seq[w[-1]]
        if op in V.MV:
            p = (min(9, max(0, p[0] + V.MV[op][0])), min(9, max(0, p[1] + V.MV[op][1])))
        st[u] = (h + 1, p)

    def fin(u, r):
        t, pos = st[u]
        if not r:
            return t
        need_w = any(j.wheat for j in r)
        bal = need = 0
        for j in r:
            bal -= j.fert
            need = max(need, -bal)
        pk = need_w + (need > 0)
        if pk:
            q = V.near_shed(pos)
            t += V.dist(pos, q) + pk
            pos = q
        for j in r:
            t = max(t + V.dist(pos, j.tile), j.release) + j.n
            pos = j.tile
        return t
    R = {u: [] for u in st}
    placed = []
    for j in sorted(extra, key=lambda x: -x.val):
        best = None
        for u, r in R.items():
            base = fin(u, r)
            for k in range(len(r) + 1):
                f = fin(u, r[:k] + [j] + r[k:])
                if f <= 24 and (best is None or f - base < best[0]):
                    best = (f - base, u, k)
        if best:
            _, u, k = best
            R[u] = R[u][:k] + [j] + R[u][k:]
            placed.append(j)
    slack = sum(max(0, 24 - st[u][0]) for u in st)
    return placed, slack


def main():
    budget = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
    ng = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    every = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    only = sys.argv[4].split(',') if len(sys.argv) > 4 else ['report', 'robust']
    rep = report_rows()
    tracers = V.load_tracer_files()
    used = set()
    games = [('ours', V.load_ours(ep)) for ep in OURS_PICK[:ng]] + [('leader', V.load_leader(t, ep)) for t, ep in LEAD_PICK[:ng]]
    rows = []
    t_all = time.perf_counter()
    for side, g in games:
        days, _ = V.rebuild(g['actions'])
        hc = V.harvest_crops(days)
        tr = tracer_for(g['ep'], days, tracers, used) if side == 'ours' else {}
        for d in range(0, 30, every):
            if not days[d]:
                continue
            row = dict(side=side, ep=g['ep'], day=d)
            rr = rep.get((side, g['ep'], d))
            if rr:
                row['rep_model'] = rr['model']['busy']
                row['rep_s1'] = rr['a']['1.0']['model']['busy']
                row['rep_c'] = rr.get('c')
            for vname, var in [x for x in (('report', {}), ('robust', dict(merge=False, strict=True, wheat=True))) if x[0] in only]:
                V.WHEAT_FLOW[0] = bool(var.get('wheat'))
                units, routes, busy, info = V.instance(days[d], merge=var.get('merge', True), strict_rel=var.get('strict', False),
                                                        hcrop=hc[d] if var.get('wheat') else None)
                frozen = {u for u in units if routes[u] and V.finish(units[u], routes[u]) > 24}
                model = sum(V.cost(units[u], routes[u]) for u in units)
                travel0 = sum(V.breakdown(units[u], routes[u])[1] for u in units)
                S = V.Search(units, routes, frozen, rng=random.Random(20260925 + d))
                t0 = time.perf_counter()
                R, tot, trace, it = S.run(budget)
                secs = time.perf_counter() - t0
                pairs, bad = V.check_solution(units, routes, R, frozen=frozen)
                travel1 = sum(V.breakdown(units[u], R[u])[1] for u in units)
                t95 = next((t for t, c in trace if model - c >= 0.95 * (model - tot)), 0.0) if model > tot else 0.0
                row[vname] = dict(model=model, search=tot, frozen=len(frozen), actual=sum(busy.values()), travel0=travel0,
                                  travel1=travel1, pairs=pairs, bad=dict(bad), secs=secs, t95=t95, iters=it,
                                  cmds=sum(j.n for r in routes.values() for j in r))
                # dropped jobs (ours, report model only)
                if side == 'ours' and vname == 'report' and d in tr:
                    executed = defaultdict(set)
                    for u, seq in days[d].items():
                        for h, p, op, c in seq:
                            executed[(p[1] * 10 + p[0], op)].add(h)
                    extra, dup_exec = [], 0
                    for jd in tr[d]['dropped']:
                        idx = jd['idx']
                        if (idx, jd['cmd']) in executed:
                            dup_exec += 1
                        rel = jd['first_open'] if jd.get('first_open') is not None else 0
                        extra.append(V.J((idx % 10, idx // 10), [jd['cmd']], h=99, u=-1, release=rel, val=jd['value'],
                                         tag=(jd.get('units') or 0)))
                    Sa = V.Search(units, routes, frozen)
                    fit_act, _ = insert_by_value(Sa, routes, extra, frozen)
                    fit_srch, R2 = insert_by_value(Sa, R, extra, frozen)
                    _, bad2 = V.check_solution(units, {u: r for u, r in R2.items()}, R2, frozen=frozen)
                    fit_app, slack = append_only(days[d], extra)
                    row['c'] = dict(n=len(extra), value=sum(j.val for j in extra), dup_executed=dup_exec,
                                    fit_actual=(len(fit_act), sum(j.val for j in fit_act)),
                                    fit_search=(len(fit_srch), sum(j.val for j in fit_srch)),
                                    fit_append=(len(fit_app), sum(j.val for j in fit_app)), slack=slack,
                                    bad_after_insert=dict(bad2),
                                    by_cmd={c: [sum(1 for j in extra if j.ops[0] == c), sum(1 for j in fit_srch if j.ops[0] == c)]
                                            for c in ('WATER', 'FERTILIZE', 'COLLECT_FERTILIZER', 'CARE', 'FEED', 'HARVEST')})
            V.WHEAT_FLOW[0] = False
            rows.append(row)
        print(f"{side} {g['ep']} done {time.perf_counter() - t_all:.0f}s", flush=True)
    tag = f'b{budget:g}' + (f'_e{every}' if every > 1 else '')
    (V.HERE / f'verify_search_rows_{tag}.jsonl').write_text('\n'.join(json.dumps(r) for r in rows) + '\n', encoding='utf-8')
    L = [f'VERIFY 3/4: own ILS search, budget {budget:g} s/day, {ng} games per side (every {every}. day)']
    rep_long = {}
    if every > 1 and (V.HERE / 'rows_both_long5_e5.jsonl').exists():
        for line in open(V.HERE / 'rows_both_long5_e5.jsonl', encoding='utf-8'):
            r = json.loads(line)
            rep_long[(r['side'], r['ep'], r['day'])] = r
    for side in ('ours', 'leader'):
        X = [r for r in rows if r['side'] == side]
        ngm = len({r['ep'] for r in X})
        rm, rs = sum(r.get('rep_model', 0) for r in X), sum(r.get('rep_s1', 0) for r in X)
        L.append(f"  {side}: report rows for the same days: model {rm / ngm:.0f} -> 1 s {rs / ngm:.0f} ({100 * (rs / rm - 1):+.1f}%)")
        RL = [rep_long.get((side, r['ep'], r['day'])) for r in X]
        if RL and all(RL):
            lm, l5 = sum(x['model']['busy'] for x in RL), sum(x['a']['5.0']['model']['busy'] for x in RL)
            L.append(f"  {side}: report long run, same days: model {lm / ngm:.0f} -> 5 s {l5 / ngm:.0f} ({100 * (l5 / lm - 1):+.1f}%)")
        for vname in [v for v in ('report', 'robust') if v in only]:
            m = sum(r[vname]['model'] for r in X)
            s = sum(r[vname]['search'] for r in X)
            a = sum(r[vname]['actual'] for r in X)
            t0 = sum(r[vname]['travel0'] for r in X)
            t1 = sum(r[vname]['travel1'] for r in X)
            fz = sum(r[vname]['frozen'] for r in X)
            bad = Counter()
            for r in X:
                bad.update(r[vname]['bad'])
            pairs = sum(r[vname]['pairs'] for r in X)
            secs = [r[vname]['secs'] for r in X]
            t95 = [r[vname]['t95'] for r in X]
            L.append(f"  {side} [{vname}]: actual {a / ngm:.0f}, model {m / ngm:.0f} ({100 * (m / a - 1):+.1f}% vs actual), own search {s / ngm:.0f} "
                     f"(model->search {100 * (s / m - 1):+.1f}%, actual->search {100 * (s / a - 1):+.1f}%); travel {t0 / ngm:.0f} -> {t1 / ngm:.0f} "
                     f"({100 * (t1 / max(1, t0) - 1):+.1f}%); frozen unit-days {fz}; solution check: {pairs} order pairs, violations {dict(bad) or 0}; "
                     f"secs mean {sum(secs) / len(secs):.2f}, t95 mean {sum(t95) / len(t95):.2f}")
            per = []
            for ep in sorted({r['ep'] for r in X}):
                Y = [r for r in X if r['ep'] == ep]
                mm, ss = sum(r[vname]['model'] for r in Y), sum(r[vname]['search'] for r in Y)
                rr_m, rr_s = sum(r.get('rep_model', 0) for r in Y), sum(r.get('rep_s1', 0) for r in Y)
                per.append(f"{ep}: {mm}->{ss} ({100 * (ss / mm - 1):+.1f}%)" + (f" [report {rr_m}->{rr_s} ({100 * (rr_s / rr_m - 1):+.1f}%)]" if vname == 'report' else ''))
            L.append('     per game: ' + ', '.join(per))
            bk = []
            for lo, hi in BUCKETS:
                Y = [r for r in X if lo <= r['day'] <= hi]
                mm, ss, aa = sum(r[vname]['model'] for r in Y), sum(r[vname]['search'] for r in Y), sum(r[vname]['actual'] for r in Y)
                bk.append(f"d{lo}-{hi}: actual {aa / ngm / (hi - lo + 1):.0f} model {mm / ngm / (hi - lo + 1):.0f} search {ss / ngm / (hi - lo + 1):.0f} ({100 * (ss / mm - 1):+.1f}%)")
            L.append('     per day by range: ' + '; '.join(bk))
    X = [r for r in rows if r['side'] == 'ours' and 'c' in r]
    if X:
        ngm = len({r['ep'] for r in X})
        def s(k, i=None):
            return sum((r['c'][k][i] if i is not None else r['c'][k]) for r in X) / ngm
        rc = [r['rep_c'] for r in X if r.get('rep_c')]
        L.append(f"  ours dropped jobs (tracer, {len(X)} days): {s('n'):.1f} jobs / {s('value'):,.0f} a game; already executed that day (same tile+cmd) {s('dup_executed'):.1f}; "
                 f"fit into our routes in the model {s('fit_actual', 0):.1f} / {s('fit_actual', 1):,.0f}; after own search {s('fit_search', 0):.1f} / {s('fit_search', 1):,.0f}; "
                 f"append-only real timing {s('fit_append', 0):.1f} / {s('fit_append', 1):,.0f}; after-last-command unit-steps {s('slack'):.0f}")
        if rc:
            L.append(f"     report rows, same days: dropped {sum(c['all'].get('n', 0) for c in rc) / ngm:.1f}, fit_actual {sum(c['fit_actual'].get('n', 0) for c in rc) / ngm:.1f} / {sum(c['fit_actual'].get('value', 0) for c in rc) / ngm:,.0f}, "
                     f"fit_search {sum(c['fit_search'].get('n', 0) for c in rc) / ngm:.1f} / {sum(c['fit_search'].get('value', 0) for c in rc) / ngm:,.0f}")
        bc = Counter()
        for r in X:
            for c, (a, b) in r['c']['by_cmd'].items():
                bc[c + '_n'] += a
                bc[c + '_fit'] += b
        L.append('     by command dropped -> fit after own search: ' + ', '.join(f"{c} {bc[c + '_n'] / ngm:.1f}->{bc[c + '_fit'] / ngm:.1f}" for c in ('WATER', 'FERTILIZE', 'COLLECT_FERTILIZER', 'CARE', 'FEED', 'HARVEST')))
        badc = Counter()
        for r in X:
            badc.update(r['c']['bad_after_insert'])
        L.append(f"     solution check after insertion: {dict(badc) or 'no violations'}")
    txt = '\n'.join(L) + '\n'
    (V.HERE / f'verify_search_{tag}.txt').write_text(txt, encoding='utf-8')
    print(txt)


if __name__ == '__main__':
    main()


