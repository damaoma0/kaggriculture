"""Abandonment research (2026-09-26): herd-level stop rule versus the maintenance module's all-or-nothing verdicts.

The module judges every animal of a kind with the same dawn quote, so a herd is abandoned (or kept) as a block. With a
shared market the value of the n-th animal falls with n. Closed form (price linear in inventory near the current
level, slope s): margin over the remaining T days, M(H) = integral of p(t) (H u - r) dt - c H T with
p(t) = p(I_d + (H u + r - D) t); dM/dH >= 0  <=>  u [pbar(H) + s (r - H u) T / 2] >= c, where
  u = units a day per animal at full care (cow 1.5, sheep 4/3, goose 2), r = rival sales a day (last 3 days, from
  inventory accounting), D = demand a day (open shops + town centre), T = 28 - d + 1, pbar(H) = price at
  I_d + (H u + r - D) T / 2 (the floor stops accumulation), s = price drop per unit there, c = wheat quote - 0.5 x
  fertilizer quote (fertilizer is collected about half the time).
H* = the largest H satisfying the condition (at least the animals that satisfy it one by one).

Evaluated on every group of animals an arm abandoned mid-season (animals.json 'mid', escape >= 12, per kind): keep
k = max(0, H* - (live herd at dawn of the first stop day - group size)) of them (earliest stop first), full care,
exact repricing (abandon_market.keep_counterfactual), versus k = 0 (the arm as played), keep all, and the best k.
Also scored on the herds the arm KEPT at dawn of d = 17 / 20 / 23: the formula's surplus H - H* dropped (animals
with the fewest remaining units first; abandon_dsmcut-style FIFO removal), exact; this checks false alarms.
usage: abandon_herd.py <arm,...> <panel>"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402
import abandon_market as AM  # noqa: E402

PI = AM.PI
U = {'COW': 1.5, 'SHEEP': 4 / 3, 'GOOSE': 2.0}


def slope(item, inv):
    return max(0, AM.price(item, inv) - AM.price(item, inv + 1))


def demand(tape, d, item):
    sh = list(tape['shops'][:min(8, d // 3)])
    return sum((12 if len(AM.E.SHOPS[s]) == 1 else 6) for s in sh if item in AM.E.SHOPS[s]) + 1


def rates(R, item, d):
    c = defaultdict(int)
    for t in R['trades']:
        if t[2] == 'SELL' and t[3] == item and d - 3 <= t[0] // 24 < d:
            c[t[1]] += 1
    return c[0] / 3, c[1] / 3


def h_star(R, tape, kind, d, hmax):
    item = AM.PROD[kind]
    inv = R['inv'][d * 24][PI[item]]
    _, r = rates(R, item, d)
    D = demand(tape, d, item)
    T = max(1, 29 - d)
    u = U[kind]
    c = AM.price('WHEAT', R['inv'][d * 24][PI['WHEAT']]) - 0.5 * AM.price('FERTILIZER', R['inv'][d * 24][PI['FERTILIZER']])
    best = 0
    for H in range(1, hmax + 1):
        mid = inv + (H * u + r - D) * T / 2
        floor_inv = next((i for i in range(int(inv), int(inv) + 400) if AM.price(item, i) <= 1), None)
        if floor_inv is not None and mid > floor_inv:
            mid = floor_inv
        v = AM.price(item, mid) + slope(item, mid) * (r - H * u) * T / 2
        if u * v >= c:
            best = H
        else:
            break
    return best


def main():
    arms = sys.argv[1].split(',')
    games = Path(sys.argv[2]).read_text().replace(',', ' ').split()
    rows = json.loads((AM.OUT / 'animals.json').read_text(encoding='utf-8'))
    tapes = {}
    for arm in arms:
        A = defaultdict(float)
        B = defaultdict(float)
        for g in games:
            team, ep = g.split(':')
            tape = tapes.get(ep) or UE.load_tape(int(team), int(ep))
            tapes[ep] = tape
            R = json.loads((AM.RDIR / arm / f'{ep}.json').read_text(encoding='utf-8'))
            live = defaultdict(int)
            for k, a in R['animals'].items():
                w, x, y, pd, kd = k.split(',')
                if w == '0':
                    for dw in a['dawn']:
                        live[(kd, dw[0])] += 1
            # (1) the arm's abandonment groups
            for kind in ('COW', 'SHEEP', 'GOOSE'):
                grp = sorted([r for r in rows if r['side'] == arm and r['ep'] == ep and r['who'] == 0 and r['cls'] == 'mid'
                              and r['escape'] >= 12 and r['kind'] == kind], key=lambda r: (r['stop'], r['x'], r['y']))
                if not grp:
                    continue
                s0 = grp[0]['stop']
                H_live = live[(kind, s0)]
                hs = h_star(R, tape, kind, s0, H_live)
                k_rule = max(0, min(len(grp), hs - (H_live - len(grp))))
                curve = [0] + [AM.keep_counterfactual(R, grp[:k], 'full')['margin'] for k in range(1, len(grp) + 1)]
                A['groups'] += 1
                A['animals'] += len(grp)
                A['rule'] += curve[k_rule]
                A['all'] += curve[-1]
                A['best'] += max(curve)
                A['k_rule'] += k_rule
                A['k_best'] += curve.index(max(curve))
            # (2) false alarms on kept herds
            for d in (17, 20, 23):
                for kind in ('COW', 'SHEEP', 'GOOSE'):
                    item = AM.PROD[kind]
                    cand = []
                    for k, a in R['animals'].items():
                        w, x, y, pd, kd = k.split(',')
                        if w != '0' or kd != kind or d not in {dw[0] for dw in a['dawn']}:
                            continue
                        made = [(nn[0], nn[6]) for nn in a['nights'] if nn[0] >= d and nn[6] > 0]
                        if made:
                            cand.append((sum(u for _, u in made), k, made, a))
                    if not cand:
                        continue
                    hs = h_star(R, tape, kind, d, len(cand))
                    surplus = len(cand) - hs
                    B['herds'] += 1
                    if surplus <= 0:
                        continue
                    B['trims'] += 1
                    B['dropped'] += surplus
                    ours = [u for u in AM.sells(R, item) if u[1] == 0]
                    used, rem = set(), []
                    wheat = fert = 0.0
                    for tot, k, made, a in sorted(cand)[:surplus]:
                        for nn, u in made:
                            c = [x for x in ours if x[0] >= (nn + 1) * 24 and x[4] not in used][:u]
                            for x in c:
                                used.add(x[4])
                                rem.append(x[4])
                        wheat += sum(AM.price('WHEAT', R['inv'][nn[0] * 24][PI['WHEAT']]) for nn in a['nights'] if nn[0] >= d and nn[1])
                        fert += sum(AM.price('FERTILIZER', R['inv'][min(718, (st // 24) * 24)][PI['FERTILIZER']])
                                    for st, c_, u_ in a['acts'] if c_ == 'COLLECT_FERTILIZER' and st // 24 >= d + 2)
                    do, dr = AM.reprice(R, item, removes=rem)
                    B['margin'] += do + wheat - fert - dr
                    B['own'] += do + wheat - fert
                    B['pos'] += (do + wheat - fert - dr) > 0
        n = len(games)
        print(f"{arm:5s} abandonment groups {A['groups'] / n:.2f}/world ({A['animals'] / n:.2f} animals): margin vs as played: "
              f"herd rule {A['rule'] / n:+.0f} (keeps {A['k_rule'] / n:.2f}/world) | keep all {A['all'] / n:+.0f} | best k {A['best'] / n:+.0f} (keeps {A['k_best'] / n:.2f})")
        print(f"      kept herds d17/20/23: {B['herds'] / n:.1f}/world, rule trims {B['trims'] / n:.2f} ({B['dropped'] / n:.2f} animals): "
              f"margin {B['margin'] / n:+.0f} own {B['own'] / n:+.0f} per world; trims with margin > 0: {B['pos']:.0f} of {B['trims']:.0f}")


if __name__ == '__main__':
    main()
