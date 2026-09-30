# Minimal mgt_m1 changes, 2026-09-22

Three isolated changes were built directly from unchanged mgt_m1. No new planner, tape router, crop system or execution controller was introduced. The selected experimental candidate is mgt_micro_wool_upturn; the baseline file remains unchanged.

## Changes and development evidence

Six historical diagnostics (four identified failure cases and two wins) ran every arm and the baseline. All six baseline controls exactly reproduced recorded actions and both final cash values. Then all four arms played 12 fresh random seeds, both seats, against responsive V56: 96 full games.

| Independent change | Policy edit | Mean paired margin change | Better / worse / unchanged |
|---|---|---:|---:|
| mgt_micro_single | Minimum sheep deficit 2 → 1; existing profitability/cash checks retained | +0 | 0 / 0 / 24 |
| mgt_micro_yarn18 | D18 Yarn Store adds two to the target; D19 purchase cutoff retained | +0 | 0 / 0 / 24 |
| mgt_micro_wool_upturn | Allow the existing three-day wool forecast above today’s price when a Yarn Store is open; retain value discount and wage checks | +94 | 6 / 0 / 18 |

The first two changes did not change any actions in the six diagnostics or the 24 development games per arm. Their inactivity is evidence that target eligibility alone did not unlock an investment, not evidence that an executed purchase was unprofitable. For example, allowing one sheep in episode 111743130 reached the evaluator but produced modeled profits of −2,893 and −2,298 on D18/D19. Raising the D18 target in episode 111678108 produced modeled profits of +51 and +705, still below the unchanged 3,000 requirement.

The wool forecast change replaces one return statement with six lines. m1 previously used the smaller of today’s quote and its existing three-day forecast, so a predicted price recovery could never justify earlier feed/care. The candidate removes that upper bound only for wool with an already revealed Yarn Store. It retains the existing sheep purchase and staffing rules and the existing forecast model. This also affects existing-sheep payout/adoption valuation, not just CARE commands. The original 20% value discount and 1.5-times marginal-wage check stay active.

The diagnostic change gained 611 margin in episode 111678108: wool revenue +870, feed purchases +203 and wages +144, alongside smaller wheat effects. It lost 494 in 111261836: two additional feeds, no net additional care or hand-days, and weaker realized revenue. Both cases were retained. Development selection used the largest positive mean paired margin with positive own cash and no errors/time overruns; it selected the wool forecast change without combining edits.

An exact physical-work trace explains the latter regression. Extra feeding on tile (3,4) kept a sheep alive across the donor's D26 DIG/PLANT-WHEAT conversion, so that crop work could not execute. The added stop also delayed an existing worker's route: the sheep at (6,2) missed its D26 harvest and three wool units were lost when it escaped. Wool generated rose 67 → 69, but harvested/sold fell 67 → 66. This is a concrete retirement/replacement and route-capacity interaction, not a reason to abandon the small-change approach. Trace artifacts are in case_traces/; scripts/trace_m1_micro_case.py reproduces both arms through the official engine.

## Untouched live confirmation

The same frozen candidate and unchanged m1 each played all 24 reserved confirmation seeds, both seats, against live V56: 96 additional full-game executions. These seeds were frozen before development outcomes. They are separate from the project's untouched 3000-Elo qualification panel.

| Metric | Confirmation result |
|---|---:|
| Mean paired margin change | +85 |
| Seed-bootstrap 95% interval | +7 to +214 |
| Mean own-cash change | +80 |
| Better / worse / unchanged games | 7 / 0 / 41 |
| Wins vs V56, baseline → candidate | 32/48 → 32/48 |
| Worst paired change | +0 |
| Best paired change | +1,359 |
| Mean wool-output change | +1.15 units |
| Mean wage change | +33 |
| Matching shop paths | 48/48 |
| Runtime / internal policy errors | 0 / 0 |
| Own actions above 1 second | 0 |

The interval resamples whole seeds, averaging both seats within each seed. Both seats are not independent worlds. Natural engine RNG is preserved; shop draws can in general diverge through policy-dependent weed draws. All completed live games have 719 actions, 720 states, DONE statuses and both cash ledgers reconciled. Runtime timings are measured offline; they are not an online submission certificate.

## Historical regression check

The frozen selected candidate was also evaluated on every locally available game of submission 56395605: 198 games, including all 89 audited losses and 109 wins. This is 198 of the 305 known completed public matches: all losses but only 109 of 216 wins. Its mean reflects that availability mix and is not an unbiased estimate of ladder gain. Six already executed diagnostic candidate rows were reused with explicit source provenance. Opponent actions and shop schedules are recorded; the comparison is to original m1 rewards, not a responsive opponent or an independent qualification.

| Cohort | Mean margin change | Better / worse / unchanged | Wins gained / lost |
|---|---:|---:|---:|
| All available matches (198) | +131 | 34 / 5 / 159 | 2 / 0 |
| Original losses (89) | +221 | 25 / 3 / 61 | 2 / 0 |
| Original wins (109) | +58 | 9 / 2 / 98 | 0 / 0 |
| Original losses below 2500 (58) | +231 | 17 / 2 / 39 | 1 / 0 |

The worst historical change is -494; the best is +2,171. Against opponents below 2500, the 58 original losses have mean change +231. Complete per-match results, including regressions, are retained in ladder_summary.json. This losing-cohort mean should not be presented as an expected ladder gain.

## Interpretation

The small forecast change has positive held-out evidence for a modest cash-margin improvement against V56. Its scope and measured benefit remain small; it does not resolve the larger strawberry/herd-capacity gap or establish a rating gain. The baseline agent was not edited or submitted. The two inactive purchase changes were not bundled into the selected candidate. A specific next experiment is a small guard against preserving an animal when the tape explicitly repurposes its tile, evaluated separately before combination.

Panel full-game executions: 24 initial historical diagnostics + 96 development + 96 confirmation + 192 additional historical checks = 408. Reused diagnostic rows are not additional executions. Two additional full-game trace reruns diagnose episode 111261836; these are not independent evidence or additional worlds.

Artifacts: [candidate](../agents/mgt_micro_wool_upturn.py), [exact small diff](../results/fresh/m1_minimal_20260922/mgt_micro_wool_upturn.diff), [frozen design](../results/fresh/m1_minimal_20260922/design.json), [confirmation summary](../results/fresh/m1_minimal_20260922/confirmation_summary.json), [historical summary](../results/fresh/m1_minimal_20260922/ladder_summary.json). Baseline SHA-256 remains 1152ef2e12c4535dbc381b9c54ac7d7a0b1a9ad3d0a8018a7567dcf5c4a52470. Candidate SHA-256 is 12f91b4bdd3970a397f16a1b39d1bbcaad99a74e794c14c640f9b476bbaf7c1e.

Reproduction: scripts/experiment_m1_micro.py (freeze, historical, development, confirmation); scripts/evaluate_m1_micro_ladder.py; scripts/report_m1_micro.py final. The bundled Python 3.12 runtime used the existing project kaggle-environments 1.32.7 packages. No dependency changes were made.
