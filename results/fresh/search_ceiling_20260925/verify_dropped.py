"""Skeptic check 6: the tracer's dropped jobs themselves (ours, 12 games, stored data only).

  - deadlines / kinds / release hours as inserted (report: release = first_open, due none)
  - item availability for inserted FERTILIZE / FEED: per day, dropped FERTILIZE jobs vs fertilizer the day could
    have supplied (sold that day + in the shed at the mid-day snapshot + carried at the snapshot, from the trace's
    'days' records); the model assumes unlimited shed stock
  - dropped jobs on a tile some unit already visited that day (could ride along an existing stay)
  - value concentration (largest single-day totals) and the tracer's reasons (idle passes)
usage: verify_dropped.py
"""
from collections import Counter

import verify_common as V


def main():
    tracers = V.load_tracer_files()
    keys = ('WATER', 'FEED', 'CARE', 'HARVEST', 'FERTILIZE')
    used = set()
    c = Counter()
    big = []
    short_days = []
    for ep in V.OURS:
        g = V.load_ours(ep)
        days, _ = V.rebuild(g['actions'])
        best = None
        for name, rr in tracers.items():
            if name in used:
                continue
            ok = sum(1 for r in rr if all(r['work'].get('op_' + k, 0) == Counter(
                op for u, seq in days[r['day']].items() for h, p, op, cmd in seq if op == k).get(k, 0) for k in keys))
            if best is None or ok > best[0]:
                best = (ok, name)
        used.add(best[1])
        for r in tracers[best[1]]:
            d = r['day']
            dr = r['dropped']
            if not dr:
                continue
            visited = {p for u, seq in days[d].items() for h, p, op, cmd in seq if V.is_work(p, op)}
            rec = g['raw']['days'][d] if d < len(g['raw']['days']) else {}
            fert_avail = (rec.get('sold', {}).get('FERTILIZER', 0) + rec.get('shed_mid', {}).get('FERTILIZER', 0)
                          + rec.get('carried_mid', {}).get('FERTILIZER', 0))
            nf = sum(1 for j in dr if j['cmd'] == 'FERTILIZE')
            c['fert_dropped'] += nf
            c['fert_covered'] += min(nf, fert_avail)
            if nf > fert_avail:
                short_days.append((ep, d, nf, fert_avail))
            tot = 0
            for j in dr:
                c['n'] += 1
                c['v'] += j['value']
                tot += j['value']
                c['kind_' + str(j.get('kind'))] += 1
                if (j['idx'] % 10, j['idx'] // 10) in visited:
                    c['tile_visited_today'] += 1
                if not j['idle']:
                    c['no_idle_pass'] += 1
                if j.get('first_open') is None:
                    c['never_in_tasks'] += 1
                elif j['first_open'] > 0:
                    c['release_after_0'] += 1
                if j.get('deadline') != 23:
                    c['deadline_not_23'] += 1
            big.append((round(tot), ep, d, [(j['cmd'], j.get('kind'), j.get('asset'), j['value'], j.get('units')) for j in sorted(dr, key=lambda x: -x['value'])[:3]]))
    big.sort(reverse=True)
    n = 12
    L = ['VERIFY 6: tracer dropped jobs (ours, 12 games, per game)']
    L.append(f"  dropped {c['n'] / n:.1f} jobs / {c['v'] / n:,.0f}; deadline != 23: {c['deadline_not_23']}; never in the task list {c['never_in_tasks'] / n:.1f}; "
             f"first opened after hour 0 {c['release_after_0'] / n:.1f}; no idle pass while open {100 * c['no_idle_pass'] / c['n']:.0f}%")
    L.append(f"  kinds: " + ', '.join(f"{k[5:]} {v / n:.1f}" for k, v in sorted(c.items()) if k.startswith('kind_')))
    L.append(f"  on a tile some unit already worked that day: {c['tile_visited_today'] / n:.1f} of {c['n'] / n:.1f}")
    L.append(f"  FERTILIZE dropped {c['fert_dropped'] / n:.1f}; covered by fertilizer the day had (sold + shed_mid + carried_mid) {c['fert_covered'] / n:.1f}; "
             f"days with more dropped FERTILIZE than that: {len(short_days)} {short_days[:6]}")
    tv = c['v']
    L.append(f"  largest single-day dropped totals: " + '; '.join(f"{b[0]} ({100 * b[0] / tv:.1f}% of all) ep {b[1]} d{b[2]} top {b[3]}" for b in big[:3]))
    txt = '\n'.join(L) + '\n'
    (V.HERE / 'verify_dropped.txt').write_text(txt, encoding='utf-8')
    print(txt)


if __name__ == '__main__':
    main()
