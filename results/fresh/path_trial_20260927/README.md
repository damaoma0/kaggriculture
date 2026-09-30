# Path-planner trial on Kaggle (2026-09-27)

Arms (spec.json; agent `agents/mgt_lead_sector_path.py` = `agents/mgt_lead_sector_search.py` at git 74d79641 + 3 flags):

| Arm | Config on top of KB109 |
|---|---|
| PP0 | none (identity check against the local KB109 results) |
| PP1 | `sd_sim_fert_free` 1 (SIMULATION ONLY: fertilizer pickups never short; engine patch `scripts/sim_fert_free.py`) |
| PP2 | PP1 + `sd_path_walk` 3 (coins per walk-only step in the path search) |
| PP3 | PP1 + walk 3 + `sd_path_polish` 1 (shortest order per route at the same services, then refill) |
| PP4 | PP1 + walk 8 + polish |
| PP5 | walk 3 + polish, no simulation rule (deployable) |

Worlds: 16732748:112602061 (labor world), 16732748:112604454 (case world); days 11-29 from DSM's day-11 morning.

## Commands (Git Bash, repo root)

```
export KGR_DATASET=yiyangxudmm/kaggriculture-path-bundle KGR_STAGE=results/fresh/kaggle_remote_path
export KGR_EXTRA="data/leader_tapes,data/leader_semantics,results/fresh/threads_20260928/dsm_dawn,results/fresh/threads_20260928/dsm_dawn_rule.json,results/fresh/threads_20260928/dsm_dayret,results/fresh/threads_20260928/dsm_hourly_profile.json,results/fresh/threads_20260928/dsm_morning,results/fresh/threads_20260928/dsm_returns,results/fresh/threads_20260928/dsm_sales,results/fresh/threads_20260928/dsm_sell_hazard.json,results/fresh/threads_20260928/dsm_sell_hazard2.json,results/fresh/threads_20260928/dsm_sell_pace.json,results/fresh/threads_20260928/panel_dsm40b.txt,results/fresh/xfix_20260925/worlds42.json,results/fresh/lead_sem4_20260925/worlds.json,scripts/xfix_arms.json,results/fresh/path_trial_20260927/spec.json,.venv/Lib/site-packages/kaggle_environments/envs/kaggriculture/kaggriculture.py,.venv/Lib/site-packages/kaggle_environments/envs/kaggriculture/kaggriculture.json"
.venv/Scripts/python.exe scripts/kaggle_remote/remote_panel.py bundle mgt_lead_sector_path
.venv/Scripts/python.exe scripts/kaggle_remote/remote_panel.py pushcmd path2 "scripts/path_trial.py --spec results/fresh/path_trial_20260927/spec.json --arms PP0,PP1,PP2,PP3,PP4,PP5 --games 16732748:112602061,16732748:112604454 --out results/fresh/path_trial_20260927 --workers 4" "results/fresh/path_trial_20260927/**/*,results/fresh/sector_20260925/multi/PP*/*.json,results/fresh/day12_viz/pp*_streams/*.json"
.venv/Scripts/python.exe scripts/kaggle_remote/remote_panel.py fetchcmd path2
```

The engine file and its kaggriculture.json must be in the bundle at their Windows venv path: `scripts/upkeep_engine.py` loads
them from there. path1 (first push) is in `path1_broken/`: no timeout switch, every arm used up the framework's 60 s
overtime bank on Kaggle's CPU by days 20-24 and was frozen; `path_trial.py` now sets KAGG_NO_TIMEOUT=1.
`ref/` holds the stored DSM / KB78 / KB109 vitals text (the other thread's run, same scripts, same two worlds).
Table: `scripts/vitals_table.py ref/vitals_dsm.txt,ref/vitals_kb78_kb109.txt,vitals_plain.txt,vitals_fertfree.txt DSM,KB78,KB109,PP0,...`
