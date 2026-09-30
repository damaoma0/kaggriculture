"""How much does the revealed shop prefix predict final physical production?

Protocol is deliberately fixed before reading scores: each corpus is evaluated
separately, with counts plus an order-sensitive exposure feature, and five
grouped outer folds defined from the *unordered* first four shops.  The latter
is only a split label: features at prefixes one through three never contain
future shops.  Ridge penalties are selected within each outer training pool.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "fresh" / "shop_prefix_predictability"
ALPHAS = (1.0, 10.0, 100.0, 1000.0, None)
FOLDS = 5
BOOTSTRAPS = 2000
BOOTSTRAP_SEED = 20260922


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def prefix_from_umg(game):
    shops = game["checkpoints"]["24"]["observation"]["town"]["unlocked_shops"]
    assert len(shops) == 8, (game["episode"], game["seat"], shops)
    return shops


def prefix_from_primary(game):
    # Recorded daily shop paths; day 24 is the first instant with all eight.
    shops = game["shops"][24]
    assert len(shops) == 8, (game["episode"], game["seat"], shops)
    return shops


def target(game, products):
    return np.array([sum(float(seg["output"].get(p, 0)) for seg in game["segments"])
                     for p in products], dtype=float)


def composition_group(shops, all_shops):
    counts = Counter(shops[:4])
    return ",".join(str(counts[s]) for s in all_shops)


def assigned_fold(group):
    # Stable content hash, rather than corpus order, fixes fold allocation.
    return int(hashlib.sha256(group.encode("utf-8")).hexdigest()[:12], 16) % FOLDS


def features(shops, x, all_shops):
    """Counts plus recency-weighted exposure; the latter preserves prefix order."""
    known = shops[:x]
    counts = np.array([known.count(s) for s in all_shops], dtype=float)
    # First revealed shop has exposure x, last has one.  No unobserved shop is read.
    exposure = np.array([sum(x - i for i, s in enumerate(known) if s == shop)
                         for shop in all_shops], dtype=float)
    return np.concatenate([counts, exposure])


def ordered_position_features(shops, x, all_shops):
    """One-hot shop identity at every observed position.

    Unlike compressed counts/exposure, this is nested information: extending
    x appends eight new columns and leaves every prior position unchanged.
    """
    result = np.zeros((x, len(all_shops)), dtype=float)
    lookup = {shop: j for j, shop in enumerate(all_shops)}
    for i, shop in enumerate(shops[:x]):
        result[i, lookup[shop]] = 1.0
    return result.ravel()


def ridge_predict(x_train, y_train, x_test, alpha):
    mean_y = y_train.mean(axis=0)
    if alpha is None:
        return np.repeat(mean_y[None, :], len(x_test), axis=0)
    mean_x = x_train.mean(axis=0)
    scale_x = np.maximum(x_train.std(axis=0), 1e-6)
    a = (x_train - mean_x) / scale_x
    b = (x_test - mean_x) / scale_x
    # Dual formulation is exact ridge and cheap when features exceed rows.
    gram = a @ a.T + alpha * np.eye(len(a))
    coef = a.T @ np.linalg.solve(gram, y_train - mean_y)
    return np.maximum(0.0, mean_y + b @ coef)


def inner_alpha(x, y, folds, outer):
    keep = folds != outer
    available = sorted(set(folds[keep]))
    losses = np.zeros((len(ALPHAS), y.shape[1]))
    for inner in available:
        valid = keep & (folds == inner)
        train = keep & (folds != inner)
        if not valid.any() or not train.any():
            continue
        # Product-scale normalization avoids wheat units selecting all penalties.
        scale = np.maximum(y[train].std(axis=0), 1.0)
        for ai, alpha in enumerate(ALPHAS):
            p = ridge_predict(x[train], y[train], x[valid], alpha)
            losses[ai] += (((p - y[valid]) / scale) ** 2).sum(axis=0)
    return np.argmin(losses, axis=0), losses


def evaluate(rows, products, shops, corpus, feature_fn, feature_schema):
    y = np.stack([r["target"] for r in rows])
    groups = [r["group"] for r in rows]
    folds = np.array([assigned_fold(g) for g in groups])
    assert len(set(folds)) == FOLDS, f"{corpus}: fewer than five populated group folds"
    metrics, prediction_rows = [], []
    for prefix_len in range(1, 9):
        x = np.stack([feature_fn(r["shops"], prefix_len, shops) for r in rows])
        pred = np.empty_like(y)
        base = np.empty_like(y)
        chosen = []
        for outer in range(FOLDS):
            held = folds == outer
            train = ~held
            best, losses = inner_alpha(x, y, folds, outer)
            candidates = [ridge_predict(x[train], y[train], x[held], alpha) for alpha in ALPHAS]
            pred[held] = np.column_stack([candidates[best[j]][:, j] for j in range(y.shape[1])])
            base[held] = y[train].mean(axis=0)
            chosen.append({"outer_fold": int(outer), "n_train": int(train.sum()),
                           "n_heldout": int(held.sum()),
                           "selected_alpha_by_product": [ALPHAS[int(v)] for v in best],
                           "inner_normalized_sse_by_alpha": losses.tolist()})
        product = {}
        valid_skills = []
        for j, name in enumerate(products):
            sse = float(((pred[:, j] - y[:, j]) ** 2).sum())
            base_sse = float(((base[:, j] - y[:, j]) ** 2).sum())
            skill = None if base_sse <= 1e-12 else 1.0 - sse / base_sse
            product[name] = {"model_sse": sse, "baseline_sse": base_sse,
                             "mae": float(np.abs(pred[:, j] - y[:, j]).mean()), "skill": skill}
            if skill is not None:
                valid_skills.append(skill)
        total_sse = float(((pred - y) ** 2).sum())
        total_base_sse = float(((base - y) ** 2).sum())
        overall = 1.0 - total_sse / total_base_sse if total_base_sse else None
        metric = {"corpus": corpus, "prefix_shops": prefix_len, "n_rows": len(rows),
                  "n_episodes": len(set(r["episode"] for r in rows)),
                  "first4_unordered_groups": len(set(groups)),
                  "feature_schema": feature_schema,
                  "overall_variance_weighted_skill": overall,
                  "macro_product_skill": float(np.mean(valid_skills)) if valid_skills else None,
                  "products": product, "nested_fold_selection": chosen}
        metrics.append(metric)
        for i, r in enumerate(rows):
            prediction_rows.append({"corpus": corpus, "prefix_shops": prefix_len,
                "episode": r["episode"], "seat": r["seat"], "outer_fold": int(folds[i]),
                "first4_unordered_group": r["group"], "revealed_shops": r["shops"][:prefix_len],
                "actual": y[i].tolist(), "prediction": pred[i].tolist(), "training_mean_baseline": base[i].tolist()})
    return metrics, prediction_rows


def bootstrap(metrics, rows, products):
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    by_key = {}
    for row in rows:
        by_key.setdefault((row["corpus"], row["prefix_shops"]), []).append(row)
    intervals = {}
    for key, items in by_key.items():
        episodes = sorted(set(r["episode"] for r in items))
        index = {e: i for i, e in enumerate(episodes)}
        # One seat per current corpora, still structured to preserve episode grouping.
        actual = np.array([r["actual"] for r in items])
        pred = np.array([r["prediction"] for r in items])
        base = np.array([r["training_mean_baseline"] for r in items])
        ep = np.array([index[r["episode"]] for r in items])
        model_sse = np.zeros((len(episodes), len(products)))
        base_sse = np.zeros_like(model_sse)
        for e in range(len(episodes)):
            take = ep == e
            model_sse[e] = ((pred[take] - actual[take]) ** 2).sum(axis=0)
            base_sse[e] = ((base[take] - actual[take]) ** 2).sum(axis=0)
        draws = rng.integers(0, len(episodes), size=(BOOTSTRAPS, len(episodes)))
        ms = model_sse[draws].sum(axis=1)
        bs = base_sse[draws].sum(axis=1)
        skills = 1 - ms / bs
        overall = 1 - ms.sum(axis=1) / bs.sum(axis=1)
        intervals[f"{key[0]}:x{key[1]}"] = {
            "method": "paired episode bootstrap over frozen outer-fold predictions; conditional on fixed CV split",
            "draws": BOOTSTRAPS, "seed": BOOTSTRAP_SEED,
            "overall_variance_weighted_skill_95_ci": np.quantile(overall, [0.025, 0.975]).tolist(),
            "macro_product_skill_95_ci": np.quantile(skills.mean(axis=1), [0.025, 0.975]).tolist(),
            "product_skill_95_ci": {p: np.quantile(skills[:, j], [0.025, 0.975]).tolist()
                                    for j, p in enumerate(products)}}
    for m in metrics:
        m["bootstrap_95_ci"] = intervals[f"{m['corpus']}:x{m['prefix_shops']}"]


def corpus_from_datasets(label, paths, prefix_getter, required_submission=None):
    combined = []
    metadata = []
    products = shops = None
    for path in paths:
        data = load_json(path)
        products = data["products"] if products is None else products
        shops = data.get("shops", shops)
        for game in data["games"]:
            if required_submission is not None and int(game.get("submission", -1)) != required_submission:
                continue
            prefix = prefix_getter(game)
            combined.append({"episode": str(game["episode"]), "seat": int(game["seat"]),
                             "shops": prefix, "target": target(game, products),
                             "group": composition_group(prefix, shops or sorted(set(prefix)) )})
        metadata.append({"path": str(path.relative_to(ROOT)), "games": len(data["games"]),
                         "manifest_sha256": data.get("manifest_sha256")})
    if shops is None:
        shops = sorted({s for r in combined for s in r["shops"]})
        for r in combined:
            r["group"] = composition_group(r["shops"], shops)
    assert len(combined) == len({(r["episode"], r["seat"]) for r in combined}), label
    assert all(len(r["shops"]) == 8 for r in combined)
    return combined, products, shops, metadata


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    # Preserve the already-run, non-nested compressed feature result verbatim.
    # The ordered method below is declared here, before it is evaluated.
    old_metrics = OUT / "metrics.json"
    old_rows = OUT / "predictionrows.json"
    if old_metrics.exists() and old_rows.exists():
        (OUT / "compressed_summary_metrics.json").write_text(old_metrics.read_text(encoding="utf-8"), encoding="utf-8")
        (OUT / "compressed_predictionrows.json").write_text(old_rows.read_text(encoding="utf-8"), encoding="utf-8")
    addendum = {
        "frozen_before_ordered_metrics": True,
        "reason": "Counts plus exposure is lossy across prefix lengths: x=8 can collapse early-shop composition. It is retained as a secondary compressed ablation, not interpreted as a marginal late-shop curve.",
        "primary_feature_schema": "ordered position one-hot: for every revealed position 1..x, one 8-category shop identity block; extending x appends a block and preserves all earlier features",
        "fixed_protocol": "same separate corpora, first-four-unordered SHA256 five-fold grouping, inner-only per-product alpha selection, alpha grid, target, and bootstrap as compressed study; no outer-score feature selection",
        "interpretation": "The primary curve describes held-out predictive association from nested information prefixes. It is not a causal percent of cumulative output explained by shops."
    }
    (OUT / "ordered_method_addendum.json").write_text(json.dumps(addendum, indent=2), encoding="utf-8")
    umg, products, shops, umg_sources = corpus_from_datasets(
        "UMG56266758", [ROOT / "results/fresh/cumulative_planning/dataset_train.json",
                         ROOT / "results/fresh/cumulative_planning/dataset_test.json"], prefix_from_umg,
        required_submission=56266758)
    # Dataset_primary intentionally stays an independent own-m1 corpus.
    m1, p2, shops2, m1_sources = corpus_from_datasets(
        "own_m1_56395605", [ROOT / "results/fresh/tape_gap_plans/dataset_primary.json"], prefix_from_primary)
    assert products == p2
    if shops2 != shops:
        shops = sorted(set(shops) | set(shops2))
        for r in umg + m1:
            r["group"] = composition_group(r["shops"], shops)
    schema = "ordered position one-hot (x blocks of 8 shop categories; nested prefix information)"
    umg_metrics, umg_rows = evaluate(umg, products, shops, "UMG56266758_native", ordered_position_features, schema)
    m1_metrics, m1_rows = evaluate(m1, products, shops, "own_m1_56395605", ordered_position_features, schema)
    all_metrics, all_rows = umg_metrics + m1_metrics, umg_rows + m1_rows
    bootstrap(all_metrics, all_rows, products)
    protocol = {
        "frozen_before_metrics": True,
        "target": "season physical cumulative output: sum of all ten segment output vectors (day 30)",
        "model": "nonnegative linear ridge; ordered position one-hot features; alpha grid [1,10,100,1000,constant]",
        "validation": "fixed five outer folds assigned by SHA256 of unordered first-four-shop composition; alpha selected within outer training data using grouped inner folds and product-scale-normalized SSE",
        "grouping_limitation": "At x=1..3 the first-four composition is used only to assign CV groups, not as a feature. This is conservative split construction but future shops influence which games are grouped together.",
        "interpretation": "Skills are associations in held-out games. Overall is raw-unit variance-weighted SSE reduction versus each fold training mean; macro is an unweighted mean over nonconstant product skills. Neither is a causal percent of output explained."
    }
    (OUT / "ordered_predictionrows.json").write_text(json.dumps({"products": products, "rows": all_rows}, indent=2), encoding="utf-8")
    (OUT / "ordered_metrics.json").write_text(json.dumps({"protocol": protocol, "method_addendum": addendum, "products": products, "shops": shops,
        "corpora": [{"name": "UMG56266758_native", "sources": umg_sources},
                    {"name": "own_m1_56395605", "sources": m1_sources}], "metrics": all_metrics}, indent=2), encoding="utf-8")
    for m in all_metrics:
        print(m["corpus"], "x", m["prefix_shops"], "overall", round(m["overall_variance_weighted_skill"], 4),
              "macro", round(m["macro_product_skill"], 4), flush=True)


if __name__ == "__main__":
    main()
