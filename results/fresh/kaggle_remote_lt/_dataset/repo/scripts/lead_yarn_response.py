"""Sheep / wool response to the first Yarn Store reveal, from stored records only (no games).

usage: lead_yarn_response.py [agent=mgt_lpv_tw0] [ref=mgt_y3_cal]
A. p2750 panel (185 worlds): sheep bought (spend / 500), wool units sold, wool revenue by day relative to the first
   Yarn Store reveal (from the cumulative revenue_daily), ours vs y3, grouped by the reveal day.
B. G1 worlds (results/fresh/lead_ledger: the leader's own replay, our leader-plan agent, the deploy of the ledger
   round): sheep on the board by day and wool sold by day around the reveal.
"""
import gzip
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / 'results/fresh/ladder_panel'


def first_yarn(by_day):
    flat = list(by_day[-1]) if by_day else []
    for i, s in enumerate(flat):
        if s == 'YARN_STORE':
            return next(d for d, lst in enumerate(by_day) if len(lst) > i)
    return None


def wool_rev(daily, a, b):
    def tot(i):
        if i < 0:
            return 0.0
        return float(daily[min(i, len(daily) - 1)].get('WOOL', 0))
    return tot(b) - tot(a - 1)


def part_a(agent, ref):
    eps = sorted(f.stem for f in (P / agent).glob('*.json') if (P / ref / f.name).exists())
    grp = defaultdict(list)
    for e in eps:
        A = json.load(open(P / agent / f'{e}.json'))
        B = json.load(open(P / ref / f'{e}.json'))
        if abs(A.get('opp_dead', 0) - B.get('opp_dead', 0)) > 40:
            continue
        by_day = json.load(gzip.open(ROOT / f'data/ladder_panel/p2750/{e}.json.gz', 'rt', encoding='utf-8'))['shops']
        y = first_yarn(by_day)
        key = 'none' if y is None else 'by day 12' if y <= 12 else 'after day 12'
        row = {}
        for tag, R in (('ours', A), ('y3', B)):
            row[tag + '_sheep'] = R['spend'].get('BUY_ANIMAL:SHEEP', 0) / 500.0
            row[tag + '_wool'] = R['sold'].get('WOOL', 0)
            if y is not None:
                row[tag + '_w0_5'] = wool_rev(R['revenue_daily'], y, y + 5)
                row[tag + '_w6_29'] = wool_rev(R['revenue_daily'], y + 6, 29)
            row[tag + '_margin'] = R['margin']
        grp[key].append(row)
    print('A. p2750 panel, clean worlds (rival tape intact against both builds), by first Yarn Store reveal:')
    print('| first Yarn reveal | worlds | sheep bought ours / y3 | wool sold ours / y3 | wool revenue reveal..+5 ours / y3 | wool revenue +6..end ours / y3 | margin gap |')
    print('|---|---|---|---|---|---|---|')
    for key in ('by day 12', 'after day 12', 'none'):
        rows = grp[key]
        if not rows:
            continue
        m = lambda k: st.mean(r[k] for r in rows) if k in rows[0] else float('nan')
        print(f"| {key} | {len(rows)} | {m('ours_sheep'):.1f} / {m('y3_sheep'):.1f} | {m('ours_wool'):.0f} / {m('y3_wool'):.0f} | "
              f"{m('ours_w0_5'):,.0f} / {m('y3_w0_5'):,.0f} | {m('ours_w6_29'):,.0f} / {m('y3_w6_29'):,.0f} | "
              f"{m('ours_margin') - m('y3_margin'):+,.0f} |")


def part_b():
    import lead_g1
    rows = {}
    for f in sorted((ROOT / 'results/fresh/lead_ledger').glob('*_1*.json')):
        r = json.load(open(f))
        rows[(r['side'], r['episode'])] = r
    eps = sorted({e for s, e in rows})
    print('B. G1 worlds (ledger replays): sheep on the board (day start) and wool sold, around the first Yarn reveal')
    print('| episode | first Yarn | side | sheep d(y-3) / d(y) / d(y+3) / d(y+6) / d(y+9) | sheep bought y..y+5 | wool sold y..end |')
    print('|---|---|---|---|---|---|')
    agg = defaultdict(lambda: defaultdict(list))
    for e in eps:
        team = next(g.split(':')[0] for g in lead_g1.GAMES if g.endswith(str(e)))
        tape = json.load(gzip.open(next(lead_g1.TAPES.glob(f'{team}_*/{e}.json.gz')), 'rt', encoding='utf-8'))
        shops_flat = tape['shops']
        by_day = [list(shops_flat[:min(8, d // 3)]) for d in range(31)]
        y = first_yarn(by_day)
        if y is None:
            continue
        for side in ('leader', 'ours', 'deploy'):
            r = rows.get((side, e))
            if r is None:
                continue
            days = r['days']
            sheep = [days[min(29, max(0, y + k))]['board'].get('SHEEP', 0) for k in (-3, 0, 3, 6, 9)]
            bought = sum(days[d]['bought'].get('BUY_ANIMAL:SHEEP', 0) for d in range(y, min(30, y + 6)))
            wool = sum(days[d]['sold'].get('WOOL', 0) for d in range(y, 30))
            print(f"| {e} | {y} | {side} | {' / '.join(str(x) for x in sheep)} | {bought} | {wool} |")
            for k, v in zip((-3, 0, 3, 6, 9), sheep):
                agg[side][k].append(v)
            agg[side]['bought'].append(bought)
            agg[side]['wool'].append(wool)
    print('means: ' + '; '.join(f"{side}: sheep " + ' / '.join(f"{st.mean(agg[side][k]):.1f}" for k in (-3, 0, 3, 6, 9))
                                + f", bought {st.mean(agg[side]['bought']):.1f}, wool {st.mean(agg[side]['wool']):.0f}"
                                for side in ('leader', 'ours', 'deploy') if agg[side][0]))


def main():
    sys.path.insert(0, str(ROOT / 'scripts'))
    agent = sys.argv[1] if len(sys.argv) > 1 else 'mgt_lpv_tw0'
    ref = sys.argv[2] if len(sys.argv) > 2 else 'mgt_y3_cal'
    part_a(agent, ref)
    part_b()


if __name__ == '__main__':
    main()
