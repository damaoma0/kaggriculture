# Crop cohort diagnostic snapshot

**COMPLETE_DIAGNOSTIC** — 120/120 expected games are valid; 30/30 candidate/opponent/seed clusters have both seats.

Headline means below use only complete two-seat seed clusters. `Actual W/T/L` is the candidate's margin against the opponent; `Delta W/T/L` is candidate-minus-baseline margin. Those are deliberately different outcomes.

| Variant | Opponent | Pairs | Clusters | Δ cash | Δ margin | Actual W/T/L | Delta W/T/L | Δ HIRE | Δ LAND | Telemetry (schema-specific means) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| v45_native_carrot_value | farmingv5 | 12/12 | 6/6 | 35.8 | 116.5 | 6/0/0 | 3/3/0 | 9.2 | 0.0 | native_crop_swap_v1: carrot sale units requested=15.0; changed crop commands=2.7; confirmed harvest units=3.0; contract errors=0.0; expired unharvested yield=0.0; overnight harvests=0.0; overnight harvest units=0.0; confirmed planting cycles=1.3; seed units requested=2.8 |
| v45_native_carrot_value | pasture2700 | 12/12 | 6/6 | -109.7 | -58.2 | 6/0/0 | 0/3/3 | -38.8 | 0.0 | native_crop_swap_v1: carrot sale units requested=15.3; changed crop commands=2.7; confirmed harvest units=2.8; contract errors=0.0; expired unharvested yield=0.0; overnight harvests=0.0; overnight harvest units=0.0; confirmed planting cycles=1.3; seed units requested=2.8 |
| v45_native_carrot_value | twocoins | 12/12 | 6/6 | -93.8 | -19.0 | 6/0/0 | 1/3/2 | -38.8 | 0.0 | native_crop_swap_v1: carrot sale units requested=15.3; changed crop commands=2.7; confirmed harvest units=2.8; contract errors=0.0; expired unharvested yield=0.0; overnight harvests=0.0; overnight harvest units=0.0; confirmed planting cycles=1.3; seed units requested=2.8 |
| v45_native_carrot_value | v44 | 12/12 | 6/6 | 48.5 | 130.8 | 6/0/0 | 3/3/0 | -14.8 | 0.0 | native_crop_swap_v1: carrot sale units requested=13.8; changed crop commands=2.7; confirmed harvest units=2.8; contract errors=0.0; expired unharvested yield=0.0; overnight harvests=0.0; overnight harvest units=0.0; confirmed planting cycles=1.3; seed units requested=2.8 |
| v45_native_carrot_value | v45 | 12/12 | 6/6 | 48.5 | 130.8 | 6/0/0 | 3/3/0 | -14.8 | 0.0 | native_crop_swap_v1: carrot sale units requested=13.8; changed crop commands=2.7; confirmed harvest units=2.8; contract errors=0.0; expired unharvested yield=0.0; overnight harvests=0.0; overnight harvest units=0.0; confirmed planting cycles=1.3; seed units requested=2.8 |

## Activity and integrity

A zero-action game has no cohort command, seed, or sale request. Identity additionally requires equal final cash, full ledgers, and realized shops.

| Variant | Opponent | Active | Zero action | Zero identity | Zero nonidentity | Same shops | Telemetry errors | Worst game Δ margin |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| v45_native_carrot_value | farmingv5 | 6 | 6 | 6 | 0 | 12/12 | 0 in 0 games | 0.0 |
| v45_native_carrot_value | pasture2700 | 6 | 6 | 6 | 0 | 12/12 | 0 in 0 games | -160.0 |
| v45_native_carrot_value | twocoins | 6 | 6 | 6 | 0 | 12/12 | 0 in 0 games | -137.0 |
| v45_native_carrot_value | v44 | 6 | 6 | 6 | 0 | 12/12 | 0 in 0 games | 0.0 |
| v45_native_carrot_value | v45 | 6 | 6 | 6 | 0 | 12/12 | 0 in 0 games | 0.0 |

## Opponent-pooled seed means

Only seeds with every requested opponent and both seats are included.

| Variant | Seed | Δ cash | Δ margin | Active games | Zero-action games |
|---|---:|---:|---:|---:|---:|
| v45_native_carrot_value | 159000 | 18.2 | 313.4 | 10 | 0 |
| v45_native_carrot_value | 159001 | 0.0 | 0.0 | 0 | 10 |
| v45_native_carrot_value | 159002 | 0.0 | 0.0 | 0 | 10 |
| v45_native_carrot_value | 159003 | 0.0 | 0.0 | 0 | 10 |
| v45_native_carrot_value | 159004 | 13.8 | 17.0 | 10 | 0 |
| v45_native_carrot_value | 159005 | -116.8 | 30.8 | 10 | 0 |

## Successful output sales

Mean units and revenue per complete opponent-seed cluster. Rows include products whose units or revenue changed, plus the crop named by each variant.

| Variant | Crop | Baseline units | Cohort units | Δ units | Baseline revenue | Cohort revenue | Δ revenue |
|---|---:|---:|---:|---:|---:|---:|---:|
| v45_native_carrot_value | CARROT | 99.0 | 101.3 | 2.3 | 7,146.2 | 7,275.1 | 128.9 |
| v45_native_carrot_value | EGG | 85.4 | 85.6 | 0.2 | 4,449.4 | 4,458.9 | 9.5 |
| v45_native_carrot_value | FERTILIZER | 356.0 | 356.8 | 0.8 | 15,076.7 | 15,078.8 | 2.2 |
| v45_native_carrot_value | MILK | 191.1 | 191.1 | 0.0 | 13,342.4 | 13,361.6 | 19.2 |
| v45_native_carrot_value | STRAWBERRY | 248.0 | 247.5 | -0.5 | 16,648.1 | 16,660.0 | 11.8 |
| v45_native_carrot_value | WHEAT | 380.0 | 374.4 | -5.6 | 14,508.9 | 14,362.2 | -146.7 |
| v45_native_carrot_value | WOOL | 158.7 | 158.7 | 0.0 | 22,703.9 | 22,704.8 | 0.8 |

> `missing_plants` is not a clean death counter: it can include natural expiry when a managed crop becomes WEED, as well as missed-care death.

> Native-swap `commitments` means confirmed planting cycles, not unique plots. `harvest_units` and `expired_unharvested_yield` retain their native-swap definitions and are not merged with the borrowed-route counters.
