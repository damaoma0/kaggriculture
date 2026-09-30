# Crop cohort diagnostic snapshot

**COMPLETE_DIAGNOSTIC** — 96/96 expected games are valid; 32/32 candidate/opponent/seed clusters have both seats.

Headline means below use only complete two-seat seed clusters. `Actual W/T/L` is the candidate's margin against the opponent; `Delta W/T/L` is candidate-minus-baseline margin. Those are deliberately different outcomes.

| Variant | Opponent | Pairs | Clusters | Δ cash | Δ margin | Actual W/T/L | Delta W/T/L | Δ HIRE | Δ LAND | Telemetry (schema-specific means) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| v45_native_carrot_2 | twocoins | 16/16 | 8/8 | -382.6 | -318.7 | 8/0/0 | 2/0/6 | 0.0 | 0.0 | native_crop_swap_v1: carrot sale units requested=33.1; changed crop commands=13.0; confirmed harvest units=13.8; contract errors=0.0; expired unharvested yield=0.0; overnight harvests=1.0; overnight harvest units=2.0; confirmed planting cycles=6.5; seed units requested=8.5 |
| v45_native_carrot_2 | v45 | 16/16 | 8/8 | -293.8 | -182.2 | 2/0/6 | 2/0/6 | 0.0 | 0.0 | native_crop_swap_v1: carrot sale units requested=30.6; changed crop commands=13.0; confirmed harvest units=13.8; contract errors=0.0; expired unharvested yield=0.0; overnight harvests=1.0; overnight harvest units=2.0; confirmed planting cycles=6.5; seed units requested=8.5 |
| v45_native_carrot_4 | twocoins | 16/16 | 8/8 | -1,034.3 | -812.3 | 8/0/0 | 1/0/7 | -108.0 | 0.0 | native_crop_swap_v1: carrot sale units requested=43.4; changed crop commands=24.2; confirmed harvest units=25.0; contract errors=0.0; expired unharvested yield=0.0; overnight harvests=1.0; overnight harvest units=2.0; confirmed planting cycles=12.1; seed units requested=16.1 |
| v45_native_carrot_4 | v45 | 16/16 | 8/8 | -545.5 | -564.8 | 1/0/7 | 1/0/7 | 18.0 | 0.0 | native_crop_swap_v1: carrot sale units requested=41.9; changed crop commands=24.2; confirmed harvest units=25.0; contract errors=0.0; expired unharvested yield=0.0; overnight harvests=1.0; overnight harvest units=2.0; confirmed planting cycles=12.1; seed units requested=16.1 |

## Successful output sales

Mean units and revenue per complete opponent-seed cluster. Rows include products whose units or revenue changed, plus the crop named by each variant.

| Variant | Crop | Baseline units | Cohort units | Δ units | Baseline revenue | Cohort revenue | Δ revenue |
|---|---:|---:|---:|---:|---:|---:|---:|
| v45_native_carrot_2 | CARROT | 96.1 | 109.6 | 13.4 | 7,654.1 | 8,159.0 | 504.8 |
| v45_native_carrot_2 | EGG | 77.8 | 79.9 | 2.1 | 3,906.9 | 4,013.4 | 106.5 |
| v45_native_carrot_2 | FERTILIZER | 353.4 | 354.0 | 0.6 | 14,713.7 | 14,713.0 | -0.7 |
| v45_native_carrot_2 | MILK | 196.8 | 196.7 | -0.1 | 22,793.2 | 22,825.5 | 32.2 |
| v45_native_carrot_2 | STRAWBERRY | 248.6 | 249.3 | 0.7 | 26,986.6 | 27,040.6 | 54.0 |
| v45_native_carrot_2 | WHEAT | 824.4 | 799.7 | -24.7 | 34,709.3 | 34,042.3 | -667.0 |
| v45_native_carrot_2 | WOOL | 173.5 | 173.6 | 0.1 | 23,193.9 | 23,192.6 | -1.3 |
| v45_native_carrot_4 | CARROT | 96.1 | 119.9 | 23.8 | 7,654.1 | 8,522.7 | 868.6 |
| v45_native_carrot_4 | EGG | 77.8 | 80.2 | 2.4 | 3,906.9 | 4,029.2 | 122.2 |
| v45_native_carrot_4 | FERTILIZER | 353.4 | 354.4 | 1.1 | 14,713.7 | 14,716.8 | 3.1 |
| v45_native_carrot_4 | MILK | 196.8 | 196.5 | -0.2 | 22,793.2 | 22,857.9 | 64.7 |
| v45_native_carrot_4 | STRAWBERRY | 248.6 | 249.7 | 1.1 | 26,986.6 | 27,070.6 | 84.0 |
| v45_native_carrot_4 | WHEAT | 824.4 | 778.0 | -46.4 | 34,709.3 | 33,397.3 | -1,312.0 |
| v45_native_carrot_4 | WOOL | 173.5 | 174.4 | 0.9 | 23,193.9 | 23,214.4 | 20.6 |

> `missing_plants` is not a clean death counter: it can include natural expiry when a managed crop becomes WEED, as well as missed-care death.

> Native-swap `commitments` means confirmed planting cycles, not unique plots. `harvest_units` and `expired_unharvested_yield` retain their native-swap definitions and are not merged with the borrowed-route counters.
