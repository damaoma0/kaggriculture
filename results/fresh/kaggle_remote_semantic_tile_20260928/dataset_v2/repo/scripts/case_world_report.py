"""Report for a case_world.py log: per product, the leader's game vs the arm's game.
usage: case_world_report.py <case json> [--days 11-28]"""
import bisect
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
d = json.load(open(sys.argv[1]))
arm = d['arm']
G = {'DSM': d['leader'], arm: d[arm]}
PRODS = d['prods']
BK = (('h0', 0, 0), ('h1', 1, 1), ('h2-11', 2, 11), ('h12-23', 12, 23))


def bucket(h):
    return next(n for n, a, b in BK if a <= h <= b)


def iget(dct, k, default=0):
    return dct.get(str(k), dct.get(k, default)) if isinstance(dct, dict) else default


def stats(L, p):
    s = {}
    ev = [e for e in L['sales'] if e[3] == p]
    for side in ('us', 'opp'):
        sl = [e for e in ev if e[1] == side and e[2] == 'SELL']
        s[side] = {'n': len(sl), 'rev': sum(e[4] for e in sl), 'stock': sum(e[5] for e in sl) / max(1, len(sl))}
        for n, a, b in BK:
            x = [e for e in sl if a <= e[0] % 24 <= b]
            s[side][n] = (len(x), sum(e[4] for e in x) / max(1, len(x)))
    harv = sum(h[4] for h in L['harv'] if h[3] == p)
    prod = 0
    for day in range(11, 29):
        t0, t1 = day * 24, (day + 1) * 24
        prod += iget(L['tiles'][p], t1) - iget(L['tiles'][p], t0)
    prod += harv                      # tile growth + harvested = produced (days 11-28 nights)
    arr = L['arrive'][p]
    mid = sum(v for t, v in arr.items() if int(t) % 24 == 23)
    day_ = sum(v for t, v in arr.items() if int(t) % 24 != 23)
    arr_b = Counter()
    for t, v in arr.items():
        t = int(t)
        arr_b[bucket((t + 1) % 24) if t % 24 == 23 else bucket(t % 24)] += v
    lost = sum(iget(v, p) for v in L['lost'].values())
    end = iget(L['tiles'][p], 719) + iget(L['carried'][p], 719) + iget(L['shed'][p], 719)
    s.update(harv=harv, prod=prod, mid=mid, dayarr=day_, arr_b=arr_b, lost=lost, end=end,
             herd=sum(iget(L['herd'][p], dd) for dd in range(11, 29)) / 18)
    return s


def cum_times(L, p, side='us'):
    return sorted(e[0] for e in L['sales'] if e[3] == p and e[1] == side and e[2] == 'SELL')


print(f"world {d['game']}  money DSM {G['DSM']['money']['us']:.0f} vs rival {G['DSM']['money']['opp']:.0f} "
      f"(margin {G['DSM']['money']['us'] - G['DSM']['money']['opp']:+.0f}) | {arm} {G[arm]['money']['us']:.0f} vs rival "
      f"{G[arm]['money']['opp']:.0f} (margin {G[arm]['money']['us'] - G[arm]['money']['opp']:+.0f})\n")
params = G[arm]['params']
for p in PRODS:
    S = {k: stats(L, p) for k, L in G.items()}
    a, b = S['DSM'], S[arm]
    print('=' * 110)
    print(f"{p}: margin gap {(b['us']['rev'] - a['us']['rev']) - (b['opp']['rev'] - a['opp']['rev']):+.0f} = our revenue "
          f"{b['us']['rev'] - a['us']['rev']:+.0f} - rival revenue {b['opp']['rev'] - a['opp']['rev']:+.0f}")
    print('%-34s %10s %10s' % ('', 'DSM', arm))
    rows = [('herd / plants (mean, days 11-28)', 'herd', '%.1f'), ('units produced (days 11-28)', 'prod', '%d'),
            ('units harvested', 'harv', '%d'), ('delivered during the day', 'dayarr', '%d'),
            ('delivered in the midnight dump', 'mid', '%d'), ('deleted at midnight', 'lost', '%d'),
            ('held at the end', 'end', '%d')]
    for lab, k, fm in rows:
        print('  %-32s %10s %10s' % (lab, fm % a[k], fm % b[k]))
    for side, nm in (('us', 'our'), ('opp', 'rival')):
        print('  %-32s %10d %10d' % (f'{nm} units sold', a[side]['n'], b[side]['n']))
        print('  %-32s %10.0f %10.0f' % (f'{nm} revenue', a[side]['rev'], b[side]['rev']))
        print('  %-32s %10.1f %10.1f' % (f'{nm} avg price', a[side]['rev'] / max(1, a[side]['n']), b[side]['rev'] / max(1, b[side]['n'])))
        print('  %-32s %10.0f %10.0f' % (f'{nm} mean market stock at sale', a[side]['stock'], b[side]['stock']))
    print('  sales by hour (units @ avg price):')
    for side, nm in (('us', 'ours '), ('opp', 'rival')):
        for k in ('DSM', arm):
            print('    %-5s %-4s' % (nm, k[:4]) + ''.join('  %6s %4d @ %5.1f' % (n, *S[k][side][n]) for n, _, _ in BK))
    print('  units reaching the shed by hour (midnight dump counted at the next h0):')
    for k in ('DSM', arm):
        print('    %-9s' % k[:9] + ''.join('  %6s %4d' % (n, S[k]['arr_b'][n]) for n, _, _ in BK))
    # rival windfall: stock at each rival sale in both games, and our cumulative sales lag behind DSM at that moment
    rl = [e for e in G['DSM']['sales'] if e[3] == p and e[1] == 'opp' and e[2] == 'SELL']
    ra = [e for e in G[arm]['sales'] if e[3] == p and e[1] == 'opp' and e[2] == 'SELL']
    cd, ca = cum_times(G['DSM'], p), cum_times(G[arm], p)
    if rl and len(rl) == len(ra):
        lag = [bisect.bisect_left(cd, e[0]) - bisect.bisect_left(ca, e[0]) for e in ra]
        print(f"  rival sales: {len(ra)} units; market stock at them DSM game {sum(e[5] for e in rl) / len(rl):.0f}, "
              f"{arm} game {sum(e[5] for e in ra) / len(ra):.0f}; at those moments DSM had sold {sum(lag) / len(lag):+.1f} "
              f"units more than we had (cumulative)")
    # counterfactuals on this product (exact market replay logic of sale_pattern_cf.py)
    L = G[arm]
    ours = [e for e in L['sales'] if e[3] == p and e[1] == 'us' and e[2] == 'SELL']
    riv = [e for e in L['sales'] if e[3] == p and e[1] == 'opp' and e[2] == 'SELL']
    at = sorted(e[0] for e in ours)
    lt = cd
    av = sorted([264] * iget(L['shed'][p], 264) + [((int(t) + 1) if int(t) % 24 == 23 else int(t)) for t, v in L['arrive'][p].items() for _ in range(max(0, v))])
    m = min(len(at), len(lt))
    stock = {int(k): v for k, v in L['stock'][p].items()}
    for tag in ('A', 'B'):
        if tag == 'A':
            cf = sorted(lt[:m] + at[m:])
        else:
            cf = sorted([max(lt[k], av[k] if k < len(av) else at[k]) for k in range(m)] + at[m:])

        def delta(t, cf=cf):
            return bisect.bisect_left(cf, t) - bisect.bisect_left(at, t)
        rv = sum(E.market_price(p, e[5] + delta(e[0]), params) for e in riv)
        our, same = 0.0, Counter()
        for t in cf:
            our += E.market_price(p, stock.get(min(t, 718), 0) + delta(t) + same[t], params)
            same[t] += 1
        o0, r0 = sum(e[4] for e in ours), sum(e[4] for e in riv)
        print('  counterfactual %s (%s): ours %+6.0f, rival %+6.0f, margin %+6.0f' % (
            tag, "our units on DSM's sale times" if tag == 'A' else "same, never before the unit is in our shed",
            our - o0, rv - r0, (our - o0) - (rv - r0)))
    # daily table
    print('  day | DSM: made  deliv(day/mid) sold h0 h1 h2-11 h12-23 @px | %s: made deliv(day/mid) sold h0 h1 h2-11 h12-23 @px del | rival px DSM/%s' % (arm, arm))
    for day in range(11, 30):
        line = '  %3d |' % day
        for k in ('DSM', arm):
            L = G[k]
            t0, t1 = day * 24, (day + 1) * 24
            hv = sum(h[4] for h in L['harv'] if h[3] == p and t0 <= h[0] < t1)
            made = (iget(L['tiles'][p], t1) - iget(L['tiles'][p], t0) + hv) if day < 29 else 0
            dd = sum(v for t, v in L['arrive'][p].items() if t0 <= int(t) < t1 and int(t) % 24 != 23)
            dm = sum(v for t, v in L['arrive'][p].items() if t0 <= int(t) < t1 and int(t) % 24 == 23)
            sl = [e for e in L['sales'] if e[3] == p and e[1] == 'us' and e[2] == 'SELL' and t0 <= e[0] < t1]
            bb = Counter(bucket(e[0] % 24) for e in sl)
            px = sum(e[4] for e in sl) / max(1, len(sl))
            line += ' %4d %4d/%-4d %3d %3d %3d %3d @%5.0f' % (made, dd, dm, bb['h0'], bb['h1'], bb['h2-11'], bb['h12-23'], px)
            if k == arm:
                line += ' %3d' % iget(L['lost'].get(str(day), {}), p)
            line += ' |'
        rp = []
        for k in ('DSM', arm):
            x = [e[4] for e in G[k]['sales'] if e[3] == p and e[1] == 'opp' and e[2] == 'SELL' and day * 24 <= e[0] < day * 24 + 24]
            rp.append('%3d@%5.0f' % (len(x), sum(x) / max(1, len(x))))
        print(line + ' ' + ' / '.join(rp))
    print()
