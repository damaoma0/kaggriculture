"""Skeptic check 8: the report's append-only bound (5.6 dropped jobs a game fit after each unit's ACTUAL last command)
starts every unit after its last non-PASS command, which includes the executor's trailing walks toward jobs it never
executes (verify_overhead: ~15 moves a day on days 12-23). Same bound, own code, two starting points:
  (a) after the last non-PASS command (the report's), (b) after the last WORK command (trailing walk dropped:
      'no re-routing, no chasing'). Real timing, a shed detour first when wheat / fertilizer is needed; cap 24.
usage: verify_append2.py
"""
from collections import Counter

import verify_common as V


def starts(day_units, mode):
    st = {}
    for u, seq in day_units.items():
        if mode == 'last_cmd':
            w = [k for k, (h, p, op, c) in enumerate(seq) if op != 'PASS']
        else:
            w = [k for k, (h, p, op, c) in enumerate(seq) if V.is_work(p, op) or op in ('PICKUP', 'DROP')]
        if not w:
            st[u] = (seq[0][0], seq[0][1])
            continue
        h, p, op, c = seq[w[-1]]
        if op in V.MV:
            p = (min(9, max(0, p[0] + V.MV[op][0])), min(9, max(0, p[1] + V.MV[op][1])))
        st[u] = (h + 1, p)
    return st


def fit(st, extra):
    def fin(u, r):
        t, pos = st[u]
        if not r:
            return t
        bal = need = 0
        for j in r:
            bal -= j.fert
            need = max(need, -bal)
        pk = any(j.wheat for j in r) + (need > 0)
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
    return placed, sum(max(0, 24 - st[u][0]) for u in st)


def main():
    tracers = V.load_tracer_files()
    keys = ('WATER', 'FEED', 'CARE', 'HARVEST', 'FERTILIZE')
    used = set()
    c = Counter()
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
            extra = [V.J((j['idx'] % 10, j['idx'] // 10), [j['cmd']], u=-1, h=99,
                         release=j['first_open'] if j.get('first_open') is not None else 0, val=j['value'])
                     for j in r['dropped']]
            c['n'] += len(extra)
            c['v'] += sum(j.val for j in extra)
            for mode in ('last_cmd', 'last_work'):
                pl, slack = fit(starts(days[d], mode), extra)
                c[mode + '_n'] += len(pl)
                c[mode + '_v'] += sum(j.val for j in pl)
                c[mode + '_slack'] += slack
                if 12 <= d <= 23:
                    c[mode + '_slack_busy'] += slack
                    c[mode + '_n_busy'] += len(pl)
            if 12 <= d <= 23:
                c['n_busy'] += len(extra)
    n = 12
    L = ['VERIFY 8: append-only lower bound, own code (ours, 12 games, per game)']
    L.append(f"  dropped {c['n'] / n:.1f} / {c['v'] / n:,.0f}")
    for mode, lab in (('last_cmd', "after the last non-PASS command (report)"), ('last_work', 'after the last work / shed command (trailing walk not done)')):
        L.append(f"  {lab}: fit {c[mode + '_n'] / n:.1f} / {c[mode + '_v'] / n:,.0f}; unit-steps after the start point {c[mode + '_slack'] / n:.0f} a game; "
                 f"days 12-23: slack {c[mode + '_slack_busy'] / n / 12:.1f} a day, fit {c[mode + '_n_busy'] / n:.1f} of {c['n_busy'] / n:.1f}")
    txt = '\n'.join(L) + '\n'
    (V.HERE / 'verify_append2.txt').write_text(txt, encoding='utf-8')
    print(txt)


if __name__ == '__main__':
    main()
