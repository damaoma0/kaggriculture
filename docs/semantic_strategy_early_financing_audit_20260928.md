# Early semantic-plan financing audit

This is a read-only source and development-record audit. No policy, executor or game was changed or run for this audit. The proposed exception below has not been tested for profit.

The bounded financing exception is preferable to an unconditional early sell-now policy: it addresses a specific mismatch between the semantic policy's same-day income credit and the executor's delayed monetization, then restores the existing seller once the remaining commitments are funded. Temporarily removing all four goods from the paced set is only a coarse implementation of that exception; it can sell substantially more than the actual shortfall and bypass the paced seller's price-floor protection.

## Verified failure mechanism

The pooled pace table was learned from steps 264–717, days 11 onward: `scripts/dsm_sell_pace.py:31`, `:38`, `:48`. Both data collection and the fitting loop exclude the opening. The table loaded by this mission has SHA256 `6d46c142b09e8b0b2a34ef011e1020e37005a0a6c35b40ad2ca7cbabf42d8294`; its provenance is `results/fresh/semantic_strategy_20260928/pace_training_provenance.json`.

The frozen executor nevertheless labels every day through 17 as the same early phase. Its preceding-rival-day set excludes days before 11, so D6–10 always uses the no-recent-rival bucket (`results/fresh/semantic_strategy_20260928/runtime/agents/mgt_lead_kb115lt.py:3824`). Thus the early seller extrapolates a later, more established-farm selling schedule into capital-constrained expansion days.

There are two separate ordering effects in `_market`:

1. Paced goods skip ordinary selling (`:3444–3448`). The purchase budget is computed from current cash plus ordinary sells (`:3546`), before paced sales are constructed. Land, animal and seed orders (`:3607–3667`) therefore cannot normally use the proceeds of paced sales in that same action. They wait until the next observation reflects cash.
2. Existing hire-funding sales (`:3559–3572`) and optional seed-funding sales (`:3642–3657`) may credit proceeds internally, but the later books block removes **all** preceding SELL orders for paced goods (`:3806`) and substitutes its own paced quantities (`:3838–3840`). A funding sale can therefore be reduced after its proceeds have already been used to budget purchases or hires. Merely enabling `seed_fund` does not reliably override this replacement.

The mission recipe has `sd_clean=1`, `sd_books_source=pace`, and paced WOOL/MILK/EGG/FERTILIZER as well as crop goods. If a product is temporarily removed from `sd_books_sell`, the ordinary seller uses its available shed quantity (`:3464–3465`), its proceeds enter the earlier purchase budget, and the books block no longer deletes its funding sale. This establishes the proposed intervention's mechanism without establishing its competitive benefit.

## Development evidence

Raw source: `results/fresh/semantic_strategy_20260928/runs/smoke_v1/development/live/live-01.json`, associated `.actions.json`, and the same paths under `strategy_v2_nearest`. Both versions have the following D6 observations:

| Quantity | D6 |
|---|---:|
| Starting cash | 729 |
| Proposed capital cost | 5,030 |
| Proposed new animals | 6 sheep, 2 cows |
| Proposed crops | 2 strawberries, 3 wheat |
| Proposed land | 1 quadrant |
| Wool harvested | 18 |
| Wool sold | 10 |
| Fertilizer collected | 5 |
| Fertilizer sold | 0 |
| Actual animal purchases | 3 sheep |
| Ending cash | 8 |

Requested D6 wool sales occur at hours 4/5/10/14/21 with quantities 3/4/1/1/1. The recorded first wool harvest is fully removed from the sheep tiles by D7. The accounting shows eight units harvested but not sold during D6; the daily artifact does not separately identify their end-of-day split between hands and shed. Accordingly, **do not claim all eight were immediately sellable at every earlier hour**. Delayed delivery and land execution are separate contributing constraints.

The later land-unlock development version `strategy_v2_unlock` harvested the same 18 wool but sold 15, collected five fertilizer and sold one on D6; it ended with 98 cash. Improved delivery and execution already reduce part of this symptom. This is another reason to test the financing exception against that corrected version, not to attribute the entire earlier gap to pacing.

## Recommended bounded rule

Enable only during D6–10, while actual cash is below the remaining cost of today's admitted and still feasible commitments. Recompute the shortfall from observed completion, not the original daily `estimated_capital_cost`:

- Remaining planted-tile jobs minus owned seed stock; count only seeds still needed today.
- Remaining animal placements minus matching animals already in the shed or hands. Do not charge again for purchased animals awaiting placement.
- Land cost only while the planned quadrant remains locked, and remaining hires plus necessary feed should remain funded first.
- Subtract current cash and any already admitted same-action funding proceeds once. Do not count undelivered or unharvested output as immediately spendable cash.

The narrowest implementation releases only the additional units of WOOL/MILK/EGG/FERTILIZER needed to cover that shortfall. The existing seller's nonlinear per-unit price walk, minimum price and ten-order handling should remain in force. If the practical first implementation temporarily removes products from `sd_books_sell`, select the smallest sufficient subset and cap its released quantities; removing all four permits over-selling even for a one-coin shortfall. Preserve wheat feed reserves/pacing. Restore ordinary pacing as soon as the observed commitments are funded or completed, and unconditionally after D10.

Care is needed with fertilizer: this recipe explicitly sets `sd_fert_sell=1`, so it currently keeps no shed fertilizer reserve, but that should not be generalized to configurations that require shed fertilizer for pending jobs. Removing a product from books also removes that product from `sd_books_walk` protection (`:3939`); a separate safe quantity cap is needed if using the coarse set-removal approach.

For evaluation, record each activated hour, remaining cost by category, observed cash and sellable stock, products released, actual extra sales, purchases completed and elapsed delay to planting/placement. Compare against the corrected land-unlock baseline on the development panel. Preserve both final margin and units: extra funding may advance productive investments but can also fund an overlarge herd or lower the rival's input/output prices. No strength claim follows from this source audit.

## Optional implementation prepared after this audit

`scripts/semantic_strategy_financing_20260928.py` now implements an off-by-default
exception, integrated immediately before the frozen executor call. It checks
today's unfinished jobs against current own cash, seed stock, animals already
bought, live occupied pens, and land/worker/feed requirements. It considers only
goods already delivered to the shed. Each candidate whole lot must pass the
executor's price-walk floor check; wheat is never released by this helper.

Among at most four eligible product lots, it chooses the subset with the smallest
estimated excess over the shortfall. It restores the base paced-product list on
every later call and unconditionally outside D6–10. Whole-lot sales may exceed
the immediate need, and 85% of current quoted value is an estimate rather than
an exact proceeds calculation. These limitations are logged in each activation.
The helper does not edit orders or the KB115LT source.

Nine focused tests cover stock already bought, completed/remapped jobs, blocked
pens, price-floor rejection, no wheat release, restoration, and input isolation.
The full semantic-strategy suite passes 65 tests. Frozen
`strategy_v4_modern4_finance` is the prepared single-change ablation against
`strategy_v3_modern4`; no financing-arm games have run yet.
