# Economic tape search and bounded switching — 23 September 2026

A public-information rollout picker recovered **10,034 coins of margin** in episode **111269605**, reducing an **11,836** loss to **1,802**. It selected the transition before evaluating the actual future. This is a working research selector; broad profitability and competition runtime are not established.

## What is implemented

The selector receives only the current public observation, our private inventory, and our own m1 memory. It does not receive the actual game seed, future shops, recorded future actions, or rival private inventory. It operates at a shop reveal. Native actions and the sheep overlay still execute the chosen production plan.

1. Keep the normal adaptive policy and the incumbent as candidates. Retrieve additional tapes under tile-distance limits of 8, 14, and 24, taking new candidates at each limit, up to seven total.
2. Start every continuation from the actual farm, including cohort birth dates, held yields, seeds, worker inventories, cash, and current prices. Simulate the official engine through step 718.
3. Force each alternative only through the next three-day reveal boundary. Afterward, the normal native router adapts to the simulated shops and changed farm. It may choose to keep the new tape.
4. Use three fixed, common random future-shop sequences, sampled uniformly with replacement. Pair these with visible-rival production scenarios at 0.7, 1.0, and 1.3 times the cohort model. Existing short crop plots repeat; no rival private inventory or unseen expansion is supplied.
5. Compare final **our cash minus rival cash**, including the effect of our sales on the rival’s prices. Rank by `mean projected margin gain − 0.5 × standard deviation`.
6. Admit only if this score exceeds 350, the worst scenario is at least −500, mean own-cash gain is positive, protected existing long crops and animals survive the first window, and failed hires do not increase. The original gate also preserves every existing-animal feed action; the cohort variant prices feed changes through their effects on survival, output, and final cash.

The three scenarios are a small stress set, not calibrated confidence bounds. Unknown rival production is modeled; the physical simulation of our proposed actions uses the installed official engine. Forecast weeds are omitted.

## Why the large wool switch works

At day 15 the incumbent donor **110226826** had demand distance **9.5** and no tile mismatch. Donor **109529802** had distance **10** and three different tile labels. The old distance rule preferred the incumbent. The rollout predicted margin gains of **6,221 / 10,594 / 10,981** and passed the strict protection gate.

The actual switch buys one sheep on day 15 and one on day 16, placing them on days 15 and 17. It also improves service of existing sheep: wool output already increases on days 17 and 18, before the new sheep can produce. From day 15 onward, successful feeds rise from **219 to 238**, and care actions from **192 to 220**. After the day-18 handoff boundary, the ordinary router continues with the new donor.

| Quantity after the decision | Baseline | Selected | Change |
|---|---:|---:|---:|
| Our final cash | 84,707 | 94,423 | +9,716 |
| Rival final cash | 96,543 | 96,225 | -318 |
| Final margin | -11,836 | -1,802 | +10,034 |
| Wool sold after day 15 | 42 | 92 | +50 |

| Economic contribution | Change in our cash |
|---|---:|
| CARROT revenue | +1,716 |
| EGG revenue | -325 |
| FERTILIZER revenue | +464 |
| MILK revenue | -76 |
| STRAWBERRY revenue | +246 |
| TOMATO revenue | -705 |
| WHEAT revenue | -1,338 |
| WOOL revenue | +10,320 |
| BUY_ANIMAL:SHEEP spending | -1,000 |
| BUY_PRODUCT:WHEAT spending | -605 |
| BUY_SEED:CARROT spending | -40 |
| BUY_SEED:TOMATO spending | +100 |
| BUY_SEED:WHEAT spending | +40 |
| HIRE spending | +919 |

Revenue rises **10,302** and spending rises **586**, giving **9,716** more own cash. The rival loses **318**, bringing the margin gain to **10,034**. All figures reconcile to the exact engine ledger.

## Full historical panel

Seven named large losses are diagnostic cases. Twelve additional games and their reveal days were sampled before the strict selector’s validation outcomes were examined. The strict selector changed none of those twelve. The cohort gate was developed using those historical results, so its figures below are development evidence, not independent validation. The live panel was kept separate for that variant.

| Episode | Day | Original margin | Strict gain | Cohort-gate gain | Best tested with hindsight |
|---|---:|---:|---:|---:|---:|
| 111261836 | 18 | -8,636 | +0 | +0 | +0 |
| 111262874 | 12 | -12,585 | +0 | +0 | +18,449 |
| 111269605 | 15 | -11,836 | +10,034 | +10,034 | +10,034 |
| 111284610 | 15 | -8,732 | +0 | +0 | +0 |
| 111287532 | 12 | -6,063 | +0 | +0 | +6,594 |
| 111324547 | 15 | -9,571 | +0 | +0 | +1,718 |
| 111337545 | 15 | -10,336 | +0 | +0 | +3,160 |
| 111245064 | 18 | +51,860 | +0 | +0 | +0 |
| 111250531 | 15 | +3,649 | +0 | +4,266 | +4,664 |
| 111286417 | 18 | +2,490 | +0 | +0 | +0 |
| 111290865 | 12 | -6,075 | +0 | +810 | +10,694 |
| 111297593 | 15 | +391 | +0 | +0 | +4,420 |
| 111305442 | 12 | +7,219 | +0 | +0 | +0 |
| 111403839 | 18 | +64 | +0 | +0 | +1,395 |
| 111668844 | 12 | -3,659 | +0 | +0 | +0 |
| 112087027 | 15 | -4,732 | +0 | +0 | +5,350 |
| 112284146 | 12 | +834 | +0 | +0 | +3,774 |
| 112430567 | 18 | +4,633 | +0 | +0 | +0 |
| 112473458 | 18 | +1,604 | +0 | +0 | +962 |

The hindsight column is an upper bound within this small tested candidate set. It is never used for selection. It shows remaining opportunity, including a **+18,449** transition in the largest loss that the current forecast/transition gate cannot justify in advance. No claim is made that its actual favorable future was predictable.

## Responsive-opponent check

Four fresh random seeds, both seats, native m1 and both research admission rules against live V56. Every game uses natural shops and weeds. There are only four independent worlds; the two seats are paired views, not eight independent samples. One day-15 decision is tested, rather than repeated intervention at every reveal.

| Rule | Pairs | Changed | Better / worse | Mean margin change | Worst | Best |
|---|---:|---:|---:|---:|---:|---:|
| Strict | 8 | 0 | 0 / 0 | +0 | +0 | +0 |
| Cohort | 8 | 2 | 2 / 0 | +543 | +0 | +2,173 |

| Seed | Seat | Baseline margin | Strict gain | Cohort gain |
|---|---:|---:|---:|---:|
| 1178485103 | 0 | +16,784 | +0 | +0 |
| 1178485103 | 1 | +16,784 | +0 | +0 |
| 1790550537 | 0 | +6,384 | +0 | +0 |
| 1790550537 | 1 | +6,384 | +0 | +0 |
| 1328429290 | 0 | -3,799 | +0 | +0 |
| 1328429290 | 1 | -3,799 | +0 | +0 |
| 1329978515 | 0 | -3,626 | +0 | +2,173 |
| 1329978515 | 1 | -3,626 | +0 | +2,173 |

**The natural-RNG uplift did not survive the demand control.** The only changed live world had different future shop draws because farm changes alter the engine’s random-number consumption. I crossed both observed shop sequences with both responsive policies, using the already-selected day-15 route. Future shops enter only the evaluation environment. Both natural-run diagonals reproduce exactly.

| Fixed future shop world | Change in our cash | Change in rival cash | Change in margin |
|---|---:|---:|---:|
| baseline | +3,783 | +6,239 | -2,456 |
| cohort | +2,401 | +2,640 | -239 |

In the original shop world, our cash increased **3,783**, but the rival gained **6,239**, so margin fell **2,456**. Rival strawberry revenue rose **6,106** and milk revenue **2,076**, with unchanged quantities sold for those two goods. The forecast includes price effects on the rival, but its simple supply model and three sampled futures did not price this exposure accurately enough. The relaxed cohort gate is **not ready to replace the baseline**. The fixed-world **+10,034** wool recovery remains a separate, verified result.

The next useful improvements are therefore specific: calibrate future rival sales by cohort and delivery date; evaluate more future demand branches adaptively for borderline switches; and use the scheduler to repair specific missing obligations in economically promising candidates. Relaxing compatibility limits alone does not establish a profitable continuation.

## Verification and practical limits

- Every historical native prefix and final cash reproduces the original recording exactly. All 19 historical controls and every live game reconcile cash to successful transactions.
- Regression checks cover the isolated official engine across midnight, agent-memory cloning across daily resets, future-shop prefix preservation, birth-date-aware asset identity, and rejection of protected-cohort loss.
- Historical decisions took **40.0–75.8 seconds** (mean **65.9**) under concurrent research workloads. This is much too slow for the competition agent. Forecast calibration and runtime need work before integration.
- Cohort protection only covers the first transition window. Full-season economic forecasts include later effects, but future uncertainty can still cause losses. The gate is not a guarantee of a lossless handoff.
- Candidate retrieval is still a shortlist from historical tapes. A missing production trajectory cannot be invented by this selector. A semantic repair compiler should add or reassign obligations only where the projected failure identifies a specific missing feed, watering, fertilizer, harvest, delivery, or replacement-cohort job.
- The deployed `agents/mgt_m1.py` remains unchanged. No competition promotion or submission was made.

## Files

- Planner: [value_tape_search.py](../scripts/value_tape_search.py)
- Admission rules: [value_tape_policies.py](../scripts/value_tape_policies.py)
- Historical runner: [probe_value_tape_search.py](../scripts/probe_value_tape_search.py)
- Live runner: [benchmark_value_tape_search.py](../scripts/benchmark_value_tape_search.py)
- Exact daily case trace: [selected_wool_case_trace.json](../results/fresh/value_tape_search_20260923/selected_wool_case_trace.json)
- Controlled live comparison: [fixed_shop_check.json](../results/fresh/value_tape_search_20260923/live/fixed_shop_check.json)
- Frozen definitions and hashes: [source_manifest.json](../results/fresh/value_tape_search_20260923/source_manifest.json)
- Detailed candidate predictions and counterfactuals: [results directory](../results/fresh/value_tape_search_20260923/)
