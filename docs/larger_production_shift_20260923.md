# Larger sheep shifts and late strawberry sales (23 September 2026)

The current `mgt_m1` tape remains the reference. None of the tested larger changes is ready to replace it. The tests below score **final cash margin against the opponent**, so price changes to the opponent's sales count as well as our own revenue.

## Early sheep expansion

The candidate credits the forecast fall in **opponent** wool prices when it values extra sheep, then relaxes the sheep target, threshold, and cutoff to allow additions through day 12. It keeps the existing cash and four-overlay-hand limits. The exact-engine replay runs our candidate agent live while retaining each opponent's recorded actions and the actual shop draws. The source and episode split were frozen before the results: [design](../results/fresh/larger_shift_20260923/sheep/design.json), [script](../scripts/investigate_sheep_shift.py).

The development panel has 14 games with at least two Yarn Stores by day 12 (seven original losses and seven wins) and four zero-Yarn controls. The further 14 high-Yarn games were used **after the development rule rejected the candidate**, as a stress test, not a promotion confirmation.

| Candidate | Development mean margin (18) | Further high-Yarn mean margin (14) | Main observation |
|---|---:|---:|---|
| Credit opponent price effect only | 0 | not run | No action changed; the existing purchase gate still decided the same way. |
| Earlier/larger sheep on current eligible fields | **−1,087** | **−114** | Bought 13 additional sheep in development and 34 further sheep; field conversion fired in 14 of 28 high-Yarn games. |
| Exclude wheat tiles, use carrot/empty only | −32 | not run | Bought **zero** overlay sheep in development. The tape had no eligible carrot-only room; this arm merely blocked existing purchases and is not an additive sheep experiment. |

Across all 28 high-Yarn games, the larger-field candidate changed 14 games: 3 improved, 11 worsened. Its mean margin change was **−756 per game** (episode bootstrap 95% interval approximately **−2,264 to +779**). Its own cash fell **3,519** and the opponent's fell **2,763** per game. The latter is real competitive value, but it did not reliably cover animal, feed, hand, and displaced-field costs. The baseline controls replayed exactly. [Combined results](../results/fresh/larger_shift_20260923/sheep/combined_summary.json), [development details](../results/fresh/larger_shift_20260923/sheep/development_summary.json), [stress details](../results/fresh/larger_shift_20260923/sheep/stress_summary.json).

The opponent price effect can be decisive in individual games. In episode **111967793**, four extra sheep changed our cash by **−10,865** but the opponent's by **−20,512**, gaining **9,647** margin. In **111735916**, our cash fell **14,453** and the opponent's **20,985**, gaining **6,532** margin. Other apparently similar states went the other way: in **111870997**, four added sheep lost **5,880** margin. Wool quote, inventory, visible Yarn Stores, and flock counts at the decision were nearly identical for 111735916 and 111870997; the rival's subsequent wool exposure differed. This is evidence for opponent-aware sizing, but not yet a dependable trigger. [Decision features](../results/fresh/larger_shift_20260923/sheep/externality_features.json).

Wheat conversion is particularly risky. The borrowed tape sometimes harvests wheat and feeds animals from that hand's carried inventory. Pasture in that field removes both the crop revenue and a link in the feed route. A carrot-only restriction avoids that specific break but found no feasible early tile in the development panel. The existing overlay does not directly support cow replacement.

## Cow-to-sheep feasibility

The engine rejects `DIG` on an occupied pasture. A cow must go unfed for two days before it escapes; only then can the pasture receive a sheep. The sheep's first wool arrives six days after placement, whereas the cow can keep producing milk every two days. We therefore tested a deliberately favorable same-route proxy on the 14 high-Yarn development games:

* An instantaneous day-12 swap of each of **72** existing cows, charging $500 and selling spare wool, was positive for **29/72** cows; the average swap was **−344** margin. Choosing the best cow **after** seeing the result gave **+419** per game, positive in **8/14** games.
* For that hindsight best cow in each game, suppressing its feed on days 10–11 so it actually escapes, then magically placing a sheep on day 12 for $500, gave only **+147** mean margin, positive in **6/14** games. This still omits purchase/pickup/placement labour and uses the recorded care route, so it is optimistic rather than an implementable policy.

The cow screen does not justify a real replacement controller. [Instant-swap results](../results/fresh/larger_shift_20260923/cow_proxy/summary.json), [escape results](../results/fresh/larger_shift_20260923/cow_proxy/escape_summary.json), [script](../scripts/investigate_cow_swap_proxy.py).

## Holding strawberries until late

The price observation is partly right. Across the 198 available `mgt_m1` full-game replays, day-28 average **realized** strawberry sale prices exceeded day-24 prices in **110/167** games with sales on both days (median rise **7.49**). But day 29 was below day 27 in most games: only **61/169** increased (median change **−5.39**). A late release therefore targets day 28, not the final day.

The exact-engine screen reserved up to 6, 12, or 24 strawberries **at a time** from day 24, 25, 26, or 27; a shed-pressure guard lifted the reserve, and the held fruit was offered for sale at day 28 hour 1. Both recorded physical plans, the actual shops, and the opponent's orders remained fixed. The 198 games were split before results into 118 development and 80 untouched confirmation games, stratified by original win/loss. All **12** development arms had negative mean final margin; the frozen selection was **unchanged**. [Design](../results/fresh/larger_shift_20260923/strawberry/design.json), [summary](../results/fresh/larger_shift_20260923/strawberry/summary.json), [script](../scripts/investigate_strawberry_holds.py).

| Six-unit reserve | Development mean own cash | Development mean opponent cash | Development mean margin | Exploratory remaining-80 margin |
|---|---:|---:|---:|---:|
| Hold from day 24 | −59 | **+318** | **−377** | −275 |
| Hold from day 26 | −77 | **+107** | **−184** | −172 |
| Hold from day 27 | −81 | **+43** | **−124** | −118 |

Holding our fruit lets the opponent sell into a higher-priced market before our release. That opponent benefit is larger than our late-price gain in the broad policy screen. The remaining-80 figures are descriptive checks of rejected arms, not a second candidate selection.

These replays use fixed recorded opponent actions and shops. They capture the engine's price response to every changed transaction, but not an opponent that replans its farm after seeing ours. No `mgt_m1` source was changed. The sensible next sheep experiment would need a **pre-decision** estimate of rival future wool exposure plus a route-aware field choice, tested against responsive opponents; the observed late-game strawberry rise alone is not a basis for holding stock.
