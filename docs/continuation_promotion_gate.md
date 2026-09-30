# Required benchmarks for a production-plan continuation

User requirement recorded 22 September 2026: reliably beat the public V56 router and win more than the original UMG tapes. These are promotion requirements, not optional diagnostics. Prediction accuracy, copied harvest counts and aggregate resource feasibility cannot replace match results.

Frozen opponent: [Kaggriculture V56 — Smarter Seeds and Fertilizer](https://www.kaggle.com/code/ahmedberatozer/kaggriculture-v56-smarter-seeds-and-fertilizer), extracted source SHA-256 `a1ad0fd1d174477ee2cbdd561a812bcb7029647ce34599e79d6b79e9057eff6c`. The notebook's declared source hash matched the static extraction. Snapshot and provenance are under `data/router_refresh_20260922/v56/`.

## Primary requirements

1. **V56 head-to-head:** at least 60% win score (win=1, tie=0.5), with the lower end of the two-sided 95% world-cluster bootstrap interval above 50%. Mean final cash margin must also have its lower 95% bound above zero.
2. **Improvement over original UMG tapes:** on a separate matched historical-world panel against the same live V56 opponent, improve win score by at least 5 percentage points and have a paired 95% interval strictly above zero. Also require a positive paired mean-margin interval. Run both literal original tapes and an explicitly labelled, production-preserving opening-repaired control; a gain explained only by an obsolete opening is insufficient.
3. **Current-policy regression control:** on the natural V56 panel, exceed unchanged m1's win score and mean margin with positive paired 95% intervals. Keep its existing file hash fixed.
4. **Execution validity:** every required game must finish normally, reconcile its cash ledger and meet the competition action limit. No silently excluded crashes, missing worlds, mixed code hashes or hand/tile failures attributable to the new compiler. Candidate-caused failures reject promotion.

The 60% and five-point thresholds are an operational definition of the user's requested reliable/material improvement, fixed before viewing the new candidate's qualification results.

## Panels and controls

- **Development only:** 16 natural seeds, 93021000–93021015, both seats. These are for debugging; no promotion claim.
- **Natural qualification:** 128 previously unused seeds, 93022000–93022127, both seats, live V56. Run candidate and frozen m1 separately on the same seed/seat pairs. Preserve ordinary engine randomness. Identical seeds do **not** guarantee identical shop paths after farm actions diverge; record actual paths and report that distinction.
- **UMG comparison:** 64 original UMG episode worlds, balanced across original seats and source versions, forced recorded shop schedules, live V56. In each world, the candidate takes the same seat as the original UMG tape; preserve native-seat order priority and budget conditions. Compare candidate, literal original tape and the opening-repaired tape separately. Freeze episode IDs, tape hashes, source policy versions and the repair implementation before candidate qualification. This is conditional performance on historical worlds, not a claim of defeating UMG's unavailable live policy.
- **Coverage diagnostics:** report each first-shop type, early/late reveal periods, repeated shops, absent-demand products, starting cash, first unavailable tape prefix and the size of the farm-state mismatch. Add a separate stress panel covering all 64 ordered first-two-shop pairs; keep it separate from the natural-distribution win rate.
- **Missing-tape focus:** report the subset where exact UMG continuation is unavailable. Candidate eligibility must be assessed from decision-time state. Gains from the opening or sale wrapper alone do not demonstrate that gap filling improved.

On natural worlds, pair by seed and seat, then bootstrap whole seed clusters. On historical worlds, pair by episode and seat and bootstrap whole episodes. Report wins/ties/losses, win score, mean/median margin, paired differences, 95% intervals, lower-tail losses and errors. Do not pool V56, older public routers and tape opponents into one headline statistic.

Original-tape and candidate runs must face **active** V56. A recorded V56 action stream is suitable only for a separately labelled diagnostic. Full known historical shop paths in the tape baseline favor that baseline; they must never be exposed as observations to the candidate or V56. These historical comparisons do not substitute for the natural qualification panel.

Check raw tape reproduction against its original replay before use. Report first physical-plan divergence and failed-command/fill changes when it faces V56. A final win against a tape broken by the opening is not evidence of outplaying original UMG; use the repaired control and live-opponent natural panel to resolve that ambiguity. See `docs/umg_benchmark_contract.md` for harness and identity details.

## Freeze and decision rules

Freeze candidate/opponent/engine hashes, all panels and all wrappers before qualification. Stop modifying files while worker processes are using them. Complete the predeclared panel even if intermediate results look favorable. If a failed qualification informs a new policy, treat that panel as development and use a new sealed block for the next claim.

Run ordinary official-framework loading and terminal/ledger checks. A local untimed simulator alone cannot establish compliance with action deadlines. The labor module's multi-second offline timings need to be resolved before qualification.

The current continuation research has **not passed these gates**. It contains target generators, aggregate calendars and short diagnostic action transfers. It is not yet an executable new full-season production policy. Qualification begins once the calendar-to-job bridge is integrated.

Machine-readable rules: `results/fresh/tape_gap_plans/promotion_protocol.json`. The 64 historical worlds are now frozen, 16 per UMG source version and original seat, excluding the 105 rich-state donor episodes in the latest production-transfer study. Their membership in the older compact tape library is disclosed; this historical control is not a blind corpus.

`scripts/check_continuation_promotion.py` evaluates normalized match rows against the fixed panels and hashes. It requires **704 qualification matches**: 256 each for candidate and m1 on natural worlds, plus 64 each for candidate, original UMG and repaired-opening UMG on historical worlds. It additionally requires the recorded reproduction, stress, missing-tape and tape-validity reviews. Seven synthetic regression checks cover missing games, duplicate games, mixed builds, policy errors, missing timing validation and gains that do not beat the controls; those synthetic tests are not gameplay evidence.

Gate status in `results/fresh/tape_gap_plans/promotion_status.json` remains **NOT_RUN**. No submission should be promoted on the research results alone.

## Initial development calibration

The unchanged m1 baseline played frozen V56 on seeds 93021000–93021003, both seats. This is an eight-game loading/development check, not qualification. All games finished with 719 actions and both final cash ledgers reconciled through the existing engine harness.

| Seed | First revealed shop | m1 margin in each seat |
|---|---|---:|
| 93021000 | Pet Cafe | −761 |
| 93021001 | Yarn Store | +22,195 |
| 93021002 | Ice Cream Shop | −1,998 |
| 93021003 | Smoothie Shop | −14,072 |

m1 won **2/8**, lost **6/8**, and had a mean margin of **+1,341**. The two seats produced identical outcomes in these four worlds, so these are four independent seed clusters, not eight independent trials. One large winning world makes the mean positive despite losing most matches: this directly motivates requiring a robust win score as well as a positive margin.

Results: `results/fresh/tape_gap_plans/v56_baseline_smoke/summary.json`; runner: `scripts/smoke_frozen_v56.py`. The sealed 93022000 qualification block remains unused. These runs validate that the downloaded opponent loads and plays; they do not establish the new continuation's performance or its runtime qualification.
