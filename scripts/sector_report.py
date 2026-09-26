"""Reports for scripts/sector_run.py (stored results only).

  sector_report.py trace <arm,...>   day 11 from the leader's exact morning (42 worlds): cash and margin gap to the leader at
      the day-12 morning (paired t CI vs the first arm), coop + goose built / placed on day 11, and hand-level dispatch
      metrics (hands only, day 11): extra hand-visits (per tile off the shed, distinct hands that stood on it minus one),
      idle steps (PASS), moves and field ops per hand-day, share of a hand's field ops in its main quadrant, hands working
      one quadrant only, main quadrant = spawn quadrant, and spawn quadrants (first NE, second NW, third SW, fourth SE).
  sector_report.py full <base> <arm,...>   full games (52 worlds): margin / own cash vs base, gap to the leader.
"""
import json
import math
import random
import statistics as st
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
OUT = ROOT / 'results/fresh/sector_20260925'
SHED = {(4, 4), (5, 4), (4, 5), (5, 5)}
FIELD = {'WATER', 'FEED', 'CARE', 'HARVEST', 'FERTILIZE', 'COLLECT_FERTILIZER', 'PLANT', 'DIG', 'BUILD_COOP',
         'BUILD_PASTURE', 'PLACE'}
QN = {'NE': 'first', 'NW': 'second', 'SW': 'third', 'SE': 'fourth'}
MOVES = {'NORTH', 'SOUTH', 'EAST', 'WEST'}


def quad(p):
    return ('N' if p[1] < 5 else 'S') + ('W' if p[0] < 5 else 'E')


def ci(d):
    if len(d) < 2:
        return f'{st.mean(d):+,.0f}' if d else '-'
    m = st.mean(d)
    h = 2.02 * st.stdev(d) / math.sqrt(len(d))
    rng = random.Random(7)
    bs = sorted(st.mean(rng.choices(d, k=len(d))) for _ in range(4000))
    return f'{m:+,.0f} (t {m - h:+,.0f}..{m + h:+,.0f}; boot {bs[100]:+,.0f}..{bs[3899]:+,.0f}) {sum(x > 0 for x in d)}/{sum(x < 0 for x in d)}'


def cen(p):
    """steps from the tile to the nearest shed-access tile (central tiles: <= 2, the animals near the shed)."""
    return min(abs(p[0] - x) + abs(p[1] - y) for x, y in SHED)


def hand_metrics(r):
    D = 11
    lo, hi = D * 24, D * 24 + 24
    visits, ops_q, spawn = {}, {}, {}
    seg, trips, last = {}, Counter(), {}
    pvisits = {}
    lastpos, dirs = {}, {}
    m = Counter()
    goose = Counter()
    for t in range(lo, hi):
        for u, pos, cmd, eff, sb, sa, ib, ia in r['units'].get(str(t), []):
            c = cmd[0] if isinstance(cmd, list) and cmd else 'PASS'
            p = tuple(pos)
            if c == 'BUILD_COOP' and eff:
                goose['coop'] += 1
            if c == 'PLACE' and eff and len(cmd) > 1 and cmd[1] == 'GOOSE' and p not in SHED:
                goose['goose'] += 1
                goose.setdefault('goose_h', t % 24)
            if u == 0:
                continue
            spawn.setdefault(u, quad(p))
            q_ = lastpos.get(u)
            if q_ is not None and q_ != p:              # a move since the last step: outward / inward / sideways
                dd = cen(p) - cen(q_)
                m['mv_out' if dd > 0 else 'mv_in' if dd < 0 else 'mv_side'] += 1
                if dd:
                    dirs.setdefault(u, []).append(1 if dd > 0 else -1)
            lastpos[u] = p
            if p not in SHED:
                visits.setdefault(p, set()).add(u)
                if cen(p) > 2:
                    pvisits.setdefault(p, set()).add(u)
            if c == 'PASS':
                m['idle'] += 1
            elif c in MOVES:
                m['moves'] += 1
            elif c in FIELD and eff and not (c == 'PLACE' and p in SHED):
                m['field'] += 1
                ops_q.setdefault(u, Counter())[quad(p)] += 1
                if not seg.get(u):
                    seg[u] = True
                    trips[u] += 1
                q0 = last.get(u)
                if q0 is not None and q0 != p and cen(q0) > 2 and cen(p) > 2:     # adjacency within the patch
                    g = abs(q0[0] - p[0]) + abs(q0[1] - p[1])
                    m['gap_n'] += 1
                    m['gap_sum'] += g
                    m['gap_%s' % (g if g < 4 else '4+')] += 1
                last[u] = p
            elif c in ('PICKUP', 'DROP', 'PLACE') and eff and p in SHED:
                seg[u] = False
                last.pop(u, None)
    hands = len(spawn)
    m['hands'] = hands
    for t_, hs in (r.get('hires') or {}).items():
        if lo <= int(t_) < hi:
            for h_ in hs:
                if h_[0]:
                    m['hired'] += 1
                    m['wages'] += float(h_[1])
    m['extra_visits'] = sum(len(v) - 1 for v in visits.values() if len(v) > 1)
    m['extra_visits_patch'] = sum(len(v) - 1 for v in pvisits.values() if len(v) > 1)
    main = {u: q.most_common(1)[0][0] for u, q in ops_q.items() if q}
    m['main_ops'] = sum(ops_q[u][main[u]] for u in main)
    m['one_quad'] = sum(1 for u, q in ops_q.items() if len(q) == 1)
    m['worked'] = len(ops_q)
    m['main_is_spawn'] = sum(1 for u in main if main[u] == spawn.get(u))
    for u, q in spawn.items():
        m['spawn_' + QN[q]] += 1
    for u, k in trips.items():
        m['trips_%s' % (k if k < 3 else '3+')] += 1
    m['trip_hands'] = len(trips)
    for u in spawn:
        sq = dirs.get(u, [])
        rev = sum(1 for a_, b_ in zip(sq, sq[1:]) if a_ != b_)
        m['reversals'] += rev
        m['no_reversal'] += 1 if rev == 0 else 0
    return m, goose


def trace(arms):
    R = {a: {int(f.stem): json.loads(f.read_text(encoding='utf-8')) for f in (OUT / 'trace' / a).glob('1*.json')}
         for a in ['LEADER'] + [a for a in arms if a != 'LEADER']}
    L = R['LEADER']
    hi = str(11 * 24 + 24)
    lines = [f'day 11 from the leader exact morning; worlds with LEADER: {len(L)}']

    def cash(r):
        return r['obs'][hi]['money']

    def margin(r):
        return r['obs'][hi]['money'] - r['opp_cash'][hi]
    base = arms[0]
    for a in [x for x in arms if x != 'LEADER']:
        A = R[a]
        c = sorted(set(A) & set(L))
        dc = [cash(A[e]) - cash(L[e]) for e in c]
        c = [e for e in c if 'opp_cash' in A[e] and 'opp_cash' in L[e]] or c
        dm = [margin(A[e]) - margin(L[e]) for e in c] if all('opp_cash' in A[e] and 'opp_cash' in L[e] for e in c) else [0.0]
        extra = ''
        if a != base and base in R and base != 'LEADER':
            cb = sorted(set(c) & set(R[base]))
            extra = f' | vs {base}: cash {ci([cash(A[e]) - cash(R[base][e]) for e in cb])}'
            if all('opp_cash' in A[e] and 'opp_cash' in R[base][e] for e in cb):
                extra += f', margin {ci([margin(A[e]) - margin(R[base][e]) for e in cb])}'
        lines.append(f'{a} ({len(c)}): cash gap to leader {st.mean(dc):+,.0f}, margin gap {st.mean(dm):+,.0f}{extra}')
    lines.append('')
    lines.append('| arm | coop built / goose placed (worlds) | hands | extra hand-visits (all / patch only) | idle (PASS) | moves / hand | field ops / hand | '
                 'main-quadrant share | one-quadrant hands | main = spawn | spawn first / second / third / fourth | '
                 'trips 1 / 2 / 3+ | work-tile gap 1 / 2 / 3 / 4+ (mean) |')
    lines.append('|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|')
    ghr = []
    import lead_g1
    g1 = set(int(g.split(':')[1]) for g in lead_g1.GAMES)
    for a in ['LEADER'] + [x for x in arms if x != 'LEADER']:
        A = R[a]
        tot, gs = Counter(), Counter()
        hrs, hrs1 = [], []
        for e, r in A.items():
            m, g = hand_metrics(r)
            tot.update(m)
            gs['coop'] += 1 if g['coop'] else 0
            gs['goose'] += 1 if g['goose'] else 0
            if 'goose_h' in g:
                hrs.append(g['goose_h'])
                if e in g1:
                    hrs1.append(g['goose_h'])
        ghr.append(f"{a}: moves per hand-day outward / inward / sideways {tot['mv_out'] / max(1, tot['hands']):.1f} / "
                   f"{tot['mv_in'] / max(1, tot['hands']):.1f} / {tot['mv_side'] / max(1, tot['hands']):.1f}; reversals per "
                   f"hand-day {tot['reversals'] / max(1, tot['hands']):.2f}, hands never reversing {tot['no_reversal'] / max(1, tot['hands']):.0%}")
        ghr.append(f"{a}: hires on day 11 {tot['hired'] / max(1, len(A)):.1f} a world, wages {tot['wages'] / max(1, len(A)):,.0f}")
        ghr.append(f"{a}: goose placed on day 11 in {len(hrs)} of {len(A)} worlds (hours {sorted(Counter(hrs).items())}); "
                   f"G1 worlds: {len(hrs1)} of {sum(1 for e in A if e in g1)} (hours {sorted(Counter(hrs1).items())})")
        n = max(1, len(A))
        hd = max(1, tot['hands'])
        lines.append(f"| {a} | {gs['coop']} / {gs['goose']} of {len(A)} | {tot['hands'] / n:.1f} | {tot['extra_visits'] / n:.1f} / {tot['extra_visits_patch'] / n:.1f} | "
                     f"{tot['idle'] / n:.1f} | {tot['moves'] / hd:.1f} | {tot['field'] / hd:.1f} | "
                     f"{tot['main_ops'] / max(1, tot['field']):.0%} | {tot['one_quad'] / max(1, tot['worked']):.0%} | "
                     f"{tot['main_is_spawn'] / max(1, tot['worked']):.0%} | {tot['spawn_first'] / n:.1f} / "
                     f"{tot['spawn_second'] / n:.1f} / {tot['spawn_third'] / n:.1f} / {tot['spawn_fourth'] / n:.1f} | "
                     f"{tot['trips_1'] / max(1, tot['trip_hands']):.0%} / {tot['trips_2'] / max(1, tot['trip_hands']):.0%} / "
                     f"{tot['trips_3+'] / max(1, tot['trip_hands']):.0%} | " + ' / '.join(
                         f"{tot['gap_' + k] / max(1, tot['gap_n']):.0%}" for k in ('1', '2', '3', '4+'))
                     + f" ({tot['gap_sum'] / max(1, tot['gap_n']):.2f}) |")
    lines += [''] + ghr
    txt = '\n'.join(lines)
    print(txt)
    (OUT / f"trace_report_{'_'.join(arms)[:60]}.txt").write_text(txt + '\n', encoding='utf-8')


def full(base, arms):
    B = {int(f.stem): json.loads(f.read_text(encoding='utf-8')) for f in (OUT / 'full' / base).glob('1*.json')}
    lines = [f'full games vs {base} ({len(B)} worlds); gap to leader {st.mean(r["target"] - r["final"] for r in B.values()):,.0f}'
             if B and 'target' in next(iter(B.values())) else f'full games vs {base} ({len(B)} worlds)']
    for a in arms:
        A = {int(f.stem): json.loads(f.read_text(encoding='utf-8')) for f in (OUT / 'full' / a).glob('1*.json')}
        c = sorted(set(A) & set(B))
        if not c:
            continue
        fo = lambda r: r.get('final')
        op = lambda r: r.get('opp_final', r.get('rival'))
        dm = [(fo(A[e]) - op(A[e])) - (fo(B[e]) - op(B[e])) for e in c]
        do = [fo(A[e]) - fo(B[e]) for e in c]
        gap = st.mean(A[e]['target'] - fo(A[e]) for e in c) if 'target' in A[c[0]] else float('nan')
        lines.append(f'{a} ({len(c)}): margin {ci(dm)} | own {ci(do)} | gap to leader {gap:,.0f}')
    txt = '\n'.join(lines)
    print(txt)
    (OUT / f"full_report_{base}_{'_'.join(arms)[:60]}.txt").write_text(txt + '\n', encoding='utf-8')


if __name__ == '__main__':
    if sys.argv[1] == 'trace':
        trace(sys.argv[2].split(','))
    else:
        full(sys.argv[2], sys.argv[3].split(','))
