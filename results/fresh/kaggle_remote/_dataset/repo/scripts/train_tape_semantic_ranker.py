"""Grouped development diagnostics for a small pairwise linear plan ranker.

The target is the four-world screen, which was observed for every candidate.
Unevaluated eight-world candidates are NOT treated as negative labels. Rows
from a single seed share a fold and each seed has equal total training weight.
Historical named recoveries are reserved regression cases, never training rows.
"""
from collections import Counter, defaultdict
from hashlib import sha256
import gzip
import json
from pathlib import Path
import pickle
import statistics
import time

import numpy as np
import tape_semantic_features as S
import value_tape_search as V
from value_tape_search_v3 import assess

OUT = S.PROFILE_PATH.parent
ALPHAS = (0.1, 1.0, 10.0, 100.0)


def load_points():
    audit = json.loads((OUT / 'dataset_audit.json').read_text(encoding='utf-8'))
    assert audit['completed'] == audit['jobs']
    points = []
    for row in sorted(audit['rows'], key=lambda x: x['id']):
        path = OUT / 'checkpoints' / f"{row['id']}.pkl.gz"
        assert sha256(path.read_bytes()).hexdigest() == row['artifact_sha256']
        with gzip.open(path, 'rb') as f:
            points.extend(pickle.load(f))
    return points


def dataset(points):
    rows, timings = [], []
    profiles = S.library()
    for p in points:
        candidates = p['decision']['candidates']
        start = time.perf_counter()
        maps = S.features(p['obs'], p['memory'], candidates, profiles)
        timings.append(time.perf_counter()-start)
        assets = V.asset_keys(p['obs']['farms'][int(p['obs']['player'])])
        base = candidates[0]['predictions'][:4]
        for candidate, features in zip(candidates[1:], maps):
            screen = assess(candidate, candidate['predictions'][:4], base, assets)
            valid = not bool(screen['protection_failures'])
            # A ranking target, not a profitability or admission prediction.
            utility = max(-10000, min(15000, screen['risk_score'])) - (0 if valid else 10000)
            rows.append(dict(query=p['id'], group=p['group'], panel=p['panel'], opponent=p['opponent'],
                route=candidate['route'], episode=candidate['episode'],
                family=profiles[candidate['episode']]['family'], features=features,
                screen_score=screen['risk_score'], screen_valid=valid, utility=utility/5000,
                selected=candidate['route'] == p['decision']['selected'],
                fully_evaluated=candidate['fully_evaluated'], admitted=candidate['admitted']))
    return rows, dict(median_seconds=statistics.median(timings), maximum_seconds=max(timings),
        decisions=len(points), includes_feature_extraction=True)


def fit(rows, alpha):
    names = sorted({key for row in rows for key in row['features']})
    X = np.array([[r['features'].get(k, 0) for k in names] for r in rows], dtype=float)
    y = np.array([r['utility'] for r in rows], dtype=float)
    groups = Counter(r['group'] for r in rows)
    weights = np.array([1/groups[r['group']] for r in rows])
    weights *= len(rows)/weights.sum()
    queries = defaultdict(list)
    for i, row in enumerate(rows):
        queries[row['query']].append(i)
    # Equivalent to within-query pairwise squared loss, without materializing
    # every pair. Constant context features cannot act as an identity lookup.
    for indices in queries.values():
        X[indices] -= X[indices].mean(axis=0)
        y[indices] -= y[indices].mean()
    scale = np.sqrt((weights[:, None]*X*X).sum(axis=0)/weights.sum())
    active = scale > 1e-8
    names = [n for n, ok in zip(names, active) if ok]
    scale = scale[active]
    X = X[:, active]/scale
    # Only training data determine normalization and the coefficients.
    root = np.sqrt(weights)
    Xw, yw = X*root[:, None], y*root
    # Dual solve is cheaper than solving over all semantic interactions.
    kernel = Xw @ Xw.T
    beta = Xw.T @ np.linalg.solve(kernel+alpha*np.eye(len(rows)), yw)
    coefficients = beta/scale
    return dict(kind='pairwise_ridge', alpha=alpha, names=names,
        coefficients=coefficients.tolist(), training_groups=sorted(groups),
        training_rows=len(rows), feature_version=S.VERSION)


def predict(model, features):
    return sum(features.get(k, 0)*w for k, w in zip(model['names'], model['coefficients']))


def metrics(rows, scores):
    queries = defaultdict(list)
    for row, score in zip(rows, scores):
        queries[row['query']].append((row, score))
    details = []
    for query, candidates in queries.items():
        ranked = sorted(candidates, key=lambda p: -p[1])
        selected = [r for r, _ in candidates if r['selected']]
        feasible = [r for r, _ in candidates if r['screen_valid'] and r['screen_score'] > 0]
        best = max(feasible, key=lambda r: r['screen_score']) if feasible else None
        teacher_top = sorted(feasible, key=lambda r: -r['screen_score'])[:2]
        order = [r['route'] for r, _ in ranked]
        details.append(dict(query=query, group=candidates[0][0]['group'], order=order,
            selected=selected[0]['route'] if selected else None,
            selected_rank=order.index(selected[0]['route'])+1 if selected else None,
            best_screen_rank=order.index(best['route'])+1 if best else None,
            teacher_finalist_ranks=[order.index(r['route'])+1 for r in teacher_top],
            best_screen_score=best['screen_score'] if best else 0))
    results = {}
    for k in (1, 2, 3, 4):
        positives = [d for d in details if d['selected_rank'] is not None]
        best = [d for d in details if d['best_screen_rank'] is not None]
        ranks = [r for d in details for r in d['teacher_finalist_ranks']]
        results[f'top{k}'] = dict(selected_retained=sum(d['selected_rank'] <= k for d in positives),
            selected_total=len(positives), best_screen_retained=sum(d['best_screen_rank'] <= k for d in best),
            best_screen_total=len(best), teacher_finalists_retained=sum(r <= k for r in ranks),
            teacher_finalists_total=len(ranks))
    return dict(queries=len(queries), groups=len({r['group'] for r in rows}), **results, details=details)


def compact(result):
    return {k: v for k, v in result.items() if k != 'details'}


def main():
    rows, timing = dataset(load_points())
    (OUT / 'feature_labels.json').write_text(json.dumps(dict(rows=rows, timings=timing), separators=(',', ':')), encoding='utf-8')
    train = [r for r in rows if r['panel'] != 'historical']
    regression = [r for r in rows if r['panel'] == 'historical']
    groups = sorted({r['group'] for r in train})
    all_scores = {str(alpha): [None]*len(train) for alpha in ALPHAS}
    for group in groups:
        learning = [r for r in train if r['group'] != group]
        indices = [i for i, r in enumerate(train) if r['group'] == group]
        assert not {r['group'] for r in learning} & {train[i]['group'] for i in indices}
        for alpha in ALPHAS:
            model = fit(learning, alpha)
            for i in indices:
                all_scores[str(alpha)][i] = predict(model, train[i]['features'])
    cv = {key: metrics(train, scores) for key, scores in all_scores.items()}
    baselines = {
        'shop_distance': metrics(train, [-r['features']['shop_distance'] for r in train]),
        'physical_distance': metrics(train, [-r['features']['hamming'] for r in train]),
        'ideal_cohort_value': metrics(train, [r['features']['heuristic_value'] for r in train]),
    }
    # Predeclared criterion: top2 exact-finalist recall first, then selected
    # recall, then more regularization. Fresh policy evaluation is separate.
    chosen = max(ALPHAS, key=lambda a: (cv[str(a)]['top2']['teacher_finalists_retained'],
        cv[str(a)]['top2']['selected_retained'], a))
    model = fit(train, chosen)
    model.update(native_sha256=V.SOURCE_SHA256,
        profiles_sha256=sha256(S.PROFILE_PATH.read_bytes()).hexdigest(),
        features_sha256=sha256(Path(S.__file__).read_bytes()).hexdigest(),
        training_data_sha256=sha256((OUT / 'feature_labels.json').read_bytes()).hexdigest(),
        criterion='Top2 teacher finalist recall, then selected recall, then larger alpha; grouped development CV only.')
    (OUT / 'ranker.json').write_text(json.dumps(model, indent=2), encoding='utf-8')
    reserved = metrics(regression, [predict(model, r['features']) for r in regression])
    # Cross-source-family stress test. Omit folds with fewer than ten training
    # rows, rather than claiming meaningful performance for an untrained model.
    family_rows = []
    for family in sorted({r['family'] for r in train}):
        learning = [r for r in train if r['family'] != family]
        testing = [r for r in train if r['family'] == family]
        if len(learning) < 10:
            family_rows.append(dict(family=family, training_rows=len(learning), tested=False))
            continue
        fmodel = fit(learning, chosen)
        family_rows.append(dict(family=family, training_rows=len(learning), tested=True,
            metrics=metrics(testing, [predict(fmodel, r['features']) for r in testing])))
    report = dict(rows=len(train), worlds=len(groups), reserved_rows=len(regression), timing=timing,
        alpha=chosen, grouped_cv=cv, baselines=baselines, reserved_regressions=reserved,
        family_stress=family_rows,
        caution='Model and alpha chosen on grouped development diagnostics. Selected outcomes are sparse and correlated. Requires new frozen-world policy validation. Four-world labels do not establish eight-world admission for censored candidates.')
    (OUT / 'training_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(dict(rows=len(train), worlds=len(groups), alpha=chosen, timing=timing,
        grouped_cv={k: compact(v) for k, v in cv.items()},
        baselines={k: compact(v) for k, v in baselines.items()},
        reserved=reserved, families=Counter(r['family'] for r in train)), indent=2), flush=True)


if __name__ == '__main__':
    main()
