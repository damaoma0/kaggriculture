"""Lower bound for (c): the tracer's dropped jobs that the SAME crew could still do AFTER each unit's actual last command
(no re-routing of anything it did, actual timing, not the model's). Each unit starts at its actual end hour and end
tile (units with no command at all: first hour, spawn tile); a route of added jobs that needs wheat / fertilizer first
walks to the nearest shed tile and picks up (whatever the unit still carries is ignored: conservative). Jobs inserted by
value (highest first), cheapest feasible position, 2-opt / or-opt after each insert, all done before midnight (24).
Order-safe as in search_ceiling (release = hour the job first appeared in the executor's task list).
usage: append_check.py   (ours only; writes append_check.json and prints a table)
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import search_ceiling as S  # noqa: E402
LS = S.LS
BUCKETS = ((0, 2), (3, 11), (12, 17), (18, 23), (24, 29))


def finish_app(start, route):
    t, pos = start
    if not route:
        return t
    need = bal = 0
    for j in route:
        bal -= j.fert
        need = max(need, -bal)
    pk = (any(j.wheat for j in route)) + (need > 0)
    if pk:
        q = LS.home(pos)
        t += LS.d(pos, q) + pk
        pos = q
    for j in route:
        t = max(t + LS.d(pos, j.tile), j.release)
        if t > j.due:
            return 99
        t += j.n
        pos = j.tile
    return t


def improve_app(start, route):
    best, bc = route, finish_app(start, route)
    better = True
    while better and len(best) > 2:
        better = False
        n = len(best)
        for i in range(n - 1):
            for k in range(i + 1, n):
                r = best[:i] + best[i:k + 1][::-1] + best[k + 1:]
                c = finish_app(start, r)
                if c < bc:
                    best, bc, better = r, c, True
    return best


def ends(sim, day):
    """unit -> (actual end hour, tile after its last non-PASS command)."""
    seq = defaultdict(list)
    for t in range(day * 24, min(719, day * 24 + 24)):
        for u, (x, y, c) in enumerate(sim.get(t, [])):
            seq[u].append((t % 24, (x, y), c[0] if c else 'PASS'))
    out = {}
    for u, v in seq.items():
        work = [k for k, (_, _, op) in enumerate(v) if op != 'PASS']
        if not work:
            out[u] = (v[0][0], v[0][1])
            continue
        h, p, op = v[work[-1]]
        if op in S.MOVES:
            dx, dy = S.MOVES[op]
            p = (min(9, max(0, p[0] + dx)), min(9, max(0, p[1] + dy)))
        out[u] = (h + 1, p)
    return out


def main():
    games = S.load_ours()
    rows = []
    for g in games:
        for day, tr in sorted(g['tracer'].items()):
            st = ends(g['sim'], day)
            R = {u: [] for u in st}
            vals, meta, extra = {}, {}, []
            for jd in tr['dropped']:
                idx = jd['idx']
                j = S.DJob((idx % 10, idx // 10), [jd['cmd']], release=jd['first_open'] if jd.get('first_open') is not None else 0)
                vals[id(j)], meta[id(j)] = jd['value'], jd
                extra.append(j)
            placed = []
            for j in sorted(extra, key=lambda x: -vals[id(x)]):
                best = None
                for u, r in R.items():
                    base = finish_app(st[u], r)
                    for k in range(len(r) + 1):
                        f = finish_app(st[u], r[:k] + [j] + r[k:])
                        if f <= 24 and (best is None or f - base < best[0]):
                            best = (f - base, u, k)
                if best:
                    _, u, k = best
                    R[u] = improve_app(st[u], R[u][:k] + [j] + R[u][k:])
                    placed.append(j)
            c = Counter()
            for j in placed:
                m = meta[id(j)]
                c['n'] += 1
                c['value'] += m['value']
                c['units'] += m.get('units') or 0
                c['n_' + m['cmd']] += 1
                c['v_' + m['cmd']] += m['value']
            slack = sum(max(0, 24 - st[u][0]) for u in st)
            rows.append(dict(ep=g['ep'], day=day, dropped=len(extra), dropped_value=sum(vals.values()), fit=dict(c),
                             slack_steps=slack))
    (HERE / 'append_check.json').write_text(json.dumps(rows), encoding='utf-8')
    n = len(games)
    L = []
    L.append(f"APPEND-ONLY lower bound (ours, {n} games, {len(rows)} tracer days): dropped jobs the same crew fits AFTER its actual last commands")
    L.append(f"  dropped {sum(r['dropped'] for r in rows) / n:.1f} jobs / {sum(r['dropped_value'] for r in rows) / n:,.0f} coins a game; "
             f"fit by appending {sum(r['fit'].get('n', 0) for r in rows) / n:.1f} / {sum(r['fit'].get('value', 0) for r in rows) / n:,.0f}; "
             f"unit-steps after the last command (incl. idle hands) {sum(r['slack_steps'] for r in rows) / n:.0f} a game")
    for cmd in ('WATER', 'FERTILIZE', 'COLLECT_FERTILIZER', 'CARE', 'FEED', 'HARVEST'):
        L.append(f"    {cmd:<19} {sum(r['fit'].get('n_' + cmd, 0) for r in rows) / n:.1f} / {sum(r['fit'].get('v_' + cmd, 0) for r in rows) / n:,.0f}")
    for lo, hi in BUCKETS:
        X = [r for r in rows if lo <= r['day'] <= hi]
        if X:
            L.append(f"    days {lo}-{hi}: dropped {sum(r['dropped'] for r in X) / n:.1f} ({sum(r['dropped_value'] for r in X) / n:,.0f}) -> "
                     f"fit by appending {sum(r['fit'].get('n', 0) for r in X) / n:.1f} ({sum(r['fit'].get('value', 0) for r in X) / n:,.0f}); "
                     f"after-last-command unit-steps {sum(r['slack_steps'] for r in X) / n / (hi - lo + 1):.0f} a day")
    (HERE / 'append_check.txt').write_text('\n'.join(L) + '\n', encoding='utf-8')
    print('\n'.join(L))


if __name__ == '__main__':
    main()
