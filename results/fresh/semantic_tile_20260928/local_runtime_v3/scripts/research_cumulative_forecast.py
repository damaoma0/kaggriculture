"""Leakage-resistant multi-horizon cumulative production forecasts.

The input is ``results/fresh/cumulative_planning/dataset.json``.  It is deliberately
permissive about field names because the extraction pass may be improved without
changing the evaluation protocol.  The only required facts for an evaluated row are
an episode identifier, a submission identifier, ten segment production vectors, and
a checkpoint state or shop prefix.  Output is written below cumulative_planning;
this program never changes the source ledger or its train/test assignment.

Model choice is made using only rows labelled train.  The held-out split is loaded
only after that choice is frozen.  All grouped folds remove every row of an episode.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
try:
    from mgt_late_choice import DEMAND
except ImportError:
    DEMAND = {}

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "results/fresh/cumulative_planning/dataset.json"
OUT = ROOT / "results/fresh/cumulative_planning/forecast"
PRODUCTS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"]
CHECKPOINTS = (12, 15, 18, 21, 24)
HORIZONS = (3, 6, "end")
ALPHAS = (0.1, 1.0, 10.0, 100.0, 1000.0)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def number(v):
    return float(v) if isinstance(v, (int, float)) and math.isfinite(v) else 0.0


def product_vector(value, products):
    """Accept normal vectors, product maps, or physical produced:* counters."""
    if isinstance(value, list):
        return np.asarray([number(x) for x in value[: len(products)]], float)
    if not isinstance(value, dict):
        return np.zeros(len(products))
    physical = value.get("output", value.get("physical", value))
    return np.asarray([number(physical.get(p, physical.get("produced:" + p, 0))) for p in products], float)


def first(row, *names, default=None):
    for name in names:
        if name in row:
            return row[name]
    return default


def segment_vectors(row, products):
    raw = first(row, "segment_outputs", "outputs", "segments", default=[])
    if isinstance(raw, dict):
        raw = [raw[k] for k in sorted(raw, key=lambda x: int(str(x).replace("segment", "")) if str(x).replace("segment", "").isdigit() else str(x))]
    out = [product_vector(x, products) for x in raw]
    if len(out) != 10:
        raise ValueError("expected exactly ten segment output vectors")
    # Extraction normally stores segment increments.  Cumulative vectors are accepted
    # when explicitly marked; do not infer this from a noisy product alone.
    if row.get("outputs_are_cumulative") or row.get("segment_outputs_are_cumulative"):
        out = [out[0]] + [np.maximum(0, out[i] - out[i - 1]) for i in range(1, len(out))]
    return np.asarray(out, float)


def checkpoint(row, day):
    states = first(row, "checkpoints", "checkpoint_states", "states", default={}) or {}
    if isinstance(states, list):
        for state in states:
            if int(first(state, "day", "checkpoint_day", "segment", default=-1)) in (day, day // 3):
                return state
        return {}
    return states.get(str(day), states.get(day, states.get(str(day // 3), states.get(day // 3, {})))) or {}


def flatten_numbers(value, prefix=""):
    """Stable numeric state map; text/action traces are intentionally excluded."""
    answer = {}
    if isinstance(value, dict):
        for key, child in value.items():
            key = str(key).upper()
            if key in {"ACTION", "ACTIONS", "TRACE", "DIGEST", "HASH", "REWARD"}:
                continue
            answer.update(flatten_numbers(child, prefix + "/" + key))
    elif isinstance(value, (int, float)) and math.isfinite(value):
        answer[prefix] = float(value)
    return answer


def numeric_state(state):
    """Compact own/opponent cohort schema, rather than arbitrary flattened tiles."""
    obs = state.get("observation", state) if isinstance(state, dict) else {}
    player = int(obs.get("player", 0)) if isinstance(obs, dict) else 0
    farms = obs.get("farms", []) if isinstance(obs, dict) else []
    answer = Counter()
    def farm_summary(farm, role):
        for row in farm.get("tiles", []) if isinstance(farm, dict) else []:
            for tile in row if isinstance(row, list) else []:
                if not isinstance(tile, dict): continue
                if isinstance(tile.get("crop"), str):
                    crop = tile["crop"].upper(); answer[f"{role}/CROP/{crop}"] += 1
                    if isinstance(tile.get("planted_day"), (int, float)):
                        age = max(0, min(5, (int(obs.get("day", state.get("day", 0))) - int(tile["planted_day"])) // 3))
                        answer[f"{role}/CROP_AGE/{crop}/{age}"] += 1
                    answer[f"{role}/CROP_YIELD/{crop}"] += number(tile.get("yield_units", tile.get("yield", 0)))
                    answer[f"{role}/CROP_UNWATERED/{crop}"] += number(tile.get("consecutive_unwatered", 0))
                    if number(tile.get("fertilized_until_day", -1)) >= number(obs.get("day", state.get("day", 0))):
                        answer[f"{role}/CROP_FERTILIZED/{crop}"] += 1
                if isinstance(tile.get("animal"), str):
                    animal = tile["animal"].upper(); answer[f"{role}/ANIMAL/{animal}"] += 1
                    answer[f"{role}/ANIMAL_PENDING/{animal}"] += number(tile.get("pending_care_bonus", tile.get("pending_care", 0)))
                    answer[f"{role}/ANIMAL_YIELD/{animal}"] += number(tile.get("yield_units", 0))
                    answer[f"{role}/ANIMAL_UNFED/{animal}"] += number(tile.get("consecutive_unfed", 0))
                    if isinstance(tile.get("placed_day"), (int, float)):
                        age = max(0, min(5, (int(obs.get("day", state.get("day", 0))) - int(tile["placed_day"])) // 3))
                        answer[f"{role}/ANIMAL_AGE/{animal}/{age}"] += 1
        answer[f"{role}/CASH"] += number(farm.get("money", farm.get("cash", 0))) if isinstance(farm, dict) else 0
    for idx, farm in enumerate(farms[:2]): farm_summary(farm, "OWN" if idx == player else "OPP")
    private = obs.get("private", state.get("private", {})) if isinstance(obs, dict) else {}
    for section in ("inventories", "seeds", "shed", "stock"):
        value = private.get(section, {}) if isinstance(private, dict) else {}
        if isinstance(value, dict):
            for key, val in value.items(): answer[f"OWN/{section.upper()}/{str(key).upper()}"] += number(val)
        elif isinstance(value, list):
            for entry in value:
                if isinstance(entry, dict):
                    for key, val in entry.items(): answer[f"OWN/{section.upper()}/{str(key).upper()}"] += number(val)
    # Prices, public supply and town stock are visible at the checkpoint.
    for section in ("market", "town"):
        visible = obs.get(section, {}) if isinstance(obs, dict) else {}
        for key, val in flatten_numbers(visible, "MARKET/" + section.upper()).items():
            answer[key] += val
    return {key: float(value) for key, value in answer.items()}


def shops_before(row, day, state):
    shops = first(state, "shops", "unlocked_shops", default=None)
    if shops is None and isinstance(state.get("observation"), dict):
        town = state["observation"].get("town", {})
        shops = first(town, "unlocked_shops", "shops", default=None)
    if shops is None:
        shops = first(row, "shops", "shop_order", "order", default=[])
        if isinstance(shops, dict):
            shops = shops.get(str(day), shops.get(str(day // 3), []))
        else:
            shops = shops[: day // 3]
    return [str(s) for s in (shops or [])]


def shop_features(shops, all_shops, day):
    counts = np.asarray([shops.count(s) for s in all_shops], float)
    timing = np.asarray([sum(max(0, day - 3 * (i + 1)) for i, x in enumerate(shops) if x == s) for s in all_shops], float)
    return counts, timing


def state_features(state, products):
    flat = numeric_state(state)
    # Restrict state to physical/economic summaries.  This avoids silently fitting
    # future production labels that happen to be placed in a checkpoint payload.
    allowed = ("OWN/", "OPP/", "BOARD", "COHORT", "AGE", "FARM", "TILE", "INVENTOR", "CASH", "MONEY", "HAND", "HIRE", "SEED", "STOCK", "MARKET", "OPPONENT")
    keys = sorted(k for k in flat if any(token in k for token in allowed) and "PRODUCED" not in k and "OUTPUT" not in k)
    # Fixed cap keeps the nonlinear design modest for small historical versions.
    base = np.asarray([flat[k] for k in keys], float)
    # Capacity summaries are intentionally crude but physically interpretable:
    # active crop/animal cohort counts can generate output; current inventory cannot.
    cap = []
    for product in products:
        aliases = {"WHEAT": ("WHEAT",), "CARROT": ("CARROT",), "TOMATO": ("TOMATO",),
                   "STRAWBERRY": ("STRAWBERRY",), "MELON": ("MELON",), "EGG": ("GOOSE", "EGG"),
                   "MILK": ("COW", "MILK"), "WOOL": ("SHEEP", "WOOL"), "FERTILIZER": ("SHEEP", "COW", "GOOSE")}[product]
        cap.append(sum(v for k, v in flat.items() if any(a in k for a in aliases) and
                       (k.startswith("OWN/CROP/") or k.startswith("OWN/ANIMAL/"))))
    return base, np.asarray(cap, float), keys


def normalise(rows, products):
    records = []
    for index, row in enumerate(rows):
        try:
            segments = segment_vectors(row, products)
        except ValueError:
            continue
        records.append({"row": row, "episode": str(first(row, "episode", "episode_id", "id", default=index)),
                        "seat": first(row, "seat", "player", default=None),
                        "submission": str(first(row, "submission", "submission_id", "version", default="unknown")),
                        "split": str(first(row, "split", "partition", default="train")).lower(),
                        "segments": np.maximum(0, segments)})
    return records


def zfit(x):
    mu = x.mean(0); scale = np.maximum(x.std(0), 1e-6)
    return mu, scale


def ridge_predict(train_x, train_y, test_x, alpha):
    mu, scale = zfit(train_x)
    x = (train_x - mu) / scale; z = (test_x - mu) / scale
    cy = train_y.mean(0)
    if x.shape[0] < x.shape[1]:
        beta = x.T @ np.linalg.solve(x @ x.T + alpha * np.eye(x.shape[0]), train_y - cy)
    else:
        beta = np.linalg.solve(x.T @ x + alpha * np.eye(x.shape[1]), x.T @ (train_y - cy))
    return cy + z @ beta


def nearest_predict(train_x, train_y, test_x):
    mu, scale = zfit(train_x)
    a = (train_x - mu) / scale; b = (test_x - mu) / scale
    answer = []
    for row in b:
        answer.append(train_y[np.argmin(np.mean(np.abs(a - row), axis=1))])
    return np.asarray(answer)


def own_demand_predict(train_x, train_y, test_x, alpha):
    """One revealed-demand scalar per output product, matching the old baseline."""
    return np.column_stack([ridge_predict(train_x[:, [j]], train_y[:, [j]], test_x[:, [j]], alpha)[:, 0]
                            for j in range(train_y.shape[1])])


def fitted_artifact(x, y, model, alpha):
    """JSON-safe full-development fit for planner-side checkpoint prediction."""
    mu, scale = zfit(x)
    a = (x - mu) / scale
    center = y.mean(0)
    if model == "nearest_state":
        return {"kind": "nearest", "mean": mu.tolist(), "scale": scale.tolist(), "x": x.tolist(), "y": y.tolist()}
    if model == "own_product_demand_ridge":
        betas = [np.linalg.solve(a[:, [j]].T @ a[:, [j]] + alpha * np.eye(1), a[:, [j]].T @ (y[:, [j]] - center[[j]])).ravel().tolist() for j in range(y.shape[1])]
        return {"kind": "own_demand", "mean": mu.tolist(), "scale": scale.tolist(), "center": center.tolist(), "betas": betas}
    beta = (a.T @ np.linalg.solve(a @ a.T + alpha * np.eye(a.shape[0]), y - center)
            if a.shape[0] < a.shape[1] else np.linalg.solve(a.T @ a + alpha * np.eye(a.shape[1]), a.T @ (y - center)))
    return {"kind": "ridge", "mean": mu.tolist(), "scale": scale.tolist(), "center": center.tolist(), "beta": beta.tolist()}


def predict_fit(fit, x):
    x = np.asarray(x, float)
    if fit["kind"] == "nearest":
        train = np.asarray(fit["x"], float); y = np.asarray(fit["y"], float)
        z = (x - np.asarray(fit["mean"])) / np.asarray(fit["scale"])
        a = (train - np.asarray(fit["mean"])) / np.asarray(fit["scale"])
        return y[np.argmin(np.mean(np.abs(a[None, :, :] - z[:, None, :]), axis=2), axis=1)]
    z = (x - np.asarray(fit["mean"])) / np.asarray(fit["scale"])
    if fit["kind"] == "own_demand":
        return np.asarray(fit["center"]) + np.column_stack([z[:, i] * fit["betas"][i][0] for i in range(len(PRODUCTS))])
    return np.asarray(fit["center"]) + z @ np.asarray(fit["beta"])


def folds(groups):
    labels = sorted(set(groups))
    if len(labels) < 3:
        return []
    # Deterministic five-fold group allocation bounds the nested-CV work while
    # keeping every row/seat from an episode in one holdout fold.
    buckets = [set(labels[i::min(5, len(labels))]) for i in range(min(5, len(labels)))]
    return [(np.asarray([g not in bucket for g in groups]), np.asarray([g in bucket for g in groups])) for bucket in buckets]


def oof_prediction(x, y, groups, model):
    """Nested group-CV: choose alpha within each outer development fold."""
    pred = np.full_like(y, np.nan, dtype=float)
    chosen = []
    for keep, hold in folds(groups):
        if model == "nearest_state":
            pred[hold] = nearest_predict(x[keep], y[keep], x[hold]); chosen.append(None); continue
        inner_groups = np.asarray(groups)[keep]
        losses = []
        for alpha in ALPHAS:
            parts = []
            for ik, ih in folds(inner_groups):
                fit = own_demand_predict if model == "own_product_demand_ridge" else ridge_predict
                err = fit(x[keep][ik], y[keep][ik], x[keep][ih], alpha) - y[keep][ih]
                scale = np.maximum(np.std(y[keep][ik], axis=0), 1.0)
                parts.append((err / scale) ** 2)
            losses.append(sum(float(np.sum(part)) for part in parts) if parts else np.inf)
        alpha = ALPHAS[int(np.argmin(losses))]
        fit = own_demand_predict if model == "own_product_demand_ridge" else ridge_predict
        pred[hold] = fit(x[keep], y[keep], x[hold], alpha)
        chosen.append(alpha)
    return pred, chosen


def model_design(record, day, horizon, all_shops, state_keys):
    state = checkpoint(record["row"], day)
    shops = shops_before(record["row"], day, state)
    counts, timing = shop_features(shops, all_shops, day)
    prior = product_vector(state.get("cumulative_output", {}), PRODUCTS)
    if not np.any(prior):
        prior = record["segments"][: day // 3].sum(0)
    prior_window = product_vector(state.get("prior_output", {}), PRODUCTS)
    base, cap, keys = state_features(state, PRODUCTS)
    # State schemas may vary.  Align by observed key universe and zero-fill absent.
    flat = numeric_state(state)
    aligned = np.asarray([flat.get(key, 0.0) for key in state_keys], float)
    rem = 30 - day if horizon == "end" else horizon
    capacity = cap * rem
    interaction = np.concatenate([capacity, capacity * (1 + counts.sum()), capacity * (1 + prior / 10.0)])
    demand = np.asarray([sum(number(DEMAND.get(shop, {}).get(product, 0)) for shop in shops) for product in PRODUCTS], float)
    return {"count_ridge": counts,
            "count_timing_ridge": np.concatenate([counts, timing]),
            "own_product_demand_ridge": demand,
            "state_ridge": np.concatenate([counts, timing, prior, prior_window, aligned, capacity]),
            "capacity_interaction_ridge": np.concatenate([counts, timing, prior, prior_window, aligned, interaction]),
            "nearest_state": np.concatenate([counts, timing, prior, prior_window, aligned, capacity])}


def target(record, day, horizon):
    start = day // 3
    end = 10 if horizon == "end" else min(10, start + horizon // 3)
    if end <= start:
        return None
    return record["segments"][start:end].sum(0)


def metric(y, p, products, scale=None):
    err = p - y
    per_rmse = np.sqrt(np.mean(err ** 2, axis=0))
    # A supplied scale is always the training target dispersion.  In particular,
    # held-out and transfer reporting must never normalize with test outcomes.
    scale = np.maximum(np.std(y, axis=0), 1.0) if scale is None else np.maximum(np.asarray(scale, float), 1.0)
    return {"mae": float(np.abs(err).mean()), "rmse": float(np.sqrt(np.mean(err ** 2))),
            "normalized_rmse": float(np.mean(per_rmse / scale)),
            "per_product": {name: {"mae": float(np.abs(err[:, i]).mean()), "rmse": float(np.sqrt(np.mean(err[:, i] ** 2))),
                                    "bias": float(err[:, i].mean())} for i, name in enumerate(products)}}


def run_one(records, day, horizon, all_shops, products, frozen_choice=None):
    eligible = [(r, target(r, day, horizon)) for r in records]
    eligible = [(r, y) for r, y in eligible if y is not None]
    train = [(r, y) for r, y in eligible if r["split"] != "test"]
    test = [(r, y) for r, y in eligible if r["split"] == "test"]
    if len(train) < 6 or len({r["episode"] for r, _ in train}) < 3:
        return {"checkpoint_day": day, "horizon": horizon, "status": "insufficient grouped training rows", "n_train": len(train), "n_test": len(test)}
    state_keys = sorted(set().union(*(numeric_state(checkpoint(r["row"], day)).keys() for r, _ in train)))
    # Keep only numeric physical/economic checkpoint features and a modest dimension.
    allowed = ("OWN/", "OPP/", "BOARD", "COHORT", "AGE", "FARM", "TILE", "INVENTOR", "CASH", "MONEY", "HAND", "HIRE", "SEED", "STOCK", "MARKET", "OPPONENT")
    state_keys = [k for k in state_keys if any(a in k for a in allowed) and "PRODUCED" not in k and "OUTPUT" not in k]
    names = ("count_ridge", "count_timing_ridge", "own_product_demand_ridge", "state_ridge", "capacity_interaction_ridge", "nearest_state")
    y = np.asarray([v for _, v in train]); groups = [r["episode"] for r, _ in train]
    train_scale = np.maximum(np.std(y, axis=0), 1.0)
    designs = {name: np.asarray([model_design(r, day, horizon, all_shops, state_keys)[name] for r, _ in train]) for name in names}
    dev = {}
    for name in names:
        p, alpha = oof_prediction(designs[name], y, groups, name)
        dev[name] = {"pred": np.maximum(0, p), "alphas": alpha, "episode_cv": metric(y, np.maximum(0, p), products)}
        # Separate composition-held-out diagnostic; never used to select the model.
        # The frozen test deliberately uses unseen *first-four* count compounds.
        # Match that shift here; order is deliberately discarded.
        comp = ["|".join(str(x) for x in shop_features(shops_before(r["row"], day, checkpoint(r["row"], day))[:4], all_shops, day)[0].astype(int)) for r, _ in train]
        cp, _ = oof_prediction(designs[name], y, comp, name)
        dev[name]["composition_cv"] = metric(y, np.maximum(0, cp), products) if not np.isnan(cp).any() else {"status": "too few distinct compositions"}
    development_winner = min(names, key=lambda n: dev[n]["episode_cv"]["normalized_rmse"])
    selected = frozen_choice.get("model", development_winner) if frozen_choice else development_winner
    if selected not in names:
        raise ValueError(f"frozen model {selected!r} is not available")
    # Calibration uses only the selected model's out-of-fold development residuals.
    residual = np.abs(y - dev[selected]["pred"])
    q = np.quantile(residual, 0.9, axis=0).tolist()
    choices = [a for a in dev[selected]["alphas"] if a is not None]
    deployment_alpha = float(np.median(choices)) if choices else None
    if frozen_choice and frozen_choice.get("alpha") is not None:
        deployment_alpha = float(frozen_choice["alpha"])
    candidate_alphas = {name: (float(np.median([a for a in dev[name]["alphas"] if a is not None]))
                               if any(a is not None for a in dev[name]["alphas"]) else None) for name in names}
    if frozen_choice and frozen_choice.get("candidate_alphas"):
        candidate_alphas.update({k: v for k, v in frozen_choice["candidate_alphas"].items() if k in candidate_alphas})
    summary = {"checkpoint_day": day, "horizon": horizon, "n_train": len(train), "n_test": len(test),
               "distinct_train_episodes": len(set(groups)), "state_feature_count": len(state_keys),
               "selection_rule": "lowest nested episode-held-out development product-normalized RMSE; test split excluded", "selected_model": selected,
               "development_winner": development_winner, "deployment_alpha": deployment_alpha, "candidate_alphas": candidate_alphas,
               "training_target_scale_by_product": dict(zip(products, train_scale.tolist())),
               "development": {n: {k: v for k, v in d.items() if k != "pred"} for n, d in dev.items()},
               "interval": {"method": "empirical 90% marginal absolute-residual band from selected-model development OOF residuals; model selection precedes it, so this is not exact conformal coverage", "half_width_by_product": dict(zip(products, q))}}
    summary["development_selected_oof_rows"] = [
        {"episode": r["episode"], "seat": r["seat"], "actual_increment": yy.tolist(), "prediction_increment": pp.tolist(),
         "actual_cumulative": (r["segments"][: day // 3].sum(0) + yy).tolist(),
         "prediction_cumulative": (r["segments"][: day // 3].sum(0) + pp).tolist()}
        for (r, yy), pp in zip(train, dev[selected]["pred"])]
    fit_alpha = deployment_alpha if deployment_alpha is not None else 10.0
    summary["fitted_model"] = {"model": selected, "alpha": deployment_alpha, "state_keys": state_keys, "shop_types": all_shops,
                                "checkpoint_day": day, "horizon": horizon,
                                "fit": fitted_artifact(designs[selected], y, selected, fit_alpha)}
    if test:
        test_designs = {name: np.asarray([model_design(r, day, horizon, all_shops, state_keys)[name] for r, _ in test]) for name in names}
        # Every candidate is evaluated with its development-frozen penalty, so the
        # final report can compare the selected model to each baseline fairly.
        candidate_test = {}
        for name in names:
            alpha0 = candidate_alphas[name] if candidate_alphas[name] is not None else 10.0
            fit = nearest_predict if name == "nearest_state" else own_demand_predict if name == "own_product_demand_ridge" else ridge_predict
            pp = fit(designs[name], y, test_designs[name], alpha0) if name != "nearest_state" else fit(designs[name], y, test_designs[name])
            candidate_test[name] = np.maximum(0, pp)
        alpha = deployment_alpha if deployment_alpha is not None else 10.0
        pred = candidate_test[selected]
        pred = np.maximum(0, pred); yt = np.asarray([v for _, v in test])
        coverage = ((yt >= pred - np.asarray(q)) & (yt <= pred + np.asarray(q))).mean(0)
        summary["frozen_test"] = {"fit_alpha": alpha if selected != "nearest_state" else None, "metrics": metric(yt, pred, products, train_scale),
                                  "all_frozen_candidates": {name: {"alpha": candidate_alphas[name], "metrics": metric(yt, pp, products, train_scale),
                                      "rows": [{"episode": r["episode"], "seat": r["seat"], "actual": yy.tolist(), "prediction": ppi.tolist()}
                                               for (r, yy), ppi in zip(test, pp)]} for name, pp in candidate_test.items()},
                                  "coverage_by_product": dict(zip(products, [float(x) for x in coverage])),
                                  "mean_coverage": float(coverage.mean()), "rows": [
                                      {"episode": r["episode"], "seat": r["seat"], "actual": yy.tolist(), "prediction": pp.tolist(),
                                       "actual_cumulative": (r["segments"][: day // 3].sum(0) + yy).tolist(),
                                       "prediction_cumulative": (r["segments"][: day // 3].sum(0) + pp).tolist()}
                                      for (r, yy), pp in zip(test, pred)]}
    return summary


def reconcile_test_horizons(outcome):
    """Use a cumulative maximum to enforce nested nonnegative horizon totals."""
    by_day = defaultdict(list)
    for result in outcome["results"]:
        if "frozen_test" in result:
            by_day[result["checkpoint_day"]].append(result)
    for day, results in by_day.items():
        ordered = sorted(results, key=lambda r: (999 if r["horizon"] == "end" else r["horizon"]))
        if len(ordered) < 2: continue
        indexed = [{(str(x["episode"]), str(x["seat"])): x for x in r["frozen_test"]["rows"]} for r in ordered]
        shared = set.intersection(*(set(x) for x in indexed))
        for key in shared:
            pred = np.maximum.accumulate(np.asarray([indexed[i][key]["prediction"] for i in range(len(indexed))], float), axis=0)
            for i, result in enumerate(ordered):
                row = indexed[i][key]
                row["cumulative_max_prediction"] = pred[i].tolist()
                row["cumulative_max_prediction_total"] = (np.asarray(row["prediction_cumulative"]) - np.asarray(row["prediction"]) + pred[i]).tolist()
        for i, result in enumerate(ordered):
            rows = [indexed[i][key] for key in shared]
            actual = np.asarray([x["actual"] for x in rows], float)
            projected = np.asarray([x["cumulative_max_prediction"] for x in rows], float)
            q = np.asarray([result["interval"]["half_width_by_product"][p] for p in outcome["products"]])
            coverage = ((actual >= projected - q) & (actual <= projected + q)).mean(0)
            scale = [result["training_target_scale_by_product"][p] for p in outcome["products"]]
            result["frozen_test"]["cumulative_max_metrics"] = metric(actual, projected, outcome["products"], scale)
            result["frozen_test"]["cumulative_max_coverage_by_product"] = dict(zip(outcome["products"], [float(x) for x in coverage]))
            result["frozen_test"]["cumulative_max_mean_coverage"] = float(coverage.mean())
            result["frozen_test"]["cumulative_max_projection"] = "elementwise maximum across nested next3/next6/end increments for the same checkpoint/episode/seat"


def domain_transfer(outcome, records, products):
    """Outcome-independent transfer evaluation of already frozen UMG fits."""
    report = []
    for result in outcome["results"]:
        artifact = result.get("fitted_model")
        if not artifact: continue
        day, horizon = result["checkpoint_day"], result["horizon"]
        rows = [(r, target(r, day, horizon)) for r in records]
        rows = [(r, y) for r, y in rows if y is not None]
        if not rows: continue
        x = np.asarray([model_design(r, day, horizon, artifact["shop_types"], artifact["state_keys"])[artifact["model"]] for r, _ in rows])
        p = np.maximum(0, predict_fit(artifact["fit"], x)); y = np.asarray([v for _, v in rows])
        scale = [result["training_target_scale_by_product"][name] for name in products]
        report.append({"checkpoint_day": day, "horizon": horizon, "n": len(rows), "model": artifact["model"], "metrics": metric(y, p, products, scale)})
    return report


def legacy_rows():
    """Development-only fallback for the existing 76 historical trajectories."""
    src = ROOT / "results/fresh/leader_segments"
    sample = read(src / "sample.json")["sample"]
    identities = {str(x["id"]): x["agents"] for x in sample}
    rows = []
    for path in src.glob("segments-*.json"):
        game = read(path); eid = str(game["episode"])
        for seat in game["seats"]:
            sub = identities[eid][seat["seat"]]["sub"]
            segments = [s.get("physical", {}) for s in seat["segments"]]
            checkpoints = {str(i * 3): {"board": seat["segments"][i].get("board_start", {}), "shops": game["shops_by_segment"].get(str(i), [])} for i in range(10)}
            rows.append({"episode": eid, "seat": seat["seat"], "submission": sub, "split": "train", "segments": segments, "checkpoints": checkpoints})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA)
    ap.add_argument("--test-data", type=Path, help="separate frozen test dataset; it is appended only with split=test")
    ap.add_argument("--write-freeze", action="store_true", help="write a selection manifest after a train-only run")
    ap.add_argument("--frozen", type=Path, help="use the fixed model/alpha choices in this manifest")
    ap.add_argument("--domain-data", type=Path, help="separate outcome-independent transfer panel; never used for fitting")
    ap.add_argument("--out", type=Path, help="output directory; use a separate path for exploratory versions")
    ap.add_argument("--submission", default="56266758", help="primary version; use all for exploratory pooled results")
    ap.add_argument("--legacy-dev", action="store_true", help="use existing 76 historical trajectories only, no frozen test")
    args = ap.parse_args()
    global OUT
    if args.out:
        OUT = args.out
    payload = read(args.data) if args.data.exists() else {"rows": legacy_rows(), "source": "legacy-development-fallback"} if args.legacy_dev else None
    if payload is None:
        raise SystemExit(f"missing {args.data}; run the dataset builder first (or pass --legacy-dev)")
    products = payload.get("products", PRODUCTS)
    rows = list(first(payload, "rows", "games", "submissions", default=[]))
    if args.test_data:
        test_payload = read(args.test_data)
        extra = list(first(test_payload, "rows", "games", "submissions", default=[]))
        for row in extra:
            row["split"] = "test"
        rows.extend(extra)
    records = normalise(rows, products)
    if args.submission != "all": records = [r for r in records if r["submission"] == str(args.submission)]
    train_episodes = {r["episode"] for r in records if r["split"] != "test"}
    test_episodes = {r["episode"] for r in records if r["split"] == "test"}
    overlap = train_episodes & test_episodes
    assert not overlap, f"episode split leakage: {sorted(overlap)}"
    # Preserve dataset's fixed eight-shop taxonomy even when a filtered version
    # happened not to observe one type.
    shops = list(payload.get("shops", [])) or sorted(set(s for r in records for day in CHECKPOINTS for s in shops_before(r["row"], day, checkpoint(r["row"], day))))
    frozen = read(args.frozen) if args.frozen else None
    if frozen and args.data.exists():
        expected_hash = frozen.get("development_sha256")
        actual_hash = hashlib.sha256(args.data.read_bytes()).hexdigest()
        if expected_hash and expected_hash != actual_hash:
            raise SystemExit("frozen selection was made on a different development dataset hash; refuse to evaluate")
    frozen_choices = frozen.get("choices", {}) if frozen else {}
    outcome = {"schema": "cumulative-forecast-v1", "source": str(args.data), "test_source": str(args.test_data) if args.test_data else None, "primary_submission": args.submission,
               "products": products, "shop_types": shops, "protocol": {"test_rule": "rows labelled test are never used for model/alpha/interval selection", "group_rule": "all seats/rows of an episode are held out together", "targets": "nonnegative future cumulative production increments at 3, 6, and season-end horizons", "models": ["count_ridge", "count_timing_ridge", "own_product_demand_ridge", "state_ridge", "capacity_interaction_ridge", "nearest_state"]},
               "records": {"total": len(records), "train": sum(r["split"] != "test" for r in records), "test": sum(r["split"] == "test" for r in records), "episodes": len(set(r["episode"] for r in records))}, "results": []}
    for day in CHECKPOINTS:
        for horizon in HORIZONS:
            if horizon != "end" and day + horizon > 30: continue
            key = f"{day}/{horizon}"
            outcome["results"].append(run_one(records, day, horizon, shops, products, frozen_choices.get(key)))
    reconcile_test_horizons(outcome)
    if args.domain_data:
        domain_payload = read(args.domain_data)
        domain_records = normalise(list(first(domain_payload, "rows", "games", "submissions", default=[])), products)
        outcome["domain_transfer"] = {"source": str(args.domain_data), "rule": "frozen UMG models applied without refitting or selection", "results": domain_transfer(outcome, domain_records, products)}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "forecast_results.json").write_text(json.dumps(outcome, indent=2), encoding="utf-8")
    if args.write_freeze:
        source_hash = hashlib.sha256(args.data.read_bytes()).hexdigest() if args.data.exists() else "legacy-development-fallback"
        choices = {f"{r['checkpoint_day']}/{r['horizon']}": {"model": r["selected_model"], "alpha": r.get("deployment_alpha"), "candidate_alphas": r.get("candidate_alphas", {})}
                   for r in outcome["results"] if "selected_model" in r}
        manifest = {"schema": "cumulative-forecast-freeze-v1", "development_data": str(args.data), "development_sha256": source_hash,
                    "submission": args.submission, "choices": choices,
                    "rule": "Created from training rows only; use with --frozen and --test-data. Do not replace after reading test metrics."}
        (OUT / "frozen_selection.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    selected = Counter(x.get("selected_model", "unavailable") for x in outcome["results"])
    print(json.dumps({"records": outcome["records"], "selected_models": selected, "output": str(OUT / "forecast_results.json")}, indent=2, default=dict))


if __name__ == "__main__":
    main()
