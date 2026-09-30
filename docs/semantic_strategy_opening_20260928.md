# DSM opening and causal strategy data, 2026-09-28

The modern DSM opening is a shared program with spending contingencies, not an identical action tape. Across the current submission's 100 recordings, all actions agree only through step 19. Nevertheless, 95/100 farms reach the same type occupancy on the day-6 morning. That is a useful handoff point for a generated strategy. The common state has ten melons, ten strawberries, two cows and three sheep in the original quadrant.

The older verified corpus contains 144 DSM seats from 143 episodes. Its raw common prefix is only ten steps. This corpus covers multiple opening variants; it should not be described as one fixed board or exact action sequence. All figures below are descriptive source-recording measurements, not newly played candidate games.

| Morning | Modern modal board /100 | Distinct boards | Modern modal daily semantic change /100 |
|---|---:|---:|---:|
| D0 | 100 | 1 | 94 |
| D1 | 94 | 2 | 76 |
| D2 | 82 | 5 | 82 |
| D3 | 86 | 6 | 85 |
| D4 | 91 | 3 | 35 |
| D5 | 95 | 2 | 94 |
| D6 | 95 | 2 | 6 |
| D7 | 6 | 52 | 5 |
| D8 | 7 | 63 | 6 |
| D9 | 11 | 54 | 2 |
| D10 | 2 | 97 | 2 |
| D11 | 2 | 99 | 2 |
| D12 | 2 | 99 | 1 |

Boards mean type occupancy, with weeds treated as empty. Daily semantics include successful planting/removal/building/animal changes, retirement, hires and land. Day-6 change diversity is much greater than day-6 starting-board diversity: expansion responds after the second shop is revealed. Grouping day-6 labels by observed shop prefix raises the within-group modal coverage from 6 to 75 out of 100. This is descriptive in-sample coverage, not held-out predictive accuracy; late prefixes have many nearly singleton groups. Prices and public opponent board histories were not retained in the compact semantic archive, so this report does not claim to explain remaining variation causally.

Cash is tight enough that a borrowed purchase queue is unsafe. In the modern100 recordings, median cash on mornings D1/D2/D3/D4 is 6/1/5/13, with minima 0/0/1/0. D1 contains 979 requested HIRE orders but 410 successful fills; D4 has 758 requests and 502 fills. These are rejected/repeated order attempts, not proof that the eventual daily crew was short. Successful daily hires and physical changes are the training labels.

## Reusable opening

`scripts/semantic_strategy_opening_20260928.py` exposes `make_opening()`. Its result is both callable and has `.act(observation, configuration=None)`. It rejects steps outside 0–143. The whole-agent wrapper takes over on the day-6 morning using the actual observed farm.

This preserves the proven `coherent_opening_v5.SemanticInputPolicy` behavior: normalized successful spending, normalized early pickup quantities, causal purchases before the next planting/feed pickup, native hand/weed/market safeguards and early animal top-ups. Routing can change on day 3. It is therefore intentionally richer than a raw fixed replay.

The sole asset is `data/semantic_strategy/opening_v5_contracts_20260928.json.gz` (1,178,967 bytes). It contains immutable historical policy data, the existing core and verbatim official unit-work helper dependencies. The adapter uses only the standard library at runtime, and does not load rich traces or Kaggle modules. Historical route suffixes remain because early sale guards and animal calendars consult them. Those are training-policy contracts; they are not an evaluated world's future. Environment oracle/research hooks are disabled. The asset's SHA-256 is `f213b2b91be941e05b0f06307a61230af5e4ad502d144407ebefc6df648b16ab`.

`opening_parity.json` records 1,152 hourly saved-observation comparisons from eight source seats, all actions identical to V5, no observation mutation, and a hash check that shared historical inputs remain unchanged. No games were executed for this audit. Cold initialization fell from 1.568 seconds to 0.248 seconds by copying mutable route metadata while sharing immutable action trees. This is local measurement, not an official-runner timing guarantee.

The prior V5 opening qualification and complete-policy limitations remain documented in `docs/coherent_opening_execution_20260924.md`. Successful opening reproduction is not evidence that the new day-6 strategy wins games.

## Causal training rows

`causal_daily_rows.json` contains 3,456 daily rows (D6–29) from 144 verified DSM seats. Features contain only the current morning's crop/species birth counts, own structures, money, land, hands, private seeds/shed/inventories, and already revealed shops. There are no future shop suffixes, source tile coordinates, source IDs, rewards or episode selectors in features. Prices and opponent cohorts are explicitly null because these rich trace files did not retain them.

Targets are successful typed changes and daily hires. They include ending crop/animal counts as conservation anchors. A two-night animal disappearance is labelled as retirement beginning on the first unfed day, separately from physical occupancy loss. This labels observed behavior and does not judge whether retirement was good or bad. Final-day occupancy is the final executed transition; an unexecuted midnight is not invented.

Source identity and provenance live in offline metadata only. `training_episodes.json` lists 143 unique episode IDs, both self-play seats where applicable, source paths/hashes and the model hash. Training excludes all 183 recorded episodes in the new protocol (development8, qualification40, reserve135), plus the previous DSM40, 223 unique IDs total. There is no overlap with either the 144-seat training set or the 112-route opening asset. Episode identity excludes shared-source seat aliases together, and each trace identity is checked against its index.

The modern100 compact recordings are included in `opening_audit.json` only; they have not been silently added to the frozen training model. `scripts/analyze_semantic_opening_20260928.py --audit-only` regenerates descriptive audits without rewriting that model.
