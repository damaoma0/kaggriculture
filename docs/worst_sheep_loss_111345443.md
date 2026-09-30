# Worst outright sheep-expansion defeat: episode 111345443

Selection: among the high-Yarn games where the early-field sheep expansion changed actions **and made the outcome worse**, this had the lowest final margin. The unchanged `mgt_m1` tape lost to a roughly 2331-rated opponent (`Kitsune0o`) by **7,922** (102,084 vs 110,006). The larger-sheep candidate lost by **13,048** (93,937 vs 106,985), a further **5,126** margin loss. The largest *incremental* regression was episode 111890117 (−11,105), but that game still ended in a win; its mechanism is separately available in the trace. [Exact engine trace for this case](../results/fresh/larger_shift_20260923/sheep/worst_loss_trace_111345443.json), [trace script](../scripts/trace_worst_sheep_loss.py).

The original tape's visible symptom is a **volume deficit**, not poor sale timing: we sold 134 strawberries against the opponent's 245, 264 wool against 367, and 85 milk against 168. Our average realized prices were actually higher on all three products because we supplied fewer units. The final town had two Yarn Stores, a Brunch Spot and Ice Cream Shop for strawberries, and Pizza and Ice Cream shops for milk. Revenue from strawberries alone was **17,657** behind; wool was **12,476** behind. Other products and lower spending offset much of this, leaving the original 7,922 loss.

At day 12 hour 2, the candidate first diverged. It bought **four sheep**, placing them on three current wheat fields and one empty tile. The unchanged tape had 10 sheep and the opponent 11; wool quoted **233**. The expansion model valued the wool gain at **16,665** and projected **3,427** profit after its cost estimates. The baseline did not buy these sheep. The opponent then grew its flock to **17 sheep by day 15**, while the baseline tape grew to 13 and the candidate to 17. No further Yarn Store appeared. The estimator had kept current animal supply fixed and assumed some wool demand from future unknown shops, so it missed both the added supply and lack of matching demand.

Wool prices collapsed after the new flock began producing. At the start of day 22, the unchanged game's wool quote was **116** and the expanded game's **66**. On day 25 both were at the **1** price floor; on day 27 they were **37** and **18**. Across the season the expansion sold **47 more wool units**, but our wool revenue increased by only **145** because the added sales repriced both new and existing wool. Opponent wool revenue fell **3,341**—the competitive price effect is real, but too small to pay for this flock.

| Exact full-game change from four extra sheep | Cash effect |
|---|---:|
| Our wool revenue | +145 |
| Our other product revenue, net | −117 |
| **Our total revenue** | **+28** |
| Sheep purchases | −2,000 |
| Extra hired hands | −2,482 |
| Extra wheat purchases | −3,693 |
| **Our final cash** | **−8,147** |
| Opponent final cash, mainly lower wool prices | −3,021 |
| **Final competitive margin** | **−5,126** |

The changed plan also sold **24 fewer wheat** and **20 fewer carrot** units through the end of the game. There was no wool lost to overnight shed overflow in this case; the added wool reached market, but the market was saturated. That distinguishes it from the largest incremental regression, episode 111890117, where a larger flock also caused **24 additional wool units** to be discarded by the 100-item overnight shed cap.

The practical diagnosis is that a day-12 sheep purchase tries to fix a wool-volume gap **after** the attractive wool window. The model treats today’s high quote as durable, underestimates future rival and tape sheep, and does not adequately price the lost crop/feed chain. The opponent-price penalty helps our relative score, but here it does not offset the extra cash cost. A useful sheep change would need a forecast of total future flock supply and a way to preserve the tape’s wheat route; this case does not support simply raising the sheep cap or relaxing the purchase threshold.
