# Most likely causes of mgt_m1 losses

The strongest diagnosis is insufficient adaptation of the production plan and its servicing calendar to actual demand. It explains both scarce products we produce too little of and glutted products we continue servicing. The diagnosis is based on all 89 audited losses, with emphasis on 58 against pre-match ratings below 2500. Counts describe this losing cohort, not how predictive each feature is among all matches.

## 1. Capacity follows a neighbouring world's plan

Wool or strawberry is the largest direct cash deficit in 46/58 losses below 2500. In all 27 wool cases we bought fewer sheep than the opponent. In all 19 strawberry cases we made fewer successful strawberry plantings: 18–31 versus 33. These are season totals, not counts of simultaneous mature plants. This supports a capacity/production-history explanation before assuming poor selling.

The active router scores weighted revealed shop-demand differences at historical checkpoints, plus tile-label differences and animal-stranding penalties. It does not score expected remaining harvests, crop/animal age, current prices or the opponent's supply. Its future-demand weight is zero. A new tape with more than eight mismatched tile labels is excluded; the current tape is exempt. This makes the choice strongly dependent on earlier investments. It can keep executing a good plan for the donor's market after the actual market diverges.

Source: [router scoring](../agents/mgt_m1.py#L1026), [eligibility and compatibility](../agents/mgt_m1.py#L1048). Price/opponent awareness does exist in the sheep overlay; the statement above concerns the main router.

Example: episode 111262874, seed 1190520739, lost 12,585 to a 2025.6 opponent. The last switch was D6. Actual demand ended with three Ice Cream Shops and one Yarn Store, versus one and two in the donor. We planted 24 strawberries versus 33 and harvested 141 versus 249, while 151/283 harvested wool units arrived at a marginal quote at or below 50. Our average strawberry sale price was actually higher (192.6 versus 188.0). The observed decisions fit a plan allocating too little capacity to strawberries and too much effort to wool for that world.

The older 86-game, 430-checkpoint best-fit audit found a 38.9% reduction in shop-history mismatch without asset constraints, but only 0.6% when aggregate asset-count distance could not worsen. That is a fit-score comparison, not a profit estimate. It argues for feasible production changes rather than simply removing the tile limit. See [best-fit study](production_plan_best_fit.md).

## 2. The sheep correction rarely reaches the missing capacity, and servicing remains insufficient

The overlay added sheep in **0/27** wool-deficit losses. In 12, every daily evaluation returned before economic sizing because the target deficit was below two. The other 15 had profit rejections; 3 also had cash rejections. None had a recorded tile rejection. Across the 378 evaluations, 288 stopped at the deficit gate, 78 had a negative best modeled profit, and four had a nonnegative best modeled profit below 3,000. Thus the 3,000 threshold alone is not the main gate.

The target adds 10, 9, 4, 2 or 2 sheep for Yarn Stores revealed on D3, D6, D9, D12 or D15, respectively; D18/D21/D24 add zero. Expansion ends after D19. Expected future additions from the donor count against today's deficit, and the one-sheep deficit is ignored. Twenty-two of these 27 losses include a Yarn Store from D18 onward. These rules are confirmed limitations; it is not established that late purchases would have paid in every affected game. The profitability model uses animal counts to estimate supply and a sheep-count model for additional labor, so it also merits calibration against executable shared routes.

Source: [active configuration and lookup](../agents/mgt_m1.py#L1217), [decision gates](../agents/mgt_m1.py#L1956). There is no equivalent active strawberry-capacity overlay.

Independent recorded-action replays of all 27 wool cases show that, after the first Yarn Store was revealed, our sheep received feed on **77.4%** of sheep-days versus **92.3%** for opponents. Both feed and care occurred on **63.7% versus 91.7%**. Rates are weighted by observed sheep-days, including season wind-down. All replays reproduce both recorded final cash values. This identifies a servicing difference as well as fewer animals; it does not value each skipped service as a profitable missed action.

Episode 111743130, seed 1439155522, is especially clear: five sheep bought versus six, but only 71 wool harvested versus 155. Our D15 target was six against five owned/planned, so the overlay declined before profit evaluation on every remaining eligible day. Existing sheep also received sparse care. The engine generated 80 wool for us, nine of which remained on animals when they escaped, compared with 155 generated and harvested by the opponent. The cash deficit in wool was 11,773 after sheep-purchase costs.

Full-season sheep yields across these 27 cases were 2,906 generated / 2,839 harvested for m1 versus 4,569 / 4,569 for opponents. Our 64 unharvested units on escaping animals explain most of the generation-to-harvest difference; the much larger difference is already present in generated output. Total escape counts should not be interpreted as mistakes: many are planned season-end exits.

## 3. Servicing and retirement do not fully respond to gluts

Nineteen of 58 losses below 2500 meet the low-price production screen; 13 include milk. The screen means at least 20 units and at least half our harvested product arrive while the marginal quote is no more than one-quarter of base. It flags candidates for economic review, not proven negative-profit enterprises.

The tape's base feeding and retirement calendar remains active. A price-aware culling function exists but is disabled; its source explicitly records a negative prior test. Top-ups can add care but do not generally redesign the donor's base work. Episode 111678108 combines only 90 wool harvested versus 155 with 69/116 milk harvested at quotes at or below 40. That is consistent with misallocated maintenance as demand changes.

Source: [top-up logic](../agents/mgt_m1.py#L1567), [disabled culling](../agents/mgt_m1.py#L1794). Merely enabling culling or stopping low-price sales is not an established fix: saved feed, fertilizer byproducts, genuinely removable labor, future prices and effects on the opponent all matter.

## 4. Extra labor magnifies some losses

The largest overall loss, episode 112109339 against a 2633.8 opponent, includes 12,363 extra wages (16,668 versus 4,305). Its sheep overlay added eight sheep on D11 and used 53 hand-days. It also sold wool at a lower average price and discarded 25 harvested wool units. The extra wages are an exact accounting contribution; the amount attributable to the overlay alone has not been isolated.

Across all 58 losses below 2500, aggregate extra wages were only 15,671 against a combined margin of -306,469. Labor is a serious case-specific problem but a weaker general explanation than output mix and servicing.

## Explanations with less support

- The old missing-worker hiring failure: zero failed in-limit HIRE requests in all 89 audited losses.
- Crashes or fallback behavior: the archived agent reproduces every recorded action in all 89 games.
- Primarily bad selling prices: wool's quantity component below 2500 is −335,291, offset by a positive 8,185 price component. Strawberry's −311,959 gross-revenue gap decomposes into −257,181 quantity and −54,778 price. These accounting components are not achievable gains.
- Simply choosing a geometrically looser tape or maintaining everything: prior continuation and maintenance changes did not improve their development seeds. See [continuation results](continuation_execution_and_recovery.md).

## Priority for the next policy experiment

First compare remaining-season value of servicing the animals and roots already present, with correct production dates and executable labor. Then adjust strawberry replacement cohorts and sheep capacity early enough to pay back. Rank candidate production plans by their feasible incremental net value, including shared-market response, rather than treating shop similarity as value. Protect profitable crop replacement when changing the work schedule. These are priorities for a controlled test on wins and losses; this diagnosis does not assert a recoverable cash amount or a win-rate improvement.

Reproduction: run scripts/diagnose_m1_failures.py with --wool-under2500, then node scripts/summarize_m1_failure_diagnosis.mjs. Four detailed representative games can also be regenerated by running the Python script with no arguments. Exact action/ledger evidence is in [the full audit](all_umg_m1_audit.md). Derived metrics are in results/fresh/all_umg_m1/diagnosis_summary.json; animal-day records are in its diagnosis/ directory. Active/archived source SHA-256: 1152ef2e12c4535dbc381b9c54ac7d7a0b1a9ad3d0a8018a7567dcf5c4a52470.
