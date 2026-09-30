"""Independent skeptic check of the T-gap top-level split (stored data only, one process).

Reads E1's raw ledgers (ledg1) and recomputes, per game and per product:
  gap = leader final - ours final
  A   = (harvested_L - harvested_O) x P_L          (fertilizer has no HARVEST op: sold units stand in)
  C1  = -[(harv_L - sold_L) - (harv_O - sold_O)] x P_L
  C2  = sold_O x (P_L - P_O)
  inputs = -(spend_L - spend_O)   (trades: seeds, animals, bought wheat/fertilizer)
  B   = wages_O - wages_L ; land = land_O - land_L
P = revenue / units sold per product and side; if a side sold none: P_L falls back to P_O, P_O to P_L.
Checks: every run's final cash == 3000 + revenue - spend - wages - land (exact), the leader replay reproduces its
recorded cash (target) and the opponent's, the per-day cash chain, and the four-quadrant split (no ' L' tile on the
leader's last board in data/leader_semantics). Also cross-checks the local results/fresh/lead_ledger copies.
Alternative definitions are printed to show how sensitive the split is.
"""
import gzip
import json
import math
import statistics as st
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
E1 = ROOT / 'results/fresh/kaggle_remote_lead/ledg1/output/kgr-ledg1-s0/out/repo/results/fresh/lead_ledger'
LOC = ROOT / 'results/fresh/lead_ledger'
SEM = ROOT / 'data/leader_semantics'
PRODUCTS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"]
T95 = {12: 2.201, 8: 2.365, 4: 3.182}


def ci(xs):
    m = st.mean(xs)
    if len(xs) < 2:
        return f'{m:+,.0f}'
    h = T95.get(len(xs), 2.0) * st.stdev(xs) / math.sqrt(len(xs))
    return f'{m:+9,.0f} ({m - h:+,.0f}..{m + h:+,.0f})'


def sums(r):
    S = dict(rev=Counter(), sold=Counter(), harv=Counter(), spend=Counter(), bought=Counter(), opk=Counter())
    wages = land = 0.0
    for d in r['days']:
        for k in S:
            S[k].update(d.get(k, {}) or {})
        wages += d.get('wages', 0) or 0
        land += d.get('land', 0) or 0
    return S, wages, land


def four(team, ep):
    g = json.load(gzip.open(SEM / team / f'{ep}.json.gz', 'rt', encoding='utf-8'))
    return sum(1 for c in g['days'][-1]['board'] if c == ' L') == 0, g['meta']


def main():
    eps = sorted(p.name[7:-5] for p in E1.glob('leader_*.json'))
    rows, problems = [], []
    for ep in eps:
        L = json.load(open(E1 / f'leader_{ep}.json'))
        O = json.load(open(E1 / f'ours_{ep}.json'))
        team = L['game'].split(':')[0]
        is4, meta = four(team, ep)
        # --- reproduction checks
        if L['final'] != L['target'] or L['opp_final'] != L['target_opp']:
            problems.append(f'{ep}: leader replay cash {L["final"]}/{L["opp_final"]} vs recorded {L["target"]}/{L["target_opp"]}')
        if L['seat'] != O['seat'] or L['seat'] != meta['seat']:
            problems.append(f'{ep}: seat mismatch L{L["seat"]} O{O["seat"]} sem{meta["seat"]}')
        if meta['rewards'][L['seat']] != L['target']:
            problems.append(f'{ep}: target != semantics reward')
        if O['target'] != L['target']:
            problems.append(f'{ep}: ours.target != leader.target')
        side = {}
        for nm, r in (('L', L), ('O', O)):
            S, w, ld = sums(r)
            flow = 3000 + sum(S['rev'].values()) - sum(S['spend'].values()) - w - ld
            if abs(flow - r['final']) > 1e-6:
                problems.append(f'{ep} {nm}: cash flow {flow} != final {r["final"]}')
            # daily cash chain: cash at hour 0 of day d+1 = cash(d) + day d flows
            for di in range(29):
                d, n = r['days'][di], r['days'][di + 1]
                if d['cash'] is None or n['cash'] is None:
                    continue
                exp = d['cash'] + sum(d['rev'].values()) - sum(d['spend'].values()) - d['wages'] - d['land']
                if abs(exp - n['cash']) > 1e-6:
                    problems.append(f'{ep} {nm}: day {di} cash chain {exp} vs {n["cash"]}')
                    break
            side[nm] = (S, w, ld)
        (SL, WL, LL), (SO, WO, LO) = side['L'], side['O']
        per, A = {}, Counter()
        tot = Counter()
        for p in PRODUCTS:
            qL, qO, rL, rO = SL['sold'][p], SO['sold'][p], SL['rev'][p], SO['rev'][p]
            PL = rL / qL if qL else (rO / qO if qO else 0.0)
            PO = rO / qO if qO else PL
            if p == 'FERTILIZER':
                hL, hO = qL, qO
            else:
                hL, hO = SL['harv'][p], SO['harv'][p]
            a = (hL - hO) * PL
            c1 = -((hL - qL) - (hO - qO)) * PL
            c2 = qO * (PL - PO)
            per[p] = dict(a=a, c1=c1, c2=c2, hL=hL, hO=hO, qL=qL, qO=qO, PL=PL, PO=PO, fbL=(qL == 0 and hL > 0),
                          fbO=(qO == 0 and hO > 0))
            tot['A'] += a
            tot['C1'] += c1
            tot['C2'] += c2
            # alternative production definitions
            if p == 'FERTILIZER':
                colL = sum(v for k, v in SL['opk'].items() if k.startswith('COLLECT_FERTILIZER:'))
                colO = sum(v for k, v in SO['opk'].items() if k.startswith('COLLECT_FERTILIZER:'))
                tot['A_fert_collected'] += (colL - colO) * PL
                appL = sum(v for k, v in SL['opk'].items() if k.startswith('FERTILIZE:'))
                appO = sum(v for k, v in SO['opk'].items() if k.startswith('FERTILIZE:'))
                tot['fert_applied_x_PL'] += -(appL - appO) * PL
                tot['fert_bought_L'] += SL['bought'].get('BUY_PRODUCT:FERTILIZER', 0)
                tot['fert_bought_O'] += SO['bought'].get('BUY_PRODUCT:FERTILIZER', 0)
                per[p].update(colL=colL, colO=colO, appL=appL, appO=appO)
            if p == 'WHEAT':
                fedL = sum(v for k, v in SL['opk'].items() if k.startswith('FEED:'))
                fedO = sum(v for k, v in SO['opk'].items() if k.startswith('FEED:'))
                bL = SL['bought'].get('BUY_PRODUCT:WHEAT', 0)
                bO = SO['bought'].get('BUY_PRODUCT:WHEAT', 0)
                per[p].update(fedL=fedL, fedO=fedO, bL=bL, bO=bO)
                tot['wheat_fed_x_PL'] += -(fedL - fedO) * PL
                tot['wheat_bought_x_PL'] += (bL - bO) * PL
        spL, spO = sum(SL['spend'].values()), sum(SO['spend'].values())
        inputs = -(spL - spO)
        gap = L['final'] - O['final']
        B = WO - WL
        land = LO - LL
        resid = gap - (tot["A"] + tot["C1"] + tot["C2"] + inputs + B + land)
        # C2 identity: sum over products of (rL - rO) must equal A + C1 + C2
        rev_gap = sum(SL['rev'].values()) - sum(SO['rev'].values())
        rows.append(dict(ep=ep, team=team, four=is4, gap=gap, A=tot['A'], inputs=inputs, B=B, land=land, C1=tot['C1'],
                         C2=tot['C2'], resid=resid, rev_gap=rev_gap, landL=LL, landO=LO, per=per, tot=dict(tot),
                         spL=dict(SL['spend']), spO=dict(SO['spend']), finL=L['final'], finO=O['final'],
                         oppL=L['opp_final'], oppO=O['opp_final']))

    # --- local copy cross-check (all shared day fields + finals)
    shared_mismatch, shared_n = [], 0
    for ep in eps:
        for s in ('leader', 'ours'):
            a = json.load(open(E1 / f'{s}_{ep}.json'))
            b = json.load(open(LOC / f'{s}_{ep}.json'))
            for k in ('final', 'opp_final', 'target', 'seat'):
                if a[k] != b[k]:
                    shared_mismatch.append((s, ep, k))
            for di in range(30):
                for k, v in a['days'][di].items():
                    shared_n += 1
                    if b['days'][di].get(k, '<missing>') != v:
                        shared_mismatch.append((s, ep, di, k))

    print('verify_top.py: E1 ledger', E1.relative_to(ROOT))
    print(f'games {len(rows)}; reproduction / cash problems: {len(problems)}')
    for p in problems:
        print('  PROBLEM', p)
    print(f'local results/fresh/lead_ledger vs E1: {shared_n} shared day-fields compared, {len(shared_mismatch)} mismatches',
          shared_mismatch[:5])
    print('land spend per game (leader == ours in every game?):',
          all(r['landL'] == r['landO'] for r in rows), sorted({(r['landL'], r['landO']) for r in rows}))
    print('four-quadrant games:', [r['ep'] for r in rows if r['four']])
    fb = [(r['ep'], p) for r in rows for p, v in r['per'].items() if v['fbL'] or v['fbO']]
    print('price fall-backs used where a side harvested but sold none (ep, product):', fb)
    for lab, sel in (('all 12', rows), ('four-quadrant 8', [r for r in rows if r['four']]),
                     ('three-quadrant 4', [r for r in rows if not r['four']])):
        print(f'\n== {lab} (n={len(sel)}), positive = leader ahead')
        for k in ('gap', 'A', 'inputs', 'B', 'land', 'C1', 'C2', 'resid'):
            print(f'  {k:8s} {ci([r[k] for r in sel])}')
        print('  max |resid| per game: %.2e' % max(abs(r['resid']) for r in sel))
        print('  rev_gap == A+C1+C2 in every game:',
              all(abs(r['rev_gap'] - (r['A'] + r['C1'] + r['C2'])) < 1e-6 for r in sel))
        for k in ('A_fert_collected', 'fert_applied_x_PL', 'wheat_fed_x_PL', 'wheat_bought_x_PL'):
            print(f'  memo {k:20s} {ci([r["tot"].get(k, 0.0) for r in sel])}')
        # per product
        print('  product      A        C1       C2     | harv L/O      sold L/O     P_L/P_O')
        for p in PRODUCTS:
            g = len(sel)
            m = lambda k: sum(r['per'][p][k] for r in sel) / g
            print(f'  {p:11s} {m("a"):+8,.0f} {m("c1"):+8,.0f} {m("c2"):+8,.0f} | {m("hL"):6.1f}/{m("hO"):6.1f} '
                  f'{m("qL"):6.1f}/{m("qO"):6.1f} {m("PL"):6.1f}/{m("PO"):6.1f}')
        g = len(sel)
        w = lambda k: sum(r['per']['WHEAT'][k] for r in sel) / g
        f = lambda k: sum(r['per']['FERTILIZER'][k] for r in sel) / g
        print(f'  wheat units L/O: fed {w("fedL"):.1f}/{w("fedO"):.1f}, bought {w("bL"):.1f}/{w("bO"):.1f}, '
              f'harvested {w("hL"):.1f}/{w("hO"):.1f}, sold {w("qL"):.1f}/{w("qO"):.1f}')
        print(f'  fertilizer units L/O: collected {f("colL"):.1f}/{f("colO"):.1f}, applied {f("appL"):.1f}/{f("appO"):.1f}, '
              f'sold {f("qL"):.1f}/{f("qO"):.1f}')
        cats = Counter()
        for r in sel:
            for k, v in r['spL'].items():
                cats[k.split(':')[0] + ':' + (k.split(':')[1] if k.startswith('BUY_PRODUCT') else '*')] += v / g
            for k, v in r['spO'].items():
                cats[k.split(':')[0] + ':' + (k.split(':')[1] if k.startswith('BUY_PRODUCT') else '*')] -= v / g
        print('  spend leader - ours:', {k: round(v) for k, v in sorted(cats.items())})
    print('\nper game: ep 4Q gap A inputs B C1 C2 resid | finals L/O | opponent final (leader replay / vs ours)')
    for r in rows:
        print(f"  {r['ep']} {'y' if r['four'] else 'n'} {r['gap']:+8,.0f} {r['A']:+8,.0f} {r['inputs']:+7,.0f} "
              f"{r['B']:+5,.0f} {r['C1']:+7,.0f} {r['C2']:+8,.0f} {r['resid']:+.1e} | {r['finL']:,.0f}/{r['finO']:,.0f} "
              f"| {r['oppL']:,.0f}/{r['oppO']:,.0f}")
    out = Path(__file__).with_name('verify_top.json')
    out.write_text(json.dumps(rows, indent=1, default=str), encoding='utf-8')


if __name__ == '__main__':
    main()
