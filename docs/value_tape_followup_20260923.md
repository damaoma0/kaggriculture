# Tape matching follow-up — 23 September 2026

## Main result

**The corrected selector turns another historical loss into a win: −12,585 → +5,864, a recovery of 18,449.**
Our own cash improves by **7,066**; rival cash falls by **11,383**. The earlier **10,034** wool recovery remains selected.

These named historical cases are **development evidence**. Separate frozen live tests produced one new **+3,783** improvement in twelve V3 pairs; eleven stayed unchanged. Six further V4 pairs all stayed unchanged. This is a small confirmation sample, not proof of broad superiority.

## What changed

1. **Forecast rival sales from the appropriate family of farms.** The original model extrapolated currently occupied plots and sold daily output at hour 1. The first replacement, trained on older UMG games, improved on that older population but still mispriced modern opponents. The final model retrieves from 75 older plus 40 modern verified training games, using public tile types, birth dates, held yield and care state. Twenty modern test games and all nineteen earlier target cases are excluded.
2. **Include delivery timing and future planting.** Use successful donor transactions at their observed hours, update projected rival boards daily, and correct quantities for differences between visible cohorts using official tile mechanics. Donor future shops are compared with sampled scenario shops, never the target’s actual future.
3. **Use eight shop futures.** At each unknown reveal every shop type occurs once across the eight scenarios. Duplicate shops within a world remain possible. These are paired worlds shared by all candidates.
4. **Complete balanced evaluation before cash admission.** V3 screened on our expected cash after only the first four worlds. That prematurely discarded the 18,449 opportunity. V4 uses the first four for margin ranking, then applies cash and downside admission after all eight.
5. **Protect existing cohorts and price the transition.** Continue the actual native executor through the official engine, accounting for seeds, animals, feed, fertilizer, wages, sales and market effects. Protect starting long crops/animals that the native baseline would retain at the next reveal; reject extra failed hires. Commit only until that next reveal.

The existing native agent is unchanged. These are research selectors, not a competition-time-budget implementation.

## Exact picking procedure

- Start with native adaptive continuation, the incumbent tape, and the native reveal-time choice. Fill a maximum-seven shortlist with two new candidates at each board-Hamming limit 8, 14 and 24, ordered by revealed-demand distance then Hamming distance. The cap may cut off later additions.
- For each sampled world, rank rival training farms by public physical/cohort distance plus 0.6 times revealed-shop distance. Among the nearest twelve, use 0.25 times sampled-future-shop distance and rotate among the best three to represent different continuations.
- Run four full-season projections for each candidate. V4 advances the best two candidates with positive risk-adjusted margin and no cohort/hire protection failure, plus native control, to eight projections.
- Score = mean projected margin gain − 0.5 × population standard deviation. Require score > 350 and mean own-cash gain > 0. Maximum forecast setback must be no worse than max(500, 25% of mean margin gain). The 25% risk budget is a declared research setting, not a guarantee.
- Choose the highest-scoring admitted route; otherwise retain native. Route zero is valid. Force the chosen route for three days, then restore native routing.

**The 18,449 recovery also passes the original fixed 500 downside limit. It does not depend on the relaxed risk budget.** Its smallest projected margin gain is +1,208.

## Rival forecast validation

Mean absolute error in cumulative net sold units per product, measured at day 15 on twenty excluded modern games:

| Horizon | Original cohort extrapolation | Older-only retrieval | Mixed-family retrieval |
|---|---:|---:|---:|
| 3 days | 6.82 | 8.31 | 1.12 |
| 6 days | 8.66 | 12.45 | 2.39 |
| 15 days | 32.49 | 36.43 | 12.36 |

That is **84% lower error over three days, 72% over six, and 62% through season end**, relative to the original extrapolation. Production/sales forecast accuracy is separate from policy profit.

The older-only model had reduced end-of-season error from 57.66 to 25.09 on thirty excluded older games, but worsened modern-game error from 32.49 to 36.43. This exposed a population mismatch; adding the modern training sample corrected it.

## Large strawberry recovery: episode 111262874, day 12

Revealed shops: **Ice Cream, Yarn, Pet Cafe, Brunch**. Future actual shops were not supplied to the selector.
The chosen donor is **110025609, route 184**. Its current board has Hamming distance zero, but its future production choices differ substantially.

| Metric | Native | Selected continuation | Change |
|---|---:|---:|---:|
| Our cash | 110,635 | 117,701 | +7,066 |
| Rival cash | 123,220 | 111,837 | -11,383 |
| Our margin | -12,585 | 5,864 | +18,449 |

Semantic changes observed in successful engine actions:

- On day 12, plant **eight strawberries instead of two**, and **two tomatoes instead of seven**; buy a cow. Other rotations also change later.
- Avoid the native plan’s two sheep purchases on days 15 and 16.
- All starting cohorts that the actual native continuation retained at the day-15 boundary also survive in the selected continuation.
- Through season end: **+97 strawberry, +25 milk, +24 carrot**, with **−82 wool and −28 tomato** produced/sold. Wages fall by 432.

Our revenue rises **5,541**, and total spending falls **1,525**, reconciling to **+7,066 cash**.

| Own revenue change | Amount |
|---|---:|
| Strawberry | +6,245 |
| Milk | +1,886 |
| Carrot | +1,028 |
| Wool | -567 |
| Tomato | -916 |
| Wheat | -1,269 |
| Fertilizer | -804 |
| Egg | -62 |

Rival quantities sold remain unchanged in this recorded-action counterfactual. Lower strawberry and milk prices cut rival revenue by **10,424** and **2,102**, partially offset by other goods. Rival revenue falls 11,040 and spending rises 343, giving **−11,383 cash**. This is why competitive recovery is much larger than our own cash gain.

Projected margin gains across eight public-only worlds: +8,826, +17,241, +3,090, +10,849, +19,454, +1,208, +2,628, +6,650.
Projected own-cash gains: +1,894, +8,109, -10,394, -3,483, +14,276, +1,254, -3,124, -2,820.
The first four average −968.5 cash; all eight average +714. This explains the old premature-screening veto. The full-world margin score is +5,572.

This route’s historical outcome was known from earlier counterfactual exploration. The new selection is public-only, but the case is therefore explicitly retrospective development evidence.

## New independent live improvement

Seed **2867821829**, seat 0, day 12, donor **109863155 / route 136**:

| Metric | Native | Selected | Change |
|---|---:|---:|---:|
| Our cash | 86,350 | 91,120 | +4,770 |
| Rival cash | 81,527 | 82,514 | +987 |
| Our margin | 4,823 | 8,606 | +3,783 |

A responsive V56 plays both sides of the counterfactual. Shops are fixed identically and both prefixes reproduce. The chosen tape buys one additional sheep on day 14. Successful postdecision work changes by **+53 feeds, +51 care actions, −39 waterings and −24 fertilizer applications**.
Production increases **22 wool, 49 eggs, 20 milk**, while carrot, tomato and strawberry output decrease. Revenue rises 3,624 and spending falls 1,146; rival cash rises 987. Thus our own +4,770 becomes a competitive **+3,783**.

V4 has exactly the same two finalists as V3 at this checkpoint (routes 136 and 137); its screening correction does not remove this selected candidate. This is an equivalence check using the saved forecasts, not a second independent live success.

## What happened to the earlier false positive?

The previously chosen route 196 lost **2,456** under its original actual shop sequence. Across sixteen independently sampled continuations of the same checkpoint, it gains only **152.375 on average**, with **nine improvements, seven regressions**, a minimum of −2,456 and maximum +2,749. The earlier +3,000 model expectation was overconfident.
With mixed-family rival forecasts, this candidate’s eight projected margin changes are -681, +1,193, +4,462, +3,472, +2,049, +3,334, +476, -273.
It now fails the existing downside admission check (−681 versus a 500 budget). This is a diagnostic rejection of that candidate; it does not establish that every future loss is preventable.

## Complete panel accounting

| Panel | Role | Pairs | Switches | Mean margin change | Improved / worse / unchanged |
|---|---|---:|---:|---:|---|
| V3 seven historical cases | Development | 7 | 1 | +1,433 | 1 / 0 / 6 |
| V3 new live worlds | Independent frozen panel | 12 | 1 | +315 | 1 / 0 / 11 |
| V4 new live worlds | Independent frozen panel | 6 | 0 | +0 | 0 / 0 / 6 |
| V4 three named historical cases | Development | 3 | 2 | +9,494 | 2 / 0 / 1 |

V4 selected the +18,449 strawberry recovery and retained +10,034 wool; it made no change in episode 111287532. The two live versions ran on different seeds, so their panel means are not a paired comparison between versions.

All fresh live outcomes:

| Version | Seed / seat | Reveal day | Route | Baseline margin | Margin change | Own cash change |
|---|---|---:|---:|---:|---:|---:|
| V3 | 2061741926 / 0 | 18 | native | 8,875 | +0 | +0 |
| V3 | 2132326042 / 0 | 15 | native | 5,716 | +0 | +0 |
| V3 | 2225979671 / 0 | 12 | native | 14,448 | +0 | +0 |
| V3 | 2354389071 / 0 | 18 | native | 8,950 | +0 | +0 |
| V3 | 2696595234 / 0 | 15 | native | 627 | +0 | +0 |
| V3 | 2761107011 / 1 | 18 | native | -6,305 | +0 | +0 |
| V3 | 2867821829 / 0 | 12 | 136 | 4,823 | +3,783 | +4,770 |
| V3 | 3201420783 / 1 | 18 | native | -4,146 | +0 | +0 |
| V3 | 3308495287 / 1 | 15 | native | 86 | +0 | +0 |
| V3 | 3632728259 / 1 | 15 | native | -2,139 | +0 | +0 |
| V3 | 3671417232 / 1 | 12 | native | 2,284 | +0 | +0 |
| V3 | 3863749308 / 1 | 12 | native | 4,418 | +0 | +0 |
| V4 | 1466168762 / 0 | 15 | native | 14,622 | +0 | +0 |
| V4 | 2517713773 / 1 | 12 | native | 6,827 | +0 | +0 |
| V4 | 3039837067 / 1 | 18 | native | 10,386 | +0 | +0 |
| V4 | 3585322908 / 0 | 18 | native | 5,863 | +0 | +0 |
| V4 | 3755917671 / 0 | 12 | native | -11,782 | +0 | +0 |
| V4 | 3982403692 / 1 | 15 | native | 8,047 | +0 | +0 |

## Verification and limits

- Five regression tests pass: excluded-data membership; public-only deterministic input handling without mutation; shop scenario marginals/prefixes; complete V1/V2 rollout equivalence under the same rival world; and the actual saved-forecast regression for postponing cash admission until all eight worlds.
- All 105 older and 60 modern library replays match recorded final cash and reconcile ledgers. All completed historical controls reproduce their recorded results; all 18 fresh live pairs have equal prefixes, fixed paired shops, complete seasons and reconciled ledgers. Both highlighted traces independently reproduce their original outcomes.
- The original `agents/mgt_m1.py` hash remains `1152ef2e12c4535dbc381b9c54ac7d7a0b1a9ad3d0a8018a7567dcf5c4a52470`.
- Live selector time was **109–208 seconds per decision** under concurrent workloads. This is substantially beyond the competition action budget.
- Rival flow/board forecasts are sampled continuations. They do not reproduce the rival’s full price-responsive policy. Eight future-shop worlds only sparsely cover joint shop sequences. The useful gain is established in specific cases, not uniformly over opponents or worlds.
- Named historical cases informed development. Six independent V4 tests made no switches, so they do not independently confirm the screening fix’s performance on a changed decision.
- One reveal-time intervention was tested per live game. Repeated closed-loop decisions and an inexpensive competition implementation remain future work.
- Cross-process forecast-cache reuse was refused because native memory includes process-local tape identities. The three V4 historical cases were rerun with fresh forecasts; hash checks were not bypassed.

## Files

- Latest selector: `scripts/value_tape_search_v4.py` (uses V3 assessment and the V2 official-engine rollout).
- Rival model: `scripts/rival_trajectory_model_v3.py`; immutable training membership in both library manifests.
- Independent panels: `results/fresh/value_tape_followup_20260923/v3_live/` and `v4_live/`, including designs, source snapshots and all outcomes.
- Detailed recovery trace: `selected_strawberry_recovery_trace.json`.
- New independent gain trace: `v3_live/2867821829-0.trace.json`.
- Tests: `tests/test_value_tape_followup.py`.
