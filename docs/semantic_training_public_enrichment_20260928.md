# Modern100 public-state enrichment

Status: exporter and immutable input bundle prepared; source replay is held while the timed V9 live batch runs. No enriched rows have been accepted yet. Local compute only, with a fresh 2.5 GiB available-memory guard and explicit shared-worker coordination.

The authorized source set is exactly the 100 episodes in `training_episodes_modern100.json`. Their original semantic targets come from `causal_daily_rows_modern100.json` (SHA-256 `48a2940a0a7aa23285b046ceb9d203fa255301a7cff390223b94bfda852778d3`). The exporter does not select episodes by outcomes and never opens a reserved recording. The old DSM40 is explicitly reused as stage-2 training, so it is not independent validation for subsequent learned policies.

`scripts/export_semantic_training_public_20260928.py prepare` copied the exporter, frozen V8 public observer and ledger dependency, original rows, authorized source manifest, and all 100 original two-seat tapes plus their compact semantic records into `results/fresh/semantic_strategy_20260928/enriched_modern100_v1/`. Bundle manifest SHA-256: `313485c1f423af470f2d85b68f5a992fdfd2744afc21883938c57be1f4d9e0cc`. Run the frozen `exporter.py` inside that directory. The script verifies every frozen file before accepting work.

Each source replay invokes only both recorded action streams in engine 1.32.7. Recorded shops are enforced in the simulator, while feature extraction sees only the shops already revealed in the current observation. No policy agent or responsive opponent is called. An episode is accepted only after:

- Both final cash totals equal the recorded native rewards exactly.
- Both successful-transaction ledgers reconcile to final cash.
- The environment contains 720 states and both players finish DONE, with 719 action calls each.
- All 24 dawns from D6 through D29 match the previously verified own crop/animal birth counts, structures, cash, land, hands and visible shops.
- All semantic target dictionaries remain unchanged.

`features(observation, memory, policy)` receives only the current actor-visible observation and memory accumulated from previous observations. It cannot see a target row, future board, recording ID, rewards or future shop sequence. The label is attached afterward. It retains the current policy projection plus actual prices, market inventory, own private stocks, rival public cohort counts, and grouped current asset states including held yield, water/fertilizer state, fed/cared status, care bonus and consecutive missed service. Coordinates are discarded by aggregation. Opponent private inventory is never read by feature extraction.

The recent history is exactly the frozen policy observer's public history for `day-3` through `day-1`. It is reconstructed by observing every prior hour, including the dawn transition. Harvest amounts are inferred from same-day public yield changes; they are not verified rival sales. The observer intentionally does not attribute ambiguous combined market transactions to one player, and it does not infer H23 harvests from a transition across midnight. These limitations are preserved rather than filled with private replay knowledge.

Three pure contract tests pass: aggregation drops coordinates and source identifiers, feature extraction ignores future/foreign private fields and selects only past history, and existing-feature comparison permits added current readiness details while rejecting a changed birth or cash value.

Checkpoint commands accept one to ten explicit authorized episode IDs and run them serially. Each passing episode is written atomically under `episodes/<id>.json.gz`; completed episodes are hash-bound to the bundle and skipped on resume. The first intended smoke is the lowest authorized ID, 112562136. Full batches follow only after that source control passes and the V9 worker exits. Existing source files, target rows and previously frozen models remain untouched.

After all 100 controls pass, `finalize` writes a separate `causal_daily_rows_modern100_public_v1.json` and `completion_manifest.json`, with 2,400 feature rows, unchanged targets, source hashes and per-episode validation. No policy training is part of this task.
