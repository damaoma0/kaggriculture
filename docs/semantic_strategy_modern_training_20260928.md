# Modern DSM semantic training extension

The separate modern model adds 60 cash-verified DSM recordings, producing 1,440 daily rows for days 6–29. The combined model has 4,896 rows from 204 seats across 203 episode IDs. Extraction takes about 1.8 seconds and executes no environment transitions. The frozen historical model is unchanged.

The source is `data/leader_semantics/16732748/`, matched by episode and seat against `data/leader_tapes/16732748_56498734/`. All 183 recorded development, qualification and reserve episode IDs from the new protocol are excluded, along with the earlier DSM40 panel. Episode exclusion applies across seats and source aliases. The 100-recording source has 60 remaining eligible episodes.

`scripts/build_semantic_strategy_modern_data_20260928.py` reconstructs features solely from prior successful planting, placement and construction, the current morning board and cash, and shops already revealed. Coordinates are discarded after calculating species/birth counts. Past structure kinds distinguish the archive's ambiguous `co` label: an empty coop and a cow have the same board label. All 1,440 feature states match the independent archive adapter's crop cohorts, animal cohorts, structures and owned quadrants.

Current-day hands are zero after the engine's daily reset. Successful daily hires are supervision labels, not features. Prices, private seeds, shed contents, unit inventories and opponent cohorts are unavailable and explicitly null. The source extractor's market, animal purchase and hire-arrival fields have a known day offset; none enters features. Current-day labels use successful changes and observed retirements. Ongoing first-harvest timing is absent. Day 29 has no observed ending boundary, so ending counts and disappearance remain null.

The combined file places modern submission 56498734 first, in ascending episode filename then day order. Historical rows follow in their original frozen relative order. This deterministic family priority makes stable retrieval ties prefer the modern submission; episode IDs remain provenance, not runtime features. Diagnostic row IDs are reassigned consecutively. The historical rows otherwise remain identical.

Files under `results/fresh/semantic_strategy_20260928/`:

- `causal_daily_rows_modern60.json`: SHA256 `92b1cdb7dd60249002e671ac2097d5c3c2c4faf07dce445f570e5314a91e31a1`.
- `causal_daily_rows_204.json`: SHA256 `92fbe42cb66f193472430d835a90d7d9ad8eedfc3ca3058c01915443f4f48083`.
- `training_episodes_modern60.json` and `training_episodes_modern204.json`: explicit training episode lists, source aliases, source hashes and exclusion manifests.
- `modern_training_audit.json`: reconstruction checks, source hashes and missing-field contract.
- `modern_training_quantity_comparison.json`: descriptive day-level medians and means.

Four regression tests pass: restricted-prefix reads, current/future-label poisoning, empty-coop/cow disambiguation, preserved historical rows, complete reserved-ID exclusion and model/manifest hashes. These checks are grouped into four tests in `tests/test_semantic_strategy_modern_data_20260928.py`.

## Descriptive quantity comparison

Values are historical 144-seat median → modern 60-seat median. They describe individual quantities; the vector of marginal medians is not necessarily one recorded plan. These are different world samples and provide no causal performance comparison.

| Successful daily quantity | D6 | D9 | D10 |
|---|---:|---:|---:|
| Wheat planted | 5 → 6 | 14 → 14 | 7.5 → 9.5 |
| Strawberries planted | 8.5 → 9 | 2 → 3 | 1 → 3 |
| Tomatoes planted | 0 → 0 | 0 → 3 | 0 → 1 |
| Cows placed | 4 → 4.5 | 2 → 2 | 0 → 0 |
| Geese placed | 2 → 1.5 | 2 → 3 | 1 → 2 |
| Sheep placed | 0 → 0 | 0 → 0 | 0 → 0 |
| Coops built | 2 → 1.5 | 2 → 3 | 1 → 2 |
| Pastures built | 6 → 5 | 2 → 2 | 0 → 0 |
| Hands hired | 8 → 8 | 10 → 10 | 11 → 11 |
| Ending owned quadrants | 2 → 2 | 3 → 3 | 3 → 4 |
| Morning cash | 765 → 843.5 | 2,014 → 2,292 | 215.5 → 146.5 |

All 60 modern recordings acquire the fourth quadrant on D10, compared with 35/144 historical seats. All acquire their second quadrant on D6. The modern third quadrant arrives on D9 in 59/60 games and on D8 in one. The modern model therefore needs a four-quadrant policy allowance to represent its recorded expansion, plus execution that responds to land unlocking within the day.

Late wheat quantities differ much less: total D21–28 wheat planting averages 54.35 per historical game and 55.73 per modern game. The strongest observed change is the larger D10 farm and its earlier ongoing-crop/geese allocation, not a demonstrated stronger late-wheat response. Performance must be measured with the fixed-world development comparison before any qualification claim.

## Explicit stage-2 reuse extension

After the separate modern60 build was frozen, the parent task authorized using the earlier DSM40 as stage-2 training. Running the builder with `--include-stage1-training` writes separate files and does not overwrite modern60 or either frozen baseline. `causal_daily_rows_modern100.json` contains 2,400 rows and has SHA256 `48a2940a0a7aa23285b046ceb9d203fa255301a7cff390223b94bfda852778d3`; `training_episodes_modern100.json` lists all 100 IDs and source hashes. All 183 new protocol development/qualification/reserve episode IDs remain excluded. The old DSM40 is explicitly marked as training and can no longer be described as independent validation for policies using this extension. All 2,400 morning feature states match the archive adapter. A separate combined244 file is also produced for optional model development.

The day-6 component oracle is separate again: `semantic_inputs_oracle_d6_40.json` contains strict count inputs with only the already-observed D0–5 prefix and D6 initial coordinates. Its future actual counts are intentionally an oracle for component diagnosis, not a new-world causal policy. Its source hashes and original both-seat tape paths are recorded in `semantic_inputs_oracle_d6_40_audit.json`. Two additional regression tests cover reserved exclusion under explicit stage-1 reuse and the day-6 oracle coordinate boundary; all six tests pass.
