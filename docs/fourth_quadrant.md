# When does the fourth quadrant pay?

## Result

**Expansion is a production-and-labor decision, not a shop-count decision alone.** The strongest tested cases are ten tomatoes under heavy tomato demand, and six sheep with at least three yarn stores already visible at day 12. Two tomato shops did not justify the tomato investment. Three tomato shops and two yarn stores are boundary cases where current prices, demand history and the opponent's production matter.

V45 already has conditional tomato and sheep expansion programs. This research tested those programs directly, then built and tried a new crop-calendar scheduler. The new scheduler produced the expected harvests, but its separate extra crew was too expensive. **No new policy was promoted or submitted.**

## What was tested

- Baseline: `agents/v45_event_opening_fixed.py`, including the safe initial feed purchase and corrected forecast entry point.
- Two **adaptive source-code opponents**, public V45 and Two Coins, using the downloaded September 16 source snapshots. No recorded opponent action streams.
- Discovery: **160 games** = ten deliberately chosen shop sequences × both seats × two opponents × four policies.
- Fresh confirmation: **96 games**, using eight new mixed-shop prefixes/seeds around the two/three tomato-shop and two/three yarn-store boundaries, both seats and both opponents.
- Eight initial smoke games, **32 standalone physical crop-plan checks**, and **12 retained integrated calendar trials**.
- Policies: no fourth quadrant; native V45 eligibility; force the tomato economic eligibility; force the sheep economic eligibility. Forced variants retain structural compatibility, cash, input-capacity and worker-index guards. Each forced variant disables the other expansion family, so the comparison is between complete investment programs.
- Controlled shop streams are identical within a pair and hidden until the engine reveals them. Later shops are drawn independently of the policy. Changed farms can still change weed draws.

The grid intentionally overrepresents rare configurations such as six tomato-consuming shops. It is **not** an estimate of average ladder benefit. Each discovery cell has one seed, two opponents and both seats; seat-swapped games are not independent worlds. Confirmation has two independently drawn mixed prefixes per boundary class. This is an initial conditional map, not a universal profitability guarantee.

## Existing V45 investments

**Tomatoes:** commit on zero-based day 18, buy the fourth quadrant and ten tomato seeds, then hire dedicated workers for planting, watering, fertilizer and harvest. Full successful fertilized production in these tests is **80 tomatoes**, delivered during days 26–29. The native gate requires at least three Pizza Shop/Farmers Market instances, tomato price at least 70, cash at least 12,000 and route compatibility. The market requests retain further budget guards.

**Sheep:** commit on day 12, buy land and six sheep, then supply feed and two additional workers daily. The native gate requires at least two Yarn Stores, wool price at least 220, wheat price at most 45 and route compatibility, followed by cash/capacity guards. This is an earlier commitment that can foreclose a later tomato investment on the same quadrant.

These use only ten or six tiles of the extra 25. Their results do not determine the value of every possible full-quadrant layout or expansion date.

## Discovery: incremental results versus staying at three quadrants

Numbers are mean full-season changes across four paired games per row. “Margin” means our final cash minus the opponent's final cash. Counts refer to shops revealed at the investment decision; tomato shops are Pizza Shop or Farmers Market, and duplicate shops count independently.

| Investment and shop configuration | Our cash change | Winning-margin change |
|---|---:|---:|
| Tomatoes, no tomato shops | -4,832 | -5,071 |
| Tomatoes, one tomato shop | -3,115 | -3,123 |
| Tomatoes, two tomato shops | -2,455 | -2,282 |
| Tomatoes, three tomato shops | +1,391 | +4,927 |
| Tomatoes, four tomato shops | **+18,884** | **+26,592** |
| Tomatoes, six tomato shops | **+60,212** | **+73,152** |
| Sheep, one Yarn Store | -15,388 | -11,242 |
| Sheep, two Yarn Stores | +596 | +8,714 |
| Sheep, four Yarn Stores by day 18, three already at day 12 | **+9,109** | **+9,628** |

Forcing the wrong product was expensive: sheep under tomato-heavy sequences generally lost about 16,000 of our cash, while tomatoes under wool/carrot-oriented sequences generally lost 3,400–5,200.

The tomato price curve steepens sharply after market inventory becomes sufficiently scarce. That is why the high-demand cases are much more valuable than a linear shop-count extrapolation suggests. In the six-tomato-shop cell, the current tomato price at investment was 132, while realized average sale prices were approximately 868–878. Conversely, two-shop cases began around 73 and sold around 85, insufficient to cover the complete plan.

The very large high-demand gains require wider confirmation before any frequency-weighted performance claim. They do establish that an unconditional three-quadrant cap can discard a valuable opportunity.

## Fresh confirmation: the boundary is conditional

Each row has a different new mixed-shop prefix, two opponents and both seats. These are forced-plan results; the native gate is discussed below.

| Prefix class | Our cash change | Margin change | Positive margin pairs |
|---|---:|---:|---:|
| Two tomato shops, prefix A | -2,285 | -2,552 | 0/4 |
| Two tomato shops, prefix B | -1,440 | -1,634 | 0/4 |
| Three tomato shops, prefix A | -1,244 | **+1,129** | 4/4 |
| Three tomato shops, prefix B | -1,508 | -1,634 | 0/4 |
| Two yarn stores, prefix A | **-11,860** | **+4,346** | 4/4 |
| Two yarn stores, prefix B | **-11,682** | **+4,257** | 4/4 |
| Three yarn stores, prefix A | **+7,972** | **+9,366** | 4/4 |
| Three yarn stores, prefix B | **+9,212** | **+9,616** | 4/4 |

### Why three tomato shops are not enough by themselves

Prefix A reveals Farmers Market early, followed later by Pizza Shop and another Farmers Market. At day 18 tomatoes cost **75**. Prefix B reveals three Pizza Shops only at days 12, 15 and 18, after Pet Cafe, Ice Cream Shop and Brunch Spot; tomatoes cost only **69** at the investment decision.

Both have three tomato shops at day 18, but their accumulated demand and market state differ. V45's existing price gate rejects the losing 69-price investment. In the 75-price case it accepts: own cash falls modestly, but the opponent's income falls more, improving margin. This supports retaining the price test rather than replacing it with a pure shop-count rule.

### Why two yarn stores can help competition while hurting our cash

The extra sheep add wool supply to a shared market. In both fresh two-store prefixes the expansion reduces our final cash by approximately 11,700–11,900, but reduces the opponent's cash even more. The margin improves by about 4,300.

That is not a profitable standalone farm investment. It is a beneficial interaction against these tested opponents. We should not assume it remains beneficial against an opponent with little wool exposure. A useful expansion evaluator needs both expected own net return and the estimated effect on the opponent's production revenue.

## First crop-plan evaluator: implemented and physically checked

`scripts/crop_plan_evaluator.py` now constructs explicit per-day crop programs for wheat, carrots, tomatoes and strawberries, with or without fertilizer, starting on day 12 or 18. It uses the official engine for planting, watering, fertilizer effects, crop maturity, harvest, decay and replanting.

For a ten-tile SE block it partitions the work into contiguous worker tours, accounting for:

- All legal shed-adjacent spawn locations, using the worst distance.
- Travel, fertilizer pickup, crop actions, harvest return and drop.
- Limited time after native hiring and the shortened final day ending at turn 718.
- Seed purchases, fertilizer opportunity/purchase cost, 4,000 land cost and **marginal Fibonacci hire costs**, rather than an average wage.

All **32 model plans** were physically executed with the official engine and matched their planned harvested-and-delivered output. These checks assume reserved inputs and shed capacity, no conflicting native jobs, and the specified daily release time. They establish physical feasibility under those assumptions, not profitability in a full match.

The evaluator also accepts baseline inventory forecasts for each delivery day and prices the additional crop sales and fertilizer purchases along the official market curves. Forecast accuracy is a separate issue; the evaluator does not know future shops.

### Example break-even prices

Ten fertilized plots starting on day 18, workers released with 20 available actions per normal day, fertilizer valued at 50/unit. These are model sensitivities with a constant existing daily crew, not the exact costs of V45's specialized routes.

| Crop | Seasonal units delivered | Break-even sale price, 8 existing hands | Break-even sale price, 10 existing hands |
|---|---:|---:|---:|
| Wheat | 170 | 46.4 | 66.3 |
| Carrots | 150 | 64.9 | 96.5 |
| Tomatoes | 80 | 87.2 | 117.2 |
| Strawberries | 20 | 328.4 | 414.8 |

Strawberries planted this late have very little remaining production time. The worker-count sensitivity is large because each additional hire costs more than the previous one. These prices include land, seeds, inputs and workers, but do not assign a value to alternative uses of existing workers or land.

## Integrated trial: separate extra crews are too expensive

Built a research adapter that executes the new calendars alongside V45's existing farm. It buys land, seeds and fertilizer, waits for native early hiring to finish, preserves native worker indices, hires the added crew, executes the tours and sells only the new workers' deposited output. It protects the final-turn delivery deadline and disables incompatible native terminal planning after commitment.

Twelve retained full-game trials, both seats and both active opponents, use discovery configurations with matching no-expansion controls. These are exploratory, not held-out selection tests.

| New calendar | Confirmed new harvest | Mean extra hire spending | Our cash change | Margin change |
|---|---:|---:|---:|---:|
| Wheat, no tomato-demand configuration | 170 | 10,230 | -9,585 | -9,408 |
| Carrots, Pet Cafe-heavy configuration | 150 | 13,846 | -12,331 | -6,829 |
| Tomatoes, three tomato shops | 80 | 6,498 | -479 | +2,774 |

All twelve produced the planned harvests, with no missing hires, budget declines or infeasible-calendar events in the retained adapter version. Each returned an action throughout the episode and reconciled terminal cash to the ledger.

The generic tomato calendar still loses to the native tomato plan on the same cell: native gives +1,391 own cash and +4,927 margin. The new one schedules more paid workers. For wheat and carrots, synchronized harvest/replant/water days cause especially expensive staffing peaks. Earlier release reduced these costs substantially during debugging, but did not make the calendars attractive.

**This rejects the naive approach of putting a separately staffed profitable-looking crop block on top of V45.** It does not reject adaptive crop choice. The next version must share and reschedule the existing workforce, or stagger crop cohorts to avoid peak hiring, before considering another land purchase. Merely counting currently idle commands is insufficient; those workers must be able to reach and service the new plots at the required times.

## Practical policy conclusion

For the tested native programs:

1. **Tomatoes:** reject zero–two relevant shops at day 18; treat three as conditional on price, demand history, workforce and rival supply; four or more are strong candidates in the tested configurations.
2. **Sheep:** reject one yarn store; two requires an explicit competitive-value assessment; three already visible at day 12 is a strong candidate, subject to affordable feed and service.
3. **Other configurations:** no general fourth-quadrant recommendation yet. The tested new wheat/carrot programs do not pay for their extra crew, even when their products have demand.
4. Retain the current native eligibility rules and the safe opening. No evidence here justifies promoting the generic scheduler or imposing a universal land cap.

A useful future gate is therefore: **expected delivered crop/animal value, including market impact and rival exposure, minus land, inputs and the cheapest feasible incremental worker schedule**. Shop count is one input to that calculation.

## Artifacts and reproducibility

- `scripts/research_fourth_quadrant.py`: discovery interventions and active-opponent games.
- `scripts/confirm_fourth_quadrant.py`: new mixed-prefix confirmation panel.
- `scripts/crop_plan_evaluator.py`: crop calendars, tour partitioning, physical validation and market-value interface.
- `scripts/trial_calendar_expansion.py`: research adapter for the generated calendars; not a standalone submission.
- `scripts/report_fourth_quadrant.py` and `scripts/finalize_fourth_quadrant.py`: paired summaries and retained-case checks.
- `results/fresh/fourth_quadrant/`: manifests, per-game ledgers, decision observations, telemetry, crop plans and summary files.

Retained mechanism runs: **264 including smoke tests**, plus **12 final calendar trials**. Debug calendar versions are not included in reported results; retained files identify adapter version 3. Final source hashes are in `final_summary.json`. Native expansion telemetry reports no lost plants, hire shortfalls or execution errors; forecast errors are zero. Maximum measured agent call in the mechanism panel was approximately **0.282 seconds**.

No agent baseline or Kaggle submission was changed.
