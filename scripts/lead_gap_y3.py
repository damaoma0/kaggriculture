"""Gap of a deploy build vs y3 on the p2750 panel from the stored panel records only (no games): margin = own cash -
rival cash; own cash = revenue - spend (spend lines); revenue by day window; rival revenue; per-world distribution and
its relation to the world's shop list (data/ladder_panel/p2750/<ep>.json.gz 'shops', reveal day 3 x (index + 1)).

usage: lead_gap_y3.py [agent=mgt_lpv_tw0] [ref=mgt_y3_cal]
"""
import gzip
import json
import random
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / 'results/fresh/ladder_panel'
WINDOWS = ((0, 5), (6, 11), (12, 17), (18, 23), (24, 29))
MILK_SHOPS = ('PIZZA_SHOP', 'ICE_CREAM_SHOP', 'SMOOTHIE_SHOP')


def boot(v, n=4000):
    rng = random.Random(3)
    s = sorted(st.mean(rng.choice(v) for _ in v) for _ in range(n))
    return s[int(.025 * n)], s[int(.975 * n)]


def spend_lines(sp):
    out = Counter()
    for k, v in sp.items():
        if k == 'HIRE':
            out['wages'] += v
        elif k == 'BUY_LAND':
            out['land'] += v
        elif k.startswith('BUY_SEED'):
            out['seeds'] += v
        elif k.startswith('BUY_ANIMAL'):
            out['animals'] += v
        elif k == 'BUY_PRODUCT:WHEAT':
            out['wheat bought'] += v
        elif k == 'BUY_PRODUCT:FERTILIZER':
            out['fertilizer bought'] += v
        else:
            out['other'] += v
    return out


def window_rev(daily, a, b):
    """revenue earned in days a..b from the cumulative per-day snapshots (entry d = cumulative at the end of day d)."""
    def tot(i):
        if i < 0:
            return 0.0
        i = min(i, len(daily) - 1)
        return float(sum(daily[i].values()))
    return tot(b) - tot(a - 1)


def main():
    agent = sys.argv[1] if len(sys.argv) > 1 else 'mgt_lpv_tw0'
    ref = sys.argv[2] if len(sys.argv) > 2 else 'mgt_y3_cal'
    eps = sorted(f.stem for f in (P / agent).glob('*.json') if (P / ref / f.name).exists())
    A = {e: json.load(open(P / agent / f'{e}.json')) for e in eps}
    B = {e: json.load(open(P / ref / f'{e}.json')) for e in eps}
    n = len(eps)
    gap = [A[e]['margin'] - B[e]['margin'] for e in eps]
    own = [A[e]['final'] - B[e]['final'] for e in eps]
    riv = [A[e]['rival'] - B[e]['rival'] for e in eps]
    lo, hi = boot(gap)
    print(f'{agent} vs {ref}, {n} worlds: margin {st.mean(gap):+,.0f} (95% CI {lo:+,.0f} .. {hi:+,.0f}) = own cash '
          f'{st.mean(own):+,.0f} - rival cash {st.mean(riv):+,.0f}')
    ra = st.mean(sum(A[e]['revenue'].values()) for e in eps)
    rb = st.mean(sum(B[e]['revenue'].values()) for e in eps)
    sa = Counter(); sb = Counter()
    for e in eps:
        sa.update(spend_lines(A[e]['spend']))
        sb.update(spend_lines(B[e]['spend']))
    print(f'  revenue {ra:,.0f} vs {rb:,.0f} ({ra - rb:+,.0f}); spend {sum(sa.values()) / n:,.0f} vs {sum(sb.values()) / n:,.0f} '
          f'({(sum(sa.values()) - sum(sb.values())) / n:+,.0f} = more spent by us)')
    print('  spend lines (ours / y3 / difference against us): ' + '; '.join(
        f'{k} {sa[k] / n:,.0f} / {sb[k] / n:,.0f} / {(sa[k] - sb[k]) / n:+,.0f}' for k in sorted(set(sa) | set(sb))))
    print('  revenue by day window (ours - y3): ' + ', '.join(
        f'd{a}-{b} {st.mean(window_rev(A[e]["revenue_daily"], a, b) - window_rev(B[e]["revenue_daily"], a, b) for e in eps):+,.0f}'
        for a, b in WINDOWS))
    rr = Counter()
    for e in eps:
        for k, v in A[e]['rival_revenue'].items():
            rr[k] += v / n
        for k, v in B[e]['rival_revenue'].items():
            rr[k] -= v / n
    print('  rival revenue (vs ours, - = the rival earns less against us): total %+.0f; ' % sum(rr.values()) + ', '.join(
        f'{k} {v:+,.0f}' for k, v in sorted(rr.items(), key=lambda x: x[1]) if abs(v) >= 50))
    clean = [g for e, g in zip(eps, gap) if abs(A[e].get('opp_dead', 0) - B[e].get('opp_dead', 0)) <= 40]
    lo2, hi2 = boot(clean)
    print(f'  excluding worlds where the rival tape breaks against one build (|rival no-effect commands diff| > 40): '
          f'{len(clean)} worlds, margin {st.mean(clean):+,.0f} (95% CI {lo2:+,.0f} .. {hi2:+,.0f}), median {sorted(clean)[len(clean) // 2]:+,.0f}')
    qs = sorted(gap)
    print('  per-world margin gap quantiles: min %+.0f, p10 %+.0f, p25 %+.0f, median %+.0f, p75 %+.0f, p90 %+.0f, max %+.0f; '
          'worlds where we beat y3: %d' % (qs[0], qs[int(.1 * n)], qs[int(.25 * n)], qs[n // 2], qs[int(.75 * n)],
                                          qs[int(.9 * n)], qs[-1], sum(g > 0 for g in gap)))
    shops, reveal = {}, {}
    for e in eps:
        g = json.load(gzip.open(ROOT / f'data/ladder_panel/p2750/{e}.json.gz', 'rt', encoding='utf-8'))
        by_day = g.get('shops') or []          # unlocked shops per day (31 lists, in unlock order)
        flat = list(by_day[-1]) if by_day else []
        shops[e] = flat
        reveal[e] = [next(d for d, lst in enumerate(by_day) if len(lst) > i) for i in range(len(flat))]
    feats = defaultdict(list)
    for e, gp in zip(eps, gap):
        sh = shops[e]
        yarn = [reveal[e][i] for i, s in enumerate(sh) if s == 'YARN_STORE']
        milk = [reveal[e][i] for i, s in enumerate(sh) if s in MILK_SHOPS]
        pet = [reveal[e][i] for i, s in enumerate(sh) if s == 'PET_CAFE']
        feats['Yarn Store: none' if not yarn else 'Yarn Store: first by day 12' if yarn[0] <= 12 else 'Yarn Store: first after day 12'].append(gp)
        feats[f'milk shops: {min(len(milk), 3)}{"+" if len(milk) >= 3 else ""}'].append(gp)
        feats['first milk shop: none' if not milk else 'first milk shop: by day 12' if milk[0] <= 12 else 'first milk shop: after day 12'].append(gp)
        feats['Pet Cafe: yes' if pet else 'Pet Cafe: no'].append(gp)
        feats['Farmers Market: yes' if 'FARMERS_MARKET' in sh else 'Farmers Market: no'].append(gp)
    print('  margin gap by shop features (mean, n):')
    for k in sorted(feats):
        v = feats[k]
        print(f'    {k:32s} {st.mean(v):+8,.0f}  (n={len(v)})')
    worst = sorted(zip(gap, eps))[:8]
    print('  worst worlds (gap, episode, opponent, shops in reveal order):')
    for gp, e in worst:
        opp = str(A[e].get("opponent")).encode('ascii', 'replace').decode('ascii')
        brk = abs(A[e].get('opp_dead', 0) - B[e].get('opp_dead', 0)) > 40
        print(f'    {gp:+9,.0f}  {e}  {opp}{"  [rival tape broken]" if brk else ""}  ' + ' '.join(s[:6] for s in shops[e]))


if __name__ == '__main__':
    main()
