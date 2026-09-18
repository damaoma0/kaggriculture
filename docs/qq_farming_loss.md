# Why we lost to QQ Farming

**Episode 109609580: our submission 56273827 scored 104,306; QQ Farming submission 56273939 scored 110,166. Loss: 5,860 cash (5.6% of our final cash).** Both agents finished normally. The submission API snapshot contains ten public wins and this one public loss; it does not provide historical opponent ratings. The reported ~1500 rating is user-supplied context, not a verified measurement here.

## Main finding

QQ converted a larger, more diversified farm into more late-game revenue. Our early cash lead overstated our position because QQ was still investing and had substantial crops and goods waiting to be sold. The replay does not establish that QQ has a better price forecaster: some realized prices were worse, and its behavior could come from a preplanned route or a reactive policy.

At turn 432 (18 days elapsed), we had **43,030 cash versus 18,656**, a lead of 24,374. But QQ had four land quadrants versus our three, 40 strawberry plants versus 31, 16 tomato plants versus zero, and 12 melon plants versus zero. It also held 42 strawberries, 12 melons and 22 milk in its shed, versus our zero strawberries, zero melons and 15 milk. These are physical assets and inventory, not cash-equivalent valuations.

| Checkpoint | Our cash | QQ cash | Our lead |
|---|---:|---:|---:|
| Turn 216 | 909 | 4,457 | -3,548 |
| Turn 288 | 17,234 | 2,962 | +14,272 |
| Turn 432 | 43,030 | 18,656 | +24,374 |
| Turn 576 | 76,214 | 69,096 | +7,118 |
| Turn 696 | 98,820 | 99,113 | -293 |
| Turn 719 | 104,306 | 110,166 | -5,860 |

## Exact cash explanation

| | Us | QQ | QQ minus us |
|---|---:|---:|---:|
| Starting cash | 3,000 | 3,000 | 0 |
| Sales revenue | 136,303 | 150,488 | +14,185 |
| Total spending | 34,997 | 43,322 | +8,325 |
| Final cash | 104,306 | 110,166 | +5,860 |

Both cash ledgers reconcile exactly: starting cash + successful sales − successful purchases, land and hiring. Requested but unsuccessful orders are not counted as sales.

| Product | Our sold units | QQ sold units | Our revenue | QQ revenue | QQ revenue advantage |
|---|---:|---:|---:|---:|---:|
| TOMATO | 0 | 166 | 0 | 13,046 | +13,046 |
| STRAWBERRY | 240 | 316 | 35,588 | 44,122 | +8,534 |
| WOOL | 133 | 161 | 19,718 | 27,625 | +7,907 |
| CARROT | 18 | 52 | 818 | 2,201 | +1,383 |
| EGG | 79 | 74 | 4,122 | 3,834 | -288 |
| FERTILIZER | 332 | 250 | 14,092 | 13,072 | -1,020 |
| MILK | 261 | 194 | 22,422 | 19,420 | -3,002 |
| MELON | 72 | 90 | 17,440 | 13,705 | -3,735 |
| WHEAT | 561 | 295 | 22,103 | 13,463 | -8,640 |

These are accounting contributions, not isolated causal estimates. Adding QQ’s tomato sales to our existing farm would require land, seed, labor and route changes, and would change shared market prices.

## Production and timing differences

- **Tomatoes were a missing revenue stream for us.** QQ sold 166 tomatoes for 13,046; we planted and sold none. It planted 21 tomatoes over the season. Of that revenue, 11,251 arrived in the last six days. The shop sequence supported tomato demand through Farmers Market and Pizza Shop.
- **Strawberries were primarily a volume advantage.** QQ sold 316 versus our 240, earning 44,122 versus 35,588. Its average sale price was actually lower (139.63 versus 148.28), so this does not demonstrate superior strawberry sale timing. QQ planted 40 strawberry seeds; our action tape requested 31 plant operations. Harvest totals were 320 versus 246, with a small amount of output not reaching sales.
- **QQ reduced its dairy operation late.** It had 11 cows at turn 432 and three at turn 576. Five cows escaped at turn 528 and three at turn 552 after missed feeding. This followed a milk-price decline from 116 at turn 432 to 13 at turn 528. We kept nine cows throughout that period. Whether QQ deliberately reacted to price or followed a fixed retirement schedule cannot be inferred from this replay.
- **More wool reached the valuable late market.** Two yarn stores had arrived by turn 504. During turns 576–718, QQ sold 74 wool for 16,138 versus our 43 for 9,317. Across the whole season QQ sold 161 wool versus 133 and earned an average 171.58 per unit versus our 148.26. This reflects different herd sizes, production dates and selling decisions together; it is not a clean test of holding inventory.
- **The extra scale did not require a larger total wage bill in this match.** QQ spent 5,303 on hiring versus our 5,400, but 7,000 on land versus our 3,000. It bought more feed and animal/seed capacity. This makes route allocation and crop choice stronger research targets than simply hiring more workers.

## What did not explain the loss

- No crash or invalid termination: both players ended DONE after 720 recorded states.
- No packaging discrepancy: all 719 submitted-agent actions matched our selected local source on the actual replay observations.
- No large pile of unsold market goods at the end: our carried inventories were empty and the shed held only five fertilizer among sellable products, quoted at one each. An unused goose and leftover seeds indicate some waste, but the animal/seed purchase costs remaining there total 490, far below the 5,860 gap; those items have no terminal salvage value.
- One loss does not prove QQ is universally stronger, or that its rating predicts the result of every match. This is one realized shop sequence and one opponent submission.

## Recommended research order

1. **Evaluate whole midgame production plans**, beginning with tomato/strawberry capacity and a fourth quadrant, using QQ’s observed output mix as a benchmark. Compare full-season margin and costs across independent shop sequences; do not copy this replay as a universal policy.
2. **Test herd retirement plus worker reassignment.** Reducing cows alone may save feed but also forgo output; the useful experiment combines retirement with productive alternative work. Our recent one-animal study does not cover this larger decision.
3. **Use inventory and forthcoming harvests in board evaluation.** The 24,374 cash lead at turn 432 was misleading. Score the board through continuations that include crop cohorts, maintenance obligations, both players’ supply and uncertain future demand.
4. Retain current sale-ordering improvements while testing these production changes. This match supplies stronger evidence for a production/route gap than for replacing the price forecaster first.

## Evidence and reproducibility

Downloaded through Kaggle’s authenticated read-only episode API. Replay: `results/fresh/qq_farming/episode-109609580-replay.json`; API match listing: `episodes.json`; exact ledger and checkpoints: `audit.json`; successful transaction records: `trades.json`; physical action traces: `physical.json`.
Run `.venv/Scripts/python.exe scripts/analyze_qq_farming.py`, then `.venv/Scripts/python.exe scripts/report_qq_farming.py`. The official local engine reproduces both farms, both private states, the market and town at every one of the 720 replay states. No opponent source code is assumed, no alternative policy was promoted, and no submission was changed.
