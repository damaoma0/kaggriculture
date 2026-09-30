# V8 costs, service and early stock recovery

V8's remaining losses have two different causes in the recorded evidence. One
retains the early wheat-shortage/animal-exit mechanism; the other two have no
unintended animal exits and lose because extra spending exceeds extra revenue.
An isolated KB115LT2 stock-recovery ablation is warranted, but cannot be presented
as a general explanation or guaranteed repair of all three losses.

This report reads saved V7/V8 results, actions and own-private snapshots. It runs
no engine, agent, game worker or qualification. V8 wins5/8 with mean margin994.5.
Shop sequences differ in7/8 V7/V8 pairs, so aggregate changes are descriptive.

## Exact full-game loss decomposition

All rows reconcile revenue difference minus spending difference to final cash
margin. These totals include the opening and every executed action, using final
cumulative ledger index30. They are not the D6-onward service-table deltas.

| V8 loss | Final margin | Revenue minus MGT | Spending minus MGT | Unintended exits |
| --- | ---: | ---: | ---: | ---: |
| live03 | -1,004 | +5,725 | +6,729 | 0 |
| live06 | -3,391 | +4,328 | +7,719 | 0 |
| live07 | -6,720 | -1,040 | +5,680 | 3 |

Spending differences:

| Item | live03 | live06 | live07 |
| --- | ---: | ---: | ---: |
| Land | +4,000 | +4,000 | +4,000 |
| Hires | +2,320 | +1,820 | -950 |
| Cow purchases | +400 | +400 | +800 |
| Sheep purchases | 0 | -500 | +1,500 |
| Goose purchases | +300 | +1,200 | +900 |
| Wheat purchases | -662 | +623 | -267 |
| Fertilizer purchases | -929 | -874 | -993 |
| All seed purchases combined | +1,300 | +1,050 | +690 |

Extra land and inputs also support extra production. These differences are not
individually avoidable-cost estimates: removing land or animals changes routes,
production and both farms' prices. In particular, live06 sells122 more eggs for
$7,098 extra egg revenue, so an indiscriminate goose cut is not established by
the $1,200 extra purchase bill.

Live03's added strawberries and tomatoes earn +$9,187 and+$3,516, while milk
earns-$1,513 and wool-$645. Live06's wool deficit is-$6,181, partly offset by
milk+$2,715, eggs+$7,098 and strawberries+$6,884. Live07's wool is-$7,179 and
milk-$1,874, while extra carrots earn+$10,560. These are different mixes of
output and costs, not one shared insufficient-production pattern.

## Quantity versus delivery-price evidence

Using rival average realized price as an algebraic reference,
revenue difference equals quantity difference at that price plus our sold
quantity times the difference in average realized prices. This is descriptive;
it does not hold prices fixed in a valid counterfactual.

| Product/case | Quantity component | Timing/price component | Total revenue difference |
| --- | ---: | ---: | ---: |
| Wool live03 | +1,494 | -2,139 | -645 |
| Wool live06 | -5,262 | -919 | -6,181 |
| Wool live07 | -7,155 | -24 | -7,179 |
| Milk live07 | -4,134 | +2,260 | -1,874 |
| Strawberry live07 | -1,094 | +3,099 | +2,005 |

Thus live07's largest wool loss is almost entirely fewer units at essentially
the same average selling price. More general selling retiming cannot supply
those missing units. Live03 does have a wool timing/cohort-age issue worth
investigating, but the saved averages do not identify a profitable sale override.
The persistent melon difference includes both fewer opening plants and lower
realized prices; it is recorded without recommending a melon expansion from
the revenue gap alone. Lower fertilizer sales also reflect fertilizer use and
collection, not simply unsold stock.

## KB2 service improves while early establishment remains slow

| Service diagnostic | V7 | V8 |
| --- | ---: | ---: |
| Committed surviving animal-days | 3,071 | 3,134 |
| Committed unfed production-days | 174 | 130 |
| Productive fed+care days | 2,075 | 2,252 |
| Banked bonus lost on unfed production | 23 | 23 |
| Committed newborns left unfed | 109 | 117 |
| No-intent exits | 11 | 14 |
| No-intent exits with future production | 10 | 11 |
| Exits before first production | 4 | 4 |
| Young committed crop losses | 1 | 0 |
| Hire shortfall | 0 | 0 |

Boundary service ends atD28; D29 has no following morning. More surviving animals
change the denominators. Three V8 no-intent exits have no future production, so
they should not automatically be counted as profitable recovery opportunities.

For animals purchased D6–10, V8 eventually places116, with30 placed on a later
day and44 total animal-days of delay. V7 places115, with30 delayed and38 delay-days.
The corresponding MGT farms place77, with8 delayed and9 delay-days. FIFO matching
counts aggregate purchase-to-placement delay, not identities while in the shed.

D6–10 paid unfinished crop-job counts are114 inV7 and111 inV8; paid unfinished
animal-job counts are37 and40. These sum daily backlogs, not distinct purchases.
All requested daily animal and seed purchases succeed on40/40 days in both
groups. V8 completes356 plants versus347 inV7, and109 new animal placements
versus110. The early physical bottleneck is still delivery/placement after
purchase rather than failed orders or missing hires.

The losses differ here too. Live03 has only two early delay-days. Live06 has
eight, including two sheep boughtD8 and placedD11. Live07 has eight, including
one sheep boughtD9 and placedD12. A three-day sheep placement delay can remove a
whole seasonal production date, but no dollar benefit of avoiding that delay is
claimed without a controlled continuation.

## Output relative to the same calendar assumption

The numerator is actual harvested units D6–29, ledger[30] minus ledger[6]. The
denominator applies the same85%-care calendar to actual observed morning cohorts.
It combines care, held yield, retirement and collection timing, and excludes
counterfactual future production of animals already lost.

| Group | Milk | Wool | Eggs |
| --- | ---: | ---: | ---: |
| V7 own | 96.3% | 98.6% | 77.9% |
| V8 own | 97.9% | 94.9% | 86.2% |
| V8 same-game MGT | 91.3% | 97.1% | 104.1% |
| Authorized native modern100 training | 91.8% | 91.7% | 92.6% |

Ratios above100% are possible because the model assumes less than perfect care.
They are not profit ratios. KB2 closes some of the observed goose-service gap,
while milk and wool aggregate realization are already near the native reference.
This weakens the case for globally suppressing herds purely from the old
executor's goose calibration. The corrected modern/V5 window provenance is
`reveal_feature_research_correction_v2.json`; no fitted model or runtime changed.

## Early partial-pickup mechanism still present

Three earlier logged first-shortage states have exact V5/V8 action prefixes for
both players, through the pickup, and identical saved current private snapshots:

* live04 D7: farmer picks1 wheat from the earlier logged1/3 request. Later it
  cares for sheep43 atH5 and sheep42 atH8 with zero carried wheat. Both animals
  are committed and finish the day unfed.
* live06 D8: worker9 picks1 from the earlier logged1/2 request. It later cares
  for cow24 atH12 with zero wheat; the cow finishes the day unfed.
* live07 D7: worker9 picks2 from the earlier logged2/4 request. It cares for
  cow47 atH11 and sheep48 atH14 with zero wheat. Both animals were bornD6, were
  meant to remain, and escape afterD7 before their first production.

V8 internal tier logs were not saved, so the original requested quantity comes
from the prior exact-prefix event, not a newly observed V8 cursor. The physical
pickup, empty inventories, care commands, missed feeds and exits are directly
present in V8's saved records. This is sufficient evidence to test the bounded
early recovery on KB2, not proof of the counterfactual profit or every route
identity. Other first-event prefixes differ and are not called matched controls.

The earlier broad recovery changes all routes and can trade survival for worse
care or planting. Keep it an isolated ablation against an explicit frozen KB2
baseline, separate from the reveal-feature quantity change. Its strongest
remaining diagnostic target is live07; live03/live06 still require quantity,
capital or cohort-timing improvements even if early feeding is repaired.

## Artifacts

All are under `results/fresh/semantic_strategy_20260928/`:

* `service_audit_v7_v8.json`: per-animal observed service, intent and exits.
* `early_allocation_v7_diagnostic.json`, `early_allocation_v8_diagnostic.json`:
  admitted counts, successful purchases and paid backlog.
* `v8_cost_service_diagnostic.json`: exact cost decompositions, all product
  quantity/price splits, placement queues and matched pickup evidence with hashes.

The final report is reproduced by
`scripts/diagnose_semantic_v8_cost_service_20260928.py`, after the existing
`audit_semantic_strategy_service_20260928.py` and
`check_semantic_early_allocation_20260928.py` saved-data audits. No game was run.
