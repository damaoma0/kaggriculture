# First completed V13 cases: actual collections and losses

Read-only inspection of completed live00/live01 confirms all 11 logged exchanges execute on the selected unit and animal. Position reconstruction matches all 120 available hourly snapshots in every run, and all 90 daily milk/wool/egg harvest balances per run match the engine ledger. No engine, agent, or qualification case was invoked for this audit.

These are natural-world comparisons against V12, not isolated season-profit measurements. live00 changes shops at D15, D18 and D24; live01 changes them at D21 and D24. The frozen short fixed-shop component experiment is separate evidence.

| Case | Accepted exchanges | Held units actually collected in those jobs | Removed jobs | Own cash change | Rival cash change | Margin change |
|---|---:|---|---|---:|---:|---:|
| live00 | 6 | 8 wool, 12 milk | 3 water, 1 collect fertilizer, 1 fertilize, 1 care | +3,081 | +3,643 | -562 |
| live01 | 5 | 6 wool, 4 egg, 2 milk | 4 water, 1 fertilize | -2,149 | -3,923 | +1,774 |

The units above are the contents of accepted harvest jobs, not additional season output relative to V12. Later baseline routes often collect the same goods. Every removed job is absent from the actual day's action stream, including commands from other workers; the exchange costs are real rather than merely nominal planner changes.

## First changes before shop divergence

live00 first changes at D12 H15: unit10 harvests four wool at sheep42 instead of preserving an optional water on young wheat31. D13 shed wool is 5 rather than 1. V13 sells four wool on D13 (H1 two units, H4 one, H13 one), versus V12's one unit at H4. Revenue is 160 versus 49; the realized average is lower, 40 versus 49. The wheat survives with one unwatered day and unchanged yield1. By D15 dawn, own cash is +30 and rival cash -66, margin +96, before trading under the changed shop.

live01 first changes at D17 H11: unit2 harvests two eggs at goose62, replacing one water on young tomato61. D18 shed eggs are 9 versus 7. V13 sells nine eggs on D18 versus seven, both averaging 44, revenue396 versus308. The tomato survives with one unwatered day. By D21 dawn, before trading under the changed shop, own cash is +655 and rival cash -118, margin +773. This includes subsequent routing and another exchange, not only those two eggs.

## Every accepted job

| Case/day | Actual harvest | Unit/hour | Displaced job |
|---|---|---|---|
| 00 D12 | 4 wool, tile42 | 10 / H15 | WATER tile31 |
| 00 D16 | 3 milk, tile35 | 8 / H5 | WATER tile23 |
| 00 D19 | 3 milk, tile47 | 5 / H13 | COLLECT_FERTILIZER tile56 |
| 00 D21 | 4 wool, tile42 | 4 / H17 | FERTILIZE tile40 |
| 00 D22 | 3 milk, tile47 | 1 / H8 | WATER tile58 |
| 00 D25 | 3 milk, tile49 | 4 / H23 | CARE tile38 |
| 01 D17 | 2 egg, tile62 | 2 / H11 | WATER tile61 |
| 01 D18 | 4 wool, tile25 | 0 / H9 | FERTILIZE tile4 |
| 01 D22 | 2 milk, tile24 | 4 / H8 | WATER tile14 |
| 01 D24 | 2 egg, tile73 | 3 / H13 | WATER tile64 |
| 01 D27 | 2 wool, tile34 | 4 / H3 | WATER tile23 |

All selected-product inventory balances show zero discarded units on the collection day and following day. Other non-purchased product balances also show zero losses on all exchange days. Wheat discard cannot be fully resolved on seven of those days because successful purchase-unit quantities were not logged; those gaps remain explicit. Thus there is no observed displacement of another measured product by the extra lot, without claiming unmeasured wheat losses are impossible.

Most removed WATER jobs leave a surviving crop with one unwatered day. live01 D27 tile23 becomes a weed, but its strawberry had already entered declared yield decay (`max_lifespan_step=648`, zero held yield) at D27 H0; water cannot stop that decay. This is not evidence that the exchange killed a productive crop. The removed D25 CARE on live00 goose38 is a real future bonus opportunity cost. The D21 live00 FERTILIZE and D18 live01 FERTILIZE removals leave their crops watered and alive but without the planned fertilizer bonus. No blanket inference that all cohort exits or retirements are harmful is made.

## Season quantities do not equal accepted-job quantities

| Product | live00 collected V12 → V13 | live00 revenue change | live01 collected V12 → V13 | live01 revenue change |
|---|---:|---:|---:|---:|
| Milk | 245 → 240 | -1,882 | 110 → 97 | -2,994 |
| Wool | 67 → 68 | +56 | 197 → 204 | +300 |
| Egg | 217 → 229 | +425 | 149 → 169 | +913 |
| Fertilizer | 376 → 376 | -35 | 368 → 375 | +133 |
| Wheat | 747 → 715 | +431 | 557 → 559 | +288 |
| Carrot | 219 → 238 | +1,204 | 489 → 515 | +332 |
| Strawberry | 103 → 103 | +1,283 | 88 → 85 | -571 |
| Tomato | 213 → 210 | +1,749 | 129 → 126 | +147 |

The animal-product totals are sold in full in both runs. Some crop totals differ from sales because stock remains or is discarded; the JSON retains both values. Most notably, final milk collected and sold falls in both cases despite accepted milk harvests. The feature succeeds at executing earlier collections; these two cases do not demonstrate increased milk production or a guaranteed competitive gain.

An inexpensive accepted lot can also have weak sale value: live00 D21's four-wool exchange occurs at a source score of6. The whole next day's nine wool sell for only13 in that natural world, averaging1.44. live01 D27's two-wool score is only0.6, replacing a zero-valued water on an expiring crop. These are not large-profit opportunities merely because a harvest was successfully added.

Sources are the immutable V12/V13 completed live00/live01 rows and both action streams. Reproducible audit: `scripts/audit_kb115lt2_v13_completed_20260928.py`; details and source hashes: `results/fresh/semantic_kb115lt2_recovery/v13_first_completed_audit.json`. The audit contains certified daily stock/sales flows, hourly sale quantities where every request is independently known to fill, next-dawn removed-tile state, and both final ledgers. It does not assign individual sale proceeds to indistinguishable units from one particular harvest.
