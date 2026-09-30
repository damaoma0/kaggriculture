"""Planner-side API for the frozen cumulative production forecaster.

Load ``forecast_results.json`` after a train-only freeze/test report, then call
``predict_checkpoint`` with the live checkpoint payload.  This module only applies
saved coefficients; it never fits, selects, or reads test outcomes.
"""
import json
from pathlib import Path
import numpy as np

from research_cumulative_forecast import PRODUCTS, model_design


def load_frozen_forecaster(path):
    report = json.loads(Path(path).read_text(encoding="utf-8"))
    return {(int(r["checkpoint_day"]), str(r["horizon"])): r["fitted_model"]
            for r in report["results"] if "fitted_model" in r}


def predict_checkpoint(models, day, horizon, checkpoint_state, shops=None):
    """Return nonnegative remaining and cumulative product forecasts.

    ``checkpoint_state`` has the dataset checkpoint shape, including observation,
    prior_output and cumulative_output.  ``shops`` is optional when the observation
    already contains ``town.unlocked_shops``.
    """
    artifact = models[(int(day), str(horizon))]
    state = dict(checkpoint_state)
    if shops is not None:
        state["shops"] = list(shops)
    record = {"row": {"checkpoints": {str(day): state}, "segments": [{"output": {}} for _ in range(10)]},
              "segments": np.zeros((10, len(PRODUCTS)))}
    x = model_design(record, int(day), horizon, artifact["shop_types"], artifact["state_keys"])[artifact["model"]]
    fit = artifact["fit"]
    if fit["kind"] == "nearest":
        train = np.asarray(fit["x"], float); y = np.asarray(fit["y"], float)
        z = (x - np.asarray(fit["mean"])) / np.asarray(fit["scale"])
        a = (train - np.asarray(fit["mean"])) / np.asarray(fit["scale"])
        predicted = y[np.argmin(np.mean(np.abs(a - z), axis=1))]
    elif fit["kind"] == "own_demand":
        z = (x - np.asarray(fit["mean"])) / np.asarray(fit["scale"])
        predicted = np.asarray(fit["center"]) + np.asarray([z[i] * fit["betas"][i][0] for i in range(len(PRODUCTS))])
    else:
        z = (x - np.asarray(fit["mean"])) / np.asarray(fit["scale"])
        predicted = np.asarray(fit["center"]) + z @ np.asarray(fit["beta"])
    predicted = np.maximum(0, predicted)
    cumulative = np.asarray([checkpoint_state.get("cumulative_output", {}).get(p, 0) for p in PRODUCTS], float) + predicted
    return {"products": PRODUCTS, "remaining_increment": predicted.tolist(), "cumulative_total": cumulative.tolist(),
            "model": artifact["model"], "checkpoint_day": int(day), "horizon": horizon}
