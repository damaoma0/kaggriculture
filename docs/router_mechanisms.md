# What makes the newer router stronger?

## Findings

**Most of the advantage over our submitted agent survives removing all four tested mechanisms.** Full V45 wins 16/16 with mean margin +11,282; combined-off also wins 16/16 with mean margin +11,569. The remaining production selection, input management, and execution layers need the next causal breakdown. This does not isolate the route portfolio itself.

- Tomato expansion adds +1,872 mean margin against ours and +1,709 against Two Coins. It activates on only two of eight shop sequences (four seat-paired games), so this is a conditional gain with limited trigger coverage.
- Advance-sale reservations add +3,405 margin against Two Coins but lose 753 against ours. Their usefulness depends on the rival and market trajectory.
- The V45 opening round trip loses 1,374 margin against ours and 1,326 against Two Coins relative to its predecessor opening. This does not rule out value against other opening order streams.
- The seven-turn terminal planner adds only about 4 cash and margin against either opponent on this panel. It activates in twelve games per opponent; the small gain is not simply lack of activation.
- Wheat accounts for +5,338 of V45's average cash advantage over ours, mostly higher sale revenue. This is the largest accounting lead and the clearest next target for mechanism tracing.

QQ Farming may have been a strong submission with an unrepresentative displayed rating. That is compatible with an unlucky pairing, but does not remove the reproducible gap against the newer public agents. No historical QQ rating was independently verified in this study.

## Method

192 full games: eight new seeds (135000–135007), both seats, two reactive opponents, and six V45 variants. Each paired comparison uses the same hidden shop sequence, sampled uniformly with replacement. Both cash ledgers reconcile in every game. Eight seeds are the independent sample; seats are paired coverage, not sixteen independent worlds.

The full agent is the downloaded V45. Interventions disable its conditional tomato investment, advance-sale reservations, seven-turn terminal planner, or V45 opening round trip separately; combined-off disables all four. Other production tapes, sale ordering, inventory safeguards, and repair layers remain active. Combined-off is not the old router.

Positive gain below means enabling the mechanism helped the full agent. It includes downstream changes and opponent reactions; the rows are not additive.

| Opponent | Disabled mechanism | Variant wins / 16 | Full margin gain | Full own-cash gain | Positive / negative pairs | Seed-average gain range |
|---|---|---:|---:|---:|---:|---:|
| selected | full | 16 | +0.0 | +0.0 | 0 / 0 | +0 to +0 |
| selected | no_tomatoes | 16 | +1,872.1 | +1,877.8 | 4 / 0 | +0 to +12,251 |
| selected | no_reservations | 16 | -752.7 | -796.4 | 2 / 14 | -2,629 to +54 |
| selected | no_terminal | 16 | +4.4 | +4.4 | 12 / 0 | +0 to +7 |
| selected | no_flip | 16 | -1,374.2 | -827.3 | 2 / 14 | -2,952 to +2,642 |
| selected | combined_off | 16 | -286.2 | +262.1 | 4 / 12 | -4,070 to +8,789 |
| twocoins | full | 16 | +0.0 | +0.0 | 0 / 0 | +0 to +0 |
| twocoins | no_tomatoes | 14 | +1,709.4 | +820.0 | 4 / 0 | +0 to +11,247 |
| twocoins | no_reservations | 12 | +3,404.9 | +1,341.6 | 12 / 4 | -652 to +13,525 |
| twocoins | no_terminal | 16 | +4.4 | +4.4 | 12 / 0 | +0 to +7 |
| twocoins | no_flip | 16 | -1,326.0 | -876.0 | 0 / 16 | -1,326 to -1,326 |
| twocoins | combined_off | 10 | +3,794.6 | +1,291.9 | 8 / 8 | -1,973 to +12,206 |

## Full-agent coverage

- Against selected: mean margin +11,282.4; tomato commitments in 4/16 games; terminal plans accepted in 12/16 games.
- Against twocoins: mean margin +7,098.3; tomato commitments in 4/16 games; terminal plans accepted in 12/16 games.

## Where our submitted control loses cash

Mean exact ledger difference, full V45 minus our submitted agent in their direct games. Product contribution is revenue less purchases of that product, its seeds, and its animals; labor and land are separate. These are accounting differences, not independent causal effects.

| Contribution | V45 advantage | Mean units sold: V45 / ours |
|---|---:|---:|
| WHEAT | +5,338.4 | 554.7 / 497.9 |
| TOMATO | +4,023.4 | 20.0 / 0.0 |
| CARROT | +1,075.2 | 92.0 / 65.6 |
| WOOL | +1,030.2 | 159.2 / 173.2 |
| MILK | +853.2 | 183.5 / 213.1 |
| EGG | +196.5 | 84.2 / 81.8 |
| STRAWBERRY | +162.1 | 248.1 / 254.0 |
| MELON | +0.0 | 72.0 / 72.0 |
| FERTILIZER | -76.6 | 341.6 / 326.1 |
| HIRE | -320.1 | — |
| BUY_LAND | -1,000.0 | — |

Sold units are gross market sales, including purchased-and-resold goods such as wheat; they are not necessarily farm production.

The wheat contribution comprises +4,751.0 sale revenue, +412.4 savings on purchased wheat, and +175.0 savings on wheat seeds. It cannot all be attributed to feeding or sale timing without further interventions.

## What the code teaches us

- **Production selection:** V45 contains 41 action tapes, with 64 ordered first-two-shop lookup entries. At turn 144 it chooses an expert based on whether either first shop is Yarn Store, then chooses that expert's route for the shop pair. At turn 648 it switches to its terminal route. These are full-game continuations, not six-day-only plans. The old parent has five tapes; Two Coins has thirteen. Tape count is a source fact, not an isolated measure of quality.
- **Investment:** the tomato expansion checks land, cash (at least 12,000), current tomato price (at least 70), and at least three revealed Pizza Shop/Farmers Market appearances. It reserves new worker indices and plants ten tomatoes on day index 18, leaving time for harvests before termination. Fertilizer has a separate marginal-benefit check. It commits to a production-and-delivery plan, not just cheap seeds.
- **Inventory and execution:** the chassis repairs weed-interrupted work. Additional layers project physical deposits before market actions, protect upcoming pickups, trim redundant replenishment, and reclaim warehouse overflow. Advance-sale reservations move eligible future sales forward and suppress the corresponding later orders so inventory is not sold twice.
- **Input economics:** feeding can be skipped when the estimated extra output is worth less than wheat, subject to tomorrow's planned service and escape constraints. Fertilizer reserves account for upcoming native and dedicated-worker pickups. These policies value the whole production cycle, including inputs and labor.
- **Opponent interaction:** sale horizons can extend when observed worker positions and production resemble the same public tape. The V45 opening replaces its predecessor's split wheat orders with a 70-unit round trip. Whether either helps depends on the opposing order stream.

Source: `data/router_refresh_20260916/v45/main.py`, especially `_router`, `_v219_qualifies`, `_v219_request`, `_r36_reserve`, `_r85_feed`, `_r85_reserve`, and the final `_OPEN_PARENT` wrapper. Published notebook: [V45](https://www.kaggle.com/code/ahmedberatozer/kaggriculture-v45-first-turn-wheat-round-trip).

## Why our earlier research missed this

Our changes mostly improved selling around an older production schedule. In the previous refresh, they added only about 101–353 average margin over the raw parent against the four stronger public agents, while both versions lost all sixteen games to each. The earlier narrow benchmark rewarded beating relatives of the same older policy. It did not validate strength against the newer production-and-execution family. See [the refresh study](router_refresh.md).

## Research priority

Use the frozen newer routers as baselines, keeping our uploaded agent as a historical control. Next isolate the remaining production selection and wheat economy: separate harvested wheat from purchased-and-resold stock, record feed consumption and discarded inventory, and compare wheat sale quantities and execution prices. Then disable feed/replenishment rules and route selection separately under common shop draws. Test early-sale decisions against several modern opponents because their effects reverse across opponents here. Terminal planning is a low priority on this evidence. These are next-step recommendations, not a promoted policy or a new submission.

## Validation and limits

All 192 games completed 720 valid states. Frozen source hashes match; disabled mechanisms have zero recorded activations. Nonzero error counters: 0. Maximum measured action time under concurrent load: 0.342s (not a competition-host timing certificate).

Results depend on these two opponents and eight shop sequences. This experiment does not isolate the entire production-route portfolio or all execution layers, estimate a settled ladder rating, or establish why QQ Farming had a particular displayed rating. The uploaded agent remains unchanged.

Reproduce: `.venv/Scripts/python.exe scripts/research_router_mechanisms.py`, then `.venv/Scripts/python.exe scripts/report_router_mechanisms.py`. Raw data and the frozen source manifest are in `results/fresh/router_mechanisms/`.
