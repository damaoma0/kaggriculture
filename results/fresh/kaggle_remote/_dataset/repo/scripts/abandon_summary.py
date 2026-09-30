"""Abandonment research (2026-09-26): the smaller tables of docs/abandonment_research_20260926.md, recomputed from
results/fresh/abandon_20260926/ (replay/, animals.json, keep.json). Prints:
  1. animals bought too late to ever produce (cow >= day 22, sheep >= 24, goose >= 26), coins per world
  2. service level: fed / fed+cared rate, units per production, shortfall vs full care
  3. care the module planned vs care done on fed days, by dawn quote (quote < 40 / >= 40)
  4. stop decisions: stop day, productions lost, dawn quote / wheat, animals per stop event (DSM vs our arms)
  5. keeping k of an abandoned cow group (exact margin, full / fed-only) for the worked-example worlds
  6. DSM's purchase days (its recorded orders)
usage: abandon_summary.py [panel]"""
import json
import sys
from collections import Counter
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402
import abandon_market as AM  # noqa: E402
import abandon_animals as AA  # noqa: E402

PANEL = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt'
G = PANEL.read_text().replace(',', ' ').split()
N = len(G)
SIDES = ['LEADER', 'KS1', 'KC8', 'KE7', 'KB1']
IV = {'COW': 2, 'SHEEP': 3, 'GOOSE': 1}
LATE = {'COW': 22, 'SHEEP': 24, 'GOOSE': 26}


def rep(side, ep):
    return json.loads((AM.RDIR / side / f'{ep}.json').read_text(encoding='utf-8'))


def main():
    rows = json.loads((AM.OUT / 'animals.json').read_text(encoding='utf-8'))
    print('1. animals bought too late to ever produce')
    for side in SIDES:
        cost, C, worlds = 0, Counter(), Counter()
        for g in G:
            ep = g.split(':')[1]
            for st, who, op, item, price, inv0 in rep(side, ep)['trades']:
                if who == 0 and op == 'BUY_ANIMAL' and st // 24 >= LATE[item]:
                    cost += price
                    C[item] += 1
                    worlds[ep] += price
        print(f'   {side:6s} {cost / N:6.0f} coins/world, units {dict(C)}, worlds {len(worlds)}, max {max(worlds.values()) if worlds else 0}')
    print('2. service level (days 11-28, our animals)')
    for side in SIDES:
        C = Counter()
        for g in G:
            for k, a in rep(side, g.split(':')[1])['animals'].items():
                w, x, y, pd, kd = k.split(',')
                if w != '0':
                    continue
                for d, fed, cared, bank, yb, prod, made, esc in a['nights']:
                    if d < 11 or esc:
                        continue
                    C[(kd, 'days')] += 1
                    C[(kd, 'fed')] += fed
                    C[(kd, 'fc')] += fed and cared
                    if prod:
                        C[(kd, 'prods')] += 1
                        C[(kd, 'made')] += made
                        C[(kd, 'full')] += 1 + IV[kd]
        print(f'   {side:6s} ' + ' | '.join(
            f"{kd}: fed {C[(kd, 'fed')] / max(1, C[(kd, 'days')]):.0%} fed+cared {C[(kd, 'fc')] / max(1, C[(kd, 'days')]):.0%} "
            f"units/prod {C[(kd, 'made')] / max(1, C[(kd, 'prods')]):.2f}/{1 + IV[kd]} short {(C[(kd, 'full')] - C[(kd, 'made')]) / N:.0f}"
            for kd in ('COW', 'SHEEP', 'GOOSE')))
    print('3. module plan vs care done on fed days (days 12-27)')
    S = AA.sm()
    for side in ('KS1', 'KC8'):
        C = Counter()
        for g in G:
            R = rep(side, g.split(':')[1])
            for k, a in R['animals'].items():
                w, x, y, pd, kd = k.split(',')
                if w != '0':
                    continue
                pd = int(pd)
                dm = {dw[0]: dw for dw in a['dawn']}
                item = AM.PROD[kd]
                for d, fed, cared, bank, yb, prod, made, esc in a['nights']:
                    if d < 12 or d > 27 or not fed or d not in dm:
                        continue
                    dw, t = dm[d], d * 24
                    pr = AM.price(item, R['inv'][t][AM.PI[item]])
                    p = S['sm_tile_plan'](kd, (pd, dw[1], dw[2], dw[3], False, False), d, 0, pr,
                                          AM.price('WHEAT', R['inv'][t][AM.PI['WHEAT']]), False, 8, 0.0,
                                          collect_price=AM.price('FERTILIZER', R['inv'][t][AM.PI['FERTILIZER']]), avail=bool(dw[4]))
                    if p['combo'] is None:
                        continue
                    C[(kd, pr < 40, bool(p['combo'][1]), bool(cared))] += 1
        for kd in ('COW', 'SHEEP', 'GOOSE'):
            for lo in (True, False):
                a_, b_ = C[(kd, lo, True, True)], C[(kd, lo, True, False)]
                c_ = C[(kd, lo, False, True)] + C[(kd, lo, False, False)]
                tot = a_ + b_ + c_
                if tot:
                    print(f"   {side} {kd:5s} quote {'<40 ' if lo else '>=40'} fed days {tot / N:5.1f}/world | planned+done {a_ / tot:.0%}"
                          f" | planned, skipped {b_ / tot:.0%} | not planned {c_ / tot:.0%}")
    print('4. stop decisions (mid-season abandonments, escape night >= 12)')
    for side in ('LEADER', 'KS1', 'KC8'):
        for kind in ('COW', 'SHEEP', 'GOOSE'):
            m = [r for r in rows if r['side'] == side and r['who'] == 0 and r['cls'] == 'mid' and r['escape'] >= 12 and r['kind'] == kind]
            if not m:
                continue
            b = Counter((r['ep'], r['stop']) for r in m)
            print(f"   {side:6s} {kind:5s} {len(m) / N:.2f}/world in {len(set(r['ep'] for r in m))} worlds | stop day median {median(r['stop'] for r in m)}"
                  f" | productions lost median {median(r['lost_nights'] for r in m)} | quote/wheat median {median(r['q_prod'] / r['q_wheat'] for r in m):.2f}"
                  f" | animals per stop event {mean(b.values()):.1f}")
    print('5. keep k of an abandoned cow group (exact margin, full care / fed only)')
    for side, ep in (('KC8', '112592389'), ('KC8', '112591190'), ('KS1', '112591190'), ('LEADER', '112592389')):
        R = rep(side, ep)
        grp = sorted([r for r in rows if r['side'] == side and r['ep'] == ep and r['who'] == 0 and r['cls'] == 'mid'
                      and r['escape'] >= 12 and r['kind'] == 'COW'], key=lambda r: (r['stop'], r['x'], r['y']))
        cur = ' '.join(f"{k}:{AM.keep_counterfactual(R, grp[:k], 'full')['margin']:+d}/{AM.keep_counterfactual(R, grp[:k], 'fed_only')['margin']:+d}"
                       for k in range(1, len(grp) + 1))
        print(f'   {side} {ep} ({len(grp)} cows): {cur}')
    print("6. DSM's recorded BUY_ANIMAL orders by day (units, 40 worlds)")
    C = Counter()
    for g in G:
        team, ep = g.split(':')
        for t, a in enumerate(UE.load_tape(int(team), int(ep))['actions']):
            if isinstance(a, dict):
                for o in a.get('market', []) or []:
                    if o and o[0] == 'BUY_ANIMAL':
                        C[(o[1], t // 24)] += int(o[2])
    for kd in ('COW', 'SHEEP', 'GOOSE'):
        print(f'   {kd:5s}', {d: C[(kd, d)] for d in range(30) if C[(kd, d)]})


if __name__ == '__main__':
    main()
