"""Reports over leader_shed_flow.py output (results/fresh/leader_shed_20260926/).
usage: leader_shed_report.py [section ...]   (sections: nights types load fates volume k5b_distance cf prices lags;
       default all). Days 11-28 (K5b's season window). Output: results/fresh/leader_shed_20260926/report.txt"""
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
import statistics as st

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / 'results/fresh/leader_shed_20260926'
PROD = ('WHEAT', 'CARROT', 'TOMATO', 'MELON', 'STRAWBERRY', 'MILK', 'EGG', 'WOOL', 'FERTILIZER')
SHORT = {'Unknown Mother-Goose': 'MG', 'Vadim Vasilenko': 'Vadim', 'M & M & P & Q': 'MMPQ', 'DECEM': 'DECEM',
         'DSM': 'DSM', 'Boey': 'Boey'}


def load(name):
    for line in gzip.open(D / f'{name}.jsonl.gz', 'rt', encoding='utf-8'):
        r = json.loads(line)
        r['who'] = SHORT.get(r['names'][r['seat']], r['names'][r['seat']]) if r['arm'] == 'leader' else r['arm']
        yield r


_G = None


def groups(days=None, k5b_eps=None):
    """{group: [game,...]}: every leader team, K5b, and DSM/MG restricted to K5b's worlds."""
    g = defaultdict(list)
    k5 = list(load('k5b'))
    eps = {r['ep'] for r in k5}
    for r in load('leaders'):
        g[r['who']].append(r)
        if r['ep'] in eps:
            g['leader@K5b'].append(r)
    g['K5b'] = k5
    return g


def G():
    global _G
    if _G is None:
        _G = groups()
    return _G


def sec_nights():
    g = G()
    D0, D1 = 11, 28
    print('%-11s %4s | %6s %6s %6s %6s | %5s %5s %5s | %6s %6s | %6s %6s %6s' % ('group','n','shed23','carry','total','lost', '>100%','>=95%','max', 'midDel','h23Del', 'held', 'sold0-2','sold23'))
    for who, games in sorted(g.items()):
        N = []; mid = []; h23 = []; held=[]; s02=[]; s23=[]; sall=[]
        for r in games:
            for n in r['nights']:
                if D0 <= n['day'] <= D1 and 'shed23' in n:
                    s = sum(n['shed23'].values()); c = sum(n['carried'].values()); l = sum(n['lost'].values())
                    N.append((s, c, s + c, l)); held.append(sum(n['held'].values()))
            md = Counter(); hd = Counter()
            for d in r['drops']:
                if D0 <= d['day'] <= D1:
                    u = sum(d['produce'].values())
                    (hd if d['h'] == 23 else md)[d['day']] += u
            mid += [md[d] for d in range(D0, D1 + 1)]; h23 += [hd[d] for d in range(D0, D1 + 1)]
            tot = Counter(); 
            for m in r['market']:
                if m['op'] == 'SELL' and D0*24 <= m['t'] < (D1+1)*24:
                    h = m['t'] % 24
                    tot['all'] += m['n']; tot['02' if h <= 2 else ('23' if h == 23 else 'mid')] += m['n']
            s02.append(tot['02'] / max(1, tot['all'])); s23.append(tot['23'] / max(1, tot['all']))
        m = lambda i: st.mean(x[i] for x in N)
        print('%-11s %4d | %6.1f %6.1f %6.1f %6.2f | %5.1f %5.1f %5d | %6.1f %6.1f | %6.1f %6.2f %6.2f' % (who, len(games), m(0), m(1), m(2), m(3),
              100*sum(x[2] > 100 for x in N)/len(N), 100*sum(x[2] >= 95 for x in N)/len(N), max(x[2] for x in N),
              st.mean(mid), st.mean(h23), st.mean(held), st.mean(s02), st.mean(s23)))

def sec_types():
    g = G()
    D0, D1 = 11, 28
    man = lambda a, b: abs(a[0]-b[0]) + abs(a[1]-b[1])
    def cat(d):
        if d['trip_start'] is None: return 'A_atshed'
        if d['h'] == 23: return 'E_h23'
        if not d['left_again']: return 'C_endroute'
        return 'B_turn'
    for who in ['DSM','MG','Vadim','DECEM','MMPQ','Boey','K5b']:
        games = g[who]; nd = len(games) * (D1 - D0 + 1)
        C = defaultdict(Counter); U = defaultdict(Counter); det = defaultdict(list); hrs = defaultdict(Counter); sold = defaultdict(lambda: [0,0])
        for r in games:
            for d in r['drops']:
                u = sum(d['produce'].values())
                if not (D0 <= d['day'] <= D1) or u <= 0: continue
                c = cat(d)
                C[c]['n'] += 1; U[c].update(d['produce'])
                hrs[c][d['h']//4*4] += u
                ss = sum(min(v, d['sold_same_h'].get(k, 0)) for k, v in d['produce'].items())
                sold[c][0] += ss; sold[c][1] += u
                if d['prev'] and d['nxt']:
                    det[c].append(man(d['prev'][1], d['at']) + man(d['at'], d['nxt'][1]) - man(d['prev'][1], d['nxt'][1]))
        print('==', who, 'games', len(games))
        for c in sorted(C):
            tot = sum(U[c].values())
            top = ', '.join('%s %.1f' % (k[:5], v/nd) for k, v in U[c].most_common(6))
            print('  %-11s drops/day %.2f units/day %5.1f units/drop %4.1f sold same h %3.0f%% detour med %s mean %.1f | %s' % (c, C[c]['n']/nd, tot/nd, tot/C[c]['n'], 100*sold[c][0]/max(1,sold[c][1]),
                  st.median(det[c]) if det[c] else '-', st.mean(det[c]) if det[c] else 0, top))
            print('              units by 4h block:', ' '.join('%02d:%.1f' % (h, v/nd) for h, v in sorted(hrs[c].items())))

def sec_load():
    g = G()
    D0, D1 = 11, 28
    rows = defaultdict(list)
    for who in ['DSM','MG','Vadim','DECEM','MMPQ','Boey','K5b']:
        for r in g[who]:
            H = Counter(); M = Counter(); M23 = Counter()
            for u in r['units']:
                pass
            for d in r['drops']:
                u = sum(d['produce'].values())
                if d['h'] < 23 and d['trip_start'] is not None: M[d['day']] += u
                elif d['h'] < 23: M[d['day']] += u
                else: M23[d['day']] += u
            # harvested per day = produce delivered (any hour) + carried produce at midnight (approx: carried minus nothing)
            for n in r['nights']:
                dd = n['day']
                if not (D0 <= dd <= D1) or 'shed23' not in n: continue
                carried = sum(n['carried'].values()); shed = sum(n['shed23'].values())
                rows[who].append(dict(M=M[dd], M23=M23[dd], C=carried, S=shed, T=carried+shed, L=sum(n['lost'].values()), held=sum(n['held'].values())))
    for who, R in rows.items():
        R.sort(key=lambda x: x['M'] + x['C'])
        q = len(R)//5
        print('==', who, 'nights', len(R), ' cf total (no midday) >100: %.0f%%   actual >100: %.0f%%' % (100*sum(x['T']+x['M']>100 for x in R)/len(R), 100*sum(x['T']>100 for x in R)/len(R)))
        for i in range(5):
            B = R[i*q:(i+1)*q] if i < 4 else R[4*q:]
            print('   quintile %d of (midday+carry): midday %5.1f carried %5.1f shed23 %5.1f total %5.1f held %5.1f lost %.2f  share midday %.0f%%' % (i+1,
                  st.mean(x['M'] for x in B), st.mean(x['C'] for x in B), st.mean(x['S'] for x in B), st.mean(x['T'] for x in B), st.mean(x['held'] for x in B), st.mean(x['L'] for x in B),
                  100*st.mean(x['M'] for x in B)/max(1e-9, st.mean(x['M']+x['C'] for x in B))))

def sec_fates():
    g = G()
    D0, D1 = 11, 28
    TOP = ['DSM','MG','Vadim','DECEM','MMPQ','Boey']
    def fate_table(games, label):
        T = defaultdict(Counter)   # (product) -> fate class counts
        HB = defaultdict(lambda: defaultdict(Counter))
        for r in games:
            for day, unit, k, h, n, fate, pos in r['harv']:
                if not (D0 <= day <= D1): continue
                f = 'consumed' if fate == -1 else ('carried' if fate == 24 else ('h23' if fate == 23 else 'sameday'))
                T[k][f] += n; T[k]['all'] += n
                HB[k][h // 4 * 4][f] += n; HB[k][h//4*4]['all'] += n
        nd = len(games) * (D1 - D0 + 1)
        print('==', label, 'games', len(games))
        for k in PROD:
            c = T[k]
            if not c['all']: continue
            byh = ' '.join('%02d:%3.0f%%(%4.1f)' % (h, 100*HB[k][h]['sameday']/max(1, HB[k][h]['all']-HB[k][h]['consumed']), HB[k][h]['all']/nd) for h in sorted(HB[k]))
            print('  %-10s %5.1f/day  same-day %3.0f%%  h23 %2.0f%%  carried %3.0f%%  consumed %3.0f%% | by harvest hour: same-day%% (units/day) %s' % (k, c['all']/nd, 100*c['sameday']/c['all'], 100*c['h23']/c['all'], 100*c['carried']/c['all'], 100*c['consumed']/c['all'], byh))
    fate_table(sum((g[t] for t in TOP), []), 'six leader teams')
    fate_table(g['DSM'], 'DSM')
    fate_table(g['K5b'], 'K5b')

def sec_prices():
    g = G()
    D0, D1 = 11, 28
    TOP = ['DSM','MG','Vadim','DECEM','MMPQ','Boey']
    PI = {p: i for i, p in enumerate(PROD)}
    for label, games in [('six leaders', sum((g[t] for t in TOP), [])), ('DSM', g['DSM']), ('K5b', g['K5b'])]:
        S = defaultdict(lambda: defaultdict(lambda: [0, 0.0]))
        Q = defaultdict(lambda: defaultdict(list))
        for r in games:
            for m in r['market']:
                if m['op'] != 'SELL' or not (D0*24 <= m['t'] < (D1+1)*24): continue
                h = m['t'] % 24
                b = 'h0-2' if h <= 2 else ('h3-11' if h <= 11 else ('h12-22' if h <= 22 else 'h23'))
                S[m['item']][b][0] += m['n']; S[m['item']][b][1] += m['rev']
            # quote by hour, averaged (market level, both players)
            for t in range(D0*24, (D1+1)*24):
                for p in ('MILK','WOOL','STRAWBERRY','EGG','WHEAT','MELON'):
                    Q[p][t % 24].append(r['quotes'][t][PI[p]])
        print('==', label)
        for p in ('MILK','WOOL','STRAWBERRY','EGG','CARROT','TOMATO','WHEAT','MELON','FERTILIZER'):
            row = ' '.join('%s %5.1f (%4.0f%%)' % (b, S[p][b][1]/S[p][b][0] if S[p][b][0] else 0, 100*S[p][b][0]/max(1,sum(v[0] for v in S[p].values()))) for b in ('h0-2','h3-11','h12-22','h23'))
            print('   %-10s avg sale price (share of units): %s' % (p, row))
        for p in ('MILK','WOOL','STRAWBERRY','EGG'):
            print('   quote by hour %-10s' % p, ' '.join('%d:%.0f' % (h, st.mean(Q[p][h])) for h in (0,1,2,3,4,6,8,12,16,20,23)))

def sec_volume():
    g = G()
    D0, D1 = 11, 28
    TOP = ['DSM','MG','Vadim','DECEM','MMPQ','Boey']
    ACC = [(4,4),(5,4),(4,5),(5,5)]
    dist = lambda p: min(abs(p[0]-a[0]) + abs(p[1]-a[1]) for a in ACC)
    games = sum((g[t] for t in TOP), [])
    # 1) quintiles of day volume: midday composition
    days = []
    for r in games:
        mid = defaultdict(Counter); vol = Counter()
        for day, unit, k, h, n, fate, pos in r['harv']:
            if not (D0 <= day <= D1) or fate == -1: continue
            vol[day] += n
            if 0 <= fate <= 22: mid[day][k] += n
        for d in range(D0, D1 + 1):
            days.append((vol[d], mid[d]))
    days.sort(key=lambda x: x[0]); q = len(days) // 5
    for i in range(5):
        B = days[i*q:(i+1)*q]
        tot = Counter()
        for _, m in B: tot.update(m)
        print('volume quintile %d: harvested %.0f/day, same-day %.1f: %s' % (i+1, st.mean(v for v,_ in B), sum(tot.values())/len(B), ', '.join('%s %.1f' % (k[:5], v/len(B)) for k, v in tot.most_common(6))))
    # 2) same-day share by product x distance x hour
    print()
    T = defaultdict(lambda: [0, 0])
    for r in games:
        for day, unit, k, h, n, fate, pos in r['harv']:
            if not (D0 <= day <= D1) or fate == -1: continue
            db = min(dist(pos), 4); hb = 'h0-7' if h < 8 else ('h8-15' if h < 16 else 'h16-23')
            T[(k, db, hb)][1] += n
            if 0 <= fate <= 23: T[(k, db, hb)][0] += n
    for k in ('MILK','WOOL','EGG','STRAWBERRY','WHEAT','CARROT','TOMATO'):
        print('%-10s' % k, ' | '.join('d%s%s: ' % (db, '+' if db == 4 else '') + ' '.join('%3.0f%%(%4.0f)' % (100*T[(k,db,hb)][0]/T[(k,db,hb)][1], T[(k,db,hb)][1]/len(games)) if T[(k,db,hb)][1] else '   -(   0)' for hb in ('h0-7','h8-15','h16-23')) for db in range(5)))

def sec_k5b_distance():
    g = G()
    D0, D1 = 11, 28
    ACC = [(4,4),(5,4),(4,5),(5,5)]
    dist = lambda p: min(min(abs(p[0]-a[0]) + abs(p[1]-a[1]) for a in ACC), 4)
    for label, games in [('leader on K5b worlds', [r for r in g['leader@K5b'] if r['team'] in ('16732748','16730612')]), ('K5b', g['K5b'])]:
        T = defaultdict(lambda: [0,0])
        for r in games:
            for day, unit, k, h, n, fate, pos in r['harv']:
                if D0 <= day <= D1 and fate != -1:
                    T[(k, dist(pos))][1] += n
                    if 0 <= fate <= 23: T[(k, dist(pos))][0] += n
        print('==', label)
        for k in ('MILK','WOOL','EGG','STRAWBERRY','WHEAT'):
            print('  %-10s same-day by distance: %s' % (k, ' '.join('d%d %3.0f%% (%3.0f/w)' % (d, 100*T[(k,d)][0]/max(1,T[(k,d)][1]), T[(k,d)][1]/len(games)) for d in range(5))))

def sec_cf():
    g = G()
    D0, D1 = 11, 28
    TOP = ['DSM','MG','Vadim','DECEM','MMPQ','Boey']
    ACC = [(4,4),(5,4),(4,5),(5,5)]
    dist = lambda p: min(min(abs(p[0]-a[0]) + abs(p[1]-a[1]) for a in ACC), 4)
    hb = lambda h: 0 if h < 8 else (1 if h < 16 else 2)
    T = defaultdict(lambda: [0, 0])
    for r in sum((g[t] for t in TOP), []):
        for day, unit, k, h, n, fate, pos in r['harv']:
            if not (D0 <= day <= D1) or fate == -1: continue
            T[(k, dist(pos), hb(h))][1] += n
            if 0 <= fate <= 23: T[(k, dist(pos), hb(h))][0] += n
    p = lambda k, d, h: T[(k, d, h)][0] / T[(k, d, h)][1] if T[(k, d, h)][1] >= 30 else 0.0
    PI = {q: i for i, q in enumerate(PROD)}
    tot = Counter(); nn = 0; per = []
    for r in g['K5b']:
        exp_rm = defaultdict(Counter)
        for day, unit, k, h, n, fate, pos in r['harv']:
            if D0 <= day <= D1 and fate == 24:
                exp_rm[day][k] += n * p(k, dist(pos), hb(h))
        for n in r['nights']:
            d = n['day']
            if not (D0 <= d <= D1) or 'shed23' not in n: continue
            total = sum(n['shed23'].values()) + sum(n['carried'].values())
            rm = sum(exp_rm[d].values())
            lost = sum(n['lost'].values())
            lost_cf = max(0, total - rm - 100)
            val = sum(v * r['quotes'][(d+1)*24][PI[k]] for k, v in n['lost'].items())
            tot['lost'] += lost; tot['lost_cf'] += lost_cf; tot['rm'] += rm; tot['val'] += val
            tot['val_cf'] += val * (lost_cf / lost if lost else 0)
            tot['nights'] += 1; tot['over'] += total > 100; tot['over_cf'] += total - rm > 100
    print('K5b nights', tot['nights'], 'units moved to same-day at leader rates %.1f/night' % (tot['rm']/tot['nights']))
    print('deleted per world (days 11-28): actual %.1f -> at leader delivery rates %.1f' % (tot['lost']/53, tot['lost_cf']/53))
    print('nights over 100: %.0f%% -> %.0f%%' % (100*tot['over']/tot['nights'], 100*tot['over_cf']/tot['nights']))
    print('deleted value per world at next-morning quote: %.0f -> %.0f (rough)' % (tot['val']/53, tot['val_cf']/53))

def sec_lags():
    g = G()
    D0, D1 = 11, 28
    TOP = ['DSM','MG','Vadim','DECEM','MMPQ','Boey']
    KS = ('MILK','WOOL','STRAWBERRY','EGG','CARROT','TOMATO','MELON','WHEAT')
    def lags(games):
        L = defaultdict(Counter)
        for r in games:
            ev = defaultdict(list)   # k -> [(t, +n, kind) or (t, -n)]
            for d in r['drops']:
                t = d['day']*24 + d['h']
                for k, v in d['delivered'].items():
                    v2 = v - d['lost_at_drop'].get(k, 0)
                    if v2 > 0 and k in KS: ev[k].append((t, 0, v2, 'mid' if d['h'] < 23 else 'h23'))
            for n in r['nights']:
                if 'carried' not in n: continue
                t = n['day']*24 + 23.5
                for k, v in n['carried'].items():
                    v2 = v - n['lost'].get(k, 0)
                    if v2 > 0 and k in KS: ev[k].append((t, 0, v2, 'night'))
            for m in r['market']:
                if m['item'] in KS and m['op'] == 'SELL': ev[m['item']].append((m['t'], 1, m['n'], None))
                if m['item'] in KS and m['op'] == 'BUY_PRODUCT': ev[m['item']].append((m['t'] - 0.1, 0, m['n'], 'buy'))
            for k, E in ev.items():
                E.sort(key=lambda x: (x[0], x[1]))
                q = []
                for t, typ, n, kind in E:
                    if typ == 0: q.append([t, n, kind]); continue
                    while n > 0 and q:
                        m = min(n, q[0][1]); t0, kind0 = q[0][0], q[0][2]
                        if D0 <= int(t0) // 24 <= D1 and kind0 in ('mid', 'night'):
                            lag = t - t0
                            if kind0 == 'mid':
                                b = 'same h' if lag < 0.5 else ('1-3h' if lag <= 3 else ('4-11h' if lag <= 11 else ('later same day' if int(t)//24 == int(t0)//24 else 'next day+')))
                            else:
                                b = 'h0' if lag < 1 else ('h1-2' if lag <= 3 else ('h3-11' if lag <= 12 else 'later'))
                            L[(k, kind0)][b] += m
                        q[0][1] -= m; n -= m
                        if q[0][1] == 0: q.pop(0)
        return L
    for label, games in [('six leaders', sum((g[t] for t in TOP), [])), ('K5b', g['K5b'])]:
        L = lags(games)
        print('==', label)
        for k in KS:
            a = L[(k, 'mid')]; s = sum(a.values())
            b = L[(k, 'night')]; s2 = sum(b.values())
            print('  %-10s midday-delivered sold: %s || night-carry sold: %s' % (k, ' '.join('%s %2.0f%%' % (x, 100*a[x]/max(1,s)) for x in ('same h','1-3h','4-11h','later same day','next day+')),
                  ' '.join('%s %2.0f%%' % (x, 100*b[x]/max(1,s2)) for x in ('h0','h1-2','h3-11','later'))))


SECTIONS = ['nights', 'types', 'load', 'fates', 'volume', 'k5b_distance', 'cf', 'prices', 'lags']

if __name__ == '__main__':
    for s in (sys.argv[1:] or SECTIONS):
        print('\n######', s)
        globals()['sec_' + s]()
