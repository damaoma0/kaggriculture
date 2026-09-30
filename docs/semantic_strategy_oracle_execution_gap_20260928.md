# Exact-layout execution gap against native DSM

The eight D6 oracle controls isolate a substantial execution gap even with the original tile layout and actual future type-change plan. Native DSM averages +17,738.625 margin; exact-layout KB averages −3,238.625, a paired loss of 20,977.25. Own cash falls 3,549 while the recorded rival gains 17,428.25. These are old-world component diagnostics, not causal new-world policy qualification. This analysis reads saved games and runs no simulations.

The dominant mechanism is delayed early cohorts and reduced early service, followed by a persistent rival price benefit. The physical yield accounting rules out increased capped or discarded milk, wool or strawberries as the D11–17 explanation.

## Rival price effects verified within each world and day

Both arms use identical recorded rival actions and shops. Rival physical ledgers match on every day in all eight worlds. Rival daily sold quantities match on every milk, wool and strawberry sale day, so the following revenue gains are changes in realized price on equal quantities, rather than an inference from averages across different worlds.

| Rival product | Identical positive sale days | Extra revenue per world |
|---|---:|---:|
| Wool | 114 | +6,214.00 |
| Strawberries | 113 | +4,926.25 |
| Milk | 140 | +4,067.25 |
| Three products | 367 | +15,207.50 |

These products explain 85.0% of the rival's total extra revenue of 17,894.625. Its extra spending is 466.375, leaving the observed 17,428.25 cash gain. Other products also have equal daily quantities except two wheat observations and one carrot observation. The script separates quantity and realized-average-price terms on matched sale days and leaves revenue unallocated when one arm has zero sales; it never invents a missing price.

The benefit accumulates after the early production gap: rival cash is +273 at D11, +3,274.5 at D18, +10,089.875 at D24 and +17,428.25 at season end. In episode 112593664, our exact-layout arm gains 13,176 own cash while the rival gains 29,296. Its extra wool and milk revenue is 13,260 and 11,666 respectively, at unchanged daily sold quantities. Own profit alone would give the wrong ranking here.

The engine's `_commit_unit` adds market inventory only for sales above $1. Consequently, cumulative gross sold-unit differences do not always equal market-inventory differences after floor-price dumping. The audit retains actual dawn inventory/prices and explicitly reports the implied difference in excluded $1 supply. It does not assume every delivered unit depresses prices equally. At D18 the observed mean wool/milk/strawberry price differences are +31.75/+33.25/+4.375; at D24 they are +38.625/+18.875/+19.375.

## Physical generation, collection and sale are distinct

The table reconciles all quantities over D11–17, exact minus native, per world. Generation is the amount due at midnight from actual surviving cohorts, their birth dates, observed feeding and prior care bank, or watered fertilizer state. This uses the official strawberry schedule of four productions two days apart. Held yield and private stock are observed at both boundaries.

| Product | Midnight generation | Change in yield held on tiles | Collection | Change in collected stock held | Sales |
|---|---:|---:|---:|---:|---:|
| Wool | −16.375 | −4.375 | −11.875 | +1.125 | −13.000 |
| Milk | −11.250 | +1.250 | −12.500 | +3.250 | −15.750 |
| Strawberries | −9.250 | −1.375 | −7.875 | −0.875 | −7.000 |

In all eight exact games, these three products have **zero yield lost to capping/removal and zero discard after collection during D11–17**. Native loses only 0.125 wool per world to the combined cap/removal term. Therefore the exact arm's collection deficit is mostly less physical generation; milk also has 1.25 more yield left on tiles and 3.25 more collected units left in stock. Selling that milk sooner could reduce part of the delivery gap, but cannot replace the missing generation.

The accounting derives the combined cap/removal term as potential generation minus collection minus the change in held tile yield. Daily observations cannot distinguish capping from destroyed uncollected yield when this residual is positive. Here it is zero in the exact arm, so that ambiguity does not affect the conclusion.

## Delayed cohorts dominate the early generation deficit

Among native births on D6–10, first observed same-tile/type births in the exact arm are delayed as follows:

| Asset | Native births | On time | Delayed | Delay distribution |
|---|---:|---:|---:|---|
| Cow | 46 | 29 | 17 | 10 by 1 day; 6 by 2; 1 by 4 |
| Sheep | 38 | 22 | 16 | 6 by 1; 2 by 2; 6 by 3; 2 by 4 |
| Goose | 45 | 24 | 21 | 19 by 1; 2 by 2 |
| Strawberry | 125 | 65 | 60 | 37 by 1; 23 by 2 |

Matching stops at the next native replacement on that tile. A delayed first observed birth can include replacement after a same-day loss that is absent from dawn records, so these are observed cohort delays, not a claim that every delay was a missed PLACE command.

Comparing only identical tile/type/birth cohorts surviving each night in both arms attributes −4.125 wool, −0.25 milk and −2.25 strawberry generation per world to different service on the same cohort. Nonmatching cohorts account for the remaining −12.25 wool, −11 milk and −7 strawberry units. This excludes deliberate native exits from the matched service comparison. It does not classify all animal retirement as harmful.

Early service also matters before output appears. At D11, the exact farm has 10.625 fewer banked sheep care units and 5 fewer cow care units per world, with 2.125 more hungry sheep and 1.625 more hungry cows. Across identical cohorts on D6–10, native feeds sheep on 3.375 occasions per world when exact does not, versus 0.5 in the opposite direction; for cows those counts are 3 versus 1. These early omissions reduce first-production bonuses. Later care recovery does not retroactively produce or sell those units.

The D6–10 workload shows 263 extra PASS commands per world, 136.625 fewer moves, 10.125 fewer PLANT commands, 18.625 fewer FEED and 20.125 fewer CARE. This is compatible with the separately reproduced partial-wheat-pickup failure and delayed land-route work. Aggregate idle time does not establish that every omitted job was feasible for a particular worker.

## Repair priorities supported by these observations

1. Complete admitted D6–10 cohorts on their intended dates, including the fourth-quadrant backlog. Native oracle controls also buy their fourth quadrant late: it is first visible at H14 in two games and H15 in six. They have 11–13 hands, median 12, already hired by H2; a late land purchase alone does not force delayed planting.
2. Preserve feed and useful care for committed early animals when a planned wheat pickup is short. The two independent recorded-action continuations already recover three premature exits; full-season impact still requires the separate ablation. Keep explicit retirement protections.
3. Reduce unnecessary milk collection-to-sale delay after D11, while measuring both players' margin. Blanket extra harvest or fertilization is not established as the main repair: early missing generation dominates and the exact arm has no D11–17 capped loss for these products.

These findings do not establish an optimal repair or a profit value for each restored unit. Cohort timing, service, selling and shared prices interact, so each candidate needs a paired fixed-world test before a performance claim.

## Reproducibility

`scripts/audit_semantic_oracle_price_gap_20260928.py` writes `results/fresh/semantic_strategy_20260928/oracle_diagnostics/d6_exact_vs_retile_v3/exact_vs_source_product_audit.json`, SHA256 `da1e9eb6053039287050cd505613e44f2239e15f7431a1a35f0440a3ea59f9a3`. It records every native/exact result and action hash, per-world daily accounting, cohort checkpoints, generation balance and observed market evidence. Four timing/attribution tests pass. The inspected official engine source has SHA256 `bc8a54879ef02c7ea64b8b333d6a976f0ea65c4949149d01f463f23bccee653e`.

Native D10 hourly hire/land evidence and successful planting totals are saved in `native_d10_labor_audit.json` in the same directory. The partial-pickup diagnoses and bounded continuations are documented in `docs/semantic_strategy_service_audit_20260928.md`.
