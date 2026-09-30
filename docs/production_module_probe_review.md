# Four-plot carrot module probe: independent review

## Follow-up validation

The parent addressed the thin harvest attribution finding after this review. The runner now instruments successful PLANT and harvested inventory gains on each of the four target tiles. All 24 configurations were rerun; all 96 plot instances have exactly one successful planting and their expected individual harvest (`per_tile`, `per_tile_passed`). The earlier empty `successful_plants` field comes from the older generic instrument and is superseded by this dedicated audit. The original findings below are retained to distinguish what prompted the additional validation. The source planting-date shift is explicitly documented as a relative-age transfer test, not exact replay fidelity.

## What the completed proof supports

`results/fresh/production_modules/probe/summary.json` records 24/24 completed games: three four-plot carrot schedules (`umg`, `majkel`, and two of each in `mixed`), four natural-RNG seeds, both seats, against the active V50 agent. In every row, recorded expected and actual carrot harvest totals match; `missing_workers` is zero; route `rejections` and `missing_inputs` are empty. The daily route report enumerates 24 visit orders when all four plot jobs are active and selects a route that fits the day. This is good evidence that these particular care-and-harvest schedules can execute with a reserved farmer and four reserved tiles under the tested engine conditions.

It demonstrates the harvesting contrast encoded in the templates: four age-3 fertilized carrots per plot in the UMG arm (16 total), versus two units per plot harvested at age 2 in the Majkel arm (8 total); the mixed arm yields 12. It does not establish a new learned policy: the modules are fixed event lists, run from day 12, and inspect no shop-demand trigger.

The reported mean cash gain above starting cash is +$228.50 UMG, +$230.00 Majkel, and +$229.25 mixed. These are valid outcomes for the isolated, reserved-capacity probes; they are not paired gains over a no-module baseline or estimates for a full farm.

## Economic and scope limits

- **No full-farm profitability conclusion.** The probe gives this module the farmer and four plots, with no V50 crop/animal route competing for their time or land. It has no paired full-agent/no-module control, no wage or lost-production charge for the reserved route, and no value for leaving those plots available to another crop. Cash, carrot revenue, and spend in the probe are execution ledgers under a shared market, not incremental full-farm profit.
- **Fertilizer cost is market-specific.** UMG buys four fertilizer units for $316/game ($79/unit in these runs); mixed buys two for $158/game. These are the observed costs in these market paths, not a stable unit-cost assumption. The UMG module earns two additional carrots per tile over the age-2 Majkel template by keeping each plot through age 3, applying fertilizer, and adding a third service day. That is four extra tile-days for the four-plot cohort, plus extra route work and fertilizer spend. The proof does not price those tile-days or compare their displaced full-farm use. The similar mean cash gains across bundles do not isolate the marginal value of fertilizer or the extra day.
- **Repeated templates are not four independent recorded cohorts.** Each four-plot config repeats two source-tile templates twice. This proves repeatability of the chosen schedule, not that the leaders ran four identical cohorts in that sampled episode.
- **UMG source-date mismatch.** The generated UMG records cite planting day 14, while the fragment has `PM_START_DAY = 12` and plants for event day 0. The proof therefore runs that template two days earlier than the cited replay planting. It remains a valid execution test for the relative-age schedule, but it is not a date-faithful replay of the UMG source instance.
- **Harvest assertion attribution is thin.** Every result has `successful_plants: {}`. Expected-vs-actual aggregate harvest matches are reassuring, but the summary does not expose a nonempty successful-plant count or per-tile audit linking each harvested unit to each new planting. Keep the claim at aggregate output agreement unless the runner's assertion source is independently documented.

## Contracts covered and still unproven

Covered in this panel: day-0 plant plus water, required fertilizer purchases for the UMG schedule, fertilize/water and age-3 harvest, the age-2 no-fertilizer schedule, route length and farmer availability, and the aggregate harvest match. The fragment sells shed stock at day-end turns; revenue appears in each result, but there is no separate proof of every sale unit or of delivery under full-agent shed congestion.

Not covered: purchase failure under constrained cash/order capacity; fertilizer carried by a different hand; blocked or weeded planting tiles (the code has rejection/fallback branches, but this panel did not exercise them); route competition with the base agent; seed/fertilizer opportunity cost versus a displaced crop; effects across varied shop draws/opponents; or full-farm profit and margin. The extraction artifact contains 40 eligible cycles, but this proof executes only four selected source cycles (two per leader), repeated to fill four plots. The probe's no-rejection results show those fallback paths were not needed here, not that they are safe in general.

**Recommendation:** accept this as an executor feasibility proof for the listed fixed carrot schedules only. Before using it in a full-agent mix, align or relabel the UMG source day, make the per-tile harvest assertion visible, then price the age-3/fertilizer upgrade against the route and crop it displaces in a paired full-agent comparison.
