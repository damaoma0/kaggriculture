"""Direction 1: tape-match quality in ladder losses vs wins.

For every ladder-panel game of mgt_m1 / mgt_t10 / mgt_lib584 (the router's history is recorded per game), take the
FINAL tape the router followed and compare its recorded shops with the world's: late (shops 5-8) Yarn Stores in
the world minus in the tape (positive = the tape planned for fewer Yarn Stores than the world got), the same for
strawberry- and milk-buying shops, and the full-shop weighted demand distance. Then ask whether losses track the
world's demand (world late Yarn) or the MISMATCH (world minus tape), in one logistic model with both terms.

Panel margins are against the recorded (frozen) opponent; for each build's own recorded games they equal the
ladder result. Writes results/fresh/newphase_20260923/ladder_tape_match.json
"""
import gzip, json, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/newphase_20260923'
PANEL = ROOT / 'results/fresh/ladder_panel'
BUYS = {'BAKERY': ('egg', 'wheat'), 'PIZZA_SHOP': ('milk', 'tomato', 'wheat'), 'BRUNCH_SPOT': ('egg', 'wheat', 'strawberry'),
        'YARN_STORE': ('wool',), 'ICE_CREAM_SHOP': ('strawberry', 'milk', 'wheat'), 'PET_CAFE': ('carrot',),
        'SMOOTHIE_SHOP': ('strawberry', 'milk'), 'FARMERS_MARKET': ('wheat', 'carrot', 'tomato', 'strawberry')}


def seq(sh):
    out, seen = [], 0
    for cur in sh:
        while len(cur) > seen:
            out.append(cur[seen]); seen += 1
    return out[:8]


def count(shops, prod):
    return sum(prod in BUYS[s] for s in shops)


def fit(X, y, iters=60):
    w = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(X @ w, -30, 30)))
        H = X.T @ (X * np.maximum(p * (1 - p), 1e-6)[:, None]) + 1e-6 * np.eye(X.shape[1])
        w += np.linalg.solve(H, X.T @ (y - p))
    return w


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    tape_shops = {}
    for p in (ROOT / 'data/mg_tapes').rglob('*.json.gz'):
        g = json.load(gzip.open(p, 'rt', encoding='utf-8'))
        tape_shops[g['episode']] = seq(g['shops'])
    worlds = {}
    for p in (ROOT / 'data/ladder_panel').rglob('*.json.gz'):
        g = json.load(gzip.open(p, 'rt', encoding='utf-8'))
        worlds[g['episode']] = seq(g['shops'])
    rows = []
    for build in ('mgt_m1', 'mgt_t10', 'mgt_lib584'):
        for f in (PANEL / build).glob('*.json'):
            r = json.loads(f.read_text(encoding='utf-8'))
            if not r.get('switches') or r['episode'] not in worlds:
                continue
            final_ep, last_day = r['switches'][-1][1], r['switches'][-1][0]
            ws, ts = worlds[r['episode']], tape_shops.get(final_ep)
            if not ts:
                continue
            row = dict(build=build, episode=r['episode'], margin=r['margin'], win=int(r['margin'] > 0), last_switch=last_day,
                       same_first4=int(ws[:4] == ts[:4]), same_last4=int(ws[4:] == ts[4:]))
            for prod in ('wool', 'strawberry', 'milk', 'tomato', 'carrot', 'egg'):
                row[f'world_late_{prod}'] = count(ws[4:], prod)
                row[f'mis_late_{prod}'] = count(ws[4:], prod) - count(ts[4:], prod)
                row[f'mis_early_{prod}'] = count(ws[:4], prod) - count(ts[:4], prod)
            rows.append(row)
    print(f'{len(rows)} panel games with a router history')
    for build in ('mgt_m1', 'mgt_t10', 'mgt_lib584'):
        rs = [r for r in rows if r['build'] == build]
        if rs:
            print(f"  {build}: n={len(rs)}, win {np.mean([r['win'] for r in rs]):.3f}, final tape has the world's first 4 shops in "
                  f"{np.mean([r['same_first4'] for r in rs]):.1%}, last 4 in {np.mean([r['same_last4'] for r in rs]):.1%}, "
                  f"last switch day median {np.median([r['last_switch'] for r in rs]):.0f}")
    # one world per episode: prefer the build that played it on the ladder (m1 on its own games), else m1, else lib584
    best = {}
    for r in rows:
        best.setdefault(r['episode'], {})[r['build']] = r
    uniq = [v.get('mgt_m1') or v.get('mgt_lib584') or v.get('mgt_t10') for v in best.values()]
    print(f'unique worlds: {len(uniq)}')
    print('\nwin rate by late-Yarn mismatch (world minus final tape), unique worlds:')
    for v in (-2, -1, 0, 1, 2):
        sel = [r for r in uniq if (r['mis_late_wool'] == v if abs(v) < 2 else (r['mis_late_wool'] >= 2 if v > 0 else r['mis_late_wool'] <= -2))]
        if sel:
            print(f"  mismatch {v:+d}{'+' if abs(v) == 2 else ' '}: n={len(sel):3d} win {np.mean([r['win'] for r in sel]):.3f} "
                  f"margin {np.mean([r['margin'] for r in sel]):+8,.0f}")
    names = ['int', 'world_late_wool', 'mis_late_wool', 'mis_early_wool', 'world_late_strawberry', 'mis_late_strawberry',
             'mis_late_milk', 'same_first4']
    X = np.array([[1.0] + [r[n] for n in names[1:]] for r in uniq])
    y = np.array([float(r['win']) for r in uniq])
    w = fit(X, y)
    rng = np.random.default_rng(3)
    B = np.array([fit(X[i], y[i]) for i in rng.integers(0, len(X), (400, len(X)))])
    print('\nlogit P(win), unique worlds (frozen-opponent panel margins):')
    res = dict(n=len(uniq), coef={})
    for j, n in enumerate(names):
        lo, hi = np.percentile(B[:, j], [2.5, 97.5])
        res['coef'][n] = [float(w[j]), float(lo), float(hi)]
        print(f"  {n:22s} {w[j]:+.3f} (odds x{np.exp(w[j]):.2f})  95% CI [{lo:+.3f}, {hi:+.3f}]{' *' if lo * hi > 0 and n != 'int' else ''}")
    res['rows'] = rows
    (OUT / 'ladder_tape_match.json').write_text(json.dumps(res), encoding='utf-8')


if __name__ == '__main__':
    main()
