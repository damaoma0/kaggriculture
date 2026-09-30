"""Summarise the self-play gate and decompose each candidate's effect on BOTH sides.

Head-to-head margin is the acceptance criterion, but in a mirror market a change that helps us can
help the frozen opponent more: cutting supply of a glutted good raises the price for whoever still
holds units, and the benchmark holds more of them. This report therefore prints, for every candidate,
the change in our own revenue AND the change in the benchmark's revenue against the same seeds of the
null control, so a margin loss can be attributed.

Usage: python report_selfplay.py [seed_base]
"""
import json, statistics as st, sys, glob
from market_corpus import ROOT

OUT = ROOT / 'results/fresh/selfplay'
ITEMS = ['WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON', 'EGG', 'MILK', 'WOOL', 'FERTILIZER']


def load(seed_base):
    rows = {}
    for path in glob.glob(str(OUT / 'games' / '*.json')):
        row = json.loads(open(path, encoding='utf-8').read())
        if not (seed_base <= row['seed'] < seed_base + 100):
            continue
        rows.setdefault(row['candidate'], []).append(row)
    return rows


def totals(rows, side):
    key = 'ledger_candidate' if side == 'own' else 'ledger_benchmark'
    return {item: st.mean(r[key]['revenue'].get(item, 0) for r in rows) for item in ITEMS}


def main():
    seed_base = int(sys.argv[1]) if len(sys.argv) > 1 else 172000
    rows = load(seed_base)
    if 'sp_null' not in rows:
        print(f'no sp_null control on seed block {seed_base}; run the gate with sp_null to enable '
              f'the two-sided decomposition')
    print(f'seed block {seed_base}, candidates: {", ".join(sorted(rows))}')
    print(f"\n{'candidate':22s} {'W-T-L':>10s} {'win%':>6s} {'margin':>9s} {'own cash':>10s} {'bench cash':>11s}")
    for name in sorted(rows):
        rs = rows[name]
        w = sum(1 for r in rs if r['margin'] > 0)
        t = sum(1 for r in rs if r['margin'] == 0)
        l = sum(1 for r in rs if r['margin'] < 0)
        print(f'{name:22s} {f"{w}-{t}-{l}":>10s} {100.0*w/len(rs):6.1f} '
              f'{st.mean(r["margin"] for r in rs):+9.0f} {st.mean(r["cash"] for r in rs):10.0f} '
              f'{st.mean(r["bench_cash"] for r in rs):11.0f}')
    if 'sp_null' not in rows:
        return
    base_own = totals(rows['sp_null'], 'own')
    base_opp = totals(rows['sp_null'], 'opp')
    print('\nrevenue change versus the null control, by product: ours / the benchmark\'s')
    print(f"{'candidate':22s} | " + ' | '.join(f'{i[:5]:>13s}' for i in ITEMS))
    for name in sorted(rows):
        if name == 'sp_null':
            continue
        own = totals(rows[name], 'own')
        opp = totals(rows[name], 'opp')
        cells = []
        for item in ITEMS:
            cells.append(f'{own[item]-base_own[item]:+6.0f}/{opp[item]-base_opp[item]:+6.0f}')
        print(f'{name:22s} | ' + ' | '.join(f'{c:>13s}' for c in cells))
    print('\ntotal revenue change and where the margin went')
    print(f"{'candidate':22s} {'our revenue':>12s} {'bench revenue':>14s} {'our spend':>10s} "
          f"{'margin':>9s} {'note':>40s}")
    for name in sorted(rows):
        if name == 'sp_null':
            continue
        rs = rows[name]
        own_rev = sum(totals(rs, 'own').values()) - sum(base_own.values())
        opp_rev = sum(totals(rs, 'opp').values()) - sum(base_opp.values())
        own_spend = (st.mean(sum(r['ledger_candidate']['spend'].values()) for r in rs)
                     - st.mean(sum(r['ledger_candidate']['spend'].values()) for r in rows['sp_null']))
        margin = st.mean(r['margin'] for r in rs)
        note = 'benchmark gained more than us' if opp_rev > own_rev else ''
        print(f'{name:22s} {own_rev:+12.0f} {opp_rev:+14.0f} {own_spend:+10.0f} {margin:+9.0f} {note:>40s}')


if __name__ == '__main__':
    main()
