"""Leader board-COUNT model: predicts leader board composition (count of tiles per label)
a few days ahead from the visible-shop demand vector plus the agent's own current counts.

Per `results/fresh/leader_retrieval/summary.md`, from about decision day 12 on a ridge
regression on composition counts beats copying (retrieving) any single leader game. This
script fits that model properly (per-label, per-horizon ridge, strength chosen by
leave-one-game-out), exports it as plain JSON, and provides a pure-Python `predict()` that
reads the JSON with NO numpy at prediction time (this will run inside a Kaggle agent, which
must be a single self-contained .py file - see CLAUDE.md conventions).

Corpus: data/leader_semantics/<team_id>/<episode>.json.gz (240 games; schema in
data/leader_semantics/README.md). Demand/label vocabulary reproduced verbatim from
scripts/leader_plan_retrieval.py (itself reproduced verbatim from the ROUTER template in
scripts/build_mg_tape_agent.py), per that file's own convention of not cross-importing into
agent-bound code.

Run as a script to fit + export + self-check + report:
    .venv/Scripts/python.exe scripts/leader_count_model.py
"""
import gzip
import json
import glob
import os
import random

import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS_GLOB = os.path.join(REPO_ROOT, 'data', 'leader_semantics', '*', '*.json.gz')
OUT_JSON = os.path.join(REPO_ROOT, 'data', 'leader_semantics', 'count_model_540.json')
RESULTS_DIR = os.path.join(REPO_ROOT, 'results', 'fresh', 'leader_count_model_540')

# ---------------------------------------------------------------------------
# Vocabulary / demand model - verbatim from scripts/leader_plan_retrieval.py.
# ---------------------------------------------------------------------------
LABELS = (' L', 'WH', 'ST', ' .', 'co', 'CA', 'sh', 'TO', 'go', 'ME', 'pa')
_LABEL_DOC = {' L': 'LOCKED', ' .': 'EMPTY', 'WH': 'WH', 'ST': 'ST', 'co': 'co',
              'CA': 'CA', 'sh': 'sh', 'TO': 'TO', 'go': 'go', 'ME': 'ME', 'pa': 'pa'}

_DEMAND = {'BAKERY': {'EGG': 1, 'WHEAT': 1}, 'PIZZA_SHOP': {'MILK': 1, 'TOMATO': 1, 'WHEAT': 1},
           'BRUNCH_SPOT': {'EGG': 1, 'WHEAT': 1, 'STRAWBERRY': 1}, 'YARN_STORE': {'WOOL': 2},
           'ICE_CREAM_SHOP': {'STRAWBERRY': 1, 'MILK': 1, 'WHEAT': 1}, 'PET_CAFE': {'CARROT': 2},
           'SMOOTHIE_SHOP': {'STRAWBERRY': 1, 'MILK': 1},
           'FARMERS_MARKET': {'WHEAT': 1, 'CARROT': 1, 'TOMATO': 1, 'STRAWBERRY': 1}}
PRODUCTS = ('STRAWBERRY', 'TOMATO', 'WOOL', 'CARROT', 'MILK', 'EGG', 'WHEAT')


def demand_vec(shop_names):
    c = [0] * len(PRODUCTS)
    for s in shop_names:
        for p, n in _DEMAND.get(s, {}).items():
            c[PRODUCTS.index(p)] += n
    return c


# ---------------------------------------------------------------------------
# Feature layout (shared by the numpy fitting code and the pure-python predict()):
#   [demand_vec (7)] + [own board counts in LABELS order (11)] + [day_frac (1)]
#   + [day_frac * demand_vec (7)]   = 26 raw features (+ bias = 27).
# ---------------------------------------------------------------------------
N_DV = len(PRODUCTS)
N_CNT = len(LABELS)
FEATURE_NAMES = (['dv_%s' % p for p in PRODUCTS] + ['cnt_%s' % _LABEL_DOC[l] for l in LABELS]
                  + ['day_frac'] + ['day_frac_x_dv_%s' % p for p in PRODUCTS])
N_FEAT = len(FEATURE_NAMES)
assert N_FEAT == N_DV + N_CNT + 1 + N_DV == 26


def build_features(shops_so_far, board_counts, day):
    """shops_so_far: list of shop-name strings visible at `day`. board_counts: dict label->count.
    Returns a length-26 plain list (matches FEATURE_NAMES order). Pure python, no numpy."""
    dv = demand_vec(shops_so_far)
    counts = [float(board_counts.get(lbl, 0)) for lbl in LABELS]
    day = max(0, min(29, int(day)))
    day_frac = day / 29.0
    return list(dv) + counts + [day_frac] + [day_frac * x for x in dv]


CROP_LABEL = {'STRAWBERRY': 'ST', 'TOMATO': 'TO', 'MELON': 'ME', 'WHEAT': 'WH', 'CARROT': 'CA'}
ANIMAL_LABELS = ('sh', 'co', 'go')

FIT_DAYS = list(range(6, 28))          # 6..27 inclusive (22 days/game)
HORIZONS = (1, 2, 3, 6)
ALPHA_GRID = (0.1, 1.0, 3.0, 10.0, 30.0, 100.0, 300.0)
DAY_BUCKETS = (('9-14', 9, 14), ('15-20', 15, 20), ('21-27', 21, 27))


# ---------------------------------------------------------------------------
# Corpus loading
# ---------------------------------------------------------------------------
def load_games():
    games = []
    for path in sorted(glob.glob(CORPUS_GLOB)):
        with gzip.open(path, 'rt', encoding='utf-8') as fh:
            games.append(json.load(fh))
    return games


# ---------------------------------------------------------------------------
# Build the (n_games, n_fitdays, N_FEAT) feature tensor and per-horizon targets.
# ---------------------------------------------------------------------------
def build_arrays(games):
    n_games = len(games)
    n_days = len(FIT_DAYS)
    X = np.zeros((n_games, n_days, N_FEAT))
    Y = {h: np.zeros((n_games, n_days, N_CNT)) for h in HORIZONS}
    for gi, d in enumerate(games):
        shops = [s['shop'] for s in d['shops']]
        days = d['days']
        for di, day in enumerate(FIT_DAYS):
            j = day // 3
            bc = days[day]['board_counts']
            X[gi, di, :] = build_features(shops[:j], bc, day)
            for h in HORIZONS:
                target_day = min(29, day + h)
                tc = days[target_day]['board_counts']
                Y[h][gi, di, :] = [tc.get(lbl, 0) for lbl in LABELS]
    return X, Y


# ---------------------------------------------------------------------------
# Ridge fitting, LOGO CV via exact per-game refit (rank-downdate of the precomputed
# full XtX/XtY - no approximation, no repeated whole-matrix multiplies).
# ---------------------------------------------------------------------------
def fit_label_horizon(Xb, y, alpha_grid):
    """Xb: (n_games, n_days, P) standardized design incl. bias col. y: (n_games, n_days)
    target counts for one label/horizon. Returns dict with chosen alpha, LOGO residuals
    (n_games, n_days) at that alpha, and the final (all-games) beta (P,)."""
    n_games, n_days, P = Xb.shape
    XtX_g = np.einsum('gdp,gdq->gpq', Xb, Xb)          # (n_games, P, P)
    XtX_full = XtX_g.sum(axis=0)                        # (P, P)
    XtY_g = np.einsum('gdp,gd->gp', Xb, y)               # (n_games, P)
    XtY_full = XtY_g.sum(axis=0)                         # (P,)

    best = None   # (mae, alpha, resid)
    for alpha in alpha_grid:
        reg = alpha * np.eye(P)
        reg[0, 0] = 0.0
        A_batch = XtX_full[None, :, :] - XtX_g + reg[None, :, :]      # (n_games,P,P)
        b_batch = (XtY_full[None, :] - XtY_g)[:, :, None]              # (n_games,P,1)
        beta_batch = np.linalg.solve(A_batch, b_batch)[:, :, 0]        # (n_games,P)
        yhat = np.einsum('gdp,gp->gd', Xb, beta_batch)                 # (n_games,n_days)
        resid = y - yhat
        mae = np.abs(resid).mean()
        if best is None or mae < best[0]:
            best = (mae, alpha, resid)
    mae, alpha, resid = best

    reg = alpha * np.eye(P)
    reg[0, 0] = 0.0
    beta_final = np.linalg.solve(XtX_full + reg, XtY_full)             # (P,)
    return {'alpha': alpha, 'logo_mae': mae, 'logo_resid': resid, 'beta_std': beta_final}


def fit_all(X, Y):
    n_games, n_days, p = X.shape
    Xflat = X.reshape(-1, p)
    mu = Xflat.mean(axis=0)
    sigma = Xflat.std(axis=0)
    sigma = np.where(sigma < 1e-8, 1.0, sigma)
    Xs = (X - mu) / sigma
    Xb = np.concatenate([np.ones((n_games, n_days, 1)), Xs], axis=-1)

    fitted = {}    # (horizon,label) -> fit dict
    for h in HORIZONS:
        for li, lbl in enumerate(LABELS):
            y = Y[h][:, :, li]
            fitted[(h, lbl)] = fit_label_horizon(Xb, y, ALPHA_GRID)
    return fitted, mu, sigma


def to_raw_coef(beta_std, mu, sigma):
    """beta_std: (P,) = [bias_std, coef_std(26,)] fit on Xb=[1, (X-mu)/sigma].
    Returns (raw_bias, raw_coef(26,)) s.t. bias_std + sum(coef_std*(X-mu)/sigma)
    == raw_bias + sum(raw_coef*X) exactly."""
    bias_std = beta_std[0]
    coef_std = beta_std[1:]
    raw_coef = coef_std / sigma
    raw_bias = bias_std - float(np.sum(coef_std * mu / sigma))
    return raw_bias, raw_coef


# ---------------------------------------------------------------------------
# Lifecycle summary: crop tile lifetimes (plant day -> day label stops showing), and
# whether animals are ever removed (culled = starved, per README diff-based detection).
# ---------------------------------------------------------------------------
def lifecycle_summary(games):
    samples = {code: [] for code in CROP_LABEL.values()}   # (duration, censored)
    for d in games:
        days = d['days']
        for day in range(0, 29):
            planted = days[day].get('planted', {})
            for crop_name, tiles in planted.items():
                code = CROP_LABEL.get(crop_name)
                if code is None:
                    continue
                for t in tiles:
                    stop_day = None
                    for later in range(day + 1, 30):
                        if days[later]['board'][t] != code:
                            stop_day = later
                            break
                    if stop_day is None:
                        samples[code].append((29 - day, True))
                    else:
                        samples[code].append((stop_day - day, False))

    def pct(vals, q):
        if not vals:
            return None
        s = sorted(vals)
        idx = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
        return s[idx]

    out = {}
    for code, samp in samples.items():
        uncensored = [v for v, c in samp if not c]
        out[code] = {
            'n_planted_events': len(samp),
            'n_censored_at_d29': sum(1 for _, c in samp if c),
            'mean_lifetime_days_uncensored': (sum(uncensored) / len(uncensored)) if uncensored else None,
            'median_lifetime_days_uncensored': pct(uncensored, 0.5),
            'p10_lifetime_days_uncensored': pct(uncensored, 0.10),
            'p90_lifetime_days_uncensored': pct(uncensored, 0.90),
            'max_lifetime_days_uncensored': max(uncensored) if uncensored else None,
        }

    # Animals: ever culled (starved)? placed tiles -> species via next day's board label.
    placed_ct = {code: 0 for code in ANIMAL_LABELS}
    culled_ct = {code: 0 for code in ANIMAL_LABELS}
    for d in games:
        days = d['days']
        for day in range(0, 29):
            for t in days[day].get('animals', {}).get('placed', []):
                lbl = days[day + 1]['board'][t]
                if lbl in placed_ct:
                    placed_ct[lbl] += 1
            for t in days[day].get('animals', {}).get('culled', []):
                lbl = days[day]['board'][t]
                if lbl in culled_ct:
                    culled_ct[lbl] += 1
    animals = {}
    for code in ANIMAL_LABELS:
        animals[code] = {
            'n_placed_events': placed_ct[code],
            'n_culled_events': culled_ct[code],
            'frac_ever_culled_per_placement': (culled_ct[code] / placed_ct[code]) if placed_ct[code] else None,
        }
    return {'crops': out, 'animals': animals,
            'note': 'crop lifetime = days from PLANT day to the first day the tile no longer '
                    'shows that crop label (harvest/replant/dig); censored = still showing at '
                    'day 29 (right-censored, treat as a lower bound). animals: fraction of '
                    'placed tiles later detected as starved (culled) - tells a planner whether '
                    'replacement/replanting must be scheduled at all for that species/crop.'}


# ---------------------------------------------------------------------------
# Export + report
# ---------------------------------------------------------------------------
def bucket_mae(resid_or_abserr, mask_by_bucket):
    return {name: float(np.abs(resid_or_abserr)[:, mask].mean()) if mask.any() else None
            for name, mask in mask_by_bucket.items()}


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    print('Loading corpus...')
    games = load_games()
    n_games = len(games)
    print('n_games=%d' % n_games)

    print('Building feature/target arrays...')
    X, Y = build_arrays(games)

    print('Fitting ridge (per label x horizon, LOGO alpha selection)...')
    fitted, mu, sigma = fit_all(X, Y)

    day_arr = np.array(FIT_DAYS)
    bucket_masks = {name: (day_arr >= lo) & (day_arr <= hi) for name, lo, hi in DAY_BUCKETS}

    # Baseline: "counts stay the same" (persistence of the current count for that label).
    baseline_abserr = {}
    for h in HORIZONS:
        for li, lbl in enumerate(LABELS):
            cur = X[:, :, N_DV + li]                 # own count feature for this label
            tgt = Y[h][:, :, li]
            baseline_abserr[(h, lbl)] = np.abs(tgt - cur)

    # ---- export JSON (coefficients in raw feature space; predict() applies them directly) ----
    coefficients = {}
    report_rows = []
    for h in HORIZONS:
        coefficients[str(h)] = {}
        for lbl in LABELS:
            fit = fitted[(h, lbl)]
            raw_bias, raw_coef = to_raw_coef(fit['beta_std'], mu, sigma)
            coefficients[str(h)][lbl] = {'bias': raw_bias, 'coef': raw_coef.tolist(), 'alpha': fit['alpha']}
            model_bkt = bucket_mae(fit['logo_resid'], bucket_masks)
            base_bkt = bucket_mae(baseline_abserr[(h, lbl)], bucket_masks)
            report_rows.append({
                'horizon': h, 'label': lbl, 'alpha': fit['alpha'], 'logo_mae_overall': fit['logo_mae'],
                'model_by_bucket': model_bkt, 'baseline_by_bucket': base_bkt,
            })

    lifecycles = lifecycle_summary(games)

    model_json = {
        'meta': {
            'n_games': n_games, 'fit_days': FIT_DAYS, 'horizons': HORIZONS,
            'labels': LABELS, 'products': PRODUCTS, 'feature_names': FEATURE_NAMES,
            'alpha_grid': ALPHA_GRID, 'cv': 'leave-one-game-out (exact refit)',
            'note': ('predict(visible_shops, board_counts, day, horizon) in this file reads '
                     'this JSON; coefficients act on raw (unstandardized) features in '
                     'feature_names order, so predict() needs no numpy/scaling at inference.'),
        },
        'coefficients': coefficients,
        'lifecycles': lifecycles,
    }
    with open(OUT_JSON, 'w') as fh:
        json.dump(model_json, fh, indent=1)
    print('Wrote', OUT_JSON)

    # ---- self-check: pure-python predict() vs the numpy standardized-space computation ----
    global _COUNT_MODEL
    _COUNT_MODEL = model_json
    rng = random.Random(0)
    mism = 0
    n_days = len(FIT_DAYS)
    for _ in range(50):
        gi = rng.randrange(n_games)
        di = rng.randrange(n_days)
        h = rng.choice(HORIZONS)
        day = FIT_DAYS[di]
        d = games[gi]
        shops = [s['shop'] for s in d['shops']]
        j = day // 3
        bc = d['days'][day]['board_counts']
        unlocked = 100 - bc.get(' L', 0)
        py_pred = predict(shops[:j], bc, day, h)
        xb_row = np.concatenate([[1.0], (X[gi, di, :] - mu) / sigma])
        for lbl in LABELS:
            beta_std = fitted[(h, lbl)]['beta_std']
            np_val = float(xb_row @ beta_std)
            np_val = max(0.0, min(float(unlocked), np_val))
            if abs(np_val - py_pred[lbl]) > 1e-6:
                mism += 1
                print('MISMATCH', gi, day, h, lbl, np_val, py_pred[lbl])
    print('predict() self-check mismatches: %d/%d rows x %d labels' % (mism, 50, len(LABELS)))

    # ---- markdown summary ----
    lines = []
    lines.append('# Leader board-count model - LOGO results\n')
    lines.append('%d games, fit days %d..%d, horizons +%s, alpha grid %s.\n' % (
        n_games, FIT_DAYS[0], FIT_DAYS[-1], HORIZONS, ALPHA_GRID))
    lines.append('predict() self-check mismatches: %d/%d (50 rows x %d labels)\n' % (mism, 50 * len(LABELS), len(LABELS)))
    for h in HORIZONS:
        lines.append('\n## Horizon +%d\n' % h)
        lines.append('| label | alpha | 9-14 model | 9-14 base | 15-20 model | 15-20 base | 21-27 model | 21-27 base |')
        lines.append('|---|---|---|---|---|---|---|---|')
        for row in report_rows:
            if row['horizon'] != h:
                continue
            m, b = row['model_by_bucket'], row['baseline_by_bucket']
            lines.append('| %s | %.1f | %.3f | %.3f | %.3f | %.3f | %.3f | %.3f |' % (
                row['label'], row['alpha'],
                m['9-14'], b['9-14'], m['15-20'], b['15-20'], m['21-27'], b['21-27']))

    lines.append('\n## Crop lifecycle (tile: PLANT day -> day label changes)\n')
    lines.append('| crop | n events | n censored@d29 | mean (uncensored) | median | p10 | p90 | max |')
    lines.append('|---|---|---|---|---|---|---|---|')
    for crop_name, code in CROP_LABEL.items():
        c = lifecycles['crops'][code]
        def fmt(v):
            return '%.2f' % v if isinstance(v, float) else ('%d' % v if v is not None else 'n/a')
        lines.append('| %s (%s) | %d | %d | %s | %s | %s | %s | %s |' % (
            crop_name, code, c['n_planted_events'], c['n_censored_at_d29'],
            fmt(c['mean_lifetime_days_uncensored']), fmt(c['median_lifetime_days_uncensored']),
            fmt(c['p10_lifetime_days_uncensored']), fmt(c['p90_lifetime_days_uncensored']),
            fmt(c['max_lifetime_days_uncensored'])))

    lines.append('\n## Animal removal (culled = starved)\n')
    lines.append('| species | n placed | n culled | frac ever culled/placement |')
    lines.append('|---|---|---|---|')
    for code, a in lifecycles['animals'].items():
        frac = '%.4f' % a['frac_ever_culled_per_placement'] if a['frac_ever_culled_per_placement'] is not None else 'n/a'
        lines.append('| %s | %d | %d | %s |' % (code, a['n_placed_events'], a['n_culled_events'], frac))

    with open(os.path.join(RESULTS_DIR, 'summary.md'), 'w') as fh:
        fh.write('\n'.join(lines) + '\n')
    print('Wrote', os.path.join(RESULTS_DIR, 'summary.md'))

    with open(os.path.join(RESULTS_DIR, 'report_rows.json'), 'w') as fh:
        json.dump(report_rows, fh, indent=1)
    print('Wrote', os.path.join(RESULTS_DIR, 'report_rows.json'))


# ---------------------------------------------------------------------------
# Pure-python inference (no numpy). This is what an agent would embed/copy.
# ---------------------------------------------------------------------------
_COUNT_MODEL = None


def load_count_model(path=None):
    global _COUNT_MODEL
    if _COUNT_MODEL is None:
        with open(path or OUT_JSON) as fh:
            _COUNT_MODEL = json.load(fh)
    return _COUNT_MODEL


def predict(visible_shops, board_counts, day, horizon, model=None):
    """visible_shops: list of shop-name strings visible at `day` (or a {reveal_day: name}
    dict). board_counts: dict label(2-char)->count for the agent's OWN board right now.
    day: current day (0-29). horizon: 1/2/3/6 (days ahead). Returns {label: predicted count
    (float, clipped to [0, unlocked_tile_count])}. Pure python/stdlib only - no numpy."""
    m = model or load_count_model()
    if isinstance(visible_shops, dict):
        visible_shops = [v for _, v in sorted(visible_shops.items())]
    feat = build_features(visible_shops, board_counts, day)
    unlocked = 100 - int(board_counts.get(' L', 0))
    coefs = m['coefficients'][str(int(horizon))]
    out = {}
    for lbl in LABELS:
        c = coefs[lbl]
        val = c['bias']
        for w, x in zip(c['coef'], feat):
            val += w * x
        out[lbl] = max(0.0, min(float(unlocked), val))
    return out


if __name__ == '__main__':
    main()
