# Margin admission challenger R4 — 24 September 2026

R4 runs frozen R3, then considers fully evaluated ordinary alternatives using competitive margin. It retains cohort protection, the risk threshold, downside limits, and requires no additional failed purchases/hires in any paired scenario. Validated R3 repairs remain available. No extra rollouts are added. Native m1, V9 and R3 source files are unchanged.

Development uses 50 exposed matchups: the earlier 24 worlds crossed with V56 and original m1, plus two repair controls. Qualification uses 24 newly generated IID shop worlds crossed with both live opponents and three arms: native m1, R3, R4. The policy and both panels were frozen before new outcomes.

## Development: 50/50 matchups

| Comparator | Better / same / worse | Mean margin gain | 95% world bootstrap interval | Wins before → after | Wins gained / lost |
|---|---:|---:|---|---:|---:|
| baseline | 9 / 40 / 1 | +774.0 | [+96.3, +1,687.5] | 19 → 23 | 5 / 1 |
| r3 | 1 / 49 / 0 | +161.1 | [+0.0, +493.1] | 23 → 23 | 0 / 0 |
| v9 | 3 / 47 / 0 | +235.5 | [+0.0, +611.8] | 22 → 23 | 1 / 0 |

1 admission overrides across 150 decisions; 49 complete two-seat action streams identical to R3. 0 search timeouts.

| Changed case vs R3 | R3 margin | R4 margin | Margin change | Own cash change | Rival cash change | Override days |
|---|---:|---:|---:|---:|---:|---|
| fresh-22-v56 | -8,908 | -854 | +8,054 | -571 | -8,625 | [15] |

| Opponent, vs R3 | Better / same / worse | Mean margin gain | Wins before → after |
|---|---:|---:|---:|
| original_m1 | 0 / 24 / 0 | +0.0 | 5 → 5 |
| v56 | 1 / 25 / 0 | +309.8 | 18 → 18 |

| Timing | R3 | R4 |
|---|---:|---:|
| Mean reveal seconds | 3.465 | 3.459 |
| P95 reveal seconds | 6.992 | 7.137 |
| Maximum reveal seconds | 13.447 | 13.910 |

Minimum measured remaining time bank: R4 44.98s. Maximum R4 process RSS: 1.91 GiB.

## Qualification: 48/48 matchups

| Comparator | Better / same / worse | Mean margin gain | 95% world bootstrap interval | Wins before → after | Wins gained / lost |
|---|---:|---:|---|---:|---:|
| baseline | 3 / 44 / 1 | +749.7 | [-46.0, +2,236.3] | 20 → 21 | 1 / 0 |
| r3 | 0 / 48 / 0 | +0.0 | [+0.0, +0.0] | 21 → 21 | 0 / 0 |

0 admission overrides across 144 decisions; 48 complete two-seat action streams identical to R3. 0 search timeouts.

| Changed case vs R3 | R3 margin | R4 margin | Margin change | Own cash change | Rival cash change | Override days |
|---|---:|---:|---:|---:|---:|---|

### Full R3/R4 package versus native m1

These changes are shared by R3 and R4; they are not incremental gains from the new admission rule.

| Case | Native margin | R3/R4 margin | Change |
|---|---:|---:|---:|
| qual-04-v56 | -3,900 | 12,205 | +16,105 |
| qual-04-original_m1 | 183 | 17,235 | +17,052 |
| qual-08-v56 | 10,661 | 9,556 | -1,105 |
| qual-23-v56 | 494 | 4,429 | +3,935 |

| Opponent, vs R3 | Better / same / worse | Mean margin gain | Wins before → after |
|---|---:|---:|---:|
| original_m1 | 0 / 24 / 0 | +0.0 | 3 → 3 |
| v56 | 0 / 24 / 0 | +0.0 | 18 → 18 |

| Timing | R3 | R4 |
|---|---:|---:|
| Mean reveal seconds | 3.265 | 3.241 |
| P95 reveal seconds | 7.155 | 7.071 |
| Maximum reveal seconds | 8.720 | 8.509 |

Minimum measured remaining time bank: R4 50.21s. Maximum R4 process RSS: 1.91 GiB.

## Incremental admission cost

Across 1000 calls on the saved recovery checkpoint, the new admission pass takes median 28.9 microseconds and P95 33.3 microseconds. It adds zero rollouts. Full-game timings include the existing search and local contention.

## Separate diagnosis of the retained route-47 regression

Actual margin change: -2,530, comprising own cash +1,768 and rival cash +4,298. The unchanged public eight-world forecast was +4,842. All substitutions below use offline future information and are unavailable to the playing selector.

| Diagnostic | Predicted own change | Predicted rival change | Predicted margin change | Margin prediction error |
|---|---:|---:|---:|---:|
| true_shops_model_0 | -1,203 | -1,085 | -118 | +2,412 |
| true_shops_model_2 | +1,874 | +2,367 | -493 | +2,037 |
| true_shops_model_4 | +1,523 | -299 | +1,822 | +4,352 |
| true_baseline_netted_rival_supply_for_both | +1,466 | +2,844 | -1,378 | +1,152 |
| branch_specific_true_netted_rival_supply | +1,767 | +3,922 | -2,155 | +375 |
| branch_specific_netted_supply_and_rival_costs | +1,767 | +4,299 | -2,532 | -2 |
| branch_specific_ordered_trades_and_rival_costs | +1,767 | +4,299 | -2,532 | -2 |
| branch_specific_ordered_trades_weeds_and_rival_costs | +1,767 | +4,299 | -2,532 | -2 |

Actual same-hour product buy/sell round trips: 5 baseline and 3 candidate. Ordered-trade diagnostics preserve gross order instead of netting these trades.

The branch-specific rival net supply predicts −2,155. Adding the actual rival cost change predicts −2,532, within 2 of the realized −2,530. Preserving gross transaction order and adding actual weeds make no further cash-difference change here. All prescribed ordered trades execute with zero shortfall/excess. One late opponent weed location collides with the projected opponent board, so the weed substitution is not a fully exact physical reconstruction.
This case points to rival sales volume/timing and cost response as the useful modeling target. It does not establish that weeds or trade order are immaterial in other games.

These substitutions are nested diagnostics, not independent causal effect estimates. Net supply, trade order, own weeds and rival costs can interact. Raw outputs record weed collisions and ordered-trade shortfall/excess to expose invalid oracle assumptions.

## Conclusion

R4 fixes a concrete competitive-objective mismatch and preserves the +8,054 development recovery. It produces no incremental result on the 48 fresh matchups. This is a narrow, inexpensive research change; broad recovery or an ELO gain has not been established. Keep it as a challenger and prioritize forecast fidelity and plans that can adapt at future reveals.

## Limits

- Matchups sharing the same shop world are correlated; intervals resample whole worlds. Only 24 new independent worlds are included.
- If every paired difference is zero, a bootstrap interval of [0, 0] describes this observed sample; it cannot rule out rare gains or regressions.
- Development controls were reused by verified content hashes. Their timing was measured in an earlier run, so development timing differences are not a controlled speed comparison.
- Qualification arms run locally with at most two workers and a memory gate; these are synchronous official-engine games, not the actual competition runner. The time bank is measured, not enforced.
- Passing the simulated spending check does not establish accurate rival forecasts. The known route-47 regression is intentionally retained and reported.
- No submission or native-agent replacement is performed.
