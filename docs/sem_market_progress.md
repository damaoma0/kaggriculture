# sem_market: a hold-and-batch sell rule without the leader's schedule (2026-09-24)

## 0. Result (FINAL, 2026-09-25 ~00:45)
- Rule: hold a product while town consumption out-runs the rival's observed sales (48-step flow from the public market
  inventory), sell at post-tick steps the units whose exact marginal price stays >= q x the 6-step price high, force
  above smax, liquidate on day 29. Fitted per product on an exact market-only replay of the 54 logged leader worlds.
- Holding ALL six fitted products: leader worlds G1 +0.019 (b4ed59e build) / +0.008 (c1 build) of leader cash, but in
  new worlds (p2750, frozen 2750-3000 rivals) margin -1,545 a game over 59 worlds (95% CI -3,474..-106): our price
  rises (+0.7k own) but the rival gains more (+2.3k), mostly wool and milk.
- Holding STRAWBERRIES ONLY (the module default now): G1 on c1 0.886 vs 0.871 (+0.015, 11 of 12 worlds better, margin
  +0.6k on intact10); p2750 on c1, 40 FRESH worlds (not used to choose it): margin +113 (-299..+557), own +812
  (+425..+1,233), wins 4 -> 4. All 100 p2750 worlds: margin -41 (-337..+244), own +875 (+607..+1,153), wins 8 -> 8.
  So: margin-neutral in new worlds, +0.9k own cash, +0.015 of leader cash in leader worlds. The six-product version
  must NOT be merged.
- Wheat buy-ahead (coordinator scope): negative in both world sets; default OFF (section 6).
- Merge: `scripts/sem_market_merge.py agents/mgt_lead_deploy.py <dst>` (section 9).

Files (all new): `scripts/fragments/sem_market.py` (stdlib-only module), `agents/mgt_lead_deploy_sell.py` (copy of
`agents/mgt_lead_deploy.py` at b4ed59e + the SEM_MARKET SELL BLOCK), `agents/mgt_lead_deploy_sell_base.py` (same, block
inert: `sell_source="leader"`), `agents/mgt_lead_deploy_sell_c1.py` / `_c1_base.py` (the block stacked on E1's c1 plan
build = working-tree `agents/mgt_lead_deploy.py` at 23:26, sha 75468cd9...), `scripts/sem_market_merge.py` (applies the
block to any deploy copy), `scripts/sem_market_g1.py` (G1 cells through `scripts/lead_ablation.py`'s deploy adapter).
Results: G1 `results/fresh/lead_agent_20260924/abl_SMK*` (SMK0/SMKC1_0/SMKL0 = block inert; SMK = v1 six products
no gate; SMKF / SMKC1 = six products gated; SMKst / SMKC1st / SMKLst = strawberry only; SMKW / SMKSW / SMKSa = wheat);
p2750 `results/fresh/ladder_panel/mgt_lead_deploy_sell_{base,v1nogate,S,A,SA}` (b4ed59e build, 12 smoke worlds),
`mgt_lead_deploy_sell_c1_base` (c1, block inert, 88 worlds), `_c1_full` (c1, six products, 60 worlds),
`_c1_straw` (c1, strawberry only, 100 worlds); c1 base for the 12 smoke worlds = E1's `mgt_lpv_c1` (same logic).
The offline market-only evaluator is scratch code (not in the repo): exact re-pricing of the 54 LEADER / mgt_y3 logs
in results/fresh/market_events_20260924 with the rival's sales fixed, calling `sem_market.decide` step by step.

## 1. What the leaders do (54 logged leader worlds, hourly; results/fresh/market_events_20260924/LEADER)
- They sell in only 10-26% of the steps in which they hold stock (strawberry 0.26, milk 0.18, wool 0.20, egg 0.12),
  lots of ~3 (strawberry 2.8, milk 3.2, wool 2.8), holding 5-9 units per product in between.
- Timing: strawberry / milk / wool right after a consumption tick (t % 4 == 1: P 0.51-0.60 vs 0.04-0.18 at the other
  phases); eggs / carrots / tomatoes mostly at hours 20-23; melons the step they arrive.
- Price: more selling at the recent high (price at a new 24-step max: P 0.44-0.56; >10% below it: 0.15-0.21); less at
  very low levels (strawberry P 0.11 below 0.4x base vs 0.37 near base; wool 0.13 vs 0.43). Stock level barely matters.
- The rival sells in the same step 4-5x more often than chance (P 0.56-0.78 when the rival sells): both sell post-tick.

## 2. Mechanism and rule
Price is a pure function of market inventory (public in the observation); our units raise it for good, consumption
lowers it on a fixed schedule. With the rival's sales fixed, a unit is worth most when sold where the market is locally
emptiest, and holding only pays while town consumption out-runs the rival's sales (otherwise the rival sells into the
room we leave). Rule per product (`sem_market.decide`), all observable:
- ref = max published price over the last W=6 steps; thr = q_p x ref;
- flow gate: rival sales rate over the last H=48 steps (exact: inventory change - our sales + consumption; checked
  0 mismatches in 25,812 step-product checks on 6 logged worlds) >= consumption rate / kappa (kappa=1) -> sell all now;
- otherwise, at post-tick steps (t % 4 == 1), sell the units whose exact marginal price f(inventory + j) >= thr
  (sell the price down to q of its recent high); never at the $1 floor; stock above smax_p is sold regardless; total
  shed stock above 70 is sold down (purchases fail at 100);
- day 29: thr falls linearly to 0 from step 696, everything is sold from step 717;
- wheat (the deploy's herd reserve kept), fertilizer (pending-fertilize reserve kept) and melon: sell at once.

## 3. Parameters from an exact market-only replay
54 leader worlds x {leader, y3} production; rival sales, buys and consumption fixed; own arrivals from the logs (the
replay reproduces the logged revenue exactly). Mean per world vs sell-on-arrival (own revenue / margin):
| product | chosen (kappa 1, H 48, W 6, post-tick, liq 696) | leader production | y3 production | leader's own schedule (L) |
|---|---|---|---|---|
| strawberry | q 1.00, smax 30 | +3526 / +180 | +2117 / +607 | +1460 / +958 |
| milk | q 0.90, smax 10 | +520 / +207 | +203 / +102 | +825 / +612 |
| wool | q 0.95, smax 30 | +1683 / +574 | +411 / +71 | +388 / +1340 |
| egg | q 1.00, smax 30 | +50 / +40 | +43 / +39 | +23 / -7 |
| carrot | q 1.00, smax 30 | +54 / 0 | +53 / +14 | +53 / +12 |
| tomato | q 1.00, smax 30 | +57 / +34 | +376 / +331 | +78 / +54 |
| melon | at once | 0 | 0 | +171 / +337 (= selling in the delivery step) |
| total | | +5.9k / +1.0k | +3.2k / +1.2k | +3.0k / +3.3k |
Without the flow gate (v1: q 0.95 strawberry, no kappa) the margin gains were smaller on y3 production; holding
harder (q 1.0 without the gate) gives +4-5k own revenue per product but -1 to -2.6k margin (the frozen rival sells into
the room): rejected. The leader's own schedule has a larger margin gain, partly an artefact (the rival reacted to it).

## 4. G1: 12 leader worlds, full deploy agent, this episode held out
intact10 = without 112708229 (rival collapses in every cell) and 112714050 (rival collapses to 0.56x in E2s only).
| cell | mean12 | mean11 | clean9 | intact10 | own intact10 | margin intact10 | worlds better/worse vs E2 |
|---|---:|---:|---:|---:|---:|---:|---|
| E2 deploy (sell on arrival) | 0.843 | 0.834 | 0.823 | 0.835 | 89,453 | -19,540 | |
| E2s + leader's sell schedule | 0.893 | 0.883 | 0.871 | 0.862 | 91,893 | -17,418 | 11/1 |
| SMK0 = copy, sell_source=leader | 0.843 | 0.834 | 0.823 | 0.835 | identical to E2 in all 12 | | 0/0 |
| SMK v1 (no flow gate) | 0.867 | 0.858 | 0.849 | 0.860 | 92,062 | -17,115 | 11/1 |
| SMKF all six held (flow-gated) | 0.862 | 0.851 | 0.839 | 0.853 | 91,162 | -18,427 | 11/1 |
| SMKW wheat buy-ahead + wheat hold only | 0.832 | 0.821 | 0.823 | 0.819 | 88,450 | -22,813 | 6/6 |
| SMKSW sell rule + wheat (hold + buy-ahead 4 d) | 0.850 | 0.839 | 0.844 | 0.839 | 90,474 | -22,178 | 10/2 |
| SMKSa sell rule + buy-ahead 10 d (wheat sold at once) | 0.849 | 0.839 | 0.853 | 0.837 | 90,308 | -21,936 | 9/3 |
| E2_c1 (E1's c1 plan build) | 0.871 | 0.865 | 0.846 | 0.873 | 93,097 | -13,044 | |
| SMKC1_0 = c1 + block, leader | identical to E2_c1 in all 12 | | | | | | |
| SMKC1 = c1 + all six held | 0.879 | 0.869 | 0.862 | 0.876 | 93,720 | -13,064 | 9/3 vs E2_c1 |
E2s's headline +0.050 is inflated by 112714050 (+0.28 there, rival collapsed); on intact10 the leader schedule is
+0.027 and the six-product rule +0.018 (v1 +0.025). Per unit (12 worlds, E2 / E2s / SMKF): strawberry 153.9 / 155.2 / 158.2,
wool 149.4 / 165.2 / 154.6, carrot 58.4 / 65.2 / 58.4, milk 126.7 / 134.6 / 127.0.

## 5. p2750 smoke worlds (12) vs y3, and 48 more p2750 worlds
Base = the same agent with the block inert (reproduces mgt_lead_deploy_s1 in all 12 smoke worlds to the dollar).
| agent (12 smoke worlds) | own | rival | margin | vs base |
|---|---:|---:|---:|---:|
| mgt_y3 | 110,322 | 105,650 | +4,672 | |
| base (b4ed59e deploy, sell on arrival) | 92,068 | 111,368 | -19,300 | |
| S = six-product sell rule | 92,797 | 112,404 | -19,607 | -306 (6/6), own +729 |
| v1 sell rule (no flow gate) | 92,752 | 112,430 | -19,678 | -377 (5/7) |
| A = wheat buy-ahead only | 91,549 | 112,001 | -20,451 | -1,151 (5/7), wheat spend +994, sold -28 u |
| SA = sell rule + wheat buy-ahead | 93,147 | 112,762 | -19,614 | -314 (6/6) |
| c1 (E1, mgt_lpv_c1) | 94,001 | 106,658 | -12,657 | |
| c1 + six-product sell rule | 94,633 | 107,488 | -12,855 | -198 (5/7), own +632 |
48 more p2750 worlds (random sample, seed 24; c1 + six-product rule vs `mgt_lead_deploy_sell_c1_base` = c1 with the block
inert), one frozen-opponent break excluded:
| set | n | margin vs base (95% CI) | better/worse | own | rival | wins base -> rule |
|---|---:|---|---|---:|---:|---|
| smoke 12 | 12 | -198 (-2,012..+1,546) | 5/7 | +632 | +830 | 1 -> 2 |
| new 48 | 47 | **-1,889 (-4,204..-154)** | 20/27 | +737 | +2,626 | 3 -> 1 |
| all | 59 | **-1,545 (-3,474..-106)** | 25/34 | +716 | +2,261 | 4 -> 3 |
Per product (59 worlds, per game, own / rival revenue): strawberry +1,055 (price 141.6 -> 147.6) / +1,025, wool +16
(161.8 -> 164.7, -2.5 units) / +637, milk -164 / +102, tomato +136 / +136; the rest (sold at once) within +-160 of 0.
The rule does what it should for OUR price (+0.7k own cash a game) but against frozen 2750-3000 rivals the room it
leaves is worth more to the rival (+2.3k): a clear margin LOSS in new worlds, unlike the leader worlds (G1 margin +1.1k
on the b4ed59e build, 0 on c1) and unlike the market-only replay on the 54 leader worlds (+1.0-1.2k margin).

## 6. Wheat (coordinator scope)
Logged leader worlds: wheat is 25 at day 0, 30 by day 2-4, 34 at day 8, 37 at day 10, 40 at day 12, then flat (median
37-41, p10 21-30 late). Leaders buy mostly days 6-12 (feed), sell 20-30/day from day 12, dump ~65 on day 28-29. The
module's `wheat_buy` covers the herd's next `cover_days` of feed while the buy quote <= buy_max_price and day <=
buy_last_day, with the cash left after every other purchase minus a reserve and within shed room 85. Result: it hardly
triggers early (the opening spends the cash), and where it does it loses: G1 -0.011 alone / -0.013 on top of the sell
rule (margin -2.9k on intact10; one world, 112715010, -0.26 when the rival's replay gains 25%); p2750 -1,151 alone (wheat
spend +994, 28 fewer wheat units sold), -8 on top of the sell rule. Holding wheat surplus with the hold rule sells it
later at lower prices (32.3 vs 33.6 per unit in G1). Default: wheat buy-ahead OFF, wheat sold at once above the herd
reserve (the deploy rule). The new-world wheat gap to y3 (230-280 vs 442 units) is production volume, not trade.

## 7. Strawberry-only hold (the default)
Chosen from the 59-world per-product split above (strawberry was the only held product with a non-negative margin),
then tested on 40 FRESH p2750 worlds (random sample, seed 25, disjoint from the 60 above), c1 + rule vs c1 base:
| set | n | margin vs base (95% CI) | better/worse | own (95% CI) | rival | wins |
|---|---:|---|---|---|---:|---|
| fresh 40 | 40 | +113 (-299..+557) | 20/20 | **+812 (+425..+1,233)** | +698 | 4 -> 4 |
Per product (fresh 40): strawberry own +895 / rival +761 (margin +134); every other product within +-60 of 0.
G1 (12 leader worlds, this episode held out):
| cell | mean12 | mean11 | clean9 | intact10 | own intact10 | margin intact10 | better/worse |
|---|---:|---:|---:|---:|---:|---:|---|
| E2_c1 (c1, sell on arrival) | 0.871 | 0.865 | 0.846 | 0.873 | 93,097 | -13,044 | |
| SMKC1 (c1, all six held) | 0.879 | 0.869 | 0.862 | 0.876 | 93,720 | -13,064 | 9/3 |
| **SMKC1st (c1, strawberry only)** | **0.886** | **0.880** | **0.859** | **0.890** | **94,765** | **-12,414** | **11/1** |
| E2 (b4ed59e, sell on arrival) | 0.843 | 0.834 | 0.823 | 0.835 | 89,453 | -19,540 | |
| SMKst (b4ed59e, strawberry only) | 0.852 | 0.843 | 0.832 | 0.845 | 90,504 | -19,845 | 9/3 |
Strawberry price per unit in G1 on c1: 151.6 -> 158.3 (+1.3k revenue a game), same units (178).
Runtime: agent tmax 0.10-0.15 s a call with the module (0.10-0.12 without), +0.2-0.5 s a game.

## 8. All 100 p2750 worlds, strawberry-only (c1 + rule vs c1 base; no broken opponent tapes, no crashes)
| set | n | margin vs base (95% CI) | better/worse | own (95% CI) | rival | wins |
|---|---:|---|---|---|---:|---|
| smoke 12 | 12 | -33 (-686..+492) | 6/6 | +704 (+361..+1,026) | +737 | 1 -> 1 |
| 48 (used to pick strawberry) | 48 | -173 (-658..+278) | 27/21 | +971 (+532..+1,419) | +1,144 | 3 -> 3 |
| fresh 40 | 40 | +113 (-299..+557) | 20/20 | +812 (+425..+1,233) | +698 | 4 -> 4 |
| **all 100** | **100** | **-41 (-337..+244)** | 53/47 | **+875 (+607..+1,153)** | +917 | 8 -> 8 |
Strawberry over 100 worlds: price 142.9 -> 148.8 per unit (same units, -0.4), own +984, rival +967. Versus y3 the c1
deploy stays about -18.8k a game either way: the sell rule is margin-neutral in new worlds; its value is own cash
(+0.9k) and the leader-world gain (G1 +0.015 on c1).

Stacking check on E1's newest working-tree deploy (00:34, sha 860fe6a1, uncommitted, merged with
`scripts/sem_market_merge.py` into a scratch copy): G1 base 0.849 / 0.844 / 0.837 -> strawberry rule 0.858 / 0.852 /
0.842 (8 of 12 better), intact10 own +1.0k, margin -0.1k; strawberry 152.5 -> 156.8 per unit. Same picture.

## 9. How to merge
1. Keep `scripts/fragments/sem_market.py` (stdlib only, `SMK_` / `_smk_` prefixes; entry points `sell_orders`,
   `decide`, `wheat_buy`, `smk_price`, `smk_consumption`).
2. `.venv/Scripts/python.exe scripts/sem_market_merge.py agents/mgt_lead_deploy.py agents/<new>.py [--default leader]`
   copies from `agents/mgt_lead_deploy_sell.py`: (a) the SEM_MARKET SELL BLOCK right above `def _market` (`_smk()` loader,
   same pattern as `_sm()`; `_smk_sells`; `_smk_wheat_buys`; research override `SEM_MARKET_PARAMS` / env
   `SEM_MARKET_JSON`), (b) call site 1 right before `# shed overflow guard` in `_market`: replaces `sells` when
   `CFG["sell_source"] == "sem"` (hire funding, shed-overflow guard, buys, order assembly unchanged), (c) call site 2
   after `buys = wheat_buy + buys` (wheat buy-ahead, a no-op while `SMK_WHEAT["on"]` is False), (d) the CFG default.
   Anchors are asserted unique. The block is inert with `sell_source="leader"`: G1 12/12 identical to E2 and to E2_c1,
   p2750 12/12 identical to mgt_lead_deploy_s1 (to the dollar).
3. Wheat reserve: `_smk_sells` takes the deploy's own wheat quota (`T.cum_sold[d]["WHEAT"] - S["sold"]["WHEAT"]`, set by
   `_dep_sell_quota`) as the herd reserve, so plan-side changes to that quota carry over.
4. `sell_orders` needs `sold_total` = every unit we ordered to sell (the block passes `S["sold"]`, updated after the final
   order assembly), otherwise hire-funding / overflow sells are counted as the rival's.
5. Kaggle packaging: like `sem_maintenance`, the fragment is read from disk by `_smk()`; the single-file packager must
   inline `sem_market.py` into the `_SMKNS` namespace the same way.
