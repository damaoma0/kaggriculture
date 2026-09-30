"""Closed-form derivation of the opening wheat-flip game, verified against the engine.

ENGINE FACTS USED (kaggriculture.py, read directly)
  * Wheat price below the neutral inventory: p(d) = round(25 + sqrt(d)), d = 10000 - inventory.
    (base 25, T 400, sqrt shape, target 0.8: amplitude 0.8*25/sqrt(400) = 1.)
  * A BUY quotes p(d+1) (post-buy inventory); a SELL quotes p(d) (current inventory).
  * Orders are matched by list index. Within an index, each round both active players quote from the SAME
    pre-round inventory, then both commit one unit.

THE FLIP GAME
  Each player submits [BUY q, SELL q] at turn 0: index 0 buys, index 1 sells the same q back. Let
  a = min(qA, qB), b = max(qA, qB).
    buys,  rounds r <= a : both buy, each pays p(2r-1)
           rounds a < r <= b : only the larger buys, pays p(a + r)
    sells, rounds r <= a : both sell, each receives p(a + b + 2 - 2r)
           rounds a < r <= b : only the larger sells, receives p(b + 1 - r)
  so
    pi_small(a, b) = sum_{r=1..a} [ p(a+b+2-2r) - p(2r-1) ]
    pi_large(a, b) = pi_small(a, b) + sum_{r=a+1..b} [ p(b+1-r) - p(a+r) ]
  Solo (a = 0): pi = sum p(k) - sum p(k) = 0 exactly. Symmetric (a = b = q): pi = sum_{k=1..q} [p(2k) - p(2k-1)].
"""
import json
from functools import lru_cache
from market_corpus import ROOT

OUT = ROOT / 'results/fresh/wheat_flip_derivation.json'


def main():
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E

    @lru_cache(maxsize=None)
    def p(d):
        return E.market_price('WHEAT', 10000 - d)

    def pi(q_self, q_opp):
        a, b = min(q_self, q_opp), max(q_self, q_opp)
        small = sum(p(a + b + 2 - 2 * r) - p(2 * r - 1) for r in range(1, a + 1))
        if q_self <= q_opp:
            return small
        return small + sum(p(b + 1 - r) - p(a + r) for r in range(a + 1, b + 1))

    # 1. verify the closed form against the engine on a grid
    def engine(q_self, q_opp):
        env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': 1})
        env.reset()
        mk = lambda q: [] if q == 0 else [['BUY_PRODUCT', 'WHEAT', q], ['SELL', 'WHEAT', q]]
        env.step([{'farmer': ['PASS'], 'hands': [], 'market': mk(q_self)},
                  {'farmer': ['PASS'], 'hands': [], 'market': mk(q_opp)}])
        f = env.state[0].observation.farms
        return f[0]['money'] - 3000, f[1]['money'] - 3000

    grid = (0, 1, 2, 3, 5, 8, 13, 20, 28, 29, 35, 50, 70, 100)
    mismatches = 0
    for x in grid:
        for y in grid:
            ex, ey = engine(x, y)
            if (ex, ey) != (pi(x, y), pi(y, x)):
                mismatches += 1
                print('MISMATCH', x, y, (ex, ey), (pi(x, y), pi(y, x)))
    print(f'closed form vs engine: {len(grid) ** 2} cells, {mismatches} mismatches')

    # 2. symmetric direct profit
    print('\nsymmetric direct profit per player, both flip q:')
    sym = {q: pi(q, q) for q in range(0, 101)}
    for q in (0, 5, 13, 35, 70, 100):
        print(f'   q={q:3d}: {sym[q]:+d}')
    print(f'   max over q<=100: {max(sym.values()):+d} at q={max(sym, key=sym.get)}, min {min(sym.values()):+d}')

    # 3. best responses and symmetric equilibria, cash and margin utilities
    Q = range(0, 101)
    br_cash, br_margin = {}, {}
    for q in Q:
        best_c = max(pi(x, q) for x in Q)
        best_m = max(pi(x, q) - pi(q, x) for x in Q)
        br_cash[q] = [x for x in Q if pi(x, q) == best_c]
        br_margin[q] = [x for x in Q if pi(x, q) - pi(q, x) == best_m]
    print('\nbest responses (all maximisers shown as a range when contiguous):')
    for q in (0, 1, 2, 3, 5, 8, 13, 20, 28, 35, 50, 70):
        bc, bm = br_cash[q], br_margin[q]
        fmt = lambda v: f'{v[0]}' if len(v) == 1 else f'{v[0]}..{v[-1]} ({len(v)} ties)'
        print(f'   vs q={q:3d}: cash BR {fmt(bc):>18s} gain {pi(bc[0], q):+4d} | margin BR {fmt(bm):>18s} gain {pi(bm[0], q) - pi(q, bm[0]):+4d}')
    eq_cash = [q for q in Q if q in br_cash[q]]
    eq_margin = [q for q in Q if q in br_margin[q]]
    print(f'\nsymmetric pure Nash equilibria of the flip game, q in 0..100: cash utility {eq_cash}; margin utility {eq_margin}')
    # exploitability of each q: the most an opponent can take from it (margin)
    print('\nexploitability: worst margin a flip of q can suffer against any other flip size')
    for q in (0, 1, 2, 5, 13, 35, 70):
        worst = min(pi(q, x) - pi(x, q) for x in Q)
        print(f'   q={q:3d}: {worst:+d}')
    OUT.write_text(json.dumps(dict(sym={str(k): v for k, v in sym.items()},
                                   br_cash={str(k): v for k, v in br_cash.items()},
                                   br_margin={str(k): v for k, v in br_margin.items()},
                                   eq_cash=eq_cash, eq_margin=eq_margin, mismatches=mismatches), indent=1),
                   encoding='utf-8')


if __name__ == '__main__':
    main()
