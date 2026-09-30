# Execution and service audit after land unlocking

The fixed-shop development comparison confirms that observed-unlock dispatch addresses a major omission, while early investment timing and animal servicing remain incomplete. These eight worlds are development evidence. No qualification results were read. The aggregate audit uses saved outcomes; the later diagnosis below adds two authorized recorded-action reconstructions and two one-day component continuations, with no live opponent calls.

The paired A/B means are −7,141.875 versus −4,078.25 margin: +3,063.625 for B. Own cash changes −105.625 per game and rival cash changes −3,169.25. Thus this is a competitive-margin improvement dominated by responsive-opponent price effects, not an isolated own-profit production gain. Natural B remains separate: mean margin −5,201.625.

## What remains incomplete

| Fixed B day | Crops placed / requested | Animals placed / requested | Animals successfully bought | Animals still in inventory next dawn |
|---|---:|---:|---:|---:|
| 6 | 73 / 93 | 22 / 59 | 36 | 14 |
| 7 | 44 / 45 | 22 / 27 | 9 | 1 |
| 8 | 10 / 10 | 13 / 29 | 19 | 7 |
| 9 | 41 / 150 | 11 / 47 | 19 | 15 |
| 10 | 120 / 142 | 29 / 41 | 27 | 13 |
| 11 | 112 / 112 | 25 / 30 | 19 | 7 |

Daily requested animals can repeat an unfulfilled earlier intention; these counts are not independent lifetime investments. Successful purchases are calculated from the ledger's fixed animal costs, not requested market orders. The stock balances account for all observed placements from day 0.

Fixed B executes 1,241/1,243 crop requests on days 11–28. There are no hire shortfalls or recorded dispatcher exceptions in either fixed arm, and physical no-effect commands are rare. This points to early timing and specific service omissions, rather than a general inability to execute crop placement.

## Expansion financing and time

All eight D6 land purchases are observed at H6; their BUY_LAND requests are at H5. The dawn shed contains none of the proposed financing products (wool, milk, eggs or fertilizer) in all eight. Advancing these purchases requires earlier collection/delivery or another funding source; releasing a morning stock cannot do it.

On D9, four of eight intended land purchases fail. Successful unlocks are observed at H6, H9, H11 and H15. The four deferred purchases unlock at D10 H12. Across 20 expansion intentions, static liquidation of actual dawn financing-product stock above the exact market-curve floor of 5 would fund land plus the requested hires in 7 cases. It funds all admitted land, seeds and animals in zero cases, even excluding feed. These are dawn liquidity bounds; they do not assume unharvested or carried goods are already saleable.

There are 462 PASS commands among 2,570 issued worker commands after successful expansion unlocks. This is aggregate slack, not proof that a particular missed route was feasible. Fourteen purchased animals remain in inventory after D6 (seven cows and seven sheep), so lack of purchasing cash alone cannot explain all missing placements. Requests for additional animals frequently appear at H18–23, and seeds at H22–23; request times do not establish successful purchase times. Hourly private-state logging or a recorded-action replay is needed to separate late delivery from an abandoned or blocked route.

## Retirement versus unintended survival loss

Fixed B has 82 exits matched to explicit retirement intentions (69 on the intended night and 13 one night early). It also has 24 exits without a matching recorded retirement, while the same-day end-board still retains those animals. Seven of the 24 have no possible remaining production before the season ends; skipping their feed may be economically intentional and is not classified as a productive loss.

The other 17 have at least one remaining production date; 11 disappear before their first production. Every unmatched exit starts the day with one unfed night and positive wheat in own inventory, and its day includes PASS commands. This establishes a conflict between the recorded retention target and physical execution; it does not establish the counterfactual profit cost or guarantee feed was in the right worker's inventory at the right time.

Among surviving animals the same-day plan retains, 95 production nights are unfed, wiping 92 already-banked bonus units. Some isolated skipped feeds can be sound decisions. The stronger repair target is preventing a second skipped night for an animal that remains explicitly committed and still has a worthwhile production future. Natural B similarly has 19 unmatched exits with remaining production, including eight before first production, plus two young ongoing-crop losses.

The frozen KB already adds mandatory FEED for hungry animals with remaining production (`mgt_lead_kb115lt.py`, lines 9837–9861, `sd_keep_alive_guard_min=1`). Adding another broad keep-alive switch would not identify the failure. Exact shadow reconstruction below establishes a partial-pickup routing failure in two early cases. Other unmatched exits have not been individually reconstructed, so this cause should not be assigned to all 17.

## Exact reconstruction and bounded recovery

Both original action streams were replayed under their fixed shops. Whole-game cash and both ledgers reproduce exactly; all 30 saved dawn observations match own farm, private inventory, market and shops. The frozen candidate was also called from step zero in shadow, without controlling the world: all 192 calls through D7 in live-04 and all 216 through D8 in live-01 reproduce the recorded actions. This recovers the actual route state, rather than inferring it from daily totals.

In live-04 D7, unit 2 requests five wheat but picks up only two at H1 after earlier workers take four. The tier route advances past that pickup, later consumes its two wheat on other cows, and skips mandatory FEED at cow 46 at H12 and cow 25 at H19. Three wheat are in the shed at those missed visits. Both cows receive CARE, but escape that night. In live-01 D8, the farmer requests three wheat and receives one at H2; it then skips mandatory FEED for sheep 46 at H10. That sheep also receives CARE but escapes. Each animal was placed the preceding day, remains committed in all four available lookahead days, and has no current retirement mapping. These are confirmed execution failures, not deliberate retirement.

The source explains both traces: `_tier_cmd` advances the pickup cursor unconditionally after taking `min(requested, available)` (lines 11717–11724), logs `pick_short`, then later skips a FEED it cannot execute (lines 11813–11816). No refill is scheduled. The recorded live-04 trace also contains repeated one-unit wheat sell/buy requests while the route is short, but this does not establish a material trading-spread loss.

Two bounded continuations preserve the exact action prefix, then activate the existing rolling dispatcher immediately after the observed wheat shortfall. They stop at the next dawn; the opponent continues its recorded actions. All explicit retirement mappings must remain empty in these fixtures. Generic rolling work construction does not itself honor the tier-specific retirement filter, so the production wrapper conservatively defers this recovery on days with an explicit retirement commitment.

| Component continuation | Exact prefix calls | Trigger | Rescued by next dawn | Extra FEED | PASS change | Move change | Own cash change |
|---|---:|---|---|---:|---:|---:|---:|
| live-04 D7 | 170 | H2, after wheat 2/5 | Cows 25 and 46 | +3 | −27 | +18 | −33 |
| live-01 D8 | 195 | H3, after wheat 1/3 | Sheep 46 | +3 | −45 | +31 | 0 |

All three rescued animals are fed and cared for, with zero consecutive unfed nights and one pending care bonus. Reported dispatcher errors, dropped mandatory jobs and calls over one second are zero. Maximum reported post-trigger call time is 156 ms and 143 ms respectively. The live-01 continuation also sells six more milk and two more fertilizer and buys two extra sheep; it changes more than the targeted feeds. These are causal next-morning rescue checks, not full-season profit or responsive-opponent validation.

`stock_recovery_diagnostic_summary.json` records source and output hashes, exact-prefix checks, observed trigger events, animal states, cash/ledger deltas and timing. Its SHA256 is `5dcd0d41427bf37b45376cb14099e1c191ea503168362c9f3ef48ac5f173cbdf`. Raw hourly evidence is in `results/fresh/semantic_strategy_20260928/service_shadows/`. Frozen KB source SHA256 is `2ebe94ece8ef48bf0058e620b5803c11050de7e663a63f4f41522f0758186ee0`.

## Wheat turnover

Fixed B both buys and sells wheat on 120 day/game observations. Stock conservation identifies purchase quantities exactly on 119 of these because the next dawn shed is below capacity; a full shed leaves unknown overflow and only a lower bound. Matching the smaller buy/sell volume at each day's average realized prices covers 769 units and gives buy-price minus sale-price of **−259 total**, about −32 per game. Natural B gives −223 across 877 matched units. This descriptive price comparison is not a causal round-trip estimate, but it provides no evidence that repeated wheat trading itself causes a material spread loss. Gross purchases largely supply feed and should not be reported as avoidable churn costs.

## Next bounded repairs to test

1. Finish the financing ablation with hourly D6–10 own stock, cash and successful-delivery evidence. Earlier actual financing and later purchasing queues must be separated from route capacity.
2. Test the bounded early wheat-shortfall recovery in a separate full-season arm. Keep the original KB frozen, retain observed-unlock dispatch and explicit retirement protections, and report purchasing/production side effects alongside survival.
3. Require a feasible feed visit for retained new animals by the second night. Treat first-day feed/care and late-season retirement as economic choices, not universal requirements.

`scripts/audit_semantic_strategy_service_20260928.py` produces `results/fresh/semantic_strategy_20260928/service_audit_v2.json`, SHA256 `35b6db9b9bf320206153f546c32f4a4ef4faf28e5e55580ff51b68798c1e076c`. It includes all per-game result/action hashes, daily quantity and financing records, cohort-level service evidence, and separate natural/fixed summaries. Fixed experiment manifest SHA256: `7f694b5ccfff4b46584c8a4236666457fba336cd4eedc098f38670c137a23996`. Frozen B candidate manifest SHA256: `c46cfc4b46542640e54af962d326c8af7a6e7c7e407d626f1e0e96027326f52e`. Day-29 service boundaries are censored because those daily logs have no following morning.
