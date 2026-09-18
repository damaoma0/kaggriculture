# BigAngel: opening capital failure and verified fix

## Finding

Episode **109709600**, seed **2006799007**, submission **56280048**, our seat **1**. Actual result: BigAngel **129,710**, us **122,927** (loss **6,783**).

The uploaded agent reproduced all **719 actions** exactly. Replaying both recorded action streams reproduced all **720 states**, checking both players' farms, market, town and private inventory. This is an inherited V45 opening weakness, not an execution timeout or the forecast entry-point bug.

At zero-based turn 0:

- We buy 70 wheat and sell 70.
- BigAngel buys 14 and sells 10, retaining four feed units.
- Under the engine's simultaneous, order-index-aligned market execution, our wheat costs **2,216** and sells for **2,174**: a **42** loss. A round trip is only neutral against an unchanged market; opposing inventory changes break that assumption.
- On turn 1 we buy five feed wheat for **140**, plus five workers and two cows/two sheep for **1,812**. Cash is **1,006**.
- The full crop plan needs **1,030** in seeds: twelve melons at 80 and seven wheat at 10. The opening is now underfunded by **24**.
- Cash reaches **6** after the turn-17 melon purchase. Wheat purchases on turns 19 and 20 are clamped to zero. Planting is suppressed on turns 20 and 21.

We end day one with **4 wheat + 12 melons**, instead of **7 wheat + 12 melons**. There are three unintended empty crop plots; the two additional empty tiles are reserved for later animals. Wheat counts recover to seven by state 96, but the missed early harvests are permanent.

## Fix

Buy and retain the five required feed units on turn 0. Remove the inherited wheat sale and feed repurchase on turn 1. Preserve the remaining route and market actions.

In this match the feed costs **136**. Workers/animals cost **1,812**, seeds cost **1,030**, leaving **22** after the complete opening. This removes exposure to a large speculative round trip and to the next turn's wheat price.

Files:

- `agents/v45_opening_capital_fixed.py`: isolated capital fix over the exact uploaded entry point, for attribution.
- `agents/v45_event_opening_fixed.py`: same capital fix plus the already prepared forecast entry-point correction; standalone candidate. SHA256 `e512d755d45fb3cee6602493a9af799131fb3b2dd3707f927e744e4b7a6cd7a3`.

Neither file has been submitted. Frozen submission archives and previous selected agents remain unchanged.

## Match counterfactual

Opponent actions and observed shop sequence are held fixed. This measures the change against this recorded stream; BigAngel would be able to react in a new live match. Other engine dynamics continue normally.

| Policy | Day-one wheat | Our final cash | BigAngel cash | Our margin |
|---|---:|---:|---:|---:|
| Uploaded original | 4 | 122,927 | 129,710 | -6,783 |
| Capital fix only | 7 | 123,161 | 129,570 | -6,409 |
| Entry-point fix only | 4 | 122,927 | 129,710 | -6,783 |
| Both fixes | 7 | 123,161 | 129,570 | -6,409 |

The opening repair improves the margin by **374**, but does not reverse the defeat. Correcting the forecast entry point changes no decisions in this episode, although it initializes the model correctly (135 valued lots, zero errors).

## Validation

- Official market engine sweep: all **5,151** opponent initial buy/sell combinations (buy 0–100 wheat, then sell 0–purchased quantity). Five feed units always acquired, with **22–25 cash** available after the full standard day-one budget. This is a bounded trade-family test, not exhaustive coverage of arbitrary market queues or nondefault game rules.
- **32 full games / 16 paired comparisons**, fresh seeds 153000–153007, eight forced first-shop types, alternating player seat by seed. Later shops use deterministic seed-specific schedules shared within each pair.
- Two opponents: native V45 and native V45 with BigAngel's observed first two market actions. The latter is an opening stress opponent, not a reconstruction of BigAngel's full strategy.
- All 16 fixed games planted **7 wheat + 12 melons** on day one.
- Against the small-flip variant: mean margin gain **312.375**, positive in **8/8** seeds; mean own-cash gain **167.125**.
- Against normal V45: own final cash unchanged on every seed; margin **+1** each, due to the opponent's cash change.
- Panel wins: **8/16 original → 16/16 fixed**. This is a narrow regression panel, not a leaderboard strength estimate.
- Actual Kaggle file-loader vs named-agent action parity: **719 actions in each of 16 isolated-fix games**. Combined standalone export separately checked for all **719 actions** in the BigAngel counterfactual, with ledger conservation verified for both players.

## Why the remaining loss needs separate work

In the combined-fix counterfactual, our total sales revenue is **164,708**, versus BigAngel's **159,757**: we earn **4,951 more**. However, we spend **11,360 more**:

| Expense | Our excess spending |
|---|---:|
| Workers | 5,613 |
| Land | 4,000 |
| Purchased wheat | 1,317 |
| Animals, net | 400 |
| Purchased fertilizer | 30 |
| Total | 11,360 |

This accounting explains the remaining **6,409** gap in the fixed-stream test. It does not prove that independently removing those expenses would retain the revenue: worker tours, land purchases and production are coupled. The useful next experiment is an observation-aware marginal-return gate on expansion and worker use, evaluated across shops and opponents, rather than further opening investment alone.

## Reproducibility

- `scripts/diagnose_bigangel.py`: builds candidates, exact replay/parity audit, four counterfactuals.
- `scripts/verify_opening_capital.py`: market stress sweep and fresh paired full games.
- `scripts/verify_bigangel_combined.py`: combined export parity, forecast initialization and ledger audit.
- Evidence: `results/fresh/bigangel/diagnosis.json`, `verification.json`, `combined_export.json`, `regressions/`, and `replays/episode-109709600-replay.json`.
