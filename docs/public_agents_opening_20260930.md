# Latest public Kaggle agents vs the opening problem (2026-09-30)

User: "look into latest open source code on kaggle and see if any of them fixes the opening problem ... One smoke run to
day 11 would be enough. They must also buy 4 quadrants."

## What was pulled

`kaggle kernels list --competition kaggriculture --sort-by dateRun`; the ten most relevant recent notebooks pulled to
results/fresh/kaggle_public_20260930/ (source only). Agents were extracted WITHOUT running notebook cells
(`scripts/kaggle_public_extract_20260930.py`: embedded blobs read as literals with ast and decoded with each
notebook's own scheme) and scanned statically: no shell, network or file-writing calls; the `exec(` calls run source
text embedded in the same files (an engine-rules module and a last-seven-turns planner), the base64 decode is a JSON
route table. Note: "Kaggriculture (TOP 2) Master Engine V4" ends with a hidden `echo <base64> | base64 -d | bash` cell
that deletes LICENSE.txt / NOTICE.txt (strips the original author's attribution); it and "The 2965 Master Hybrid
Engine" ship byte-identical main.py files.

Seven distinct agents, all one lineage (the public router descended from Ahmed Berat Ozer's V56, our V56 benchmark:
shop-keyed route table "R108" + later layers): A Song of Ice and Fire (Fixed + Flexible), Demand-Preserving Turn Sale
Timing, God's Mode (Hacked Stores; adds a shop predictor / overlay), Harvest Ledger, Multi-Route Farming Agent,
TOP 2 Master V4 (= 2965 Master), Version 31 (bronze, going up). "Farmer John and the Wheat Seller" did not extract
(empty archive blob).

## Day-11 smoke (`scripts/public_opening_smoke_20260930.py AGENT_DIR EP`)

Each agent plays DSM's seat from step 0 in DSM-new world 115518441 (forced shops, recorded opponent with its logged
weeds and exact purchase credit), our seat passes after step 263.

| | quadrants at day-11 dawn | 2nd / 3rd / 4th quadrant | cash at day-11 dawn | day-11 board |
|---|---|---|---:|---|
| all seven public agents | **2** | day 6 / - / - | 16.5-16.8k | 20 strawberry, 12 wheat, 8 cows, 6 sheep, 2 geese (+2 coops) |
| DSM (its own game) | **4** | day 6 h4 / day 8 h7 / day 10 h10 | 4.3k | 30 strawberry, 28 wheat, 7 melon, 3 tomato, 7 cows, 3 sheep, 10 geese |

Six of the seven end day 10 on the identical board (the same route table drives days 0-10); composition distance to
DSM's day-11 board 31 tiles for all. None fixes the opening problem: the public lineage stays on two quadrants and
banks the melon money (+14.6k on day 10) instead of buying land.

## Other findings

- "God's Mode. Hacked Stores": the shop draws share the RNG stream with the farms' weed spawns; a reconstructed formula
  predicted all 3,136 shop events of 392 games, and one extra RNG call (e.g. a final DIG) changed the shop in 98 of
  128 paired games. Seed inference from natural play is too late for control before day ~15-24.
- destbreso, "Everyone is playing the same opening": one opening spread to about half of sampled seats within ~48 h;
  teams agree action for action to turn ~100 and then diverge; adopting it bought about a quarter of what iterating
  on anything bought.
