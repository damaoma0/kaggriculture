# What is left to gain by modifying her tape (2026-09-20)

Base: `mgt_b1` = router over 584 of her recorded games + feed guard + care top-up + orphan adoption + sell one step
early. All numbers paired, leave-one-out (her worlds, that world's tape removed, live opponent) unless noted.

## The ceiling
| Same 40 worlds | vs V50 | vs frozen benchmark |
|---|---|---|
| her NATIVE tape (her plan made for that world) through our chassis | +8,507 (37-3) | +11,014 (39-1) |
| ours, borrowed tapes + repairs | +4,345 (28-12) | +6,735 (31-9) |
| gap | -4,163 | -4,279 |

We hold about 60% of her edge (51% against V50). Natural seeds, 256 games: 71.5% vs V50, 77.0% vs V48.
Her native tape IS the ceiling of tape modification: anything beyond it means out-planning her, not editing her.

## Production is already hers: the yields carry over
| per plant / animal | ours on a borrowed tape | her native tape |
|---|---|---|
| tomato | 7.00 (10.2 plants) | 7.06 (10.9) |
| strawberry | 7.22 (27.5) | 7.24 (27.1) |
| melon / carrot / wheat | 5.95 / 3.26 / 2.64 | 5.94 / 3.27 / 2.70 |
| wool per sheep / milk per cow / eggs per goose | 19.7 / 25.5 / 34.0 | 19.3 / 24.9 / 34.7 |

The 7.2-vs-4 tomato gap belonged to the V45 chassis. On her tape there is no yield gap and no plant-count gap, so
the executor's original justification (her fertilize / harvest schedule) is gone.

## What the remaining -4.2k is made of (ours minus native, vs V50)
own cash -3,673, rival +490: **price effect -2,785** (milk -1,714, wool -845, strawberry -348), unit effect -213
(tomato -544, wheat -493, wool -371, egg -342, carrot -298, offset by milk +1,550 from the care top-up), our overlay's
spending +675 (hires +368, wheat +346). Concentrated: four worlds lose 13-16k each (multi-Yarn, four-Pizza), the
median world loses 2.7k, 17 of 40 are within 2k of native.
The price effect is not sale timing (every sale-side change is measured null or negative). It is mostly production
not sized to THIS world's demand: a tape from a Yarn-heavier world over-supplies wool where ours has less demand, and
the care top-up adds milk everywhere, including where it only lowers the price.

## Inventory, ranked by value x chance of landing
| # | Modification | Value | How estimated | Build | Tape permits? | Lands in 10 days? |
|---|---|---|---|---|---|---|
| 1 | Care top-up priced with its OWN price impact (stop adding milk / wool where it only moves the quote) | +0.3 to +0.8k | inferred: milk price effect -1.7k against +1.55k of units; the valuation uses the outlook price, not the marginal one | hours | yes (overlay) | yes |
| 2 | Crop mix by shop draw (port the crop-swap layer + market model) | +0.5 to +1.3k | inferred: the crop unit effects vs native sum to -1.3k (tomato, wheat, carrot, egg); the V45 version measured +0.5k paired | 1-2 days | partly: wheat<->carrot swaps ride her visits; strawberry<->tomato need her fertilize calendar checked tile by tile | probably |
| 3 | Animal counts sized to demand, in BOTH directions (fewer sheep / cows where the shops do not buy) | +0.5 to +1.5k | inferred from the price effect; the upward half is MEASURED: +139 n.s. (80 worlds; +11.1k, +7.6k, -7.6k) | 1-2 days for the downward half (skip her BUY_ANIMAL + service visits) | yes for skipping purchases; extra animals need the SE quadrant (built) | maybe |
| 4 | Melon day re-plan (one step ahead on every lot) | ~+2k us, ~-2k rival | modelled on the engine curve and the traced lots (identical on both sides) | large: re-routing day 10 | NO - executor | no |
| 5 | Hour-1 farmer sale (farmer milks / shears the animal next to the shed at hour 0, sells at hour 1) | +0.1 to +0.3k | modelled: hour 1 is +10-15% on wool and milk, one or two animals a day | 1 day (farmer override + route repair) | executor-lite | unlikely to pay for itself |
| 6 | V48 / V50 sale-timing layers | +0.0 to +0.2k | measured on other bases: +137 (V44/V45); our own sell-early +22..+37 | 0.5-1 day each | yes | yes, but small |
| - | Tape selection | exhausted | measured: no day-12 feature beats the ranking; future-demand term -2.4k to -4.3k | - | - | - |
| - | Sale timing: hold, tick-align, post-reveal hold, sell-all at her sale points | 0 / -658 / +25, -405 / -194 | measured | - | - | - |
| - | Fertilizer guard | 0 (never fires) | measured | - | - | - |
| - | Feed economy / spending | nothing to take | measured: she feeds what her peers feed; the purchase gap is round-trip wheat | - | - | - |
| - | Late sheep expansion, wheat-field pastures | negative | measured: -2k to -13k a world | - | - | - |

## Overlaps
- 1, 2 and 3 are the same money seen three ways (production matched to this world's demand); together they are bounded
  by the price effect plus the crop unit effects, about 3k, not 3k each. 1 is the cheap slice of 3.
- 2 and 4 do not collide: the melon field is cleared on day 10-11 and her strawberries / tomatoes go in afterwards.
  2 and 3 share labour only through our own overlay hands (each is the 12th-14th hire, 144-377 a day).
- 4 and 5 both need command rewriting of her units, i.e. the same executor machinery; 5 is a small first piece of 4.
