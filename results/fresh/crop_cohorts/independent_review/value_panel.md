# Crop cohort diagnostic snapshot

**COMPLETE_DIAGNOSTIC** — 64/64 expected games are valid; 16/16 candidate/opponent/seed clusters have both seats.

Headline means below use only complete two-seat seed clusters. `Actual W/T/L` is the candidate's margin against the opponent; `Delta W/T/L` is candidate-minus-baseline margin. Those are deliberately different outcomes.

| Variant | Opponent | Pairs | Clusters | Δ cash | Δ margin | Actual W/T/L | Delta W/T/L | Δ HIRE | Δ LAND | Telemetry (schema-specific means) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| v45_native_carrot_value | twocoins | 16/16 | 8/8 | -36.5 | 83.5 | 8/0/0 | 1/7/0 | 0.0 | 0.0 | native_crop_swap_v1: carrot sale units requested=4.2; changed crop commands=1.5; confirmed harvest units=1.6; contract errors=0.0; expired unharvested yield=0.0; overnight harvests=0.0; overnight harvest units=0.0; confirmed planting cycles=0.8; seed units requested=1.1 |
| v45_native_carrot_value | v45 | 16/16 | 8/8 | 27.2 | 172.0 | 7/0/1 | 1/7/0 | 0.0 | 0.0 | native_crop_swap_v1: carrot sale units requested=3.9; changed crop commands=1.5; confirmed harvest units=1.6; contract errors=0.0; expired unharvested yield=0.0; overnight harvests=0.0; overnight harvest units=0.0; confirmed planting cycles=0.8; seed units requested=1.1 |

## Activity and integrity

A zero-action game has no cohort command, seed, or sale request. Identity additionally requires equal final cash, full ledgers, and realized shops.

| Variant | Opponent | Active | Zero action | Zero identity | Zero nonidentity | Same shops | Telemetry errors | Worst game Δ margin |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| v45_native_carrot_value | twocoins | 2 | 14 | 14 | 0 | 16/16 | 0 in 0 games | 0.0 |
| v45_native_carrot_value | v45 | 2 | 14 | 14 | 0 | 16/16 | 0 in 0 games | 0.0 |

## Opponent-pooled seed means

Only seeds with every requested opponent and both seats are included.

| Variant | Seed | Δ cash | Δ margin | Active games | Zero-action games |
|---|---:|---:|---:|---:|---:|
| v45_native_carrot_value | 158000 | 0.0 | 0.0 | 0 | 4 |
| v45_native_carrot_value | 158003 | -37.0 | 1,022.0 | 4 | 0 |
| v45_native_carrot_value | 158005 | 0.0 | 0.0 | 0 | 4 |
| v45_native_carrot_value | 158006 | 0.0 | 0.0 | 0 | 4 |
| v45_native_carrot_value | 158008 | 0.0 | 0.0 | 0 | 4 |
| v45_native_carrot_value | 158011 | 0.0 | 0.0 | 0 | 4 |
| v45_native_carrot_value | 158015 | 0.0 | 0.0 | 0 | 4 |
| v45_native_carrot_value | 158024 | 0.0 | 0.0 | 0 | 4 |

## Successful output sales

Mean units and revenue per complete opponent-seed cluster. Rows include products whose units or revenue changed, plus the crop named by each variant.

| Variant | Crop | Baseline units | Cohort units | Δ units | Baseline revenue | Cohort revenue | Δ revenue |
|---|---:|---:|---:|---:|---:|---:|---:|
| v45_native_carrot_value | CARROT | 96.1 | 97.8 | 1.6 | 7,654.1 | 7,761.9 | 107.8 |
| v45_native_carrot_value | EGG | 77.8 | 78.1 | 0.3 | 3,906.9 | 3,919.8 | 12.9 |
| v45_native_carrot_value | FERTILIZER | 353.4 | 353.6 | 0.2 | 14,713.7 | 14,715.2 | 1.5 |
| v45_native_carrot_value | MILK | 196.8 | 196.8 | 0.0 | 22,793.2 | 22,792.1 | -1.1 |
| v45_native_carrot_value | STRAWBERRY | 248.6 | 248.8 | 0.1 | 26,986.6 | 26,994.7 | 8.1 |
| v45_native_carrot_value | WHEAT | 824.4 | 820.4 | -3.9 | 34,709.3 | 34,597.2 | -112.1 |

> `missing_plants` is not a clean death counter: it can include natural expiry when a managed crop becomes WEED, as well as missed-care death.

> Native-swap `commitments` means confirmed planting cycles, not unique plots. `harvest_units` and `expired_unharvested_yield` retain their native-swap definitions and are not merged with the borrowed-route counters.
