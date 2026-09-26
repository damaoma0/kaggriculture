"""Abandonment research (2026-09-26): exact value of DROPPING one animal at the start of day d, for every animal of
ours alive at dawn of d that still produced afterwards in the recorded game, d in DAYS.

Counterfactual (one animal at a time, everything else as recorded): the animal is not fed from day d, so it escapes
on night d+1 at the latest; its units made on nights >= d (as recorded, incl. the care bank) are not produced; the
same number of OUR recorded sales of the product are removed (FIFO = the first units we sold after each of those
productions; LIFO = our last units of the season, a bracket); the rival's units are repriced exactly
(abandon_market.reprice). Saved: the wheat it was fed on days >= d (dawn quote). Lost: its fertilizer collections on
days >= d+2 (dawn quote). Positive d_margin = dropping was better for margin.

Online features at dawn of d (everything an agent can observe): q0 (quote), excess (inventory - I0), demand/day
(shops + town centre), rival_rate and our_rate (units sold a day over the previous 3 days), herd (our live animals of
the kind), rival_herd, shed (our stock of the product at dawn), wheat, fert quotes, days_left.
usage: abandon_drop.py <side,...> <panel> -> results/fresh/abandon_20260926/drop.json
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402
import abandon_market as AM  # noqa: E402

E = UE.engine()
PROD = AM.PROD
PI = AM.PI
DAYS = (14, 17, 20, 23, 26)
OUT = AM.OUT


def demand(tape, d, item):
    sh = list(tape['shops'][:min(8, d // 3)])
    return sum((12 if len(E.SHOPS[s]) == 1 else 6) for s in sh if item in E.SHOPS[s]) + 1


def drop_rows(side, ep, tape):
    R = json.loads((AM.RDIR / side / f'{ep}.json').read_text(encoding='utf-8'))
    S = {it: AM.sells(R, it) for it in ('MILK', 'WOOL', 'EGG')}
    ours = {it: [u for u in S[it] if u[1] == 0] for it in S}
    sold_day = defaultdict(int)
    for u in R['trades']:
        if u[2] == 'SELL':
            sold_day[(u[1], u[3], u[0] // 24)] += 1
    herd = defaultdict(int)
    for k, a in R['animals'].items():
        who, x, y, pd, kind = k.split(',')
        for dw in a['dawn']:
            herd[(int(who), kind, dw[0])] += 1
    out = []
    for k, a in R['animals'].items():
        who, x, y, pd, kind = k.split(',')
        if who != '0':
            continue
        item = PROD[kind]
        dawn_days = {dw[0] for dw in a['dawn']}
        for d in DAYS:
            if d not in dawn_days:
                continue
            made = [(n[0], n[6]) for n in a['nights'] if n[0] >= d and n[6] > 0]
            if not made:
                continue
            fed = [n[0] for n in a['nights'] if n[0] >= d and n[1]]
            wheat = sum(AM.price('WHEAT', R['inv'][dd * 24][PI['WHEAT']]) for dd in fed)
            coll = [s for s, c, u in a['acts'] if c == 'COLLECT_FERTILIZER' and s // 24 >= d + 2]
            fert = sum(AM.price('FERTILIZER', R['inv'][min(718, (s // 24) * 24)][PI['FERTILIZER']]) for s in coll)
            units = sum(u for _, u in made)
            res = {}
            for mode in ('fifo', 'lifo'):
                rem = []
                if mode == 'fifo':
                    used = set()
                    for n, u in made:
                        c = [x for x in ours[item] if x[0] >= (n + 1) * 24 and x[4] not in used][:u]
                        for x in c:
                            used.add(x[4])
                        rem += [x[4] for x in c]
                else:
                    rem = [x[4] for x in ours[item][-units:]] if units else []
                do, dr = AM.reprice(R, item, removes=rem, S=S[item])
                res[mode] = (round(do), round(dr), len(rem))
            inv = R['inv'][d * 24][PI[item]]
            f = dict(side=side, ep=ep, kind=kind, key=k, d=d, units=units, wheat=round(wheat), fert=round(fert),
                     acts=sum(1 for s, c, u in a['acts'] if s // 24 >= d),
                     q0=AM.price(item, inv), excess=inv - 10000, demand=demand(tape, d, item),
                     rival_rate=round(sum(sold_day[(1, item, dd)] for dd in (d - 1, d - 2, d - 3)) / 3, 2),
                     our_rate=round(sum(sold_day[(0, item, dd)] for dd in (d - 1, d - 2, d - 3)) / 3, 2),
                     herd=herd[(0, kind, d)], rival_herd=herd[(1, kind, d)],
                     wheat_q=AM.price('WHEAT', R['inv'][d * 24][PI['WHEAT']]),
                     fert_q=AM.price('FERTILIZER', R['inv'][d * 24][PI['FERTILIZER']]), days_left=29 - d)
            for mode, (do, dr, nrem) in res.items():
                f[f'd_own_{mode}'] = do + f['wheat'] - f['fert']
                f[f'd_rival_{mode}'] = dr
                f[f'd_margin_{mode}'] = do + f['wheat'] - f['fert'] - dr
                f[f'removed_{mode}'] = nrem
            out.append(f)
    return out


def main():
    sides = sys.argv[1].split(',')
    games = Path(sys.argv[2]).read_text().replace(',', ' ').split()
    rows = []
    for g in games:
        team, ep = g.split(':')
        tape = UE.load_tape(int(team), int(ep))
        for side in sides:
            rows += drop_rows(side, ep, tape)
    (OUT / 'drop.json').write_text(json.dumps(rows), encoding='utf-8')
    print(len(rows), 'animal-decisions')


if __name__ == '__main__':
    main()
