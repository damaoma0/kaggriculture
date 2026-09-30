# Production modules in the full UMG farm

## Decision

**Keep `mgt_m1` as the current agent. The first integrated crop replacement executes correctly but reduces profit relative to the matching tape-holding control.** This completes the bounded integration experiment, not the larger multi-crop planner. No new agent was uploaded.

The earlier isolated experiment showed that leader-derived production cycles could be scheduled. This experiment charges them for real baseline land and existing worker appointments. It demonstrates why an executable production plan is not automatically a profitable replacement.

## What changed

The generated candidates append an overlay to the frozen `agents/mgt_m1.py`:

- Replace at most two planned wheat plantings on elapsed days 12–21, one cycle at a time.
- Reserve the baseline's existing visits before committing: plant and water at age 0, water at age 2, then harvest at age 2 if a later visit exists, otherwise age 3. Output is two carrots. The age-2 schedule comes from the Majkel module; the age-3 fallback is an adaptation.
- Buy one additional carrot seed for each replacement. Existing wheat seed is not treated as a cash saving.
- Preserve movement, hires, animal work and inventory-handling commands. The replacement adds no fertilizer.
- Hold the selected tape through the original wheat's age-4 cycle so its promised future visits remain available. A separate **hold-only control** makes this same intervention without replacing crops.
- Confirm planting from the board and harvesting from inventory changes. Delivery credit cannot exceed observed shed gain. Abort before planting if the tile or seed is unavailable.

The **value-gated** arm also requires an already visible carrot buyer and current prices satisfying `2 × carrot price ≥ 20 + 6 × wheat price`. This is deliberately conservative and does not use future shops. The **off** build is byte-identical to the baseline.

The natural panel's tile audit matches all 32 replacements to actual wheat plantings in the hold-only control. Those wheat cycles produce **164 wheat, or 5.125 per cycle**; the replacements produce **64 carrots, or two per cycle**, and cost an additional $20 seed per cycle. The original wheat seed is not refunded. Earlier harvesting does not compensate here because this version does not schedule a second crop into the freed interval.

This does not yet integrate the fertilized four-carrot UMG module, tomato cohorts, an arbitrary mixture of leaders, or a new multi-worker route optimizer.

## Comparisons

All numbers below are mean changes in final winning margin, measured against the same baseline world. Cash changes and complete records are in `results/fresh/production_modules/integration_findings.json`.

| Test | Forced carrot replacement | Hold-only control | Value-gated replacement |
|---|---:|---:|---:|
| Natural shops, active V48/V50 opponents, 16 games per arm | +1,158.50 | +1,623.38 | 0.00 |
| Baseline shops held fixed, active V48/V50, 16 games per arm | +1,939.50 | +2,443.88 | Not rerun: identical to baseline in the natural panel |
| Recorded ladder opponents, 12 worlds per arm | −361.00 | −80.42 | 0.00 |

**The crop replacement loses to the hold-only control in every compared game:**

- Natural panel: −464.88 margin and −433.88 own cash per game.
- Fixed-shop panel: −504.38 margin and −432.25 own cash per game.
- Recorded ladder panel: −280.58 margin and −222.75 own cash per game.

The natural panel's positive average over baseline comes entirely from one of four seeds. The other three lose money with forced replacement. Holding the tape alone also creates the positive outlier, and its gain remains when shops are held fixed. Thus neither the carrot production nor merely a lucky new shop draw explains that gain; delayed routing and subsequent board/market feedback matter.

The conservative value gate makes no commitments in the natural panel and reproduces all 16 baseline action streams. Its zero delta on the ladder sample is also a no-improvement result, not proof that the gate is optimal. The off build reproduces all 16 natural baseline streams and scores.

Both baseline and all candidates beat the active public opponents in all 16 natural matches. That win count does not distinguish these candidates. On the 12 selected recorded ladder worlds, baseline wins 12; forced and hold-only win 11. Forced replacement worsens all 12 margins. No additional opponent-tape breakage flags or hire-shortfall games were detected.

## Validation and experimental limits

The natural panel uses seeds 172000–172003, both seats, two active opponents and five arms: 80 configurations. The fixed-shop diagnostic uses the same worlds and three arms: 48 configurations. Its baseline reconstructs the original baseline action streams and cash exactly. It forces only the shops; opponents remain active and weeds remain natural.

The ladder diagnostic samples four episodes from each of three stored submission pools using random seed 20260921, selected without reference to outcomes. Its 48 configurations replay the recorded opponent and shop history. These opponents cannot adapt, so this is a diagnostic rather than a new live-ladder score. The selected episode list is saved in `results/fresh/production_modules/ladder_selection.json`.

There are only four independent natural seeds. The seat-swapped results are mirrored, and the two opponents share lineage. Replays for better instrumentation are not new independent tests. These results reject this particular crop swap; they do not reject the broader production-plan approach.

Every active-opponent game uses Kaggle's actual last-callable loader and the official engine, finishes 719 actions with both agents DONE, and reconciles its final cash ledger. Five focused regression checks cover duplicate harvest credit, shed overflow, and same-hour care-slot collisions.

The final engine audit verifies **64/64 replacement cycles**, 32 under natural shops and 32 under fixed shops: exactly one successful carrot planting and two harvested carrots per cycle. No module errors, crop-output mismatches, movement rewrites or hire rewrites were reported. Those are repeated executions across the stated small panels, not 64 independent shop configurations.

The first trace filter mistakenly used a helper clock that stayed at zero, leaving tile-event arrays empty. The filter was corrected to use the actual observation step; unchanged agents were replayed for the tile audit, with assertions that actions and final scores reproduced exactly. Preliminary agent-side harvest confirmation was not used as a substitute for this final engine audit.

## What to keep and what to try next

**Scope correction:** the user's intended next objective is a whole remaining-season production-plan fallback when suitable UMG tapes are unavailable. See `docs/production_plan_continuation.md`. The isolated-cohort suggestion below was a narrower research direction and is superseded by that corrected mission.

Keep the reservation/execution layer and the experimental controls. Do not promote the forced crop rule or the hold-only rule from this sample. The hold-only rule loses in the ladder diagnostic and its natural gain is concentrated in one seed.

The next production-policy candidate should earn more from the reserved capacity: for example, the previously identified demand-conditioned tomato cohort, with its full planting, watering, collection and delivery obligations. A short carrot cycle only creates value from freeing land early if the planner can actually use the freed land and worker visits. This experiment leaves that capacity largely unused.

Before selecting a module, compare its forecast receipts with the measured output of the native crop it replaces, extra seed/fertilizer costs, and any cost of constraining future tape switches. Continue to include a hold-only control and recorded ladder worlds. A mixture of leaders is useful only if those comparisons justify the chosen module in the observed market.

## Artifacts and reproduction

- `scripts/build_mgt_production_modules.py`: asserts the frozen baseline byte hash and builds four ablations.
- `scripts/fragments/mgt_production_modules.py`: bounded overlay and telemetry.
- `scripts/benchmark_production_modules.py`: natural full-farm panel, ledgers and engine events.
- `scripts/benchmark_production_modules_fixed_shops.py`: controlled shop diagnostic.
- `scripts/check_production_module_regressions.py`: five passed regressions.
- `scripts/summarize_production_module_integration.py`: combined panel summary and crop audit.
- `docs/production_module_cost_audit.md`: cheaper-model review of costs and local crop output.
- `results/fresh/production_modules/integration_findings.json`: combined results.

Baseline raw-byte SHA256: `1152ef2e12c4535dbc381b9c54ac7d7a0b1a9ad3d0a8018a7567dcf5c4a52470`. Source-text hashes in individual run records normalize Windows line endings; manifests record raw-byte hashes.
