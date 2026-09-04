# Kaggriculture project notes

Kaggle simulation competition: an agent runs a farm for a 30-day season, one turn per in-game hour,
competing on profit against other agents in a shared market. Competition page:
https://www.kaggle.com/competitions/kaggriculture

## Conventions
- One agent per file in `agents/`. The submitted entry point must be a single self-contained file
  (Kaggle simulation competitions upload one `.py`), so avoid cross-module imports in agent code.
- `scripts/run_local.py` runs an agent through the `kaggle_environments` engine locally.
- Record every submission in `submissions/<date>-<name>/` with the exact file uploaded and a note on
  the local score.
- Keep environment findings (action format, observation schema, market rules) in `docs/environment.md`
  as they are discovered. The exact spec must be read from the competition's environment code, not guessed.

## Status
- 2026-09-04: project scaffolded. Environment spec not yet inspected. Kaggle CLI not yet installed.
