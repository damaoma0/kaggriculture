# V13 live05: two mandatory cow feeds lose the stock allocation

The exact development replay proves that both cows' FEED jobs survive planning and polishing. They fail during execution because their assigned worker gets only one of its three requested wheat. It uses that wheat on the goose, then reaches both cows with empty inventory. This is a stock delivery and budget consistency failure, not an intentional retirement or an omitted keepalive job.

The capture uses frozen V13 and the predeclared development `live-05`, seed779294796, own seat1. Both original action streams execute under the original shops; the candidate runs only in shadow. All192 shadow actions match exactly through D7H23. Both farms' dawn0–8 states, own private state, market/town and both D8 cumulative cash/physical/revenue/sales/spend ledgers match. No command, policy or executor was changed. Maximum shadow call0.7511s, total3.0866s, all60s overage bank remains; capture copying accounts for0.0266s. This short replay is a diagnostic, not a new performance result.

## Assignment and execution

Cows5/15 were placed on D6 and start D7 with `consecutive_unfed=1`. Retirement maps are empty and all three semantic animal lookahead maps preserve both cows. The D7 core input marks FEED mandatory for cows5/15 and goose36. The final post-polish routes preserve these jobs:

| Unit | Final route responsibility | Planned feed times |
|---|---|---|
| 9 | Pickup3 wheat; place geese; feed goose36; plant/water three wheat; feed cows15/5 | H7, H21, H23 |
| 3 | Collect fertilizer and CARE on goose36/cows15/5; optional crop water | No FEED assigned |

The earlier observation that unit3 visited these animals carrying zero wheat did not identify their FEED owner. The full-route capture corrects that inference.

| D7 hour | Unit9 actual result |
|---|---|
| H2 | Requests pickup3; shared stock after earlier units permits1. Logs `pick_short WHEAT 1/3`; cursor advances. |
| H3 | Narrow retry sees zero unreserved shed wheat and rejects with `wheat_retry_reserved_stock 0`. Picks one of two requested geese. |
| H7 | Places goose46. |
| H9 | Feeds existing goose36 with its only wheat. |
| H12 | Skips second goose placement at26 because it carries none. |
| H13–20 | Plants and waters wheat at27/17/16. |
| H22 | At cow15, `_tier_check(FEED)` returns `skip` with empty inventory. Moves toward5. |
| H23 | At cow5, the same check skips FEED; unit passes. |

Both cows disappear by D8 dawn. Goose36 survives. This directly ties each failed cow feed to its assigned worker and local stock. There are no executor exceptions, retirement exclusions, missing FEED records or polish deletions in this chain. Units2/6 have empty final routes, but their existence alone does not supply wheat or prove a feasible profitable reassignment.

There is also a spawn/timing mismatch: unit9 is planned to start H1 at tile45 but actually starts H2 at tile55. H0's BUY and SELL plus eight hires fill the ten-order limit, deferring the ninth hire to H1. Its initial delay and the missing second goose both alter the route timetable. Skipping an unfunded build could save an action, but whether that and a new stock allocation preserve all other jobs requires a separate controlled check; this capture does not establish it.

## Wheat and cash do not obey one consistent budget

At D7 dawn the tier planner has eleven feeds, three shed wheat, zero actually carried wheat and `wheat_buy=8`. Seven feeds are mandatory and four optional. Cash is54; the shed contains three fertilizer worth264 in the realized sale.

| Hour | Observed shed wheat | Actually carried before action | `_market` carried argument | Issued wheat pickups | Market orders relevant to funding |
|---|---:|---:|---:|---:|---|
| H0 | 3 | 0 | 2 | 0 | BUY1 wheat, SELL3 fertilizer, HIRE8 |
| H1 | 4 | 0 | 4 | 4 | HIRE1, BUY5 wheat, BUY2 wheat seeds |
| H2 | 5 | 4 | 9 | 5 | SELL1 wheat; no stock remains to sell |
| H3 | 0 | 9 | 9 | 0 | None |

The H0 tier buy is capped using starting cash (`54 // (31+2) = 1`) and latches `wheat_bought=True` despite satisfying only one of the requested eight. The fertilizer sale follows it; later observed cash therefore cannot complete that tier request through the same branch.

The fallback H1 formula is also inconsistent with command timing: demand13 minus carried4 minus observed shed4 produces a request for5. Those four carried units are the farmer's just-issued pickup from the same four shed units. Physical unit commands execute before market orders, so these four units are counted twice. At H2 all five observed shed wheat are again being picked while the market counts carried9 plus shed5. Moreover, H0's carried argument already contains two hypothetical greedy pickups even though the final tier command is PASS and every actual inventory is empty. The original dispatcher mutates `carried`; `_tier_override` replaces its commands without rebuilding that argument before `_market`.

Relevant frozen executor source sections are `_market` around3412/3624/3749, `carried` initialization and mutation around1988/2419/2497, tier override then market call around2588–2601, and dawn `wbuy` around10375. All source hashes are bound in the capture manifest. The accounting defect is general, but this diagnostic alone does not establish its prevalence or the profit of a repair.

The complete D7 cash identity is **54 +264 fertilizer revenue −191 wheat purchases −88 hires −20 seeds =19**. Six purchased wheat plus three starting wheat yield nine feeds. All four optional feeds succeed, while only five of seven mandatory feeds succeed. Nine available wheat could cover all seven mandatory jobs with a different allocation. Buying enough for all eleven while retaining the observed wages and seed purchases would require more money; fixing the double count does not by itself make every dawn commitment affordable.

## Repair options supported by this evidence

1. Recompute market stock from observed inventories and the final issued commands, with same-turn shed pickups debited once. Do not credit commands discarded by tier override.
2. Track remaining route material obligations explicitly, including partial pickup residuals, and reserve scarce wheat for retained mandatory FEED before optional use. Respect cohort identity and retirement commitments.
3. Keep unsatisfied purchase obligations live after a cash-capped buy. Reconcile them against observed receipts and a feasible cash/order schedule. Sales funding and hires must preserve spawn/route timing; simply moving orders or adding workers is not an established fix.

These are separate implementation choices, not tested counterfactual gains. No intervention or additional game was performed here. Fresh V9-lite smoke cases were neither used for this replay nor fitted.

## Artifacts

Recovery worktree bundle: `results/fresh/semantic_kb115lt2_recovery/v13_newborn_shadow_live05_v1/`. Manifest SHA `7d9c232711fdc119571667fae2ae7c8fe154c55a9eeb3adecd33501eea789584`; verified capture SHA `a090fab7a2208d3402f53914a37086754d617d22a988f5c51332b0c24d15abcb`. Frozen V13 executor SHA `656fc41fdb3c772e9bd8a13ffedea79c7e8c412acdb4c64218344fa63f082da1`.

`scripts/audit_v13_newborn_shadow_20260928.py` asserts feed ownership, seven mandatory/four optional assignments, actual pickup and skip events, both-cohort exits, retired-map emptiness and cash reconciliation. It reads saved JSON only. Output `results/fresh/semantic_kb115lt2_recovery/diagnostics/v13_newborn_feed/audit.json`, SHA `4b92ab65744586d01a8ee4b2d6118fce0f45c00adb768a4182ed38ce73a79c32`, includes exact route/item/cursor timelines and source hashes. Original and frozen files remain unchanged.
