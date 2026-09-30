# Episode 111345443: full audit of the unchanged mgt_m1 tape

This is the original mgt_m1 game against Kitsune0o (about 2331 rating), not the four-extra-sheep experiment. Exact recorded-action replay reproduces **102,084 vs 110,006**, a **7,922 loss**. The final margin is a **24,650 revenue deficit**, partly offset by **16,728 less spending**. The [machine-readable audit](../results/fresh/all_umg_m1/diagnosis/111345443_deep.json) and [reproduction script](../scripts/audit_111345443_tape.py) use the native engine and preserve the original submitted agent.

## When the game turned

| Start of day | Our cash | Rival cash | Margin |
|---:|---:|---:|---:|
| 12 | 13,604 | 13,353 | +251 |
| 15 | 22,960 | 14,535 | +8,425 |
| 18 | 39,289 | 36,251 | +3,038 |
| 21 | 60,563 | 64,501 | −3,938 |
| 24 | 75,332 | 82,790 | −7,458 |
| Final | 102,084 | 110,006 | −7,922 |

From days 15–23, our revenue was **21,193 lower**. Spending **5,310 less** softened the damage, but the margin fell **15,883**. Strawberry revenue accounted for **12,947** of the revenue gap in that window, wool for **9,849**. These are observed accounting gaps, not the profit a new plan would necessarily earn: extra supply would change both players' prices.

## The largest error: too few berries, and weak yields on those planted

The third shop, revealed on day 9, was **Brunch Spot**, adding strawberry demand to the starting Farmers Market. On day 11 the opponent planted **13** new strawberry plots; mgt_m1 planted **4** that day and **2** on day 12. Across the whole game it planted **24** berries versus **33**. At the start of day 12 it had **14 empty unlocked tiles**, so the immediate shortfall was not a hard space limit. It had 13,333 cash at the start of day 11.

The opponent harvested **248 berries from 33 plots** (**7.52 per plot**); mgt_m1 harvested **138 from 24** (**5.75 per plot**). The game permits at most eight from one strawberry crop. Our first four day-5 plants averaged 7.5, but the eight day-6 plants averaged 5.5 and the four day-11 plants produced only 4 each. The opponent's thirteen day-11 plants averaged 7.77. Thus the 110-unit harvest difference comes from both missing plots and lower yield per existing plot. Sales were **134 vs 245** for **23,640 vs 41,297** revenue. Our average sale price was higher (**176 vs 169**), which rules out cheap selling as the main symptom.

Fertilizer allocation is the strongest visible explanation for the yield gap. We made **159 successful crop fertilizations**, but only **26** were on strawberries; **78** went to wheat, **37** to carrot, **16** to tomato and **2** to melon. The opponent made only **84** fertilizations in total, with **60** on strawberries. Successful strawberry watering per planted plot was similar, so basic watering does not explain the gap. A timed fertilizer application can cover several days and raise berry yield; the current trace does not assign an exact cash value to reallocating it.

The fall from **24 live strawberry plots on day 21 to 9 on day 24** looks alarming, but the early cohorts were dug at or after their fourth production cycle, as were the opponent's. The late volume gap was created earlier, mainly by the small day-11 cohort; it was not primarily premature digging. Holding existing berries for the final days is also unattractive in this particular game: the opening strawberry quote fell from **213 on day 15** to **147 on day 24** and **112 on day 29**.

## Why the route did not correct itself

At day 12 the selected donor was UMG episode **110141763**. Its first four shops were **Farmers Market, Yarn Store, Bakery, Yarn Store**. The actual four were **Farmers Market, Yarn Store, Brunch Spot, Yarn Store**. The Bakery/Brunch swap matters because Brunch adds strawberry demand while both use eggs and wheat. Later, the donor expected **Bakery, Pet Cafe** where the actual town got **Pizza Shop, Ice Cream Shop**. That introduced milk and more strawberry demand in the real game, but the donor's late plan anticipated carrot demand from Pet Cafe.

The 584-tape library did contain one donor with the exact first three shops, but its board differed on **12 tiles** at day 9, above the router's eight-tile switch limit. No donor had the exact first four shops. By day 15, after the chosen production plan shaped our board, **only the current donor** met the switch limit. This is a coverage and lock-in problem: the route could recognize the worsening demand score but could not switch to a compatible better plan. The selected donor's production pattern was followed closely: around day 15 it had 23 strawberry plots, 13 sheep, 4 cows and 2 geese; our board had 24, 13, 4 and 2.

The donor's total final strawberry shop count happened to equal the actual town's count, but its second and third strawberry shops came **much later**. Timing matters for a crop with a 10-day wait to first yield. Its donor town had **no milk shop** and **three carrot shops**, while the actual town had **two milk shops** and **one carrot shop**.

## Capital, animals and the other products

The opponent bought the fourth land block for **4,000 on day 12**; mgt_m1 never did. By day 15 our three-block board had only **five empty unlocked tiles**, whereas the opponent's four-block board could keep more strawberries, sheep, cows and wheat at once. The opponent also bought **21 more worker-days** overall and spent **3,995 more** on them. This helps explain why simply adding four sheep to the existing three-block layout failed in the prior experiment: that change displaced wheat and required extra workers and feed. In an exact full replay it worsened the competitive margin by **5,126**. It does not prove that sheep are bad when supported by more land and feed.

The opponent grew to **17 sheep by day 15** versus our **13**. Wool sales were **264 vs 367** and revenue **39,548 vs 52,024**. The valuable part of that gap came before the crash: on days 15–23 wool revenue was **9,849 lower**. The late gap is less persuasive as an investment opportunity because the wool opening quote fell from **234 on day 15** to **24 on day 24** and sometimes hit the one-unit floor. Several of our sheep stopped receiving feed and escaped on days 24–29; those late retirements may be sensible, while the smaller flock during the earlier high-price window deserves testing.

The opponent kept six or seven cows against our peak of four, then two after escapes on days **20 and 23**. Milk revenue was **5,494 vs 10,248**, with **3,909** of the gap on days 24–29. Yet milk was at the one-unit price floor on day 15 and only **7** on day 18; it recovered to **74** on day 27. The late milk gap suggests the donor's no-milk-shop feed-termination calendar was stale, but more cows or later feeding could cost more than they earn. This needs a full-game counterfactual.

The supposed excesses are mixed. We sold **199 carrots vs 81** at an average of only **39**, consistent with the donor's Pet Cafe expectation failing to appear. But that still made **5,027 more carrot revenue**; its opportunity cost in land and worker time is unmeasured. Tomatoes made **4,953** revenue and match the actual Pizza Shop. Eggs made **3,576**, and the actual Brunch Spot plus two Bakeries wanted them, so the geese are not obviously a mistake. Our wheat harvest was almost the same as the opponent's (**560 vs 564**); buying **99 vs 265** wheat units saved about **7,001** in direct wheat purchases, though it also meant supporting a smaller herd. These strengths offset much of the berry and wool loss.

## Execution noise

The tape issued **107 farm commands with no physical effect** among **3,006** attempted plant, harvest, water, care, feed, fertilize, fertilizer-collect and dig commands (**3.6%**). The opponent had **20 among 3,307** (**0.6%**). Our wasted commands included **31 water, 19 harvest, 15 feed and 14 fertilize** attempts; **76** of the 107 came on days 18–29. This is a genuine replay efficiency problem, but the difference of 87 wasted commands is smaller than the large crop and animal production gaps. Neither side had failed hire requests, and this audit found no berry or wool shed loss large enough to explain the result.

The first controlled change worth testing is a **day-9/11 strawberry expansion plus targeted strawberry fertilization**, with a separate fourth-land decision if the enlarged orchard later crowds out wheat or animals. Test it against this fixed opponent and a wider panel, measuring both players' final cash and milk/wool/berry price effects. A second isolated test can delay feed termination for the two cows, conditional on milk-shop demand and the observed price recovery. Keep the previous four-sheep-only loss as a guardrail against treating a product revenue gap as a profitable purchase instruction.
