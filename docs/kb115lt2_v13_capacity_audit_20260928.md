# V13: actual stock loss on five modeled capacity-risk days

All five days have **zero actual discarded units across every shed-stored item**, proved from saved private stocks, physical collection/consumption and sale ledgers. No engine or agent call was needed. A low dawn shed total alone would not establish this result.

The identity is opening shed plus carried stock, plus successful collection and actual purchases, minus sales, successful consumption and closing stock. Successful FEED/FERTILIZE consumption is the physical operation count minus its no-effect count. Each of the nine products closes separately, so aggregation cannot conceal one product's loss with another's gain.

| Case / day | Modeled load | Opening stock | Collected | Bought | Sold | Consumed | Closing stock | Discard |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 02 / D18 | 103 | 76 | 120 | 0 | 80 | 25 | 91 | 0 |
| 03 / D19 | 101 | 89 | 116 | 0 | 87 | 28 | 90 | 0 |
| 05 / D14 | 101 | 81 | 115 | 0 | 78 | 23 | 95 | 0 |
| 06 / D21 | 108 | 85 | 118 | 3 | 89 | 26 | 91 | 0 |
| 06 / D27 | 112 | 95 | 132 | 0 | 111 | 18 | 98 | 0 |

Four days have zero product-purchase spending. On live06 D21 the wheat identity excluding purchases is −3, while the first ten market orders request at most three wheat in total (H0 one, H4 two). Thus actual wheat buys are at most three, and nonnegative discard requires at least three: exactly three were bought and zero were discarded. This is a conservation proof, not an assumption that requests filled. Every other product that day has no purchases and a zero residual.

No animal stock or animal purchases occur on these five days. Seeds are held separately in the official engine's `private.seeds`; they do not consume shed capacity. The complete shed item set is therefore covered. Zero total discard also excludes daytime DROP losses, not just midnight overflow. It does not certify a precise intraday maximum shed occupancy.

All five selected animal harvests execute at the logged tile and unit with the exact held quantity: 02 D18 sheep48, four wool, unit7 H23; 03 D19 sheep65, four wool, unit6 H12; 05 D14 goose64, two eggs, unit7 H7; 06 D21 sheep48, four wool, unit7 H15; 06 D27 cow46, three milk, unit5 H5. Each displaced optional command is absent from that day's actual commands. All five target lots enter the automatic midnight delivery without loss.

The broader audit also preserves a diagnostic limitation: on live03 D14/D25, live05 D18 and live06 D18, the successful target harvest is performed by a different unit from the logged planned exchange. The target species, held quantity and daily collection balances match, but worker identity is explicitly marked false. These four cases are outside the five capacity-risk days; the audit does not silently equate planner logs with execution.

Reproduce using `scripts/audit_kb115lt2_v13_completed_20260928.py --cases live-02,live-03,live-05,live-06 --output results/fresh/semantic_kb115lt2_recovery/v13_modeled_capacity_cases_audit.json`. The JSON embeds exact hashes of all eight result/action pairs, the movement reconstruction helper, official engine source and audit script, plus per-product arithmetic. Source games and frozen executors remain unchanged. These are capacity/execution findings, not isolated full-season profit attribution; the natural shop sequences differ between arms.
