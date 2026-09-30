# Cumulative production forecasting protocol

This is a forward forecast of harvested or collected product units, excluding purchases and sales. At each day-12, 15, 18, 21, or 24 checkpoint, it predicts the nonnegative production increment for the next three days, next six days, and the rest of the season. A forecast can therefore be converted to a cumulative total by adding the checkpoint's already observed production. It is not a production plan, feasibility proof, profit forecast, or a claim that copying a historical farm will win.

## Data and isolation

`results/fresh/cumulative_planning/dataset_train.json` and `dataset_test.json` contain one row per submitted game seat. Each row has an episode, seat, submission, fixed split, ten exact segment output vectors, and complete checkpoint observations. A group is an **episode**, so every row from that episode is absent from the corresponding training fold. The primary analysis is submission `56266758`; other versions are separate exploratory populations and are never silently pooled into its fit.

The planned primary partition has 75 train and 30 test games. The 30 test episodes use shop-count compositions not present in the old 30-game data; this is intentionally a difficult distribution change. Test labels must remain unread while choosing a model.

Run selection only on the training file:

```powershell
.venv\Scripts\python.exe scripts\research_cumulative_forecast.py --data results\fresh\cumulative_planning\dataset_train.json --submission 56266758 --write-freeze
```

This writes `results/fresh/cumulative_planning/forecast/frozen_selection.json`, including the development file hash, selected model, and fixed ridge penalty for each checkpoint/horizon. Then make one frozen test report:

```powershell
.venv\Scripts\python.exe scripts\research_cumulative_forecast.py --data results\fresh\cumulative_planning\dataset_train.json --test-data results\fresh\cumulative_planning\dataset_test.json --submission 56266758 --frozen results\fresh\cumulative_planning\forecast\frozen_selection.json
```

`scripts/cumulative_forecast_model.py` exposes `load_frozen_forecaster(path)` and `predict_checkpoint(models, day, horizon, checkpoint_state, shops=None)`. It applies the full-development fitted artifact stored in the report and does not fit or select anything.

## Candidate models fixed before test

All models fit products separately in a multivariate ridge implementation with feature standardization learned in each training fold.

| Model | Checkpoint information |
|---|---|
| `count_ridge` | Revealed shop-type counts |
| `count_timing_ridge` | Counts plus days since each shop reveal |
| `state_ridge` | Counts/timing plus previous output, observed farm/cohort/board, private and opponent summaries |
| `capacity_interaction_ridge` | State model plus crop/animal cohort capacity proxies and compact capacity-by-demand/output interactions |
| `nearest_state` | Whole-episode-excluded nearest observed checkpoint donor |
| `own_product_demand_ridge` | A low-dimensional per-product revealed-shop-demand baseline |

The capacity terms are deliberately approximate: standing crops and animals can produce, while stored inventory cannot. The state schema includes own and opponent crop counts by age bucket, crop yield/watering/fertilizer condition, animal age/yield/care/feeding condition, private seeds/inventory/shed, cash, and visible market/town quantities. It does not reconstruct exact future actions, pathing, or stochastic sales; trace/action/hash fields and future-output labels are excluded.

For every outer episode fold, ridge penalty is chosen again from `{0.1, 1, 10, 100, 1000}` with inner episode folds. Both levels use deterministic five-fold episode groups. The selected deployment model is the lowest nested episode-held-out product-normalized RMSE, so wheat-scale units cannot dominate the choice. A second holdout grouped by the unordered count vector of the first four shops is reported as a harsher diagnostic and is never used for selection.

## Constraints and uncertainty

Predicted increments are clipped at zero. For each checkpoint/episode/seat, the frozen-test report applies an elementwise cumulative maximum to the nested horizon predictions, enforcing `next 3 ≤ next 6 ≤ end`; it evaluates that cumulative-max projection and recalculates its interval coverage as well as reporting raw predictions. The evaluation reports product MAE, RMSE, normalized RMSE, and bias. A 90% marginal empirical band is `prediction ± q`, where `q` is the 90th percentile of absolute selected-model out-of-fold development residuals. Because model selection happens before this residual calculation, it is not an exact conformal interval; its test coverage is descriptive and can miss under a new composition distribution.

The report records every frozen-test prediction with episode and seat so aggregate results can be checked without treating correlated seats or repeated checkpoint rows as independent games. It does not claim an improvement over the v10 router-selected tape unless a separately supplied tape baseline is evaluated under the same frozen episode split.

## Frozen UMG result

The split audit supplied with the corpus found 75 unique train seeds and 30 unique test seeds, with zero seed, episode, or first-four unordered-count-composition overlap. Identities, compact action checks, rewards, and raw replay hashes passed in the corpus audit. Selection was frozen from train only: capacity-interaction ridge won 12 of 15 checkpoint/horizon cells, timing ridge won two, and state ridge won one.

| Checkpoint | Horizon | Frozen model | Test MAE | Product-normalized RMSE | Empirical 90% coverage |
|---:|---|---|---:|---:|---:|
| 12 | 3 days | capacity interaction | 1.37 | 0.35 | 93.0% |
| 12 | 6 days | capacity interaction | 3.52 | 0.55 | 92.2% |
| 12 | end | count + timing | 24.83 | 0.59 | 86.3% |
| 15 | 3 days | capacity interaction | 1.51 | 0.23 | 93.7% |
| 15 | 6 days | state ridge | 5.34 | 0.49 | 87.0% |
| 15 | end | count + timing | 20.40 | 0.53 | 85.6% |
| 18 | 3 days | capacity interaction | 2.15 | 0.31 | 90.7% |
| 18 | 6 days | capacity interaction | 5.83 | 0.32 | 88.1% |
| 18 | end | capacity interaction | 15.07 | 0.37 | 91.1% |
| 21 | 3 days | capacity interaction | 2.77 | 0.29 | 88.5% |
| 21 | 6 days | capacity interaction | 7.63 | 0.36 | 87.0% |
| 21 | end | capacity interaction | 12.15 | 0.37 | 90.0% |
| 24 | 3 days | capacity interaction | 3.53 | 0.27 | 90.0% |
| 24 | 6 days/end | capacity interaction | 7.15 | 0.26 | 94.4% |

For end-of-season forecasts, MAE falls from 24.83 at day 12 to 7.15 at day 24. At day 24, product MAE is wheat 17.37, carrot 14.82, tomato 4.06, strawberry 7.21, melon 0.00, egg 3.89, milk 5.44, wool 6.40, and fertilizer 5.13. Every frozen candidate is evaluated in the machine-readable result. The selected model is not uniformly the lowest test MAE: for example, capacity interaction scores 19.14 at day-15-to-end versus the frozen timing model's 20.40. This is the expected consequence of freezing selection and is not retuned.

The separate random 16-game v10 panel was never used for fitting or selection. Frozen UMG end-horizon MAE on that transfer panel is 29.26, 30.42, 20.06, 16.91, and 11.08 at days 12, 15, 18, 21, and 24 respectively, versus 24.83, 20.40, 15.07, 12.15, and 7.15 on the UMG test. This indicates material version/domain shift; it does not compare against the actual v10 router tape or establish a v10 deployment gain.

## Separate reference-version diagnostics

These are independent train-only episode-grouped cross-validations, stored under `results/fresh/cumulative_planning/references/`. They do not pool their rows with UMG and have no held-out UMG claim. Majkel1337 `56216119` has 30 trajectories: selected end-horizon OOF MAE is 34.17, 25.94, 18.58, 17.38, and 11.42 at days 12, 15, 18, 21, and 24. The two eight-trajectory references are too small for reliable model comparison: `56254996` has corresponding MAE 35.93, 33.15, 31.40, 30.64, 24.25; earlier Majkel `56156662` has 28.50, 25.01, 24.87, 18.33, 13.53. Their selected models vary across cells, which is a small-sample warning rather than evidence that their policies are recoverable or preferable.

## Small-version limits

The historical evidence is narrow and policies create strong correlation between shops, board state, timing, and output. A positive development score is association, not a causal effect of a shop or cohort. The composition split, model-selection multiplicity, correlated paired seats, approximate state feature extraction, and version drift all make broad generalization uncertain. The test result should be reported even if every candidate loses to a simple baseline.
