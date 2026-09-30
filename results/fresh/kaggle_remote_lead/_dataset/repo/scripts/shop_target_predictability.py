"""Does shop-conditioned plan learning extend past day 9? Out-of-sample R^2 of day-d board counts (sheep, cows, geese,
strawberry, tomato, wheat, carrot, melon tiles) predicted from the shops revealed by day d, for DSM (109 farm-games,
exact boards) and Mother-Goose old (584 tapes; cow count is an upper bound). Features: count of each of the 8 shop
types among the revealed shops, and among the latest two reveals separately (recency). Ridge regression, alpha chosen
by inner leave-one-out over a small grid, scored by leave-one-out over games. A constant prediction scores 0.
Inputs: results/fresh/newphase_20260923/leader_response/{dsm_cache,umg_cache}.json
"""
import json, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'results/fresh/newphase_20260923/leader_response'
SHOPS = ['BAKERY', 'PIZZA_SHOP', 'BRUNCH_SPOT', 'YARN_STORE', 'ICE_CREAM_SHOP', 'PET_CAFE', 'SMOOTHIE_SHOP', 'FARMERS_MARKET']
ITEMS = ['SHEEP', 'COW', 'GOOSE', 'STRAWBERRY', 'TOMATO', 'WHEAT', 'CARROT', 'MELON']


def reveal(shops_by_day):
    seq, seen = [], 0
    for cur in shops_by_day:
        while len(cur) > seen:
            seq.append(cur[seen]); seen += 1
    return seq


def feats(seq, day):
    k = min(8, day // 3)
    s = seq[:k]
    a = [s.count(x) for x in SHOPS]
    b = [s[-2:].count(x) for x in SHOPS]
    return a + b


def loo_ridge_r2(X, y, alphas=(0.3, 1, 3, 10, 30)):
    X = np.asarray(X, float); y = np.asarray(y, float)
    n = len(y)
    Xc = np.hstack([np.ones((n, 1)), X])

    def loo_pred(alpha, Xm, ym):
        I = np.eye(Xm.shape[1]); I[0, 0] = 0
        H = Xm @ np.linalg.solve(Xm.T @ Xm + alpha * I, Xm.T)
        yhat = H @ ym
        h = np.clip(np.diag(H), 0, 0.999)
        return (yhat - h * ym) / (1 - h)          # exact LOO residual shortcut for ridge
    best = min(alphas, key=lambda a: np.mean((loo_pred(a, Xc, y) - y) ** 2))
    p = loo_pred(best, Xc, y)
    sst = np.mean((y - y.mean()) ** 2)
    return 1 - np.mean((p - y) ** 2) / sst if sst > 0 else float('nan'), best


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    dsm = json.loads((SRC / 'dsm_cache.json').read_text(encoding='utf-8'))
    umg = json.loads((SRC / 'umg_cache.json').read_text(encoding='utf-8'))
    sets = {'DSM': [], 'UMG-old': []}
    for g in dsm.values():
        for s, f in g['per_farm'].items():
            if int(s) in g['dsm_indices']:
                sets['DSM'].append((reveal(g['shops_by_day']), f['day_counts']))
    for g in (umg.values() if isinstance(umg, dict) else umg):
        sets['UMG-old'].append((reveal(g['shops_by_day']), g['day_counts']))
    out = {}
    for name, rows in sets.items():
        out[name] = {}
        print(f'{name} (n={len(rows)}): out-of-sample R^2 of day-d counts from the shops revealed by day d')
        for day in (9, 12, 15, 18, 21, 24):
            X = [feats(seq, day) for seq, _ in rows]
            line = []
            for it in ITEMS:
                y = [c[day].get(it, 0) if len(c) > day else 0 for _, c in rows]
                r2, _ = loo_ridge_r2(X, y)
                out[name].setdefault(day, {})[it] = r2
                line.append(f'{it[:5]} {r2:5.2f}')
            print(f'  day {day:2d}: ' + '  '.join(line))
    (ROOT / 'results/fresh/newphase_20260923/opening/shop_target_predictability.json').write_text(json.dumps(out, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
