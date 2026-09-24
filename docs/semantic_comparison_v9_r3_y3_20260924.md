# Semantic comparison: our chassis+y3, V9, R3 (2026-09-24)

Reading-and-reasoning only; no games run, no files under `agents/`/`scripts/` edited.

## 1. What each system does

**Our chassis + y3.** Decision points: the router `_mgt_router` (`scripts/build_mg_tape_agent.py:140`) fires every
`step%24==0` from day 3 (`step>=72`) through day 28; the overlay (`scripts/fragments/mgt_sheep.py`, entry `agent` at
line 1432) runs every hour. Information used: the current observation only — own board tiles labelled by
kind/animal, a cumulative shop-demand vector at checkpoints 2/4/5/6/8 (`_mgt_vec`, line 89), and, for the overlay,
today's own market prices (`_shp_outlook`, line 638). No simulation, no opponent model, no lookahead past a static
`future_weight` expectation term (line 124). Objective: minimize a hand-tuned distance to the closest-matching
recorded expert continuation (`_mgt_distance`, line 116: weighted demand mismatch + board Hamming + strand/crop-strand
penalties), i.e. imitate; the overlay separately maximizes local task value (price × output − wheat cost) for
neglected animal jobs (`_shp_topups`, line 376). Action space: which of up to 584 recorded tapes to follow this day
(one discrete whole-plan switch/day) plus a handful of extra hidden-hand FEED/CARE/HARVEST/WATER commands merged into
the tape's own orders.

**V9.** Decision points: only the reveals of days 12/15/18 (`_V9_REVEALS=(288,360,432)`,
`scripts/package_v9y3_main.py:21`); every other hour is 100% native m1/y3. Information used: the full observation plus
our own agent's memory (`shortlist`, `scripts/value_tape_search.py:102`, up to 7 candidates across hamming tolerances
8/14/24), and a **rival model** (`scripts/rival_trajectory_model_v3.py:41` `select_donor`, `:59` `world`) that
retrieves the nearest of 115 historical/modern games by board+shop distance and synthesizes an hourly rival trade
schedule from it. Each candidate is forward-simulated with an independently instantiated copy of the **official
engine** (`isolated_engine`, `value_tape_search.py:77`) for 3 days under up to 8 sampled (shop-sequence,
rival-scale) scenarios (`rollout`, line 194). Objective: maximize risk-adjusted predicted **margin** (own − rival
cash gain: `score = mean(margin_deltas) − .5·pstdev`, line 299) subject to (a) no loss of any live cohort at the
commitment boundary (`asset_keys`/early-rejection guard, `value_tape_search_v7.py:22-46`), (b) mean own-cash delta
> 0, (c) worst-case margin ≥ −500 (`choose`, line 302). Action space: same discrete tape choice as ours, but
exercised only 3×/game, each commitment binding until the next reveal.

**R3.** Same 3 reveals; literally "V9 + a repair stage" (`import value_tape_search_v9 as B`,
`scripts/value_tape_repair_r1.py:14`). It re-simulates a rejected candidate's first scenario to find exactly which
named cohort would go missing, then re-admits that candidate only if a *repaired* version — with named
crops/animals kept alive — beats the native fallback over 16 ordinary shop futures and clears 16 rival-sale-delay
(6h/12h) stresses inside an 18s cooperative deadline (`value_tape_repair_r3.py:29-117`), else it falls back to V9's
own choice. Action space: a tape route plus up to 6 named "protect this tile" targets
(`TransitionRepair.activate`, `value_tape_repair_r1.py:41`).

## 2. Already have under a different name

- **Cohort preservation**: V9's `asset_keys` + early-rejection guard vs. our `strand_penalty`/`crop_strand_penalty`
  (`build_mg_tape_agent.py:184-209`). Ours is a static 2-day board-lookahead baked into the router's distance metric
  at every day start, cheap and approximate; V9/R3's is a simulation-verified hard veto computed only 3×/game from an
  actual 3-day play-out — stronger evidence, ~1000× the cost, and only covers assets present at commitment time.
- **Repair jobs**: R3's `TransitionRepair` (`value_tape_repair_r1.py:26-142`) does not add new execution machinery —
  its `topups`/`work`/`cull` methods monkey-patch and re-call **our own** `_shp_topups`/`_shp_work`/`_shp_apply_cull`.
  The only new thing is *which* tiles to protect (found by simulation) vs. our own heuristics: the orphan rule
  ("untouched for 3 days", `mgt_sheep.py:431-460`) and `rescue_pin` ("consecutive_unfed≥1", lines 429/443-448). R3 is
  a smarter target-selector bolted onto our existing rescue/orphan/top-up executor, not a competing one.
- **Rival model**: we have none. `_shp_outlook`/`_shp_price` (`mgt_sheep.py:593-648`) forecast only our own price
  curve; there is no opponent-cash or opponent-output model anywhere in our chassis. This is genuinely new.
- **Value-density scoring**: `_shp_topups`'s value (price×outlook−wheat) vs. V9's `risk_score`
  (mean−0.5·stdev of margin deltas) are both "expectation minus uncertainty discount" rules, but ours is local
  (one job, own price, 0.025s) and V9's is global (whole continuation, own+modeled rival, ~64s).
- **Bank-aware budgeting**: `package_v9y3_main.py`'s `budget = min(20, (bank−8)/reveals_left)` is new; our layers
  never measure wall time because they cost ~1.4ms/step (max 0.025s, `submissions/2026-09-24-mgt_y3/NOTES.txt`).

## 3. Mergeable by reimplementation by 2026-09-28 (ranked)

1. **Extend strand/crop-strand lookahead from 2 to 3 days**, matching V9/R3's commitment horizon
   (`until=(day+3)*24`), in `_mgt_router` (`build_mg_tape_agent.py:204-209`). ~3-4h incl. p2750/ladder panel check.
   Evidence: the existing 2-day version already measures +0.46k on the ladder panel and stops ~0.8 abandoned
   tiles/game; widening the window is a small, proven-analog parametric change. Risk: low-moderate, regression-testable.
2. **Auto-pin newly-orphaned tiles at switch time**, without simulation: when `_mgt_router` changes `state['route']`,
   diff the old tape's serviced-tile set vs. the new one's for currently-live animals/crops (already computed via
   `_shp_cal`, `mgt_sheep.py:365`) and push the difference straight into `state['rescue_pinned']` (line 413) instead
   of waiting up to 3 days for the orphan detector to notice. This reimplements R3's *mechanical* intent — protect a
   named asset through a switch — using our existing executor, with zero simulation dependency. ~4-6h. Evidence: R3
   found repair-servicing succeeds mechanically almost always (156/160 scouts) even though only 8/160 were
   economically worth it — the expensive part is the forecast, not the service; skipping the forecast keeps the
   mechanical benefit near-free. Risk: medium (R3 found 152/160 forecasts non-positive, so gate it behind the
   existing `topup_min` value check already used elsewhere in `_shp_topups`).
3. **Diagnostic-only shortlist logging**: port `shortlist`'s multi-tolerance candidate scan (8/14/24 hamming,
   `value_tape_search.py:124-133`) into the router as read-only telemetry, to see how often the greedy pick would
   differ from a wider-tolerance pick. 2-4h, no behavior change, informs future work only.

True margin optimization and whole-season official-engine rollouts (V9/R3's core) are not on this list — see §4.

## 4. Inspiring but not buildable by the 28th

- **V9's forward search**: needs an isolated clone of the official engine module plus a rival-behavior model trained
  on a curated 115-game library — this took the donor project six iterations (V1-V9) and several days
  (`docs/value_tape_search_20260923.md` through `value_tape_wide_20260923.md`) to build and validate, and still
  costs ~64s/game after five speed passes, against a 1s/step + 60s/game budget.
- **R3's 16+16-scenario repair validation**: needs V9 first, plus its own separate stress harness; even the donor
  project has not made it net-positive yet (measured −233 vs. V9, mostly deadline fallbacks).
- **A genuine rival financial model**: needs the curated donor library and production-flow reconciliation
  (`rival_trajectory_model.py`/`_v3.py`); multi-day effort, and the docs already flag it as imperfect (misses
  endogenous price response).
- **Multi-file Kaggle packaging** (`scripts/package_v9y3.py`, bank-aware budget, gzip fallback): mechanically
  reproducing this took its own dedicated commit and isolated-directory test; wiring a genuinely new merge through it
  needs fresh end-to-end Kaggle validation, exactly the class of risk that already caused a silent −104k..−168k
  incident (commit `6668175`, gzip-decompressed libraries).

## 5. Irreconcilable conflicts

- **Control authority**: not fatal but fragile — V9/R3 hold `chassis.router` only from a reveal until `until`
  (`package_v9y3_main.py`'s `committed` closure), then hand back. This is a single mutable attribute; any other code
  that also wants to own it (e.g. a future opening-handoff, or the `MGT_LATE_ONLY` research hook) will silently clash.
- **Shared labour**: R3's `TransitionRepair` monkey-patches `_shp_topups`/`_shp_work`/`_shp_apply_cull`/`agent` by
  exact name inside a throwaway cloned namespace (`value_tape_search.py:45` `fresh_agent`), so it never fights the
  live overlay's hidden-hand bookkeeping (`_shp_hidden`, `mgt_sheep.py:1419`) in production — but it hard-assumes
  those function names and signatures; any refactor of `mgt_sheep.py` breaks R3 without warning.
- **Time bank**: our chassis costs ~1.4ms/step; V9/R3 spend up to 20-64s at 3 specific steps from the 60s overage
  bank, leaving only an 8s reserve (`_V9_RESERVE`). Any future feature that also wants overage time must renegotiate
  this split — there is no slack today.
- **Packaging/dependencies**: CLAUDE.md's own convention is one self-contained file with no cross-module imports;
  y3 satisfies it via text substitution, V9/R3 fundamentally cannot (they import `scripts/value_tape_search*.py`,
  `rival_trajectory_model*.py`, and MB-scale donor libraries), hence the separate tar.gz + `main.py` loader. Two
  structurally different submission formats must coexist.
- **Objective**: our router/overlay never model the opponent and score locally (imitation distance; price×output);
  V9/R3 rank by predicted margin against a modeled rival, with own-cash-positive as a separate floor. A tape that
  looks good locally can be bad on margin if it also helps the modeled rival — exactly the failure the donor project
  found and flagged ("own cash +3783 but rival +6239", `docs/value_tape_search_20260923.md`). Our cheap heuristics
  cannot see this; V9's expensive ones exist specifically to catch it.

## Recommendation

1. Keep y3 as the base and defer V9/R3 entirely for the 28th deadline — they are not packaging- or timing-safe yet,
   and R3 currently underperforms V9 on its own measured panel because of deadline fallbacks.
2. In our own chassis, widen crop/strand-penalty's lookahead to 3 days and auto-pin newly-orphaned tiles at switch
   time into the existing `rescue_pin` path (items 1-2 in §3) — this captures R3's mechanical intent without any
   simulation dependency, in well under a day of work.
3. Track V9/R3 as a longer-horizon research line past the 28th: the one piece that is not reimplementable quickly —
   a real rival financial model — is worth keeping as separate IP rather than merging under deadline pressure.

## Corrections after checking (parent thread, 2026-09-24)

- **Rollout horizon.** V9's rollouts run to the end of the season, not for 3 days: `value_tape_search.py::rollout`
  loops `for t in range(start, 719)`; `until = (day+3)*24` is only the commitment boundary where cohorts are checked.
  So "simulate a shortened horizon" is a real cost lever (stream B), not something V9 already does.
- **§3 item 1 is dead.** The crop version of the strand rule was measured the same day: positive on both frozen
  panels but −785 vs y3 against live V56 (`docs/crop_strand_20260924.md`). Widening its window is not a safe merge.
- **Recommendation 1 predates the measurements.** V9 on y3 is +472 vs y3 on the 2750-3000 panel (CI +253..+740) and
  +320 against live V56 (CI −104..+890); the packaged build (`submissions/2026-09-24-mgt_v9y3/`) loads and plays from
  an isolated directory with a bank-aware budget. Whether it is timing-safe on official hardware with the budget is
  being measured, not assumed. The decision to defer or ship V9 rests on those results.
