# Bounded fixes to existing MGT — September 25

Scope: packaged `submissions/2026-09-24-mgt_v9lite/pkg`, not the separately evolving leader executor. Architecture remains paused. This is a code and saved-evidence audit; no new game benchmark or policy promotion.

Follow-up: the user authorized implementation and testing. The frozen four-arm experiment is in `results/fresh/v9lite_replacement_20260925/`, built by `scripts/experiment_v9lite_replacement.py`. Both historical diagnostics reject the hard replacement guard: mean margin -3,178 versus current V9-lite; wool-upturn alone -10; combination -2,914.5. The guard restores the specific blocked D26 planting but loses more valuable wool. Fresh responsive tests are recorded separately in that experiment. The hypotheses below are research history, not accepted fixes.

## 1. Align route admission with competitive margin

The packaged `_admit` requires positive mean own-cash gain in addition to positive risk-adjusted competitive margin, acceptable downside, full evaluation and cohort protection. That rejects a possible strategy where our cash falls but the rival loses more.

New audit: `scripts/audit_v9lite_fix_candidates.py` reproduced all 339 logged candidate admission flags using the actual packaged pure function. Two log entries (the same apparent scenario, not independent evidence) reject route 147 solely on own cash: mean forecast margin +12,757.75, worst forecast margin +10,097, mean own cash -3,943.5. Route 140 is selected instead. This verifies an active policy restriction, not a realized profit opportunity. Logs include development/runtime runs and are not a random sample.

Proposed isolated challenger: replace the own-cash-improvement veto with actual funding/execution feasibility, retaining protection, downside, risk and complete-evaluation gates. Before testing broadly, compare route 147 and 140 in world 112200188 against native play and a responsive opponent. Recompute the whole selection process: changing admission can change lazy expansion. The prior +8,054 checkpoint ablation in the opportunity audit used an older eight-world selector; do not attribute that gain to current four-world V9-lite.

## 2. Guard animal maintenance against scheduled tile replacement

The y3 top-up calendar tracks FEED, CARE, HARVEST and COLLECT_FERTILIZER; DIG/PLANT replacement intent is not represented in that service set. The extra-service branches do not price the crop replacement that keeping an animal alive can block.

Existing physical evidence: the separate wool-upturn experiment in episode 111261836 kept a sheep on tile (3,4) across a planned D26 wheat conversion and displaced a wool harvest elsewhere; final margin fell 494. This occurred in a micro candidate, not a newly established V9-lite regression. The corresponding risk remains structurally plausible in y3 and must be reproduced there.

Proposed fix: identify explicit scheduled tile conversions from the selected route; compare preservation with retirement before adding FEED/CARE. Preserve profitable final harvests and genuine rescue commitments. Do not simply suppress all late feeding. Validate actual successful conversion, recovered crop output, wages and any animal output lost, then check wins as well as losses.

## 3. Revisit the one-sided wool price forecast, with replacement guard

Packaged y3 still returns `min(today, forecast)` in `_shp_outlook`. Even a predicted recovery after a revealed Yarn Store cannot raise the maintenance valuation above today's quote.

There is already a small isolated candidate, `agents/mgt_micro_wool_upturn.py`, tested against m1: +85 mean margin on 24 held-out seeds, both seats, against responsive V56 (seed-bootstrap interval +7 to +214), with unchanged wins. This is old control evidence, not evidence that combining it with y3/V9-lite improves the current package. Its known replacement regression motivates item 2.

Proposed experiment: freeze current V9-lite and compare separate retirement-guard, wool-upturn and combined arms. Start with the known regression and positive diagnostic, then unused seeds and the 2750–3000 panel. Keep own cash, rival cash, product units, replacement success and wage deltas separate. Stop an arm if it fails to change the intended behavior or causes physical regressions.

## Larger issue to keep bounded

The current rival world model uses recorded, scaled trades and donor future farm snapshots; it does not react to our changed prices by rerunning a rival policy. The saved opportunity audit also contains an incorrectly ranked switch even with true future shops. Thus loosening admission may amplify forecast error. Calibration against existing responsive controls is necessary before promotion; these controls cannot establish competitiveness with today's private 3000+ agents.

Avoid another architecture restart, blanket extra care, indiscriminate additional tapes or headline-score opponent downloads. The recent V9-lite loss audit reproduced 15 losses: 14 had no V9 switch, and its single switch improved the recorded-world counterfactual. That does not support disabling search globally.

Evidence: `results/fresh/v9lite_fix_audit_20260925/admission_audit.json`, `results/fresh/v9lite_diagnosis/report.md`, `docs/mgt_m1_minimal_experiments.md`, `docs/tape_opportunity_audit_20260924.md`.
