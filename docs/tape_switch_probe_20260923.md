# Tape switch failure and transition gate probe — 23 September 2026

## First switch attempt: exact world tape at day 18

The target was episode **110402676**. The current `mgt_m1` route was tape **110063277** at the day-18 boundary. An experimental copy with the existing research hook was forced onto the target world's *own* recorded tape, **110402676**, at day 18. Both arms replayed the same target seed and recorded shop path against the same live rival. The control kept the target tape hidden and used the ordinary router. Both arms had **40,737 cash and the same 73 productive assets** immediately before the switch. This is a selected severe case from prior late-switch results, not a blind estimate of average harm.

| Result | No switch | Forced day-18 switch | Difference |
|---|---:|---:|---:|
| Our final margin | -1,197 | -23,082 | **-21,885** |
| Our final cash difference | — | — | **-15,175** |
| Rival final cash difference | — | — | **+6,710** |
| Flagged invalid tile commands, days 18–29 | 224 | 492 | **+268** |
| Day-21 own cash | 70,674 | 64,320 | **-6,354** |

The command classifier is a precondition diagnostic, not the engine's own no-effect counter. The switch added 65 WATER-on-no-plant flags, 69 HARVEST-on-empty flags, 39 COLLECT-with-nothing flags, 21 FERTILIZE-on-no-plant flags, and 25 FEED-on-no-animal flags. By the next morning the switched farm had 22 rather than 27 strawberry plants and 1 rather than 5 tomato plants. By day 24 it had lost two sheep, two cows and the goose relative to the control. Its eventual sold-unit deficits included 55 wheat, 41 strawberries, 31 tomatoes, 38 wool, 20 milk and 19 eggs. Cash briefly rose on day 19; that did not compensate for the broken production calendar.

The tape's shop match was perfect by construction. The failure came from **the physical program**: animal and crop locations, structures, ages, worker visits and later planting commitments were those of the destination tape, while the live farm was the incumbent's. The destination route therefore addressed the wrong tiles. The two-day visit audit found two animals with incumbent FEED visits but none on the destination tape, three crop tiles losing service, and 21 immediate tile-type mismatches for the destination versus seven for the incumbent. These counts correctly reject this raw switch. A separate positive day-12 case, episode **109827922**, gained **14,573 margin** from a forced switch; its audit found no lost obligations and equal first-day mismatch counts. These two outcome-selected examples show that the audit can distinguish obvious cases, not that its rule predicts all game outcomes.

Prior 64-world hindsight tests in `docs/gap_ceilings.md` found mean gains of **+2,663** for a forced day-12 exact-world switch, then mean losses of **-3,128 at day 15** and **-5,343 at day 18**. The target tape was known only to the retrospective experiment. Those results explain why matching demand alone cannot justify a late raw switch.

## Experimental matcher and what failed

`scripts/tape_switch_admission.py` reconstructs the two route calendars from their recorded actions, compares visits with the live day-boundary assets and flags orphaned feed work, lost crop service and immediate commands aimed at the wrong tile type. `scripts/fragments/tape_transition_gate.py` is the small portable version. `scripts/build_transition_candidate.py` embeds it in a self-contained experimental agent; **`agents/mgt_m1.py` is unchanged**.

The first gate evaluated the top eight nearest tapes from day 12. On seed 174026 it initially missed a damaging day-18 switch because the check omitted placement and long-lived asset identity. After adding those checks, it prevented that switch and improved that particular natural V50 game by 2,635 margin. A four-seed/both-seat V56 development panel was mixed: two seeds unchanged, one +9,049, one -7,111. The regression came from rejecting a productive day-12 choice and selecting another tape.

Moving the gate to day 15 still failed a fresh eight-seed/both-seat V56 panel: mean margin **-550** versus m1, with one seed +12,699, one **-17,105**, six unchanged. In the worst seed the incumbent made a valuable day-15 switch with exact board labels; the gate vetoed it because two-day service counts were different. This shows that missing a recorded service visit does not by itself imply economic harm. Changed actions can also change weed RNG consumption and later shops, so the natural-game deltas are policy comparisons, not isolated switch costs.

The final *selective* candidate evaluates only the best ordinary-router choice, only from day 15, and only when its board Hamming distance is at least three. It never substitutes a lower-ranked “safe” tape. On eight new natural V56 seeds, both seats, **all 16 candidate games were identical to m1**; this provides no performance evidence. In ten historical fixed-shop ladder games where m1 actually made such a late switch, it improved six, worsened four, and averaged **+1,187 margin** on those ten (bootstrap interval **-751 to +3,030**). The fixed opponent does not react; these are already exposed ladder worlds and were selected for the triggering switch. The candidate remains **unpromoted and unsubmitted**.

## Requirements for a low-loss handoff

A reliable selector must compare **complete obligations**, not just shop distance and day-start board labels. A workable admission decision should:

1. Retrieve tapes by revealed demand and the live production calendar: exact animal/crop identity, cohort age, yield held, care bank, fertilizer, worker count, feed/seed/fertilizer stock and funded pending purchases.
2. Project the incumbent and destination from the **same actual checkpoint** through at least the next reveal, including market fills, hires, travel, tile jobs, daily refresh, shed overflow and replacement planting. Price the terminal assets and care banks, not only immediate cash.
3. Build a separate rescue schedule for every incumbent animal and crop that the destination does not service. Reassign tile jobs and market orders from real positions; never replay a destination action against a mismatched coordinate. Reject a switch if the repair displaces a higher-value incumbent job or has no funded, executable continuation.
4. Admit a switch only when the projected demand benefit exceeds transition cost plus uncertainty. If the transition cannot be compiled, keep the current route and adapt production in place. A raw late switch is not an acceptable fallback.
5. Validate a complete game panel against unchanged m1, both seats and live opponents. Keep exact fixed-shop diagnostics separate from natural RNG games. In particular, check the lower tail and productive replacement cohorts; prior three-day continuation work preserved maintenance but lost whole-season crop cycles.

The present visit audit is a fast **screen**, not the projection or repair executor in steps 2–3. It can veto a clearly impossible raw switch, but it cannot yet make a necessary mismatched switch safe.

## Reproduction

The exact-engine replay and precondition trace are in `scripts/probe_late_tape_switch.py` and `results/fresh/tape_switch_probe_20260923/probe-110402676-d18.json`. The visit-audit output is the adjacent `-admission.json`. The positive day-12 probe is `probe-109827922-d12.json`. Natural V56 panels are `results/fresh/selfplay/summary-transition_gate_dev_20260923.json`, `summary-transition_gate_holdout_20260923.json`, and `summary-transition_gate_selective_20260923.json`; source hashes are in their manifests. The final selective source is frozen at `results/fresh/tape_switch_probe_20260923/sources/mgt_transition_candidate.py` (SHA-256 `f834904e96ea60baaca66fa1aea7f87b46ebad0b68051bf6cfaaffbfffd283f6`). The two earlier gate versions have hashes and outcome rows but were not frozen as separate source files, so their exact bytes cannot be independently replayed from this directory. The fixed-shop ladder result files are under `results/fresh/ladder_panel/mgt_transition_candidate/`.
