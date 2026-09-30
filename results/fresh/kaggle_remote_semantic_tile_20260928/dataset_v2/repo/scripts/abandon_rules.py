"""Abandonment research (2026-09-26): which unit value should the maintenance DP (scripts/fragments/sem_maintenance.py)
use to decide whether to keep feeding an animal?  Scored on the exact per-animal drop counterfactuals of
scripts/abandon_drop.py (ground truth: d_margin_fifo > 0 means dropping the animal at dawn of d was better).

For each decision (animal alive at dawn of d, d in 14/17/20/23/26) the module's own DP (sm_tile_plan, collect=True as
in KS1: product value, wheat and fertilizer at the given prices) is followed along its planned path from the recorded
dawn state; the DP "keeps" the animal when the planned path keeps it alive through its last production night.
Unit values tried (all but ORACLE are computable online at dawn of d):
  QUOTE   the dawn quote (what the agent does now)
  FWD_OWN / FWD_MARGIN  forward value from the observable inventory, shops and the last-3-day sale rates of both
          players: I(t) = I_d + (o + r - D) (t - d), floored where the price reaches 1; a unit sold on day t is worth
          p(I_t) - s(I_t) o (29 - t) for own cash, p(I_t) + s(I_t) (r - o) (29 - t) for margin (s = price drop per
          unit at I_t); v = the best day t in [d+1, 29]
  BASE    the product's base price (160 milk, 200 wool, 50 egg)
  ORACLE  the exact realised margin value of one extra unit (abandon_market.marginal_tables margin_best, day d+1)
  FLOOR   max(quote, FLOOR_V[product]) (milk 60, wool 100, egg 45: the panel's own-cash value of a unit held to the end)
  LAST_CYCLE  the DP at the quote decides only when one production night is left; earlier the animal is kept
Regret = sum of |d_margin| over wrong decisions (drop when keeping was better, keep when dropping was better).
usage: abandon_rules.py -> results/fresh/abandon_20260926/rules.json + printed table
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import abandon_market as AM  # noqa: E402

E = AM.E
PI = AM.PI
PROD = AM.PROD
_NS = {}
BASE = {'MILK': 160, 'WOOL': 200, 'EGG': 50}
FLOOR_V = {'MILK': 60, 'WOOL': 100, 'EGG': 45}


def sm():
    if not _NS:
        exec(compile((ROOT / 'scripts/fragments/sem_maintenance.py').read_text(encoding='utf-8'), 'sm', 'exec'), _NS)
    return _NS


def slope(item, inv):
    return max(0, AM.price(item, inv) - AM.price(item, inv + 1))


def fwd_value(item, inv_d, d, o, r, D, margin=True):
    best = None
    inv = inv_d
    floor_inv = None
    for t in range(d, 30):
        if t > d:
            inv = inv + (o + r - D)
            if AM.price(item, inv) <= 1:          # units sold at $1 stop adding inventory
                if floor_inv is None:
                    floor_inv = inv
                inv = min(inv, floor_inv)
        if t < d + 1:
            continue
        p, s = AM.price(item, inv), slope(item, inv)
        left = 29 - t
        v = p + s * (r - o) * left if margin else p - s * o * left
        best = v if best is None else max(best, v)
    return max(1.0, best)


def dp_keeps(kind, st, d, price, wheat, fert, avail):
    """follow the DP's planned path from dawn of d; True when the animal is alive after its last production night."""
    S_ = sm()
    rin = S_['_sm_ratio'](wheat, price)
    rc = S_['_sm_ratio'](fert, price)
    solver = S_['_sm_solver'](kind, False, rin, 0, 8, rc)
    best = solver.today(st, d, 0, avail=avail)
    if best is None:
        return False
    s_, day = best[2], d + 1
    nights = [n for n in AM.prod_nights(kind, st[0]) if n >= d]
    last = max(nights) if nights else d
    while s_ is not None and s_ != 'GONE' and day <= last:
        b = solver.value(s_, day)
        if b[1] is None:
            return False
        s_, day = b[2], day + 1
    return s_ is not None and s_ != 'GONE'


def main():
    drops = json.loads((AM.OUT / 'drop.json').read_text(encoding='utf-8'))
    marg = json.loads((AM.OUT / 'marginal.json').read_text(encoding='utf-8'))
    cache = {}
    res = []
    for x in drops:
        k = (x['side'], x['ep'])
        if k not in cache:
            cache.clear()
            cache[k] = json.loads((AM.RDIR / x['side'] / f"{x['ep']}.json").read_text(encoding='utf-8'))
        R = cache[k]
        a = R['animals'][x['key']]
        dw = {r[0]: r for r in a['dawn']}[x['d']]
        kind, d = x['kind'], x['d']
        item = PROD[kind]
        placed = int(x['key'].split(',')[3])
        st = (placed, dw[1], dw[2], dw[3], False, False)
        inv = R['inv'][d * 24][PI[item]]
        vals = {
            'QUOTE': float(x['q0']),
            'FWD_OWN': fwd_value(item, inv, d, x['our_rate'], x['rival_rate'], x['demand'], margin=False),
            'FWD_MARGIN': fwd_value(item, inv, d, x['our_rate'], x['rival_rate'], x['demand'], margin=True),
            'BASE': float(BASE[item]),
            'ORACLE': max(1.0, float(marg[x['side']][x['ep']][item][str(min(29, d + 1))]['margin_best'])),
            'FLOOR': max(float(x['q0']), float(FLOOR_V[item])),
        }
        keep = {n: dp_keeps(kind, st, d, v, x['wheat_q'], x['fert_q'], bool(dw[4])) for n, v in vals.items()}
        keep['NEVER_DROP'] = True
        left = [n for n in AM.prod_nights(kind, placed) if n >= d]
        keep['LAST_CYCLE'] = keep['QUOTE'] if len(left) <= 1 else True
        res.append(dict(side=x['side'], ep=x['ep'], kind=kind, d=d, key=x['key'], vals=vals, keep=keep,
                        d_margin=x['d_margin_fifo'], d_own=x['d_own_fifo'], d_margin_lifo=x['d_margin_lifo']))
    (AM.OUT / 'rules.json').write_text(json.dumps(res), encoding='utf-8')
    rules = ['QUOTE', 'FWD_MARGIN', 'FLOOR', 'LAST_CYCLE', 'ORACLE', 'NEVER_DROP']
    for side in ('LEADER', 'KS1', 'KC8', 'KE7'):
        rs = [r for r in res if r['side'] == side]
        print(f'== {side}: {len(rs)} decisions (40 worlds x days 14/17/20/23/26); regret per world, margin FIFO (LIFO)')
        for kd in ('COW', 'SHEEP', 'GOOSE', 'ALL'):
            sub = [r for r in rs if kd == 'ALL' or r['kind'] == kd]
            line = []
            for rule in rules:
                reg = sum((-r['d_margin'] if (not r['keep'][rule] and r['d_margin'] < 0) else 0)
                          + (r['d_margin'] if (r['keep'][rule] and r['d_margin'] > 0) else 0) for r in sub) / 40
                rego = sum((-r['d_margin_lifo'] if (not r['keep'][rule] and r['d_margin_lifo'] < 0) else 0)
                           + (r['d_margin_lifo'] if (r['keep'][rule] and r['d_margin_lifo'] > 0) else 0) for r in sub) / 40
                nd = sum(1 for r in sub if not r['keep'][rule]) / 40
                line.append(f'{rule} {reg:5.0f} ({rego:5.0f}) drops {nd:4.1f}')
            print(f'  {kd:5s} ' + ' | '.join(line))


if __name__ == '__main__':
    main()
