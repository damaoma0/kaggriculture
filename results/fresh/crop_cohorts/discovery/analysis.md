# Crop cohort diagnostic snapshot

**COMPLETE_DIAGNOSTIC** — 80/80 expected games are valid; 32/32 candidate/opponent/seed clusters have both seats.

Headline means below use only complete two-seat seed clusters. `Actual W/T/L` is the candidate's margin against the opponent; `Delta W/T/L` is candidate-minus-baseline margin. Those are deliberately different outcomes.

| Variant | Opponent | Pairs | Clusters | Δ cash | Δ margin | Actual W/T/L | Delta W/T/L | Δ HIRE | Δ LAND | Commit | Harvest | Plant fail | Missing |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| carrot_batch | twocoins | 8/8 | 4/4 | -604.2 | -672.0 | 4/0/0 | 0/0/4 | 0.0 | 0.0 | 1.2 | 3.8 | 0.0 | 0.8 |
| carrot_batch | v45 | 8/8 | 4/4 | -512.2 | -781.8 | 1/0/3 | 0/0/4 | -22.2 | 0.0 | 1.2 | 3.8 | 0.0 | 0.8 |
| carrot_stagger | twocoins | 8/8 | 4/4 | -574.0 | -625.0 | 4/0/0 | 0/0/4 | 0.0 | 0.0 | 0.8 | 2.8 | 0.0 | 0.2 |
| carrot_stagger | v45 | 8/8 | 4/4 | -417.0 | -611.2 | 2/0/2 | 0/0/4 | -22.2 | 0.0 | 0.8 | 2.8 | 0.0 | 0.2 |
| tomato_batch | twocoins | 8/8 | 4/4 | -490.5 | -605.2 | 4/0/0 | 0/0/4 | -36.0 | 0.0 | 1.8 | 2.0 | 0.0 | 1.0 |
| tomato_batch | v45 | 8/8 | 4/4 | -496.8 | -610.2 | 0/0/4 | 0/0/4 | 0.0 | 0.0 | 1.8 | 2.0 | 0.0 | 1.0 |
| tomato_stagger | twocoins | 8/8 | 4/4 | -668.5 | -770.2 | 4/0/0 | 0/0/4 | 0.0 | 0.0 | 1.8 | 2.2 | 0.0 | 1.0 |
| tomato_stagger | v45 | 8/8 | 4/4 | -725.2 | -828.0 | 0/0/4 | 0/0/4 | -22.2 | 0.0 | 1.8 | 2.2 | 0.0 | 1.0 |

## Successful output sales

Mean units and revenue per complete opponent-seed cluster. Rows include products whose units or revenue changed, plus the crop named by each variant.

| Variant | Crop | Baseline units | Cohort units | Δ units | Baseline revenue | Cohort revenue | Δ revenue |
|---|---:|---:|---:|---:|---:|---:|---:|
| carrot_batch | CARROT | 87.2 | 90.6 | 3.4 | 4,106.9 | 4,250.6 | 143.8 |
| carrot_batch | FERTILIZER | 358.9 | 358.0 | -0.9 | 14,570.6 | 14,565.2 | -5.4 |
| carrot_batch | MILK | 176.9 | 176.1 | -0.8 | 19,646.0 | 19,534.4 | -111.6 |
| carrot_batch | STRAWBERRY | 245.0 | 242.8 | -2.2 | 17,173.9 | 17,157.1 | -16.8 |
| carrot_batch | WHEAT | 1,165.9 | 1,158.6 | -7.2 | 50,347.4 | 50,133.8 | -213.6 |
| carrot_batch | WOOL | 236.1 | 234.4 | -1.8 | 47,184.6 | 46,905.1 | -279.5 |
| carrot_stagger | CARROT | 87.2 | 89.6 | 2.4 | 4,106.9 | 4,197.8 | 90.9 |
| carrot_stagger | FERTILIZER | 358.9 | 358.0 | -0.9 | 14,570.6 | 14,565.6 | -5.0 |
| carrot_stagger | MILK | 176.9 | 176.1 | -0.8 | 19,646.0 | 19,532.5 | -113.5 |
| carrot_stagger | STRAWBERRY | 245.0 | 243.0 | -2.0 | 17,173.9 | 17,162.4 | -11.5 |
| carrot_stagger | WHEAT | 1,165.9 | 1,161.6 | -4.2 | 50,347.4 | 50,214.6 | -132.8 |
| carrot_stagger | WOOL | 236.1 | 234.4 | -1.8 | 47,184.6 | 46,917.2 | -267.4 |
| tomato_batch | CARROT | 87.2 | 82.5 | -4.8 | 4,106.9 | 3,884.2 | -222.6 |
| tomato_batch | EGG | 59.1 | 59.6 | 0.5 | 3,282.1 | 3,309.8 | 27.6 |
| tomato_batch | FERTILIZER | 358.9 | 359.5 | 0.6 | 14,570.6 | 14,567.7 | -2.9 |
| tomato_batch | MILK | 176.9 | 177.0 | 0.1 | 19,646.0 | 19,631.1 | -14.9 |
| tomato_batch | STRAWBERRY | 245.0 | 241.2 | -3.8 | 17,173.9 | 17,111.6 | -62.2 |
| tomato_batch | TOMATO | 0.0 | 2.5 | 2.5 | 0.0 | 242.0 | 242.0 |
| tomato_batch | WHEAT | 1,165.9 | 1,156.4 | -9.5 | 50,347.4 | 50,032.8 | -314.6 |
| tomato_batch | WOOL | 236.1 | 236.1 | 0.0 | 47,184.6 | 47,184.4 | -0.2 |
| tomato_stagger | CARROT | 87.2 | 83.5 | -3.8 | 4,106.9 | 3,911.5 | -195.4 |
| tomato_stagger | EGG | 59.1 | 59.0 | -0.1 | 3,282.1 | 3,275.8 | -6.4 |
| tomato_stagger | FERTILIZER | 358.9 | 358.2 | -0.6 | 14,570.6 | 14,564.4 | -6.1 |
| tomato_stagger | MILK | 176.9 | 175.5 | -1.4 | 19,646.0 | 19,475.9 | -170.1 |
| tomato_stagger | STRAWBERRY | 245.0 | 240.8 | -4.2 | 17,173.9 | 17,101.9 | -72.0 |
| tomato_stagger | TOMATO | 0.0 | 2.5 | 2.5 | 0.0 | 242.4 | 242.4 |
| tomato_stagger | WHEAT | 1,165.9 | 1,155.9 | -10.0 | 50,347.4 | 50,014.0 | -333.4 |
| tomato_stagger | WOOL | 236.1 | 236.1 | 0.0 | 47,184.6 | 47,183.9 | -0.8 |

> `missing_plants` is not a clean death counter: it can include natural expiry when a managed crop becomes WEED, as well as missed-care death.
