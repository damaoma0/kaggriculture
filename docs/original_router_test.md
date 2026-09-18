# Direct test against the original public router

Selected agent: `agents/market_impact_selected.py`. Opponent: **`agents/public/tschinkel_router_v31.py`**, the original public router, distinct from the six-day router. No agent code was changed or tuned for this test.

## Results

| Panel | Games | Wins / ties / losses | Our average cash | Router average cash | Average margin | Worst margin |
|---|---:|---|---:|---:|---:|---:|
| natural | 32 | 32 / 0 / 0 | 99,137.7 | 79,425.8 | +19,711.9 | +9,503 |
| shops | 16 | 16 / 0 / 0 | 107,051.1 | 85,873.0 | +21,178.1 | +7,612 |
| all | 48 | 48 / 0 / 0 | 101,775.5 | 81,574.9 | +20,200.6 | +7,612 |

## Coverage

The natural panel uses 16 fresh seeds (127000–127015), each played in both seats. The additional controlled panel uses eight fresh seeds (128000–128007), one for each possible first shop, also in both seats. Future controlled shop draws remain hidden from both agents until revealed. The two panels are reported separately; the controlled panel is a coverage check, not a sample of natural shop frequencies.

| First shop in controlled panel | Mean margin across both seats |
|---|---:|
| BAKERY | +9,406.0 |
| BRUNCH_SPOT | +19,325.0 |
| FARMERS_MARKET | +8,114.0 |
| ICE_CREAM_SHOP | +12,112.0 |
| PET_CAFE | +39,495.0 |
| PIZZA_SHOP | +23,447.0 |
| SMOOTHIE_SHOP | +29,036.0 |
| YARN_STORE | +28,490.0 |

## Checks and limits

- All 48 games completed the 30-day season (720 states) with valid statuses. Both players' final cash reconciled exactly against the transaction ledger. Each game ran in a fresh worker process.

- Source hashes and seeds were frozen before play. Seats are paired checks, not independent seeds. No Kaggle submission was made; these results concern the exact local router file above.

- The previously recorded six-day-router result remains 16–0 on confirmation plus 8–0 in discovery. Those were different seeds and a different opponent file.

Reproduce with `.venv/Scripts/python.exe scripts/test_original_router.py`. Full results, ledgers, shop sequences and source hashes: `results/fresh/original_router_test/`.
