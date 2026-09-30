"""Abandonment research (2026-09-26): exact market economics of one more / one fewer unit of an animal product, and
of keeping the animals we (or DSM) abandoned, from the replays of scripts/abandon_replay.py.

Why exact: the shared market price is a pure function of the product inventory; shops and the town centre consume a
FIXED number of units every 4 / 24 steps whatever the price, and every SELL at a price > 1 adds 1 unit for the rest
of the season. The rival replays recorded actions, so its quantities and sale steps are fixed; only its prices move.
Inserting k extra units of ours at step s therefore shifts the inventory of every later unit (ours and the rival's)
by the number of extra units sold above the floor, and each later unit is repriced with market_price(inv0 + shift)
(sequentially, so a unit that falls to / rises from the $1 floor stops / starts adding inventory).

reprice(R, item, adds, removes) -> (d_own, d_rival): adds = [(step, n)] extra units of ours sold at the start of that
step's market; removes = [(trade index)] our own recorded units that are no longer sold.

Outputs (results/fresh/abandon_20260926/):
  marginal.json: per side / ep / item / day d: the value of ONE extra unit available at dawn of day d
      own_end  (sold at step 718 after every other unit: no later unit of ours pays for it),
      own_best / margin_best (best sale step in [24d, 718] for own cash / for margin = own - rival),
      own_same / margin_same (sold at hour 12 of day d), q0 (dawn quote)
  keep.json: per side / ep: the abandoned animals ('mid' rows of animals.json, escapes on nights >= 12) kept alive to
      the end, full care (fed + cared every day, 1 + interval units a production, sold the morning after each
      production at hour 8) or fed only (feed every other day, 1 unit a production): extra units, own revenue change
      (the extra units' revenue minus what our other units lose), rival revenue change, wheat cost at the dawn quote,
      fertilizer (1 a day alive, at the dawn quote), extra unit-actions; own and margin totals.
usage: abandon_market.py <side,...> <panel>
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
AN = E.ANIMALS
P = E.PRODUCTS
PI = {p: i for i, p in enumerate(P)}
PROD = {'COW': 'MILK', 'SHEEP': 'WOOL', 'GOOSE': 'EGG'}
RDIR = ROOT / 'results/fresh/abandon_20260926/replay'
OUT = ROOT / 'results/fresh/abandon_20260926'
LAST = 718


def price(item, inv):
    return E.market_price(item, inv)


def sells(R, item):
    """our and the rival's SELL units of item, in engine order: [step, who, price, quote inventory, idx].
    In a lockstep round both players are quoted at the same pre-commit inventory, so the second seller's recorded
    inventory (taken just before its own commit) is one above its quote inventory: recover it from the price."""
    out = []
    for i, t in enumerate(R['trades']):
        if t[2] != 'SELL' or t[3] != item:
            continue
        inv = t[5]
        if price(item, inv) != t[4] and price(item, inv - 1) == t[4]:
            inv -= 1
        out.append([t[0], t[1], t[4], inv, i])
    return out


def reprice(R, item, adds=(), removes=(), S=None):
    S = sells(R, item) if S is None else S
    adds = sorted(adds)
    rem = set(removes)
    d_own = d_riv = 0.0
    shift = 0
    ai = 0
    for st, who, p0, inv0, idx in S + [[10 ** 6, -1, 0, 0, -1]]:
        while ai < len(adds) and adds[ai][0] <= st:
            s_, n_ = adds[ai]
            base = R['inv'][min(s_, LAST)][PI[item]]
            # units of this step already sold before our insertion point are not counted: insert first in the step
            for _ in range(n_):
                p = price(item, base + shift)
                d_own += p
                if p > 1:
                    shift += 1
            ai += 1
        if who < 0:
            break
        if idx in rem:
            d_own -= p0
            if p0 > 1:
                shift -= 1
            continue
        if shift == 0:
            continue
        p1 = price(item, inv0 + shift)
        if who == 0:
            d_own += p1 - p0
        else:
            d_riv += p1 - p0
        if p0 > 1 and p1 <= 1:
            shift -= 1
        elif p0 <= 1 and p1 > 1:
            shift += 1
    return d_own, d_riv


def marginal_tables(R, items=('MILK', 'WOOL', 'EGG'), days=range(11, 30)):
    out = {}
    for item in items:
        S = sells(R, item)
        # value of one extra unit sold at step s (inserted first in the step): exact via reprice
        cache = {}

        def val(s):
            if s not in cache:
                cache[s] = reprice(R, item, [(s, 1)], S=S)
            return cache[s]
        # candidate sale steps: every 4th step (demand ticks) plus the last step
        cand = list(range(11 * 24, LAST, 4)) + [LAST]
        vals = {s: val(s) for s in cand}
        # "after every other unit" at 718: price at the final inventory
        inv_end = R['inv'][LAST][PI[item]]
        for st, who, p0, inv0, idx in S:
            if st == LAST:
                inv_end = inv0 + (1 if p0 > 1 else 0)
        rows = {}
        for d in days:
            lo = d * 24
            cs = [s for s in cand if s >= lo]
            ob = max(cs, key=lambda s: vals[s][0])
            mb = max(cs, key=lambda s: vals[s][0] - vals[s][1])
            s12 = min(cs, key=lambda s: abs(s - (lo + 12)))
            rows[d] = dict(q0=price(item, R['inv'][lo][PI[item]]), own_end=price(item, inv_end),
                           own_best=round(vals[ob][0], 1), own_best_step=ob,
                           margin_best=round(vals[mb][0] - vals[mb][1], 1), margin_best_step=mb,
                           own_same=round(vals[s12][0], 1), margin_same=round(vals[s12][0] - vals[s12][1], 1))
        out[item] = rows
    return out


def prod_nights(kind, placed):
    a = AN[kind]
    return [n for n in range(placed, 29) if (n + 1 - placed - a['first_yield_day']) >= 0
            and (n + 1 - placed - a['first_yield_day']) % a['interval'] == 0]


def keep_counterfactual(R, rows, mode='full', sale_hour=8, min_escape=12):
    """rows: this side/ep's 'mid' animals (ours). -> dict of totals"""
    adds = defaultdict(list)
    wheat = fert = 0.0
    acts = 0
    units = defaultdict(int)
    n_an = 0
    for r in rows:
        if r['cls'] != 'mid' or r['who'] != 0 or r['escape'] < min_escape:
            continue
        n_an += 1
        kind, item = r['kind'], PROD[r['kind']]
        iv = AN[kind]['interval']
        s, e = r['stop'], r['escape']
        lost = [n for n in prod_nights(kind, r['placed']) if n >= e]
        for j, n in enumerate(lost):
            u = (1 + iv) if mode == 'full' else 1
            if mode == 'full' and j == 0 and r['bank_lost_stop']:
                u += r['bank_lost_stop']
            step = min(LAST, (n + 1) * 24 + sale_hour)
            adds[item].append((step, u))
            units[item] += u
        feed_days = list(range(s, 29)) if mode == 'full' else list(range(s, 29, 2))
        for d in feed_days:
            wheat += price('WHEAT', R['inv'][d * 24][PI['WHEAT']])
        for d in range(e + 1, 30):
            fert += price('FERTILIZER', R['inv'][min(LAST, d * 24)][PI['FERTILIZER']])
        acts += len(feed_days) * (2 if mode == 'full' else 1) + len(lost) + (30 - e - 1)
    res = dict(n_animals=n_an, units=dict(units), wheat=round(wheat), fert=round(fert), actions=acts)
    d_own = d_riv = 0.0
    per = {}
    for item, a in adds.items():
        o, v = reprice(R, item, a)
        per[item] = [round(o), round(v)]
        d_own += o
        d_riv += v
    res.update(per_item=per, d_own_sales=round(d_own), d_rival=round(d_riv),
               own=round(d_own - wheat + fert), margin=round(d_own - wheat + fert - d_riv))
    return res


def main():
    sides = sys.argv[1].split(',')
    games = Path(sys.argv[2]).read_text().replace(',', ' ').split()
    rows = json.loads((OUT / 'animals.json').read_text(encoding='utf-8'))
    by = defaultdict(list)
    for r in rows:
        by[(r['side'], r['ep'])].append(r)
    marg, keep = {}, {}
    for side in sides:
        marg[side], keep[side] = {}, {}
        for g in games:
            ep = g.split(':')[1]
            R = json.loads((RDIR / side / f'{ep}.json').read_text(encoding='utf-8'))
            marg[side][ep] = marginal_tables(R)
            keep[side][ep] = {m: keep_counterfactual(R, by[(side, ep)], m) for m in ('full', 'fed_only')}
        print(side, 'done', flush=True)
    (OUT / 'marginal.json').write_text(json.dumps(marg), encoding='utf-8')
    (OUT / 'keep.json').write_text(json.dumps(keep), encoding='utf-8')
    n = len(games)
    for side in sides:
        for m in ('full', 'fed_only'):
            K = [keep[side][g.split(':')[1]][m] for g in games]
            tot = lambda k: sum(x[k] for x in K) / n
            print(f"{side:6s} keep-abandoned {m:8s}: animals {tot('n_animals'):.2f} | own sales {tot('d_own_sales'):+.0f} "
                  f"wheat {-tot('wheat'):+.0f} fert {tot('fert'):+.0f} | own {tot('own'):+.0f} | rival {tot('d_rival'):+.0f} | "
                  f"margin {tot('margin'):+.0f} | actions {tot('actions'):.0f}  (per world)")


if __name__ == '__main__':
    main()
