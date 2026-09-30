"""Direction 1/3: how much win rate is tied to specific world features on the real ladder?

Fits P(win) ~ opponent rating + seat + build + early/late Yarn Stores + strawberry/milk/tomato/carrot/egg
shop counts (engine demand table) on our 856 ladder games (t10 + m1), then asks: if the fitted penalty of a
feature were removed (our response to that demand as good as in worlds without it), what would the
sample's mean predicted win rate be? FITTED, cross-sectional: an upper-bound style estimate of what a
perfect response to that demand is worth in W/L, not a causal measurement.
"""
import json, math, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/newphase_20260923'
sys.stdout.reconfigure(encoding='utf-8')


def fit(X, y, iters=60):
    w = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(X @ w, -30, 30)))
        H = X.T @ (X * np.maximum(p * (1 - p), 1e-6)[:, None]) + 1e-6 * np.eye(X.shape[1])
        w += np.linalg.solve(H, X.T @ (y - p))
    return w


def main():
    rows = json.loads((OUT / 'ladder_games.json').read_text(encoding='utf-8'))
    rs = [r for r in rows if r['submission'] in ('56368334', '56395605') and r['opp_rating'] not in (None, '')]
    names = ['int', 'opp_rating', 'seat1', 'is_m1', 'yarn_early', 'yarn_late', 'straw', 'milk', 'tomato', 'carrot', 'egg']

    def F(r):
        d, dl = r['demand'], r['demand_late']
        return [1.0, (float(r['opp_rating']) - 2400) / 400, 1.0 * (r['seat'] == 1), 1.0 * (r['submission'] == '56395605'),
                d.get('wool', 0) - dl.get('wool', 0), dl.get('wool', 0), d.get('strawberry', 0), d.get('milk', 0),
                d.get('tomato', 0), d.get('carrot', 0), d.get('egg', 0)]
    X = np.array([F(r) for r in rs]); y = np.array([float(r['win']) for r in rs])
    w = fit(X, y)
    rng = np.random.default_rng(1)
    B = np.array([fit(X[i], y[i]) for i in rng.integers(0, len(X), (400, len(X)))])
    p0 = 1 / (1 + np.exp(-(X @ w)))
    res = dict(n=len(rs), observed_win=float(y.mean()), fitted_win=float(p0.mean()), coef=dict(zip(names, w.tolist())), removed={})
    print(f'n={len(rs)} observed win {y.mean():.3f}, fitted {p0.mean():.3f}')
    for feats in (['yarn_late'], ['yarn_early', 'yarn_late'], ['straw'], ['milk'], ['yarn_early', 'yarn_late', 'straw', 'milk']):
        idx = [names.index(f) for f in feats]
        def cf(wv):
            Xc = X.copy()
            for j in idx:
                if wv[j] < 0:                      # only remove penalties
                    Xc[:, j] = 0
            return float((1 / (1 + np.exp(-(Xc @ wv)))).mean())
        v = cf(w); bs = sorted(cf(b) - float((1 / (1 + np.exp(-(X @ b)))).mean()) for b in B)
        res['removed']['+'.join(feats)] = dict(win=v, gain=v - p0.mean(), ci=[bs[10], bs[-11]])
        print(f'  remove penalty of {"+".join(feats):40s}: win {v:.3f} (gain {v - p0.mean():+.3f}, 95% CI {bs[10]:+.3f}..{bs[-11]:+.3f})')
    (OUT / 'world_counterfactual.json').write_text(json.dumps(res, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
