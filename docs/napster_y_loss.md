# Napster Y: similar farm, different cash

**Episode 109611734: our submission 56273827 finished at 108,333; Napster Y submission 56051218 finished at 112,815. Gap: 4,482.** Both finished normally. All 720 replay states reproduce exactly with the installed engine, including both farms, private inventories, town and market. All 719 of our actions match the submitted agent.

## The early cash lead was largely inventory

At turn 144, after six days, both farms had four cows, two sheep, three wheat plants, four strawberry plants and twelve melon plants. Our cash was 220; Napster's was 846, a difference of 626.

But our private seed stock included four strawberry seeds, nine wheat seeds and three carrot seeds; Napster held none. Those cost **550** to buy. We also held 20 wheat versus their 17. Thus the visible farm configuration concealed a substantial difference in prepaid supplies. This explains much of the cash lead without implying that one farm was worth 626 more. Seed purchase cost is not an estimate of its optimal continuation value.

## The mature farms were similar, but not identical

At turn 288 both farms had three land quadrants, 33 strawberry plants and 20 wheat plants. Their herds differed:

| | Us | Napster Y |
|---|---:|---:|
| Sheep | 10 | 11 |
| Cows | 7 | 6 |

Three animal positions differed. At `(5,3)` and `(5,4)` we had cows while Napster had sheep; at `(6,4)` we had a sheep while Napster had a cow. These coordinates are zero-based. Our two cows produced 27 milk each; their two corresponding sheep produced 26 wool each. Our third slot produced 24 wool, while their cow there produced 27 milk. Across these three positions alone, their realized harvested output was **28 more wool and 27 fewer milk**.

The purchase timing also differed. At turn 150 we bought two cows, whereas Napster bought two sheep. Later purchases changed the third position and final herd balance. This was not the turn-265 purchase examined in our recent demand study.

Over the whole season, Napster harvested 282 wool versus our 247, and sold 278 versus our 247. They harvested/sold 191 milk versus our 215. Small differences in species, placement dates, care and harvest schedules can matter despite a similar board silhouette.

## Exact financial comparison

| | Us | Napster Y | Napster minus us |
|---|---:|---:|---:|
| Sales revenue | 140,838 | 137,975 | -2,863 |
| Spending | 35,505 | 28,160 | -7,345 |
| Starting cash | 3,000 | 3,000 | 0 |
| Final cash | 108,333 | 112,815 | +4,482 |

We actually earned more gross revenue, but spent more. However, comparing purchase bills alone is misleading: we also sold much more wheat. The following accounting groups offset related revenues and purchases:

| Accounting group | Our net cash contribution | Napster net cash contribution | Napster advantage |
|---|---:|---:|---:|
| Milk + wool revenue minus cow + sheep purchases | 67,724 | 74,089 | +6,365 |
| Wheat sales minus wheat purchases and wheat seeds | 8,185 | 4,189 | -3,996 |
| Fertilizer sales minus fertilizer purchases | 12,371 | 12,778 | +407 |
| Carrot sales minus carrot seeds | 408 | 1,980 | +1,572 |
| Strawberry sales minus strawberry seeds | 11,727 | 11,450 | -277 |
| Melon sales minus melon seeds | 13,318 | 13,271 | -47 |
| Hiring | -5,400 | -4,942 | +458 |
| Land | -3,000 | -3,000 | 0 |
| **Total, excluding identical starting cash** | **105,333** | **109,815** | **+4,482** |

Feed spending is included in the wheat group, not allocated to individual animals. Fertilizer use, labor and land likewise cross production categories. These are exact accounting contributions, not isolated profitability estimates or counterfactual proof that changing just one purchase would earn the entire difference.

### More wool, rather than substantially better wool prices

- Our 247 wool sold for 56,974: **230.66 per unit**.
- Napster's 278 wool sold for 64,417: **231.72 per unit**.
- Revenue difference: **7,443**. Valuing the additional 31 units at our average price explains approximately **7,151**; the remaining **292** is the average-price difference applied to their quantity. This is an arithmetic decomposition, not a sale-timing experiment.
- Napster also sold 91 carrots versus our 18. After seed costs, the carrot difference contributed **1,572**.

### Less buying was not automatically more efficient

We bought 349 wheat and sold 568; Napster bought 140 and sold 263. Our wheat purchases cost 10,945 versus 5,330, but our wheat sales were 21,100 versus 11,089. After wheat seeds, our net wheat cash contribution was **3,996 higher**. Napster actually fed animals 384 times versus our 364, so their smaller wheat purchase bill does not mean lower feed consumption.

Similarly, fertilizer purchases cost us 1,950 versus their 418, but we also earned more fertilizer revenue. The net fertilizer advantage to Napster was **407**, not the full 1,532 purchase-cost difference.

## Shops and the limits of the inference

The shared shop sequence was Yarn Store, Pizza Shop, Brunch Spot, Ice Cream Shop, Yarn Store, Bakery, Pizza Shop, Ice Cream Shop, arriving every three days. Yarn demand was already visible before the turn-150 purchases, and a second yarn store arrived on day 15. Wool prices stayed strong while milk prices weakened: at turn 432 wool was quoted at 234 and milk at 99; at turn 576 the quotes were 233 and 42.

This sequence rewarded the sheep-heavy mix. It is evidence that Napster's allocation worked better here, not proof it would dominate under other shop draws. The replay cannot reveal whether their policy dynamically forecasts prices or selects among precomputed routes.

Our first two sheep escaped at turn 696 after feeding stopped; Napster retained all eleven sheep. That alone is not proof of a mistake: ours had zero held yield at escape, and the original sheep's next regular production day would fall outside the season. Any proposed extension of care needs a full marginal-cost calculation.

## Research implication

This match suggests a narrower experiment than the QQ Farming comparison: **vary species assignments and purchase timing within an otherwise similar farm plan**, and include the cost of reserving seed/feed inventories. The current-price sale ordering is not the obvious main weakness here. A worthwhile test should cover the earlier turn-150 animal purchases, maintain feasible cash and service schedules, and evaluate multiple future shop sequences and opponents. The one-animal turn-265 test did not cover this decision.

No policy changes or Kaggle submissions were made during this audit.

## Evidence and reproduction

- Replay: `results/fresh/napster_y/episode-109611734-replay.json`.
- Exact ledgers/checkpoints: `results/fresh/napster_y/audit.json`.
- Successful transactions: `results/fresh/napster_y/trades.json`.
- Physical actions and harvested quantities: `results/fresh/napster_y/physical.json`.
- Episode metadata: `results/fresh/napster_y/episodes.json`.
- Reproduce the audit with `.venv/Scripts/python.exe scripts/analyze_qq_farming.py --episode 109611734 --out results/fresh/napster_y`.

The shared audit script retains its original QQ Farming defaults. It now accepts an episode and output directory so both analyses use the same accounting and exact-reproduction checks.
