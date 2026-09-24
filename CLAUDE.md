# Kaggriculture project notes

Kaggle simulation competition: an agent runs a farm for a 30-day season, one turn per in-game hour,
competing on profit against other agents in a shared market. Competition page:
https://www.kaggle.com/competitions/kaggriculture

## Conventions
- 2026-09-24 ACCEPTANCE TEST = the 2750-3000 exact panel `data/ladder_panel/p2750/` (185 games: 81 of our own vs
  2750-3000 teams, 104 team-vs-team; `scripts/build_p2750_panel.py`, `scripts/report_p2750.py`; submission arg
  `p2750` to ladder_panel.py / remote_panel.py). Win rates there: m1 45.4%, t10 42.2% (t10 −352 vs m1, CI
  −648..−76), y3 47.0%. CANDIDATE `agents/mgt_y3.py` (= m1 + yarn_service, yarn_gate, rescue_pin,
  yarn_harvest_min=4), packaged in `submissions/2026-09-24-mgt_y3/` but NOT submitted: vs live V56 +295 (+69..+554),
  180 ladder worlds +183 (+105..+266), p2750 +306 (+204..+416); max 0.025 s a call. New opening: measurably fails in
  the tape architecture (`docs/new_opening_20260924.md`): graft −66k/−87k (hidden state), DSM library −7.1k.
- 2026-09-23 remote panels + late-Yarn layer: see `docs/late_yarn_layer_20260923.md`. Kaggle remote panels are
  VALIDATED (`scripts/kaggle_remote/remote_panel.py`; 40/40 dollar-identical to local, t10 20/20 to its ladder
  recordings; 5 private sessions about 20 games/min; the user's other agent system shares the account's sessions).
  Layer = `--sheep yarn_service=1,yarn_gate=1` (`agents/mgt_y2.py`): h2h +67 (−13..+156), ladder panel +57
  (−21..+133), mostly through the rival's wool price (frozen-opponent caveat); no expansion collision. PARKED
  (user, 2026-09-23). Tail defect traced (world 111302438, −3.2k): a yarn task outbids a sheep rescue for the hidden
  hand's last slot (the sheep escapes), and the automatic HARVEST fragments batches. Fixes and a 2750-3000 exact panel
  are in a separate thread (mgt_y3, dataset kaggriculture-panel-bundle-y2). No late strawberry response exists to
  copy (the deficit is in the opening). MAIN LINE NOW: the DSM opening (O1 = replayed DSM days 0-5 + router
  handoff at the day-6 morning, the only day the new board is tape-compatible: 10-16 tapes within 8 tiles).
- 2026-09-23 losses / winner tapes / coverage / opening: see `docs/losses_winners_coverage_20260923.md`
  (results in `results/fresh/newphase_20260923/`). Live: t10 2805, m1 2700; no t10-vs-m1 difference after controls.
  Late Yarn Stores drive losses (odds x0.37 each); the near-causal |tape-vs-world late-Yarn mismatch| gives x0.51. No
  seat asymmetry (n=856). No current top-6 agent is harvestable (all closed-loop). Library-size panel: 292 tapes
  -505 (n.s.), 146 -3.2k, so more recorded tapes are saturated. Prefix-twin ceiling: perfect coverage -4,345 ->
  +898, but a perfect day-12 match only +0.7k; about 4.5k is in shops 5-8 and must be generated, not recorded.
  The top-4 share a new fixed opening (2 cows / 3 sheep, 10 melons, strawberries from day 2); tapes cannot follow
  it. MEMORY: the laptop is shared with the user's other agent systems. Max 4 game workers, check free memory
  first (`ladder_panel.py` now sizes its pool from free memory).
- 2026-09-22 replay-first follow-up: user wants every store-driven goods mismatch
  pair examined and the best production shift measured, beyond milk-to-wool.
  First requested deliverable is the back-to-back before/after pilot replay:
  `viz/tape-109740300-before-after.html`, built by
  `scripts/build_tape_variant_replays.py`. Two exact 720-state reconstructions
  reproduce frozen cash/harvest/action results; browser checks pass, including
  automatic before-to-after playback and the D17 care state. Exported data and
  verification are under `results/fresh/tape_variants_20260922/replays/`.
  Broader mismatch-pair/production-amount search is still pending. It must include
  under- and overproduction for all goods, observed demand outside the chosen
  donor's scenario, feasible sequence/cohort/retirement changes, and opponent
  price effects. Report best tested amounts and uncertainty, not a global optimum
  from a single hindsight replay. Prioritize competitive cash margin.
- 2026-09-22 per-tape sequence revision pilot: `docs/tape_sequence_variants.md`.
  User prefers small, marked improvements to individual tapes. Register at
  `data/tape_variants/index.json` covers 584 originals; 13 milk-to-wool review flags
  are associations with audited losses, not causal or recoverable-profit claims.
  First variant `109740300-milk-care-to-wool-v1` redirects one worker's cow care
  to the adjacent sheep, rejoining the same route at hour 5, on D17/19/21 in the
  discovery case 111678108. Four commands/day, no additional hires/travel/spend.
  Result: +314 own cash, opponent +226, margin +88; wool +1, milk -3. Existing
  overlay already supplied two of the three sheep cares. D23 rejected because
  next harvest conflicts with D26 pasture conversion. Three other-donor controls
  unchanged; eight full-game executions and seven boundary/isolation tests pass.
  Marked diagnostic improvement only; applicable responsive-opponent validation
  remains outstanding. `agents/mgt_tape_care_v1.py` is separate and does NOT bundle
  the earlier wool-forecast patch. mgt_m1 and all original tapes remain unchanged.
- 2026-09-22 minimal m1 experiments: see `docs/mgt_m1_minimal_experiments.md`.
  Three isolated edits, no planner changes. One-sheep eligibility and a D18 Yarn
  target produced identical actions in 6 diagnostics and 24 development games each.
  `agents/mgt_micro_wool_upturn.py` replaces one return with six lines, allowing the
  existing wool forecast above today's price when a Yarn Store is open. Independent
  24-seed/both-seat live-V56 confirmation: +85 paired margin (seed-bootstrap 95% CI
  +7..+214), +80 own cash; 7 better / 0 worse / 41 same; wins unchanged at 32/48.
  Historical 198 available m1 games: +131 margin, 34 better / 5 worse / 159 same;
  two losses flip, no wins lost. All 89 original losses included (+221; below2500 +231).
  Historical opponents are recorded and losses are oversampled. Worst regression
  -494 is traced: extra feeding prevents planned D26 pasture-to-wheat conversion and
  delays another harvest. Test a retirement/replant guard separately next. Candidate
  remains separate; mgt_m1 is unchanged and no submission was made. Frozen sources,
  408 panel executions and 2 diagnostic trace reruns are under `results/fresh/m1_minimal_20260922/`.
- 2026-09-22 continuation execution/recovery implementation: see
  `docs/continuation_execution_and_recovery.md`. New bounded compiler reproduces
  8/12 native three-day windows with exact output and ending tiles (old: 4/12);
  maximum native action 0.290s. Ten runtime/engine/fault-injection tests pass.
  Three experimental policies were evaluated on 8 fresh development seeds, both
  seats, live V56. m1: 10W/6L, +2943 margin; maintenance version: 8W/8L, -4216;
  final productive fallback: 4W/12L, -11883. NO promotion: m1 remains selected.
  Eighty full-game executions total; v3 reuses 16 hash-verified v2 control rows.
  Sources/results are frozen under `results/fresh/continuation_executor/`.
  Final experimental agent is `agents/mgt_continuation_dev.py`. Its runtime is
  bounded, but policy strength fails; planned maintenance is not enough to
  preserve profitable replacement cohorts. Sixteen confirmation seeds and the
  existing qualification panel remain unused. Venv launcher did not start here;
  bundled Python 3.12 + existing venv site-packages ran engine 1.32.7 unchanged.
- 2026-09-22 DSM/UMG rotation screen and independent validation: see
  `docs/rotation_experiments_random_seeds.md`, `results/fresh/rotation_experiments/`.
  332 benchmark games across 46 new random seeds; m1 unchanged. Development (12 seeds,
  both seats) paired margin changes vs V56: DSM library -9921, age-aware routing +38,
  two tomato rotations -57, hold-only control +564. Selected hold-only on 32 untouched
  seeds: +84 paired margin (seed-bootstrap 95% CI -735..+877), own cash +390; vs m1
  directly 21W/32T/11L, mean +731 (CI -74..+1830). NO reliable improvement/promotion.
  All 48 development rotations harvested four tomatoes, but rotations underperform the
  hold control by 621. Direct two-m1-family same-process games have a seat-0 GC pause
  at step 24 (confirmed by two serial diagnostics); V56 validation has no own-agent
  calls over 1s. Preserve raw timing failures. Frozen sources are in panel directories;
  the editable rotation template has a later planting-day-water guard absent in those
  frozen sources, excluding two unused proposals from 19,479 audited opportunities.
- 2026-09-22 three-day segment stitching prototype: see
  `docs/three_day_segment_stitch_experiment.md` and `results/fresh/segment_stitch/`.
  Extracted 630 UMG segments (105 rich replays), independently checked harvest/collection
  totals for all 630. Final v3 native gate: 4/12 full windows reproduce exact output AND
  full end-tile state; 8 fail labour/delivery capacity. Frozen 8-development-world/both-seat
  panel: candidate versus V56 9W/0T/7L, mean margin -1682; m1 control same seeds 9W/0T/7L,
  mean +1760. Candidate versus m1 0W/4T/12L, mean -6094. No donor changes between active
  windows; exact cohort matching remains restrictive. Worst decision 21.56 seconds;
  offline runner records but does not enforce timeout. DO NOT PROMOTE/SUBMIT this candidate.
  m1 remains unchanged. Partial native successes are reconstruction evidence, not a
  validated general continuation. V1/v2 were debugging stages, not benchmark improvements.
- 2026-09-22 completed random-world baseline survey: frozen current mgt_m1 versus frozen V56,
  128 fresh random seeds, both seats, 256 games: 177 wins / 0 ties / 79 losses (69.14%;
  seed-clustered 95% CI 61.33–76.95%), mean margin +2744 (95% CI +1519 to +3974).
  All games DONE, both ledgers reconciled, no calls over 1 second. See
  `docs/v56_random_world_benchmark.md` and `results/fresh/v56_random_20260922/`.
  222/256 games had no exact UMG prefix by D12; no full eight-shop match in the panel.
  This is current m1 performance, not the unfinished production-plan continuation or
  the full promotion protocol. It falls short of the 80.83% standard-Elo planning target.
- 2026-09-22 continuation target: use the hash-checked 3000-Elo addendum protocol
  `results/fresh/tape_gap_plans/promotion_protocol_3000_v2.json` (which inherits the frozen
  `promotion_protocol.json`) and `docs/continuation_3000_target_addendum.md`. The v1 gate remains
  an improvement threshold, not a 3000 claim. V56 source is in
  `data/router_refresh_20260922/v56/main.py` (SHA a1ad0fd1d174477ee2cbdd561a812bcb7029647ce34599e79d6b79e9057eff6c).
  Qualification has NOT run; production forecasts/aggregate calendars are not gameplay evidence.
  Keep natural live-V56, historical original-tape and repaired-opening controls separate. Do not
  tune on the frozen qualification panel or promote a candidate using only short tape diagnostics.
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
  (day table), `scripts/compare.py` (revenue by product for both sides).
- 2026-09-08: current agent is `agents/hybrid_v1.py`, GENERATED by `scripts/build_hybrid.py` from
  `agents/plan_v1.py` (edit plan_v1, then rebuild). It replays the public router's opening for steps
  0-263 (weed repair only), then the plan_v1 planner. Local: router gate 0-12 (-25k), 8 ladder tapes
  29-3, starter +126k. Ladder tapes come from `scripts/make_tapes.py` over `data/replays/`.
  Kaggle submissions (only latest 2 active): hybrid_v2 56105759 (yuto083 opening; 9-3, ~930 after
  14 games) and hybrid_v1b 56103113 (~975). Retired: hybrid_v1 56102841 (~1013), plan_v1b, plan_v1.
  Account identity-verified; `kaggle competitions submit` works. Public router author sits ~2470,
  top of ladder ~2930, median ~790 (8244 teams).
- Default opening tape is now `agents/tapes/yuto083_106870999.py` (an ~1850-rated team's episode);
  `scripts/build_hybrid.py --tape` swaps it. Local reference for hybrid_v2: router gate 0-12 (-24k),
  strong ~1000-tier family panel 16-16, original 8-tape panel 31-1, starter +129k.
- Next work: the ~24k late-game gap to the router (units, not prices: strawberries and wheat
  cycles), and the planner still loses to yuto083's own late game by ~8k.

## Working notes
- Same seed does NOT give the same shops across code changes: the shop draw shares the RNG stream
  with weed spawning, which depends on both farms. Use 6-12 seed gates, never single games.
- Engine facts that bit us: no HARVEST before first_yield_day even at max yield (so fertilizer cannot
  speed up melons); hands hired at hour h act from h+1; FEED needs wheat in the unit's own inventory;
  the 10-order cap silently drops orders past index 9; step 718 is the last executed action.
- Watering only matters for survival (never two misses in a row; a seedling must be watered the
  day it is planted), a one-time crop's bonus window, and a FERTILIZED ongoing crop's production
  day. Unfertilized strawberries yield 1 regardless of water. Watering everything daily wastes ~25%
  of labor; the top tapes water wheat 3x per cycle and strawberries every other day.
- Wheat is a tradable asset: shops drain 25-30/day so its price climbs 25->54 over a season; strong
  tapes buy ~700 early and sell ~800 late. The shed cap (100) silently discards midnight overflow.
- Fourth quadrant, 13 hands, 41 strawberries, 20 melons: all tested worse. Wheat fertilization at
  scale tested worse (labor).
- Kaggle's loader calls the last NEW callable name in the file. A fragment that re-defines `agent`
  does not move the name, so a helper defined later becomes the entry point and the agent sits at
  3,000 cash all game. Harnesses that call `ns['agent']` (mgt_loo, the debug scripts) do not show it;
  `selfplay_gate.py` does. `build_mg_tape_agent.py` appends `mgt_kaggle_entry` last and asserts it.
- Adding hands of our own on top of a replayed tape: hire them only AFTER the tape's last hire of the
  day. A new hand spawns on the least-occupied shed tile, so an extra unit standing at the shed moves
  the tape's next spawns and those hands replay their whole day one tile off (cost 5-9k a game).
  Hide the extra hands from the tape layer (observation without them, merge commands by real index).
- Animal care is settled at day end: production first (pays 1 + banked bonus if fed that day, else 1
  and the bank is wiped), THEN a fed+cared day banks +1 for the next production. Order of FEED/CARE
  within a day is irrelevant; care on the last production day is wasted. Checked by calling
  `_daily_refresh_animals` directly (engine 1.32.7): a missed feed on a NON-production day only loses
  that day's +1 (bank 3 stays 3); a missed feed on the PRODUCTION day wipes the whole accumulated bank
  (sheep: 6 -> 1). Yield on the tile is capped at max_held, so an unharvested 6 swallows the next
  production entirely.
- Mother-Goose's servicing is demand-conditioned (`scripts/mg_care_rule.py`, 584 tapes): sheep cared
  46% / fed 68% of animal-days with no Yarn Store vs 75-90% with one; cows 65% -> 86% as milk shops
  appear; geese always ~92%. Her tapes also over-request animal orders (six "BUY SHEEP 1" at once), so
  count sheep from boards, not from orders.
- 2026-09-20: live submissions are `agents/mgt_m1.py` (56395605, submitted 2026-09-20) and `agents/mgt_t10.py`
  (56368334, ~2430); `mgt_m1` = t10 + sell_lead + hire guard + strand rule is the best measured build. README.md and `docs/` are the live log;
  the status lines above are history. Head to head against her ORIGINAL tape in 128 fresh recorded worlds: -4.5k
  (19-109) when her tape for the world is excluded, +0.5k (98-30; b1 +0.8k, 111-17) on her own plan. The layers are
  net positive; the whole gap is playing a neighbour's plan. "Price, not units" was an AVERAGE ARTIFACT (corrected the
  same day): where the tape's world and the real world have the same demand for a product our realised price equals
  hers (wool 112.7 vs 112.1), so a neighbour's SELL TIMING costs nothing; where the world has more late demand we are
  short of UNITS at high prices (-4.2k in those worlds), where it has less we over-produce into a glut and gain nothing.
  Her late game is a live demand response (care 3% -> 94% the day a Yarn Store opens; late plantings, fertilizer and
  herd scale with open demand). Her crew routing is within 4% of optimal per hand (`docs/tape_opportunity_map.md`).
- LADDER PANEL (`scripts/ladder_panel_fetch.py`, `scripts/ladder_panel.py run|report`, `docs/ladder_panel.md`): our
  recorded ladder games replayed with the same seed, forced shops and the OPPONENT's recorded actions against a live
  build. `mgt_t10` reproduces its 141 ladder results to the dollar. 378 worlds on disk (7.9 MB); 141 games ~7 min.
  Measure anything that touches cash, hires, the router or the overlay here as well as on the V50 panels: the
  ladder's price impact exercises paths the V50 panels barely do (hire shortfalls never, the sheep expansion in 4%
  of games against ~6%).
- Hire shortfalls come from her opening spending to the last coin (days 5-9, cash under 500), NOT from the sheep
  expansion: seeds listed before HIREs, or hour-0 purchases leaving less than the hour-1 wages. One missing hand
  shifts every later hand index that day (-2k typical, -22k worst). `--sheep hire_guard=1` removes them.
- Late tape switches that strand live animals were the identifiable harm of switching; `--cfg strand_penalty=4.0`
  (one-directional, only tiles with a live animal of ours the candidate tape will not service) is +0.46k on the
  ladder panel where the blanket `animal_weight` was negative.
- Never edit a script while a ProcessPool run that uses it is in flight: on Windows every worker re-imports
  `__main__`, so a half-written file fails every remaining game (lost 133 of 141 games that way once).

### 2026-09-23 economic tape search and controlled handoffs

- `docs/value_tape_search_20260923.md`, `scripts/value_tape_search.py`: a research selector takes public observation
  and native m1 memory only, shortlists up to seven tapes across 8/14/24 tile tolerances, projects the official
  engine to season end under three sampled shop / rival-supply scenarios, and commits an alternative only until
  the next reveal before restoring native routing. Rank competitive margin, discount forecast dispersion, and
  protect existing cohorts. Runtime 40–76 seconds per decision under concurrent workloads; not competition ready.
- Strict gate on seven diagnostic losses plus twelve frozen sampled historical cases changed only episode
  **111269605 day15**: donor **109529802 (route0)** replaces **110226826**. Public projected gains
  +6221/+10594/+10981; actual fixed-world margin **−11836 -> −1802 (+10034)**, own cash +9716, rival −318.
  Two sheep bought D15/D16, placed D15/D17; existing sheep also receive better care. Postdecision wool sales
  42->92, revenue +10302, net spending +586 (wages −919, sheep +1000, feed purchases +605).
- `value_tape_policies.py` relaxes matching feed counts while retaining exact projected cohort survival and
  economics. It adds +4266 and +810 on the historical sample. These are DEVELOPMENT figures because that
  sample informed the revised gate. The +10034 case remains the major prospective fixed-world proof.
- Independent live V56 panel: four fresh random seeds, both seats, one D15 intervention. Strict changes none.
  Cohort gate changes seed1329978515 in both seats: apparent +2173 each / +543 mean over eight pairs. **Do not
  promote or quote that as an isolated production gain**: policy-dependent weeds changed future shop draws.
  `check_value_tape_shop_confound.py` crossed both actual shop sequences with responsive opponents. The chosen
  route196 **loses −2456 under original shops and −239 under its own natural shops**. Both natural diagonals
  reproduce exactly. In the original world own cash +3783 but rival +6239; rival berry revenue +6106 and milk
  +2076 at unchanged sold quantities. Current rival supply / demand-branch model underprices this externality.
- Five regression checks passed; all 19 historical native controls reproduce and ledgers reconcile, as do all
  24 live games and four controlled-shop runs. Frozen source hashes and full candidate counterfactuals live in
  `results/fresh/value_tape_search_20260923/`. Baseline mgt_m1 SHA remains
  `1152ef2e12c4535dbc381b9c54ac7d7a0b1a9ad3d0a8018a7567dcf5c4a52470`.
- Next concrete work: model rival sales by cohort AND delivery date, broaden future-demand scenarios for marginal
  decisions, and repair specific missing jobs using the existing labor scheduler. Do not label the whole approach
  failed: the same-shop +10034 recovery is real, while the live false positive identifies a forecast weakness.

### Tape-value follow-up: rival family matching and complete scenario screening (2026-09-23)

- Report: `docs/value_tape_followup_20260923.md`; results: `results/fresh/value_tape_followup_20260923/`.
  Latest research selector is `scripts/value_tape_search_v4.py`, with `rival_trajectory_model_v3.py`.
  Keep all frozen V1/V2/V3/V4 experiment files and source snapshots intact. Baseline mgt_m1 is unchanged.
- Major new selected recovery: historical **111262874 D12**, route **184 / donor110025609**, board-label Hamming0.
  Margin **-12585 -> +5864 (+18449)**; our cash **110635 ->117701 (+7066)**; rival **123220 ->111837 (-11383)**.
  D12 plants8 strawberries instead of2, two tomatoes instead of7, and buys a cow; avoids two D15/D16 sheep buys.
  Postdecision output/sales +97 strawberry,+25 milk,+24 carrot,-82 wool,-28 tomato. Own revenue+5541,
  spend-1525 (including wages-432); rival sold quantities unchanged, berry revenue-10424 and milk-2102.
  All starting cohorts retained by the actual native plan at D15 also survive the switch. Full paired trace:
  `selected_strawberry_recovery_trace.json`. This target's outcome was known from earlier counterfactuals:
  **development evidence**, even though the selector only receives agent-visible inputs.
- Earlier **111269605 D15 route0 +10034** recovery remains selected. V4 checks on three named historical cases:
  +18449,+10034,0. The two gains do not require the newly declared scaled downside allowance; strict min-500 passes.
- Diagnosed V1: exact future shops alone did not reject the live bad switch; actual daily rival trades did.
  Older-only retrieved trajectories improved 30 older heldouts but worsened modern forecast accuracy.
  Added an outcome-blind random modern library: 40train/20test, excludes all19 prior target cases. Combined
  model uses115train (75older+40modern), public crop/animal cohorts, successful hourly transactions and future
  rotations. On20 excluded modern games, D15 cumulative net-sale MAE (V1 -> V3): 3days6.82->1.12,
  6days8.66->2.39, remaining15days32.49->12.36. No target suffix, rival private inventory, or actual future shops
  enter selection. Rival model still has imperfect endogenous price response; accuracy is not proof of profit.
- Known bad live route196: 16 new paired responsive continuations from its checkpoint, sampled future shops,
  mean+152.375,9positive/7negative,min-2456,max+2749. Mixed-family prediction includes -681 downside and rejects
  this candidate with the existing500 limit. Do not say all future losses can be prevented.
- Frozen **V3 independent live panel**: 12 fresh random fixed-shop worlds, balancedD12/D15/D18 and seats;
  one switch, **+3783 margin / +4770 own cash**, 11unchanged, no regressions, mean+315.25. Seed2867821829 seat0
  D12 donor109863155 route136: margin4823->8606; +22wool,+49egg,+20milk; extra sheep boughtD14; +53feeds,+51care,
  -39water,-24fertilize, wages-665. Both live responsive paired results independently reproduced in detailed trace.
- V3 wrongly applied expected-own-cash screen after only4 of8 shop worlds. For184, first4 own-cash mean-968.5;
  full8 +714, with all8 margin gains positive (+1208 minimum). **V4 uses first4 only for margin ranking**, then
  complete8 for final cash/risk admission. Separate frozen **V4 independent6 live worlds all unchanged**; they do
  not independently confirm the screening fix on an executed switch. V3 and V4 live samples use different seeds.
- Candidate search: native+incumbent/native reveal choice, fill up to7 from hamming8/14/24; four common worlds
  for screening, top2 plus native to8. Eight stratified shop futures, family/cohort-conditioned rival donors.
  Final preserve-cohorts/no-extra-failed-hires gate; own expectedcash>0; score meanmargin-.5SD>350; forecast
  downside >=-max(500,.25*meanmargin). Force only3days then restore native routing. No repeated-reveal test yet.
- Five new regression checks pass, including recorded forecast fixture reproducing/fixing the premature veto.
  All105older+60modern source replays cash-match/reconcile; historical native controls reproduce; all18 fresh
  live pairs fixed-shop, identical-prefix, complete and ledger-verified. Research runtime109-208sec/decision
  under concurrent load: **not competition ready**. Cross-process forecast cache correctly refused hashes with
  process-local tape ids; V4 historical runs used fresh forecasts. Do not bypass cache validation.
- Next work should address efficient wider tape search and closed-loop reveal decisions, retaining these
  real-scale recoveries as regressions. Do not tune only to the named historical cases or mistake unchanged
  small live panels for broad policy superiority. There are no unfinished worker pools from this experiment.

### Tape-value generalization and exact speed improvements (2026-09-23)

- Report: `docs/value_tape_generalization_speed_20260923.md`; artifacts:
  `results/fresh/value_tape_speed_20260923/`. Latest research selector is
  `scripts/value_tape_search_v7.py`, built on frozen V5/V6 runtime improvements.
  No submission. Baseline mgt_m1 hash is still 1152ef2e12c4535dbc381b9c54ac7d7a0b1a9ad3d0a8018a7567dcf5c4a52470.
- Corrected new panel: six shop worlds (four IID, two declared late-demand stresses)
  crossed with three live opponents, alternating seats, re-evaluation at D12/D15/D18.
  **18 paired games: 9 improved / 9 unchanged / 0 worse by margin; mean +2881.78**.
  Own cash +800.78 mean, rival -2081; wins remain12/18. Same shops within each pair,
  all full games and both cash ledgers verified. These are six demand samples,
  NOT18 independent worlds. All9 changed games execute one switch: still no
  validated case with two executed switches in one game. Four IID worlds yield
  12 matchups mean+3669.5; two stress worlds yield6 matchups mean+1306.33.
- Correct live-V56 six-pair mean+3093.5, sixday+2452.33, pasture+3099.5.
  The original `generalization/` harness mistakenly invoked V56's earlier
  module.agent. `benchmark_value_tape_generalization_v2.py` invokes the actual
  Kaggle last-new-callable e410_agent and reruns those same6 worlds, retaining
  twelve valid other-opponent artifacts by hash. Use ONLY `generalization_corrected/`
  for policy results. The correction is not a new independent test or policy tuning.
- D15 first-Yarn example versus pasture: donor109547210/route23, margin+7838,
  own+8711,rival+873; two extra sheep, sales+53wool,+41milk,-124wheat,-36carrot,
  wages-1152. D18 route197 improves+6740 vsV56,+4355 vs sixday. D12 route47 gains
  +6678/+6437/+3581 across V56/sixday/pasture. D12 route38 gains competitive margin
  +5143/+3922/+7178 while LOSING own cash7693/8662/6178. Own expectedcash>0 is not
  a realized-own-cash guarantee; these three share one future shop branch.
- V5 reuses immutable decoded tapes and private simulator templates, resets agent
  state per rollout, and copies plain JSON observation trees. Initial isolated
  wool V4=104.12s -> V5 cold9.61s / warm7.54-7.77s, with full forecast equality.
  V6 borrows only the simulated observation, guarded by the exact frozen agent hash.
  Current-source ownership audit1438 calls passes; earlier broader audit2298 calls
  also passed. Four reset/copy/isolation tests pass. Full V6 live replay matches
  ALL54 decisions,1636 forecasts,all actual actions and both cash totals of V5.
- Later runtimes rose for both implementations; cause not isolated. Contemporaneous
  V5/V6 paired CPU medians49.58s/27.85s (wall50.15s/28.12s). Do not multiply ratios
  across different runs or claim a stable subsecond implementation. Raw profiles
  and timings are saved. Cloud audit corrected the budget:1s/action, total overage60s;
  manual benchmark does not enforce this. Competition readiness is unresolved.
- V7 exactly stops a candidate when a baseline-retained starting cohort is already
  missing at the next reveal in any required world. No partial-profit or hire-count
  cutoff. Saved-forecast fixture checks preserve all54 selections/admission flags,
  pruning126 candidates and26.3% of simulated turns (593660->437348). This count is
  fixture/work evidence, not measured wall speed or another live panel. Official
  engine checks on three historical cases preserve selection/admission and every
  unpruned forecast, including the+18449 strawberry and+10034 wool recoveries.
- Next: use exact paired rollout labels to learn a fast value ranker over semantic
  output, sale dates, cohort/maintenance commitments and cash/labor changes. Validate
  by held-out shop composition, rival strategy and source-tape family, and budget
  exact labor/transition checks for finalists. A deadline-aware fallback still needs
  implementing/testing. Keep recorded requested actions distinct from verified
  successful production. No unfinished worker pools remain from this turn.

### Semantic ranker and staged scouting qualification (2026-09-23)

- Report: `docs/value_tape_scout_20260923.md`; artifacts:
  `results/fresh/value_tape_ranker_20260923/`. Latest research selector is
  `scripts/value_tape_search_v8.py`. It changes candidate search: one exact
  full-season scout in scenario0 for every alternative, keep2 even if their
  first-world gains are negative, expand to4 and then8 with the unchanged V4
  final admission rules. Early protected-cohort rejection is inherited fromV7.
  Candidate ranking is approximate; do not claim universal V7 equivalence.
  Baseline `agents/mgt_m1.py` remains unchanged at SHA1152ef2e12c4535dbc381b9c54ac7d7a0b1a9ad3d0a8018a7567dcf5c4a52470.
- Built584 dated requested-plan profiles and verified75 input checkpoints:
  72 previous live decisions from24 independent worlds, plus3 reserved historical
  regressions. All36 live games reproduce cash/prefix;18 multi-decision games
  also reproduce every action.414 alternative rows have complete4-world labels;
  unevaluated8-world candidates are never labeled negative. Whole-world grouped
  development CV: learned linear semantic ranker retains5/10 selected routes in
  top2,10/10 in top3, but misses both reserved major recoveries in top2 (wool
  ranked6th, strawberry3rd). Median warm feature+score3.32ms, profiles/model load
  0.62s in one measurement. **The static ranker is not used by V8.** Only two
  source submissions appear in the training candidate set; family tests are
  diagnostics, not broad source-family validation.
- One exact scout world retains10/10 old live selections and both historical
  recoveries in top2. Saved fixtures preserve all74 resolvable V7 choices with
  26.4% fewer turns. The75th checkpoint, seed2761107011/seat1/D18, required fresh
  eight-world labels (oldV3 premature cash screen); V7 andV8 both remain native.
  Three official uncached case checks preserve selected0/184/None and72 common
  forecasts. Paired wall seconds: strawberry24.01->30.04, wool24.74->19.20,
  control34.57->21.72. Aggregate about15% lower, with a slower outlier; do not
  claim uniform runtime speedup or multiply ratios across prior experiments.
- **Frozen fresh qualification:** six new IID shop worlds x three live opponents,
  D12/D15/D18 repeated decisions. Native, fullV7 and scoutV8 each play complete
  games:54 total, all ledgers/prefixes verified.18 paired matchups:6 improved,
  12 unchanged,0 worse margin; mean+461.833, own+54.167, rival-407.667; wins15->15.
  V8 matches all54 V7 choices and all18 complete action streams/cash totals.
  Work383542->280913 simulated turns (**26.8% less**),1131->871 rollout calls.
  Common exact forecasts are cached within an identical input only; reference
  also plays full games, reusing decisions only on equal portable input digests.
  Shadow wall time is not comparable. Scout call median10.51s, range5.80–23.04,
  excludes initial runtime and per-decision simulator setup. Not competition ready.
- Fresh improvements occur in2/6 worlds (opponents/dates correlated), all oneD18
  commitment per game. Seed3626998516 route74/donor109644324 improves margin
  +2410/+1079/+1350 vsV56/sixday/pasture, own+281/-289/+695. Yarn revealsD18;
  vsV56 buyone more sheep, sell38 more wool and38 more fertilizer, wages-864;
  margin-6452->-4042. Seed1607935832 instead **retains incumbent561/donor110366265**,
  preventing the native D18 switch to329 despite shop-distance21 vs9; improves
  +793/+1277/+1404, own+207/+75/+6. A selected commitment need not change tapes.
  The fresh mean is much smaller than prior+2882; preserve both results. No new
  game validates multiple executed commitments or converts a loss to a win.
- Optional `budget_seconds` aborts between stages/every8 simulated turns;
  engine hooks restored and only complete8-world admitted candidates can commit.
  Four tests pass, including interrupted rollout followed by identical full
  forecast and public-input/route-ID isolation. Cooperative deadline, not a hard
  real-time guarantee;1s/action plus60s total overage (corrected by cloud audit).
- Next: train continuation value on actual3-day physical transition outputs,
  inventories, cohorts and labor, replacing the expensive full-season scout only
  after grouped/fresh validation. Requested-plan features alone were insufficient.
  All worker pools from this experiment have finished.

## 2026-09-23 V9 exact tape-search speed

- User requested local continuation while other agent systems use cloud resources.
  `scripts/value_tape_search_v9.py` shares current rival production and public donor
  ranking within a decision, and uses bounded content-based packed board matching
  inside the private simulator. V8 search/admission code and simulated work are unchanged.
- Serial frozen six-checkpoint ablation: mean warm V8 15.695s, shared scenarios
  14.083s, V9 13.435s; **14.4% lower wall/CPU time**, all six cases faster.
  All 54 decisions and 124 distinct forecasts match; 600 scenarios over 75
  checkpoints match; 4,404 board/mutation checks and deadline cleanup pass.
  The first 8,192-entry cache thrashed and was slower; raw failed-trial samples
  are retained. Final capacity 32,768 eliminates repeated encoding misses here.
- Two existing fresh-scout V56 recovery games, 2-v56 and 5-v56, reproduce all
  actions/cash and retain +2,410/+793 margin improvements. Local per-turn bank
  accounting, including initialization and search plus action together, leaves
  17.44s/20.97s of the 60s overage. This records timing in a manual engine replay;
  it does not validate the actual competition subprocess or guarantee deployment.
- Report: `docs/value_tape_exact_speed_20260923.md`; final frozen sources and
  serial drivers/results: `results/fresh/tape_exact_speed_20260923_01a0_v2/`.
  Native mgt_m1 remains SHA1152ef2e...; no production selection or submission.
  Next deployment gate: bank-aware reveal spending and the actual submission runner.

### Wider V9 tape selection evaluation (2026-09-23)
- Report: `docs/value_tape_wide_20260923.md`; frozen sources, designs and all evidence: `results/fresh/value_tape_wide_20260923_01a0/`.
- Completed 106 pairs / 254 full games, with unchanged V9 and original m1. Fresh 32 worlds x live V56/m1: 7 better, 57 identical, 0 worse; mean margin +317 vs V56, +543 vs m1. V56 wins 20 -> 21/32; only 6.6% of its baseline loss deficit recovered. Four of 32 independent fresh worlds improved.
- Fetched 32 recordings from eight submissions rated 2757-2984. All originals reconstruct exactly, but 11 counterfactual playbacks materially break after replacing their original rival; do not count their inflated margins as opponent strength. Remaining 21: +504 mean margin, 2 better/19 same. Opponents still cannot react.
- Added all ten qualifying actual original-m1 games across six opponents rated 2753-2804, with exact native cash/hourly board/private-state equality required first. All ten controls pass; +665 mean, 2 better/8 same, 0 worse, no opponent board divergence. Evil Mango loss -12635 -> -6214 (+6421); Snorlax loss -25467 remains untouched.
- Final audit: all 254 ledgers and action hashes, all 42 source reconstructions, 318 decisions and frozen source hashes verified. Zero measured local time-bank exhaustions; framework setup and competition sandbox enforcement are outside this timing measurement. No production edit or submission. Next research target is coverage of the untouched losses, keeping this completed panel separate from subsequent tuning.

### Cross-thread tape findings (2026-09-24)
- User asked to incorporate suggestions/findings in other project prompts. Read `Refetch game records and diagnose`, the m1/t10/V56 picker comparison, `Review kaggriculture project context`, and `Assess UMG imitation coverage`; integrated the saved production-plan recommendations in `docs/value_tape_cross_thread_findings_20260923.md`.
- User's three-day semantic segment proposal remains relevant: carry plantings, herd/service investment, deliveries, replacement cycles and next-reveal farm state; compile changes on our actual board through the scheduler. V9 commits an existing tape for three days but is not this general compiler. Earlier segment implementations failed execution and replacement-cycle maintenance.
- Fresh 25-game m1 diagnostic: sales shortfalls versus matched rivals 7.4% strawberry, 21.7% wool, 12.7% milk. These are descriptive gaps, not automatic investment instructions. Two unchanged games in the other thread's eight-game V9 sample overlap this thread's exact-recording panel; retain separate estimates.
- Read-only audit of the frozen 64 live matchups: 477/1115 alternatives reject for loss of baseline-preserved cohorts; by day 12/15/18: 59/384 (15.4%), 200/375 (53.3%), 218/356 (61.2%). Other alternatives: 293 not expanded after one scenario, 298 stopped at four-world nonpositive risk, 38 failed final eight-world gate, 9 admitted across 7 selected decisions. Unexpanded routes are not proven unprofitable.
- Snorlax 112109339 (-25467) exact ledger: wool revenue -16297, extra hires -12363, other net +3193. Wool harvested 541 vs 558; sold 516 vs 558; average sale price154.10 vs171.70; 11 own wool still held at finish. Day12 best scout fails four-world economics; all four alternative tapes at each of D15/D18 fail cohort preservation. This motivates repaired service/delivery transitions and costed retirement, not simply dropping the guard or buying more sheep.
- `scripts/audit_cross_thread_tape_findings_20260923.py` creates `results/fresh/tape_cross_thread_20260923_01a0/audit.json` from completed artifacts, with source hashes and ledger/panel-size assertions. No additional games or policy edits; m1 and V9 hashes unchanged. Next implementation remains a separate research policy for repaired transitions and reveal-conditioned production deltas.


### Costed tape transition repairs (2026-09-24; R3)

Research only; native mgt_m1 and frozen V9 unchanged. Report: docs/tape_transition_repair_20260924.md. Scripts value_tape_repair_r1/r2/r3.py add bounded three-day cohort service repairs through the native funded hidden-worker scheduler. R3 validates repairs over 16 shop futures plus 16 separate 6/12h rival-sale-delay stress scenarios; default cooperative 18s decision deadline. Source freeze and all raw results: results/fresh/tape_repair_20260924_01a0/.

Development R1: all32 prior V56 worlds +2 exact m1 recordings, one +2705 vsV9, one -1570,32unchanged. Extra ordinary shop samples (R2,32futures) did not catch the regression. R3 sale-delay stress vetoed that regression and retained +2705 development recovery. Physical repairs succeeded in156/160 initial scouts, but152/160 forecasts had nonpositive risk-adjusted economics.

Frozen new qualification r3holdout24:24 unseen IID eight-shop worlds x liveV56/originalm1 x original/V9/R3 =144 full games. R3 vs original:7better,40same,1worse; mean margin+531.4375 (+294.625 vsV56,+768.25 vsoriginalm1). VersusV9:1better(+1016),47exact same two-seat action streams,0worse; mean+21.1667. Only one repaired commitment in144R3 decisions;194/200 repair scouts preserved cohorts,185 ended with nonpositive value. Fresh repair fresh-11-original_m1 D18route422 keeps sheep(7,4,SHEEP,8),strawberry(8,2,STRAWBERRY,6); tie->win1016; owncash-1260,rival-2276. No additional losing-game deficit recovery fromR3. Fullpackage deficit recovery1.25%. One-world incremental gain is not a broad upgrade. Fresh mean/median/p95/max reveal3.40/2.33/6.97/7.89s, minimum measured bank48.45s, no deadline exhaustion. At most2memory-gated workers; local shared-laptop timing, not official sandbox certification.

Fresh regression shared byV9/R3: fresh-12-v56 seed1895503985 D12route47, native+1692->-838 (-2530). Owncash+1768,rival+4298; own wool sales-44,rival wool receipts+6674. Applying16futures+16delivery stresses to this ordinary switch after evaluation STILL approves(mean+5023,worststress+301). Diagnostic only in ordinary_timing_diagnostic.json; no policy tuning on the holdout. Future rival production/market modeling must address this failure; timing stress alone is insufficient.

R3record42:42additional candidate games on prior32rated recordings+10exactm1anchors; reused controls verified against168file hashes and42exact source reconstructions. All31cases without material opponent-command collapse unchanged vsV9. One+2473 vsV9 on TheEggman112562107 is excluded because baseline,V9,R3all have material frozen-opponent command failure. Original anchors retain+664.6mean vsoriginal, eligible21rated+503.8. Snorlax112109339 remains-25467; EvilMango112543358 retains+6421recovery. No replay timeouts, min measured bank45.30s. Do not count broken playback gains as live strength.

Functional checks and final audits passed; audit_tape_repair_panel.py and audit_tape_repair_recordings.py reproduce summaries. Next reuse candidates: tape_semantic_features.py / verified whole-farm segments for economic retrieval; agents/adaptive_market_order.py::FlowModel for observed rival sale history (not integrated into R3). No new production submission.
