"""Evaluation harness for scripts/leader_plan_retrieval.py (gate G2).

Implements the same retrieval math as retrieve()/retrieve_games() but vectorised with numpy
for speed over the full grid (7 decision days x 3 protocols x 3 k's x 4 lambdas x 240 games x
2 horizons). Correctness is cross-checked against the pure-Python retrieve_games() on a random
sample before trusting the big grid (see _selfcheck()).

Also implements the ridge-regression baseline (composition counts, leave-one-game-out via the
ridge hat-matrix LOO shortcut) and the two required baselines (persistence, corpus-modal-board).

Outputs:
  results/fresh/leader_retrieval/results.json
  results/fresh/leader_retrieval/summary.md
"""
import os
import json
import random
import collections
import numpy as np

import leader_plan_retrieval as lpr

RESULTS_DIR = lpr.RESULTS_DIR
DECISION_DAYS = lpr.DECISION_DAYS
HORIZONS = lpr.HORIZONS
K_GRID = lpr.K_GRID
LAM_GRID = lpr.LAM_GRID
LABELS = lpr.LABELS
LABEL_INDEX = {lbl: i for i, lbl in enumerate(LABELS)}


# ---------------------------------------------------------------------------
# Precompute dense numpy arrays from the corpus (mirrors leader_plan_retrieval.py exactly).
# ---------------------------------------------------------------------------
def build_arrays():
    corpus = lpr.load_corpus()
    lpr._ensure_families()
    n = len(corpus)
    n_days = len(corpus[0]['boards'])
    n_tiles = len(corpus[0]['boards'][0])

    boards_int = np.zeros((n, n_days, n_tiles), dtype=np.int8)
    for i, g in enumerate(corpus):
        for d, board in enumerate(g['boards']):
            boards_int[i, d, :] = [LABEL_INDEX[lbl] for lbl in board]

    # one-hot counts per day: (n_days, n, 11)
    eye = np.eye(len(LABELS), dtype=np.float64)
    counts = np.zeros((n_days, n, len(LABELS)))
    for d in range(n_days):
        counts[d] = eye[boards_int[:, d, :]].sum(axis=1)

    # vecs[j]: (n, 7) demand vector using the game's own first-j-shops history
    n_j = len(corpus[0]['vecs'])
    vecs = np.zeros((n_j, n, len(lpr._PRODUCTS)))
    for j in range(n_j):
        for i, g in enumerate(corpus):
            vecs[j, i, :] = g['vecs'][j]

    team_ids = np.array([g['team_id'] for g in corpus])
    families = np.array([g['family'] for g in corpus])
    episodes = np.array([g['episode'] for g in corpus])
    teams_str = np.array([g['team'] for g in corpus])
    W = np.array(lpr._W)
    return {
        'corpus': corpus, 'n': n, 'n_days': n_days, 'n_tiles': n_tiles,
        'boards_int': boards_int, 'counts': counts, 'vecs': vecs,
        'team_ids': team_ids, 'families': families, 'episodes': episodes,
        'teams_str': teams_str, 'W': W,
    }


def _protocol_masks(A):
    n = A['n']
    eye = np.eye(n, dtype=bool)
    logo = ~eye
    loto = A['team_ids'][:, None] != A['team_ids'][None, :]
    family_logo = (A['families'][:, None] == A['families'][None, :]) & ~eye
    return {'logo': logo, 'loto': loto, 'family_logo': family_logo}


def _weighted_majority(neigh_boards, weights, n_tiles):
    """neigh_boards: (n, k, n_tiles) int labels; weights: (n, k). Returns (n, n_tiles) int."""
    n, k, _ = neigh_boards.shape
    best_score = np.full((n, n_tiles), -1.0)
    best_label = np.zeros((n, n_tiles), dtype=np.int8)
    for lbl in range(len(LABELS)):
        mask = (neigh_boards == lbl)                       # (n,k,n_tiles)
        score = (mask * weights[:, :, None]).sum(axis=1)    # (n,n_tiles)
        take = score > best_score
        best_label = np.where(take, lbl, best_label)
        best_score = np.where(take, score, best_score)
    return best_label


def hamming_np(a, b):
    return (a != b).sum(axis=-1)


def counts_from_board(board_int, n_labels=len(LABELS)):
    eye = np.eye(n_labels, dtype=np.float64)
    return eye[board_int].sum(axis=-2)


def mae_counts(pred_counts, actual_counts):
    return np.abs(pred_counts - actual_counts).mean(axis=-1)


# ---------------------------------------------------------------------------
# Self-check: numpy batch math must match the pure-python retrieve_games() reference.
# ---------------------------------------------------------------------------
def _selfcheck(A, trials=25, seed=0):
    rng = random.Random(seed)
    corpus = A['corpus']
    masks = _protocol_masks(A)
    mism = 0
    for _ in range(trials):
        i = rng.randrange(A['n'])
        day = rng.choice(DECISION_DAYS)
        k = rng.choice(K_GRID)
        lam = rng.choice(LAM_GRID)
        proto = rng.choice(['logo', 'loto', 'family_logo'])
        g = corpus[i]
        j = day // 3
        shops = g['shops'][:j]
        board = g['boards'][day]
        if proto == 'logo':
            ref = lpr.retrieve_games(shops, board, day, k=k, lam=lam, exclude_episode=g['episode'])
        elif proto == 'loto':
            ref = lpr.retrieve_games(shops, board, day, k=k, lam=lam, exclude_team=g['team_id'])
        else:
            fam = g['family']
            ref = lpr.retrieve_games(shops, board, day, k=k, lam=lam, family=fam, exclude_episode=g['episode'])
        ref_eps = sorted(rg['episode'] for rg, _ in ref)

        shop_dist = np.abs(A['vecs'][j] - A['vecs'][j][i]) @ A['W']
        ham = hamming_np(A['boards_int'][:, day, :], A['boards_int'][i, day, :])
        d = shop_dist + lam * ham
        mask = masks[proto][i].copy()
        if proto == 'family_logo':
            mask &= (A['families'] == g['family'])
        d = np.where(mask, d, np.inf)
        order = np.argsort(d, kind='stable')[:k]
        got_eps = sorted(A['episodes'][idx] for idx in order)
        if ref_eps != got_eps:
            mism += 1
            print('MISMATCH', i, day, k, lam, proto, ref_eps, got_eps)
    print('selfcheck mismatches: %d/%d' % (mism, trials))
    return mism == 0


# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------
def baseline_persistence(A, day, target_day):
    board_now = A['boards_int'][:, day, :]
    board_future = A['boards_int'][:, target_day, :]
    ham = hamming_np(board_now, board_future)
    mae = mae_counts(A['counts'][day], A['counts'][target_day])
    within8 = (ham <= 8).mean()
    return {'ham_mean': float(ham.mean()), 'mae_mean': float(mae.mean()), 'within8': float(within8)}


def baseline_corpus_mode(A, target_day):
    """LOGO corpus-modal board at target_day: for each query game i, the most common OTHER
    game's board at target_day (self excluded)."""
    boards = A['boards_int'][:, target_day, :]
    n = A['n']
    ham = np.zeros(n)
    mae = np.zeros(n)
    # global mode excluding each self in turn - with n=240 a python Counter pass per query
    # would be slow only if done per-query from scratch; instead compute the global mode board
    # and, for queries whose own board equals it, fall back to the 2nd most common.
    keys = [tuple(row) for row in boards]
    counter = collections.Counter(keys)
    ranked = counter.most_common()
    top_key, top_ct = ranked[0]
    second_key = ranked[1][0] if len(ranked) > 1 else ranked[0][0]
    for i in range(n):
        mode_key = second_key if keys[i] == top_key and counter[top_key] == 1 else top_key
        # if self is the unique holder of the top mode, exclude it properly; otherwise the mode
        # still holds with self removed (count > 1)
        if keys[i] == top_key and counter[top_key] <= 1:
            mode_key = second_key
        mode_board = np.array(mode_key, dtype=np.int8)
        ham[i] = (boards[i] != mode_board).sum()
        mae[i] = np.abs(counts_from_board(boards[i]) - counts_from_board(mode_board)).mean()
    within8 = (ham <= 8).mean()
    return {'ham_mean': float(ham.mean()), 'mae_mean': float(mae.mean()), 'within8': float(within8)}


# ---------------------------------------------------------------------------
# Retrieval grid evaluation
# ---------------------------------------------------------------------------
def eval_retrieval(A):
    masks = _protocol_masks(A)
    out = {}
    for day in DECISION_DAYS:
        j = day // 3
        vecs_j = A['vecs'][j]                                  # (n,7)
        shop_dist = np.abs(vecs_j[:, None, :] - vecs_j[None, :, :]) @ A['W']   # (n,n)
        board_day = A['boards_int'][:, day, :]
        ham_day = (board_day[:, None, :] != board_day[None, :, :]).sum(axis=2).astype(float)
        for proto, base_mask in masks.items():
            for lam in LAM_GRID:
                d = shop_dist + lam * ham_day
                d = np.where(base_mask, d, np.inf)
                for k in K_GRID:
                    order = np.argsort(d, axis=1, kind='stable')[:, :k]     # (n,k)
                    n = A['n']
                    dk = np.take_along_axis(d, order, axis=1)
                    valid = np.isfinite(dk)
                    n_valid = valid.sum(axis=1)
                    skip_rows = n_valid == 0
                    inv = np.where(valid, 1.0 / (dk + 1e-6), 0.0)
                    wsum = inv.sum(axis=1, keepdims=True)
                    wsum[wsum == 0] = 1.0
                    weights = inv / wsum                                     # (n,k)

                    for h in HORIZONS:
                        target_day = min(29, day + h)
                        neigh_boards = A['boards_int'][order, target_day, :]  # (n,k,n_tiles)
                        pred_board = _weighted_majority(neigh_boards, weights, A['n_tiles'])
                        actual_board = A['boards_int'][:, target_day, :]
                        ham = (pred_board != actual_board).sum(axis=1).astype(float)
                        pred_counts = counts_from_board(pred_board)
                        actual_counts = A['counts'][target_day]
                        mae = np.abs(pred_counts - actual_counts).mean(axis=1)
                        keep = ~skip_rows
                        rec = {
                            'n_games': int(keep.sum()),
                            'ham_mean': float(ham[keep].mean()) if keep.any() else None,
                            'mae_mean': float(mae[keep].mean()) if keep.any() else None,
                            'within8': float((ham[keep] <= 8).mean()) if keep.any() else None,
                        }
                        out[(day, proto, k, lam, h)] = rec
    return out


# ---------------------------------------------------------------------------
# Ridge regression (composition counts), LOGO via hat-matrix shortcut
# ---------------------------------------------------------------------------
def ridge_logo_mae(X, Y, alpha):
    n, p = X.shape
    Xb = np.hstack([np.ones((n, 1)), X])
    XtX = Xb.T @ Xb
    reg = alpha * np.eye(p + 1)
    reg[0, 0] = 0.0   # do not regularise the intercept
    A_inv = np.linalg.inv(XtX + reg)
    H = Xb @ A_inv @ Xb.T
    h_diag = np.clip(np.diag(H).copy(), 0, 0.999999)
    Yhat = H @ Y
    loo_pred = (Yhat - h_diag[:, None] * Y) / (1 - h_diag[:, None])
    mae_per_game = np.abs(loo_pred - Y).mean(axis=1)
    return float(mae_per_game.mean()), loo_pred


def eval_regression(A, alphas=(0.1, 1.0, 5.0, 10.0, 30.0)):
    out = {}
    chosen_alpha = {}
    for day in DECISION_DAYS:
        j = day // 3
        X = np.hstack([A['vecs'][j], A['counts'][day]])   # (n, 18)
        for h in HORIZONS:
            target_day = min(29, day + h)
            Y = A['counts'][target_day]
            best = None
            for alpha in alphas:
                mae, _ = ridge_logo_mae(X, Y, alpha)
                if best is None or mae < best[0]:
                    best = (mae, alpha)
            out[(day, h)] = {'mae_mean': best[0], 'alpha': best[1], 'n_games': A['n']}
            chosen_alpha[(day, h)] = best[1]
    return out, chosen_alpha


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------
def best_settings_table(retrieval_results):
    """Per day, best (proto,k,lam) by within8 (primary) then ham_mean, for each horizon."""
    best = {}
    for (day, proto, k, lam, h), rec in retrieval_results.items():
        if rec['within8'] is None:
            continue
        key = (day, h)
        score = (rec['within8'], -rec['ham_mean'])
        if key not in best or score > best[key][0]:
            best[key] = (score, proto, k, lam, rec)
    return best


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    print('Loading corpus + building arrays...')
    A = build_arrays()
    print('n games=%d' % A['n'])

    print('Self-check numpy batch vs pure-python retrieve_games()...')
    ok = _selfcheck(A, trials=30)
    if not ok:
        raise SystemExit('self-check failed - numpy batch math diverges from retrieve_games()')

    print('Baselines...')
    baselines = {}
    for day in DECISION_DAYS:
        for h in HORIZONS:
            target_day = min(29, day + h)
            baselines[(day, h, 'persistence')] = baseline_persistence(A, day, target_day)
            baselines[(day, h, 'corpus_mode')] = baseline_corpus_mode(A, target_day)

    print('Retrieval grid (this is the slow part)...')
    retrieval_results = eval_retrieval(A)

    print('Ridge regression (LOGO)...')
    regression_results, chosen_alpha = eval_regression(A)

    best = best_settings_table(retrieval_results)

    # ---- serialise ----
    def key_str(k):
        return '|'.join(str(x) for x in k)

    dump = {
        'meta': {
            'n_games': A['n'], 'decision_days': DECISION_DAYS, 'horizons': HORIZONS,
            'k_grid': K_GRID, 'lambda_grid': LAM_GRID, 'labels': LABELS,
            'families': {'0': 'DSM/Vadim/Mother-Goose/DECEM shared opening',
                         '1': 'M & M & P & Q', '2': 'Boey'},
            'selfcheck_trials': 30, 'selfcheck_ok': ok,
        },
        'baselines': {key_str(k): v for k, v in baselines.items()},
        'retrieval_grid': {key_str(k): v for k, v in retrieval_results.items()},
        'regression': {key_str(k): v for k, v in regression_results.items()},
        'regression_chosen_alpha': {key_str(k): v for k, v in chosen_alpha.items()},
        'best_by_day_horizon': {
            key_str(k): {'proto': v[1], 'k': v[2], 'lam': v[3], **v[4]}
            for k, v in best.items()
        },
    }
    with open(os.path.join(RESULTS_DIR, 'results.json'), 'w') as fh:
        json.dump(dump, fh, indent=1)

    # ---- markdown summary ----
    lines = []
    lines.append('# Leader-plan retrieval (gate G2) - results summary\n')
    lines.append('240 games (6 teams x 40), decision days %s, horizons +%s.\n' % (DECISION_DAYS, HORIZONS))
    lines.append('Self-check (numpy batch vs pure-python `retrieve_games()`): %d/30 mismatches.\n' % (0 if ok else -1))

    lines.append('\n## Best retrieval setting per (decision day, horizon)\n')
    lines.append('| day | horizon | protocol | k | lambda | n | tile-Hamming mean | composition MAE | frac <=8 tiles |')
    lines.append('|---|---|---|---|---|---|---|---|---|')
    for day in DECISION_DAYS:
        for h in HORIZONS:
            v = best.get((day, h))
            if not v:
                continue
            _, proto, k, lam, rec = v
            lines.append('| %d | +%d | %s | %d | %.2f | %d | %.2f | %.3f | %.3f |' % (
                day, h, proto, k, lam, rec['n_games'], rec['ham_mean'], rec['mae_mean'], rec['within8']))

    lines.append('\n## Baselines\n')
    lines.append('| day | horizon | baseline | tile-Hamming mean | composition MAE | frac <=8 tiles |')
    lines.append('|---|---|---|---|---|---|')
    for day in DECISION_DAYS:
        for h in HORIZONS:
            for name in ('persistence', 'corpus_mode'):
                b = baselines[(day, h, name)]
                lines.append('| %d | +%d | %s | %.2f | %.3f | %.3f |' % (
                    day, h, name, b['ham_mean'], b['mae_mean'], b['within8']))

    lines.append('\n## Ridge regression (composition counts, LOGO, best alpha from {0.1,1,5,10,30})\n')
    lines.append('| day | horizon | alpha | composition MAE |')
    lines.append('|---|---|---|---|')
    for day in DECISION_DAYS:
        for h in HORIZONS:
            r = regression_results[(day, h)]
            lines.append('| %d | +%d | %.1f | %.3f |' % (day, h, r['alpha'], r['mae_mean']))

    lines.append('\n## Protocol comparison at the best k/lambda-per-protocol (composition MAE, horizon +3)\n')
    lines.append('| day | logo | loto | family_logo |')
    lines.append('|---|---|---|---|')
    for day in DECISION_DAYS:
        row = [str(day)]
        for proto in ('logo', 'loto', 'family_logo'):
            best_here = None
            for k in K_GRID:
                for lam in LAM_GRID:
                    rec = retrieval_results[(day, proto, k, lam, 3)]
                    if rec['mae_mean'] is None:
                        continue
                    if best_here is None or rec['mae_mean'] < best_here:
                        best_here = rec['mae_mean']
            row.append('%.3f' % best_here if best_here is not None else 'n/a')
        lines.append('| ' + ' | '.join(row) + ' |')

    with open(os.path.join(RESULTS_DIR, 'summary.md'), 'w') as fh:
        fh.write('\n'.join(lines) + '\n')

    print('Wrote', os.path.join(RESULTS_DIR, 'results.json'))
    print('Wrote', os.path.join(RESULTS_DIR, 'summary.md'))


if __name__ == '__main__':
    main()
