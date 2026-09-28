# Bounded optional animal-harvest exchange

This default-OFF component repairs an omitted opportunity in the final polish pass, not a demonstrated loss of existing harvest jobs. The original pass preserves all existing HARVEST actions, but cannot exchange another optional task for an animal HARVEST left in `rest`. No original KB115LT2 file, V12 snapshot, or active candidate was changed.

## Scope and safeguards

`agents/mgt_lead_kb115lt2_harvestx.py` derives from the untouched routefix-fast executor. Set `sd_polish_harvest_exchange=1` to allow one deterministic accepted exchange per day, after final polish. The pass scores at most 96 proposals. It replaces one optional WATER, FERTILIZE, CARE, or COLLECT_FERTILIZER action at an existing visit with a currently valid, positive-valued optional animal HARVEST from `rest`.

It protects mandatory jobs, all FEED and existing HARVEST actions, fixed delivery/placement/build stops, the first real visit, and every retirement tile, including retirement records whose value is false. All route travel and actions must finish by hour 24; fertilizer feasibility cannot worsen. The original harvest value, `0.3 * held units * current price`, must more than offset the original polish score lost from the removed action. This heuristic is an opportunity score, not forecast profit or new physical production.

Storage is a hard restriction. The existing midnight load bound must remain satisfied. The extra lot must reach the shed by automatic midnight transfer: applicable intermediate delivery, DROP, PLACE_HARVEST, or paired delivery rejects the proposal, because route inventory clearing alone cannot establish free intraday shed space. Delivery-pass capacity removals are recorded by tile while the feature is enabled and cannot be resurrected. Old fixtures with untracked delivery deferrals are conservatively skipped.

## Pure validation and captured fixtures

Twelve pure regression tests pass for the direct and runtime-composed executor. They cover OFF parity, retirement and mandatory-job protection, deterministic caps, strict score improvement, time/supply/load constraints, explicit-delivery rejection, and delivery-deferral provenance. No game engine is constructed by these tests.

The four input fixtures come from the independently verified frozen V8 live01 shadow replay: 648 exact actions, both cash ledgers, and all dawn states matched. Three repetitions of each fixture give 12/12 exact OFF output matches and deterministic ON output. Existing mandatory jobs, FEEDs, harvests, and fixed deliveries remain identical.

| Day | ON result | Extra-pass median |
|---|---|---:|
| 7 | No eligible rest harvest | 0.019 ms |
| 12 | No eligible rest harvest | 0.032 ms |
| 18 | One accepted exchange; 34 proposals scored | 1.495 ms |
| 26 | Unknown delivery deferrals; skipped | 0.004 ms |

These are isolated fixture timings, not season runtime evidence. Full-call differences were noise-sized and are not claimed as speed improvements.

On day 18, unit 5 already visits sheep tile 36. The pass replaces its COLLECT_FERTILIZER at hour 7 with HARVEST of four held WOOL at hour 9, moving FEED and CARE from hours 8/9 to 7/8. Every later job keeps its hour: tile 37 collection at 11, tile 57 collection/feed at 14/15, tile 58 wheat plant/water at 17/18, and watering tiles 69/79 at 21/23. Its first cow visit at tile 35 is unchanged. The final route ends at 24.

The modeled gain is 184.8 harvest value minus 48 collection value = 136.8. Projected midnight load changes 79 to 82 under the existing limit of 95, reflecting four wool replacing one fertilizer. The extra wool is scheduled for the day-19 dawn shed. Actual receipt, sales, overflow, and subsequent work are not yet established; a controlled component continuation is prepared separately.

## Source provenance

| Artifact | SHA256 |
|---|---|
| Untouched routefix-fast base | `5c2dfb70eaf68e1b415fe14fd6414774b467afa81b4f66f9d170e792e0dfe833` |
| Harvest exchange source | `69541cff63983f8fa450ee2caa739c8f709dc010beefdbc74b534f3ea4cdc53a` |
| Eval-cache intermediate | `eeb3fd3f2e652a68a5466d9cfd58e3f480b4045ba36771a4fc263e184ff8ecfc` |
| Harvest + runtime caches | `1770e5ab8edf4ae1c7bdd50959349579acba6f1226a0fad8951700e5e4e3119e` |
| Four-fixture evidence JSON | `501861a361b79952c37977d8996df6e2c0eea12ef35c06ec5bcd9e9efeedea66` |

Root's two declared builders compose the cache changes into a new `agents/mgt_lead_kb115lt2_harvestx_fast.py`. Against untouched runtime-fast `d6769c6994a9445f96a34e6c517e4fdee8d3bd3160d349e7d480bdc89871452b`, the only changed existing definitions are `_tier_deliver` and `_tier_polish`; `_tier_harvest_exchange` is the sole added function. The complete AST/hash audit is `results/fresh/semantic_kb115lt2_recovery/harvest_exchange_composition_audit.json`.

## Prepared component control

`scripts/replay_kb115lt2_harvest_exchange_20260928.py prepare` freezes a new executor/driver bundle and binds the exact V8 live01 source actions and candidate manifest. Preparation performs no gameplay. A separately released sole engine slot and at least 2.5 GiB free RAM are mandatory for either run mode.

First run `shadow`: both saved streams are executed through day-20 dawn, while the candidate is invoked with the exchange disabled. Every candidate action before treatment, public/private dawn state, and both cumulative ledgers must match. Only a verified shadow enables `continue`, which turns the exchange on for day 18, off for day 19, and lets the causal candidate act through both days. The rival actions and original shop sequence stay recorded. Actual per-unit sales and midnight inventory transfers/deletions are captured. Failed diagnostics retain a separate failure artifact.

## Controlled component result

The subsequently authorized control and continuation are complete. The control matches all 480 candidate actions through day-20 dawn, observed public/private dawn states and both cumulative ledgers. The treatment matches the first 432 actions, then enables the one exchange at day-18 dawn; it is disabled again on day 19. Both use the original fixed shops and recorded rival actions. No live opponent was invoked.

Only three physical commands change: unit 5 at day-18 hours 7/8/9 changes COLLECT_FERTILIZER, FEED, CARE to FEED, CARE, HARVEST. Every other physical command through day 19 is identical. The planned mandatory-job multisets are identical; all literal mandatory commands execute, including every affected-unit job. Delivery macros on other units expand to ordinary PLACE/DROP commands, and those units' physical streams are unchanged. All crop tiles remain identical at day-20 dawn. Sheep 36 has the same feed/survival/care bank, with held wool 4 versus 0 because the treatment collected it earlier.

The actual day-19 shed contains WOOL 10 versus 6 and FERTILIZER 12 versus 13. Neither side loses any units to midnight overflow on either day. By day-20 dawn, the treatment has sold four more wool and one less fertilizer; all other sold quantities, costs, and physical counts are identical. This is earlier delivery of existing wool, not four additional biological units produced during the test.

Own cash changes 42,685 to 42,739 (+54): wool revenue +83, fertilizer -42, and other price effects +13. Rival cash changes 44,728 to 44,573 (-155), with the same quantities and spending: wool revenue -163 and other prices +8. Competitive margin improves 209 in this short controlled recorded-rival continuation. These figures do not establish a full-season or responsive-rival benefit.

Frozen evidence and hash manifest are under `results/fresh/semantic_kb115lt2_recovery/harvest_exchange_component_v1/`; `audit.json` contains independent action, receipt, crop, mandatory-job and ledger checks. The frozen executor remains `1770e5ab8edf4ae1c7bdd50959349579acba6f1226a0fad8951700e5e4e3119e`. Control elapsed 24.40 seconds and treatment 30.59 seconds include replay and detailed diagnostics; these are not official game runtime measurements.

## Fixed-timestamp revision after independent review

The independent review identified a gap outside the successful D18 route: preserving a fixed delivery's stop and commands does not preserve its hour if an earlier optional action is removed. The new `agents/mgt_lead_kb115lt2_harvestx2.py` rejects a proposal unless every original operation on fixed stops and the first real visit retains its exact reference `_tier_eval(..., want_hours=True)` timestamp. Matching uses operation identity, tile and full command, so duplicate operations cannot hide a shift. The original version and its frozen component evidence remain unchanged.

Composed `agents/mgt_lead_kb115lt2_harvestx2_fast.py` has SHA256 `656fc41fdb3c772e9bd8a13ffedea79c7e8c412acdb4c64218344fa63f082da1`; only `_tier_harvest_exchange` differs from composed v1. Fourteen pure tests pass for both direct and composed variants. One regression demonstrates a profitable-looking exchange that v1 accepts while advancing an earlier DELIVER; v2 rejects it. Another verifies first-visit timestamps cannot shift when a harvest is inserted before existing work.

All four original captured inputs still match the reference exactly with the feature OFF. ON, their resulting farm-planner state, routes, remaining work and selected exchange remain identical to v1, including the actual D18 four-wool route used by the controlled test. The comparison allows rejection-diagnostic differences only. This revision had no additional engine run. Validation and source hashes are saved in `harvest_exchange_fixedtime_audit.json`, SHA256 `847929e0745ac81271f22378293951bdd99e97ed107236c93a4637f84c92017b`.
