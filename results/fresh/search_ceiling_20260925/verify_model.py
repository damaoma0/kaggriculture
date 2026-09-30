"""Skeptic check 2: does the time model fit the actual routes, and how much do the job-extraction choices matter?

Own code (verify_common). For all 12 games per side, per unit-day:
  model of the actual arrangement (report variant: merge revisits, release = first stay's hour, time-order constraint)
  vs actual busy steps; frozen unit-days (model finish > 24) under time order and under labour_search's unit order.
Report numbers to reproduce: ours model 6419 / actual 7138 (-10.1%), within +-2: 65.2%, model < actual-2: 34.6%,
frozen 31 (0.8%) time order / 576 (13.9%) unit order; leader 6696 / 7298 (-8.2%), 77.8%, 21.7%, 176 (4.5%) / 929 (24.0%).
Per-game model values from report.txt (2a per game) are compared one by one.
Variants (sensitivity of the job set): strict purchase release (hour of the stay holding the PLANT/PLACE/BUILD),
no merging of same-unit revisits.
Diagnostics: where the model is short of the actual (per unit-day decomposition), same-unit revisits, merged jobs
whose purchase op happened at a later stay, frozen leader units in detail.
usage: verify_model.py
"""
import json
import re
from collections import Counter, defaultdict

import verify_common as V


def per_game_report():
    txt = (V.HERE / 'report.txt').read_text(encoding='utf-8')
    out = {}
    for m in re.finditer(r'(\d{9}): (\d+)->(\d+) \(', txt):
        out[int(m.group(1))] = (int(m.group(2)), int(m.group(3)))
    return out


def analyse(g, variant):
    days, _ = V.rebuild(g['actions'])
    hc = V.harvest_crops(days) if variant.get('wheat') else None
    V.WHEAT_FLOW[0] = bool(variant.get('wheat'))
    agg = Counter()
    frozen_list = []
    ud_rows = []
    for d in range(30):
        if not days[d]:
            continue
        units, routes, busy, info = V.instance(days[d], merge=variant.get('merge', True),
                                                strict_rel=variant.get('strict', False), order='time',
                                                hcrop=hc[d] if hc else None)
        for u in units:
            r = routes[u]
            f, tr, cm, pk, dr, wt = V.breakdown(units[u], r)
            fin = V.finish(units[u], r)
            mdl = (fin - units[u][0]) if r else 0
            if r and fin > 24:
                agg['frozen'] += 1
                frozen_list.append((d, u, units[u][0], len(r), fin, busy[u]))
            agg['model'] += mdl
            agg['actual'] += busy[u]
            agg['unit_days'] += 1
            agg['travel'] += tr
            agg['cmds'] += cm
            agg['pk'] += pk
            agg['drops'] += dr
            agg['wait'] += wt
            diff = mdl - busy[u]
            agg['within2'] += abs(diff) <= 2
            agg['model_short'] += diff < -2
            agg['model_long'] += diff > 2
            ud_rows.append((d, u, mdl, busy[u]))
        if variant.get('unit_order'):
            u2, r2, b2, _ = V.instance(days[d], merge=True, strict_rel=False, order='unit')
            for u in u2:
                if r2[u] and V.finish(u2[u], r2[u]) > 24:
                    agg['frozen_unit_order'] += 1
                agg['model_unit_order'] += V.cost(u2[u], r2[u])
        agg['order_pairs_L'] += info['order_pairs_L']
    return agg, frozen_list, ud_rows


def diagnostics(g):
    """per game: revisits, late purchase ops inside merged jobs, today-drop artefacts, actual decomposition."""
    days, _ = V.rebuild(g['actions'])
    c = Counter()
    for d in range(30):
        for u, seq in days[d].items():
            js_m = V.jobs(seq, u, merge=True)
            js_s = V.jobs(seq, u, merge=False)
            c['jobs_merged'] += len(js_m)
            c['stays'] += len(js_s)
            # purchase op at a later stay than the merged job's first hour
            stays, cur = [], None
            for h, p, op, cmd in seq:
                if V.is_work(p, op):
                    if cur is not None and cur[0] == p:
                        cur[2].append((h, op))
                    else:
                        cur = [p, h, [(h, op)]]
                        stays.append(cur)
                else:
                    cur = None
            first = {}
            for s in stays:
                first.setdefault(s[0], s[1])
            for s in stays:
                if s[1] != first[s[0]] and any(o in V.BOUGHT for _, o in s[2]):
                    c['bought_op_at_later_stay'] += 1
                    c['bought_later_by_hours'] += s[1] - first[s[0]]
            # shed trips: PICKUPs per unit-day beyond one per item type
            items = Counter(tuple(cmd[:2]) for h, p, op, cmd in seq if op == 'PICKUP')
            c['pickup_cmds'] += sum(items.values())
            c['pickup_item_types'] += len(items)
            # shed visits in the middle of a route (a PICKUP/DROP after the unit's first work op)
            w = [k for k, (h, p, op, cmd) in enumerate(seq) if V.is_work(p, op)]
            if w:
                c['mid_shed_cmds'] += sum(1 for h, p, op, cmd in seq[w[0]:w[-1]] if op in ('PICKUP', 'DROP') or (op == 'PLACE' and p in V.SHEDSET))
    return c


def main():
    rep = per_game_report()
    variants = [('report (merge, first-stay release, time order)', dict(unit_order=True)),
                ('strict purchase release', dict(strict=True)),
                ('no merge of revisits', dict(merge=False)),
                ('no merge + strict release', dict(merge=False, strict=True)),
                ('wheat flow (HARVEST wheat gives 3; pickup only on a deficit)', dict(wheat=True)),
                ('wheat flow + strict release', dict(wheat=True, strict=True))]
    res = {}
    L = ['VERIFY 2: model fit of the actual routes (own code, 12 games per side)']
    games = [('ours', V.load_ours(ep)) for ep in V.OURS] + [('leader', V.load_leader(t, ep)) for t, ep in V.LEADER]
    for vname, var in variants:
        for side in ('ours', 'leader'):
            A = Counter()
            per = []
            fz = []
            for s, g in games:
                if s != side:
                    continue
                a, fl, _ = analyse(g, var)
                A.update(a)
                per.append((g['ep'], a['model'], rep.get(g['ep'], (None,))[0]))
                fz += [(g['ep'],) + x for x in fl]
            res[(vname, side)] = (A, per, fz)
            n = A['unit_days']
            L.append(f"  [{vname}] {side}: model {A['model'] / 12:.0f} / actual {A['actual'] / 12:.0f} "
                     f"({100 * (A['model'] / A['actual'] - 1):+.1f}%), within+-2 {100 * A['within2'] / n:.1f}%, "
                     f"model<actual-2 {100 * A['model_short'] / n:.1f}%, model>actual+2 {100 * A['model_long'] / n:.1f}%, "
                     f"frozen {A['frozen']} ({100 * A['frozen'] / n:.1f}%) of {n}"
                     + (f"; unit-order instance: frozen {A['frozen_unit_order']} ({100 * A['frozen_unit_order'] / n:.1f}%), model {A['model_unit_order'] / 12:.0f}" if var.get('unit_order') else '')
                     + f"; travel {A['travel'] / 12:.0f} pickups {A['pk'] / 12:.0f} drops {A['drops'] / 12:.0f} wait {A['wait'] / 12:.0f}")
            if vname.startswith('report'):
                mism = [(ep, m, r) for ep, m, r in per if r is not None and m != r]
                L.append(f"      per-game model vs report.txt: {sum(1 for ep, m, r in per if m == r)}/{len(per)} identical"
                         + (f", differ: {mism}" if mism else ''))
    L.append('  diagnostics per game (sum / 12):')
    for side in ('ours', 'leader'):
        C = Counter()
        for s, g in games:
            if s == side:
                C.update(diagnostics(g))
        L.append(f"    {side}: stays {C['stays'] / 12:.0f} -> merged jobs {C['jobs_merged'] / 12:.0f} (same-unit revisits merged {(C['stays'] - C['jobs_merged']) / 12:.0f}); "
                 f"purchase ops done at a LATER stay than the merged job's release hour {C['bought_op_at_later_stay'] / 12:.1f} "
                 f"(mean {C['bought_later_by_hours'] / max(1, C['bought_op_at_later_stay']):.1f} h later); "
                 f"PICKUP cmds {C['pickup_cmds'] / 12:.0f} vs distinct (item) per unit-day {C['pickup_item_types'] / 12:.0f}; "
                 f"shed cmds between first and last work op {C['mid_shed_cmds'] / 12:.0f}")
    # frozen leader units: where does the model exceed the actual?
    V.WHEAT_FLOW[0] = False
    A, per, fz = res[('report (merge, first-stay release, time order)', 'leader')]
    L.append(f"  leader frozen unit-days: {len(fz)}; first 3 decomposed:")
    lg = {g['ep']: g for s, g in games if s == 'leader'}
    for ep, d, u, st, nj, fin, busy in fz[:3]:
        days, _ = V.rebuild(lg[ep]['actions'])
        seq = days[d][u]
        units, routes, b, _ = V.instance(days[d])
        f, tr, cm, pk, dr, wt = V.breakdown(units[u], routes[u])
        acts = ' '.join(f"{h}:{op[:4]}@{p[0]}{p[1]}" for h, p, op, cmd in seq if op != 'PASS')
        L.append(f"    ep {ep} d{d} u{u}: model finish {fin} (travel {tr}, cmds {cm}, pickups {pk}, drops {dr}, wait {wt}), actual busy {busy}; "
                 f"jobs {[(j.tile, j.ops, j.today, j.release, j.due) for j in routes[u]]}")
        L.append(f"      actual: {acts}")
    (V.HERE / 'verify_model.txt').write_text('\n'.join(L) + '\n', encoding='utf-8')
    print('\n'.join(L))


if __name__ == '__main__':
    main()
