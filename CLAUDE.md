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
- 2026-09-04: project scaffolded.
- 2026-09-06: venv at `.venv` with kaggle-environments 1.32.7 and kaggle CLI 2.2.4 installed.
  Environment spec captured in docs/environment.md. Kaggle API token not yet configured.
  Always run Python via `.venv/Scripts/python.exe`.
- 2026-09-07: `agents/greedy_v2.py` is the current closed-loop agent. Reference gate (12 seeds, both
  seats): beats built-in starter 24-0 (+105k mean), loses to `agents/public/tschinkel_router_v31.py`
  0-24 (-44k mean; was -118k for v1). Tools: `scripts/eval.py` (paired-seed gate), `scripts/trace.py`
  (day table), `scripts/compare.py` (revenue by product for both sides). Not yet submitted to Kaggle.

## Working notes
- Same seed does NOT give the same shops across code changes: the shop draw shares the RNG stream
  with weed spawning, which depends on both farms. Use 6-12 seed gates, never single games.
- Engine facts that bit us: no HARVEST before first_yield_day even at max yield (so fertilizer cannot
  speed up melons); hands hired at hour h act from h+1; FEED needs wheat in the unit's own inventory;
  the 10-order cap silently drops orders past index 9; step 718 is the last executed action.
